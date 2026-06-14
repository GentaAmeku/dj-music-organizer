# ADR 0008: Copy Audio Content Without Filesystem Metadata

## Status

Accepted

## Context

The organizer may run from WSL against Windows-mounted or removable drives.

Some filesystems and mount combinations, especially removable exFAT drives accessed through WSL, may allow file content writes but reject metadata operations such as preserving permissions or timestamps.

Using metadata-preserving copy APIs can therefore produce a partial result:

- the analyzed output file exists,
- the original file remains in `00_Inbox`,
- the operation is logged as an error.

## Decision

The organizer copies audio files with content-only copy behavior and verifies the resulting file with SHA-256.

It does not rely on filesystem metadata preservation for DJ library output files.

Before `--apply`, the organizer runs a small preflight inside the target library root to confirm that content copy and archive move operations work.

## Consequences

This favors portability and predictable USB behavior over preserving source timestamps and permissions.

If a destination file already exists with the same SHA-256, the apply/recovery path can reuse it safely. If it exists with different content, the organizer fails rather than overwriting.
