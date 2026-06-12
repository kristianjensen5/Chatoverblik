# Command Center (Chatoverblik) — Status

**Type:** privat (workflow-værktøj, men bruges til arbejdsprojekter)
**Live URL:** http://localhost:7777 (lokal kun)
**GitHub:** `kristianjensen5/Chatoverblik` (eget nestet repo, pushes løbende)
**Senest opdateret:** 2026-06-12 (Fable-audit: stabilitet som primær indgang)

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

---

## Næste skridt

1. ✅ ~~Test og merge PR 6~~ — merget. ~~Test 🚀 Genoptag~~ — verificeret 2026-06-10, virker.
2. **Test mobile preview hjemme** på privat WiFi nu hvor preview-token + VPN-IP-fix er på plads
3. **Distribuér Command Center til første kollega** — alle distribution-blockers er ude. Tjek først at de hardkodede stier ikke længere er et issue (PR 5).
4. **Vent på redaktør-feedback** på politiken-widget-services.md
5. **Hvis grønt lys fra redaktør:** start migration af Cloudflare-konto + GitHub Organization
6. **Bygge LESSONS.md-viewer** i Command Center så fixede bugs er let tilgængelige per projekt

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

## Parallelt spor: politiken.widget

Redaktør har spurgt om hvilke services Politiken skal levere for at holde
vibecoding in-house. Min anbefaling ligger som
`Masterversioner/politiken-widget-services.md` og er sendt videre.
Afventer feedback. Estimat: $650-1250/md for 5 journalister.
