---
name: dj-music-organizer-ops
description: Safely operate the DJ Music Organizer project for WSL/Windows USB workflows. Use when Codex needs to organize or analyze DJ audio files, run the project scripts, prepare or inspect a DJ Music library, manage reports, avoid PowerShell/WSL quoting mistakes, or update this repository.
---

# DJ Music Organizer Ops

## Core Rule

Treat the repository checkout as the tool repository and an external `DJ Music` directory as the music library.

Do not put real music libraries inside the repository. Do not touch `PIONEER`, `.Spotlight-V100`, `System Volume Information`, or `._*` files unless the user explicitly asks.

## First Checks

Before operating on music files:

1. Read repository `AGENTS.md`.
2. Read `DESIGN.md` and the relevant ADRs if changing behavior.
3. Check the library's `reports/INDEX.md` if reports exist.
4. Confirm the target path and whether the action is dry-run or apply.

For detailed commands and known traps, read `references/operation-checklists.md`.

## Safety Workflow

Always run a small dry-run before a broad action.

Use this order for analysis:

```bash
cd /path/to/dj-music-organizer
.venv/bin/python tools/dj_music_organizer.py --input "/path/to/DJ Music/00_Inbox" --limit 10
```

Only after reviewing the sample, run a full dry-run. Use `--apply` only after the dry-run result is acceptable. Use `--apply --yes` only when the user explicitly approves non-interactive mutation.

## WSL and PowerShell

Prefer `wsl -e bash -lc '...'` when using Bash features such as pipes, command substitution, globs, or quoted paths.

If a Windows drive mount such as `/mnt/e` is missing, mount the USB drive with root:

```powershell
wsl -u root sh -lc 'mkdir -p /mnt/e && mount -t drvfs E: /mnt/e'
```

Avoid passing `$()`, `|`, `*.mp3`, or Bash redirection through PowerShell without protective quoting.

## Reports

Write reports under:

```text
<DJ Music>/reports/YYYY-MM-DD/
```

Prefer JSON for machine-readable reports and Markdown for human review. After report changes, update:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\index_reports.ps1" -LibraryRoot "X:\DJ Music"
```

## Repository Hygiene

Keep `.venv`, `__pycache__`, real audio libraries, runtime logs, and generated library folders out of Git.

Before finalizing repository changes, run:

```bash
cd /path/to/dj-music-organizer
git status --short --ignored
```

Do not commit unless the user asks.
