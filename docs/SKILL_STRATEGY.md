# Skill Strategy

## Recommendation

Create a small operational skill first, then add selection-oriented skills later.

The first skill should prevent repeated mistakes around WSL, PowerShell quoting, USB paths, reports, dry-run/apply discipline, and DJ library layout.

## Proposed Skills

### `dj-music-organizer-ops`

Use for operating this DJ Music Organizer project safely.

Responsibilities:

- Check the library's `reports/INDEX.md` before making changes.
- Confirm whether the target Windows/USB drive is mounted before WSL-based analysis.
- Use `wsl -e bash -lc '...'` for Bash pipelines and command substitution.
- Run `--limit 10` dry-run before all-file analysis.
- Audit `rounded_bpm` and `bpm_candidates` before deciding that a BPM range has no tracks.
- Generate rekordbox BPM playlists with `--include-candidates` when half/double tempo candidates should be visible.
- Keep reports under `reports/YYYY-MM-DD/` and update `reports/INDEX.md`.
- Avoid touching `PIONEER`, system folders, and AppleDouble `._*` files.
- Keep project changes in Git, excluding `.venv`, `__pycache__`, and runtime music-library outputs.

Suggested location:

```text
/path/to/dj-music-organizer/.codex/skills/dj-music-organizer-ops
```

This keeps the skill versioned with the project and makes the Codex-specific purpose explicit. If a Codex surface does not auto-discover repository-local skills, install or copy this directory into the user skill directory as a fallback.

### `dj-transition-suggest`

Use later for suggesting tracks from `organizer_log.jsonl`.

Responsibilities:

- Read BPM, Camelot key, source_hint, and paths from logs.
- Suggest candidates by BPM proximity and Camelot compatibility.
- Treat UnknownKey and estimated metadata cautiously.

### `dj-source-playlists`

Use later for source-hint playlist operations.

Responsibilities:

- Generate or inspect source_hint `.m3u8` playlists.
- Prefer relative paths for USB structure.
- Use JSONL logs as source data, not filename scraping.

### `dj-bpm-playlists`

Use later if BPM playlist operations grow beyond the operational checklist.

Responsibilities:

- Generate or inspect `playlists/BPM/{BPMRange}.m3u8`.
- Compare physical BPM folders with `rounded_bpm` and `bpm_candidates`.
- Explain duplicate playlist membership caused by half/double tempo candidates.
- Avoid renaming or moving files based only on candidates.

## Why Not One Big Skill

Combining operations, recommendations, and playlist generation would make the skill too broad.

The operational skill should be narrow and safety-oriented. The recommendation and playlist skills can be added after the organizer output stabilizes.
