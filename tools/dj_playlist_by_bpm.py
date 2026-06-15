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
            if entry.get("status") in {"applied", "copied_archived", "bpm_corrected"} and entry.get("dest_path"):
                entries.append(entry)
    return entries


def latest_existing_entries_by_dest(root: Path, config: dict[str, Any]) -> dict[Path, dict[str, Any]]:
    log_path = root / config["log_file"]

    latest_by_dest: dict[Path, dict[str, Any]] = {}
    for entry in read_successful_entries(log_path):
        dest = Path(entry["dest_path"])
        if dest.exists():
            latest_by_dest[dest] = entry
    return latest_by_dest


def tempos_for_entry(entry: dict[str, Any], include_candidates: bool) -> set[int | None]:
    tempos: set[int | None] = set()
    rounded_bpm = entry.get("rounded_bpm")
    if isinstance(rounded_bpm, int):
        tempos.add(rounded_bpm)
    else:
        tempos.add(None)

    if include_candidates:
        for candidate in entry.get("bpm_candidates") or []:
            if isinstance(candidate, int):
                tempos.add(candidate)
    return tempos


def grouped_audio_files_from_entries(
    entries_by_dest: dict[Path, dict[str, Any]],
    config: dict[str, Any],
    include_candidates: bool,
) -> dict[str, set[Path]]:
    grouped: dict[str, set[Path]] = {name: set() for name in bpm_playlist_names(config)}
    for dest, entry in entries_by_dest.items():
        for tempo in tempos_for_entry(entry, include_candidates):
            grouped.setdefault(bpm_folder(tempo, config["bpm_ranges"]), set()).add(dest)

    return grouped


def global_grouped_audio_files(
    root: Path,
    config: dict[str, Any],
    include_candidates: bool,
    entries_by_dest: dict[Path, dict[str, Any]],
) -> dict[str, set[Path]]:
    if include_candidates:
        return grouped_audio_files_from_entries(entries_by_dest, config, include_candidates=True)
    return {name: set(audio_files_for_bpm(root, config, name)) for name in bpm_playlist_names(config)}


def collection_grouped_audio_files(
    config: dict[str, Any],
    include_candidates: bool,
    entries_by_dest: dict[Path, dict[str, Any]],
) -> dict[str, dict[str, set[Path]]]:
    grouped: dict[str, dict[str, set[Path]]] = {}
    for dest, entry in entries_by_dest.items():
        source_hint = sanitize_playlist_name(str(entry.get("source_hint") or "UnknownSource"))
        source_groups = grouped.setdefault(
            source_hint,
            {name: set() for name in bpm_playlist_names(config)},
        )
        for tempo in tempos_for_entry(entry, include_candidates):
            source_groups.setdefault(bpm_folder(tempo, config["bpm_ranges"]), set()).add(dest)
    return grouped


def playlist_lines(paths: list[Path], playlist_path: Path) -> list[str]:
    lines = ["#EXTM3U"]
    playlist_dir = playlist_path.parent.resolve()
    for path in paths:
        rel = os.path.relpath(path.resolve(), playlist_dir).replace(os.sep, "/")
        lines.append(rel)
    return lines


def write_playlist(playlist_path: Path, paths: list[Path], apply: bool) -> None:
    lines = playlist_lines(paths, playlist_path)
    print(f"[PLAYLIST] {playlist_path}")
    print(f"  tracks: {len(paths)}")
    if apply:
        playlist_path.parent.mkdir(parents=True, exist_ok=True)
        playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_bpm_playlists(
    playlist_root: Path,
    groups: dict[str, set[Path]],
    names: list[str],
    only_non_empty: bool,
    apply: bool,
) -> tuple[int, int, int]:
    generated = 0
    skipped_empty = 0
    total_tracks = 0

    for bpm_name in names:
        paths = sorted(groups.get(bpm_name, set()))
        if only_non_empty and not paths:
            skipped_empty += 1
            continue

        write_playlist(playlist_root / f"{bpm_name}.m3u8", paths, apply)
        generated += 1
        total_tracks += len(paths)

    return generated, skipped_empty, total_tracks


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate BPM folder .m3u8 playlists.")
    parser.add_argument("--library-root", required=True, help="DJ Music root folder")
    parser.add_argument("--config", default="dj_music_organizer.config.json")
    parser.add_argument("--apply", action="store_true", help="Write playlist files")
    parser.add_argument(
        "--scope",
        choices=["collections", "global", "both"],
        default="collections",
        help="Playlist tree to generate",
    )
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
    playlist_dir = root / config.get("playlist_dir", "playlists")
    entries_by_dest = latest_existing_entries_by_dest(root, config)
    bpm_names = bpm_playlist_names(config)

    print("APPLY MODE" if args.apply else "DRY RUN - no playlist files will be written")
    print(f"library_root: {root}")
    print(f"playlist_dir: {playlist_dir}")
    print(f"scope: {args.scope}")
    print(f"include_candidates: {args.include_candidates}\n")

    total_tracks = 0
    generated = 0
    skipped_empty = 0

    if args.scope in {"global", "both"}:
        global_root = playlist_dir / "Global" / "BPM"
        groups = global_grouped_audio_files(root, config, args.include_candidates, entries_by_dest)
        gen, skip, tracks = generate_bpm_playlists(
            global_root,
            groups,
            bpm_names,
            args.only_non_empty,
            args.apply,
        )
        generated += gen
        skipped_empty += skip
        total_tracks += tracks

    if args.scope in {"collections", "both"}:
        collections = collection_grouped_audio_files(config, args.include_candidates, entries_by_dest)
        for source_hint, groups in sorted(collections.items()):
            source_root = playlist_dir / "Collections" / source_hint
            all_paths = sorted({path for paths in groups.values() for path in paths})
            if not (args.only_non_empty and not all_paths):
                write_playlist(source_root / f"{source_hint}_All.m3u8", all_paths, args.apply)
                generated += 1
                total_tracks += len(all_paths)
            elif args.only_non_empty:
                skipped_empty += 1

            gen, skip, tracks = generate_bpm_playlists(
                source_root / "BPM",
                groups,
                bpm_names,
                args.only_non_empty,
                args.apply,
            )
            generated += gen
            skipped_empty += skip
            total_tracks += tracks

    print("\nSummary:")
    print(f"  playlists: {generated}")
    print(f"  skipped_empty: {skipped_empty}")
    print(f"  tracks: {total_tracks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
