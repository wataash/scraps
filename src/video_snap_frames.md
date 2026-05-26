# video_snap_frames.py

[video_snap_frames.py](video_snap_frames.py)

mpv で再生しながら手動で記録したタイムスタンプ一覧を stdin に渡すと、各時刻の1フレームを crop して `001.webp`, `002.webp`, ... の連番 WebP として保存するスクリプト。

fps サンプリング + dHash 重複除去で一括抽出する場合は [video_extract_score.py](video_extract_score.py) を使う。

## 使用例

```sh
mpv --term-status-msg='frame:${estimated-frame-number} time=${time-pos/full}' --loop=inf in.webm
# 保存したいフレームで Ctrl+C してタイムスタンプをコピー

video_snap_frames.py in.webm out/ --crop WIDTH:HEIGHT:X:Y <<'TIMES'
frame:0 time=00:00:00.000
frame:1059 time=00:00:17.650
frame:13880 time=00:03:51.350
TIMES
```

## 入力形式

stdin (または `--times_file`) の各行は以下の形式を受け付ける。

- `frame:N time=HH:MM:SS.sss` — mpv の `--term-status-msg` 出力をそのまま貼れる
- `HH:MM:SS.sss` — プレーンなタイムスタンプ

空行・`#` 始まりの行は無視される。

## オプション

| オプション | 説明 |
| --- | --- |
| `--crop` | 切り出し範囲。`幅:高さ:x:y` 形式（必須） |
| `--times_file` | タイムスタンプファイル。省略時は stdin |
| `--quality` | WebP の品質 (default: 95) |
| `--method` | WebP エンコード方法。0–6、大きいほど高圧縮 (default: 6) |
| `--digits` | 出力ファイル名のゼロ埋め桁数 (default: 3) |
| `--clean` / `--no-clean` | 出力先の既存 `*.webp` を削除してから保存するか (default: `--clean`) |
| `-n` / `--dry_run` | ffmpeg コマンドを表示するだけで実行しない |
