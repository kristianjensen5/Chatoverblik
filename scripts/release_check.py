#!/usr/bin/env python3
"""Reproducerbar release-check for Command Center.

Checker kun lokale filer. Ingen netværk, ingen deploy, ingen sletning.
"""

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path


TEXT_EXTS = {".py", ".html", ".md", ".txt", ".command", ".json"}


def repo_root():
    return Path(__file__).resolve().parents[1]


def load_manifest(root):
    manifest_path = root / "release_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def iter_manifest_files(root, manifest):
    for item in manifest["files"]:
        src = root / item["src"]
        dst = Path(manifest["root_dir"]) / item["dst"]
        yield src, dst


def scan_text(name, text, banned):
    hits = []
    for pattern in banned:
        if pattern in text:
            hits.append(f"{name}: banned pattern {pattern!r}")
    return hits


def build_release_bytes(root, manifest):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, dst in iter_manifest_files(root, manifest):
            zf.write(src, dst.as_posix())
    return buf.getvalue()


def check_current_source(root, manifest):
    errors = []
    for src, _dst in iter_manifest_files(root, manifest):
        if not src.exists() or not src.is_file():
            errors.append(f"missing release source: {src.relative_to(root)}")
            continue
        if src.suffix.lower() in TEXT_EXTS:
            text = src.read_text(encoding="utf-8", errors="replace")
            errors.extend(scan_text(str(src.relative_to(root)), text,
                                    manifest["banned_text_patterns"]))
    index = (root / "index.html").read_text(encoding="utf-8", errors="replace")
    if "<script src=\"https://" in index or "<script src='https://" in index:
        errors.append("index.html: external executable script tag is not allowed")
    server = (root / "chatoverblik.py").read_text(encoding="utf-8", errors="replace")
    if "Content-Security-Policy" not in server or "APP_CSP" not in server:
        errors.append("chatoverblik.py: strict CSP header is missing")
    return errors


def check_zip_bytes(zip_bytes, manifest):
    errors = []
    names_seen = set()
    expected = {
        (Path(manifest["root_dir"]) / item["dst"]).as_posix()
        for item in manifest["files"]
    }
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            names_seen.add(info.filename)
            suffix = Path(info.filename).suffix.lower()
            if suffix in TEXT_EXTS:
                text = zf.read(info.filename).decode("utf-8", errors="replace")
                errors.extend(scan_text(info.filename, text,
                                        manifest["banned_text_patterns"]))
    missing = sorted(expected - names_seen)
    extra = sorted(names_seen - expected)
    if missing:
        errors.append("release zip missing files: " + ", ".join(missing))
    if extra:
        errors.append("release zip contains non-manifest files: " + ", ".join(extra))
    return errors


def legacy_artifact_has_banned_patterns(path, manifest):
    banned = manifest["banned_text_patterns"]
    if path.is_dir():
        for child in path.rglob("*"):
            if child.is_file() and child.suffix.lower() in TEXT_EXTS:
                text = child.read_text(encoding="utf-8", errors="replace")
                if scan_text(str(child), text, banned):
                    return True
        return False
    if path.is_file() and path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path, "r") as zf:
                for info in zf.infolist():
                    if Path(info.filename).suffix.lower() in TEXT_EXTS:
                        text = zf.read(info.filename).decode("utf-8", errors="replace")
                        if scan_text(info.filename, text, banned):
                            return True
        except zipfile.BadZipFile:
            return True
    return False


def check_legacy_artifacts(root, manifest):
    evidence = []
    errors = []
    for rel in manifest.get("blocked_legacy_artifacts", []):
        path = (root / rel).resolve()
        if not path.exists():
            evidence.append(f"legacy missing: {rel}")
            continue
        if legacy_artifact_has_banned_patterns(path, manifest):
            evidence.append(f"legacy blocked (unsafe, not current): {rel}")
        else:
            errors.append(f"legacy artifact no longer matches blocked signature: {rel}")
    return errors, evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    manifest = load_manifest(root)
    errors = []
    evidence = []

    errors.extend(check_current_source(root, manifest))
    zip_bytes = build_release_bytes(root, manifest)
    errors.extend(check_zip_bytes(zip_bytes, manifest))
    legacy_errors, legacy_evidence = check_legacy_artifacts(root, manifest)
    errors.extend(legacy_errors)
    evidence.extend(legacy_evidence)

    result = {
        "ok": not errors,
        "package": manifest["current_package"],
        "manifest_files": [item["dst"] for item in manifest["files"]],
        "evidence": evidence,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("release-check:", "OK" if result["ok"] else "FAILED")
        for line in evidence:
            print("evidence:", line)
        for line in errors:
            print("error:", line)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
