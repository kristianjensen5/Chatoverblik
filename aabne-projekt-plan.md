# Plan: fiks projekt-åbning fra Command Center

**Skrevet:** 2026-08-18 · **Af:** Opus (plan) → bygges af Sonnet
**Gælder:** `POST /api/open-in-windsurf` i `chatoverblik.py` + de knapper i
`index.html` der kalder den med `mode: "new-chat"`.

---

## Problemet — målt, ikke gættet

Ét klik på "åbn projekt" giver i dag tre uønskede ting:

- **(a)** En Claude-fane lander i et ANDET, allerede åbent projekt
- **(b)** Et tomt, sort standard-VS-Code-vindue åbner
- **(c)** Det rigtige farvede vindue åbner, men uden chat — Kristian skal
  selv ind i Chats → Claude → ny samtale

Alle tre har samme årsag. `chatoverblik.py:2408-2413` venter et fast
`time.sleep(0.8)` + `0.2` efter `code -n`, og fyrer så
`open vscode://anthropic.claude-code/open`. Vinduet er aldrig klar efter 1 sekund.

Målt ved at sammenholde `logs/subprocess.log` med mtime på Claude-udvidelsens
egne lock-filer i `~/.claude/ide/*.lock`:

| Klik (`code -n`) | URI fyret | Udvidelsen klar | Fyret for tidligt med |
|---|---|---|---|
| 09:53:05 | 09:53:06 | 09:53:29 | 23 s |
| 09:58:22 | 09:58:23 | 09:58:25 | 2 s |
| 20:58:36 | 20:58:37 | 20:58:48 | 11 s |
| 21:14:40 | 21:14:41 | 21:15:01 | 20 s |

4 af 4 ramte ved siden af. Loggen har oven i købet en
`-609 Forbindelsen er ugyldig` fra `osascript` kl. 09:58 — VS Code svarede
ikke, fordi den stadig startede op.

**Følgeslutninger:**
- (a) `vscode://`-URI'en routes til det VS Code-vindue der er forrest på
  fyrings-tidspunktet. Det er det gamle projekt.
- (b) Kommer URI'en før noget vindue kan tage imod den, åbner VS Code et
  tomt vindue for at håndtere den. Tomt vindue = ingen workspace = ingen
  farve = sort. (Hypotese med høj sandsynlighed; bekræftes af at symptomet
  forsvinder når vi kun fyrer på et klart vindue.)
- (c) Følger af (a)/(b).

Beslægtede, allerede kendte lektier (`context/05_lessons_fuld.md`):
`VS Code --command fyrer for tidligt før extensions er aktiveret` og
`VS Code code -n virker ikke når workspace allerede er åbent`.

---

## Løsningen — fire trin

Byg ét trin ad gangen. Commit lokalt efter hvert trin (rule 7, små diffs).
Push først efter Kristians OK.

### Trin 1 — vent på et ægte klarsignal

Claude Code-udvidelsen skriver ved aktivering en fil til
`~/.claude/ide/<port>.lock` med dette indhold:

```json
{"pid":52534,"workspaceFolders":["/Users/…/Masterversioner/Nyelands drømmeverden"],
 "ideName":"Visual Studio Code","transport":"ws","runningInWindows":false,
 "authToken":"…"}
```

Filen er det eneste pålidelige "dette vindue er klar OG det er dette projekt".

Nye hjælpefunktioner i `chatoverblik.py`, lige over
`get_project_workspace_file()`:

```python
IDE_LOCK_DIR = Path.home() / ".claude" / "ide"


def _norm_path(p):
    """macOS blander NFC og NFD i filnavne — 'drømmeverden' kan være kodet
    på to måder der ser ens ud. Udvidelsen skriver NFC; normalisér begge
    sider, ellers matcher danske mappenavne aldrig."""
    try:
        p = os.path.realpath(p)
    except Exception:
        pass
    return unicodedata.normalize("NFC", str(p)).rstrip("/")


def _ide_lock_workspaces(min_mtime=0.0):
    """Returnér mængden af projektmapper som Claude-udvidelsen p.t. er
    kørende i. min_mtime filtrerer forældede lock-filer fra — der ligger
    uger gamle filer fra vinduer der for længst er lukket."""
    found = set()
    try:
        entries = list(IDE_LOCK_DIR.glob("*.lock"))
    except Exception:
        return found
    for f in entries:
        try:
            if f.stat().st_mtime < min_mtime:
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for w in data.get("workspaceFolders") or []:
            found.add(_norm_path(w))
    return found


def _wait_for_ide_ready(workspace_root, since_ts, timeout=45.0, interval=0.4):
    """Vent til Claude-udvidelsen melder sig klar i netop dette projekts
    vindue. Returnér ventetiden i sekunder, eller None ved timeout."""
    target = _norm_path(workspace_root)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if target in _ide_lock_workspaces(min_mtime=since_ts - 2):
            return round(time.time() - (deadline - timeout), 1)
        time.sleep(interval)
    return None
```

> **Hvorfor virker det også for Codex?** Claude-udvidelsen har
> `activationEvents: ["onStartupFinished"]` og starter derfor i ALLE
> VS Code-vinduer, uanset hvilken AI Kristian valgte. Lock-filen er altså
> et "vinduet er klar"-signal, ikke et "Claude blev valgt"-signal.
> Codex-udvidelsen har ingen tilsvarende fil.

### Trin 2 — brug signalet i `/api/open-in-windsurf`

Erstat blokken `chatoverblik.py:2396-2417`. Ny rækkefølge:

1. **Før** `code -n` fyres: `already_open = _norm_path(workspace_root) in
   _ide_lock_workspaces(min_mtime=time.time() - 86400)` og
   `launched_at = time.time()`.
2. Fyr `code -n <ws_file>` som i dag.
3. Hvis `extension_uri` skal fyres:
   - `already_open` → `time.sleep(1.5)` (vinduet findes; `code -n` fokuserer
     det. Der kommer ingen NY lock-fil, så en poll ville løbe tør)
   - ellers → `waited = _wait_for_ide_ready(workspace_root, launched_at)`
   - **Kun hvis vinduet er klar:** `osascript … activate`, `time.sleep(0.4)`,
     `open <extension_uri>`.
   - **Ved timeout: fyr INGENTING.** Bedre ingen chat end en chat i det
     forkerte projekt. Det er hele pointen med rettelsen.
4. Svar med `{"ok": true, "ready": bool, "waited": float|null, …}` oveni de
   felter der returneres i dag (`opened`, `workspace_file`, `color`,
   `project`) — frontend'en bruger dem allerede.

Endpointet bliver dermed langsomt (op til 45 s). Det er acceptabelt:
serveren er en `ThreadingHTTPServer`, så hver request kører i sin egen tråd
og blokerer hverken 4-sekunders-pollingen eller andre knapper. Trin 4 gør
ventetiden synlig i brugerfladen i stedet for at skjule den.

### Trin 3 — send første besked med i linket

Claude-udvidelsens URI-handler (verificeret i
`~/.vscode/extensions/anthropic.claude-code-*/extension.js`) understøtter:

```
vscode://anthropic.claude-code/open?prompt=<urlencoded>&session=<id>
```

`prompt` sendes videre til `claude-vscode.primaryEditor.open` →
`createPanel(session, prompt, ViewColumn.Active)`, som åbner en NY samtale
med teksten allerede i inputfeltet. Det fjerner hele
"Chats → Claude → ny samtale → ⌘V"-dansen.

- Læs valgfrit `prompt` fra request-body i `/api/open-in-windsurf`.
- **Kun for `source == "claude"`.** Codex-URI'en (`vscode://openai.chatgpt/`)
  har ingen dokumenteret prompt-parameter — find ikke på en. Codex beholder
  clipboard-flowet uændret.
- Byg med `urllib.parse.quote(prompt, safe="")` (tilføj importen).
- **Loft på 8000 tegn.** Genoptag-briefet kan blive langt, og en URL er ikke
  et sted at sende ubegrænset tekst. Over loftet: drop `prompt` fra URI'en og
  sæt `"prompt_sent": false` i svaret, så frontend'en kan sige "brug ⌘V".
- Clipboard-kopieringen i frontend'en **bevares altid** som fallback.

### Trin 4 — ærlig knap i brugerfladen

Tre kaldesteder i `index.html`:

| Linje | Knap | Ændring |
|---|---|---|
| ~3075 | `np-open` — "Åbn i VS Code →" i nyt-projekt-flowet | send `prompt: firstPrompt`; disable knappen og skift tekst til "Åbner… venter på at VS Code er klar" mens der ventes |
| ~2729 | `launchIn(source)` i genoptag-guiden | send `prompt: buildPrompt()` (kun claude); samme vente-tilstand |
| ~2388, ~2110, ~3433 | almindelig "↗ VS Code" uden `mode` | **rør ikke** — de fyrer ingen URI og er hurtige |

Efter svaret:
- `d.ready === true` → toast "Klar — chatten er åbnet i <projekt>"
  (eller "…, paste med ⌘V" hvis `prompt_sent === false`)
- `d.ready === false` → toast "VS Code nåede ikke at blive klar. Vinduet er
  åbent — start chatten manuelt." Ingen chat er fyret nogen steder.

Genaktivér knappen i en `finally`, så en fejl ikke efterlader den død.

---

## Acceptkriterier (rule 14)

**Automatisk, kør før du siger færdig:**

Ny `tests/test_ide_ready.py` der tester `_wait_for_ide_ready` mod en
midlertidig lock-mappe (monkeypatch `IDE_LOCK_DIR`), med fire tilfælde:

1. Lock-fil dukker op efter ~1 s → returnerer en ventetid, ikke None
2. Lock-fil dukker aldrig op → returnerer None inden for timeout
3. Forældet lock-fil (mtime sat 3 dage tilbage) for samme mappe → ignoreres,
   returnerer None
4. Dansk mappenavn skrevet NFD i lock-filen og NFC i forespørgslen (fx
   `drømmeverden`) → matcher alligevel

Kør den og vis output. En påstand uden kommando-output tæller ikke.

**Manuelt — Kristian tester selv (rule 14, han foretrækker at teste selv):**

Med ét projekt åbent i forvejen, åbn tre andre projekter i træk fra
Command Center. Alle tre gange skal gælde:

- Ingen ny fane i det projekt der var åbent i forvejen
- Intet tomt sort VS Code-vindue
- Det nye vindue har projektets farve OG en åben Claude-chat med startprompten
  allerede skrevet i feltet

---

## Bindende ramme

- Rør kun `/api/open-in-windsurf` i `chatoverblik.py` og de tre `mode:
  "new-chat"`-kaldesteder i `index.html`. Intet andet i Command Center.
- Ingen nye afhængigheder. Alt bruger stdlib + filer der allerede findes.
- Ingen cloud-AI-kald tilføjes.
- **Ingen commit eller push uden Kristians OK.** Ingen deploy.
- Rammer du noget planen ikke dækker: STOP og spørg. Improvisér ikke.

---

## Bagefter

Log lektien i `Chatoverblik/LESSONS.md` — og den er globalt relevant
(gælder enhver automatisering der starter en GUI-app og derefter vil sende
den en kommando), så også i `context/05_lessons_fuld.md` efterfulgt af
`python3 context/byg_lessons_indeks.py`. Kernen:

> Et fast `sleep` er ikke en synkronisering. Skal du sende en kommando til en
> app du selv lige har startet, så find appens eget klarsignal på disken og
> vent på DET — og fyr ingenting hvis signalet udebliver, i stedet for at
> fyre i blinde mod hvad der nu tilfældigvis er forrest.
