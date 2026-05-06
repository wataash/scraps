#!/usr/bin/env python
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

epilog = r'''
ff.py -h
ff.py -n video_ts_hist PXL_20260423_104829819.mp4
ff.py video_ts_hist -h
ff.py video_ts_hist PXL_20260423_104829819.mp4
ff.py video_ts_hist --dts PXL_20260423_104829819.mp4
ff.py video_frame_type_count -h
ff.py -n video_frame_type_count PXL_20260423_104829819.mp4
ff.py video_frame_type_count PXL_20260423_104829819.mp4
ff.py mp4_cut -h
# --aac=192k --fps 30
ff.py -n mp4_cut -y --fps 30 --start 1 --end f:90 in.mp4 out.mp4
ff.py -n mp4_cut --fps 30 --start 00:01 --duration f:30 in.mp4 out.mp4 -- -c:v libx264 -crf 18 -c:a copy
'''[1:]

import argparse
import collections
import fractions
import json
import logging
import pathlib
import shlex
import subprocess
import sys
import typing as t

from lib_ import video_time


class MyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = {
            logging.CRITICAL: '\x1b[31m',
            logging.ERROR: '\x1b[31m',
            logging.WARNING: '\x1b[33m',
            logging.INFO: '\x1b[34m',
            logging.DEBUG: '\x1b[37m',
        }[record.levelno]
        fn = '' if record.funcName == '<module>' else f' {record.funcName}()'
        fmt = f'{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s\x1b[m'
        return logging.Formatter(fmt=fmt, datefmt='%T').format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


class ArgumentDefaultsRawTextHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawTextHelpFormatter,
):
    pass


class PacketTimestamps(t.NamedTuple):
    time_base: fractions.Fraction
    pts: list[int | None]
    dts: list[int | None]


class VideoTiming(t.NamedTuple):
    fps: fractions.Fraction | None
    duration: fractions.Fraction | None


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument(
        '-n',
        '--dry_run',
        action='store_true',
        help='show ffprobe/ffmpeg commands without executing them',
    )
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser(
        'video_ts_hist',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='Print a video packet timestamp delta histogram',
    )
    subparser.set_defaults(func=cmd_video_ts_hist)
    subparser.add_argument('files', nargs='+', type=pathlib.Path)
    subparser.add_argument(
        '--stream',
        default='v:0',
        help='ffprobe stream selector',
    )
    subparser.add_argument(
        '--bar-width',
        type=int,
        default=40,
        help='maximum ASCII bar width',
    )
    subparser.add_argument(
        '--dts',
        action='store_true',
        help='show DTS histogram instead of PTS',
    )
    subparser.add_argument(
        '--sort-by-count',
        action='store_true',
        help='sort histogram rows by count descending',
    )

    subparser = subparsers.add_parser(
        'video_frame_type_count',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='Count video frame pict_types',
    )
    subparser.set_defaults(func=cmd_video_frame_type_count)
    subparser.add_argument('files', nargs='+', type=pathlib.Path)
    subparser.add_argument(
        '--stream',
        default='v:0',
        help='ffprobe stream selector',
    )

    subparser = subparsers.add_parser(
        'mp4_cut',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='Cut an MP4 by time using ffmpeg',
        description=(
            'Cut INPUT to OUTPUT. At least one of --start, --end, --duration is required.\n'
            'Pass ffmpeg output options after "--"; defaults to "-c copy" when omitted.'
        ),
    )
    subparser.set_defaults(func=cmd_mp4_cut)
    subparser.add_argument(
        '-y',
        '--overwrite',
        action='store_true',
        help='overwrite output file without asking',
    )
    subparser.add_argument(
        '--aac',
        metavar='BITRATE',
        help='encode audio as AAC at BITRATE, e.g. 192k',
    )
    subparser.add_argument(
        '--fps',
        type=video_time.parse_fps,
        help='fps used to resolve frame:N/f:N without ffprobe, useful with -n',
    )
    subparser.add_argument('--start', type=video_time.parse_time_or_frame, help='cut start time, frame:N/f:N, or last')
    subparser.add_argument('--end', type=video_time.parse_time_or_frame, help='cut end time, frame:N/f:N, or last')
    subparser.add_argument('--duration', type=video_time.parse_time_or_frame, help='cut duration time or frame:N/f:N')
    subparser.add_argument('input', type=pathlib.Path)
    subparser.add_argument('output', type=pathlib.Path)
    subparser.add_argument(
        'ffmpeg_args',
        nargs=argparse.REMAINDER,
        help='ffmpeg output options after "--" (default: -c copy)',
    )

    args = parser.parse_args()
    return args.func(args)


def cmd_video_ts_hist(args: argparse.Namespace) -> int:
    if args.bar_width <= 0:
        logger.error('--bar-width must be positive')
        return 2

    for path in args.files:
        timestamps = load_packet_timestamps(path, args.stream, dry_run=args.dry_run)
        if timestamps is None:
            continue
        warn_if_pts_dts_differ(path, timestamps)
        print_histogram(
            path,
            timestamps,
            args.bar_width,
            show_dts=args.dts,
            sort_by_count=args.sort_by_count,
        )
    return 0


def cmd_video_frame_type_count(args: argparse.Namespace) -> int:
    for path in args.files:
        frame_types = load_frame_pict_types(path, args.stream, dry_run=args.dry_run)
        if frame_types is None:
            continue
        print_frame_type_count(path, frame_types)
    return 0


def cmd_mp4_cut(args: argparse.Namespace) -> int:
    fps = args.fps
    duration = None
    if video_time.is_last_ref(args.duration):
        raise SystemExit('--duration cannot be last')
    if any(video_time.is_frame_ref(value) for value in (args.start, args.end, args.duration)):
        if fps is None:
            fps = load_video_timing(args.input, dry_run=args.dry_run).fps
        if fps is None:
            raise SystemExit('frame:N/f:N needs video fps; rerun without -n or pass --fps')
    if any(video_time.is_last_ref(value) for value in (args.start, args.end)):
        timing = load_video_timing(args.input, dry_run=args.dry_run)
        duration = timing.duration
        if duration is None:
            raise SystemExit('last needs video duration; rerun without -n')
    times = video_time.resolve_cut_times(
        start=video_time.resolve_seconds(args.start, fps, duration),
        end=video_time.resolve_seconds(args.end, fps, duration),
        duration=video_time.resolve_seconds(args.duration, fps, duration),
    )
    command = build_mp4_cut_command(
        infile=args.input,
        outfile=args.output,
        times=times,
        ffmpeg_args=normalize_ffmpeg_args(args.ffmpeg_args, aac_bitrate=args.aac),
        overwrite=args.overwrite,
    )
    run_ffmpeg(command, dry_run=args.dry_run)
    return 0


def load_packet_timestamps(
    path: pathlib.Path,
    stream: str,
    *,
    dry_run: bool,
) -> PacketTimestamps | None:
    data = run_ffprobe_json(
        path,
        stream,
        'stream=time_base:packet=pts,dts',
        dry_run=dry_run,
    )
    if data is None:
        return None
    streams = data.get('streams', [])
    if not streams:
        raise SystemExit(f'no stream matched {stream!r} in {path}')

    time_base = fractions.Fraction(streams[0]['time_base'])
    packets = data.get('packets', [])
    pts = [parse_optional_int(packet.get('pts')) for packet in packets]
    dts = [parse_optional_int(packet.get('dts')) for packet in packets]
    return PacketTimestamps(time_base=time_base, pts=pts, dts=dts)


def load_frame_pict_types(
    path: pathlib.Path,
    stream: str,
    *,
    dry_run: bool,
) -> list[str] | None:
    data = run_ffprobe_json(path, stream, 'frame=pict_type', dry_run=dry_run)
    if data is None:
        return None
    frames = data.get('frames', [])
    return [frame['pict_type'] for frame in frames if 'pict_type' in frame]


def run_ffprobe_json(
    path: pathlib.Path,
    stream: str,
    show_entries: str,
    *,
    dry_run: bool,
) -> dict[str, t.Any] | None:
    cmd = [
        'ffprobe',
        '-v',
        'error',
        '-select_streams',
        stream,
        '-show_entries',
        show_entries,
        '-of',
        'json',
        str(path),
    ]
    command_text = shlex.join(cmd)
    if dry_run:
        logger.info('dry_run: %s', command_text)
        return None

    logger.debug('running command: %s', command_text)
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SystemExit('ffprobe not found in PATH') from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise SystemExit(stderr or f'ffprobe failed for {path}') from exc

    data = json.loads(res.stdout)
    return t.cast(dict[str, t.Any], data)


def load_video_fps(path: pathlib.Path, *, dry_run: bool) -> fractions.Fraction | None:
    return load_video_timing(path, dry_run=dry_run).fps


def load_video_timing(path: pathlib.Path, *, dry_run: bool) -> VideoTiming:
    data = run_ffprobe_json(
        path,
        'v:0',
        'stream=avg_frame_rate,r_frame_rate,duration:format=duration',
        dry_run=dry_run,
    )
    if data is None:
        return VideoTiming(fps=None, duration=None)
    streams = data.get('streams', [])
    if not streams:
        raise SystemExit(f'no video stream found in {path}')

    stream = streams[0]
    fps = None
    for key in ('avg_frame_rate', 'r_frame_rate'):
        value = stream.get(key)
        if not value or value == '0/0':
            continue
        candidate = fractions.Fraction(value)
        if candidate > 0:
            fps = candidate
            break

    duration = parse_optional_fraction(stream.get('duration'))
    if duration is None:
        duration = parse_optional_fraction(data.get('format', {}).get('duration'))
    return VideoTiming(fps=fps, duration=duration)


def run_ffmpeg(cmd: list[str], *, dry_run: bool) -> None:
    command_text = shlex.join(cmd)
    if dry_run:
        print(command_text)
        return

    logger.info(command_text)
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise SystemExit('ffmpeg not found in PATH') from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f'ffmpeg failed with exit code {exc.returncode}') from exc


def parse_optional_int(value: str | None) -> int | None:
    if value in (None, 'N/A'):
        return None
    return int(value)


def parse_optional_fraction(value: str | None) -> fractions.Fraction | None:
    if value in (None, 'N/A'):
        return None
    parsed = fractions.Fraction(value)
    return parsed if parsed >= 0 else None


def normalize_ffmpeg_args(
    ffmpeg_args: list[str],
    *,
    aac_bitrate: str | None,
) -> list[str]:
    if ffmpeg_args and ffmpeg_args[0] == '--':
        ffmpeg_args = ffmpeg_args[1:]
    if not ffmpeg_args:
        ffmpeg_args = ['-c', 'copy']
    if aac_bitrate:
        ffmpeg_args = [*ffmpeg_args, '-c:a', 'aac', '-b:a', aac_bitrate]
    return ffmpeg_args


def build_mp4_cut_command(
    *,
    infile: pathlib.Path,
    outfile: pathlib.Path,
    times: video_time.CutTimes,
    ffmpeg_args: list[str],
    overwrite: bool,
) -> list[str]:
    command = ['ffmpeg', '-hide_banner']
    if overwrite:
        command.append('-y')
    if times.start is not None:
        command.extend(['-ss', format_time_arg(times.start)])
    command.extend(['-i', str(infile)])
    if times.duration is not None:
        command.extend(['-t', format_time_arg(times.duration)])
    command.extend(ffmpeg_args)
    command.append(str(outfile))
    return command


def format_time_arg(value: fractions.Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    text = f'{float(value):.9f}'.rstrip('0').rstrip('.')
    return text or '0'


def print_histogram(
    path: pathlib.Path,
    timestamps: PacketTimestamps,
    bar_width: int,
    *,
    show_dts: bool,
    sort_by_count: bool,
) -> None:
    print(f'FILE {path}')
    print(f'time_base={timestamps.time_base}')
    label = 'DTS' if show_dts else 'PTS'
    values = timestamps.dts if show_dts else timestamps.pts
    print(
        format_histogram(
            label,
            timestamps.time_base,
            values,
            bar_width,
            sort_by_count=sort_by_count,
        )
    )
    print()


def print_frame_type_count(path: pathlib.Path, frame_types: list[str]) -> None:
    counts = collections.Counter(frame_types)
    known_types = ('I', 'P', 'B')
    fields = [f'{frame_type} {counts.get(frame_type, 0)}' for frame_type in known_types]
    for frame_type in sorted(counts):
        if frame_type in known_types:
            continue
        fields.append(f'{frame_type} {counts[frame_type]}')
    print(f'FILE {path}')
    print(' '.join(fields))
    print()


def warn_if_pts_dts_differ(path: pathlib.Path, timestamps: PacketTimestamps) -> None:
    if timestamps.pts == timestamps.dts:
        return

    mismatch_count = 0
    first_mismatch: tuple[int, int | None, int | None] | None = None
    max_len = max(len(timestamps.pts), len(timestamps.dts))
    for i in range(max_len):
        pts = timestamps.pts[i] if i < len(timestamps.pts) else None
        dts = timestamps.dts[i] if i < len(timestamps.dts) else None
        if pts == dts:
            continue
        mismatch_count += 1
        if first_mismatch is None:
            first_mismatch = (i, pts, dts)

    assert first_mismatch is not None
    index, pts, dts = first_mismatch
    logger.warning(
        '%s: pts and dts differ (%d mismatched packets, first at index=%d pts=%r dts=%r)',
        path,
        mismatch_count,
        index,
        pts,
        dts,
    )


def format_histogram(
    label: str,
    time_base: fractions.Fraction,
    values: list[int | None],
    bar_width: int,
    *,
    sort_by_count: bool,
) -> str:
    histogram = collections.Counter(
        compute_deltas(values, reorder_for_display=(label == 'PTS'))
    )
    total = sum(histogram.values())
    lines = [f'[{label}] total_deltas={total}']
    if total == 0:
        lines.append('  (no deltas)')
        return '\n'.join(lines)

    max_count = max(histogram.values())
    if sort_by_count:
        ticks_values = sorted(histogram, key=lambda ticks: (-histogram[ticks], ticks))
    else:
        ticks_values = sorted(histogram)

    for ticks in ticks_values:
        seconds = float(ticks * time_base)
        hz_text = 'inf' if seconds == 0 else f'{1 / seconds:.8f}'
        count = histogram[ticks]
        share = count / total
        width = max(1, round(bar_width * count / max_count))
        bar = '#' * width
        lines.append(
            f'  {seconds:>12.9f} s ({hz_text} Hz)  ticks={ticks:>5}  '
            f'count={count:>5}  share={share:>8.4%}  {bar}'
        )
    return '\n'.join(lines)


def compute_deltas(
    values: list[int | None],
    *,
    reorder_for_display: bool = False,
) -> list[int]:
    if reorder_for_display:
        filtered_values: list[int | None] = sorted(
            (value for value in values if value is not None)
        )
    else:
        filtered_values = values

    deltas: list[int] = []
    prev: int | None = None
    for value in filtered_values:
        if value is None:
            continue
        if prev is not None:
            deltas.append(value - prev)
        prev = value
    return deltas


if __name__ == '__main__':
    raise SystemExit(main())
