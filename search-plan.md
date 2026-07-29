# Plan: bedre søgning i Command Center

**Skrevet:** 2026-07-29 af Opus, efter undersøgelse af rådata.
**Til:** en bygge-model (Sonnet eller Codex gpt-5.5 på `medium`).
**Status:** klar til byggeri. Ingen arkitekturvalg er efterladt til udførende model.

---

## Problemet, med bevis

Kristian: *"Jeg kan have svært ved at finde den korrekte chat. For eksempel ved
jeg, at jeg har en chat der omhandler alle mine kvitteringer for ai services.
En anden omhandler min github lukning. Søgefeltet giver mig ikke altid svar,
hvis min søgning er mere vag."*

**Årsag:** søgningen er ét eksakt tekstopslag — `body.find(q)` i
`chatoverblik.py` (`/api/search`-grenen). Ordene skal stå i præcis den
rækkefølge brugeren skrev dem. Frontendens metadata-filter i `filterAndSort()`
har samme fejl: `(s.title||"").toLowerCase().includes(q)` på hele strengen.

**Målt baseline på den kørende server 2026-07-29 (155 chats):**

| Søgning | Træf i dag |
|---|---|
| `github lukning` | 1 |
| `lukning github` (samme ord, byttet om) | **0** |
| `csp onclick` (begge ord findes i samme chat) | **0** |
| `kvittering` | 23 |

At bytte om på to ord fjerner alle træf. Det er selve fælden.

## Den vigtigste indsigt — læs denne før du bygger

Kristians kvitterings-samtale er **ikke en chat om kvitteringer**. Det er
9 beskeder inde i en chat på 1055 beskeder der hedder *"Opret AI-assistent
workspace"* under projektet `Kristians mentor`.

Ingen forbedring af titel- eller resumé-søgning vil nogensinde finde den.
Derfor er **trin 4 (uddrag og spring til stedet) lige så vigtigt som trin 1-3.**
Byg ikke kun rangeringen og kald opgaven løst.

---

## Hvad der skal bygges — fire trin, ét ad gangen, commit efter hvert

### Trin 1 — Del søgningen op i ord, kræv alle, uanset rækkefølge

Både i `/api/search` (server) og i `filterAndSort()` (frontend). En chat er et
træf hvis **alle** søgeord findes et sted i dens felter — ikke som én
sammenhængende streng.

*Acceptkriterium:* `lukning github` giver samme træf som `github lukning`.

### Trin 2 — Match på ordstamme, og fold accenter

`kvittering` skal også finde `kvitteringer`; `lukning` skal finde `lukket`.
Brug præfiks-match: et søgeord på ≥4 tegn matcher et ord i teksten hvis ordet
starter med søgeordets stamme. Ingen rigtig stemmer, intet bibliotek — det er
bevidst. Fold også store/små bogstaver og accenter (`å`/`aa`, `ø`, `æ`).

*Acceptkriterium:* `kvittering` og `kvitteringer` giver samme antal træf.

### Trin 3 — Rangér i stedet for at opremse

I dag returneres træf i vilkårlig rækkefølge. Score per chat:

| Hvor ordet findes | Vægt |
|---|---|
| Titel | 6 |
| Projektnavn | 5 |
| Resumé | 4 |
| Brødtekst | 1 |

Læg vægte sammen per ord, og lad **antallet af forskellige søgeord der er
ramt** veje tungest af alt — en chat der rammer begge ord skal altid ligge over
en der kun rammer det ene, uanset hvor mange gange.

*Simuleret resultat (Opus, 2026-07-29):* `github lukning` giver
`Investiger GitHub-lukning` på førstepladsen med score 14 mod 6 til nummer to.
Det er målestokken.

*Bemærk:* der findes allerede en `searchTier()` i `index.html` og en
tier-sortering i `filterAndSort()`. Byg videre på den — lav ikke et parallelt
system ved siden af.

### Trin 4 — Vis hvor i chatten træffet er

I dag returnerer `/api/search` ét uddrag på ~160 tegn per chat. Når træffet
ligger begravet i 1055 beskeder, er det ikke nok.

- Returnér op til 3 uddrag per chat, spredt over samtalen, med de ramte ord
  markeret.
- Vis dem i chat-rækken (`renderSnippet()` findes allerede).
- Gør det muligt at komme til stedet: chat-modalen har en
  "Vis hele chatten"-udfoldning — spring dertil og fremhæv træffet.

*Acceptkriterium:* en søgning på `kvitteringer` viser uddrag fra selve
kvitterings-passagen inde i `Opret AI-assistent workspace` — ikke bare
chattens titel.

---

## Bindende rammer — brud på disse er en fejl, ikke en afvejning

1. **Ingen cloud-AI.** Søgningen må ikke sende noget til Anthropic eller
   OpenAI. Default-deny (`CLOUD_AI_AUTO_TITLES` + `.command-center-cloud-ai-ok`)
   må ikke røres. Betydnings-søgning med embeddings er **bevidst fravalgt** —
   se afsnittet nederst.
2. **Python stdlib only.** Ingen pip-pakker. Ingen nye JS-biblioteker i
   `index.html` (CSP forbyder alligevel eksterne scripts).
3. **Ingen inline `onclick`** i `index.html`. CSP'en er
   `script-src 'self' 'nonce-…'` uden `unsafe-inline`; inline-handlere bliver
   stille blokeret. Brug `addEventListener`. Der er en test der fanger det:
   `test_no_inline_event_handlers_in_index`.
4. **Rør ikke sorteringen.** `_order`-mekanismen i `filterAndSort()` +
   `renderGrid()` sikrer at projektgrupper ordnes efter nyeste aktivitet og
   ikke efter pin. Under søgning er pin-løftet bevidst slået fra, så
   relevans vinder. Begge dele skal overleve uændret.
5. **GitHub-kontoen er suspenderet.** `git push` fejler med 403. Commit
   lokalt på `dev`, push ikke. Begge repos står allerede foran remote.

---

## Verificering — krav før opgaven må kaldes færdig

Regel 14 i `context/01_arbejdsgang.md`: ingen "det virker nu" uden bevis.

1. **Mål før og efter** med de fire baseline-søgninger i tabellen øverst mod
   den kørende server på `localhost:7777`. Vis begge kolonner.
2. **Ingen tabte træf:** kør alle fire søgninger plus mindst 5 egne, og
   bekræft at intet der blev fundet før, forsvinder.
3. **Regressionstests:** `python3 -m unittest discover -s tests` skal være
   grøn (14/14 i dag). Tilføj tests for ordrækkefølge, ordstamme og rangering.
4. **Browsertest under den faktiske CSP:** `tests/test_b1_csp_browser.mjs`
   viser mønsteret. Kræver kørende server + `npx playwright install chromium`.
   Konsollen skal være fri for CSP-fejl.
5. **Genbyg release-pakken til sidst:** `python3 scripts/build_release.py`,
   derefter `python3 scripts/release_check.py`. Checket **fejler med vilje**
   hvis zippen ikke er genbygget efter en kildeændring — det er ikke en fejl i
   dit arbejde, det er gaten der virker.
6. **Kristians egen kontrol:** han søger efter sine kvitteringer og sin
   GitHub-lukning i browseren og bekræfter at han finder dem. Serveren skal
   genstartes for Python-ændringer. Brug **almindelig Safari/Chrome**, ikke
   web app'en fra Dock — den cacher aggressivt (se `LESSONS.md`).

---

## Hvad der bevidst IKKE skal bygges

**Ægte betydnings-søgning** (embeddings — der forstår at "lukning" og
"suspenderet" er det samme). Cloud ville sende indholdet af 155 chats afsted og
bryde default-deny. En lokal model ville være en ny afhængighed i et projekt
hvis pointe er at det bare virker uden installation. Fravalgt af Kristian
2026-07-29 efter fremlæggelse.

**"Spørg AI hvilken chat"-knap** (sender kun 155 titler + resuméer, ca. 30 KB,
gennem den eksisterende bekræftelses-dialog). Holdt i baghånden hvis
ordsøgningen ikke rækker. Byg den ikke uopfordret — og bemærk at den ikke ville
have løst Kristians eget kvitterings-eksempel.

---

## Kendt sidespor, ikke en del af denne opgave

Mappen `Masterversioner/Kvitteringer på AI services/` findes på disken, men
**ingen chats er tildelt den** — alt kvitteringsarbejdet ligger under
`Kristians mentor`. Derfor hjælper projektfilteret ikke. Nævn det for Kristian,
løs det ikke her.

---

## Filer du skal kende

| Fil | Hvad |
|---|---|
| `chatoverblik.py` | `/api/search`-grenen, `build_search_index()` |
| `index.html` | `filterAndSort()`, `searchTier()`, `renderSnippet()`, `chatRow()` |
| `tests/test_p0_hardening.py` | regressionstests (14 i dag) |
| `STATUS.md` | projektets tilstand — opdatér ved milepæl og ved sessionsslut |
| `LESSONS.md` | fælder i netop dette projekt — læs før du fejlsøger |
