# P0 hardening baseline

Dato: 2026-07-11

## 1. Kollegadistribution

- Source-of-truth: `release_manifest.json`.
- Build: `python3 scripts/build_release.py --output <zip>`.
- Check: `python3 scripts/release_check.py --json`.
- Den gamle `../Chatoverblik-dist` og `../Chatoverblik-1.0.zip` er markeret som
  `blocked_legacy_artifacts`. Release-check accepterer dem kun som legacy og
  bygger aldrig current-pakken fra dem.

Bevis:

```text
python3 scripts/release_check.py --json
ok: true
legacy blocked (unsafe, not current): ../Chatoverblik-dist
legacy blocked (unsafe, not current): ../Chatoverblik-1.0.zip
```

## 2. Tredjepartskode og CSP

- Eksterne jsdelivr script-tags er fjernet fra `index.html`.
- App-HTML serveres med nonce-baseret CSP via `APP_CSP`.
- API-svar serveres med `default-src 'none'`.
- Preview har separat CSP og path-gate.

Bevis:

```text
python3 -m unittest discover -s tests -v
test_csp_is_strict_for_app_and_api ... ok
```

## 3. Canonical path-validator

- Central validator: `validate_canonical_path()`.
- Bruges til `file-tree`, `file-content`, `move-chat` og `preview`.
- Denylist dækker secrets, datafiler, rå chats/logs/cache og kildenote-mapper.

Bevis:

```text
test_path_traversal_and_secret_denylist ... ok
test_file_tree_filters_data_and_source_notes ... ok
test_move_chat_and_preview_block_sensitive_paths ... ok
```

## 4. Cloud-AI default-deny

- Automatisk AI-titelgenerering kræver både `COMMAND_CENTER_AUTO_AI_TITLES=1`
  og en projektmarkør `.command-center-cloud-ai-ok`.
- Manuelle AI-ruter returnerer først `409 requires_confirmation` med præcis
  payload og SHA-256-hash.
- Frontend viser payloaden i en readonly tekstboks og sender først efter aktivt
  klik på `Send til cloud-AI`.

Bevis:

```text
test_sensitive_ai_chat_requires_payload_confirmation ... ok
```

## 5. Regressionstests

Committed testfil: `tests/test_p0_hardening.py`.

Dækker:

- CSRF
- gammel RCE-rute
- path traversal
- secret/data/source-note denylist
- følsom AI-chat confirmation
- distributionspakken og legacy-blokering

Bevis:

```text
python3 -m py_compile chatoverblik.py scripts/release_check.py scripts/build_release.py tests/test_p0_hardening.py
python3 -m unittest discover -s tests -v
Ran 8 tests ... OK
```
