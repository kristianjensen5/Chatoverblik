#!/usr/bin/env python3
"""Byg current-kollegapakken fra release_manifest.json."""

import argparse
import json
import stat
import sys
import zipfile
from pathlib import Path


def repo_root():
    return Path(__file__).resolve().parents[1]


def main():
    root = repo_root()
    manifest = json.loads((root / "release_manifest.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(root / "release" / manifest["current_package"]),
        help="Output-zip. Default: release/<current_package>",
    )
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in manifest["files"]:
            src = root / item["src"]
            dst = Path(manifest["root_dir"]) / item["dst"]
            info = zipfile.ZipInfo(dst.as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = src.stat().st_mode
            if mode & stat.S_IXUSR:
                info.external_attr = 0o755 << 16
            else:
                info.external_attr = 0o644 << 16
            zf.writestr(info, src.read_bytes())
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
