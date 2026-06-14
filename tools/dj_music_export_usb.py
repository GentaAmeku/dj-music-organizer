#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def read_config(root: Path, config_name: str) -> dict[str, Any]:
    with (root / config_name).open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_export_files(root: Path, config: dict[str, Any]) -> list[Path]:
    extensions = {ext.lower() for ext in config["audio_extensions"]}
    analyzed = root / config["analyzed_dir"]
    playlists = root / config.get("playlist_dir", "playlists")

    files: list[Path] = []
    if analyzed.exists():
        files.extend(
            p for p in analyzed.rglob("*") if p.is_file() and p.suffix.lower() in extensions
        )
    if playlists.exists():
        files.extend(p for p in playlists.rglob("*.m3u8") if p.is_file())
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export DJ Music analyzed files and playlists to USB.")
    parser.add_argument("--library-root", required=True, help="Source DJ Music root folder")
    parser.add_argument("--usb-root", required=True, help="USB root folder, not the DJ Music folder itself")
    parser.add_argument("--config", default="dj_music_organizer.config.json")
    parser.add_argument("--apply", action="store_true", help="Copy files")
    parser.add_argument("--update", action="store_true", help="Update existing files when source differs")
    args = parser.parse_args()

    root = Path(args.library_root).expanduser().resolve()
    usb_root = Path(args.usb_root).expanduser().resolve()
    target_root = usb_root / root.name
    config = read_config(root, args.config)
    files = iter_export_files(root, config)

    print("APPLY MODE" if args.apply else "DRY RUN - no files will be copied")
    print(f"library_root: {root}")
    print(f"usb_target: {target_root}\n")

    copy_count = 0
    skip_count = 0
    update_count = 0

    for source in files:
        rel = source.relative_to(root)
        dest = target_root / rel
        action = "copy"
        if dest.exists():
            if args.update and (source.stat().st_size != dest.stat().st_size or int(source.stat().st_mtime) > int(dest.stat().st_mtime)):
                action = "update"
            else:
                action = "skip"

        print(f"[{action.upper()}] {source} -> {dest}")

        if action == "copy":
            copy_count += 1
        elif action == "update":
            update_count += 1
        else:
            skip_count += 1

        if args.apply and action in {"copy", "update"}:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)

    print("\nSummary:")
    print(f"  total: {len(files)}")
    print(f"  copy: {copy_count}")
    print(f"  update: {update_count}")
    print(f"  skip: {skip_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
