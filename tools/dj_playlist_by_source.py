#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


def sanitize_playlist_name(value: str) -> str:
    value = "".join(c if 32 <= ord(c) <= 126 and c not in '<>:"/\\|?*' else "_" for c in value)
    value = re.sub(r"_+", "_", value).strip(" ._")
    return value or "UnknownSource"


def read_config(root: Path, config_name: str) -> dict[str, Any]:
    with (root / config_name).open("r", encoding="utf-8") as f:
        return json.load(f)


def read_entries(log_path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not log_path.exists():
        return entries
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("status") in {"applied", "copied_archived"} and entry.get("source_hint"):
                entries.append(entry)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate source_hint .m3u8 playlists.")
    parser.add_argument("--library-root", required=True, help="DJ Music root folder")
    parser.add_argument("--config", default="dj_music_organizer.config.json")
    parser.add_argument("--apply", action="store_true", help="Write playlist files")
    parser.add_argument("--include-missing", action="store_true", help="Include paths whose files are missing")
    args = parser.parse_args()

    root = Path(args.library_root).expanduser().resolve()
    config = read_config(root, args.config)
    log_path = root / config["log_file"]
    playlist_dir = root / config.get("playlist_dir", "playlists")
    entries = read_entries(log_path)

    grouped: dict[str, set[Path]] = {}
    for entry in entries:
        dest = Path(entry["dest_path"])
        if not dest.exists() and not args.include_missing:
            continue
        grouped.setdefault(entry["source_hint"], set()).add(dest)

    print("APPLY MODE" if args.apply else "DRY RUN - no playlist files will be written")
    print(f"library_root: {root}")
    print(f"log: {log_path}\n")

    if args.apply:
        playlist_dir.mkdir(parents=True, exist_ok=True)

    for source_hint, paths in sorted(grouped.items()):
        playlist_path = playlist_dir / f"{sanitize_playlist_name(source_hint)}.m3u8"
        lines = ["#EXTM3U"]
        for path in sorted(paths):
            rel = os.path.relpath(path.resolve(), playlist_dir.resolve()).replace(os.sep, "/")
            lines.append(rel)

        print(f"[PLAYLIST] {playlist_path}")
        print(f"  tracks: {len(paths)}")
        if args.apply:
            playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\nSummary:")
    print(f"  sources: {len(grouped)}")
    print(f"  tracks: {sum(len(v) for v in grouped.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
