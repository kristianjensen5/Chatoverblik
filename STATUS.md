# Command Center (Chatoverblik) — Status

**Type:** privat (workflow-værktøj, men bruges til arbejdsprojekter)
**Tilstand:** aktiv
**Data:** kildemateriale — indirekte, men reelt. Appen læser HELE chat-historikken
fra `~/.claude/projects/` og `~/.codex/sessions/`, og de chats kan indeholde
journalistisk kildemateriale. Intet af det ligger i repoet: `cache.json`,
`analysis.md` og `logs/` er gitignorerede og verificeret utrackede. Men uddrag
SENDES til Anthropic ved AI-titler, resumé, workflow-analyse og ugens retro —
og taksonomiens række "Kilde-noter" i `08_repo_politik.md` siger *"kun lokale
værktøjer, cloud-AI ikke"*. Modforanstaltningen er, at hvert eneste cloud-AI-kald
kræver en eksplicit godkendelse, hvor den fulde payload vises på skærmen først
(`require_ai_confirmation`, uden undtagelser). Åbn aldrig et endpoint der springer
den over.
**Live URL:** http://localhost:7777 (lokal kun)
**GitHub:** `kristianjensen5-projekter/Chatoverblik` (eget nestet repo)
**Senest opdateret:** 2026-09-08 (Manifest-arbejdet fra 26.-27. august er nu
committet sammen med en testrettelse — to commits, der venter på push. De to
tests, der stod noteret som fejlende, er verificeret grønne: 38/38. Intet er
pushet eller distribueret.)

---

## De to "fejlende tests" og rodens .gitignore (2026-09-08)

En tidligere session efterlod to punkter under "mangler". Begge er lukket, men
den ene viste sig at være to forskellige ting.

- ✅ **`test_sensitive_ai_chat_requires_payload_confirmation`** var en ægte
  fejl. Race-fiksen i `33b6c63` (2026-08-13) gav `require_ai_confirmation` en
  fjerde returværdi, men testen pakkede stadig kun tre ud og fejlede med
  `ValueError: too many values to unpack (expected 3, got 4)`. Selve
  bekræftelsen var uændret — kun testens kald var bagud. Rettet i `6451c02`.
- ✅ **`test_release_check_passes_and_blocks_legacy_artifacts` var aldrig i
  stykker.** Den kræver `release/Chatoverblik-current.zip` på disken, og den
  fil er gitignoreret. Den består derfor lokalt og fejler i enhver frisk klon.
  Se "Kendte problemer".
- ✅ **Regressionstest:** 38/38 bestået med
  `python3 -m unittest discover -s tests`. Bemærk: testene er `unittest`, ikke
  pytest — pytest er ikke installeret på nogen af maskinens Python-versioner,
  så `python3 -m pytest` fejler misvisende med "No module named pytest".
- ✅ **Releasepakken er aktuel.** `release/Chatoverblik-current.zip` (27. august
  09:09) er verificeret byte-identisk med den nuværende kildekode på alle fem
  tekstfiler, og indeholder kun de syv manifestfiler — ingen `cache.json`,
  `analysis.md`, `logs/` eller interne noter. Stadig ikke godkendt til
  udlevering; gates fra pause-checkpointet står ved magt.
- ✅ **Rodens `.gitignore` er lagt om til deny-by-default** (`d458aa4` i
  Masterversioner-repoet). Den var en manuelt vedligeholdt navneliste på 143
  linjer, og 22 projektmapper stod uden for den — `git add .` i roden ville
  have taget 2.191 filer med, heriblandt `Hackerman/` og
  `Kristians privater serverkontrol/`. Nu ignoreres alt på topniveau, og kun
  eksplicit whitelistede mapper er synlige. Målt: 2.191 → 12 filer, 79 trackede
  filer uændret, 0 sletninger. Lektien ligger i `context/05_lessons_fuld.md`.

**Rettet antagelse:** briefet fra sidste session anførte, at commits `38a2600`,
`e11db0f` og `babd728` var fra samme dag som klarsignal-arbejdet. De er fra
**18. august**. Manifest-arbejdet fra 26.-27. august var altså nyere end dem —
det er grunden til, at zip'en bygget 27. august stadig matcher kildekoden.

---

## Manifeststyret projektoprettelse (2026-08-26)

Den hidtidige formular havde sin egen forældede startprompt og kendte ikke den
centrale context-routing. Det gjorde Command Center til en parallel regelkilde.

- ✅ `chatoverblik.py` læser nu `../context/manifest.json` og vælger både
  `always`-regler og de dokumenter, der matcher projektets type,
  leveringsform, data og eksterne services.
- ✅ Formularen indsamler klassifikationen samt dagens mål, færdigbevis og
  bindende ramme. Den første prompt genereres af backenden, ikke af en
  hardkodet JavaScript-kopi.
- ✅ Nye projekter får `STATUS.md`, `README.md`, `.gitignore`, `AGENTS.md`,
  `CLAUDE.md` og `LESSONS.md` fra de kanoniske templates. Der oprettes ikke
  længere automatisk en `index.html`, fordi ikke alle projekter er websites.
- ✅ Eksisterende filer overskrives ikke. Manifest og alle templates valideres,
  før en ny mappe oprettes. Nye projekter bygges i en stagingmappe og flyttes
  først på plads, når alle filer er skrevet; eksisterende projekter bruger
  eksklusiv filoprettelse uden overskrivning.
- ✅ Startprompt og projektinstruktion bruger absolutte stier til den centrale
  bootstrap og de routede filer. Unicode-navne normaliseres, og en eksisterende
  selvstændig `CLAUDE.md` udløser konflikt i stedet for parallelle regler.
- ✅ Regressionstest: 38 Python-tests bestået. Browserkontrol bestået på
  desktop og 390 px mobil; ugyldig `../`-sti blev afvist uden filoprettelse,
  submitknappen blev genaktiveret efter fejlen, modal-scroll og bredde bestod,
  og browserkonsollen var uden warnings eller errors.
- ✅ `release/Chatoverblik-current.zip` er genbygget og valideret lokalt.
  Pakken er ikke publiceret eller distribueret.
- ✅ Kollegapakken indeholder bevidst ikke Kristians private context. "Nyt
  projekt" skjules derfor automatisk, når en komplet lokal
  `context/manifest.json` ikke findes; de øvrige værktøjer påvirkes ikke.
- ✅ Den normale proces på port 7777 er startet 2026-08-27 og svarer med
  `project_setup_available: true`.

---

## Hvad er det?

Lokal webapp ("Command Center") der scanner alle mine Claude- og Codex-chats fra
~/.claude/projects/ og ~/.codex/sessions/, viser dem grupperet per projekt med
AI-genererede titler (eller VS Codes egne ext_labels), og fungerer som central
indgangsvinkel til mine projekter. Også et workflow-værktøj med analyse,
genoptag-guide, ugens retro, og nyt-projekt-flow.

---

## Status lige nu

### Fungerer i produktion
- ✅ Scanner 115+ chats fra både Claude og Codex
- ✅ AI-genererede titler + resuméer (cached i cache.json)
- ✅ Læser VS Codes egne titler fra workspaceStorage som primær kilde
- ✅ Sidebar med Alle chats / Favoritter / Korte chats / Aktivitet
- ✅ Sammenfoldelige projekt-grupper i hovedpanelet med URL-chips (LIVE/GitHub)
- ✅ Søgning i titler + body-content (fulltext)
- ✅ Pin/favorit, omdøb, slet chat
- ✅ Per-chat: "Find chatten i VS Code"-flow med QR-relevant info
- ✅ Per-projekt: 📖 Genoptag-guide (AI-genereret HANDOVER.md), 📱 Mobile Preview (QR-kode), ↗ VS Code, 📁 Finder
- ✅ Værktøjer: 📊 Workflow-analyse, 📅 Ugens retro, 🆕 Nyt projekt
- ✅ Server-health badge med animeret Command Center-ikon (rødt lys blinker når live)
- ✅ Persisterede UI-præferencer i localStorage
- ✅ Path-baseret detektion af projektmappe (fanger 44 chats der skulle ligge under undermapper i stedet for Masterversioner-roden)
- ✅ Safari web app med custom ikon
- ✅ Rebrandet fra "Chatoverblik" → "Command Center" i UI

### Projekt-dashboard "Status på mine projekter" (2026-07-02)
Bygget efter plan fra Opus (`dashboard-plan.md`), trin 1-8 udført af Sonnet,
ét trin ad gangen med commit efter hvert (8 commits i Chatoverblik + 1 i
Masterversioner-roden for `/luk`-ændringen).

- ✅ **Ny knap "📊 Projekt-status"** i Værktøjer-sektionen åbner et bredt
  modal med ét kort pr. mappe i Masterversioner (60 kort: rod + 59
  undermapper minus infrastruktur-skipliste).
- ✅ **5 statuslamper pr. kort** (grøn/gul/rød/grå): Sikret (har mappen et
  git-remote — "Mistet Mac"-testen), Ændringer (ucommittet?), Pushet (foran
  sidst-kendte remote?), Deployet (git-tag `deployed` peger på HEAD?),
  STATUS.md (findes + < 30 dage gammel?). Se `dashboard-plan.md` afsnit 1
  for præcis lampe-logik.
- ✅ **`GET /api/repo-status`** — separat on-demand-endpoint (IKKE på
  4-sekunders-pollingen), 60-sek. in-memory cache, ↻-knap kan bypasse med
  `?force=1`. Ingen `git fetch` — måler kun mod lokalt kendt remote-state.
- ✅ **`git tag -f deployed HEAD` tilføjet til `/luk`-skillen** (efter et
  vellykket deploy) — datakilden til Deployet-lampen. Indtil et projekt får
  sit første `/luk`-deploy efter denne ændring, viser lampen ærligt
  rødt/gråt for det projekt (ikke en bug).
- ✅ Verificeret: unit-tests mod scratch-repos for alle lampe-tilstande,
  Playwright-browsertest af den kørende server (grid renderer uden overlap,
  sortering med alarmer øverst, ↻-knap virker, ingen JS-fejl ud over kendt
  font-CORS på localhost).
- ✅ **Kristian testede live og gav 3 runder feedback — alle rettet samme dag:**
  - ✅ Label-overlap (lampe-tekst flød sammen uden mellemrum): `min-width:0`
    + `overflow-wrap:anywhere` på lamp-label, ny dedikeret `--lamp-gray`
    (var for tæt på kortets egen kant-farve), større prikker med kontur.
  - ✅ Udfoldelig hjælpeboks ("▸ Hvad måler de 5 lamper?") — forklarer hver
    lampe + hvad hver farve betyder for netop den, da hover-tooltip alene
    ikke var tydeligt nok.
  - ✅ Filter over grid'en: **Alle / Seneste 20 / Grønne (færdige) / Mangler**.
    "Seneste 20" bruger nyt `last_commit_ts`-felt (`git log -1 --format=%ct`)
    i `git_status_for()`. Ren client-side filtrering af allerede hentet data.
  - ✅ Lamper forstørret 13px→18px + kort gjort bredere (240px→270px min,
    færre kolonner) for bedre overblik.
  - ✅ **"↗ VS Code" / "📁 Finder"-knapper på hvert kort** — genbruger
    eksisterende `/api/open-in-windsurf` + `/api/open-in-finder`. Kristian
    kan nu klikke sig direkte ind i et problem-projekt og rette det derfra
    (selve commit/push/deploy sker fortsat kun efter hans eget OK i den
    session — dashboardet auto-fixer intet).
- Fase 2 (Cloudflare-API som ægte-live-bekræftelse for de 6
  wrangler.toml-projekter) er bevidst udskudt — se `dashboard-plan.md` trin 9.

### Sorteringsfix i projektlisten (2026-07-21)
Kristian meldte at "Senest aktive" ikke afspejlede virkeligheden: Kristians
mentor — brugt samme dag og hele ugen — lå nr. 4, mens MacGameBridge (urørt i
en uge) lå nr. 3. Samme symptom inde i en projektgruppe.

- ✅ **Root cause:** `filterAndSort()` sorterer korrekt efter nyhed, men kører
  derefter et sidste trin der løfter pinnede chats (★) til toppen.
  `renderGrid()` grupperede så med `new Map()`, som bevarer insertion-order —
  grupperne arvede altså rækkefølgen fra pin-løftet, ikke fra nyheds-
  sorteringen. Tre gamle pinnede chats (Chatoverblik 22/6, Generelle
  spørgsmål 18/6, MacGameBridge 9/6) trak hele deres projekt op i toppen.
- ✅ **Beslutning (Kristian):** ★ skal kun påvirke rækkefølgen INDE i et
  projekt. Projekt-rækkefølgen bestemmes udelukkende af nyeste aktivitet.
- ✅ **Fix:** `s._order = i` noteres før pin-løftet
  ([index.html:1761-1764](index.html#L1761-L1764)); grupperne sorteres efter
  laveste `_order` i gruppen ([index.html:1876-1885](index.html#L1876-L1885)).
  Følger automatisk med når brugeren skifter sorteringsvalg eller søger.
- ✅ **Verificeret:** de faktiske funktioner klippet ud af `index.html` med
  `sed` på linjenumre og kørt i Node mod 184 rigtige chats fra
  `/api/sessions`. Resultat: projekter i faldende nyhedsorden, pinnet chat
  stadig øverst inde i sit eget projekt. Kristian bekræftede derefter selv i
  browseren at rækkefølgen er rigtig.
- ✅ Logget i ny `LESSONS.md` + `context/05_lessons.md` (fælden er generel:
  insertion-order i en Map er ikke en sortering, det er et biprodukt).
- ⚠️ **B1 er IKKE rørt** i denne session — den står fortsat åben, se nedenfor.

### Projekt-åbning venter nu på VS Codes ægte klarsignal (2026-08-18)
Kristian meldte tre fejl ved ét klik på "åbn projekt": en Claude-fane landede i
et ANDET allerede åbent projekt, et tomt sort VS Code-vindue åbnede, og det
rigtige farvede vindue kom uden chat — han skulle stadig selv ind i
Chats → Claude → ny samtale.

- ✅ **Root cause, målt:** endpointet ventede et fast `time.sleep(0.8)` efter
  `code -n` og fyrede så `vscode://`-URI'en. Sammenholdt `logs/subprocess.log`
  med mtime på Claude-udvidelsens lock-filer i `~/.claude/ide/`: URI'en var
  **2-23 sekunder for tidlig i 4 af 4 tilfælde**. Den gik derfor til det vindue
  der tilfældigvis var forrest. Loggen havde oven i købet en `osascript`-fejl
  `-609 Forbindelsen er ugyldig` — VS Code svarede ikke, fordi den stadig startede.
- ✅ **Fix:** `_wait_for_ide_ready()` venter på udvidelsens eget klarsignal — en
  lock-fil med projektets sti. Kommer det ikke inden for 45 sek., **fyres
  INTET**. Bedre ingen chat end en chat i det forkerte projekt.
- ✅ **"Er projektet allerede åbent" afgøres af processens liv, ikke filens
  alder.** Udvidelsen skriver lock-filen én gang ved opstart og rører den aldrig
  igen, så et vindue der har stået åbent siden i går, har en lock-fil fra i går.
  Første udkast brugte en 24-timers mtime-grænse og ville have fejlet på præcis
  det. Fanget i review før test.
- ✅ **Første besked sendes med i linket** (`?prompt=`, verificeret i
  udvidelsens `extension.js` → `createPanel(session, prompt)`). Chatten åbner
  med teksten klar. Kun Claude — Codex' URI-format kan ikke bære den. Loft på
  8000 tegn, clipboard beholdt som fallback.
- ✅ **UI-rækkefølgen gjort synlig** efter Kristians spørgsmål "hvilken
  rækkefølge skal jeg trykke i?": "↗ VS Code" starter nu også en tom Claude-chat
  (hans valg), tooltip'en der påstod "med Claude klar" uden at starte en chat er
  rettet begge steder, og genoptag-forløbet er nummereret Trin 1-3 af 3.
  Numrene vises kun dér — godkendelses-panelet bruges også af analyse/retro/titler.
- ✅ **De to identiske kopier af knap-logikken samlet** i
  `openProjectFromButton()`. De lå på projekt-headeren og på dashboard-kortene.
- ✅ **Verificeret:** 10 tests i `tests/test_ide_ready.py` (klarsignal for sent,
  aldrig, forældet, dansk NFD/NFC-mappenavn, død/levende proces),
  `node --check` på hele UI-JavaScriptet, `py_compile`, og et realdata-tjek mod
  Kristians faktiske vinduer. Kristian bekræftede live at fejlene udeblev.
- Plan: `aabne-projekt-plan.md`. Commit `38a2600`, pushet til `dev`.
- ✅ **Kristian har testet hele kæden 2026-08-18 og bekræftet alle fire dele:**
  tooltip'en, den tomme chat via "↗ VS Code" (Commander Keen 6), trin 1-3 i
  genoptag-forløbet, og at briefet står klar i chatfeltet (Tingfinder) uden at
  han skulle paste noget. Loggen viste **33 sekunders ventetid** på Keen 6 —
  med den gamle kode ville kommandoen være fyret 32 sekunder for tidligt.
- **Ikke en fejl, men værd at vide:** VS Code genskaber selv det layout du
  forlod et projekt med — Codex-panel, Explorer, åbne filer. Den tomme chat
  kommer altså oveni det, du havde åbent sidst. Vi har bevidst IKKE tvunget et
  fast layout frem; det ville også smide layouts væk som Kristian gerne vil have.

### "Resumé" betød to forskellige ting i UI'et (2026-08-18)
Under testen ledte Kristian efter genoptag-briefet og landede på "↻ Ny AI-titel",
fordi chat-vinduets felt hed **Resumé** og teksten dér pegede på netop den knap.
To ting, ét ord.

- ✅ Feltet hedder nu **Kort beskrivelse**, med en forklarende under-linje
  ("den ene linje der vises i listen og bruges i søgning").
- ✅ Begge knappers tooltips siger nu eksplicit, hvad de IKKE er:
  "↻ Ny AI-titel … Har intet med Fortsæt i ny chat at gøre."
- ✅ `CLOUD_AI_SKIPPED_NOTE` omformuleret tilsvarende. **Fælde undgået:**
  `isSkipNote()` i frontend'en genkender noten med et regex, og noten gemmes i
  `cache.json`. De gamle formuleringer er derfor BEVARET i regex'et, så
  tidligere scannede chats stadig vises neutralt. (Målt: 0 chats i cachen bar
  den gamle note, men mønstret koster intet og beskytter mod chats uden for
  cachen.)
- ✅ Søgefeltets placeholder siger nu "beskrivelser" i stedet for "resuméer".

### Bedre søgning med uddrag og hop til træf (2026-07-29)
Bygget efter `search-plan.md`, fire trin med lokal commit efter hvert trin.
Ingen cloud-AI, ingen nye app-afhængigheder, ingen inline `onclick`, og
projekt-/pin-sorteringen er bevaret.

- ✅ **Søgeord deles op og kan stå i vilkårlig rækkefølge.** `github lukning`
  og `lukning github` giver nu samme træf.
- ✅ **Danske bøjnings-/accentformer matches uden eksterne biblioteker.**
  `kvittering` og `kvitteringer` giver samme antal træf; `lukning` finder også
  `lukket`; `å/aa`, `ø/oe`, `æ/ae` foldes.
- ✅ **Søgning rangeres efter relevans.** Vægte: titel 6, projekt 5, resumé 4,
  body 1, og antal ramte søgeord dominerer score. `github lukning` placerer
  `Investiger GitHub-lukning` øverst med score 14.
- ✅ **Body-træf viser op til 3 uddrag pr. chat.** Uddragene kommer fra de
  faktiske beskeder og har `message_index`, så et klik åbner "Vis hele chatten",
  scroller til beskeden og fremhæver søgetermerne.
- ✅ **Kristians kvitterings-eksempel er dækket.** `kvitteringer` viser uddrag
  fra `Opret AI-assistent workspace` under `Kristians mentor`, bl.a. passagen
  "jeg har nu tilføjet 44 kvitteringer fra open ai..." inde i den lange chat.
- ✅ **Verificeret:** efter-tal på kørende server: `github lukning` 53,
  `lukning github` 53, `csp onclick` 7, `kvittering` 26 (156 chats inkl. den
  aktive Codex-session). Lokal før/efter-simulation viste `lost 0` for alle
  fire baseline-søgninger og mindst fem ekstra søgninger. Regression: 18/18
  unittests OK, `py_compile` OK, CSP-browsertest 5/5 OK, release-check OK efter
  genbygget `release/Chatoverblik-current.zip`.

### B1 lukket + release-check udvidet (2026-07-29)
Blocker B1 er rettet og verificeret i en rigtig browser under den faktiske
nonce-CSP — det bevis der manglede hele vejen igennem.

- ✅ **Alle tre inline `onclick` er væk fra `index.html`** og erstattet af
  `addEventListener`: 📋 Kopiér sti wires nu efter hver `setServerHealth()`-
  render, og `stopPropagation` på url-chips + `.proj-header-actions` sker i en
  delegeret listener i `renderGrid()`.
- ⚠️ **Gaten overvurderede B1.** Baseline-testen FØR fixet viste at kun ét af
  de tre påståede symptomer var ægte: 📋 Kopiér sti var reelt død, men
  projekt-header-knapperne og url-chips foldede **ikke** gruppen — den
  delegerede knap-handler kaldte allerede både `stopPropagation()` og
  `preventDefault()`, og det er `preventDefault()` der stopper `<summary>`-
  foldning. De to inline-attributter var altså død kode, der kun larmede i
  konsollen. Logget i `LESSONS.md` + `context/05_lessons.md`.
- ✅ **Verificeret (regel 14):** `tests/test_b1_csp_browser.mjs` (Playwright mod
  den kørende server) — 3/5 før fixet, **5/5 efter**: header-knap folder ikke
  gruppen og åbner Filer-modalen, url-chip folder ikke gruppen, 📋 Kopiér sti
  lægger den rigtige sti i udklipsholderen, og konsollen er fri for
  CSP-violations (2 før fixet).
- ✅ **Proces-hullet er lukket permanent** med to guards: browsertesten ovenfor
  + `test_no_inline_event_handlers_in_index` i `tests/test_p0_hardening.py`
  (billig regex-guard, negativ-kontrolleret: den fejler faktisk hvis en inline
  `onclick` genindføres).
- ✅ **Release-checket validerer nu disk-artefaktet.** Nyt `check_disk_artifact()`
  i `scripts/release_check.py` sammenligner hvert medlem i
  `release/Chatoverblik-current.zip` byte for byte med kilderne. Kørt mod den
  gamle zip FØRST: den fejlede korrekt med `disk artifact is stale`. ZIP'en er
  genbygget fra manifestet; checket er nu OK.
- ✅ Regressionstests: **9/9 OK** (`python3 -m unittest discover -s tests`),
  `python3 -m py_compile chatoverblik.py` OK.
- ⚠️ **Stadig ikke GO til distribution:** næste skridt er en ny uafhængig
  read-only P0-gate og derefter colleague-readiness-gaten. Del intet endnu.

### Spøgelses-chats og fastlåste "cloud-AI sprunget over"-noter (2026-07-29)

**A. Fravalg af cloud-AI blev gemt som om det var et svar.**
- ✅ Noten `(Cloud-AI ikke sendt automatisk…)` blev skrevet ind i `cache.json`.
  Da cachen tjekkes før alt andet, ville de ramte chats beholde noten for
  evigt — også efter cloud-AI blev slået til. 26 chats var ramt.
- ✅ **Fix:** fravalget cachet ikke længere; gamle poster renses ved
  serverstart (`drop_cached_skip_notes()`), og kun `title`/`summary` fjernes —
  `user_title`, `pinned` og `user_cwd` røres ikke. `enrich_with_ai()` bruger nu
  "mangler AI-titel" i stedet for "mangler cache-post", så en pinnet eller
  omdøbt chat også kan få titel senere.
- ✅ Noten er neutral i UI'et i stedet for at ligne en fejl, og siger hvad man
  skal gøre. **Default-deny er urørt** — ingen chat sendes uden aktivt klik.

**B. 29 spøgelses-chats i oversigten.** Kristian meldte at mange chats havde
fået samme navn (14 stk. hed `stærkt tak`) og gættede på at det skyldtes chats
startet uden om Command Center. Det var det ikke.
- ✅ **Root cause:** Codex skriver sit eget godkendelsesdokument ind i
  rollout-filen som et almindeligt `user_message`. Det indlejrer hele
  transskriptet fra en tidligere samtale, så titlen blev klippet ud af midten
  af en fremmed samtale — og fælles transskripter gav identiske titler.
  30 af 163 filer bar dokumentet; **29 af dem indeholdt ikke én eneste besked
  Kristian selv havde skrevet.** Se `LESSONS.md`.
- ✅ **Fix:** dokumentet genkendes i `_BOOTSTRAP_PREFIXES`; `clean_user_text()`
  klipper kun efter `"My request for Codex:"` når beskeden faktisk åbner med en
  kendt indpakning (`_IDE_WRAPPER_PREFIXES`); `response_item`-fallbacken tjekker
  råteksten før oprensning.
- ✅ **Sidegevinst (privatliv):** de ramte chats bar 80-90 KB fra et ANDET
  projekt rundt i AI-titel-payloaden. Filteret lukker også det.
- ✅ **Verificeret:** parseren kørt mod alle 163 Codex-filer og alle 32
  Claude-filer før og efter. 29 forsvinder, 0 dukker uventet op, 0 overlevende
  chats skifter titel eller tælling, Claude-siden helt uændret. Chat-tallet
  falder fra 184 til ca. 155.
- ✅ Regressionstests: **14/14 OK** (5 nye siden 21. juli).
- ✅ **Bekræftet efter Kristians genstart 2026-07-29:** 184 → **155 chats**,
  0 røde cloud-AI-noter (var 26), 0 "stærkt tak"-dubletter (var 14).
- **Bevidst ikke gjort:** de 29 forældede poster i `cache.json` ryddes ikke.
  De læses aldrig (chatten findes ikke længere), og en oprydningsrutine kunne
  ved en delvis scanning komme til at slette `user_title`/`pinned` for en chat
  der bare var midlertidigt uskannet. Risikoen er større end gevinsten.

### P0-hardening baseline (2026-07-11)
Fokuseret sikkerheds-sprint uden nye dashboard-/UX-features. Dokumenteret i
`P0_HARDENING.md`.

- ✅ **Kollegadistribution har én source-of-truth:** `release_manifest.json` +
  `scripts/build_release.py` + `scripts/release_check.py`. Den gamle
  `../Chatoverblik-dist` og `../Chatoverblik-1.0.zip` registreres som
  blokeret legacy og må ikke blive current-pakken.
- ✅ **Eksekverbar tredjepartskode fjernet fra localhost-origin:** eksterne
  jsdelivr-script-tags er fjernet fra `index.html`; appen serveres med
  nonce-baseret CSP, API-svar med `default-src 'none'`, og preview har separat
  låst CSP.
- ✅ **Central canonical-path-validator:** `validate_canonical_path()` bruges
  nu af file-tree, file-content, move-chat og preview. Den blokerer traversal,
  secrets, datafiler, rå chats/logs/cache og kildenote-mapper.
- ✅ **Cloud-AI er default-deny:** en `ANTHROPIC_API_KEY` sender ikke længere
  automatisk chats. Automatisk AI-titelgenerering kræver både
  `COMMAND_CENTER_AUTO_AI_TITLES=1` og projektmarkør
  `.command-center-cloud-ai-ok`. Manuelle AI-knapper viser præcis payload og
  kræver aktiv bekræftelse før cloud-send.
- ✅ **Regressionstests committed:** CSRF, gammel RCE-rute, path traversal,
  secret/data/source-note denylist, følsom AI-chat og distributionspakken.
- ✅ Verificeret lokalt: `python3 -m py_compile ...`,
  `python3 -m unittest discover -s tests -v` (8 tests OK),
  `python3 scripts/release_check.py --json` (OK, legacy blokeret).

### Uafhængig release-gate (Opus, 2026-07-12) — NO-GO til P0-godkendelse
Read-only gate af P0-sprintet. **Sikkerhedssubstansen bestod alt:** RCE væk (ingen
`shell=True`/`os.system`/`open-in-terminal`, alle subprocess list-form), CSRF +
5 MB body-cap ægte og håndhævet i `do_POST`, central `validate_canonical_path()`
brugt af file-tree/file-content/move-chat/preview (resolver symlinks → escape
dækket, traversal + secrets/CSV/data/kildenoter blokeret), cloud-AI default-deny
(auto kræver env-flag + `.command-center-cloud-ai-ok`; manuel kræver
SHA-256-payload-bekræftelse → følsom chat sender 0 tegn), 8/8 tests OK,
`release_check.py` OK, release-zip **byte-identisk reproducerbar** fra manifestet
(kun de 7 tilladte filer), legacy blokeret.

**Blocker B1 (skal fixes før pilot):** Den nye `script-src 'self' 'nonce-{nonce}'`
(uden `unsafe-inline`/`unsafe-hashes`) blokerer 3 inline-`onclick` i `index.html`:
- [index.html:1897](index.html#L1897) + [index.html:1890](index.html#L1890):
  `proj-header-actions` / url-chips mister `stopPropagation` → **hvert klik på
  en projekt-header-knap (📖/📄/📱/↗/📁) folder samtidig hele projektgruppen.**
- [index.html:1590](index.html#L1590): 📋 Kopiér sti-knappen (server-nede-badge) helt død.
- **Root-cause i proces:** CSP-testen tjekker kun CSP-*teksten*, ikke at appen
  kører under den (regel 14-hul — ingen browser-smoke-test af CSP-ændringen).
- **Fix:** 3 `onclick` → `addEventListener`/delegering (som resten af appen),
  derefter én browser-test der bekræfter: klik header-knap folder IKKE gruppen,
  og console er fri for CSP-violations. Så er det rent GO.

**Ikke-blokerende noter ved pausen:** (1) `release_check.py` bygger sin egen
in-memory-zip og validerer ikke selve disk-artefaktet
`release/Chatoverblik-current.zip`. (2) `INSTALL.md:151` undersælger
default-deny. (3) `README.md` er stadig en stub. (4) Kildenote-detektion er
navne-/mappe-baseret; en løs kilde-note `.md` i en projektrod uden
"kilde"/"source" i navnet ville kunne vises. Den tidligere misvisende legacy-
tekst under "Vigtige filer" er rettet i pause-checkpointet nedenfor.

### Pause-checkpoint (Kristian + Codex, 2026-07-12)

Projektet er **bevidst pauset**. Git stod ved pausen på `dev`, commit `5a5e161`
(`Harden command center baseline`); eneste lokale ændring er denne `STATUS.md`
(Opus-gate + dette handoff). Der er ikke lavet nyt commit, push eller deploy herfra.

- **Må ikke deles nu:** Det eksisterende
  `release/Chatoverblik-current.zip` er bygget før B1 er rettet og er derfor
  NO-GO. Det skal genbygges og kontrolleres igen efter fixet.
- **Første og eneste kodeopgave ved genoptagelse:** Ret B1's tre inline
  `onclick`, og verificér under den rigtige CSP i browseren. Bland ikke de
  øvrige reviewspor ind i samme fix.
- **P0-GO er ikke automatisk pilot-GO:** Opus-gaten var afgrænset til P0-
  hardeningen. En kollegapilot kræver bagefter en kort, separat readiness-gate
  for tre stadig kodeverificerede workflowproblemer:
  1. **Installation/bootstrap:** Nyt-projekt-flowet kan stadig skrive en tom
     STATUS hvis `context/06_status_template.md` ikke findes, opretter en svag
     `.gitignore`, hardcoder `Masterversioner` og udelader obligatorisk
     `context/08_repo_politik.md` (`chatoverblik.py:2709-2740`,
     `index.html:2887-2903`).
  2. **Dashboard-sandhed:** "Sikret" beviser kun at et remote-navn findes,
     "Pushet" bruger kun lokalt kendt upstream, STATUS-lampen ser kun på dato,
     og "Grønne (færdige)" accepterer grå/ukendt (`chatoverblik.py:711-733`,
     `chatoverblik.py:779-812`, `index.html:3217-3236`).
  3. **Kollegadokumentation:** `README.md` er stadig en stub, INSTALL har
     modstridende cloud-AI-tekst, og en frisk installation i en vilkårligt
     navngivet projektrod er ikke verificeret end-to-end.

**Genoptagelsesbevis før deling:** B1-browsertest består uden CSP-fejl → alle
regressionstests består → disk-artefaktet genbygges fra manifestet og valideres
direkte → uafhængig P0-gate siger GO → readiness-gaten ovenfor siger GO →
Kristian laver manuel smoke-test. Først derefter må én kollega få ZIP-filen.

### Næsten færdig
- ⏳ Mobile Preview backend virker — men netværks-isolation på Politiken-WiFi blokerer iPhone fra at nå Mac. Skal testes hjemme på privat WiFi.
- ✅ **Etape 2 af "drøm-workflow" — i mål med små caveats:**
  - ✅ Per-projekt `.code-workspace`-fil genereres i `Chatoverblik/.workspaces/` (skjult)
  - ✅ Hver workspace har sin egen Peacock-farve inline (Hulemanden=orange, GriseCounter=grøn, MacGameBridge=lilla, osv.)
  - ✅ `code -n <ws-file>` — hver fil er unik workspace-identity → nyt VS Code-vindue per projekt
  - ✅ Døde `--command`-args fjernet; VS Code åbnes direkte med `code -n <ws-file>`
  - ✅ Chat-extension åbnes eksplicit efter workspace-aktivering: **Claude** via URI-handler og **Codex** via URI-handler
  - ⚠️ Begge AI-extensions loader som tabs i secondary sidebar uden vi kan "switche" — det er Kristians sidebar-bredde der afgør om begge er synlige eller skjult bag "..."-menu
  - Workspace Trust skal accepteres første gang per workspace for farve at vises

### Nyere features (juni 2026)
- ✅ **WIDGETS.md viewer/editor** — knap i Værktøjer-sektionen, modal med markdown-render + redigeringstilstand med backup ved hver gem
- ✅ **Code viewer / file browser** — 📄 Filer-knap på projekt-overskrifterne. Tre-kolonne layout: filtræ til venstre, syntax-highlightet kode til højre (Prism.js, supporterer HTML/CSS/JS/Python/JSON/Markdown/Bash mfl.). Sikkerhed: kun filer under kendte projekt-cwds, max 500KB, skipper støj (node_modules, __pycache__ osv.)
- ✅ **Flyt chat til andet projekt** — 📁 Flyt-knap i chat-modalen, dropdown med ALLE Masterversioner-undermapper (inkl. tomme). Bruger `user_cwd`-override i cache.json uden at røre selve jsonl-filen
- ✅ **Auto-åbn workspace-root** — `find_workspace_root()` scanner opad fra cwd til nærmeste CLAUDE.md/AGENTS.md, så Claude/Codex finder chat-historikken korrekt
- ✅ **Per-projekt Peacock-farver via `.code-workspace`-filer** — hver projekt får sin egen workspace-identity og farve. Genereres i Chatoverblik/.workspaces/
- ✅ **Nyt projekt-flow** — første-besked-prompt der tvinger AI'en til at læse CLAUDE.md, STATUS.md, WIDGETS.md + bekræfte memory. Claude/Codex extension-vælger inkluderet

### To åbn-bugfixes (2026-06-23)
Test afslørede at "Åbn i VS Code" landede i forkert workspace. Opus-debug fandt **to separate bugs**:
- ✅ **Forkert mappe (data):** `detect_subfolder_from_paths` skubbede en chats cwd ned i en under-undermappe når stien blev nævnt ≥5 gange (sker konstant via tool-kald), mens kortets navn altid beregnes på projekt-niveau. Resultat: kort hed "LæsernesVerdenskort" men knappen åbnede `/widget`-undermappen (også ideerogtests/`scripts` ramt — systemisk). Fix: ny `project_root_from_cwd` normaliserer cwd op til projekt-roden (Masterversioner+1), så åbnet mappe altid matcher kortets navn. Bonus: ingen dobbelt-kort, URL/fil-scan kører nu på projekt-roden.
- ✅ **Forkert vindue (race):** `osascript activate` fyrede øjeblikkeligt efter `code -n`, før det nye vindue var oppe → rev et andet allerede-åbent vindue i front. Fix: activate sker nu KUN i new-chat-flowet; almindelig åbning lader `code -n` styre fokus selv.
- Fjernet 2 forældreløse cache-workspace-filer (`widget`, `scripts`).

### Workspace-fix + genoptag-titel (2026-06-22)
- ✅ **Genoptag-chat-titel forkortet** til `G: <projekt>` (før: "Genoptag chat fra projekt: X" der blev afkortet til ens-udseende titler i Claude/Codex' sidebar)
- ✅ **Workspace-tildeling rettet** — Opus-audit fandt at `find_workspace_root` scannede opad efter CLAUDE.md, men kun 3 af 61 projekter har deres egen, så de resterende 58 åbnede hele Masterversioner-roden i stedet for projektmappen. Forværret af at kun genoptag-knappen sendte `keep_cwd`, så resultatet afhang af hvilken knap man klikkede, og `.code-workspace`-filen flip-floppede. Fix: `workspace_root = cwd` altid; `find_workspace_root` + `keep_cwd` fjernet helt. Alle fire åbn-flows (Åbn-knap, chat-modal, genoptag, nyt projekt) lander nu konsistent i selve projektmappen. Stale workspace-filer selv-healer ved næste åbning.

### Ultra-review-fixes (2026-06-04 + 2026-06-05)
Multi-agent kode-review (`ULTRA_REVIEW.md`) fandt 15 fund — alle nu lukket eller eksplicit udskudt. Distribueret over 6 PR'er på `dev`-branchen:

- ✅ **PR 1** sikkerhed: RCE i open-in-terminal fjernet, CSRF-check på alle POST, path-traversal i file-content/file-tree lukket, 5MB body-cap
- ✅ **PR 2** quickwins: `file_to_open` NameError, `_TAG_BLOCKS` permissions-regex, `_serve_preview` query-string, weekly-retro timezone
- ✅ **PR 3** data-sikkerhed: `STATE_LOCK = threading.RLock()` + cache-merge i stedet for overwrite → pin/rename overlever cold-start AI-køen
- ✅ **PR 4** UX: polling skipper når bruger-mutationer er in-flight + triggerer fresh poll efter mutation → ingen "spring tilbage" på rename/pin/delete
- ✅ **PR 5** multi-user: `MASTERVERSIONER_ROOT = HERE.parent` (afledt), preview-token (1-times TTL) erstatter base64-cwd, project-handover validerer mod root. Plus `get_local_ip()` foretrækker LAN frem for VPN-tunnel (QR'en pegede tidligere på VPN-IP)
- ✅ **PR 6** tech-debt (merget): `call_anthropic()` helper samler 4 kopier af urllib-kode, `openModal()` collapse 8 kopier af modal-skelet, visibility-aware polling (stopper når fanen er skjult)
- ✅ **PR 7-8** docs + 🚀 Genoptag-chat: INSTALL.md til kolleger, `/api/resume-summary`-endpoint der genererer AI-brief af en gammel chat til indsætning i ny chat

### Genoptag-chat verificeret (2026-06-10)
- ✅ **🚀 Genoptag virker end-to-end** — testet live mod kørende server: `/api/resume-summary` returnerer `ok: True` med korrekt markdown-brief (bruger `call_anthropic()`-helper fra PR 6, default-model `claude-sonnet-4-6`). Frontend-felterne (`summary`/`project`/`model`) matcher response. Ingen reel bug tilbage — punktet manglede kun verifikation

### Ikke startet
- ❌ Per-projekt LESSONS.md-viewer
- ❌ Curated terminal-knapper (deploy, git status osv.) — overvejes som næste step
- ❌ Migration af min Chatoverblik-kode til politiken-widget Cloudflare-konto (afventer redaktør-svar)
- ❌ **Udskudt fra ultra-review:** cwd-felt-konsolidering (`cwd`/`original_cwd`/`cwd_hint`/`user_cwd` → ét felt + source-tag), split preview-listener på separat port, inline-styles → CSS-klasser. Ingen distribution-blockers.

---

## Fable-audit 2026-06-12: stabilitet som primær indgang

Mål: Command Center skal være den stabile, primære indgang til at kode i
VS Code. Auditten fandt to rod-årsager til Kristians ustabilitets-oplevelse
— begge verificeret med kommando-output, ikke antagelser.

### Fund A — "Åbn i VS Code" åbner aldrig chat-extensionen

`do_POST /api/open-in-windsurf` (chatoverblik.py ~linje 1598-1624) sender
`--command claude-vscode.sidebar.open` m.fl. til `code`-CLI'en. **VS Code
CLI 1.124 har intet `--command`-flag** (verificeret med `code --help`
2026-06-12) — flagene ignoreres, og fejlen er usynlig fordi stderr sendes
til DEVNULL. Linje 45-46 i denne fil påstod at kæden virkede ("Codex virker
via chatgpt.newChat") — det blev aldrig verificeret end-to-end og er forkert.

### Fund B — Nye chats vises først efter server-genstart

`background_load()` (linje 1160) kører ÉN gang i en tråd ved serverstart.
Frontend poller `/api/sessions` hvert 4. sekund (index.html linje 3060), men
serveren genscanner aldrig `~/.claude/projects/` eller `~/.codex/sessions/`.
Pollingen serverer altså den samme døde STATE — nye chatvinduer i VS Code
dukker først op når serveren genstartes.

### Fix-liste til Codex (prioriteret — ét trin ad gangen, commit per trin)

1. ✅ **Rescan-loop (Fund B):** daemon-tråd der hvert ~20.-30. sekund kører en
   inkrementel scanning (kun jsonl-filer med mtime nyere end sidste scan),
   merger ind i STATE under `STATE_LOCK`, og kun AI-beriger NYE sessioner
   (cache dækker resten). Plus `/api/rescan`-endpoint + ↻-knap i UI til
   manuel fuld genscanning.
   *Acceptkriterium:* start en ny chat i VS Code → den vises i Command
   Center inden 30 sek. uden server-genstart; eksisterende titler, pins og
   omdøbninger overlever.
   *Verificeret 2026-06-12:* Ny Codex-chat med titlen `Test af rescan-loop`
   dukkede op i Command Centers `/api/sessions` uden server-genstart
   (`129 chats`, status `Klar`).
   *Testdefinition:* "Ny chat i VS Code" betyder en ny samtale i Claude- eller
   Codex-sidebaren via `+` / New Chat / New Conversation, efterfulgt af én
   sendt besked. File-menuens `New File`, `New Text File` og `New Window`
   opretter ikke en AI-chat og tester derfor ikke rescan-loopet.
2. ✅ **Synlige subprocess-fejl:** erstat `stderr=subprocess.DEVNULL` med
   append til `logs/subprocess.log` i alle `subprocess.Popen`-kald.
   *Acceptkriterium:* et bevidst forkert CLI-flag efterlader en linje i
   loggen.
   *Verificeret 2026-06-12:* `logged_popen(["python3",
   "--definitely-wrong-command-center-flag"])` skrev kommando + Python-fejl
   til `logs/subprocess.log`.
3. ✅ **Extension-åbning (Fund A):** fjern de døde `--command`-args. Test
   derefter løsninger i denne rækkefølge, og stop ved første der virker:
   (a) tjek om Claude-/Codex-extensionerne har en auto-åbn/startup-setting
   der kan embeddes i den genererede `.code-workspace`-fil (eleganteste —
   ingen timing-problemer); (b) test `code -n <ws> --agents`-flaget (nyt i
   VS Code, "Opens the agents window"); (c) test URI-handler:
   `open "vscode://anthropic.claude-code"` o.l.; (d) osascript-keystroke
   (Cmd+Esc for Claude) efter activate + delay — kræver
   Accessibility-tilladelse; (e) hvis intet virker: vis toast i CC
   "Vinduet er åbnet — tryk Cmd+Esc for Claude" og dokumentér begrænsningen
   her i STATUS.md.
   *Acceptkriterium:* "Nyt projekt → åbn i VS Code (claude)" ender med et
   vindue HVOR chat-panelet er synligt uden manuelle klik — eller en ærlig
   toast, hvis (e) blev endestationen.
   *Verificeret 2026-06-13:* (a) ingen brugbar Claude startup-setting; (b)
   `code -n <ws> --agents` åbnede kun et generisk Agents-vindue; (c) virker
   med rækkefølgen `code -n <workspace>` → aktivér VS Code →
   `vscode://anthropic.claude-code/open`. Kristian verificerede, at
   Pauseklovnen-workspace åbner med synlig Claude Code-fane uden manuelle
   klik. Follow-up verificerede samme eksplicitte URI-flow for Codex med
   `vscode://openai.chatgpt/`: Pauseklovnen-workspace åbner med synligt
   Codex-panel.
4. ✅ **Ret linje 45-46 i denne fil** så de matcher virkeligheden efter trin 3.

### Kristians end-to-end-sluttest 2026-06-13 (regel 14-kvittering)

1. ✅ **Rescan:** nyt projekt dukkede op i Command Center kort efter — uden
   server-genstart.
2. ✅ **Claude-åbning:** rette workspace + rette chat åben, ingen manuelle klik.
3. ⚠️ **Codex-åbning — delvist:** rette workspace + synligt Codex-panel, men
   den KONKRETE chat åbnes ikke — panelet viser Sessions-listen, hvor chatten
   ligger øverst (ét klik fra mål).

**Accepteret begrænsning (Fable-undersøgt 2026-06-13):** Codex-extensionens
URI-handler sender blot URI-stien videre som rute til panelets webview
(`handleUri` → `navigateToRoute`). Ruterne er udokumenterede, ligger i
minificerede bundles og ændrer sig ved extension-opdateringer — ingen
"genoptag chat"-rute fundet i hverken `out/extension.js` eller
webview-chunks. Deep-link droppes bevidst: skrøbeligt gætteri for at spare
ét klik. Valgfri rest-opgave (lav prioritet): toast i CC ved Codex-genoptag —
"Codex-panelet er åbnet — din chat ligger øverst i Sessions-listen".

---

## Næste skridt

**Ved genoptagelse — følg rækkefølgen og hold hvert trin afgrænset:**

1. ✅ ~~Fix blocker B1~~ — lukket 2026-07-29, se ovenfor.
2. ✅ ~~Browser-smoke-test under den faktiske CSP~~ — 5/5, konsol ren.
3. ✅ ~~Regressionstests, genbyg ZIP, udvid release-checket til disk-artefaktet~~
   — 9/9 tests, ZIP genbygget, `check_disk_artifact()` tilføjet og bevist mod
   den forældede pakke.
4. **Kør en ny uafhængig read-only P0-gate** (dyb model, se `07_model_playbook.md`).
   Bed den eksplicit om at afkræfte hvert fund med den billigste mulige test
   før den kalder noget en blocker — det var netop dét, der manglede sidst.
5. Kør derefter den separate colleague-readiness-gate fra pause-checkpointet.
6. ~~**Blokerende: GitHub-kontoen er suspenderet.**~~ **OPHÆVET — verificeret
   2026-08-18.** `git push origin dev` gik igennem (`33b6c63..38a2600`), og
   `git rev-list --count origin/dev..HEAD` viste 0 upushede commits FØR dagens
   arbejde. Spærren var altså væk noget tid før den blev opdaget her — denne
   fil påstod stadig det modsatte og ville have fået en fremtidig session til
   at handle på en falsk blocker. Time Machine er en selvstændig sag og skal
   stadig efterprøves mod regel 0 i `08_repo_politik.md`.

**Aktuel næste kodeopgave:** ingen valgt. Bedre søgning fra `search-plan.md`
er bygget og verificeret 2026-07-29; se afsnittet "Bedre søgning med uddrag og
hop til træf" ovenfor. Gates/backlog nedenfor er bevidst ikke aktuelle lige nu.

**Øvrig backlog:**

1. ✅ ~~Kristian tester det nye projekt-dashboard~~ — testet 2026-07-02, gav 3 runder feedback, alle rettet (se ovenfor). Dashboardet er i drift.
2. ✅ ~~Test og merge PR 6~~ — merget. ~~Test 🚀 Genoptag~~ — verificeret 2026-06-10, virker.
3. **Test mobile preview hjemme** på privat WiFi nu hvor preview-token + VPN-IP-fix er på plads
4. **Distribuér Command Center til første kollega — BLOKERET ved pausen.** Må
   først ske efter hele beviskæden i pause-checkpointet. Del kun en nybygget,
   direkte valideret manifest-pakke — aldrig `../Chatoverblik-dist` eller
   `../Chatoverblik-1.0.zip`.
5. **Vent på redaktør-feedback** på politiken-widget-services.md
6. **Hvis grønt lys fra redaktør:** start migration af Cloudflare-konto + GitHub Organization
7. **Bygge LESSONS.md-viewer** i Command Center så fixede bugs er let tilgængelige per projekt
8. **(Valgfrit, senere) Fase 2 af dashboardet:** Cloudflare-API-verifikation af den ægte live-commit for de 6 wrangler.toml-projekter — se `dashboard-plan.md` trin 9

---

## Tekniske beslutninger

- **Python stdlib only** (ingen pip-deps) — bevarer at det "bare virker" på enhver Mac med Python 3.9+
- **VS Code labels > AI-titler** — Læs ext_labels fra `~/Library/Application Support/Code/User/workspaceStorage/<hash>/state.vscdb` direkte, brug AI som fallback. Sikrer at titler matcher VS Codes Past Conversations 1:1
- **Server binder 0.0.0.0** — for mobile preview. Sikkerhed: `_is_external()` blokerer eksterne for alt undtagen `/preview/*`, `_is_csrf()` blokerer cross-site POST, og `/preview/*` kræver token med 1-times TTL (`STATE['preview_tokens']`)
- **`STATE_LOCK = threading.RLock()`** omkring alle read-modify-write på STATE og cache. Forhindrer race conditions mellem ThreadingHTTPServer-handlers + AI-worker-pool
- **Cache.json som single source of truth** for user_title, pinned-state, AI-titel-cache (merged, ikke overskrevet, ved hver AI-worker-write)
- **`MASTERVERSIONER_ROOT = HERE.parent`** — afledt fra script-placering, ingen hardkodede brugerstier
- **`call_anthropic()` helper** samler 4 tidligere kopier af urllib+headers+parse
- **Path-baseret projektdetektion** — scan jsonl for filstier under cwd; den hyppigste undermappe vinder (min 5 nævninger)
- **Symlink AGENTS.md → CLAUDE.md** så Codex og Claude bruger samme regelsæt
- **localhost:7777** som fast port
- **Cloud-AI default-deny** — API-key alene sender intet. Manuel cloud-AI kræver
  payload-preview + SHA-256-bekræftelse; automatisk titelgenerering kræver både
  env-flag og projektmarkør.
- **Release-manifest som source-of-truth** — current-kollegapakken bygges kun
  fra `release_manifest.json`; gamle dist/zip-artefakter er blokeret legacy.

---

## Kendte problemer

- ✅ **Cloud-AI-bekræftelsen — LUKKET 2026-08-13.** Symptom: *"Cloud-AI kræver
  aktivt valg… send igen med ai_confirmed=true"*, hvis dialogen stod åben over
  ~25 sek. Årsag: `require_ai_confirmation` genberegnede payload ved andet
  kald og sammenlignede hash, mens `rescan_loop` opdaterede
  `STATE["sessions"]` hvert `RESCAN_INTERVAL_SECONDS` (=25) — så payloaden
  ændrede sig under læsningen. Fix: payloads gemmes nu i
  `_AI_PENDING_PAYLOADS` under `"<action>:<sha256>"` og sendes tilbage til
  kaldestedet, så **præcis den tekst der blev godkendt, er den der sendes**
  (før kunne tekst A godkendes og tekst B sendes). Godkendelsen er bundet til
  sit endpoint og gælder én gang; TTL 15 min. Verificeret med fire tests:
  409 ved første kald · godkendelse accepteres trods ændret payload og sender
  den oprindelige · hash kan ikke genbruges · hash virker ikke på tværs af
  endpoints. Alle seks kaldesteder opdateret til 4-tuple.
- ✅ **B1 — LUKKET 2026-07-29.** Alle tre inline-`onclick` konverteret til
  `addEventListener` og verificeret i browser under den faktiske CSP (5/5,
  konsol ren). To guards forhindrer tilbagefald. Se afsnittet ovenfor.
- ~~**GitHub-kontoen er suspenderet (blocker, uden for koden).**~~ **LUKKET
  2026-08-18** — push virker igen, verificeret med en faktisk push. Lærdommen
  består: en tilstandsbeskrivelse i en STATUS-fil er en momentopgørelse, ikke
  en sandhed. Denne stod forkert i ukendt tid, fordi ingen efterprøvede den med
  én kommando (`git rev-list --count origin/dev..HEAD`).
- **`test_release_check_passes_and_blocks_legacy_artifacts` kan ikke bestå på
  en frisk klon.** Den kræver `release/Chatoverblik-current.zip` på disken, men
  `release/` står i `.gitignore`. Testen består lokalt, hvor pakken ligger, og
  fejler for enhver, der lige har klonet repoet — med beskeden
  `disk artifact missing: release/Chatoverblik-current.zip`. Det er ikke en
  kodefejl: kør `python3 scripts/build_release.py` først. Fælden er reel, fordi
  fejlen ligner en ægte regression og kan sende en fremtidig session i gang med
  at "reparere" noget, der virker. Overvej at lade testen springe over med
  `skipUnless`, når artefaktet mangler.
- **Testene er `unittest`, ikke pytest.** `python3 -m pytest` fejler med
  "No module named pytest" på alle maskinens Python-versioner. Brug
  `python3 -m unittest discover -s tests`.
- **Mobile preview blokeres på Politikens WiFi** — formentlig client isolation på corporate netværk. Virker på private/home-netværk. Ikke en kode-fejl.
- **Codex søgefelt understøtter ikke altid højreklik-paste** — VS Code/OpenAI-quirk. Workaround: ⌘V i stedet
- **Cache for analysis.md eller HANDOVER.md kan blive forældet** hvis chats slettes/opdateres efter generering. Lav "↻ Genberegn"-knap som workaround
- **`get_local_ip()` foretrækker rigtige LAN-interfaces** frem for VPN-tunnels (PR 5). Skulle dække de almindelige tilfælde, men eksotiske VPN-konfigurationer (WireGuard der præsenterer sig som broadcast) kan stadig snyde den
- **macOS Documents/-mappen** blokerer LaunchAgent — derfor er autostart valgt fra; manuel start.command-flow

---

## Vigtige filer

- `chatoverblik.py` — Python-serveren, alle endpoints
- `index.html` — single-page UI
- `LESSONS.md` — projektets lærte lektier (læs ved sessions-start)
- `cache.json` — AI-titler, user_title-overrides, pinned-state (genereres automatisk)
- `analysis.md` — gemt workflow-analyse (genereres ved klik)
- `start.command` — dobbeltklik-launcher
- `icon.png` / `favicon.png` — Command Center-ikon serveret via /icon.png
- `AppIcon.icns` — macOS-app-ikon
- `~/Applications/Command Center.app` — min legacy launcher app (kan også bruges hvis Safari web app ikke er nok)
- `release/Chatoverblik-current.zip` — current-kandidat; genbygget efter B1
  (2026-07-29) og valideret direkte mod kilderne. Stadig ikke godkendt til
  udlevering: mangler ny P0-gate + readiness-gate
- `tests/test_b1_csp_browser.mjs` — Playwright-browsertest af den faktiske CSP
  (kræver kørende server + `npx playwright install chromium`; dev-only, ikke
  en del af release-pakken)
- `release_manifest.json` + `scripts/build_release.py` +
  `scripts/release_check.py` — release source-of-truth og gates
- `../Chatoverblik-dist/` + `../Chatoverblik-1.0.zip` — **blokeret legacy;
  må aldrig distribueres som current**
- `P0_HARDENING.md` + `tests/test_p0_hardening.py` — P0-beslutninger og
  regressionstest
- `ULTRA_REVIEW.md` — rapport fra multi-agent code review (2026-06-04), alle 15 fund + status
- `dashboard-plan.md` — plan for projekt-dashboardet (lampe-logik, scope-regel, acceptkriterier, trinvis byggeplan)

## Parallelt spor: politiken.widget

Redaktør har spurgt om hvilke services Politiken skal levere for at holde
vibecoding in-house. Min anbefaling ligger som
`Masterversioner/politiken-widget-services.md` og er sendt videre.
Afventer feedback. Estimat: $650-1250/md for 5 journalister.
