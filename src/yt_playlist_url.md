# yt_playlist_url.py

[yt_playlist_url.py](yt_playlist_url.py)

YouTubeリンクを含むテキストから、一時プレイリストURLを作ります。

対応しているYouTube URLから動画IDを抽出し、ブラウザで開いてYouTubeプレイリストに保存できる `watch_videos` URLを出力します。

## 使い方

```bash
python yt_playlist_url.py input.txt
python yt_playlist_url.py input1.txt input2.txt
printf '%s\n' 'https://youtu.be/70SIcpdk_Mo?si=example' | python yt_playlist_url.py
python yt_playlist_url.py --ids-only input.txt
```

## オプション

| オプション | デフォルト | 説明 |
| --- | --- | --- |
| `input_files` | `-` | YouTube URLを含むテキストファイル(複数指定可)。`-` は標準入力。 |
| `--ids-only` | off | `watch_videos` URLではなく、カンマ区切りの動画IDだけを出力する。 |
| `--keep-duplicates` | off | 抽出順を保ったまま、重複した動画IDも残す。 |

## 対応URL

- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://m.youtube.com/watch?v=VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
