# DJ Music Organizer Design

## Decision Records

Architecture decisions are recorded under `docs/adr/`.

## Goal

Build a safe WSL Ubuntu based workflow for preparing DJ music files for DDJ-FLX4 and rekordbox.

The first success condition is not automatic mutation. The first success condition is a dry-run that scans `00_Inbox`, analyzes audio, and shows the proposed BPM, Camelot key, destination path, archive path, and warnings before any file changes.

## Library Layout

The working library lives under a `DJ Music` root.

```text
DJ Music/
  dj_music_organizer.config.json
  organizer_log.jsonl
  00_Inbox/
  01_Analyzed/
    Under100/
    100-109/
    110-119/
    120-124/
    125-128/
    129-132/
    133-139/
    140-159/
    160-169/
    170-179/
    180-189/
    190-199/
    200-209/
    210-219/
    220plus/
    UnknownBPM/
  90_Archive/
  playlists/
    Collections/
      DJMAX/
        DJMAX_All.m3u8
        BPM/
          Under100.m3u8
          100-109.m3u8
          ...
    Global/
      BPM/
        Under100.m3u8
        100-109.m3u8
        ...
  reports/
```

Reports are indexed at:

```text
DJ Music/reports/INDEX.md
```

`00_Inbox/{Source}/...` may be used by the user to provide a source hint such as `DJMAX` or `RagnarokOnline`. The source hint is logged and later used as the collection id for playlist generation, but it is not placed in the analyzed file name.

## File Naming

Analyzed file names use only title/artist, rounded BPM, and Camelot key.

```text
{Title}_{BPM}BPM_{Camelot}.{ext}
{Artist} - {Title}_{BPM}BPM_{Camelot}.{ext}
```

Examples:

```text
Prontera_128BPM_6A.wav
M2U - glory day_128BPM_8A.mp3
TrackName_126BPM_UnknownKey.wav
```

If BPM cannot be estimated, use `UnknownBPM`. If major/minor cannot be determined for key conversion, use `UnknownKey`.

File names must be USB/Windows friendly:

- Replace Windows unsafe characters with `_`.
- Replace non-ASCII characters with `_`.
- Avoid trailing spaces and dots.
- Limit file names to about 180 characters including extension.
- Add a short hash only when shortening or non-ASCII replacement makes the name hard to identify.
- Use `__2`, `__3`, etc. for ordinary name collisions.

Existing `_128BPM_6A` style suffixes must not be duplicated. The organizer may reanalyze such files, but generated names should strip old BPM/Camelot suffixes before adding the current one.

## Analysis Rules

The initial target runtime is WSL Ubuntu.

The first implementation may depend on external Python/audio libraries. BPM and key are estimates, not authoritative truth.

Rules:

- Round BPM to the nearest integer for file names and folder placement.
- Store the selected floating BPM, rounded BPM, candidate BPMs, analysis policy, source, alternatives, and confidence in the log.
- Keep the default BPM policy as `consensus`.
- Use multiple internal analysis signals before selecting BPM.
- Allow an explicit `prefer-dj-range` policy for previewing DJ-friendly half/double choices.
- Keep external BPM overrides out of normal analysis unless explicitly requested.
- Show candidate tempos such as `87 / 174` in dry-run output.
- Do not force Camelot conversion when major/minor is unknown.
- Continue processing other files when one file fails.

### BPM analysis workflow

The primary goal is to make the program's own BPM analysis as accurate as practical.

The analyzer should combine full-audio onset strength, percussive onset strength, beat tracking, tempogram peaks, and adjacent onset intervals.

Half-time and double-time ambiguity should be resolved only when the internal evidence supports it.
For example, if the consensus result is below the preferred DJ tempo range but a doubled tempo has strong direct support from onset intervals or the tempogram, the analyzer may select the doubled tempo.

rekordbox import remains an optional comparison or manual-correction tool.
It must not affect normal organizer runs unless `--use-bpm-overrides` is explicitly passed.

## Apply Behavior

Default execution is dry-run.

`--apply` still displays the planned changes and asks `Proceed? [y/N]`.

Only `--apply --yes` skips confirmation.

On successful apply:

```text
00_Inbox/file.mp3
  -> copy analyzed output to 01_Analyzed/{BPMRange}/...
  -> move original file to 90_Archive/{original relative path}
```

Failed unreadable files remain in `00_Inbox`.

Unknown BPM and Unknown Key are not fatal if an output file can still be created.

No output path may be overwritten. This applies to both `01_Analyzed` and `90_Archive`.

## Logging

Append one JSON object per processed file to:

```text
DJ Music/organizer_log.jsonl
```

Minimum fields:

```text
timestamp
source_path
archive_path
dest_path
original_filename
new_filename
source_hint
file_sha256
estimated_bpm
rounded_bpm
bpm_candidates
bpm_source
bpm_policy
bpm_alternatives
bpm_confidence
estimated_key_raw
estimated_key
camelot
status
error
```

Use file-wide SHA-256 to detect repeated input files. A normalized audio fingerprint is out of scope for the first version.

If a file hash or source path already appears in a successful log entry, skip it by default. Reprocess only with `--force`.

## Unknown Key Reanalysis

Support a future mode:

```bash
python tools/dj_music_organizer.py --input "/path/to/DJ Music/01_Analyzed" --reanalyze-unknown-key
```

Initial rule:

- Updating `UnknownKey` to a known Camelot key is allowed after dry-run review.
- Changing one known Camelot key to another known Camelot key should warn and not auto-apply in the first version.

## Playlist Generation

Recommendation and playlist generation are separate from the organizer.

Use two future Codex skills:

- `dj-transition-suggest`: use `organizer_log.jsonl`, BPM, Camelot key, source hint, and paths to suggest transition candidates.
- `dj-source-playlists`: generate source-hint playlists from `organizer_log.jsonl`.

### BPM playlists

rekordbox may not preserve the physical `01_Analyzed/{BPMRange}` folder hierarchy as a browsable playlist tree. To make title and BPM browsing explicit, generate collection-scoped playlists from `source_hint`:

```text
DJ Music/playlists/Collections/DJMAX/DJMAX_All.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/Under100.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/100-109.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/110-119.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/120-124.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/125-128.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/129-132.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/133-139.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/140-159.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/160-169.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/170-179.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/180-189.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/190-199.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/200-209.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/210-219.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/220plus.m3u8
DJ Music/playlists/Collections/DJMAX/BPM/UnknownBPM.m3u8
```

The actual list of BPM playlists comes from `dj_music_organizer.config.json` `bpm_ranges`, so BPM values at `180` and above are analyzed, placed, and exported without changing the script.

BPM playlists can be generated from either the filesystem under `01_Analyzed` or from successful `organizer_log.jsonl` entries.

The collection mode uses successful log entries because source information is not present in the physical `01_Analyzed/{BPMRange}` folder path.

The candidate mode uses `rounded_bpm` and `bpm_candidates` from the log. This is useful when the analyzer may have detected a half-time BPM such as `99` while also recording `198` as a plausible DJ tempo. In candidate mode, the same track may appear in multiple BPM playlists. Candidate mode does not rename or move audio files.

Global BPM playlists may also be generated for all-library browsing:

```text
DJ Music/playlists/Global/BPM/125-128.m3u8
```

Entries are relative to each `.m3u8` file:

```text
../../../../01_Analyzed/125-128/M2U - glory day_128BPM_8A.mp3
```

### Source playlists

For now, provide a script that generates source-hint `.m3u8` files:

```text
DJ Music/playlists/{source_hint}.m3u8
```

The `.m3u8` entries should be relative paths suitable for copying the whole `DJ Music` folder to USB:

```text
../01_Analyzed/125-128/M2U - glory day_128BPM_8A.mp3
```

rekordbox supports importing `.m3u`, `.m3u8`, and `.pls` playlists.

## USB Export

USB is a final output target, not the primary working library.

Initial USB export behavior:

- Copy only `01_Analyzed` audio files and `playlists/*.m3u8`.
- Preserve the same `DJ Music` structure on USB.
- Do not copy `00_Inbox`, `90_Archive`, config, or logs.
- Do not delete files from USB.
- Copy missing files only.
- Existing files are skipped by default.
- `--update` may update existing files when explicitly requested.
- Keep dry-run as the default.

Final USB structure:

```text
USB/
  DJ Music/
    01_Analyzed/
    playlists/
      Collections/
      Global/
```
