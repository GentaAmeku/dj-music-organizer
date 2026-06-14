# DJ Music Organizer

DDJ-FLX4とrekordboxで使いやすい形に音源を整理するためのローカル音源整理ツール群です。

`00_Inbox` に置いた音源を解析し、BPMとCamelot Keyをファイル名に入れたうえで、BPM帯ごとのフォルダへ配置します。初期版では安全性を優先し、通常実行はプレビュー実行です。プレビュー実行では、ファイルを変更せずに処理予定だけを表示します。

## 現在の目的

- `00_Inbox` 配下の音源を検出する
- BPMを推定する
- Keyを推定し、Camelot表記へ変換する
- `{Artist} - {Title}_{BPM}BPM_{Camelot}.{ext}` 形式へ整理する
- BPM帯ごとに `01_Analyzed` へコピーする
- 元ファイルを `90_Archive` へ退避する
- BPM帯ごとの `.m3u8` プレイリストを作る
- `source_hint` 別の `.m3u8` プレイリストを作る
- USBへ `01_Analyzed` と `playlists` だけを書き出す

## 重要な前提

このリポジトリはツール置き場です。音源ライブラリではありません。

```text
/path/to/dj-music-organizer
  = ツール、設計書、Git管理対象

X:\DJ Music
/mnt/x/DJ Music
  = 実音源ライブラリ
```

実音源はリポジトリ内に置かないでください。

## 音源ライブラリ構成

```text
DJ Music/
  dj_music_organizer.config.json
  organizer_log.jsonl
  00_Inbox/
    GameOST/
    Unsorted/
  01_Analyzed/
    Under100/
    100-109/
    110-119/
    120-124/
    125-128/
    129-132/
    133-139/
    140-159/
    160-169/
    170-179/
    180-189/
    190-199/
    200-209/
    210-219/
    220plus/
    UnknownBPM/
  90_Archive/
  playlists/
    BPM/
      Under100.m3u8
      100-109.m3u8
      ...
  reports/
```

`00_Inbox/{Source}/...` の `{Source}` は `source_hint` としてログに残ります。たとえば `00_Inbox/GameOST/` に入れた曲は、後で `GameOST.m3u8` の材料になります。

## セットアップ

WSL Ubuntuで実行します。

```bash
cd /path/to/dj-music-organizer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`ffmpeg` も必要です。

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

USBやWindowsドライブがWSLから見えない場合は、PowerShell側からマウントします。以下は `E:` を `/mnt/e` にマウントする例です。

```powershell
wsl -u root sh -lc 'mkdir -p /mnt/e && mount -t drvfs E: /mnt/e'
```

## 基本コマンド

まず少数でプレビュー実行します。

```bash
cd /path/to/dj-music-organizer
.venv/bin/python tools/dj_music_organizer.py --input "/path/to/DJ Music/00_Inbox" --limit 10
```

問題なければ全件プレビュー実行します。

```bash
.venv/bin/python tools/dj_music_organizer.py --input "/path/to/DJ Music/00_Inbox"
```

実際にコピーとアーカイブを行う場合です。

```bash
.venv/bin/python tools/dj_music_organizer.py --input "/path/to/DJ Music/00_Inbox" --apply
```

`--apply` でも確認プロンプトが出ます。確認なしの `--apply --yes` は、明示的に必要なときだけ使います。

## BPMプレイリスト生成

rekordboxでBPM帯の構造をプレイリストとして読み込むため、`01_Analyzed` のBPMフォルダから `.m3u8` を生成します。

```bash
.venv/bin/python tools/dj_playlist_by_bpm.py --library-root "/path/to/DJ Music" --apply
```

プレイリストは以下に作られます。

```text
X:\DJ Music\playlists\BPM\Under100.m3u8
X:\DJ Music\playlists\BPM\100-109.m3u8
X:\DJ Music\playlists\BPM\110-119.m3u8
X:\DJ Music\playlists\BPM\120-124.m3u8
X:\DJ Music\playlists\BPM\125-128.m3u8
X:\DJ Music\playlists\BPM\129-132.m3u8
X:\DJ Music\playlists\BPM\133-139.m3u8
X:\DJ Music\playlists\BPM\140-159.m3u8
X:\DJ Music\playlists\BPM\160-169.m3u8
X:\DJ Music\playlists\BPM\170-179.m3u8
X:\DJ Music\playlists\BPM\180-189.m3u8
X:\DJ Music\playlists\BPM\190-199.m3u8
X:\DJ Music\playlists\BPM\200-209.m3u8
X:\DJ Music\playlists\BPM\210-219.m3u8
X:\DJ Music\playlists\BPM\220plus.m3u8
X:\DJ Music\playlists\BPM\UnknownBPM.m3u8
```

実際には `dj_music_organizer.config.json` の `bpm_ranges` を使うため、180以上のBPM帯も解析、配置、プレイリスト生成の対象になります。

`.m3u8` 内のパスは、各プレイリストファイルから見た相対パスです。たとえば `playlists/BPM/125-128.m3u8` では以下のようになります。

```text
../../01_Analyzed/125-128/M2U - glory day_128BPM_8A.mp3
```

空のBPM帯も含めて構造を作るのが標準です。曲が入っているBPM帯だけ作りたい場合は `--only-non-empty` を使います。

## Sourceプレイリスト生成

`organizer_log.jsonl` から `source_hint` 別の `.m3u8` を生成します。

```bash
.venv/bin/python tools/dj_playlist_by_source.py --library-root "/path/to/DJ Music" --apply
```

プレイリストは以下に作られます。

```text
X:\DJ Music\playlists\GameOST.m3u8
```

`.m3u8` 内のパスはUSBコピー後も壊れにくいように、`playlists/` から見た相対パスです。

## USB書き出し

USBには成果物だけを書き出します。

対象:

- `01_Analyzed` 配下の音源ファイル
- `playlists` 配下の `.m3u8`

対象外:

- `00_Inbox`
- `90_Archive`
- `organizer_log.jsonl`
- 設定ファイル
- レポート

プレビュー実行:

```bash
.venv/bin/python tools/dj_music_export_usb.py --library-root "/path/to/DJ Music" --usb-root "/path/to/USB"
```

実コピー:

```bash
.venv/bin/python tools/dj_music_export_usb.py --library-root "/path/to/DJ Music" --usb-root "/path/to/USB" --apply
```

既存ファイルは標準ではスキップします。更新したい場合だけ `--update` を使います。削除同期はしません。

## レポート

レポートは日付ごとにまとめます。

```text
X:\DJ Music\reports\YYYY-MM-DD\
```

索引は以下です。

```text
X:\DJ Music\reports\INDEX.md
```

索引更新:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\index_reports.ps1" -LibraryRoot "X:\DJ Music"
```

CSVよりJSONとMarkdownを優先します。

## 安全ルール

- 通常実行はプレビュー実行
- 全件処理の前に `--limit 10`
- 上書き禁止
- 解析に失敗しても全体を止めない
- `PIONEER`、`.Spotlight-V100`、`System Volume Information`、`._*` は触らない
- BPM/Keyは推定値として扱う
- Keyが怪しい場合に自動補正しない

## ドキュメント

- [DESIGN.md](DESIGN.md): 設計メモ
- [PLAN.md](PLAN.md): フェーズ計画
- [docs/adr/](docs/adr/): Architecture Decision Records
- [docs/SKILL_STRATEGY.md](docs/SKILL_STRATEGY.md): Codexスキル化方針
- [.codex/skills/dj-music-organizer-ops/](.codex/skills/dj-music-organizer-ops/): このプロジェクト用の運用スキル

## 現在の制約

- Key推定は簡易実装です。精度は今後改善します。
- `--reanalyze-unknown-key` は設計済みですが、まだ本格実装前です。
- rekordboxでの `.m3u8` 相対パス挙動は実機確認が必要です。
- USB書き出しは削除同期しません。
