# ADR 0001: Architecture Decision Records を残す

## Status

Accepted

## Context

DJ Music Organizer は、音源ファイルの解析、リネーム、アーカイブ、プレイリスト生成、USB書き出しまで複数の判断を含む。

特に dry-run、安全な apply、WSL Ubuntu 前提、USB向け相対パスなどは、後から見返したときに「なぜそうしたか」が分からなくなりやすい。

## Decision

重要な設計判断は `docs/adr/` に ADR として残す。

ADR は以下を含める。

- Status
- Context
- Decision
- Consequences

## Consequences

設計変更時に判断の履歴を追いやすくなる。

一方で、仕様を変更した場合は該当ADRを更新するか、新しいADRを追加する手間が増える。

