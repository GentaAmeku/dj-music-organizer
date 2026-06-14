# Operation Checklists

## Path Model

- Repository: `/path/to/dj-music-organizer`
- Windows library example: `X:\DJ Music`
- WSL library example: `/mnt/x/DJ Music`
- Inbox source hint folder example: `<DJ Music>/00_Inbox/GameOST`
- Reports index: `<DJ Music>/reports/INDEX.md`

The repository contains tools and documentation. The Windows library contains real music files.

## Before Touching Music Files

1. Confirm the requested target and action.
2. Check whether the action mutates files.
3. If mutating, first run the equivalent dry-run.
4. If using WSL, confirm the target mount exists:

```bash
ls -la /mnt/e
```

5. If missing, mount from PowerShell:

```powershell
wsl -u root sh -lc 'mkdir -p /mnt/e && mount -t drvfs E: /mnt/e'
```

## Safe Analysis Sequence

Use a small sample first:

```bash
cd /path/to/dj-music-organizer
.venv/bin/python tools/dj_music_organizer.py --input "/path/to/DJ Music/00_Inbox" --limit 10
```

Then run full dry-run:

```bash
.venv/bin/python tools/dj_music_organizer.py --input "/path/to/DJ Music/00_Inbox"
```

Only after review, run apply:

```bash
.venv/bin/python tools/dj_music_organizer.py --input "/path/to/DJ Music/00_Inbox" --apply
```

Use `--apply --yes` only with explicit approval.

## Report Handling

Reports should be grouped by date:

```text
<DJ Music>/reports/YYYY-MM-DD/
```

Prefer `.json` and `.md`. Avoid introducing new `.csv` reports unless the user asks.

Update the index after report changes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\index_reports.ps1" -LibraryRoot "X:\DJ Music"
```

## PowerShell and WSL Quoting

Use `wsl -e bash -lc '...'` for Bash-heavy commands.

Good:

```powershell
wsl -e bash -lc 'cd /path/to/dj-music-organizer && first=$(find "/path/to/DJ Music/00_Inbox/GameOST" -maxdepth 1 -type f -iname "*.mp3" | sort | head -n 1) && .venv/bin/python tools/dj_music_organizer.py --input "$first"'
```

Risky:

```powershell
wsl sh -lc "first=$(find ... | head -n 1)"
```

PowerShell may consume `$()`, pipes, globs, or redirection before WSL sees them.

## DJMAX Flattening Lessons

When flattening album folders into a source-hint inbox such as `00_Inbox\GameOST`:

- Exclude AppleDouble files matching `._*`.
- Preserve no original album folder structure in Inbox unless requested.
- Convert non-ASCII names to ASCII before analysis if the USB/DJ app workflow requires it.
- Resolve collisions with `__2`, `__3`, etc.
- Write JSON and Markdown reports under `reports/YYYY-MM-DD/`.

## Metadata Lessons

Some tracks have useful ASCII filenames but non-ASCII metadata titles.

For this project, when ASCII filenames already exist and metadata contains non-ASCII title values, prefer the file name for generated DJ filenames. This avoids names collapsing to generic placeholders after ASCII sanitization.

## Git Hygiene

Expected ignored entries:

```text
.venv/
__pycache__/
```

Do not add real audio files, runtime reports, or runtime logs to the repository unless the user explicitly asks for a fixture or example.
