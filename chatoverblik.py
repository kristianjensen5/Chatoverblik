#!/usr/bin/env python3
"""
Chatoverblik — lokal webside der viser alle Claude- og Codex-chats.

Start:
    python3 chatoverblik.py

Åbn så http://localhost:7777 i browseren.

Krav:
    - Python 3.9+
    - Miljøvariabel ANTHROPIC_API_KEY (til AI-titler)
"""

import html
import http.server
import json
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ───────── Konfiguration ─────────
HOME = Path.home()
CLAUDE_DIR = HOME / ".claude" / "projects"
CODEX_DIR = HOME / ".codex" / "sessions"
HERE = Path(__file__).parent
# Masterversioner-roden = den mappe Chatoverblik/ ligger i. Derived så
# Command Center virker på enhver brugers Mac uden at editere koden.
MASTERVERSIONER_ROOT = HERE.parent
CACHE_FILE = HERE / "cache.json"
INDEX_FILE = HERE / "index.html"
LOGS_DIR = HERE / "logs"
SUBPROCESS_LOG_FILE = LOGS_DIR / "subprocess.log"
PORT = 7777
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5-20251001"
PROMPT_PREVIEW_CHARS = 3000      # hvor meget af chatten vi sender til AI
MAX_PARALLEL_AI_CALLS = 8
PREVIEW_TOKEN_TTL = 60 * 60  # Preview-links udløber efter 1 time
RESCAN_INTERVAL_SECONDS = 25
CLAUDE_CODE_URI = "vscode://anthropic.claude-code/open"
CODEX_URI = "vscode://openai.chatgpt/"

# Alle modeller frontend må vælge. Tidligere copy-pasted i 3+ endpoints med
# forskellige allowlists — workflow-analysis udelukkede tilfældigt haiku.
ALLOWED_MODELS = {
    "claude-sonnet-4-6",
    "claude-opus-4-8",
    "claude-haiku-4-5-20251001",
}
DEFAULT_MODEL = "claude-sonnet-4-6"


def logged_popen(args, **kwargs):
    LOGS_DIR.mkdir(exist_ok=True)
    with SUBPROCESS_LOG_FILE.open("a", encoding="utf-8") as log:
        log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] $ {' '.join(map(str, args))}\n")
        log.flush()
        kwargs.setdefault("stderr", log)
        return subprocess.Popen(args, **kwargs)


def pick_model(requested):
    """Normalisér en bruger-valgt model — falder tilbage til default ved ukendt."""
    return requested if requested in ALLOWED_MODELS else DEFAULT_MODEL


def call_anthropic(prompt, *, model=DEFAULT_MODEL, max_tokens=1000, timeout=60):
    """POST til Anthropic Messages API. Returnerer text-indholdet.

    Tidligere copy-pasted 4 steder med små variationer i max_tokens/timeout.
    Raiser urllib.error.URLError / json.JSONDecodeError ved fejl — caller
    afgør hvordan disse skal håndteres.
    """
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = "".join(b.get("text", "") for b in data.get("content", [])
                   if b.get("type") == "text")
    # Diagnostik: hvis text er tom, log struktur til terminal så vi kan se
    # hvorfor (typisk: extended-thinking-modeller bruger alle tokens på
    # 'thinking'-blokke når max_tokens er for lavt).
    if not text.strip():
        types = [b.get("type") for b in data.get("content", [])]
        print(f"[call_anthropic] Tom text fra {model}. "
              f"Block-typer: {types}. stop_reason: {data.get('stop_reason')}. "
              f"usage: {data.get('usage')}", flush=True)
    return text


# ───────── Cache for AI-titler ─────────
def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_cache(cache):
    # Hold lock under json.dumps så cachen ikke ændrer størrelse mens vi
    # serialiserer (RuntimeError: dictionary changed size during iteration).
    # tmp.replace er atomisk på POSIX, så samtidige writes går ikke i stykker
    # på disk — men sidste-skriver-vinder semantikken er nu indeholdt i locken.
    with STATE_LOCK:
        payload = json.dumps(cache, indent=2, ensure_ascii=False)
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(payload)
    tmp.replace(CACHE_FILE)


# ───────── Læs chats fra disk ─────────
def read_first_lines(path, limit=20):
    lines = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                line = line.strip()
                if line:
                    lines.append(line)
    except Exception:
        pass
    return lines


def parse_jsonl(path):
    msgs = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msgs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return msgs


def extract_text_from_content(content):
    """Codex og Claude bruger lidt forskellige content-formater."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and "text" in part:
                    chunks.append(part["text"])
                elif "text" in part:
                    chunks.append(str(part["text"]))
                elif part.get("type") == "input_text":
                    chunks.append(part.get("text", ""))
            elif isinstance(part, str):
                chunks.append(part)
        return "\n".join(chunks)
    return ""


# Tags Claude og Codex pakker IDE-kontekst og system-reminders ind i.
# Vi fjerner indholdet af disse blokke for at finde den rigtige bruger-tekst.
_TAG_BLOCKS = [
    "ide_opened_file", "ide_selection", "system-reminder", "command-name",
    "command-message", "command-args", "local-command-stdout", "local-command-stderr",
    "environment_context", "permissions", "collaboration_mode",
    "INSTRUCTIONS", "user-prompt-submit-hook",
]
_TAG_RE = re.compile(
    r"<(" + "|".join(re.escape(t) for t in _TAG_BLOCKS) + r")\b[^>]*>.*?</\1>",
    re.S | re.I,
)
_SELF_CLOSE_RE = re.compile(
    r"<(" + "|".join(re.escape(t) for t in _TAG_BLOCKS) + r")\b[^/>]*/?>",
    re.I,
)
_BOOTSTRAP_PREFIXES = (
    "# AGENTS.md", "# CLAUDE.md", "<permissions",
    "<collaboration_mode", "<environment_context",
)


def clean_user_text(text):
    """Fjern IDE-kontekst, system-tags og bootstrap-prompts for at finde den
    egentlige besked brugeren skrev."""
    if not text:
        return ""
    cleaned = _TAG_RE.sub("", text)
    cleaned = _SELF_CLOSE_RE.sub("", cleaned)
    # Windsurf-Codex pakker brugerinput ind i "Context from my IDE setup" —
    # det rigtige input ligger efter "My request for Codex:"
    for marker in ("## My request for Codex:", "## My request:", "My request for Codex:"):
        idx = cleaned.find(marker)
        if idx != -1:
            cleaned = cleaned[idx + len(marker):]
            break
    # Trim tomme linjer
    lines = [ln for ln in cleaned.splitlines() if ln.strip()]
    return "\n".join(lines).strip()


def is_bootstrap_message(text):
    """True hvis dette ligner system-instruktioner (AGENTS.md mv.), ikke brugerinput."""
    t = text.lstrip()
    if not t:
        return True
    return t.startswith(_BOOTSTRAP_PREFIXES)


def parse_claude_session_file(f):
    msgs = parse_jsonl(f)
    if not msgs:
        return None
    cwd = next((m.get("cwd") for m in msgs if m.get("cwd")), "")
    first_user_text = ""
    timestamps = []
    user_count = 0
    assistant_count = 0
    for m in msgs:
        ts = m.get("timestamp")
        if ts:
            timestamps.append(ts)
        msg = m.get("message") or {}
        role = msg.get("role") or m.get("type")
        if role == "user":
            raw = extract_text_from_content(msg.get("content", ""))
            cleaned = clean_user_text(raw)
            if cleaned and not is_bootstrap_message(cleaned):
                user_count += 1
                if not first_user_text:
                    first_user_text = cleaned
        elif role == "assistant":
            assistant_count += 1
    if not first_user_text:
        return None
    session_id = f.stem
    path_hint = detect_subfolder_from_paths(cwd, msgs)
    # Normalisér op til projekt-roden, så åbnet mappe matcher kortets navn
    # (detect_subfolder kan ellers pege på en under-undermappe som .../widget)
    effective_cwd = project_root_from_cwd(path_hint or cwd)
    return {
        "source": "claude",
        "id": session_id,
        "file": str(f),
        "cwd": effective_cwd,
        "original_cwd": cwd,
        "project": project_name_from_cwd(effective_cwd),
        "first_user": first_user_text[:PROMPT_PREVIEW_CHARS],
        "started": timestamps[0] if timestamps else "",
        "ended": timestamps[-1] if timestamps else "",
        "msg_count": user_count + assistant_count,
        "user_msg_count": user_count,
    }


def scan_claude():
    """Returnér liste af chat-meta fra ~/.claude/projects/*/<session>.jsonl."""
    sessions = []
    if not CLAUDE_DIR.exists():
        return sessions
    for project_dir in CLAUDE_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for f in project_dir.glob("*.jsonl"):
            session = parse_claude_session_file(f)
            if session:
                sessions.append(session)
    return sessions


def parse_codex_session_file(f):
    msgs = parse_jsonl(f)
    if not msgs:
        return None
    meta = next((m for m in msgs if m.get("type") == "session_meta"), None) or {}
    payload = meta.get("payload", {}) if isinstance(meta, dict) else {}
    cwd = payload.get("cwd", "")
    sess_id = payload.get("id") or f.stem
    started = payload.get("timestamp") or meta.get("timestamp", "")
    first_user_text = ""
    user_count = 0
    assistant_count = 0
    last_ts = started
    for m in msgs:
        if m.get("timestamp"):
            last_ts = m["timestamp"]
        t = m.get("type")
        p = m.get("payload", {}) if isinstance(m.get("payload"), dict) else {}
        # Codex event_msg/user_message er den rene tekst brugeren skrev
        if t == "event_msg" and p.get("type") == "user_message":
            txt = (p.get("message") or extract_text_from_content(p.get("content", ""))).strip()
            if txt and not is_bootstrap_message(txt):
                user_count += 1
                if not first_user_text:
                    first_user_text = clean_user_text(txt)
        elif t == "event_msg" and p.get("type") == "agent_message":
            assistant_count += 1
    # Fallback: brug response_item-messages hvis ingen event_msg user_messages fundet
    if not first_user_text:
        for m in msgs:
            if m.get("type") == "response_item":
                p = m.get("payload", {})
                if p.get("type") == "message" and p.get("role") == "user":
                    raw = extract_text_from_content(p.get("content", ""))
                    cleaned = clean_user_text(raw)
                    if cleaned and not is_bootstrap_message(cleaned):
                        first_user_text = cleaned
                        user_count = max(user_count, 1)
                        break
    if not first_user_text:
        return None
    path_hint = detect_subfolder_from_paths(cwd, msgs)
    # Normalisér op til projekt-roden, så åbnet mappe matcher kortets navn
    # (detect_subfolder kan ellers pege på en under-undermappe som .../widget)
    effective_cwd = project_root_from_cwd(path_hint or cwd)
    return {
        "source": "codex",
        "id": sess_id,
        "file": str(f),
        "cwd": effective_cwd,
        "original_cwd": cwd,
        "project": project_name_from_cwd(effective_cwd),
        "first_user": first_user_text[:PROMPT_PREVIEW_CHARS],
        "started": started,
        "ended": last_ts,
        "msg_count": user_count + assistant_count,
        "user_msg_count": user_count,
    }


def scan_codex():
    """Returnér liste fra ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl."""
    sessions = []
    if not CODEX_DIR.exists():
        return sessions
    for f in CODEX_DIR.rglob("rollout-*.jsonl"):
        session = parse_codex_session_file(f)
        if session:
            sessions.append(session)
    return sessions


def iter_chat_files():
    if CLAUDE_DIR.exists():
        for project_dir in CLAUDE_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            for f in project_dir.glob("*.jsonl"):
                yield "claude", f
    if CODEX_DIR.exists():
        for f in CODEX_DIR.rglob("rollout-*.jsonl"):
            yield "codex", f


def parse_session_file(source, path):
    if source == "claude":
        return parse_claude_session_file(path)
    if source == "codex":
        return parse_codex_session_file(path)
    return None


def session_key(session):
    return f"{session['source']}:{session['id']}"


def session_sort_value(session):
    return session.get("ended") or session.get("started") or ""


def collect_chat_file_mtimes():
    mtimes = {}
    for _, path in iter_chat_files():
        try:
            mtimes[str(path)] = path.stat().st_mtime_ns
        except OSError:
            pass
    return mtimes


def project_name_from_cwd(cwd):
    if not cwd:
        return "(uden mappe)"
    parts = [p for p in cwd.split("/") if p]
    if not parts:
        return "(rod)"
    if "Masterversioner" in parts:
        idx = parts.index("Masterversioner")
        # Brug undermappens navn — eller "Masterversioner" hvis chatten er på rod-niveau
        return parts[idx + 1] if idx + 1 < len(parts) else "Masterversioner"
    return parts[-1]


def project_root_from_cwd(cwd):
    """Normalisér en cwd OP til projekt-roden — den Masterversioner-direkte
    undermappe. Det er præcis det niveau project_name_from_cwd navngiver, så
    den mappe vi ÅBNER altid matcher kortets navn.

    Uden dette kunne en chat der arbejdede meget i en under-undermappe (fx
    .../LæsernesVerdenskort/widget) få sin cwd skubbet derned af
    detect_subfolder_from_paths — så kortet hed 'LæsernesVerdenskort' men
    knappen åbnede 'widget'-undermappen. Vi kapper altid ved projekt-roden."""
    if not cwd:
        return cwd
    # Bevar trailing slash-status ved at arbejde på segmenter
    parts = cwd.split("/")
    if "Masterversioner" in parts:
        idx = parts.index("Masterversioner")
        # Behold alt til og med Masterversioner + ÉT segment (projekt-roden)
        keep = parts[: idx + 2] if idx + 1 < len(parts) else parts[: idx + 1]
        return "/".join(keep)
    # Uden for Masterversioner kender vi ikke projektstrukturen — lad cwd stå
    return cwd


# ───────── URL-scanning per projekt ─────────
_URL_RE = re.compile(r"https?://[a-zA-Z0-9./_?&=#%~+:@,;!*'()-]+")

# Domæner vi vil VISE som live-links
_LIVE_HOST_PATTERNS = (
    ".pages.dev", ".workers.dev", ".github.io", ".netlify.app", ".vercel.app",
    "borneavisen-app.workers.dev", "boerneavisen-app.workers.dev",
    "politiken.dk", "pol.dk",
)
# Domæner vi springer over (CDN, dokumentation, baggrundsdata)
_SKIP_HOSTS = (
    "cdn.jsdelivr.net", "unpkg.com", "esm.sh", "cdnjs.cloudflare.com",
    "fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net",
    "console.anthropic.com", "console.cloudflare.com",
    "developers.cloudflare.com", "docs.anthropic.com", "anthropic.com",
    "stackoverflow.com", "github.io", "raw.githubusercontent.com",
    "mdn.io", "developer.mozilla.org", "wikipedia.org",
    "openai.com", "platform.openai.com",
    "schemas.android.com", "www.w3.org",
)


def _normalize_url(u):
    return u.rstrip(".,;:)]}>'\"")


_ASSET_EXTS = (".js", ".css", ".woff", ".woff2", ".ttf", ".otf", ".eot",
               ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
               ".mp4", ".webm", ".mp3", ".wav", ".pdf",
               ".json", ".xml", ".txt", ".map")

_ASSET_PATH_HINTS = ("/assets/", "/incoming/static/", "/static/", "/fonts/",
                     "/images/", "/img/", "/css/", "/dist/", "/build/",
                     "/_next/", "/sw.js")


def _classify_url(url):
    """Returnér ('live'|'repo'|None, normaliseret URL) eller None hvis vi springer over."""
    url = _normalize_url(url)
    if "/api/" in url:
        return None
    lower = url.lower()
    if lower.endswith(_ASSET_EXTS):
        return None
    if any(hint in lower for hint in _ASSET_PATH_HINTS):
        return None
    try:
        host = url.split("/")[2].lower()
    except IndexError:
        return None
    if any(host.endswith(h) for h in _SKIP_HOSTS):
        return None
    if "github.com" in host:
        if "kristianjensen5" in url:
            return ("repo", url)
        return None
    for pat in _LIVE_HOST_PATTERNS:
        if pat in host:
            return ("live", url)
    return None


def _wrangler_pages_url(toml_path):
    """Læs `name = "..."` fra wrangler.toml og dan pages.dev-URL."""
    try:
        for line in toml_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("name") and "=" in line and "[" not in line:
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and " " not in val:
                    return f"https://{val}.pages.dev"
                break
    except Exception:
        pass
    return None


def scan_project_urls(cwd):
    """Find live-URLs og repo-URL i en projektmappe."""
    if not cwd:
        return []
    root = Path(cwd)
    if not root.exists() or not root.is_dir():
        return []
    urls = {}  # url -> kind

    # 1) wrangler.toml → pages.dev
    wrangler = root / "wrangler.toml"
    if wrangler.exists():
        u = _wrangler_pages_url(wrangler)
        if u:
            urls[u] = "live"

    # 2) .git/config → GitHub-repo
    gitcfg = root / ".git" / "config"
    if gitcfg.exists():
        try:
            txt = gitcfg.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'url\s*=\s*([^\s]+)', txt)
            if m:
                gu = m.group(1).strip()
                if gu.endswith(".git"):
                    gu = gu[:-4]
                if "github.com" in gu:
                    urls[gu] = "repo"
        except Exception:
            pass

    # 3) Tekstfiler i roden — README, STATUS, DEPLOY, CLAUDE, alle *.md
    text_targets = []
    for name in ("README.md", "STATUS.md", "DEPLOY.md", "CLAUDE.md", "AGENTS.md"):
        p = root / name
        if p.exists():
            text_targets.append(p)
    # Alle .md-filer i roden (typisk få per projekt)
    for p in sorted(root.glob("*.md")):
        if p not in text_targets:
            text_targets.append(p)

    # 4) HTML-filer i roden — top + bund (anchors og kommentarer ligger ofte i bunden)
    html_files = sorted(root.glob("*.html"))[:6]

    for path in text_targets:
        try:
            txt = path.read_text(encoding="utf-8", errors="replace")
            for raw in _URL_RE.findall(txt):
                cls = _classify_url(raw)
                if cls:
                    kind, u = cls
                    if u not in urls or (urls[u] == "repo" and kind == "live"):
                        urls[u] = kind
        except Exception:
            continue

    for path in html_files:
        try:
            txt = path.read_text(encoding="utf-8", errors="replace")
            # Stor men ikke gigantisk — fanger URLs i kommentarer og top af head
            snippet = txt[:30000]
            for raw in _URL_RE.findall(snippet):
                cls = _classify_url(raw)
                if cls:
                    kind, u = cls
                    if u not in urls or (urls[u] == "repo" and kind == "live"):
                        urls[u] = kind
        except Exception:
            continue

    # Trin 1: dedup trailing slash
    deduped = {}
    for u, k in urls.items():
        base = u.rstrip("/")
        existing = deduped.get(base)
        if existing is None:
            deduped[base] = (u, k)
        else:
            ex_url, ex_kind = existing
            if k == "live" and ex_kind == "repo":
                deduped[base] = (u, k)
            elif len(u) > len(ex_url):
                deduped[base] = (u, ex_kind if ex_kind == k else k)

    # Trin 2: kun én URL per host+kind — foretrækker den korteste/root-URL
    # (så kristian-ideer.pages.dev/01.html kollapses med kristian-ideer.pages.dev/02)
    from urllib.parse import urlparse
    host_best = {}
    for _, (u, k) in deduped.items():
        try:
            host = (urlparse(u).hostname or u).lower()
        except Exception:
            host = u.lower()
        key = (host, k)
        existing = host_best.get(key)
        if existing is None or len(u) < len(existing[0]):
            host_best[key] = (u, k)

    return [{"kind": k, "url": u} for (u, k) in host_best.values()]


def build_projects_index(sessions):
    """Lav projekt-index med chat-antal og URLs."""
    by_cwd = {}
    for s in sessions:
        # Normaliser cwd (fjern trailing slash)
        cwd = (s.get("cwd") or "").rstrip("/")
        s["cwd_norm"] = cwd
        key = cwd or "__none__"
        if key not in by_cwd:
            by_cwd[key] = {
                "cwd": cwd,
                "name": s.get("project") or "(uden mappe)",
                "chats": 0,
                "urls": [],
                "latest": "",
            }
        by_cwd[key]["chats"] += 1
        latest = s.get("ended") or s.get("started") or ""
        if latest > by_cwd[key]["latest"]:
            by_cwd[key]["latest"] = latest

    # Scan URLs (én gang per projekt)
    for key, proj in by_cwd.items():
        if proj["cwd"]:
            proj["urls"] = scan_project_urls(proj["cwd"])

    # Sortér efter seneste aktivitet
    projects = sorted(by_cwd.values(), key=lambda p: p["latest"], reverse=True)
    return projects


# ───────── AI-titler ─────────
def ai_title_and_summary(session, cache):
    """Generér {title, summary} for en chat. Cacher per session-id."""
    cache_key = f"{session['source']}:{session['id']}"
    if cache_key in cache:
        return cache[cache_key]

    if not ANTHROPIC_KEY:
        cache[cache_key] = {
            "title": fallback_title(session["first_user"]),
            "summary": "(AI ikke aktiveret — sæt ANTHROPIC_API_KEY)",
        }
        return cache[cache_key]

    prompt = (
        "Du får uddrag af en chat mellem en bruger og en AI-kodeassistent. "
        "Lav et JSON-objekt med to felter:\n"
        '  - "title": maks 6 ord, sigende — fx "Fixede sound-bug i Greenland-scene"\n'
        '  - "summary": maks 2 sætninger der opsummerer hvad chatten handlede om\n\n'
        "VIGTIGT om sprog: title OG summary skal være på SAMME sprog som "
        "brugerens første besked. Hvis brugeren skriver på dansk → dansk titel/resumé. "
        "Hvis brugeren skriver på engelsk → engelsk titel/resumé. Spejl det sprog brugeren bruger.\n\n"
        "Svar KUN med rent JSON, ingen markdown-blokke.\n\n"
        f"Projekt: {session['project']}\n"
        f"Antal beskeder: {session['msg_count']}\n\n"
        "Første brugerbesked:\n"
        f"\"\"\"\n{session['first_user'][:PROMPT_PREVIEW_CHARS]}\n\"\"\""
    )

    try:
        text = call_anthropic(prompt, model=MODEL, max_tokens=300, timeout=45)
        # Find første { … } i tilfælde af at modellen alligevel skriver lidt rundt om
        m = re.search(r"\{.*\}", text, re.S)
        parsed = json.loads(m.group(0)) if m else json.loads(text)
        result = {
            "title": (parsed.get("title") or fallback_title(session["first_user"]))[:80],
            "summary": (parsed.get("summary") or "").strip(),
        }
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        result = {
            "title": fallback_title(session["first_user"]),
            "summary": f"(AI-fejl: {type(e).__name__})",
        }

    # Merge i stedet for at overskrive — ellers wiper vi user_title/pinned/
    # user_cwd hvis brugeren rørte chatten mens AI-kaldet var in-flight.
    # Hold lock omkring read-modify-write så samtidige AI-workers ikke racer.
    with STATE_LOCK:
        existing = cache.get(cache_key) or {}
        existing.update(result)
        cache[cache_key] = existing
    return result


def fallback_title(text):
    t = text.strip().splitlines()[0] if text.strip() else "(tom chat)"
    return t[:60].rstrip() + ("…" if len(t) > 60 else "")


def apply_cached_titles(sessions, cache, ext_labels=None):
    """Sæt title/summary/pinned på hver session fra cachen (eller fallback).
    Prioritering for title: user_title > extension-label > AI-titel > fallback.
    user_cwd-override trumfer detekteret cwd (manuel flyt-til-projekt)."""
    ext_labels = ext_labels or {}
    for s in sessions:
        key = f"{s['source']}:{s['id']}"
        meta = cache.get(key, {})
        ai_title = meta.get("title") or fallback_title(s["first_user"])
        user_title = meta.get("user_title", "")
        ext_label = ext_labels.get(key, "")
        s["title"] = user_title or ext_label or ai_title
        s["ai_title"] = ai_title
        s["ext_label"] = ext_label
        s["user_title"] = user_title
        s["summary"] = meta.get("summary") or ""
        s["pinned"] = bool(meta.get("pinned", False))
        # Hvis brugeren manuelt har flyttet chatten til en anden projektmappe,
        # respektér det — overskriver path-detektion
        user_cwd = meta.get("user_cwd", "")
        if user_cwd:
            s["original_cwd"] = s.get("cwd", "")
            s["cwd"] = user_cwd
            s["project"] = project_name_from_cwd(user_cwd)
            s["cwd_hint"] = ""
            s["user_cwd"] = user_cwd
        else:
            hint = detect_subfolder_hint(s.get("cwd", ""), s.get("first_user", ""))
            s["cwd_hint"] = hint or ""
            s["user_cwd"] = ""


def build_search_index(sessions):
    """Saml alle beskeder pr. session til en stor søgbar streng.
    Hentes via /api/search; sendes IKKE i /api/sessions (for stort)."""
    index = {}
    for s in sessions:
        try:
            msgs = render_chat_for_view(s)
            joined = "\n".join(m["text"] for m in msgs)
            # Komprimér whitespace, lowercase
            joined = re.sub(r"\s+", " ", joined).lower()
            index[f"{s['source']}:{s['id']}"] = joined[:120000]
        except Exception:
            index[f"{s['source']}:{s['id']}"] = ""
    return index


def enrich_with_ai(sessions, cache, status_cb=None, ext_labels=None):
    # Initial fallback-titler så frontenden viser noget med det samme
    apply_cached_titles(sessions, cache, ext_labels)

    needed = [s for s in sessions if not cache.get(f"{s['source']}:{s['id']}")]
    total = len(needed)
    if total == 0:
        if status_cb:
            status_cb(f"Klar ({len(sessions)} chats)")
        return sessions
    if status_cb:
        status_cb(f"AI-titler: 0/{total}")

    done = 0
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_AI_CALLS) as ex:
        futures = {ex.submit(ai_title_and_summary, s, cache): s for s in needed}
        for fut in as_completed(futures):
            s = futures[fut]
            done += 1
            # Opdatér denne session live
            meta = cache.get(f"{s['source']}:{s['id']}", {})
            if meta:
                s["title"] = meta.get("title") or s["title"]
                s["summary"] = meta.get("summary") or s["summary"]
            if done % 5 == 0 or done == total:
                save_cache(cache)
            if status_cb:
                status_cb(f"AI-titler: {done}/{total}")
    save_cache(cache)
    return sessions


# ───────── Chat-visning (resume + full) ─────────
def render_chat_for_view(session):
    """Hent og udtræk beskeder fra jsonl til visning i frontenden."""
    msgs = parse_jsonl(Path(session["file"]))
    out = []
    if session["source"] == "claude":
        for m in msgs:
            msg = m.get("message") or {}
            role = msg.get("role") or m.get("type")
            if role not in ("user", "assistant"):
                continue
            text = extract_text_from_content(msg.get("content", ""))
            if role == "user":
                text = clean_user_text(text)
                if not text or is_bootstrap_message(text):
                    continue
            if not text.strip():
                continue
            out.append({"role": role, "text": text, "ts": m.get("timestamp", "")})
    else:  # codex
        for m in msgs:
            t = m.get("type")
            p = m.get("payload", {}) if isinstance(m.get("payload"), dict) else {}
            if t == "event_msg" and p.get("type") == "user_message":
                txt = (p.get("message") or extract_text_from_content(p.get("content", ""))).strip()
                txt = clean_user_text(txt)
                if txt and not is_bootstrap_message(txt):
                    out.append({"role": "user", "text": txt, "ts": m.get("timestamp", "")})
            elif t == "event_msg" and p.get("type") == "agent_message":
                txt = (p.get("message") or extract_text_from_content(p.get("content", ""))).strip()
                if txt:
                    out.append({"role": "assistant", "text": txt, "ts": m.get("timestamp", "")})
    return out


# ───────── HTTP-server ─────────
def detect_subfolder_from_paths(cwd, msgs):
    """Scan ALLE beskeder for filstier under cwd. Returnér den mest hyppige
    undermappe hvis den nævnes >= 5 gange. Mere pålideligt end at gætte fra
    første besked, fordi det dækker hele samtalen incl. tool-kald."""
    if not cwd or not msgs:
        return None
    cwd_norm = cwd.rstrip("/") + "/"
    pattern = re.compile(re.escape(cwd_norm) + r"([^/\s\"'`)<>]+)")
    counts = {}
    for m in msgs:
        # Saml alt tekst-indhold til scanning
        chunks = []
        msg_obj = m.get("message") or {}
        if msg_obj:
            chunks.append(json.dumps(msg_obj, ensure_ascii=False))
        payload = m.get("payload") if isinstance(m.get("payload"), dict) else None
        if payload:
            chunks.append(json.dumps(payload, ensure_ascii=False))
        text = " ".join(chunks)
        for match in pattern.findall(text):
            if "." in match or len(match) < 2:
                continue  # skip filer og 1-char-fragmenter
            counts[match] = counts.get(match, 0) + 1
    if not counts:
        return None
    top_folder, top_count = max(counts.items(), key=lambda x: x[1])
    if top_count < 5:
        return None
    full_path = cwd_norm + top_folder
    if Path(full_path).is_dir():
        return full_path
    return None


def detect_subfolder_hint(cwd, first_user):
    """Hvis chatten kører fra en mappe og første besked tydeligt peger på en
    undermappe (fx 'find mappen X', '/X/' i en sti, 'i X-mappen'),
    returnér den fulde sti til undermappen."""
    if not cwd or not first_user:
        return None
    root = Path(cwd)
    if not root.exists() or not root.is_dir():
        return None
    text_lower = first_user.lower()
    candidates = []
    try:
        for child in root.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            name = child.name
            n = name.lower()
            if len(n) < 4:
                continue
            # Stærke signaler for at brugeren faktisk peger på den mappe
            patterns = [
                f"mappen {n}",         # "find mappen dagsrader"
                f"{n}-mappen",         # "Dagsrader-mappen"
                f"mappe {n}",          # "ny mappe Dagsrader"
                f"i {n} ",             # "vi arbejder i Klaver"
                f"i {n}/",             # path-style
                f"/{n}/",              # i en sti
                f"/{n} ",              # path med space efter
                f"`{n}`",              # i backticks
                f"'{n}'",              # i quotes
                f'"{n}"',
            ]
            if any(p in text_lower for p in patterns):
                candidates.append(child)
    except Exception:
        return None
    if len(candidates) == 1:
        return str(candidates[0])
    return None


def scan_extension_labels():
    """Læs chat-titler direkte fra VS Code/Windsurf-extensionernes
    workspace-storage. Returnér {source:id → label}."""
    import sqlite3
    labels = {}
    storage_paths = [
        HOME / "Library/Application Support/Code/User/workspaceStorage",
        HOME / "Library/Application Support/Windsurf/User/workspaceStorage",
        HOME / "Library/Application Support/Cursor/User/workspaceStorage",
    ]
    for base in storage_paths:
        if not base.exists():
            continue
        for workspace_dir in base.iterdir():
            db = workspace_dir / "state.vscdb"
            if not db.exists():
                continue
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
                cur = conn.cursor()
                cur.execute("SELECT value FROM ItemTable WHERE key='agentSessions.model.cache'")
                row = cur.fetchone()
                conn.close()
            except Exception:
                continue
            if not row:
                continue
            try:
                sessions = json.loads(row[0])
            except Exception:
                continue
            for s in sessions:
                resource = s.get("resource", "")
                label = (s.get("label") or "").strip()
                if not resource or not label:
                    continue
                # claude-code:/<uuid>  eller  openai-codex://route/local/<uuid>
                sess_id = resource.rstrip("/").split("/")[-1]
                if "claude-code" in resource:
                    labels[f"claude:{sess_id}"] = label
                elif "openai-codex" in resource:
                    labels[f"codex:{sess_id}"] = label
    return labels


# File extension → Prism.js language mapping
EXT_TO_LANG = {
    ".html": "markup", ".htm": "markup", ".svg": "markup", ".xml": "markup",
    ".css": "css",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".jsx": "jsx",
    ".py": "python",
    ".json": "json", ".webmanifest": "json",
    ".md": "markdown",
    ".sh": "bash", ".command": "bash", ".zsh": "bash",
    ".toml": "toml",
    ".yaml": "yaml", ".yml": "yaml",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".php": "php",
    ".txt": "plaintext", ".log": "plaintext",
    ".env": "bash",
    ".gitignore": "bash",
}


def build_file_tree(root, max_depth=4, current_depth=0):
    """Returnér en hierarkisk fil/mappe-struktur fra root.
    Skipper skjulte filer, node_modules og lignende støj."""
    if current_depth >= max_depth:
        return []
    items = []
    skip_names = {"node_modules", "__pycache__", ".wrangler",
                  ".DS_Store", ".workspaces", "logs", "Backups"}
    try:
        children = sorted(root.iterdir(),
                         key=lambda p: (not p.is_dir(), p.name.lower()))
    except Exception:
        return []
    for child in children:
        if child.name in skip_names:
            continue
        if child.name.startswith(".") and child.name not in (".gitignore", ".env.example"):
            continue
        try:
            if child.is_dir():
                items.append({
                    "name": child.name,
                    "type": "dir",
                    "path": str(child),
                    "children": build_file_tree(child, max_depth, current_depth + 1),
                })
            else:
                size = child.stat().st_size
                items.append({
                    "name": child.name,
                    "type": "file",
                    "path": str(child),
                    "size": size,
                    "ext": child.suffix.lower(),
                })
        except Exception:
            continue
    return items


def get_local_ip():
    """Find Mac'ens lokale IP på WiFi/LAN (for mobile preview).

    Foretrækker rigtige LAN-interfaces (WiFi, Ethernet) frem for VPN-tunnels.
    Parses ifconfig: 'inet'-linjer med 'broadcast' er rigtige netværk, mens
    point-to-point tunnels (Politiken-VPN, WireGuard, osv.) har '-->' i stedet.
    Falder tilbage til den klassiske 8.8.8.8-trick hvis parsing fejler.
    """
    import socket
    try:
        out = subprocess.run(["ifconfig"], capture_output=True, text=True,
                             timeout=2).stdout
        candidates = []
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("inet ") or "broadcast" not in line:
                continue
            parts = line.split()
            if len(parts) < 2 or parts[1] == "127.0.0.1":
                continue
            candidates.append(parts[1])
        if candidates:
            # Foretræk klassisk hjemme-WiFi → hotspot/Ethernet → 10.x
            def rank(ip):
                if ip.startswith("192.168."):
                    return 0
                if ip.startswith("172."):
                    try:
                        if 16 <= int(ip.split(".")[1]) <= 31:
                            return 1
                    except ValueError:
                        pass
                if ip.startswith("10."):
                    return 2
                return 3
            candidates.sort(key=rank)
            return candidates[0]
    except Exception:
        pass
    # Fallback: spørg routing-tabellen via UDP-socket. Returnerer VPN-IP'en
    # hvis en VPN er aktiv, men er bedre end ingenting.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# Tilladte filtyper i /preview/-ruten (sikkerhed: ingen vilkårlige filer)
_PREVIEW_EXTS = {
    ".html", ".htm", ".css", ".js", ".mjs", ".json", ".xml", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".webm", ".wav", ".m4a", ".ogg",
    ".map", ".webmanifest",
}


# Peacock-inspireret farvepalette — projekter får en stabil farve baseret på navn
_PEACOCK_PALETTE = [
    "#1e88e5",  # blue
    "#43a047",  # green
    "#e53935",  # red
    "#ff8f00",  # orange
    "#5e35b1",  # purple
    "#00897b",  # teal
    "#d81b60",  # pink
    "#3949ab",  # indigo
    "#8e24aa",  # light purple
    "#00acc1",  # cyan
    "#7cb342",  # lime
    "#6d4c41",  # brown
    "#546e7a",  # blue grey
    "#f4511e",  # deep orange
]


def project_color(name):
    """Returnér en stabil hex-farve for et projektnavn (samme navn = samme farve)."""
    if not name:
        return _PEACOCK_PALETTE[0]
    h = sum(ord(c) for c in name)
    return _PEACOCK_PALETTE[h % len(_PEACOCK_PALETTE)]


def _darken_hex(hex_color, factor=0.78):
    c = hex_color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


def color_customizations(color):
    """Beregn workbench.colorCustomizations for en farve."""
    dark = _darken_hex(color, 0.78)
    return {
        "activityBar.activeBackground": color,
        "activityBar.background": color,
        "activityBar.foreground": "#ffffff",
        "activityBar.inactiveForeground": "#ffffff99",
        "activityBarBadge.background": "#FFC107",
        "activityBarBadge.foreground": "#15202b",
        "commandCenter.border": "#e7e7e7",
        "sash.hoverBorder": color,
        "statusBar.background": dark,
        "statusBar.foreground": "#ffffff",
        "statusBarItem.hoverBackground": color,
        "statusBarItem.remoteBackground": dark,
        "statusBarItem.remoteForeground": "#ffffff",
        "titleBar.activeBackground": dark,
        "titleBar.activeForeground": "#ffffff",
        "titleBar.inactiveBackground": dark + "99",
        "titleBar.inactiveForeground": "#ffffff99",
    }


WORKSPACES_DIR = HERE / ".workspaces"


def get_project_workspace_file(workspace_root, project_name, color):
    """Generér eller opdatér en .code-workspace fil per projekt.

    Hvert projekt får sin egen workspace-identity. Det giver:
      - VS Code åbner i NYT VINDUE per projekt (forskellig .code-workspace = forskellig identity)
      - Per-projekt farve (settings inline i workspace-filen, ikke shared via .vscode/)
      - Projektmappen selv som primær folder → rigtigt filtræ + Claude-historik per cwd

    Filerne ligger i Chatoverblik/.workspaces/ — skjult for brugeren."""
    try:
        WORKSPACES_DIR.mkdir(exist_ok=True)
    except Exception:
        return None
    safe_name = re.sub(r"[^a-zA-Z0-9_æøåÆØÅ-]", "_", project_name) or "default"
    ws_file = WORKSPACES_DIR / f"{safe_name}.code-workspace"
    workspace_data = {
        "folders": [{"path": workspace_root}],
        "settings": {
            "peacock.color": color,
            "workbench.colorCustomizations": color_customizations(color),
            # Skip Welcome-fanen så chat-kommandoen kan tage fokus uden konflikt
            "workbench.startupEditor": "none",
        },
    }
    try:
        ws_file.write_text(json.dumps(workspace_data, indent=2, ensure_ascii=False),
                          encoding="utf-8")
        return str(ws_file)
    except Exception:
        return None


def find_code_cli():
    """Find VS Code CLI (`code`) — prøver typiske placeringer."""
    candidates = [
        "/usr/local/bin/code",
        "/opt/homebrew/bin/code",
        "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    try:
        r = subprocess.run(["which", "code"], capture_output=True,
                           text=True, timeout=2)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


STATE = {
    "sessions": [], "projects": [], "loading": True,
    "status": "Starter…", "cache": {}, "search_index": {},
    "ext_labels": {}, "file_mtimes": {}, "rescan_running": False,
    # token -> {"cwd": str, "expires_at": float}. Genereres af /api/preview-info,
    # tjekkes af _serve_preview. Sikrer at en LAN-besøgende skal have et levende
    # QR-link for at kunne tilgå projekt-filer — ikke kun et gættet projekt-navn.
    "preview_tokens": {},
}
# Re-entrant lock omkring alle read-modify-write på STATE og cache.
# ThreadingHTTPServer + ThreadPoolExecutor til AI-kald gør at flere tråde
# muterer samme dicts samtidig — uden lock kan vi tabe pin/rename eller få
# 'dict changed size during iteration' under serialisering.
STATE_LOCK = threading.RLock()


def _new_preview_token(cwd):
    """Generér et nyt token der mapper til cwd. Bruges som adgangstoken
    i /preview/<token>/<sti>. Pruner samtidig udløbne tokens."""
    token = secrets.token_urlsafe(16)
    expires_at = time.time() + PREVIEW_TOKEN_TTL
    with STATE_LOCK:
        now = time.time()
        STATE["preview_tokens"] = {
            t: v for t, v in STATE["preview_tokens"].items()
            if v["expires_at"] > now
        }
        STATE["preview_tokens"][token] = {"cwd": cwd, "expires_at": expires_at}
    return token


def _resolve_preview_token(token):
    """Returnér cwd hvis token er gyldig og ikke udløbet, ellers None."""
    with STATE_LOCK:
        entry = STATE["preview_tokens"].get(token)
        if not entry:
            return None
        if entry["expires_at"] < time.time():
            STATE["preview_tokens"].pop(token, None)
            return None
        return entry["cwd"]


def set_status(status):
    with STATE_LOCK:
        STATE["status"] = status


def perform_rescan(full=False, initial=False):
    with STATE_LOCK:
        if STATE["rescan_running"]:
            return False
        STATE["rescan_running"] = True
        STATE["status"] = "Scanner alle chats…" if full else "Scanner nye chats…"
        if full or initial:
            STATE["loading"] = True
        existing_keys = {session_key(s) for s in STATE["sessions"]}
        previous_mtimes = dict(STATE["file_mtimes"])
        cache = STATE["cache"] or load_cache()

    try:
        if full or initial:
            cache = load_cache()
            set_status("Scanner Claude-chats…")
            claude = scan_claude()
            set_status("Scanner Codex-chats…")
            codex = scan_codex()
            set_status("Henter titler fra VS Code…")
            ext_labels = scan_extension_labels()
            all_sessions = claude + codex
            all_sessions.sort(key=session_sort_value, reverse=True)
            apply_cached_titles(all_sessions, cache, ext_labels)
            ai_targets = all_sessions if initial else [
                s for s in all_sessions if session_key(s) not in existing_keys
            ]
            set_status("Scanner projekter for live-URLs…")
            projects = build_projects_index(all_sessions)
            set_status("Bygger søgeindeks…")
            search_index = build_search_index(all_sessions)
            file_mtimes = collect_chat_file_mtimes()
            with STATE_LOCK:
                STATE["cache"] = cache
                STATE["ext_labels"] = ext_labels
                STATE["sessions"] = all_sessions
                STATE["projects"] = projects
                STATE["search_index"] = search_index
                STATE["file_mtimes"] = file_mtimes
                STATE["loading"] = False
        else:
            current_mtimes = {}
            changed = []
            for source, path in iter_chat_files():
                try:
                    mtime = path.stat().st_mtime_ns
                except OSError:
                    continue
                current_mtimes[str(path)] = mtime
                if mtime > previous_mtimes.get(str(path), 0):
                    changed.append((source, path))

            if not changed:
                with STATE_LOCK:
                    STATE["file_mtimes"] = current_mtimes
                    STATE["status"] = f"Klar ({len(STATE['sessions'])} chats)"
                return True

            set_status(f"Scanner nye chats ({len(changed)} filer)…")
            ext_labels = scan_extension_labels()
            changed_sessions = []
            for source, path in changed:
                session = parse_session_file(source, path)
                if session:
                    changed_sessions.append(session)
            apply_cached_titles(changed_sessions, cache, ext_labels)
            changed_search_index = build_search_index(changed_sessions)

            with STATE_LOCK:
                existing_by_key = {session_key(s): s for s in STATE["sessions"]}
                ai_targets = []
                for session in changed_sessions:
                    key = session_key(session)
                    if key not in existing_by_key:
                        ai_targets.append(session)
                    existing_by_key[key] = session
                all_sessions = sorted(
                    existing_by_key.values(),
                    key=session_sort_value,
                    reverse=True,
                )
                search_index = dict(STATE["search_index"])
                search_index.update(changed_search_index)

            projects = build_projects_index(all_sessions)
            with STATE_LOCK:
                STATE["ext_labels"] = ext_labels
                STATE["sessions"] = all_sessions
                STATE["projects"] = projects
                STATE["search_index"] = search_index
                STATE["file_mtimes"] = current_mtimes
                STATE["loading"] = False

        if ai_targets:
            set_status(f"Henter AI-titler ({len(ai_targets)} nye chats)…")
            enrich_with_ai(ai_targets, cache,
                           status_cb=set_status,
                           ext_labels=STATE.get("ext_labels", {}))
        with STATE_LOCK:
            STATE["status"] = f"Klar ({len(STATE['sessions'])} chats)"
        return True
    except Exception as e:
        print(f"[rescan] {type(e).__name__}: {e}", flush=True)
        with STATE_LOCK:
            STATE["status"] = f"Rescan-fejl: {type(e).__name__}"
        return False
    finally:
        with STATE_LOCK:
            STATE["loading"] = False
            STATE["rescan_running"] = False


def background_load():
    perform_rescan(full=True, initial=True)


def rescan_loop():
    while True:
        time.sleep(RESCAN_INTERVAL_SECONDS)
        perform_rescan(full=False)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # stille

    def _is_external(self):
        """True hvis requesten kommer fra ikke-localhost (fx en telefon på WiFi)."""
        addr = self.client_address[0] if self.client_address else ""
        return addr not in ("127.0.0.1", "::1", "localhost")

    def _is_csrf(self):
        """True hvis POST mangler en gyldig Origin/Referer mod localhost:PORT.

        Beskytter mod cross-site requests fra browser-faner på andre sites:
        en webside kan tvinge browseren til at POSTe til localhost, men kan
        ikke sætte Origin-headeren — så vi afviser alle POST uden gyldig origin.
        """
        allowed = (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}")
        origin = self.headers.get("Origin", "")
        if origin:
            return origin not in allowed
        # Hvis ingen Origin: tjek Referer som fallback (ældre browsere)
        referer = self.headers.get("Referer", "")
        if referer:
            return not any(referer.startswith(a + "/") or referer == a for a in allowed)
        # Hverken Origin eller Referer → afvis (typisk curl/CSRF-tricks)
        return True

    def _forbidden(self):
        self.send_response(403)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Adgang nægtet — Command Center er kun tilgængelig fra Mac'en\n"
                        "selv. /preview/* er den eneste rute der kan tilgås udefra.".encode("utf-8"))

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # Tillad cache for static-assets, men ikke HTML (så reload ses)
        if not content_type.startswith("text/html"):
            self.send_header("Cache-Control", "public, max-age=300")
        else:
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_preview(self):
        """Server filer fra en projektmappe under /preview/<token>/<sti>.

        Token genereres af /api/preview-info når brugeren klikker 'Mobile Preview'
        og udløber efter PREVIEW_TOKEN_TTL. Erstatter den gamle base64-cwd som
        var trivielt at gætte (projekt-stier er kendte).
        """
        import mimetypes
        from urllib.parse import unquote, urlparse
        try:
            # Brug urlparse for at strippe query-string (?v=cachebust osv.)
            path_only = urlparse(self.path).path
            rest = path_only[len("/preview/"):]
            parts = rest.split("/", 1)
            token = parts[0]
            sub_path = unquote(parts[1]) if len(parts) > 1 else "index.html"
            if not sub_path or sub_path.endswith("/"):
                sub_path = (sub_path + "index.html").lstrip("/")
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        # Sikkerhed 1: token skal være gyldig og ikke udløbet
        cwd = _resolve_preview_token(token)
        if not cwd:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Preview-link er udl\xc3\xb8bet eller ugyldigt")
            return

        # Sikkerhed 2: ingen path-traversal
        base = Path(cwd).resolve()
        try:
            target = (base / sub_path).resolve()
        except Exception:
            self.send_response(400)
            self.end_headers()
            return
        if not (target == base or str(target).startswith(str(base) + "/")):
            self.send_response(403)
            self.end_headers()
            return

        # Sikkerhed 3: kun whitelistede filtyper
        if target.is_file() and target.suffix.lower() not in _PREVIEW_EXTS:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Filtypen kan ikke serveres")
            return

        if not target.exists() or not target.is_file():
            self.send_response(404)
            self.end_headers()
            return

        ctype, _ = mimetypes.guess_type(str(target))
        if not ctype:
            ctype = "application/octet-stream"
        if target.suffix.lower() in (".html", ".htm"):
            ctype = "text/html; charset=utf-8"
        self._send_file(target, ctype)

    def do_GET(self):
        # Ekstern adgang: kun /preview/* — alt andet er forbudt
        if self._is_external() and not self.path.startswith("/preview/"):
            self._forbidden()
            return

        if self.path.startswith("/preview/"):
            self._serve_preview()
            return
        if self.path == "/" or self.path.startswith("/index.html"):
            # Injicér app-mappens absolutte sti så "Server kører ikke"-badgen
            # kan vise hvor start.command ligger (browseren kender ikke selv
            # filsystem-stien når siden serveres over http).
            html = INDEX_FILE.read_text(encoding="utf-8")
            html = html.replace("__APP_DIR__", str(HERE))
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/icon.png":
            icon = HERE / "icon.png"
            if icon.exists():
                self._send_file(icon, "image/png")
                return
        if self.path == "/favicon.ico" or self.path == "/favicon.png":
            favicon = HERE / "favicon.png"
            if favicon.exists():
                self._send_file(favicon, "image/png")
                return
        if self.path == "/api/sessions":
            self._send_json({
                "loading": STATE["loading"],
                "status": STATE["status"],
                "sessions": STATE["sessions"],
                "projects": STATE["projects"],
            })
            return
        if self.path == "/api/projects":
            self._send_json({"projects": STATE["projects"]})
            return
        if self.path.startswith("/api/file-tree"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            cwd = (qs.get("cwd") or [""])[0]
            if not cwd or not Path(cwd).is_dir():
                self._send_json({"ok": False, "error": "Mappen findes ikke"}, 400)
                return
            # Sikkerhed: skal være under et kendt projekt eller Masterversioner.
            # Filtrér tomme strenge fra — ellers ville startswith(""+"/") matche
            # ENHVER absolut sti og åbne for path-traversal.
            valid_roots = {(s.get("cwd") or "").rstrip("/") for s in STATE["sessions"]}
            valid_roots |= {(p.get("cwd") or "").rstrip("/") for p in STATE["projects"]}
            valid_roots.add(str(MASTERVERSIONER_ROOT))
            valid_roots = {r for r in valid_roots if r}
            cwd_norm = cwd.rstrip("/")
            allowed = any(cwd_norm == r or cwd_norm.startswith(r + "/") for r in valid_roots)
            if not allowed:
                self._send_json({"ok": False, "error": "Mappen er ikke tilladt"}, 403)
                return
            tree = build_file_tree(Path(cwd), max_depth=4)
            self._send_json({"ok": True, "tree": tree, "root": cwd})
            return

        if self.path.startswith("/api/file-content"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            file_path = (qs.get("path") or [""])[0]
            if not file_path or not Path(file_path).is_file():
                self._send_json({"ok": False, "error": "Fil findes ikke"}, 400)
                return
            # Sikkerhed: skal være under et kendt projekt eller Masterversioner.
            # Filtrér tomme strenge fra — ellers ville startswith(""+"/") matche
            # ENHVER absolut sti og åbne for path-traversal.
            valid_roots = {(s.get("cwd") or "").rstrip("/") for s in STATE["sessions"]}
            valid_roots |= {(p.get("cwd") or "").rstrip("/") for p in STATE["projects"]}
            valid_roots.add(str(MASTERVERSIONER_ROOT))
            valid_roots = {r for r in valid_roots if r}
            try:
                target = Path(file_path).resolve()
            except Exception:
                self._send_json({"ok": False, "error": "Ugyldig sti"}, 400)
                return
            target_str = str(target)
            allowed = any(target_str == r or target_str.startswith(r + "/") for r in valid_roots)
            if not allowed:
                self._send_json({"ok": False, "error": "Filen er ikke tilladt"}, 403)
                return
            # Størrelses- og typebegrænsninger
            size = target.stat().st_size
            if size > 500_000:
                self._send_json({"ok": False, "error": f"Filen er for stor ({size:,} bytes)"}, 400)
                return
            ext = target.suffix.lower()
            lang = EXT_TO_LANG.get(ext, "plaintext")
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                self._send_json({"ok": False, "error": f"Kunne ikke læse: {e}"}, 500)
                return
            self._send_json({
                "ok": True,
                "path": target_str,
                "size": size,
                "language": lang,
                "content": content,
            })
            return

        if self.path == "/api/widgets":
            widgets_file = MASTERVERSIONER_ROOT / "context" / "04_widgets.md"
            if not widgets_file.exists():
                self._send_json({"ok": True, "markdown": "", "exists": False})
                return
            try:
                content = widgets_file.read_text(encoding="utf-8")
                self._send_json({
                    "ok": True,
                    "markdown": content,
                    "exists": True,
                    "path": str(widgets_file),
                })
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/all-folders":
            # Alle umiddelbare undermapper i Masterversioner — inkl. tomme,
            # så man kan flytte chats til mapper uden eksisterende chats
            root = MASTERVERSIONER_ROOT
            folders = []
            if root.exists():
                skip = {"node_modules", "__pycache__", ".wrangler",
                       "Chatoverblik-dist", "cloudflare-backup-2026-05-13"}
                for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                    if (child.is_dir() and not child.name.startswith(".")
                            and child.name not in skip):
                        folders.append({"name": child.name, "cwd": str(child)})
            self._send_json({"folders": folders})
            return
        if self.path.startswith("/api/preview-info"):
            from urllib.parse import urlparse, parse_qs, quote
            qs = parse_qs(urlparse(self.path).query)
            cwd = (qs.get("cwd") or [""])[0]
            if not cwd or not Path(cwd).is_dir():
                self._send_json({"ok": False, "error": "Mappen findes ikke"}, 400)
                return
            base = Path(cwd)
            # Find HTML-filer i roden + 1-2 niveauer dybt (mange projekter har widget/index.html)
            html_files = []
            for f in sorted(base.glob("*.html")):
                html_files.append(f.name)
            for sub in sorted(base.iterdir()):
                if sub.is_dir() and not sub.name.startswith(".") and sub.name not in ("node_modules", "logs", "__pycache__", ".wrangler"):
                    for f in sorted(sub.glob("*.html")):
                        html_files.append(f"{sub.name}/{f.name}")
                    for sub2 in sorted(sub.iterdir()):
                        if sub2.is_dir() and not sub2.name.startswith("."):
                            for f in sorted(sub2.glob("*.html"))[:3]:
                                html_files.append(f"{sub.name}/{sub2.name}/{f.name}")
            if not html_files:
                self._send_json({"ok": False, "error": "Ingen HTML-fil fundet i projektet"}, 400)
                return
            # Foretrukken: index.html i rod, ellers widget/index.html, ellers første
            preferred = ["index.html", "index.cms.html", "widget/index.html",
                        "widget/index.cms.html", "mobile.html", "index.mobile.html"]
            hf_set = set(html_files)
            index_file = next((p for p in preferred if p in hf_set), html_files[0])
            ip = get_local_ip()
            # Token erstatter den tidligere base64-cwd: ikke-gættelig adgangs-
            # nøgle med 1-times TTL. Frontend bruger token til at omkonstruere
            # URL'en hvis brugeren skifter HTML-fil i dropdown.
            token = _new_preview_token(cwd.rstrip("/"))
            # URL-encode hver sti-komponent så filer med æ/ø/å og mellemrum virker
            url_path = "/".join(quote(part) for part in index_file.split("/"))
            url = f"http://{ip}:{PORT}/preview/{token}/{url_path}"
            self._send_json({
                "ok": True,
                "ip": ip,
                "port": PORT,
                "url": url,
                "token": token,
                "default_file": index_file,
                "html_files": html_files,
            })
            return
        if self.path == "/api/workflow-analysis-cached":
            analysis_file = HERE / "analysis.md"
            if analysis_file.exists():
                text = analysis_file.read_text(encoding="utf-8")
                gen, model = "", ""
                first_line = text.splitlines()[0] if text else ""
                if first_line.startswith("<!-- "):
                    meta = first_line.replace("<!--", "").replace("-->", "").strip()
                    for part in meta.split("|"):
                        part = part.strip()
                        if part.startswith("Genereret:"):
                            gen = part.replace("Genereret:", "").strip()
                        elif part.startswith("Model:"):
                            model = part.replace("Model:", "").strip()
                    text = "\n".join(text.splitlines()[2:])
                self._send_json({"ok": True, "markdown": text,
                                "generated_at": gen, "model": model})
            else:
                self._send_json({"ok": False, "error": "Ingen analyse endnu"}, 404)
            return
        if self.path.startswith("/api/search"):
            from urllib.parse import urlparse, parse_qs
            q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0].lower().strip()
            if len(q) < 2:
                self._send_json({"matches": []})
                return
            matches = []
            for key, body in STATE["search_index"].items():
                idx = body.find(q)
                if idx == -1:
                    continue
                # Snippet ~100 chars omkring fundet
                start = max(0, idx - 40)
                end = min(len(body), idx + 120)
                snippet = body[start:end].strip()
                if start > 0:
                    snippet = "…" + snippet
                if end < len(body):
                    snippet = snippet + "…"
                source, sess_id = key.split(":", 1)
                matches.append({"source": source, "id": sess_id, "snippet": snippet})
            self._send_json({"matches": matches})
            return
        if self.path.startswith("/api/chat/"):
            # /api/chat/<source>/<id>
            parts = self.path.split("/")
            if len(parts) >= 5:
                source, sess_id = parts[3], parts[4]
                match = next((s for s in STATE["sessions"]
                              if s["source"] == source and s["id"] == sess_id), None)
                if match:
                    self._send_json({"session": match, "messages": render_chat_for_view(match)})
                    return
            self._send_json({"error": "not found"}, 404)
            return
        self._send_json({"error": "unknown route"}, 404)

    def do_POST(self):
        if self._is_external():
            self._forbidden()
            return
        if self._is_csrf():
            self._send_json({"ok": False, "error": "Ugyldig origin"}, 403)
            return
        length = int(self.headers.get("Content-Length", "0"))
        # Cap: en POST på 5 MB er rigeligt for alle eksisterende endpoints
        # (widgets-doc, project-handover osv.). Forhindrer OOM-DoS.
        if length > 5_000_000:
            self._send_json({"ok": False, "error": "Body for stor"}, 413)
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {}

        if self.path == "/api/rescan":
            with STATE_LOCK:
                running = STATE["rescan_running"]
            if not running:
                threading.Thread(target=perform_rescan,
                                 kwargs={"full": True},
                                 daemon=True).start()
            self._send_json({
                "ok": True,
                "status": "Rescan kører allerede" if running else "Rescan startet",
            })
            return

        if self.path == "/api/open-in-windsurf":
            # Routen hedder fortsat 'windsurf' af bagudkompatibilitetshensyn,
            # men åbner nu VS Code.
            cwd = data.get("cwd", "")
            if not cwd or not Path(cwd).exists():
                self._send_json({"ok": False, "error": "Mappen findes ikke"}, 400)
                return
            source = data.get("source", "")
            # Åbn ALTID præcis på chattens cwd (projektmappen) — vi scanner
            # IKKE opad efter CLAUDE.md. Tidligere gjorde en opad-scanning at
            # de ~58 projekter uden egen CLAUDE.md åbnede hele Masterversioner-
            # roden i stedet for sig selv. Claude/Codex læser stadig den
            # nedarvede CLAUDE.md ved selv at scanne forældre, og chat-historik
            # gemmes per cwd — så projektmappen er den rigtige workspace-rod.
            workspace_root = cwd

            # Find projektnavn til farvevalg + workspace-fil
            project_name = Path(workspace_root).name
            color = project_color(project_name)
            # Generér per-projekt .code-workspace fil — hvert projekt får sin
            # egen identity, så VS Code åbner i nyt vindue, og hvert vindue har
            # sin egen farve (ingen mere shared color via .vscode/settings.json)
            ws_file = get_project_workspace_file(workspace_root, project_name, color)

            mode = data.get("mode", "")
            try:
                code_cli = find_code_cli()

                # Åbn workspace-FILEN i stedet for folder. .code-workspace files
                # giver VS Code en unik workspace-identity per projekt, så -n
                # faktisk skaber et nyt vindue. Hver fil har sin egen farve inline.
                target = ws_file if ws_file else workspace_root
                args = [code_cli, "-n", target]

                if code_cli:
                    logged_popen(args, stdout=subprocess.DEVNULL)
                else:
                    logged_popen(["open", "-a", "Visual Studio Code", workspace_root],
                                 stdout=subprocess.DEVNULL)

                extension_uri = None
                if mode == "new-chat":
                    if source == "claude":
                        extension_uri = CLAUDE_CODE_URI
                    elif source == "codex":
                        extension_uri = CODEX_URI

                # Aktivér KUN VS Code når vi bagefter skal fyre en extension-URI
                # (new-chat). Ved almindelig åbning lader vi `code -n` selv tage
                # fokus på det NYE vindue — ellers ville et øjeblikkeligt
                # 'activate' rive et ANDET, allerede åbent vindue i front før det
                # nye er oppe (du klikkede ét projekt, men endte i et andet).
                if extension_uri:
                    time.sleep(0.8)
                    logged_popen(["osascript", "-e",
                                  'tell application "Visual Studio Code" to activate'])
                    time.sleep(0.2)
                    logged_popen(["open", extension_uri])

                self._send_json({"ok": True, "opened": workspace_root,
                                "workspace_file": ws_file,
                                "color": color, "project": project_name})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/workflow-analysis":
            # Saml struktureret data — sortér nyeste først
            from datetime import datetime, timezone
            sorted_sessions = sorted(
                STATE["sessions"],
                key=lambda s: s.get("ended") or s.get("started") or "",
                reverse=True,
            )
            now = datetime.now(timezone.utc)
            chats_summary = []
            for s in sorted_sessions:
                started = s.get("started", "") or ""
                days_ago = ""
                try:
                    dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    days_ago = (now - dt).days
                except Exception:
                    pass
                chats_summary.append({
                    "projekt": s.get("project", ""),
                    "kilde": s.get("source", ""),
                    "titel": s.get("title", "")[:120],
                    "første_besked": (s.get("first_user", "") or "")[:600],
                    "ai_resumé": s.get("summary", "")[:400],
                    "antal_beskeder": s.get("msg_count", 0),
                    "antal_brugerbeskeder": s.get("user_msg_count", 0),
                    "dage_siden": days_ago,
                    "startet": started[:10],
                })
            projects_summary = []
            for p in STATE["projects"]:
                projects_summary.append({
                    "navn": p.get("name", ""),
                    "antal_chats": p.get("chats", 0),
                    "har_live_url": any(u.get("kind") == "live" for u in p.get("urls", [])),
                    "har_repo": any(u.get("kind") == "repo" for u in p.get("urls", [])),
                    "seneste_aktivitet": (p.get("latest", "") or "")[:10],
                })

            prompt = f"""Du er en ærlig, dygtig konsulent der analyserer en vibe-coders \
workflow. Brugeren er Kristian Jensen — digital journalist på Politiken (Danmarks \
største avis), baggrund i motion design og After Effects. Han bygger interaktive \
widgets, spil og explainers til politiken.dk. Han skriver ikke kode selv — han \
\"vibe-coder\" via AI-assistenter (Claude Code og Codex i VS Code/Windsurf).

VIGTIG VÆGTNING: Chats er sorteret med NYESTE FØRST. Hvert chat har et "dage_siden"-felt. \
Kristian har lært meget undervejs — derfor vægter du nyere chats højere end gamle, fordi \
de afspejler hans nuværende kompetenceniveau. Gamle chats (>120 dage) bruges primært til \
at vise UDVIKLING og hvad han er blevet bedre til, ikke som kritik af hans nuværende niveau.

Her er data fra hans {len(chats_summary)} chats fordelt på {len(projects_summary)} projekter:

PROJEKTER:
{json.dumps(projects_summary, indent=2, ensure_ascii=False)}

CHATS (nyeste først):
{json.dumps(chats_summary, indent=2, ensure_ascii=False)}

Lav en konkret, ærlig analyse i 5 sektioner. Brug markdown. Vær specifik med eksempler/citater \
(citér korte uddrag i kursiv). Skriv på dansk. Pak ikke kritik ind i bomuld — men vær respektfuld.

## 1. Mønstre i hvordan jeg formulerer projekter
Hvad fungerer i hans nyere åbningsbeskeder? Er han blevet bedre over tid? \
Hvor er han stadig vag eller savner info? Citér eksempler (markér gerne om eksemplet er nyt eller gammelt).

## 2. Gentagende bugs og svage sider
Hvilke tekniske emner/problemer dukker op igen og igen — også i de seneste chats? \
Hvor bør han investere i at lære bedre? Skeln mellem "engang-problemer" og "stadig-aktuelle-problemer".

## 3. Færdiggørelses-mønstre + tekniske valg
Hvilke projekter går i mål (live URL) vs strander? Korrelation mellem dybde (beskeder) og succes? \
Tekniske valg han gør igen og igen — over/underengineerer han nogle steder? \
Er der ændringer i hans valg over tid?

## 4. Hvad virker rigtig godt — ros og positive mønstre
Hvad gør han særligt smart i de nyeste chats? Hvilke vaner bør han holde fast i? \
Hvor er han stærkest? Hvilken læringskurve kan du se?

## 5. Konkret to-do: 5-10 vaner at prøve i næste projekt
Praktiske, handlingsbare anbefalinger der bygger på hvor han ER NU. Specifikke ting at prøve. \
Ikke generiske råd. Hvis et råd kun gælder gamle vaner han allerede har fixet, så drop det.

Afslut med en kort 2-linjers "samlet vurdering" der fokuserer på hans nuværende niveau og trajectory."""

            if not ANTHROPIC_KEY:
                self._send_json({"ok": False,
                    "error": "ANTHROPIC_API_KEY mangler — kan ikke køre analyse"}, 400)
                return

            model_choice = pick_model(data.get("model"))
            try:
                text = call_anthropic(prompt, model=model_choice,
                                      max_tokens=4000, timeout=180)
                # Gem til disk for re-visning (metadata i kommentar-linje)
                analysis_file = HERE / "analysis.md"
                ts = time.strftime("%Y-%m-%d %H:%M")
                analysis_file.write_text(
                    f"<!-- Genereret: {ts} | Model: {model_choice} -->\n\n{text}",
                    encoding="utf-8"
                )
                self._send_json({"ok": True, "markdown": text,
                                "generated_at": ts, "model": model_choice})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/project-handover":
            # Genererer "sådan genoptager du dette projekt"-guide
            cwd = data.get("cwd", "")
            project_name = data.get("project", "")
            if not cwd or not Path(cwd).is_dir():
                self._send_json({"ok": False, "error": "Mappe findes ikke"}, 400)
                return
            # Sikkerhed: HANDOVER.md skrives til disk — tillad kun mapper
            # under Masterversioner. Uden dette kan en CSRF-side eller buggy
            # klient få os til at overskrive HANDOVER.md vilkårlige steder.
            try:
                target = Path(cwd).resolve()
            except Exception:
                self._send_json({"ok": False, "error": "Ugyldig sti"}, 400)
                return
            root_str = str(MASTERVERSIONER_ROOT.resolve())
            if not (str(target) == root_str or str(target).startswith(root_str + "/")):
                self._send_json({"ok": False,
                                "error": "Mappen er ikke under Masterversioner"}, 403)
                return
            if not ANTHROPIC_KEY:
                self._send_json({"ok": False, "error": "ANTHROPIC_API_KEY mangler"}, 400)
                return
            # Saml kontekst om projektet
            proj_path = Path(cwd)
            ctx_files = {}
            for fname in ("STATUS.md", "README.md", "LESSONS.md", "AGENT_BRIEF.md",
                          "WORKFLOW_ANCHORS.md", "AI_INDEX.md"):
                p = proj_path / fname
                if p.exists() and p.is_file():
                    try:
                        ctx_files[fname] = p.read_text(encoding="utf-8", errors="replace")[:5000]
                    except Exception:
                        pass
            # Top-level filer i mappen
            try:
                file_list = [f.name for f in sorted(proj_path.iterdir())
                            if not f.name.startswith(".")][:40]
            except Exception:
                file_list = []
            # Chats for projektet (relevante uddrag)
            proj_chats = [s for s in STATE["sessions"]
                         if (s.get("cwd") or "").rstrip("/") == cwd.rstrip("/")]
            chat_summary = []
            for s in sorted(proj_chats,
                          key=lambda x: x.get("ended") or x.get("started") or "",
                          reverse=True)[:15]:
                chat_summary.append({
                    "titel": s.get("title", "")[:120],
                    "resumé": s.get("summary", "")[:300],
                    "antal_beskeder": s.get("msg_count", 0),
                    "startet": (s.get("started", "") or "")[:10],
                })

            ctx_text = "\n\n".join(f"### {fname}\n```\n{content}\n```"
                                   for fname, content in ctx_files.items())
            prompt = f"""Lav en kompakt "genoptag-guide" til et projekt — en kort manual \
en ny person (eller jeg selv om 3 måneder) kan læse på 2 minutter for at forstå projektet \
og komme i gang.

PROJEKT: {project_name}
MAPPE: {cwd}

FILER I MAPPEN:
{json.dumps(file_list, ensure_ascii=False)}

EKSISTERENDE KONTEKST-FILER:
{ctx_text if ctx_text else '(ingen)'}

SENESTE CHATS (nyeste først):
{json.dumps(chat_summary, indent=2, ensure_ascii=False)}

Lav en markdown-guide med disse sektioner. Skriv på dansk. Vær KONKRET — citater fra chats \
og filnavne er bedre end abstrakt beskrivelse.

## Hvad er dette projekt?
1-2 sætninger der fanger essensen. Ikke generelle floskler.

## Status lige nu
Hvor langt er det? Hvad virker, hvad mangler? Live URL hvis sat.

## Sådan kommer du i gang igen
Trin-for-trin: hvilke filer skal du åbne, hvilke kommandoer skal du køre, \
hvor starter en typisk arbejdsdag.

## Nøglefiler og hvad de gør
3-6 vigtigste filer, hver med 1 linje om hvad de er.

## Vigtige tekniske valg
Beslutninger du skal kende for ikke at gå imod dem ved et uheld.

## Faldgruber
Subtle ting (iOS-quirks, deploy-fælder, font-loading) hentet fra LESSONS.md \
eller chats hvis nævnt.

## Næste skridt
1-3 konkrete punkter at gå videre med. Citér evt. STATUS.md hvis relevant.

Afslut med en lille "TL;DR i én linje" der opsummerer projektet."""

            model_choice = pick_model(data.get("model"))
            try:
                text = call_anthropic(prompt, model=model_choice,
                                      max_tokens=2500, timeout=120)
                # Gem som HANDOVER.md i projektmappen
                handover_file = proj_path / "HANDOVER.md"
                ts = time.strftime("%Y-%m-%d %H:%M")
                handover_file.write_text(
                    f"<!-- Genereret af Chatoverblik: {ts} | Model: {model_choice} -->\n\n{text}",
                    encoding="utf-8"
                )
                self._send_json({"ok": True, "markdown": text,
                                "generated_at": ts, "model": model_choice,
                                "file": str(handover_file)})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/weekly-retro":
            # Workflow-analyse begrænset til sidste 7 dage.
            # Parse timestamps til datetime før sammenligning — Claude bruger
            # 'Z'-suffix, isoformat() bruger '+00:00', og string-compare på
            # tværs af de to suffixer er forkert (Z > + lexicografisk).
            from datetime import datetime, timezone, timedelta
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=7)

            def _parse_ts(s):
                if not s:
                    return None
                try:
                    return datetime.fromisoformat(s.replace("Z", "+00:00"))
                except ValueError:
                    return None

            recent = []
            for s in STATE["sessions"]:
                ts = _parse_ts(s.get("ended") or s.get("started"))
                if ts and ts >= cutoff_dt:
                    recent.append(s)
            if not recent:
                self._send_json({"ok": False, "error": "Ingen chats sidste 7 dage"}, 400)
                return
            if not ANTHROPIC_KEY:
                self._send_json({"ok": False, "error": "ANTHROPIC_API_KEY mangler"}, 400)
                return
            recent.sort(key=lambda s: s.get("ended") or s.get("started") or "",
                       reverse=True)
            chat_data = []
            for s in recent:
                chat_data.append({
                    "projekt": s.get("project", ""),
                    "titel": s.get("title", "")[:120],
                    "første_besked": (s.get("first_user", "") or "")[:400],
                    "resumé": s.get("summary", "")[:300],
                    "antal_beskeder": s.get("msg_count", 0),
                    "antal_brugerbeskeder": s.get("user_msg_count", 0),
                    "dato": (s.get("started", "") or "")[:10],
                })
            prompt = f"""Lav en kort ugentlig retrospektiv baseret på Kristians sidste 7 \
dages chats. Han er digital journalist på Politiken, vibe-coder. \
Total: {len(recent)} chats.

CHATS:
{json.dumps(chat_data, indent=2, ensure_ascii=False)}

Lav en kompakt rapport (max 600 ord) i markdown med disse sektioner. \
Vær konkret, kort, ærlig. Skriv på dansk.

## Ugens overblik
- Antal aktive projekter, hvilke
- Hvor brugte du mest tid?
- Største fremskridt

## Hvad gik godt
2-3 konkrete sejre fra ugen

## Hvor sad du fast
2-3 ting der trak energi eller ikke kom videre

## Næste uge — fokus
2-3 konkrete forslag til hvad du bør prioritere

## En enkelt observation
En ting der overraskede dig i mønstrene"""

            model_choice = pick_model(data.get("model"))
            try:
                text = call_anthropic(prompt, model=model_choice,
                                      max_tokens=2000, timeout=90)
                ts = time.strftime("%Y-%m-%d %H:%M")
                self._send_json({"ok": True, "markdown": text,
                                "generated_at": ts, "model": model_choice,
                                "chat_count": len(recent)})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/prompting-review":
            # Fokuseret review af FORMULERINGER — sender Kristians faktiske
            # åbnings-beskeder (first_user) på tværs af de seneste 21 dage til
            # AI'en. Adskiller sig fra workflow-analyse ved at se på HVORDAN
            # Kristian skriver, ikke HVAD chats handler om.
            from datetime import datetime, timezone, timedelta
            days = int(data.get("days") or 21)
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)

            def _parse_ts(s):
                if not s:
                    return None
                try:
                    return datetime.fromisoformat(s.replace("Z", "+00:00"))
                except ValueError:
                    return None

            recent = []
            for s in STATE["sessions"]:
                ts = _parse_ts(s.get("ended") or s.get("started"))
                if ts and ts >= cutoff_dt:
                    recent.append(s)
            if not recent:
                self._send_json({"ok": False,
                    "error": f"Ingen chats sidste {days} dage"}, 400)
                return
            if not ANTHROPIC_KEY:
                self._send_json({"ok": False, "error": "ANTHROPIC_API_KEY mangler"}, 400)
                return

            recent.sort(key=lambda s: s.get("started") or "", reverse=True)
            # Saml chats med både first_user (~1200 tegn) OG last_user (~600 tegn).
            # Sidstnævnte er nødvendig for deliverable #2 (lukning ↔ næste åbning):
            # modellen parrer en chats sidste besked med den næste chats første
            # besked i samme projekt for at se om Kristian lukker eller ebber ud.
            chat_data = []
            for s in recent:
                fu = (s.get("first_user", "") or "").strip()
                if not fu:
                    continue
                # Træk last_user ud af chat-jsonl'en. render_chat_for_view returnerer
                # alle user/assistant-beskeder i kronologisk rækkefølge.
                last_user = ""
                try:
                    msgs = render_chat_for_view(s)
                    for m in reversed(msgs):
                        if m.get("role") == "user" and m.get("text", "").strip():
                            last_user = m["text"].strip()[:600]
                            break
                except Exception:
                    pass
                # Hvis kun én user-besked: last_user == first_user. Drop for
                # at undgå at modellen tror det er to forskellige beskeder.
                if last_user[:200] == fu[:200]:
                    last_user = ""
                chat_data.append({
                    "projekt": s.get("project", ""),
                    "titel": (s.get("title", "") or "")[:120],
                    "kilde": s.get("source", ""),
                    "antal_beskeder": s.get("msg_count", 0),
                    "dato": (s.get("started", "") or "")[:10],
                    "min_aabningsbesked": fu[:1200],
                    "min_sidste_besked": last_user,
                    "resumé": (s.get("summary", "") or "")[:200],
                })
            if not chat_data:
                self._send_json({"ok": False,
                    "error": "Ingen chats med åbningsbesked fundet"}, 400)
                return

            prompt = f"""Du er en reviewer der ser på HVORDAN Kristian \
formulerer sine åbnings- OG lukke-beskeder til AI'er — ikke HVAD chats \
handler om. Han er digital journalist på Politiken, vibe-coder, og leder \
efter mønstre i sine egne formuleringer.

Du har her hans {len(chat_data)} chats fra sidste {days} dage. For hver \
chat ser du første-besked (det HAN skrev som åbning), sidste-besked (det \
HAN skrev før chatten lukkede), titlen, projektet, antal beskeder, dato \
og et kort resumé. Når en chat kun havde én user-besked er min_sidste_besked \
tom.

DATA:
{json.dumps(chat_data, indent=2, ensure_ascii=False)}

Lever en skarp analyse i markdown:

## 1. Mønstre i åbnings-formuleringerne
3-5 mønstre, citerede, skel mellem "virker" og "dårlig vane" — med konkret \
alternativ-formulering for hver dårlig vane. Notér særskilt: genbruger han \
sine egne skabelon-prompts, eller skriver han fra bunden hver gang?

## 2. Lukning og genåbning
Par sidste besked i en chat med første besked i projektets NÆSTE chat \
(sortér chats per projekt efter dato): sluttede chatten med en lukke-handling \
(deploy, STATUS.md, verificering), og samlede næste åbning det op — eller \
ebbede den ud, hvorefter næste chat startede med noget nyt? Citér de \
tydeligste par.

## 3. Definition of done
Hvor mange åbninger siger hvornår opgaven er færdig, eller hvilket bevis \
der kræves ("vi er færdige når...", "testet på mobil", "deployet")? Citér \
de bedste og de mest åbne. Tjek mod gentagelses-signalet: genåbnes chats \
med slutkriterium sjældnere end chats uden?

## 4. Constraints før features
Nævner åbningen de bindende rammer (mobil/desktop, CMS-embed, scope-låst, \
læserdata/sikkerhed), eller er den ren feature-bestilling? Citér eksempler \
på begge.

## 5. Én ting at ændre i morgen
Én sætning til kopi-paste i næste åbnings-besked.

Begrænsninger:
- Ingen kompliment-runde
- Citér faktiske formuleringer som bevis — ingen påstande uden citat
- Hvis du ikke har nok data til et punkt: sig det
"""

            model_choice = pick_model(data.get("model"))
            try:
                # Højt max_tokens-loft fordi en dyb model (Opus) kan bruge
                # extended thinking — hvis budgettet er for lavt æder tankerækker
                # alle tokens og text-blokken returnerer tom. 16000 giver
                # plads til både thinking og det fulde markdown-output.
                text = call_anthropic(prompt, model=model_choice,
                                      max_tokens=16000, timeout=180)
                if not text.strip():
                    self._send_json({"ok": False,
                        "error": (f"{model_choice} returnerede tom text. "
                                 "Sandsynligvis extended-thinking der har \xc3\xa6dt "
                                 "alle tokens. Tjek terminalen for stop_reason. "
                                 "Pr\xc3\xb8v evt. Sonnet 4.6 indtil videre.")},
                        500)
                    return
                ts = time.strftime("%Y-%m-%d %H:%M")
                self._send_json({"ok": True, "markdown": text,
                                "generated_at": ts, "model": model_choice,
                                "chat_count": len(chat_data), "days": days})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/new-project":
            ptype = (data.get("type") or "").strip()
            if ptype not in ("arbejde", "privat"):
                self._send_json({"ok": False, "error": "Type skal være 'arbejde' eller 'privat'"}, 400)
                return
            # Brug eksisterende mappe (top-niveau under Masterversioner) ELLER opret ny
            existing_cwd = (data.get("existing_cwd") or "").strip()
            if existing_cwd:
                try:
                    target = Path(existing_cwd).resolve()
                except Exception:
                    self._send_json({"ok": False, "error": "Ugyldig sti"}, 400)
                    return
                root_str = str(MASTERVERSIONER_ROOT.resolve())
                if not (str(target).startswith(root_str + "/") and target.is_dir()):
                    self._send_json({"ok": False,
                        "error": "Mappen er ikke under Masterversioner"}, 403)
                    return
                base = target
                name = target.name
            else:
                name = (data.get("name") or "").strip()
                if not name or not re.match(r"^[A-Za-zÆØÅæøå0-9 _-]+$", name):
                    self._send_json({"ok": False,
                        "error": "Ugyldigt navn (kun bogstaver, tal, mellemrum, _ og -)"}, 400)
                    return
                base = MASTERVERSIONER_ROOT / name
                if base.exists():
                    self._send_json({"ok": False, "error": f"Mappen findes allerede: {base}"}, 400)
                    return
            created = []
            skipped = []
            try:
                if not existing_cwd:
                    base.mkdir(parents=True)
                # STATUS.md — kun hvis den ikke findes (beskyt eksisterende arbejde)
                status_path = base / "STATUS.md"
                if status_path.exists():
                    skipped.append("STATUS.md")
                else:
                    template = (MASTERVERSIONER_ROOT
                               / "context" / "06_status_template.md")
                    status_text = template.read_text(encoding="utf-8") if template.exists() else ""
                    status_text = (status_text
                                  .replace("<PROJEKTNAVN>", name)
                                  .replace("arbejde | privat", ptype)
                                  .replace("ÅÅÅÅ-MM-DD", time.strftime("%Y-%m-%d")))
                    status_path.write_text(status_text, encoding="utf-8")
                    created.append("STATUS.md")
                # README.md
                readme_path = base / "README.md"
                if readme_path.exists():
                    skipped.append("README.md")
                else:
                    readme_path.write_text(
                        f"# {name}\n\nKort beskrivelse her.\n\nSe STATUS.md for igangværende status.\n",
                        encoding="utf-8")
                    created.append("README.md")
                # .gitignore
                gitignore_path = base / ".gitignore"
                if gitignore_path.exists():
                    skipped.append(".gitignore")
                else:
                    gitignore_path.write_text(
                        ".DS_Store\nnode_modules/\n*.log\n.wrangler/\n",
                        encoding="utf-8")
                    created.append(".gitignore")
                # index.html — opret kun hvis mappen ikke har en *.html i forvejen
                if any(base.glob("*.html")):
                    skipped.append("index.html (anden .html findes allerede)")
                else:
                    (base / "index.html").write_text(
                        f"<!DOCTYPE html>\n<html lang=\"da\">\n<head>\n  <meta charset=\"utf-8\">\n"
                        f"  <title>{name}</title>\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                        f"</head>\n<body>\n  <h1>{name}</h1>\n</body>\n</html>\n",
                        encoding="utf-8")
                    created.append("index.html")
                self._send_json({"ok": True, "path": str(base), "name": name,
                                "created": created, "skipped": skipped,
                                "reused": bool(existing_cwd)})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/widgets":
            # POST: gem context/04_widgets.md
            content = data.get("markdown", "")
            widgets_file = MASTERVERSIONER_ROOT / "context" / "04_widgets.md"
            try:
                # Sørg for at context-mappen findes
                widgets_file.parent.mkdir(exist_ok=True)
                # Backup gammel version
                if widgets_file.exists():
                    backup = widgets_file.with_suffix(".md.bak")
                    backup.write_text(widgets_file.read_text(encoding="utf-8"),
                                     encoding="utf-8")
                widgets_file.write_text(content, encoding="utf-8")
                self._send_json({"ok": True, "saved_at": time.strftime("%Y-%m-%d %H:%M")})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/delete":
            source = data.get("source", "")
            sess_id = data.get("id", "")
            with STATE_LOCK:
                match = next((s for s in STATE["sessions"]
                              if s["source"] == source and s["id"] == sess_id), None)
                if not match:
                    self._send_json({"ok": False, "error": "Chat ikke fundet"}, 404)
                    return
                file_path = Path(match["file"])
                try:
                    if file_path.exists():
                        file_path.unlink()
                    STATE["sessions"] = [s for s in STATE["sessions"]
                                         if not (s["source"] == source and s["id"] == sess_id)]
                    STATE["search_index"].pop(f"{source}:{sess_id}", None)
                    STATE["cache"].pop(f"{source}:{sess_id}", None)
                    save_cache(STATE["cache"])
                    STATE["projects"] = build_projects_index(STATE["sessions"])
                    self._send_json({"ok": True})
                except Exception as e:
                    self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/pin":
            source = data.get("source", "")
            sess_id = data.get("id", "")
            pinned = bool(data.get("pinned"))
            key = f"{source}:{sess_id}"
            with STATE_LOCK:
                cache = STATE["cache"]
                entry = cache.get(key) or {}
                if pinned:
                    entry["pinned"] = True
                else:
                    entry.pop("pinned", None)
                cache[key] = entry
                save_cache(cache)
                for s in STATE["sessions"]:
                    if s["source"] == source and s["id"] == sess_id:
                        s["pinned"] = pinned
                        break
            self._send_json({"ok": True, "pinned": pinned})
            return

        if self.path == "/api/open-in-finder":
            cwd = data.get("cwd", "")
            if not cwd or not Path(cwd).exists():
                self._send_json({"ok": False, "error": "Mappen findes ikke"}, 400)
                return
            try:
                logged_popen(["open", cwd])
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/regenerate-title":
            source = data.get("source", "")
            sess_id = data.get("id", "")
            with STATE_LOCK:
                session = next((s for s in STATE["sessions"]
                                if s["source"] == source and s["id"] == sess_id), None)
                if not session:
                    self._send_json({"ok": False, "error": "Chat ikke fundet"}, 404)
                    return
                cache = STATE["cache"]
                key = f"{source}:{sess_id}"
                # Bevar evt. user_title (manuel omdøbning) men fjern AI-felter
                user_title = (cache.get(key) or {}).get("user_title", "")
                pinned = (cache.get(key) or {}).get("pinned", False)
                cache.pop(key, None)
            # AI-kald uden for locken (kan tage 5-30s) — ai_title_and_summary
            # tager selv locken når den merger ind i cachen.
            result = ai_title_and_summary(session, cache)
            with STATE_LOCK:
                entry = cache.get(key) or {}
                if user_title: entry["user_title"] = user_title
                if pinned: entry["pinned"] = True
                cache[key] = entry
                save_cache(cache)
                session["ai_title"] = result.get("title", "")
                session["summary"] = result.get("summary", "")
                if not user_title:
                    session["title"] = session["ai_title"]
            self._send_json({"ok": True, "title": result.get("title"), "summary": result.get("summary")})
            return

        if self.path == "/api/resume-summary":
            # Genererer et 'genoptag-brief': kompakt resumé af en gammel chat
            # til indsætning som første prompt i en ny chat. Lader brugeren
            # fortsætte med frisk kontekst i stedet for at åbne den fulde chat
            # (som ville tvinge modellen til at læse alle tidligere tool-kald).
            source = data.get("source", "")
            sess_id = data.get("id", "")
            with STATE_LOCK:
                session = next((s for s in STATE["sessions"]
                                if s["source"] == source and s["id"] == sess_id), None)
            if not session:
                self._send_json({"ok": False, "error": "Chat ikke fundet"}, 404)
                return
            if not ANTHROPIC_KEY:
                self._send_json({"ok": False, "error": "ANTHROPIC_API_KEY mangler"}, 400)
                return
            # Hent chat-content som læselig sekvens af user/assistant-beskeder
            try:
                chat_msgs = render_chat_for_view(session)
            except Exception as e:
                self._send_json({"ok": False, "error": f"Kunne ikke læse chat: {e}"}, 500)
                return
            if not chat_msgs:
                self._send_json({"ok": False, "error": "Chatten er tom"}, 400)
                return
            # Cap chat-tekst — meget lange chats sender vi de første ~80k + de
            # sidste ~40k tegn af (intro + nylige beslutninger). Holder os under
            # Sonnet's context window og fokuserer på det vigtigste.
            chat_text_full = "\n\n".join(
                f"[{m['role'].upper()}] {m['text']}" for m in chat_msgs
            )
            if len(chat_text_full) > 120_000:
                chat_text = (chat_text_full[:80_000]
                             + "\n\n[…midten af chatten klippet…]\n\n"
                             + chat_text_full[-40_000:])
            else:
                chat_text = chat_text_full
            project_name = session.get("project") or "(ukendt projekt)"
            prompt = f"""Du laver et 'genoptag-brief' til Kristian. Han har \
tidligere haft denne chat om projektet '{project_name}' og vil fortsætte \
arbejdet i en NY chat med frisk kontekst (i stedet for at åbne den fulde \
gamle chat). Briefet bliver indsat som første prompt i den nye chat.

Skriv på dansk. Max 400 ord. Brug markdown. Vær KONKRET — citér filnavne, \
specifikke beslutninger, faktiske kommandoer.

Format:

## Hvad chatten handlede om
1-2 sætninger der fanger essensen.

## Hvad blev besluttet
2-4 bullets med konkrete beslutninger der blev truffet (arkitektur, biblioteker, \
flow). Tag KUN ting med der faktisk blev konkluderet — ikke ting der bare blev \
nævnt.

## Hvad virker / er færdigt
Bullets med tilstand der er afsluttet og deployet/testet.

## Hvad mangler / blev ikke løst
Bullets med åbne ender Kristian skal videre med.

## Filer der blev rørt
Op til 5 centrale filer (med kort beskrivelse af hvad de gør i konteksten).

## Vigtige fælder
Antagelser eller bugs Kristian skal være OBS på — 'hvis du gør X, så fejler Y'. \
Spring sektionen over hvis der ingen er.

CHAT-INDHOLD:
{chat_text}"""
            model_choice = pick_model(data.get("model"))
            try:
                text = call_anthropic(prompt, model=model_choice,
                                      max_tokens=2000, timeout=90)
                ts = time.strftime("%Y-%m-%d %H:%M")
                self._send_json({
                    "ok": True,
                    "summary": text,
                    "project": project_name,
                    "cwd": session.get("cwd", ""),
                    "source": source,
                    "model": model_choice,
                    "generated_at": ts,
                    "original_title": session.get("title", ""),
                })
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
            return

        if self.path == "/api/move-chat":
            # Flyt en chat til en anden projektmappe — gemmer user_cwd-override
            # i cache.json uden at røre selve .jsonl-filen
            source = data.get("source", "")
            sess_id = data.get("id", "")
            target_cwd = (data.get("target_cwd") or "").rstrip("/")
            if not target_cwd or not Path(target_cwd).is_dir():
                self._send_json({"ok": False, "error": "Mål-mappen findes ikke"}, 400)
                return
            key = f"{source}:{sess_id}"
            with STATE_LOCK:
                cache = STATE["cache"]
                entry = cache.get(key) or {}
                entry["user_cwd"] = target_cwd
                cache[key] = entry
                save_cache(cache)
                for s in STATE["sessions"]:
                    if s["source"] == source and s["id"] == sess_id:
                        s["original_cwd"] = s.get("original_cwd") or s.get("cwd", "")
                        s["cwd"] = target_cwd
                        s["project"] = project_name_from_cwd(target_cwd)
                        s["cwd_hint"] = ""
                        s["user_cwd"] = target_cwd
                        break
                STATE["projects"] = build_projects_index(STATE["sessions"])
            self._send_json({"ok": True,
                            "project": project_name_from_cwd(target_cwd)})
            return

        if self.path == "/api/rename":
            source = data.get("source", "")
            sess_id = data.get("id", "")
            new_title = (data.get("title") or "").strip()[:120]
            key = f"{source}:{sess_id}"
            with STATE_LOCK:
                cache = STATE["cache"]
                entry = cache.get(key) or {}
                if new_title:
                    entry["user_title"] = new_title
                else:
                    entry.pop("user_title", None)
                cache[key] = entry
                save_cache(cache)
                for s in STATE["sessions"]:
                    if s["source"] == source and s["id"] == sess_id:
                        s["user_title"] = new_title
                        s["title"] = new_title or s.get("ai_title") or fallback_title(s["first_user"])
                        break
            self._send_json({"ok": True, "title": new_title})
            return

        self._send_json({"error": "unknown route"}, 404)


def main():
    # Start scanning + AI-titler i baggrunden
    threading.Thread(target=background_load, daemon=True).start()
    threading.Thread(target=rescan_loop, daemon=True).start()
    print(f"\n  Chatoverblik kører på  →  http://localhost:{PORT}\n")
    print("  (Stop med Ctrl+C)\n")
    # Åbn browseren automatisk
    try:
        logged_popen(["open", f"http://localhost:{PORT}"])
    except Exception:
        pass
    try:
        # 0.0.0.0 så telefoner på samme WiFi kan tilgå /preview/-ruten.
        # Sikkerhed: do_GET/do_POST checker self._is_external() og
        # tillader KUN /preview/* udadtil — alle andre API-kald nægtes.
        with http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nLukker.")


if __name__ == "__main__":
    main()
