# score_remove_overlay.py

[score_remove_overlay.py](score_remove_overlay.py)

## Purpose

Remove colored playback overlays from score screenshots while keeping black score notation, chord text, staff lines, and measure bars.

The tool is meant for score videos where the current measure is tinted or a colored playback cursor moves across the score. It does not assume a specific color such as yellow or blue; it detects bright chromatic overlays and vertical chromatic cursor columns.

## Usage

```sh
score_remove_overlay.py process just_img just_img_clean
```

```sh
score_remove_overlay.py process just_img just_img_clean --min_chroma 14 --cursor_min_column_pixels 20
```

## Options

| Option | Description |
| --- | --- |
| `input_dir` | Directory containing source images. |
| `output_dir` | Directory for cleaned images. Created if needed. |
| `--pattern` | Input glob pattern. |
| `--min_chroma` | Minimum color spread for broad overlay detection. Lower catches weaker tint. |
| `--min_overlay_luma` | Minimum brightness for broad overlay detection. Higher protects darker antialiased notation. |
| `--cursor_min_chroma` | Minimum color spread for cursor detection. |
| `--min_cursor_luma` | Minimum brightness for cursor detection. |
| `--cursor_min_column_pixels` | Minimum colored pixels in a column. `0` means derive from image height. |
| `--cursor_min_vertical_span` | Minimum vertical span for a cursor-like column. |
| `--cursor_max_width` | Maximum contiguous cursor width. Wider colored areas are treated as broad highlights, not cursors. |
| `--cursor_expand` | Extra columns on each side of detected cursor columns. |
| `--artifact_min_column_ratio` | Minimum ratio of non-paper pixels in a column for detecting cursor compression shadows. |
| `--artifact_min_luma` | Minimum brightness for cursor shadow detection. |
| `--artifact_max_luma` | Maximum brightness for cursor shadow detection. |
| `--artifact_max_median_luma` | Maximum median brightness for cursor shadow columns. |
