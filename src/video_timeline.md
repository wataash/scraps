# video_timeline.py

[video_timeline.py](video_timeline.py)

Read video filenames from stdin (one per line), probe each with `ffprobe`, and print a cumulative timeline of the would-be concatenated output.

## Usage

```sh
ls *.mp4 | video_timeline.py
printf '%s\n' a.mp4 b.mp4 c.mp4 | video_timeline.py
video_timeline.py -n < list.txt
```

stdout (short, chapter-marker style):

```
0:00 a.mp4
0:52 b.mp4
1:55 c.mp4
```

stderr (info log, full precision with start, end, and duration):

```
[I ...] 0:00:00.000 - 0:00:52.097 (0:00:52.097) a.mp4
[I ...] 0:00:52.097 - 0:01:55.791 (0:01:03.694) b.mp4
[I ...] 0:01:55.791 - 0:06:38.666 (0:04:42.875) c.mp4
```

stdout format: `M:SS FILENAME` (cumulative start time of each file, suitable for YouTube chapter markers).
Detailed timeline (`H:MM:SS.fff` start - end (duration)) goes to stderr via the info logger; redirect with `2>` to keep or discard.

## Options

| Option | Description |
| --- | --- |
| `-n`, `--dry_run` | Print the `ffprobe` commands that would be run, but do not execute. |
| `-h`, `--help` | Show help. |

## Requirements

- `ffprobe` available on `PATH`.
