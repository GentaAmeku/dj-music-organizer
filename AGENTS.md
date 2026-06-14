# AGENTS.md

このプロジェクトでは常に日本語で返答する。ユーザーの前提にはまず批判的に向き合い、合理的な場合に限って同意する。

## Project Shape

- このリポジトリはツール本体と設計文書の置き場である。
- 実音源ライブラリは任意の外部ディレクトリに置く。原則としてこのリポジトリ内に `00_Inbox` を作らない。
- `PIONEER`、`.Spotlight-V100`、`System Volume Information`、`._*` はDJアプリやOS由来の可能性があるため、明示依頼なしに変更しない。

## Required Safety Workflow

- 音源ファイルに対する操作は、必ずdry-runを先に実行する。
- `--apply` はdry-run結果を確認してから使う。
- `--apply --yes` はユーザーが明示した場合だけ使う。
- 上書きや削除を避ける。USB exportでも削除同期はしない。
- 全件処理の前に `--limit 10` などで小さく確認する。

## WSL and PowerShell Lessons

- WSLでWindows/USBドライブが見えない場合は、まず対象の `/mnt/<drive-letter>` の有無を確認する。
- 必要なら `wsl -u root sh -lc 'mkdir -p /mnt/e && mount -t drvfs E: /mnt/e'` のように対象ドライブをマウントする。
- PowerShellからWSLへ複雑なコマンドを渡す場合、`$()` やパイプがPowerShell側に解釈されないように注意する。
- Bashのパイプやコマンド置換を使う場合は、`wsl -e bash -lc '...'` を優先する。
- PowerShellスクリプトは実行ポリシーで止まることがあるため、必要に応じて `powershell -NoProfile -ExecutionPolicy Bypass -File ...` を使う。

## Reports

- レポートは音源ライブラリ配下の `reports/YYYY-MM-DD/` に置く。
- 最新の索引は音源ライブラリ配下の `reports/INDEX.md`。
- レポート生成や移動後は `tools/index_reports.ps1` で索引を更新する。
- CSVよりJSON/Markdownを優先する。JSONは機械可読、Markdownは人間確認用。

## Analysis Notes

- `.venv` はリポジトリに含めない。
- 解析環境はプロジェクト内 `.venv` を使う。
- BPM/Keyは推定値であり、正解として扱わない。
- Key推定は特に揺れるため、`UnknownKey` や怪しい結果を無理に補正しない。
- BPM帯の有無を判断するときは、物理フォルダだけでなく `organizer_log.jsonl` の `rounded_bpm` と `bpm_candidates` も確認する。
- `bpm_candidates` はプレイリスト候補として扱い、正解データなしにリネームや物理移動へ使わない。
- 非ASCIIのメタデータがあり、ファイル名がASCII化済みの場合は、ファイル名側を優先した方が安全なことがある。

## Useful Commands

```bash
cd /path/to/dj-music-organizer
.venv/bin/python tools/dj_music_organizer.py --input "/path/to/DJ Music/00_Inbox" --limit 10
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\index_reports.ps1" -LibraryRoot "X:\DJ Music"
```
