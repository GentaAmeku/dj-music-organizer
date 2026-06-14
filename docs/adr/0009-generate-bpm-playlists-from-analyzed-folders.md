# ADR 0009: BPMプレイリストは解析済みフォルダと候補BPMから生成する

## Status

Accepted

## Context

rekordboxでBPM帯のフォルダ構造を見やすく扱うには、実ファイルのフォルダ構造だけでなく、プレイリストとしての構造も必要になる。

このプロジェクトでは、解析済み音源を `01_Analyzed/{BPMRange}/` に配置している。BPMプレイリストはこの表示をrekordboxへ渡すためのものなので、現在の解析済みフォルダ構造を反映していることが重要である。

一方で、BPM解析は半分または倍のテンポで検出されることがある。たとえば主BPMが `99` と推定された曲でも、DJ用途では `198` として扱いたい場合がある。

以前の方針では、半分/倍テンポへの自動補正は行わないことにしていた。これは今も維持する。正解データなしに音源ファイルをリネーム、移動するのは危険である。

ただし、プレイリストは表示用の派生物なので、`bpm_candidates` を使って同じ曲を複数のBPM帯に出すことは比較的安全である。

## Decision

BPMプレイリストは2つのモードで生成できる。

通常モードでは、`01_Analyzed/{BPMRange}/` の実ファイルから生成する。

候補BPMモードでは、成功した `organizer_log.jsonl` の `rounded_bpm` と `bpm_candidates` から生成する。存在しない `dest_path` は含めない。同じ曲が複数のBPM帯に入ることを許容する。

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

候補BPMモードを使うと、半分で解析された可能性のある曲も180以上などのBPM帯に表示できる。

USBへ `01_Analyzed` と `playlists` を同じ構造でコピーすれば、PC内ライブラリとUSB内ライブラリの両方で同じ相対パスを使える。

一方で、候補BPMモードでは同じ曲が複数のBPMプレイリストに出る。これは誤りではなく、半分/倍テンポの候補をrekordbox側で見つけやすくするための設計である。
