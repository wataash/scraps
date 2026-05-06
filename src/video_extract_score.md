# video_extract_score.py

[video_extract_score.py](video_extract_score.py)

動画内に表示されている譜面帯を切り出し、重複を除いて `001.webp`, `002.webp`, ... の連番 WebP として保存するスクリプト。

主な用途は、演奏動画の上部に表示される五線譜や TAB 譜を画像として抜き出すこと。

## 基本的な使い方

```bash
video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y
```

この例では、`INPUT_VIDEO` から譜面帯を抽出し、`OUTPUT_DIR/001.webp` 以降に保存する。入力動画は `mp4`、`webm` など、ffmpeg が読める形式を指定できる。

基本的には以下の処理を行う。

- 1 秒ごとに動画をサンプリングする
- `--crop` で指定した範囲を初期位置として譜面帯を切り出す
  - クロップ範囲は [video_crop_gui.py](video_crop_gui.py) で行うと便利
- 暗い画像を除外する
- dHash で前回保存した画像と近いものを重複として除外する
- 出力先に既存の `*.webp` があれば削除してから保存する

## オプション

```bash
video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y
```

- `INPUT_VIDEO`: 入力動画ファイル。`mp4`、`webm` など、ffmpeg が読める形式
- `OUTPUT_DIR`: WebP を保存するディレクトリ

| オプション | 説明 |
| --- | --- |
| `--crop` | 初期状態の譜面帯を切り出す範囲。`幅:高さ:x:y` 形式。 |
| `--start` / `--end` / `--duration` | see [`lib_/video_time.md`](lib_/video_time.md) |
| `--fps` | 動画を何 fps でサンプリングするかを決める。ffmpeg の `fps` フィルタに渡す値。正の数または分数で指定する。`--start` / `--end` / `--duration` の `f:N` / `frame:N` 指定には使わない。フレーム指定は入力動画のフレームを基準に解決する。譜面の切り替わりが速い場合は大きくする (default: 1)。 |
| `--min_mean` | 切り出した画像の平均明度がこの値未満なら捨てる。暗転や黒画面を除外するための設定 (default: 90.0)。 |
| `--hash_size` | dHash のサイズ。通常は変更不要 (default: 16)。 |
| `--distance_threshold` | 前回保存した画像との dHash 距離がこの値以下なら重複扱いにする。保存枚数が少なすぎる場合は値を下げる。保存枚数が多すぎる場合は値を上げる (default: 18)。 |
| `--quality` | WebP の品質 (default: 95)。 |
| `--method` | WebP エンコード方法。`0` から `6`。大きいほど遅いが圧縮品質が上がりやすい (default: 6)。 |
| `--digits` | 出力ファイル名のゼロ埋め桁数。例: `001.webp`, `002.webp` (default: 3)。 |
| `--clean` / `--no-clean` | 出力先の既存 `*.webp` を削除してから保存するかどうか (default: `--clean`)。 |

### 複数区間の処理

複数の時間区間で譜面位置が違う場合は、区間ごとに複数回実行する。2回目以降は `--no-clean` を付けると、既存の最大連番の次から追記する。

```bash
video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y --start 00:00 --end 00:08
video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y --start 00:08 --no-clean
```

`--clean` の場合は `001.webp` から保存する。`--no-clean` の場合は、既存の `NNN.webp` の最大番号を探して、その次から保存する。
