# images_to_a4_pdf.py

[images_to_a4_pdf.py](images_to_a4_pdf.py)

画像列を A4 PDF にまとめるスクリプト。

横長の譜面帯、スクリーンショット、スキャン画像などを、白背景の A4 ページへ上から順に配置する。

## 基本的な使い方

```bash
images_to_a4_pdf.py build 'score/*.webp' score.pdf
```

`INPUT_PATTERN` に一致した画像を自然順で並べ、`OUTPUT_PDF` に保存する。入力画像は WebP、PNG、JPEG など、Pillow が読める形式を指定できる。

## オプション

```bash
images_to_a4_pdf.py build INPUT_PATTERN OUTPUT_PDF
```

- `INPUT_PATTERN`: 入力画像の glob パターン
- `OUTPUT_PDF`: 出力 PDF ファイル

| オプション | 説明 |
| --- | --- |
| `--page_size` | ページサイズ (default: `a4`)。 |
| `--orientation` | ページの向き。`portrait` または `landscape` (default: `portrait`)。 |
| `--dpi` | PDF 作成時の解像度とページピクセルサイズの計算に使う dpi (default: 300)。 |
| `--margin_x` | 左右の余白。ピクセル単位 (default: 140)。 |
| `--margin_y` | 上下の余白。ピクセル単位 (default: 160)。 |
| `--gap` | 画像同士の間隔。ピクセル単位 (default: 32)。 |
| `--background` | ページ背景色。Pillow が解釈できる色名または `#RRGGBB` (default: `white`)。 |
| `--sort` | 入力画像の並び順 (default: `natural`)。 |
| `--no_upscale` | ページ幅より小さい画像を拡大しない。 |
| `-n` / `--dry_run` | PDF を作らず、入力枚数、ページサイズ、ページ数見込み、出力先を表示する。 |

## レイアウト

各画像はページの本文幅に合わせて拡大縮小し、中央揃えで上から順に配置する。

ページに収まらない場合は次のページに送る。1 枚の画像が本文高さより大きい場合は、本文高さに収まるように縮小する。

## 例

今回のように `score/*.webp` を A4 PDF にまとめる。

```bash
images_to_a4_pdf.py build 'score/*.webp' score.pdf
```

実行前にページ数を確認する。

```bash
images_to_a4_pdf.py build 'score/*.webp' score.pdf -n
```
