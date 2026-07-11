# Command Center (Chatoverblik) — Status

**Type:** privat (workflow-værktøj, men bruges til arbejdsprojekter)
**Live URL:** http://localhost:7777 (lokal kun)
**GitHub:** `kristianjensen5/Chatoverblik` (eget nestet repo, pushes løbende)
**Senest opdateret:** 2026-07-11 (P0-hardening: distribution, CSP, path-gate, cloud-AI default-deny og regressionstests)

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

1. ✅ ~~Kristian tester det nye projekt-dashboard~~ — testet 2026-07-02, gav 3 runder feedback, alle rettet (se ovenfor). Dashboardet er i drift.
2. ✅ ~~Test og merge PR 6~~ — merget. ~~Test 🚀 Genoptag~~ — verificeret 2026-06-10, virker.
3. **Test mobile preview hjemme** på privat WiFi nu hvor preview-token + VPN-IP-fix er på plads
4. **Distribuér Command Center til første kollega** via den nye current-pakke:
   kør `python3 scripts/release_check.py --json`, byg med
   `python3 scripts/build_release.py`, og del kun manifest-pakken — aldrig
   `../Chatoverblik-dist` eller `../Chatoverblik-1.0.zip`.
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

- **Mobile preview blokeres på Politikens WiFi** — formentlig client isolation på corporate netværk. Virker på private/home-netværk. Ikke en kode-fejl.
- **Codex søgefelt understøtter ikke altid højreklik-paste** — VS Code/OpenAI-quirk. Workaround: ⌘V i stedet
- **Cache for analysis.md eller HANDOVER.md kan blive forældet** hvis chats slettes/opdateres efter generering. Lav "↻ Genberegn"-knap som workaround
- **`get_local_ip()` foretrækker rigtige LAN-interfaces** frem for VPN-tunnels (PR 5). Skulle dække de almindelige tilfælde, men eksotiske VPN-konfigurationer (WireGuard der præsenterer sig som broadcast) kan stadig snyde den
- **macOS Documents/-mappen** blokerer LaunchAgent — derfor er autostart valgt fra; manuel start.command-flow

---

## Vigtige filer

- `chatoverblik.py` — Python-serveren, alle endpoints
- `index.html` — single-page UI
- `cache.json` — AI-titler, user_title-overrides, pinned-state (genereres automatisk)
- `analysis.md` — gemt workflow-analyse (genereres ved klik)
- `start.command` — dobbeltklik-launcher
- `icon.png` / `favicon.png` — Command Center-ikon serveret via /icon.png
- `AppIcon.icns` — macOS-app-ikon
- `~/Applications/Command Center.app` — min legacy launcher app (kan også bruges hvis Safari web app ikke er nok)
- `Chatoverblik-dist/` + `Chatoverblik-1.0.zip` — distribution til kollega
- `ULTRA_REVIEW.md` — rapport fra multi-agent code review (2026-06-04), alle 15 fund + status
- `dashboard-plan.md` — plan for projekt-dashboardet (lampe-logik, scope-regel, acceptkriterier, trinvis byggeplan)

## Parallelt spor: politiken.widget

Redaktør har spurgt om hvilke services Politiken skal levere for at holde
vibecoding in-house. Min anbefaling ligger som
`Masterversioner/politiken-widget-services.md` og er sendt videre.
Afventer feedback. Estimat: $650-1250/md for 5 journalister.
