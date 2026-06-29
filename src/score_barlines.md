# score_barlines.py

[score_barlines.py](score_barlines.py)

Detect bar-line x coordinates in a single horizontal staff image, split the image into measure slices, and lay those slices out into an A4 PDF.

The detector finds the five staff lines, extracts long vertical ink components inside the staff region, rejects likely note stems by checking a small set of geometric and neighborhood properties, then groups close accepted strokes as one barline.

The main candidate checks are:

1. The vertical stroke is almost as tall as the staff.
2. The stroke is wide enough to be a barline (>= 4 px), or just narrower (>= 3 px) with very clean surroundings, or a very clean 2 px stroke whose height is close to the staff height.
3. The immediate neighborhood has little non-staff ink, so it is not attached to a notehead or beam.
4. On compact scans, nearby full-height strokes that form a thick double/repeat bar are accepted together even when their immediate neighborhood is darker.

Double bars and repeat bars are handled by the same grouping rule: nearby candidates are grouped, and the left-side member is used as the representative `x`. Splitting and PDF layout use that representative `x`, so double/repeat bars are split at the left barline.

## Usage

```bash
python score_barlines.py detect_barlines a.webp
```

For a machine-readable result and a visual check image:

```bash
python score_barlines.py detect_barlines a.webp --json --overlay a_barlines.webp
```

To wrap a very wide visual check image for easier viewing:

```bash
python score_barlines.py detect_barlines a.webp --overlay a_barlines.png --wrap-width 2400
```

To split the full image height into numbered WebP files at detected barlines:

```bash
python score_barlines.py detect_barlines a.webp --split-dir measures
```

When writing split images, existing `NNN.webp` files in the split directory are removed first so stale measure files from an earlier run do not remain.

To lay numbered measure WebP files out into an A4 PDF:

```bash
python score_barlines.py measures_pdf a.webp out.pdf --margin 40 --scale 1.0 --measure-numbers
```

The PDF layout splits the original image at detected barlines, then packs as many measure images as possible on each row within the margin. Use `--break-after` to force row breaks after specific measure numbers, and `--measure-numbers` to draw 3-digit measure labels in the PDF.

## Options

### `detect_barlines`

| Option | Purpose |
| --- | --- |
| `image` | Input staff image. |
| `--json` | Print JSON output. |
| `--overlay PATH` | Write a visual check image with staff lines and barlines. |
| `--wrap-width PX` | Wrap the overlay image into rows of this width before saving. Detection coordinates and split images remain based on the original image. |
| `--split-dir DIR` | Write full-height slices split at detected barline x positions as `001.webp`, `002.webp`, ... Existing `NNN.webp` files in the directory are removed first. |
| `-v`, `--verbose` | Enable debug logging. |

### `measures_pdf`

| Option | Purpose |
| --- | --- |
| `source_image` | Original full-width score image used to create measure slices. |
| `output_pdf` | Output A4 PDF path. |
| `--margin PX` | Page margin in output pixels. |
| `--scale FLOAT` | Scale applied to every measure before layout. |
| `--dpi DPI` | PDF resolution; A4 page pixels are derived from this value. |
| `--row-gap PX` | Vertical gap between rows. |
| `--page-orientation portrait\|landscape` | A4 orientation. |
| `--break-after LIST` | Force row breaks after measure numbers. Accepts comma lists and ranges, e.g. `4,10-12`. Can be repeated. |
| `--exclude LIST` | Exclude measure numbers from the PDF. Accepts the same format. Other measures keep their original numbers. |
| `--measure-numbers` | Draw 3-digit measure numbers on the PDF for visual checking. |
| `-v`, `--verbose` | Enable debug logging. |
