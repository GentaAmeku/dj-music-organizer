# ADR 0004: BPM帯フォルダと最小限のファイル名を使う

## Status

Accepted

## Context

初期版では多くの情報を管理しすぎない方針とする。

ジャンル、用途、Source、Version などをファイル名に入れると、後から命名規則が複雑になりやすい。

## Decision

出力先はBPM帯フォルダを主軸にする。

ファイル名に入れる情報は、原則として以下だけにする。

- Title または Artist - Title
- rounded BPM
- Camelot Key

Source は `source_hint` としてログに残すが、初期版ではファイル名に入れない。

日本語などの非ASCII文字はファイル名では `_` に置換し、元名はログに残す。

## Consequences

DJ中にファイル名を読みやすく、USBやDJアプリでの互換性も高めやすい。

一方で、日本語タイトルや作品名はファイル名だけでは分かりにくくなるため、ログが対応表として重要になる。

