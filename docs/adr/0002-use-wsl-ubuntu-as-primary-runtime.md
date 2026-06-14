# ADR 0002: WSL Ubuntu を初期版の正式実行環境にする

## Status

Accepted

## Context

音源解析では `librosa`、将来的には `essentia` や `ffmpeg` などの外部依存を使う可能性がある。

Windows ネイティブでも実行できる可能性はあるが、音楽解析ライブラリや `ffmpeg` の導入は Linux の方が安定しやすい。

## Decision

初期版の正式ターゲットは WSL Ubuntu とする。

Windows PowerShell からの直接実行は、初期版では正式サポート外とする。

## Consequences

解析ライブラリ導入の難易度を下げられる。

Windows の `X:\DJ Music` のようなライブラリは、WSL では `/mnt/x/DJ Music` のようなLinuxパスとして扱う必要がある。

rekordbox やUSB向けのパスを扱う場合は、LinuxパスとWindows/USB上のパスの違いに注意する。
