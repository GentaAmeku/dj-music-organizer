#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dj_music_organizer import (
    bpm_folder,
    load_bpm_overrides,
    load_config,
    lookup_bpm_override,
    path_matches_hash,
    sha256_file,
    unique_path,
)


TAG_SUFFIX_RE = re.compile(
    r"(?P<base>.+?)_(?P<bpm>UnknownBPM|\d{1,3}BPM)_(?P<key>UnknownKey|(?:[1-9]|1[0-2])[AB])$",
    re.IGNORECASE,
)


def iter_analyzed_files(root: Path, config: dict[str, Any]) -> list[Path]:
    extensions = {ext.lower() for ext in config["audio_extensions"]}
    analyzed = root / config["analyzed_dir"]
    if not analyzed.exists():
        return []
    return sorted(p for p in analyzed.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def corrected_filename(path: Path, rounded_bpm: int) -> str:
    match = TAG_SUFFIX_RE.match(path.stem)
    if match:
        stem = f"{match.group('base')}_{rounded_bpm}BPM_{match.group('key')}"
    else:
        stem = f"{path.stem}_{rounded_bpm}BPM_UnknownKey"
    return f"{stem}{path.suffix.lower()}"


def correction_log_entry(
    source_path: Path,
    dest_path: Path,
    file_hash: str,
    override: dict[str, Any],
    rounded_bpm: int,
    source_hint: str | None,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_path": None,
        "archive_path": None,
        "dest_path": str(dest_path),
        "previous_dest_path": str(source_path),
        "original_filename": source_path.name,
        "new_filename": dest_path.name,
        "source_hint": source_hint,
        "file_sha256": file_hash,
        "estimated_bpm": float(override["bpm"]),
        "rounded_bpm": rounded_bpm,
        "bpm_candidates": [rounded_bpm],
        "bpm_source": str(override.get("source") or "override"),
        "bpm_policy": "override",
        "bpm_alternatives": [],
        "bpm_confidence": "manual",
        "estimated_key_raw": None,
        "estimated_key": None,
        "camelot": None,
        "status": status,
        "error": error,
    }


def source_hint_from_logs(log_path: Path) -> dict[str, str | None]:
    hints: dict[str, str | None] = {}
    if not log_path.exists():
        return hints
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            digest = entry.get("file_sha256")
            if digest and entry.get("source_hint"):
                hints[str(digest)] = str(entry["source_hint"])
    return hints


def main() -> int:
    parser = argparse.ArgumentParser(description="Move/rename analyzed files using bpm_overrides.json.")
    parser.add_argument("--library-root", required=True, help="DJ Music root folder")
    parser.add_argument("--config", default="dj_music_organizer.config.json")
    parser.add_argument("--apply", action="store_true", help="Actually move files and append correction logs")
    args = parser.parse_args()

    root = Path(args.library_root).expanduser().resolve()
    config = load_config(root, args.config)
    overrides = load_bpm_overrides(root, config)
    log_path = root / config["log_file"]
    hints = source_hint_from_logs(log_path)
    files = iter_analyzed_files(root, config)
    reserved: set[Path] = set()

    print("APPLY MODE" if args.apply else "DRY RUN - no files will be changed")
    print(f"library_root: {root}")
    print(f"files: {len(files)}\n")

    planned: list[dict[str, Any]] = []
    for path in files:
        digest = sha256_file(path)
        override = lookup_bpm_override(overrides, path, digest)
        if not override:
            continue
        rounded_bpm = int(round(float(override["bpm"])))
        dest_name = corrected_filename(path, rounded_bpm)
        dest = root / config["analyzed_dir"] / bpm_folder(rounded_bpm, config["bpm_ranges"]) / dest_name
        dest = unique_path(dest, reserved, digest)
        reserved.add(dest)
        if path.resolve() == dest.resolve():
            continue
        planned.append(
            {
                "source": path,
                "dest": dest,
                "digest": digest,
                "override": override,
                "rounded_bpm": rounded_bpm,
                "source_hint": hints.get(digest),
            }
        )

    for item in planned:
        print(f"[BPM FIX] {item['source']}")
        print(f"  -> {item['dest']}")
        print(f"  rekordbox bpm: {item['override']['bpm']}")

    print("\nSummary:")
    print(f"  corrections: {len(planned)}")
    if not args.apply:
        return 0

    with log_path.open("a", encoding="utf-8") as log:
        for item in planned:
            source = item["source"]
            dest = item["dest"]
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and not path_matches_hash(dest, item["digest"]):
                    raise FileExistsError(f"destination exists with different content: {dest}")
                if not dest.exists():
                    source.replace(dest)
                elif source.exists():
                    source.unlink()
                entry = correction_log_entry(
                    source,
                    dest,
                    item["digest"],
                    item["override"],
                    item["rounded_bpm"],
                    item["source_hint"],
                    "bpm_corrected",
                )
                print(f"[APPLIED] {source} -> {dest}")
            except Exception as exc:
                entry = correction_log_entry(
                    source,
                    dest,
                    item["digest"],
                    item["override"],
                    item["rounded_bpm"],
                    item["source_hint"],
                    "error",
                    str(exc),
                )
                print(f"[ERROR] {source}: {exc}", file=sys.stderr)
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
