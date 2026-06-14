# ADR 0006: USB向け m3u8 は相対パスにする

## Status

Accepted

## Context

最終的な利用先はUSB上の `DJ Music` フォルダである。

Windows のUSBドライブレターは `E:\`、`F:\` など環境や接続タイミングで変わる可能性がある。

`.m3u8` に絶対パスを書くと、ドライブレターが変わったときにプレイリストが壊れる可能性がある。

## Decision

`playlists/{source_hint}.m3u8` には、`playlists/` から見た相対パスを書く。

例:

```text
../01_Analyzed/125-128/M2U - glory day_128BPM_8A.mp3
```

`playlists/BPM/{BPMRange}.m3u8` には、`playlists/BPM/` から見た相対パスを書く。

例:

```text
../../01_Analyzed/125-128/M2U - glory day_128BPM_8A.mp3
```

PC内ライブラリとUSB内ライブラリは同じ構成にする。

```text
DJ Music/
  01_Analyzed/
  playlists/
    BPM/
```

## Consequences

USBのドライブレターが変わっても、フォルダ構造が保たれていればプレイリストが壊れにくい。

一方で、rekordbox側の相対パス解決に依存するため、実機での確認は必要になる。
