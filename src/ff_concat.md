# ff_concat.py

[ff_concat.py](ff_concat.py)

stdin で動画ファイル名を受け取り、それらを結合する `ffmpeg` コマンドを標準出力に**印刷**するスクリプト。コマンドは実行せず、コピー & ペーストで実行する。

入力動画の解像度に応じて 3 通りのコマンドを出し分ける。

- 解像度が全て同じ: concat demuxer (`-f concat`) を使うコマンド。`--resolution H` 指定時は `-vf scale=-2:H` を付ける。
- 解像度が異なる && `--resolution` なし: `filter_complex` で各動画を最大解像度に scale + pad → `concat` フィルタ
- 解像度が異なる && `--resolution H` あり: 上記の末尾に `scale=-2:H` を 1 段足して縮小

## 基本的な使い方

```bash
ls *.mp4 | ff_concat.py
ls *.mp4 | ff_concat.py -o out.mkv
ls *.mp4 | ff_concat.py --resolution 320p -o out.320.mkv
printf '%s\n' a.mp4 b.mp4 c.mp4 | ff_concat.py
```

stdin で読んだ各ファイルに対して `ffprobe` を呼んで解像度を取得し、stderr に一覧を出力したうえで、結合コマンドを stdout に印刷する。

## オプション

| オプション | 説明 |
| --- | --- |
| `-o`, `--output` | 出力ファイル名 (default: `out.mkv`)。 |
| `--resolution` | 最終出力の高さ。`320` または `320p` のように指定。 |

## 出力例

解像度が異なる入力 + `--resolution 320p`:

```text
ffmpeg -hide_banner \
  -i a.mp4 \
  -i b.mp4 \
  -filter_complex '
    [0:v]scale=W:H:force_original_aspect_ratio=decrease,pad=W:H:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v0];
    [1:v]scale=W:H:force_original_aspect_ratio=decrease,pad=W:H:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v1];
    [v0][0:a][v1][1:a]concat=n=2:v=1:a=1[vc][a];
    [vc]scale=-2:320[v]
  ' -map '[v]' -map '[a]' -movflags +faststart -pix_fmt yuvj420p -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k out.mkv
```

解像度が同じ入力:

```text
printf "file '%s'\n" \
  a.mp4 \
  b.mp4 \
  > list.txt
ffmpeg -hide_banner -f concat -safe 0 -i list.txt -movflags +faststart -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k out.mkv
```

## 前提・注意

- 入力動画のフレームレート (`r_frame_rate`) とオーディオサンプルレートは全ファイルで揃っている必要がある。異なる場合はエラー終了する (`concat` フィルタが `Input link parameters do not match` で失敗するのを未然に防ぐため)。揃えたい場合は別途 `ffmpeg -r ... -ar ...` で前処理する。
