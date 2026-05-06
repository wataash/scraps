# Video Track Guidelines

[video_track.py](video_track.py)

## Project Structure & Module Organization

The video tracking tools are standalone Python CLI scripts centered on `video_track.py`.

- `video_track.py` is the main tracking CLI entry point.
- `video_track_draw_box.py` and `video_track_stabilize.py` hold larger subcommand implementations split out from `video_track.py`.
- `lib_/video_time.py` contains reusable, generic video time/frame parsing logic. Keep `lib_/` limited to broadly reusable helpers.
- Generated media, JSON/JSONL tracking files, model weights, and preview images should not be treated as source.

## Build, Test, and Development Commands

There is no build step. Run scripts directly:

```bash
video_track.py -h
video_track.py detect input.mp4 input.detect.jsonl --start=0 --end=last --init-bbox W:H:X:Y
video_track.py finalize input.mp4 input.detect.jsonl input.detect.json
video_track.py draw_box input.mp4 input.detect.json --preview_gui
video_track.py stabilize input.mp4 input.detect.json
```

`detect` writes live JSONL and annotated preview videos while it runs:

- `<input>.detect.preview.mp4v.mkv`
- `<input>.detect.preview.h264.mkv`

`draw_box input.mp4 input.detect.json` writes boxed videos by default:

- `input.boxed.mp4v.mkv`
- `input.boxed.h264.mkv`

The `*.boxed.h264.mkv` file is encoded in real time from the drawn frames with `libx264` while copying audio from the source.

`stabilize input.mp4 input.detect.json` writes stabilized videos by default:

- `input.stabilized.mp4v.mkv`
- `input.stabilized.h264.mkv`

The `*.stabilized.h264.mkv` file is also encoded in real time with `libx264` while copying audio from the source.

Check syntax before committing:

```bash
python3 -m py_compile video_track.py video_track_draw_box.py video_track_stabilize.py lib_/video_time.py
```

These commands require external tools such as `ffmpeg`, `ffprobe`, OpenCV, tqdm, and optional YOLO model weights.

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation and type hints where they clarify interfaces. Prefer `argparse` subcommands for user-facing behavior. Keep CLI option names explicit and consistent with existing style, for example `--preview_gui`, `--start`, `--end`, and `--duration`.

Use `snake_case` for functions, variables, and module names. Keep video-track-specific code in `video_track_*.py`; only move generic utilities into `lib_/`.

## Testing Guidelines

No formal test suite is currently present. Validate changes with focused CLI smoke tests and syntax checks. For video changes, test a short clip and verify JSONL, both detect preview videos, and final output video behavior.

Useful checks:

```bash
video_track.py detect short.mp4 short.detect.jsonl --preview_gui --init-bbox W:H:X:Y
video_track.py finalize short.mp4 short.detect.jsonl short.detect.json
video_track.py draw_box short.mp4 short.detect.json --preview_gui
ffprobe -hide_banner -v error -select_streams v:0 -show_entries stream=codec_name short.mp4.detect.preview.h264.mkv
```

## Commit & Pull Request Guidelines

Recent commits use short, path-focused messages such as `s/video_track.py` or `s/lib_/video_time.py`. Keep commits small and describe the files or behavior changed.

For pull requests, include the user-visible command affected, a concise behavior summary, and any manual verification commands. Include screenshots or preview notes when GUI or video output changes.

## Agent-Specific Instructions

Do not overwrite unrelated local changes. Use `rg` for searching. Prefer small, scoped edits and preserve existing CLI behavior unless the requested change explicitly alters it.
