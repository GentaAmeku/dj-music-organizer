# ADR 0009: BPMプレイリストは解析済みフォルダから生成する

## Status

Accepted

## Context

rekordboxでBPM帯のフォルダ構造を見やすく扱うには、実ファイルのフォルダ構造だけでなく、プレイリストとしての構造も必要になる。

このプロジェクトでは、解析済み音源を `01_Analyzed/{BPMRange}/` に配置している。BPMプレイリストはこの表示をrekordboxへ渡すためのものなので、過去の処理ログよりも、現在の解析済みフォルダ構造を反映していることが重要である。

`organizer_log.jsonl` には復旧履歴や過去の失敗履歴が残ることがある。そのため、BPMプレイリストをログから作ると、現在存在しないファイルや重複した処理履歴の影響を受けやすい。

## Decision

BPMプレイリストは `01_Analyzed/{BPMRange}/` の実ファイルから生成する。

出力先は以下とする。

```text
DJ Music/playlists/BPM/{BPMRange}.m3u8
```

`{BPMRange}` は `dj_music_organizer.config.json` の `bpm_ranges` に従う。`UnknownBPM` も同じ階層に生成する。

`.m3u8` 内のパスは、各 `.m3u8` ファイルから見た相対パスにする。

例:

```text
../../01_Analyzed/125-128/M2U - glory day_128BPM_8A.mp3
```

## Consequences

rekordboxに取り込むためのBPM別プレイリストが、現在の `01_Analyzed` の状態と一致しやすくなる。

USBへ `01_Analyzed` と `playlists` を同じ構造でコピーすれば、PC内ライブラリとUSB内ライブラリの両方で同じ相対パスを使える。

一方で、`01_Analyzed` の外にある音源や、手動で別フォルダへ移動した音源はBPMプレイリストに入らない。BPMプレイリストへ載せたい音源は、まず `01_Analyzed/{BPMRange}/` に配置する必要がある。
