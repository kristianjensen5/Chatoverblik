# Command Center (Chatoverblik) — Status

**Type:** privat (workflow-værktøj, men bruges til arbejdsprojekter)
**Live URL:** http://localhost:7777 (lokal kun)
**GitHub:** (ikke pushed endnu)
**Senest opdateret:** 2026-06-04

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
  - ✅ `workbench.action.closeAllEditors` kæde'd ind så Welcome-fanen ikke vises
  - ⚠️ Auto-ny-chat ved opstart: **Codex** virker via `chatgpt.newChat`. **Claude** har INGEN eksponeret "New Conversation"-kommando — vi åbner kun sidebaren og bruger klikker "+" selv
  - ⚠️ Begge AI-extensions loader som tabs i secondary sidebar uden vi kan "switche" — det er Kristians sidebar-bredde der afgør om begge er synlige eller skjult bag "..."-menu
  - Workspace Trust skal accepteres første gang per workspace for farve at vises

### Nyere features (juni 2026)
- ✅ **WIDGETS.md viewer/editor** — knap i Værktøjer-sektionen, modal med markdown-render + redigeringstilstand med backup ved hver gem
- ✅ **Code viewer / file browser** — 📄 Filer-knap på projekt-overskrifterne. Tre-kolonne layout: filtræ til venstre, syntax-highlightet kode til højre (Prism.js, supporterer HTML/CSS/JS/Python/JSON/Markdown/Bash mfl.). Sikkerhed: kun filer under kendte projekt-cwds, max 500KB, skipper støj (node_modules, __pycache__ osv.)
- ✅ **Flyt chat til andet projekt** — 📁 Flyt-knap i chat-modalen, dropdown med ALLE Masterversioner-undermapper (inkl. tomme). Bruger `user_cwd`-override i cache.json uden at røre selve jsonl-filen
- ✅ **Auto-åbn workspace-root** — `find_workspace_root()` scanner opad fra cwd til nærmeste CLAUDE.md/AGENTS.md, så Claude/Codex finder chat-historikken korrekt
- ✅ **Per-projekt Peacock-farver via `.code-workspace`-filer** — hver projekt får sin egen workspace-identity og farve. Genereres i Chatoverblik/.workspaces/
- ✅ **Nyt projekt-flow** — første-besked-prompt der tvinger AI'en til at læse CLAUDE.md, STATUS.md, WIDGETS.md + bekræfte memory. Claude/Codex extension-vælger inkluderet

### Ikke startet
- ❌ Per-projekt LESSONS.md-viewer
- ❌ Curated terminal-knapper (deploy, git status osv.) — overvejes som næste step
- ❌ Migration af min Chatoverblik-kode til politiken-widget Cloudflare-konto (afventer redaktør-svar)

---

## Næste skridt

1. **Test mobile preview hjemme** på privat WiFi for at bekræfte at QR-flow virker når netværket ikke isolerer klienter
2. **Vent på redaktør-feedback** på politiken-widget-services.md (sendt til hende)
3. **Hvis grønt lys fra redaktør:** start migration af Cloudflare-konto + GitHub Organization
4. **Bygge LESSONS.md-viewer** i Command Center så fixede bugs er let tilgængelige per projekt
5. **Bygge WIDGETS.md-viewer/editor** i Command Center

---

## Tekniske beslutninger

- **Python stdlib only** (ingen pip-deps) — bevarer at det "bare virker" på enhver Mac med Python 3.9+
- **VS Code labels > AI-titler** — Læs ext_labels fra `~/Library/Application Support/Code/User/workspaceStorage/<hash>/state.vscdb` direkte, brug AI som fallback. Sikrer at titler matcher VS Codes Past Conversations 1:1
- **Server binder 0.0.0.0** — for mobile preview. Sikkerhed: `_is_external()`-check tillader KUN `/preview/*` til eksterne klienter
- **Cache.json som single source of truth** for user_title, pinned-state, AI-titel-cache
- **Path-baseret projektdetektion** — scan jsonl for filstier under cwd; den hyppigste undermappe vinder (min 5 nævninger)
- **Symlink AGENTS.md → CLAUDE.md** så Codex og Claude bruger samme regelsæt
- **localhost:7777** som fast port

---

## Kendte problemer

- **Mobile preview blokeres på Politikens WiFi** — formentlig client isolation på corporate netværk. Virker på private/home-netværk. Ikke en kode-fejl.
- **Codex søgefelt understøtter ikke altid højreklik-paste** — VS Code/OpenAI-quirk. Workaround: ⌘V i stedet
- **Cache for analysis.md eller HANDOVER.md kan blive forældet** hvis chats slettes/opdateres efter generering. Lav "↻ Genberegn"-knap som workaround
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

## Parallelt spor: politiken.widget

Redaktør har spurgt om hvilke services Politiken skal levere for at holde
vibecoding in-house. Min anbefaling ligger som
`Masterversioner/politiken-widget-services.md` og er sendt videre.
Afventer feedback. Estimat: $650-1250/md for 5 journalister.
