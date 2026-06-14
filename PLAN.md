# DJ Music Organizer Plan

## Phase 0: Specification Baseline

Tasks:

- Capture the design decisions in `DESIGN.md`.
- Create a default config file.
- Create the project directory structure.
- Keep the design intentionally small: organizer, source playlists, USB export.

Exit criteria:

- A new contributor can read the documents and understand what the first implementation must and must not do.

## Phase 1: Safe Organizer MVP

Tasks:

- Keep `DJ Music/reports/INDEX.md` updated so future sessions can find generated reports.
- Implement recursive audio detection for `.wav`, `.aiff`, `.aif`, `.mp3`, `.m4a`, and `.flac`.
- Infer library root from `--input` when it points to `00_Inbox` or a child of it.
- Load `dj_music_organizer.config.json`.
- Calculate SHA-256 for duplicate detection.
- Extract basic title/artist metadata when available.
- Analyze BPM and key with best-effort library support.
- Generate sanitized ASCII file names.
- Assign BPM range folders.
- Show dry-run details and summary.
- Implement `--apply`, confirmation prompt, and `--yes`.
- Copy analyzed files to `01_Analyzed`.
- Move originals to `90_Archive`, preserving relative path.
- Append JSONL logs.

Exit criteria:

- Dry-run works with sample dummy files and does not mutate files.
- Apply copies and archives without overwriting.
- Failures are logged and do not stop the run.

## Phase 2: Better Analysis

Tasks:

- Improve BPM estimation quality.
- Improve key estimation quality on WSL Ubuntu.
- Add clear warnings for low-confidence or incomplete key results.
- Add `--reanalyze-unknown-key` dry-run behavior.
- Track analysis engine and version in logs.

Exit criteria:

- UnknownKey tracks can be reviewed and upgraded without changing known-key tracks automatically.

## Phase 3: Playlist Scripts

Tasks:

- Generate BPM playlists from `01_Analyzed/{BPMRange}`.
- Write BPM playlists to `playlists/BPM/{BPMRange}.m3u8`.
- Keep BPM playlist names aligned with `dj_music_organizer.config.json` `bpm_ranges`.
- Read `organizer_log.jsonl`.
- Group successful analyzed tracks by `source_hint`.
- Generate `playlists/{source_hint}.m3u8`.
- Use relative paths from each `.m3u8` file to `01_Analyzed`.
- Skip missing output files unless `--include-missing` is explicitly added later.

Exit criteria:

- Copying `DJ Music/01_Analyzed` and `DJ Music/playlists` to USB preserves BPM and source playlist path validity.

## Phase 4: USB Export Script

Tasks:

- Copy only audio files under `01_Analyzed` and `.m3u8` files under `playlists`.
- Preserve relative structure under `USB/DJ Music`.
- Default to dry-run.
- Copy missing files only.
- Skip existing files unless `--update` is provided.
- Never delete USB files.

Exit criteria:

- A dry-run clearly shows every planned copy/skip.
- Apply can populate a blank USB target without copying archive/log/config files.

## Phase 5: Codex Skills

Tasks:

- Create `dj-transition-suggest`.
- Create `dj-source-playlists` if the script workflow becomes repeated enough to benefit from Codex orchestration.
- Keep both skills based on `organizer_log.jsonl`; do not reanalyze audio in the skills.

Exit criteria:

- Codex can answer transition questions from the log.
- Codex can regenerate or inspect source playlists without touching organizer internals.
