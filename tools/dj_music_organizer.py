#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections.abc import Iterable


GENERIC_VALUES = {
    "",
    "unknown",
    "unknown artist",
    "untitled",
    "track",
    "audio",
    "none",
    "null",
}

CAMLOT_BY_KEY = {
    ("C", "major"): "8B",
    ("G", "major"): "9B",
    ("D", "major"): "10B",
    ("A", "major"): "11B",
    ("E", "major"): "12B",
    ("B", "major"): "1B",
    ("F#", "major"): "2B",
    ("C#", "major"): "3B",
    ("G#", "major"): "4B",
    ("D#", "major"): "5B",
    ("A#", "major"): "6B",
    ("F", "major"): "7B",
    ("A", "minor"): "8A",
    ("E", "minor"): "9A",
    ("B", "minor"): "10A",
    ("F#", "minor"): "11A",
    ("C#", "minor"): "12A",
    ("G#", "minor"): "1A",
    ("D#", "minor"): "2A",
    ("A#", "minor"): "3A",
    ("F", "minor"): "4A",
    ("C", "minor"): "5A",
    ("G", "minor"): "6A",
    ("D", "minor"): "7A",
}

FLAT_TO_SHARP = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
}


@dataclass
class PlanItem:
    source_path: Path
    dest_path: Path
    archive_path: Path
    source_hint: str | None
    original_filename: str
    new_filename: str
    file_sha256: str
    estimated_bpm: float | None
    rounded_bpm: int | None
    bpm_candidates: list[int]
    bpm_source: str
    bpm_policy: str
    bpm_alternatives: list[dict[str, Any]]
    bpm_confidence: str | None
    estimated_key_raw: str | None
    estimated_key: str | None
    camelot: str
    status: str
    error: str | None = None
    skipped_reason: str | None = None


@dataclass
class BpmEstimate:
    bpm: float | None
    rounded_bpm: int | None
    candidates: list[int]
    source: str
    policy: str
    alternatives: list[dict[str, Any]]
    confidence: str | None
    warning: str | None = None


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_library_root(input_path: Path, config_name: str, library_root: str | None) -> Path:
    if library_root:
        return Path(library_root).expanduser().resolve()

    resolved = input_path.expanduser().resolve()
    for candidate in [resolved, *resolved.parents]:
        if candidate.name == "00_Inbox":
            return candidate.parent
        if (candidate / config_name).exists():
            return candidate
    raise SystemExit(
        "Could not infer library root. Point --input at 00_Inbox or pass --library-root."
    )


def load_config(root: Path, config_name: str) -> dict[str, Any]:
    path = root / config_name
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    return load_json(path)


def load_bpm_overrides(root: Path, config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    override_name = config.get("bpm_overrides_file")
    if not override_name:
        return {"hash": [], "filename": [], "path": []}

    path = root / str(override_name)
    if not path.exists():
        return {"hash": [], "filename": [], "path": []}

    data = load_json(path)
    if isinstance(data, dict):
        raw_items = data.get("items", [])
    elif isinstance(data, list):
        raw_items = data
    else:
        raw_items = []
    indexes: dict[str, list[dict[str, Any]]] = {"hash": [], "filename": [], "path": []}
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        try:
            bpm = float(raw_item["bpm"])
        except (KeyError, TypeError, ValueError):
            continue
        item = dict(raw_item)
        item["bpm"] = bpm
        if item.get("file_sha256"):
            indexes["hash"].append(item)
        if item.get("filename"):
            indexes["filename"].append(item)
        if item.get("path"):
            indexes["path"].append(item)
    return indexes


def normalize_lookup_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def lookup_bpm_override(
    overrides: dict[str, list[dict[str, Any]]],
    source_path: Path,
    file_hash: str,
) -> dict[str, Any] | None:
    normalized_name = normalize_lookup_text(source_path.name)
    normalized_path = normalize_lookup_text(str(source_path))

    for item in overrides["hash"]:
        if normalize_lookup_text(str(item.get("file_sha256"))) == file_hash.casefold():
            return item
    for item in overrides["path"]:
        if normalize_lookup_text(str(item.get("path"))) == normalized_path:
            return item
    for item in overrides["filename"]:
        if normalize_lookup_text(str(item.get("filename"))) == normalized_name:
            return item
    return None


def iter_audio_files(input_path: Path, extensions: set[str]) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in extensions else []
    return sorted(
        p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() in extensions
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_successful_log_keys(log_path: Path) -> tuple[set[str], set[str]]:
    hashes: set[str] = set()
    paths: set[str] = set()
    if not log_path.exists():
        return hashes, paths
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("status") in {"applied", "copied_archived", "bpm_corrected"}:
                if entry.get("file_sha256"):
                    hashes.add(entry["file_sha256"])
                if entry.get("source_path"):
                    paths.add(entry["source_path"])
    return hashes, paths


def clean_generic(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(str(value).strip().split())
    if value.casefold() in GENERIC_VALUES:
        return None
    return value


def first_tag(tags: dict[str, Any], names: list[str]) -> str | None:
    for name in names:
        value = tags.get(name)
        if isinstance(value, Iterable) and not isinstance(value, str):
            values = list(value)
            if values:
                return clean_generic(str(values[0]))
        if value:
            return clean_generic(str(value))
    return None


def read_metadata(path: Path) -> tuple[str | None, str | None]:
    try:
        from mutagen import File
    except Exception:
        return None, None

    try:
        audio = File(path, easy=True)
    except Exception:
        return None, None
    if not audio:
        return None, None

    artist = first_tag(audio, ["artist", "albumartist", "composer"])
    title = first_tag(audio, ["title"])
    return artist, title


TAG_SUFFIX_RE = re.compile(
    r"(?P<base>.+?)_(?:UnknownBPM|\d{1,3}BPM)_(?:UnknownKey|(?:[1-9]|1[0-2])[AB])$",
    re.IGNORECASE,
)


def strip_existing_tags(stem: str) -> str:
    match = TAG_SUFFIX_RE.match(stem)
    return match.group("base") if match else stem


def parse_name(path: Path, artist: str | None, title: str | None) -> tuple[str | None, str]:
    stem = strip_existing_tags(path.stem)
    stem = re.sub(r"^\d+\s*[-.]?\s*", "", stem).strip()
    file_artist = None
    file_title = stem
    parsed_file_name = False
    if " - " in stem:
        left, right = stem.split(" - ", 1)
        file_artist = clean_generic(left)
        file_title = clean_generic(right) or stem
        parsed_file_name = True
    elif " _ " in stem:
        left, right = stem.split(" _ ", 1)
        file_artist = clean_generic(left)
        file_title = clean_generic(right) or stem
        parsed_file_name = True

    if title:
        metadata_has_non_ascii = any(ord(char) > 127 for char in f"{artist or ''}{title}")
        file_name_is_ascii = all(ord(char) <= 127 for char in f"{file_artist or ''}{file_title}")
        if parsed_file_name and metadata_has_non_ascii and file_name_is_ascii:
            return file_artist, file_title

        title_is_non_ascii = any(ord(char) > 127 for char in title)
        file_title_is_ascii = all(ord(char) <= 127 for char in file_title)
        if title_is_non_ascii and file_title_is_ascii:
            return artist or file_artist, file_title
        return artist, title
    return file_artist, file_title


def sanitize_component(value: str, ascii_only: bool) -> str:
    value = value.strip()
    unsafe = '<>:"/\\|?*'
    value = "".join("_" if c in unsafe or ord(c) < 32 else c for c in value)
    if ascii_only:
        value = "".join(c if 32 <= ord(c) <= 126 else "_" for c in value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip(" ._")
    return value or "Track"


def shorten_filename(stem: str, suffix: str, ext: str, max_length: int, digest: str) -> str:
    filename = f"{stem}{suffix}{ext}"
    if len(filename) <= max_length:
        return filename
    hash_part = digest[:8]
    reserve = len(suffix) + len(ext) + len(hash_part) + 1
    allowed = max(12, max_length - reserve)
    return f"{stem[:allowed].rstrip(' ._')}_{hash_part}{suffix}{ext}"


def unique_path(
    path: Path,
    reserved: set[Path] | None = None,
    expected_hash: str | None = None,
) -> Path:
    reserved = reserved or set()
    if not path.exists() and path not in reserved:
        return path
    if (
        expected_hash
        and path.exists()
        and path not in reserved
        and path_matches_hash(path, expected_hash)
    ):
        return path
    for index in range(2, 10000):
        candidate = path.with_name(f"{path.stem}__{index}{path.suffix}")
        if not candidate.exists() and candidate not in reserved:
            return candidate
        if (
            expected_hash
            and candidate.exists()
            and candidate not in reserved
            and path_matches_hash(candidate, expected_hash)
        ):
            return candidate
    raise RuntimeError(f"Could not find available file name for {path}")


def bpm_folder(rounded_bpm: int | None, ranges: list[dict[str, Any]]) -> str:
    if rounded_bpm is None:
        return "UnknownBPM"
    for item in ranges:
        lo = item.get("min")
        hi = item.get("max")
        if (lo is None or rounded_bpm >= lo) and (hi is None or rounded_bpm <= hi):
            return item["name"]
    return "UnknownBPM"


def bpm_candidates(rounded_bpm: int | None) -> list[int]:
    if rounded_bpm is None:
        return []
    candidates = {rounded_bpm}
    if rounded_bpm < 120:
        candidates.add(rounded_bpm * 2)
    if rounded_bpm >= 160:
        candidates.add(round(rounded_bpm / 2))
    return sorted(candidates)


def tempo_in_bounds(value: int, config: dict[str, Any]) -> bool:
    bpm_config = config.get("bpm_analysis", {})
    lo = int(bpm_config.get("min_tempo", 60))
    hi = int(bpm_config.get("max_tempo", 260))
    return lo <= value <= hi


def normalized_bpm_candidates(
    rounded_values: Iterable[int | None],
    config: dict[str, Any],
) -> list[int]:
    candidates: set[int] = set()
    for rounded in rounded_values:
        if rounded is None:
            continue
        for value in bpm_candidates(rounded):
            if tempo_in_bounds(value, config):
                candidates.add(value)
    return sorted(candidates)


def estimate_bpm_from_signal(y: Any, sr: int, config: dict[str, Any]) -> BpmEstimate:
    import librosa
    import numpy as np

    bpm_config = config.get("bpm_analysis", {})
    policy = str(bpm_config.get("policy", "raw"))
    preferred_min = int(bpm_config.get("preferred_min", 120))
    preferred_max = int(bpm_config.get("preferred_max", 220))

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    estimates: list[dict[str, Any]] = []

    def add_estimate(method: str, value: float | None) -> None:
        if value is None or not np.isfinite(value) or value <= 0:
            return
        rounded = int(round(float(value)))
        if tempo_in_bounds(rounded, config):
            estimates.append(
                {
                    "method": method,
                    "bpm": float(value),
                    "rounded_bpm": rounded,
                }
            )

    try:
        primary = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=np.median)
        add_estimate("onset_median", float(primary[0]) if len(primary) else None)
    except Exception:
        pass

    try:
        mean_tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=np.mean)
        add_estimate("onset_mean", float(mean_tempo[0]) if len(mean_tempo) else None)
    except Exception:
        pass

    try:
        frame_tempos = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=None)
        if len(frame_tempos):
            add_estimate("frame_median", float(np.median(frame_tempos)))
            add_estimate("frame_mode", float(np.bincount(np.rint(frame_tempos).astype(int)).argmax()))
    except Exception:
        pass

    if not estimates:
        return BpmEstimate(None, None, [], "analysis", policy, [], None, "BPM could not be estimated")

    primary = estimates[0]
    candidate_values = normalized_bpm_candidates(
        (item["rounded_bpm"] for item in estimates),
        config,
    )

    selected = int(primary["rounded_bpm"])
    if policy == "prefer-dj-range":
        scores: dict[int, float] = {}
        for item in estimates:
            rounded = int(item["rounded_bpm"])
            scores[rounded] = scores.get(rounded, 0.0) + 1.0
            for candidate in bpm_candidates(rounded):
                if candidate != rounded and tempo_in_bounds(candidate, config):
                    scores[candidate] = scores.get(candidate, 0.0) + 0.85
        for candidate in list(scores):
            if preferred_min <= candidate <= preferred_max:
                scores[candidate] += 0.4
        selected = sorted(
            scores,
            key=lambda value: (
                -scores[value],
                abs(value - int(primary["rounded_bpm"])),
                value,
            ),
        )[0]

    if selected not in candidate_values:
        candidate_values.append(selected)
        candidate_values.sort()

    support = sum(1 for item in estimates if int(item["rounded_bpm"]) == selected)
    scaled_support = sum(
        1
        for item in estimates
        if selected in bpm_candidates(int(item["rounded_bpm"]))
        and int(item["rounded_bpm"]) != selected
    )
    if support >= 2:
        confidence = "high"
    elif support == 1 or scaled_support >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    selected_float = float(selected)
    return BpmEstimate(
        bpm=selected_float,
        rounded_bpm=selected,
        candidates=candidate_values,
        source="analysis",
        policy=policy,
        alternatives=estimates,
        confidence=confidence,
    )


def bpm_estimate_from_override(item: dict[str, Any], config: dict[str, Any]) -> BpmEstimate:
    rounded = int(round(float(item["bpm"])))
    candidates = normalized_bpm_candidates([rounded], config)
    if rounded not in candidates:
        candidates.append(rounded)
        candidates.sort()
    return BpmEstimate(
        bpm=float(item["bpm"]),
        rounded_bpm=rounded,
        candidates=candidates,
        source=str(item.get("source") or "override"),
        policy="override",
        alternatives=[],
        confidence="manual",
    )


def estimate_audio(path: Path, config: dict[str, Any]) -> tuple[BpmEstimate, str | None, str | None, str | None, str | None]:
    try:
        import librosa
        import numpy as np
    except Exception as exc:
        empty = BpmEstimate(None, None, [], "analysis", "raw", [], None)
        return empty, None, None, None, f"analysis dependencies unavailable: {exc}"

    try:
        y, sr = librosa.load(str(path), sr=None, mono=True)
        if len(y) == 0:
            empty = BpmEstimate(None, None, [], "analysis", "raw", [], None)
            return empty, None, None, None, "empty audio"

        bpm_estimate = estimate_bpm_from_signal(y, sr, config)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)
        key_raw, key_name, camelot = estimate_key_from_chroma(chroma_mean)
        return bpm_estimate, key_raw, key_name, camelot, bpm_estimate.warning
    except Exception as exc:
        empty = BpmEstimate(None, None, [], "analysis", "raw", [], None)
        return empty, None, None, None, str(exc)


def estimate_key_from_chroma(chroma_mean: Any) -> tuple[str | None, str | None, str]:
    import numpy as np

    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    chroma = np.asarray(chroma_mean, dtype=float)
    if not np.isfinite(chroma).all() or float(np.sum(chroma)) <= 0:
        return None, None, "UnknownKey"
    chroma = (chroma - np.mean(chroma)) / (np.std(chroma) or 1.0)

    best_score = -10**9
    best_key: tuple[str, str] | None = None
    for i, name in enumerate(names):
        for mode, profile in [("major", major_profile), ("minor", minor_profile)]:
            rolled = np.roll(profile, i)
            rolled = (rolled - np.mean(rolled)) / (np.std(rolled) or 1.0)
            score = float(np.dot(chroma, rolled))
            if score > best_score:
                best_score = score
                best_key = (name, mode)

    if not best_key:
        return None, None, "UnknownKey"
    key, mode = best_key
    camelot = CAMLOT_BY_KEY.get((key, mode), "UnknownKey")
    label = f"{key} {mode}"
    return label, label, camelot


def make_plan_item(
    source_path: Path,
    root: Path,
    input_path: Path,
    config: dict[str, Any],
    bpm_overrides: dict[str, list[dict[str, Any]]],
    seen_hashes: set[str],
    seen_paths: set[str],
    force: bool,
    reserved_dest_paths: set[Path],
    reserved_archive_paths: set[Path],
) -> PlanItem:
    inbox = root / config["inbox_dir"]
    analyzed = root / config["analyzed_dir"]
    archive = root / config["archive_dir"]
    file_hash = sha256_file(source_path)

    try:
        relative_to_inbox = source_path.resolve().relative_to(inbox.resolve())
    except ValueError:
        relative_to_inbox = source_path.name

    if isinstance(relative_to_inbox, Path) and len(relative_to_inbox.parts) > 1:
        source_hint = relative_to_inbox.parts[0]
    else:
        source_hint = None

    artist, title = read_metadata(source_path)
    artist, title = parse_name(source_path, artist, title)

    if not force and (file_hash in seen_hashes or str(source_path) in seen_paths):
        dummy_archive = archive / relative_to_inbox if isinstance(relative_to_inbox, Path) else archive / source_path.name
        return PlanItem(
            source_path=source_path,
            dest_path=Path(),
            archive_path=dummy_archive,
            source_hint=source_hint,
            original_filename=source_path.name,
            new_filename="",
            file_sha256=file_hash,
            estimated_bpm=None,
            rounded_bpm=None,
            bpm_candidates=[],
            bpm_source="none",
            bpm_policy=str(config.get("bpm_analysis", {}).get("policy", "raw")),
            bpm_alternatives=[],
            bpm_confidence=None,
            estimated_key_raw=None,
            estimated_key=None,
            camelot="UnknownKey",
            status="skipped",
            skipped_reason="already processed",
        )

    bpm_estimate, key_raw, key_name, camelot_from_analysis, error = estimate_audio(source_path, config)
    override_item = lookup_bpm_override(bpm_overrides, source_path, file_hash)
    if override_item:
        bpm_estimate = bpm_estimate_from_override(override_item, config)
    estimated_bpm = bpm_estimate.bpm
    rounded = bpm_estimate.rounded_bpm
    camelot = camelot_from_analysis or "UnknownKey"
    if key_name is None:
        camelot = "UnknownKey"

    bpm_label = f"{rounded}BPM" if rounded is not None else "UnknownBPM"
    safe_title = sanitize_component(title, config.get("ascii_filenames", True))
    safe_artist = sanitize_component(artist, config.get("ascii_filenames", True)) if artist else None
    base_stem = f"{safe_artist} - {safe_title}" if safe_artist else safe_title
    suffix = f"_{bpm_label}_{camelot}"
    filename = shorten_filename(
        base_stem,
        suffix,
        source_path.suffix.lower(),
        int(config.get("max_filename_length", 180)),
        file_hash,
    )

    folder = bpm_folder(rounded, config["bpm_ranges"])
    dest_path = unique_path(analyzed / folder / filename, reserved_dest_paths, file_hash)
    reserved_dest_paths.add(dest_path)
    archive_path = archive / relative_to_inbox if isinstance(relative_to_inbox, Path) else archive / source_path.name
    archive_path = unique_path(archive_path, reserved_archive_paths)
    reserved_archive_paths.add(archive_path)

    return PlanItem(
        source_path=source_path,
        dest_path=dest_path,
        archive_path=archive_path,
        source_hint=source_hint,
        original_filename=source_path.name,
        new_filename=filename,
        file_sha256=file_hash,
        estimated_bpm=estimated_bpm,
        rounded_bpm=rounded,
        bpm_candidates=bpm_estimate.candidates,
        bpm_source=bpm_estimate.source,
        bpm_policy=bpm_estimate.policy,
        bpm_alternatives=bpm_estimate.alternatives,
        bpm_confidence=bpm_estimate.confidence,
        estimated_key_raw=key_raw,
        estimated_key=key_name,
        camelot=camelot,
        status="ready",
        error=error if estimated_bpm is None and key_name is None else None,
    )


def item_to_log(item: PlanItem, status: str, error: str | None = None) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_path": str(item.source_path),
        "archive_path": str(item.archive_path) if item.archive_path else None,
        "dest_path": str(item.dest_path) if item.dest_path else None,
        "original_filename": item.original_filename,
        "new_filename": item.new_filename,
        "source_hint": item.source_hint,
        "file_sha256": item.file_sha256,
        "estimated_bpm": item.estimated_bpm,
        "rounded_bpm": item.rounded_bpm,
        "bpm_candidates": item.bpm_candidates,
        "bpm_source": item.bpm_source,
        "bpm_policy": item.bpm_policy,
        "bpm_alternatives": item.bpm_alternatives,
        "bpm_confidence": item.bpm_confidence,
        "estimated_key_raw": item.estimated_key_raw,
        "estimated_key": item.estimated_key,
        "camelot": item.camelot,
        "status": status,
        "error": error or item.error,
    }


def print_item(item: PlanItem) -> None:
    if item.status == "skipped":
        print(f"[SKIP] {item.source_path}")
        print(f"  reason: {item.skipped_reason}")
        return
    label = "OK"
    if item.rounded_bpm is None or item.camelot == "UnknownKey":
        label = "WARN"
    if item.error:
        label = "WARN"
    print(f"[{label}] {item.source_path}")
    print(f"  -> {item.dest_path}")
    print(f"  archive -> {item.archive_path}")
    print(f"  bpm: {item.estimated_bpm if item.estimated_bpm is not None else 'Unknown'} -> {item.rounded_bpm if item.rounded_bpm is not None else 'Unknown'}")
    print(f"  bpm candidates: {', '.join(map(str, item.bpm_candidates)) if item.bpm_candidates else 'Unknown'}")
    print(f"  bpm source: {item.bpm_source} / {item.bpm_policy} / confidence={item.bpm_confidence or 'Unknown'}")
    print(f"  key: {item.estimated_key_raw or 'Unknown'} -> {item.camelot}")
    print(f"  source_hint: {item.source_hint or 'None'}")
    if item.error:
        print(f"  warning: {item.error}")


def print_summary(items: list[PlanItem]) -> None:
    ready = [i for i in items if i.status == "ready"]
    print("\nSummary:")
    print(f"  total: {len(items)}")
    print(f"  ready: {len(ready)}")
    print(f"  skipped: {sum(1 for i in items if i.status == 'skipped')}")
    print(f"  unknown_bpm: {sum(1 for i in ready if i.rounded_bpm is None)}")
    print(f"  unknown_key: {sum(1 for i in ready if i.camelot == 'UnknownKey')}")
    print(f"  warnings: {sum(1 for i in ready if i.error)}")


def path_matches_hash(path: Path, expected_hash: str) -> bool:
    return path.exists() and sha256_file(path) == expected_hash


def copy_without_metadata(source_path: Path, dest_path: Path, expected_hash: str) -> None:
    if dest_path.exists():
        if path_matches_hash(dest_path, expected_hash):
            return
        raise FileExistsError(f"destination path already exists with different content: {dest_path}")

    shutil.copyfile(source_path, dest_path)
    if not path_matches_hash(dest_path, expected_hash):
        try:
            dest_path.unlink()
        except OSError:
            pass
        raise RuntimeError(f"copied file hash mismatch: {dest_path}")


def archive_source(source_path: Path, archive_path: Path, expected_hash: str) -> None:
    if archive_path.exists():
        if not path_matches_hash(archive_path, expected_hash):
            raise FileExistsError(f"archive path already exists with different content: {archive_path}")
        if source_path.exists():
            source_path.unlink()
        return

    source_path.replace(archive_path)


def preflight_apply_environment(root: Path) -> None:
    temp_root = root / ".organizer_preflight"
    source_dir = temp_root / "source"
    dest_dir = temp_root / "dest"
    archive_dir = temp_root / "archive"
    source_path = source_dir / "preflight.txt"
    dest_path = dest_dir / "preflight.txt"
    archive_path = archive_dir / "preflight.txt"
    payload = b"dj-music-organizer preflight\n"
    expected_hash = hashlib.sha256(payload).hexdigest()

    try:
        if temp_root.exists():
            shutil.rmtree(temp_root)
        source_dir.mkdir(parents=True)
        dest_dir.mkdir(parents=True)
        archive_dir.mkdir(parents=True)
        source_path.write_bytes(payload)
        copy_without_metadata(source_path, dest_path, expected_hash)
        archive_source(source_path, archive_path, expected_hash)
        if source_path.exists() or not dest_path.exists() or not archive_path.exists():
            raise RuntimeError("preflight copy/archive result was incomplete")
    except Exception as exc:
        raise RuntimeError(
            f"Apply preflight failed under {root}. Check drive permissions/mount state: {exc}"
        ) from exc
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)


def apply_items(items: list[PlanItem], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        for item in items:
            if item.status != "ready":
                continue
            try:
                item.dest_path.parent.mkdir(parents=True, exist_ok=True)
                item.archive_path.parent.mkdir(parents=True, exist_ok=True)
                copy_without_metadata(item.source_path, item.dest_path, item.file_sha256)
                archive_source(item.source_path, item.archive_path, item.file_sha256)
                entry = item_to_log(item, "applied")
                print(f"[APPLIED] {item.source_path} -> {item.dest_path}")
            except Exception as exc:
                entry = item_to_log(item, "error", str(exc))
                print(f"[ERROR] {item.source_path}: {exc}", file=sys.stderr)
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze and organize DJ music files.")
    parser.add_argument("--input", required=True, help="Input file/folder, normally DJ Music/00_Inbox")
    parser.add_argument("--library-root", help="DJ Music root folder")
    parser.add_argument("--config", default="dj_music_organizer.config.json")
    parser.add_argument("--apply", action="store_true", help="Actually copy analyzed files and archive originals")
    parser.add_argument("--yes", action="store_true", help="Skip apply confirmation")
    parser.add_argument("--force", action="store_true", help="Reprocess files seen in previous successful logs")
    parser.add_argument("--limit", type=int, help="Analyze at most this many files")
    parser.add_argument(
        "--bpm-policy",
        choices=["raw", "prefer-dj-range"],
        help="Override bpm_analysis.policy for this run",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    root = find_library_root(input_path, args.config, args.library_root)
    config = load_config(root, args.config)
    if args.bpm_policy:
        config.setdefault("bpm_analysis", {})["policy"] = args.bpm_policy
    bpm_overrides = load_bpm_overrides(root, config)
    log_path = root / config["log_file"]
    extensions = {ext.lower() for ext in config["audio_extensions"]}
    files = iter_audio_files(input_path, extensions)
    if args.limit is not None:
        files = files[: max(0, args.limit)]
    seen_hashes, seen_paths = read_successful_log_keys(log_path)

    print("APPLY MODE" if args.apply else "DRY RUN - no files will be changed")
    print(f"library_root: {root}")
    print(f"input: {input_path}\n")

    reserved_dest_paths: set[Path] = set()
    reserved_archive_paths: set[Path] = set()
    items = [
        make_plan_item(
            path,
            root,
            input_path,
            config,
            bpm_overrides,
            seen_hashes,
            seen_paths,
            args.force,
            reserved_dest_paths,
            reserved_archive_paths,
        )
        for path in files
    ]
    for item in items:
        print_item(item)
        print()
    print_summary(items)

    if not args.apply:
        return 0

    if not args.yes:
        answer = input("\nProceed? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Aborted.")
            return 1

    preflight_apply_environment(root)
    apply_items(items, log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
