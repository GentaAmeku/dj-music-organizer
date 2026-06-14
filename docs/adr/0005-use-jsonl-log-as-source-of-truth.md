# ADR 0005: JSONLログを後続処理の情報源にする

## Status

Accepted

## Context

将来的に、source_hint 別プレイリスト生成や曲つなぎ候補の提案を行いたい。

これらをファイル名だけから復元すると、情報が不足しやすい。

## Decision

処理済み記録は `organizer_log.jsonl` に1曲1行のJSONとして追記する。

ログには少なくとも以下を残す。

- 元パス
- 出力先パス
- アーカイブ先パス
- source_hint
- SHA-256
- 推定BPM
- 丸めBPM
- BPM候補
- 推定Key
- Camelot Key
- status
- error

source_hint 別プレイリスト生成や Codex による曲提案は、このログを主な入力にする。

## Consequences

後続処理がファイル名パースに依存しにくくなる。

ログが壊れたり欠けたりすると、プレイリスト生成や推薦の品質に影響する。

