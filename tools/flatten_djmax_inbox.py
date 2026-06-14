#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


AUDIO_EXTENSIONS = {".wav", ".aiff", ".aif", ".mp3", ".m4a", ".flac"}

HANGUL_L = [
    "g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s",
    "ss", "", "j", "jj", "ch", "k", "t", "p", "h",
]
HANGUL_V = [
    "a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa",
    "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i",
]
HANGUL_T = [
    "", "k", "kk", "ks", "n", "nj", "nh", "t", "l", "lk",
    "lm", "lb", "ls", "lt", "lp", "lh", "m", "p", "ps", "t",
    "t", "ng", "t", "t", "k", "t", "p", "h",
]


@dataclass
class MovePlan:
    source: Path
    target: Path
    original_name: str
    target_name: str
    changed_name: bool
    collision: bool


def romanize_hangul_char(char: str) -> str:
    code = ord(char)
    if 0xAC00 <= code <= 0xD7A3:
        syllable = code - 0xAC00
        lead = syllable // 588
        vowel = (syllable % 588) // 28
        tail = syllable % 28
        return HANGUL_L[lead] + HANGUL_V[vowel] + HANGUL_T[tail]
    return char


def ascii_filename(filename: str) -> str:
    path = Path(filename)
    stem = unicodedata.normalize("NFKC", path.stem).replace("\u00a0", " ")
    stem = "".join(romanize_hangul_char(char) for char in stem)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    stem = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in stem)
    stem = re.sub(r"\s+", " ", stem)
    stem = re.sub(r"_+", "_", stem).strip(" ._")
    return f"{stem or 'Track'}{path.suffix.lower()}"


def unique_target(base: Path, used_names: set[str]) -> tuple[Path, bool]:
    collision = base.name in used_names or base.exists()
    if not collision:
        used_names.add(base.name)
        return base, False

    for index in range(2, 10000):
        candidate = base.with_name(f"{base.stem}__{index}{base.suffix}")
        if candidate.name not in used_names and not candidate.exists():
            used_names.add(candidate.name)
            return candidate, True
    raise RuntimeError(f"Could not create unique target for {base}")


def build_plan(usb_root: Path, target_dir: Path) -> list[MovePlan]:
    album_roots = sorted(
        path for path in usb_root.iterdir()
        if path.is_dir() and path.name.startswith("DJMAX RESPECT V - ")
    )
    files = sorted(
        path
        for root in album_roots
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )

    used_names = {path.name for path in target_dir.iterdir() if path.is_file()} if target_dir.exists() else set()
    plan: list[MovePlan] = []
    for source in files:
        target_name = ascii_filename(source.name)
        target, collision = unique_target(target_dir / target_name, used_names)
        plan.append(
            MovePlan(
                source=source,
                target=target,
                original_name=source.name,
                target_name=target.name,
                changed_name=source.name != target.name,
                collision=collision,
            )
        )
    return plan


def plan_to_dict(item: MovePlan) -> dict[str, object]:
    return {
        "source": str(item.source),
        "target": str(item.target),
        "original_name": item.original_name,
        "target_name": item.target_name,
        "changed_name": item.changed_name,
        "collision": item.collision,
    }


def write_reports(plan: list[MovePlan], base_path: Path, usb_root: Path, target_dir: Path) -> tuple[Path, Path]:
    base_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = base_path.with_suffix(".json")
    md_path = base_path.with_suffix(".md")

    summary = {
        "generated_at": datetime.now().isoformat(),
        "usb_root": str(usb_root),
        "target": str(target_dir),
        "audio_files": len(plan),
        "renamed_or_ascii_changed": sum(1 for item in plan if item.changed_name),
        "collisions_resolved": sum(1 for item in plan if item.collision),
    }
    json_path.write_text(
        json.dumps({"summary": summary, "moves": [plan_to_dict(item) for item in plan]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# DJMAX Flatten Report",
        "",
        "## Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- USB root: `{summary['usb_root']}`",
        f"- Target: `{summary['target']}`",
        f"- Audio files: {summary['audio_files']}",
        f"- Renamed or ASCII changed: {summary['renamed_or_ascii_changed']}",
        f"- Collisions resolved: {summary['collisions_resolved']}",
        "",
    ]

    collisions = [item for item in plan if item.collision]
    if collisions:
        lines += ["## Collisions", "", "| Original name | Target name |", "| --- | --- |"]
        for item in collisions:
            lines.append(f"| `{item.original_name.replace('|', '\\|')}` | `{item.target_name.replace('|', '\\|')}` |")
        lines.append("")

    changed = [item for item in plan if item.changed_name][:100]
    if changed:
        lines += ["## Rename Preview", "", "| Original name | Target name |", "| --- | --- |"]
        for item in changed:
            lines.append(f"| `{item.original_name.replace('|', '\\|')}` | `{item.target_name.replace('|', '\\|')}` |")
        lines.append("")
        if summary["renamed_or_ascii_changed"] > len(changed):
            lines.append(f"Only the first {len(changed)} renamed items are shown here. See the JSON report for the full move list.")
            lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Flatten DJMAX OST audio files into DJ Music/00_Inbox/DJMAX.")
    parser.add_argument("--usb-root", required=True, help="USB or source root path")
    parser.add_argument("--target", required=True, help="Target source-hint inbox path, for example '/path/to/DJ Music/00_Inbox/DJMAX'")
    parser.add_argument("--apply", action="store_true", help="Move files")
    args = parser.parse_args()

    usb_root = Path(args.usb_root).resolve()
    target_dir = Path(args.target).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if not str(target_dir).startswith(str(usb_root)):
        raise SystemExit(f"Refusing target outside usb root: {target_dir}")

    plan = build_plan(usb_root, target_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_base = target_dir.parent.parent / "reports" / datetime.now().strftime("%Y-%m-%d") / f"djmax_flatten_report_{stamp}"
    json_report_path, md_report_path = write_reports(plan, report_base, usb_root, target_dir)

    print("APPLY MODE" if args.apply else "DRY RUN - no files will be moved")
    print(f"usb_root: {usb_root}")
    print(f"target: {target_dir}")
    print(f"json_report: {json_report_path}")
    print(f"md_report: {md_report_path}")
    print()

    print(f"audio_files: {len(plan)}")
    print(f"renamed_or_ascii_changed: {sum(1 for item in plan if item.changed_name)}")
    print(f"collisions_resolved: {sum(1 for item in plan if item.collision)}")
    print()

    collision_items = [item for item in plan if item.collision]
    if collision_items:
        print("Collisions:")
        for item in collision_items[:50]:
            print(f"  {item.original_name} -> {item.target_name}")
        print()

    changed_items = [item for item in plan if item.changed_name]
    if changed_items:
        print("Rename examples:")
        for item in changed_items[:50]:
            print(f"  {item.original_name} -> {item.target_name}")
        print()

    if args.apply:
        for item in plan:
            item.target.parent.mkdir(parents=True, exist_ok=True)
            if item.target.exists():
                raise FileExistsError(f"Target already exists: {item.target}")
            shutil.move(str(item.source), str(item.target))
        print(f"Moved: {len(plan)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
