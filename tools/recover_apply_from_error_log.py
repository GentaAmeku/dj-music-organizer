#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_organizer_module():
    module_path = Path(__file__).with_name("dj_music_organizer.py").resolve()
    spec = importlib.util.spec_from_file_location("dj_music_organizer", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load organizer module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_error_entries(log_path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    successful_keys: set[tuple[str | None, str | None]] = set()
    if not log_path.exists():
        return entries
    with log_path.open("r", encoding="utf-8") as log:
        for line in log:
            if not line.strip():
                continue
            entry = json.loads(line)
            key = (entry.get("file_sha256"), entry.get("source_path"))
            if entry.get("status") in {"applied", "copied_archived"}:
                successful_keys.add(key)
            if entry.get("status") == "error":
                entries.append(entry)
    return [
        entry
        for entry in entries
        if (entry.get("file_sha256"), entry.get("source_path")) not in successful_keys
    ]


def write_reports(root: Path, run_id: str, summary: dict[str, Any]) -> tuple[Path, Path]:
    report_dir = root / "reports" / datetime.now().strftime("%Y-%m-%d")
    report_dir.mkdir(parents=True, exist_ok=True)
    json_report = report_dir / f"organizer_apply_recovery_{run_id}.json"
    md_report = report_dir / f"organizer_apply_recovery_{run_id}.md"

    json_report.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        f"# Organizer Apply Recovery {run_id}",
        "",
        "## Summary",
        "",
        f"- input_error_entries: {summary['input_error_entries']}",
        f"- applied: {summary['applied']}",
        f"- reused_existing_dest: {summary['reused_existing_dest']}",
        f"- copied_new_dest: {summary['copied_new_dest']}",
        f"- archived: {summary['archived']}",
        f"- already_archived: {summary['already_archived']}",
        f"- errors: {summary['errors']}",
        "",
    ]
    if summary["error_items"]:
        lines.extend(["## Errors", ""])
        for item in summary["error_items"][:100]:
            lines.append(f"- `{item['source_path']}`: {item['error']}")
        if len(summary["error_items"]) > 100:
            lines.append(f"- ... and {len(summary['error_items']) - 100} more")
    md_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_report, md_report


def recover(root: Path, apply: bool) -> dict[str, Any]:
    organizer = load_organizer_module()
    log_path = root / "organizer_log.jsonl"
    entries = read_error_entries(log_path)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    reserved_dest: set[Path] = set()
    reserved_archive: set[Path] = set()

    summary: dict[str, Any] = {
        "run_id": run_id,
        "apply": apply,
        "input_error_entries": len(entries),
        "applied": 0,
        "reused_existing_dest": 0,
        "copied_new_dest": 0,
        "archived": 0,
        "already_archived": 0,
        "errors": 0,
        "error_items": [],
    }

    log_handle = log_path.open("a", encoding="utf-8") if apply else None
    try:
        for index, entry in enumerate(entries, 1):
            source = Path(entry["source_path"])
            file_hash = entry["file_sha256"]
            original_dest = Path(entry["dest_path"])
            original_archive = Path(entry["archive_path"])
            try:
                dest = organizer.unique_path(original_dest, reserved_dest, file_hash)
                reserved_dest.add(dest)
                archive = organizer.unique_path(original_archive, reserved_archive, file_hash)
                reserved_archive.add(archive)

                dest_existed = dest.exists()
                if apply:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    if not source.exists() and archive.exists() and organizer.path_matches_hash(archive, file_hash):
                        summary["already_archived"] += 1
                    else:
                        organizer.copy_without_metadata(source, dest, file_hash)
                        if dest_existed:
                            summary["reused_existing_dest"] += 1
                        else:
                            summary["copied_new_dest"] += 1
                        organizer.archive_source(source, archive, file_hash)
                        summary["archived"] += 1

                    applied_entry = dict(entry)
                    applied_entry.update(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "dest_path": str(dest),
                            "archive_path": str(archive),
                            "status": "applied",
                            "error": None,
                            "recovered_from_error": entry.get("error"),
                        }
                    )
                    assert log_handle is not None
                    log_handle.write(json.dumps(applied_entry, ensure_ascii=False) + "\n")
                summary["applied"] += 1
            except Exception as exc:
                summary["errors"] += 1
                summary["error_items"].append(
                    {
                        "source_path": str(source),
                        "dest_path": entry.get("dest_path"),
                        "archive_path": entry.get("archive_path"),
                        "error": str(exc),
                        "traceback": traceback.format_exc(limit=2),
                    }
                )

            if index % 50 == 0 or index == len(entries):
                print(
                    f"processed {index}/{len(entries)} "
                    f"applied={summary['applied']} errors={summary['errors']}",
                    flush=True,
                )
    finally:
        if log_handle is not None:
            log_handle.close()

    json_report, md_report = write_reports(root, run_id, summary)
    summary["json_report"] = str(json_report)
    summary["md_report"] = str(md_report)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover failed apply logs without re-analyzing audio.")
    parser.add_argument("--library-root", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    summary = recover(Path(args.library_root).expanduser().resolve(), args.apply)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
