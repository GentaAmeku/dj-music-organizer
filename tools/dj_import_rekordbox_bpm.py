#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def path_from_rekordbox_location(value: str) -> Path | None:
    if not value:
        return None
    if value.startswith("file:"):
        parsed = urllib.parse.urlparse(value)
        decoded = urllib.parse.unquote(parsed.path)
        if parsed.netloc and parsed.netloc != "localhost":
            decoded = f"//{parsed.netloc}{decoded}"
    else:
        decoded = urllib.parse.unquote(value)

    decoded = decoded.replace("|", ":")
    windows_match = re.match(r"^/?([A-Za-z]):/(.*)$", decoded)
    if windows_match:
        drive = windows_match.group(1).lower()
        rest = windows_match.group(2)
        return Path(f"/mnt/{drive}/{rest}")
    return Path(decoded)


def parse_bpm(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        bpm = float(text)
    except ValueError:
        return None
    return bpm if bpm > 0 else None


def parse_xml(path: Path) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    rows: list[dict[str, Any]] = []
    for track in root.iter("TRACK"):
        bpm = parse_bpm(track.attrib.get("AverageBpm") or track.attrib.get("AverageBPM"))
        if bpm is None:
            continue
        location = track.attrib.get("Location") or ""
        file_path = path_from_rekordbox_location(location)
        rows.append(
            {
                "bpm": bpm,
                "path": str(file_path) if file_path else None,
                "filename": file_path.name if file_path else None,
                "title": track.attrib.get("Name"),
                "artist": track.attrib.get("Artist"),
                "source": "rekordbox",
            }
        )
    return rows


def parse_csv_file(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return rows
        field_by_normalized = {normalize_text(name): name for name in reader.fieldnames}
        bpm_field = next(
            (
                field_by_normalized[name]
                for name in ["bpm", "average bpm", "averagebpm", "tempo"]
                if name in field_by_normalized
            ),
            None,
        )
        location_field = next(
            (
                field_by_normalized[name]
                for name in ["location", "file path", "filepath", "path"]
                if name in field_by_normalized
            ),
            None,
        )
        title_field = next((field_by_normalized[name] for name in ["title", "name"] if name in field_by_normalized), None)
        artist_field = field_by_normalized.get("artist")
        if not bpm_field:
            raise SystemExit(f"Could not find a BPM column in CSV: {path}")

        for row in reader:
            bpm = parse_bpm(row.get(bpm_field))
            if bpm is None:
                continue
            raw_path = row.get(location_field, "") if location_field else ""
            file_path = path_from_rekordbox_location(raw_path) if raw_path else None
            rows.append(
                {
                    "bpm": bpm,
                    "path": str(file_path) if file_path else None,
                    "filename": file_path.name if file_path else None,
                    "title": row.get(title_field) if title_field else None,
                    "artist": row.get(artist_field) if artist_field else None,
                    "source": "rekordbox",
                }
            )
    return rows


def read_rekordbox_export(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".xml":
        return parse_xml(path)
    if path.suffix.lower() == ".csv":
        return parse_csv_file(path)
    raise SystemExit(f"Unsupported rekordbox export format: {path.suffix}")


def sha256_file(path: Path) -> str | None:
    import hashlib

    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def enrich_with_hash(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        raw_path = row.get("path")
        if not raw_path:
            continue
        digest = sha256_file(Path(raw_path))
        if digest:
            row["file_sha256"] = digest


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("file_sha256") or ""),
            normalize_text(str(row.get("path") or "")),
            normalize_text(str(row.get("filename") or "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append({k: v for k, v in row.items() if v not in {None, ""}})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Import rekordbox BPM values into bpm_overrides.json.")
    parser.add_argument("--rekordbox-export", required=True, help="rekordbox XML or CSV export")
    parser.add_argument("--library-root", required=True, help="DJ Music root folder")
    parser.add_argument("--output", default="bpm_overrides.json", help="Output JSON name/path")
    parser.add_argument("--apply", action="store_true", help="Write the override file")
    args = parser.parse_args()

    export_path = Path(args.rekordbox_export).expanduser().resolve()
    library_root = Path(args.library_root).expanduser().resolve()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = library_root / output_path

    rows = read_rekordbox_export(export_path)
    enrich_with_hash(rows)
    items = dedupe_rows(rows)
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(export_path),
        "items": items,
    }

    print(f"rekordbox rows: {len(rows)}")
    print(f"override items: {len(items)}")
    print(f"with file_sha256: {sum(1 for item in items if item.get('file_sha256'))}")
    print(f"output: {output_path}")

    if not args.apply:
        print("PREVIEW - no file was written")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:4000])
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
