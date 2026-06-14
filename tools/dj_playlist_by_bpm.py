#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def read_config(root: Path, config_name: str) -> dict[str, Any]:
    with (root / config_name).open("r", encoding="utf-8") as f:
        return json.load(f)


def bpm_playlist_names(config: dict[str, Any]) -> list[str]:
    names = [str(item["name"]) for item in config["bpm_ranges"]]
    names.append("UnknownBPM")
    return names


def bpm_folder(rounded_bpm: int | None, ranges: list[dict[str, Any]]) -> str:
    if rounded_bpm is None:
        return "UnknownBPM"
    for item in ranges:
        lo = item.get("min")
        hi = item.get("max")
        if (lo is None or rounded_bpm >= lo) and (hi is None or rounded_bpm <= hi):
            return str(item["name"])
    return "UnknownBPM"


def audio_files_for_bpm(root: Path, config: dict[str, Any], bpm_name: str) -> list[Path]:
    extensions = {ext.lower() for ext in config["audio_extensions"]}
    folder = root / config["analyzed_dir"] / bpm_name
    if not folder.exists():
        return []
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def read_successful_entries(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []

    entries: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("status") in {"applied", "copied_archived"} and entry.get("dest_path"):
                entries.append(entry)
    return entries


def candidate_grouped_audio_files(root: Path, config: dict[str, Any]) -> dict[str, set[Path]]:
    grouped: dict[str, set[Path]] = {name: set() for name in bpm_playlist_names(config)}
    log_path = root / config["log_file"]

    latest_by_dest: dict[Path, dict[str, Any]] = {}
    for entry in read_successful_entries(log_path):
        dest = Path(entry["dest_path"])
        latest_by_dest[dest] = entry

    for dest, entry in latest_by_dest.items():
        if not dest.exists():
            continue

        tempos: set[int | None] = set()
        rounded_bpm = entry.get("rounded_bpm")
        if isinstance(rounded_bpm, int):
            tempos.add(rounded_bpm)
        else:
            tempos.add(None)

        for candidate in entry.get("bpm_candidates") or []:
            if isinstance(candidate, int):
                tempos.add(candidate)

        for tempo in tempos:
            grouped.setdefault(bpm_folder(tempo, config["bpm_ranges"]), set()).add(dest)

    return grouped


def playlist_lines(paths: list[Path], playlist_path: Path) -> list[str]:
    lines = ["#EXTM3U"]
    playlist_dir = playlist_path.parent.resolve()
    for path in paths:
        rel = os.path.relpath(path.resolve(), playlist_dir).replace(os.sep, "/")
        lines.append(rel)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate BPM folder .m3u8 playlists.")
    parser.add_argument("--library-root", required=True, help="DJ Music root folder")
    parser.add_argument("--config", default="dj_music_organizer.config.json")
    parser.add_argument("--apply", action="store_true", help="Write playlist files")
    parser.add_argument(
        "--only-non-empty",
        action="store_true",
        help="Generate only BPM playlists that contain at least one track",
    )
    parser.add_argument(
        "--include-candidates",
        action="store_true",
        help="Also include bpm_candidates from organizer_log.jsonl in BPM playlists",
    )
    args = parser.parse_args()

    root = Path(args.library_root).expanduser().resolve()
    config = read_config(root, args.config)
    playlist_root = root / config.get("playlist_dir", "playlists") / "BPM"
    candidate_groups = candidate_grouped_audio_files(root, config) if args.include_candidates else {}

    print("APPLY MODE" if args.apply else "DRY RUN - no playlist files will be written")
    print(f"library_root: {root}")
    print(f"playlist_root: {playlist_root}\n")

    if args.apply:
        playlist_root.mkdir(parents=True, exist_ok=True)

    total_tracks = 0
    generated = 0
    skipped_empty = 0

    for bpm_name in bpm_playlist_names(config):
        if args.include_candidates:
            paths = sorted(candidate_groups.get(bpm_name, set()))
        else:
            paths = audio_files_for_bpm(root, config, bpm_name)
        if args.only_non_empty and not paths:
            skipped_empty += 1
            continue

        playlist_path = playlist_root / f"{bpm_name}.m3u8"
        lines = playlist_lines(paths, playlist_path)
        print(f"[PLAYLIST] {playlist_path}")
        print(f"  tracks: {len(paths)}")

        total_tracks += len(paths)
        generated += 1

        if args.apply:
            playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\nSummary:")
    print(f"  playlists: {generated}")
    print(f"  skipped_empty: {skipped_empty}")
    print(f"  tracks: {total_tracks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
