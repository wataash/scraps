# score_stitch.py

[score_stitch.py](score_stitch.py)

## Purpose

Stitch a series of horizontally-overlapping score image fragments into a single
wide image. For each pair of consecutive images, find the overlap width by
scanning for the column shift with a low mean absolute error between the right
edge of the earlier image and the left edge of the next, then concatenate with
overlaps removed.

Designed for cases where score systems were captured as separate strips that
were intentionally cut with a small overlap (so adjacent strips share one or
more bars at their boundary).

## Usage

```sh
score_stitch.py stitch feel feel.webp
```

```sh
score_stitch.py stitch feel feel.webp --kmax 600 --threshold 12
```

```sh
score_stitch.py stitch feel feel.webp -n
```

```sh
score_stitch.py stitch just_clean just_wrapped.png --wrap-width 2400
```

## Options

| Option | Description |
| --- | --- |
| `input_dir` | Directory containing source images. Files are sorted by name. |
| `output_file` | Output image path. WebP recommended. |
| `--pattern` | Input glob pattern. |
| `--kmin` | Minimum overlap width to consider, in pixels. |
| `--kmax` | Maximum overlap width to consider, in pixels. If omitted, it is chosen from the input width. |
| `--score-margin` | Prefer the largest overlap whose MAE is within this margin of the best MAE. This avoids choosing tiny false overlaps on mostly-white score images. |
| `--larger-min-gap` | Only prefer a larger near-tie overlap when it is at least this many pixels larger than the best-MAE overlap. |
| `--threshold` | If best MAE for a pair is at least this value, the pair is treated as having no overlap (k=0) and a warning is emitted. |
| `--wrap-width` | Wrap the stitched image into rows of this width before saving. |
| `--lossless` | Write WebP losslessly when saving to `.webp`. |
| `-n`, `--dry_run` | Detect overlaps and report sizes only; do not write the output file. |

## Notes

- WebP has a hard maximum dimension of 16383 px. If the stitched output exceeds
  that size and the requested output suffix is `.webp`, the script automatically
  falls back to saving as `.png` at the same basename and emits a warning.
- The automatic `--kmax` is `min(width - 1, max(400, width * 0.75))`, so wide
  score strips can detect large overlaps without extra options.
- The default threshold is intentionally a little tolerant because compressed
  WebP score captures often have MAE slightly above 10 even at the right match.
