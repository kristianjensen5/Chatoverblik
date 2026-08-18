# Lærte lektier — Command Center (Chatoverblik)

Projekt-specifikke fælder. Globalt relevante lektier kopieres også til
`Masterversioner/context/05_lessons.md`.

---

## Et fast `sleep` er ikke en synkronisering — find programmets eget klarsignal

**Problem:** Ét klik på "åbn projekt" i Command Center gav tre fejl på én gang:
en Claude-fane landede i et ANDET allerede åbent projekt, et tomt sort
VS Code-vindue åbnede, og det rigtige farvede vindue kom uden chat. Det lignede
tre uafhængige bugs.

**Årsag:** Én fejl. `/api/open-in-windsurf` startede VS Code med `code -n` og
ventede så et fast `time.sleep(0.8)` før den fyrede `vscode://`-URI'en, der
åbner chatten. macOS sender sådan en URI til det vindue der er forrest netop
dá. Efter ét sekund er det nye vindue ikke oppe — så kommandoen ramte det gamle
projekt (fejl 1), eller ankom før noget vindue kunne tage imod den, hvorefter
VS Code åbnede et tomt vindue for at håndtere den (fejl 2). Fejl 3 var bare
følgen: chatten var landet et andet sted.

**Bevis frem for gæt:** `logs/subprocess.log` har tidsstempler på hver kommando,
og Claude-udvidelsen skriver en lock-fil til `~/.claude/ide/` når den er klar.
Sammenholdt viste de, at URI'en var 2, 11, 20 og 23 sekunder for tidlig i fire
af fire målte åbninger. Uden den sammenstilling ville "vinduet er nok klar efter
0,8 sek." have lydt rimeligt.

**Fix:** Vent på programmets EGET klarsignal i stedet for på uret:

```python
def _wait_for_ide_ready(workspace_root, since_ts, timeout=45.0, interval=0.4):
    target = _norm_path(workspace_root)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if target in _ide_lock_workspaces(min_mtime=since_ts - 2):
            return round(time.time() - (deadline - timeout), 1)
        time.sleep(interval)
    return None
```

Og — vigtigere end selve ventetiden — **fyr ingenting hvis signalet udebliver.**
Den gamle kode fyrede altid; det var dét, der gjorde en timingfejl til en fane i
det forkerte projekt. Ingen chat er et ærligt resultat, en chat i et fremmed
projekt er ikke.

**To fælder i selve signalet:**

1. **Lock-filens alder svarer ikke på "er det åbent nu".** Udvidelsen skriver
   filen én gang ved opstart og rører den aldrig igen, så et vindue der har
   stået åbent siden i går, har en lock-fil fra i går. Første udkast brugte en
   24-timers grænse og ville have ventet forgæves på præcis de vinduer, der var
   åbne. Brug i stedet processens liv (`os.kill(pid, 0)`) — en lock-fil fra et
   lukket VS Code peger på en død proces.
2. **Danske mappenavne matcher ikke sig selv.** macOS blander NFC og NFD, så
   `drømmeverden` kan være kodet på to måder, der ser ens ud på skærmen og er
   forskellige strenge. Normalisér begge sider med
   `unicodedata.normalize("NFC", …)` før sammenligning, ellers fejler netop de
   projekter der har ø, æ eller å i navnet.

**Dato:** 2026-08-18

---

## En Map bygget fra en sorteret liste arver rækkefølgen fra det SIDSTE sorteringstrin

**Problem:** Projektlisten på forsiden stod i forkert rækkefølge, selvom
"Senest aktive" var valgt. Kristians mentor — brugt samme dag og hele den
foregående uge — lå på 4. plads, mens MacGameBridge (ikke rørt i en uge) lå
nr. 3. Samme symptom inde i en projektgruppe: en chat fra 4 uger siden lå
over en fra 1 minut siden.

**Årsag:** `filterAndSort()` sorterer korrekt efter nyhed, men kører DEREFTER
et sidste, separat sorteringstrin der løfter pinnede chats (★) til toppen.
`renderGrid()` grupperede så efter projekt med `new Map()` — og en Map
bevarer insertion-order. Grupperne blev dermed oprettet i den rækkefølge
deres første chat optrådte, altså efter pin-løftet. Tre gamle pinnede chats
(Chatoverblik 22/6, Generelle spørgsmål 18/6, MacGameBridge 9/6) trak hele
deres projekt op i toppen. Pin-løftet var designet til at gælde *inde i* en
gruppe, men fik utilsigtet lov at bestemme rækkefølgen *mellem* grupperne.

**Fix:** Notér hver chats plads i rækkefølgen FØR pin-løftet (`s._order = i`),
og sortér grupperne efter den laveste `_order` i gruppen — ikke efter Map'ets
insertion-order:

```js
// i filterAndSort(), lige før pin-sorteringen:
xs.forEach((s, i) => { s._order = i; });

// i renderGrid(), efter grupperne er bygget:
const groupRank = new Map();
for (const [proj, items] of groups) {
  groupRank.set(proj, Math.min(...items.map(s => s._order ?? Infinity)));
}
const orderedGroups = [...groups.entries()]
  .sort((a, b) => groupRank.get(a[0]) - groupRank.get(b[0]));
```

Fordi rangeringen aflæses af den allerede sorterede liste og ikke af et
hårdkodet tidsstempel, følger gruppe-rækkefølgen automatisk med, uanset hvilken
sortering brugeren vælger (nyeste/ældste/oprettet) og uanset søge-tiers.

**Dato:** 2026-07-21

---

## Et værktøjs egne interne dokumenter kan ligne brugerens beskeder i logfilen

**Problem:** 14 chats i "Kristians mentor" hed alle `stærkt tak`, og flere
projekter havde samme mønster. Det lignede et navngivningsproblem — måske
udløst af at chatten var startet uden om Command Center.

**Årsag:** Noget helt andet. Codex skriver sit eget godkendelsesdokument
("The following is the Codex agent history whose request action you are
assessing…") ind i rollout-filen som et almindeligt `event_msg` /
`user_message`. Dokumentet er 80-90 KB og indlejrer hele transskriptet fra en
tidligere samtale. `is_bootstrap_message()` kendte kun fem præfikser og
genkendte det ikke, så det blev læst som brugerens første besked. Og
`clean_user_text()` gjorde det værre: den klippede efter det FØRSTE
`"My request for Codex:"` uanset hvor i teksten det lå — dybt inde i det
indlejrede transskript — og hev dermed et stykke af en fremmed samtale ud som
titel. Fordi de samme transskripter går igen, blev titlerne identiske.
Målt: 30 af 163 rollout-filer bar dokumentet, og **29 af dem indeholdt ikke én
eneste besked brugeren selv havde skrevet**. Det var ikke chats med dårlige
navne — det var spøgelser der aldrig havde været samtaler.

**Fix:** (1) Genkend dokumentet i `_BOOTSTRAP_PREFIXES`, så det hverken bliver
titel eller tælles som brugerbesked — en fil uden brugerbeskeder falder så
automatisk ud som "ikke en chat". (2) Klip kun efter `"My request for Codex:"`
når beskeden faktisk ÅBNER med en kendt indpakning (`_IDE_WRAPPER_PREFIXES` —
målt til præcis tre former på 250 filer). (3) Tjek råteksten for
bootstrap-mønstre FØR oprensning i `response_item`-fallbacken; oprensningen
fjerner netop det kendetegn vi genkender dokumentet på.

**To generelle regler:** En logfil fra et AI-værktøj indeholder både det
brugeren skrev og det værktøjet skrev til sig selv — antag aldrig at
`role: user` betyder "et menneske skrev det". Og en markør må kun bruges til at
klippe i tekst, når man har bekræftet at teksten ER af den form markøren hører
til; ellers rammer man tilfældige forekomster i citeret eller indlejret indhold.

**Sidegevinst:** de ramte chats sendte 80 KB fra et ANDET projekt med i
AI-titel-payloaden. En mentor-chat bar indhold fra "Kvitteringer på AI
services". Filteret lukker også det.

**Verificering:** parseren kørt mod alle 163 rigtige Codex-filer og alle 32
Claude-filer før og efter. Resultat: 29 forsvinder, 0 dukker uventet op, 0
overlevende chats skifter titel eller tælling, Claude-siden helt uændret.

**Dato:** 2026-07-29

---

## En kode-gate kan overvurdere en fejl lige så let som at overse den

**Problem:** Release-gaten (2026-07-12) udpegede B1 med tre symptomer, alle
læst ud af koden: 📋 Kopiér sti er død, OG hvert klik på en projekt-header-knap
(📖/📄/📱/↗/📁) folder hele projektgruppen sammen, OG url-chips gør det samme.
Projektet blev pauset i en uge på den vurdering. En browsertest under den
faktiske CSP viste at kun det FØRSTE symptom var ægte.

**Årsag:** CSP blokerer ganske rigtigt de tre inline `onclick`. Men de to af
dem (`event.stopPropagation()` på url-chip og på `.proj-header-actions`) var
allerede overflødige: den delegerede `addEventListener` på knapperne kalder
selv både `stopPropagation()` OG `preventDefault()`
([index.html:2003-2005](index.html#L2003-L2005)). Og det er `preventDefault()`
— ikke `stopPropagation()` — der forhindrer `<summary>`-elementets
foldnings-adfærd, fordi foldning er en *aktiverings-adfærd*, ikke en
almindelig event-handler. Gaten læste "inline onclick bliver blokeret" og
sluttede "altså går funktionen tabt", uden at spørge om noget andet allerede
dækkede den.

**Fix:** Alle tre attributter fjernet og erstattet af `addEventListener`. To
guards, så hullet ikke kan genopstå:
`tests/test_b1_csp_browser.mjs` (Playwright mod den kørende server under den
rigtige CSP) og `test_no_inline_event_handlers_in_index` i
`tests/test_p0_hardening.py` (billig regex-guard, negativ-kontrolleret).

**Lektien:** en read-only gate leverer *hypoteser*, ikke fund. Kør den
billigste test der kan afkræfte hver enkelt, FØR du planlægger efter dem —
også når gaten er kørt af en dyb model. Her kostede det en uges pause på to
symptomer der ikke fandtes.

**Dato:** 2026-07-29

---

## Verificér frontend-sortering mod ægte data — ikke mod kodelæsning

**Problem:** Sorteringsfejlen ovenfor var usynlig ved at læse koden; hvert
enkelt sorteringstrin så korrekt ud isoleret. Det var samspillet mellem dem
der var forkert.

**Årsag:** Rækkefølgefejl viser sig først når man ser den faktiske rækkefølge
på faktiske data. Samme proces-hul som B1 (CSP-testen tjekkede kun CSP-teksten,
ikke at appen kørte under den).

**Fix:** Hent rådata fra det kørende endpoint (`curl localhost:7777/api/sessions`),
klip de RIGTIGE funktioner ud af `index.html` med `sed` på linjenumre, og
`eval` dem i Node med en minimal `state`-stub. Så testes den kode der faktisk
er i filen — ikke en genskrivning der kan indeholde de samme fejl som
udviklerens forståelse. Erstatter ikke Kristians egen browser-bekræftelse
til sidst, men fanger fejlen før den vises frem.

Én fælde i stub'en: `state.selectedCwd` skal være `""`, ikke `null` — koden
tester `!== ""`, så `null` filtrerer alt væk og giver et falsk "0 chats".

**Dato:** 2026-07-21
