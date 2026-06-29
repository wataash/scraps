#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
ls *.mp4 | ff_concat.py
ls *.mp4 | ff_concat.py -o out.mkv
ls *.mp4 | ff_concat.py --resolution 320p -o out.320.mkv
printf '%s\n' a.mp4 b.mp4 c.mp4 | ff_concat.py
'''[1:]

import argparse
import json
import logging
import pathlib
import re
import subprocess
import sys
import typing as t


try:
    from _colorize import get_colors  # Python 3.13+ (private API)
except ImportError:
    class _NoColors:
        RED = YELLOW = BLUE = WHITE = RESET = ""

    def get_colors(colorize=False, *, file=None):  # type: ignore[misc]
        return _NoColors


class MyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        c = get_colors(file=sys.stderr)
        color = {
            logging.CRITICAL: c.RED,
            logging.ERROR: c.RED,
            logging.WARNING: c.YELLOW,
            logging.INFO: c.BLUE,
            logging.DEBUG: c.WHITE,
        }[record.levelno]
        fn = '' if record.funcName == '<module>' else f' {record.funcName}()'
        fmt = f'{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s{c.RESET}'
        return logging.Formatter(fmt=fmt, datefmt='%T').format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


class ProbeResult(t.NamedTuple):
    width: int
    height: int
    fps: str  # r_frame_rate, e.g. '30/1'
    sample_rate: str  # e.g. '48000'


def probe(path: pathlib.Path, progress: str = '') -> ProbeResult:
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'stream=codec_type,width,height,r_frame_rate,sample_rate',
        '-of', 'json', str(path),
    ]
    logger.debug(f'{progress}+ {" ".join(cmd)}')
    out = subprocess.check_output(cmd, text=True)
    streams = json.loads(out)['streams']
    v = next((s for s in streams if s.get('codec_type') == 'video'), None)
    a = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if v is None:
        raise RuntimeError(f'no video stream in {path}')
    if a is None:
        raise RuntimeError(f'no audio stream in {path}')
    result = ProbeResult(
        width=int(v['width']),
        height=int(v['height']),
        fps=str(v['r_frame_rate']),
        sample_rate=str(a['sample_rate']),
    )
    logger.debug(f'  -> {result}')
    return result


def parse_resolution(s: str) -> int:
    m = re.fullmatch(r'(\d+)p?', s)
    if not m:
        raise argparse.ArgumentTypeError(f'invalid resolution: {s!r} (expected e.g. 320 or 320p)')
    return int(m.group(1))


def build_concat_demuxer_cmd(files: list[pathlib.Path], out_h: int | None, output: str) -> str:
    lines = ['printf "file \'%s\'\\n" \\']
    for f in files:
        lines.append(f'  {f} \\')
    lines.append('  > list.txt')
    vf = f'-vf scale=-2:{out_h} ' if out_h is not None else ''
    lines.append(
        f'ffmpeg -hide_banner -f concat -safe 0 -i list.txt '
        f'{vf}-movflags +faststart -c:v libx264 -crf 18 -preset medium '
        f'-c:a aac -b:a 192k {output}'
    )
    return '\n'.join(lines)


def build_filter_complex_cmd(
    files: list[pathlib.Path],
    max_w: int,
    max_h: int,
    out_h: int | None,
    output: str,
) -> str:
    lines = ['ffmpeg -hide_banner \\']
    for f in files:
        lines.append(f'  -i {f} \\')
    lines.append("  -filter_complex '")
    for i, _ in enumerate(files):
        lines.append(
            f'    [{i}:v]scale={max_w}:{max_h}:force_original_aspect_ratio=decrease,'
            f'pad={max_w}:{max_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v{i}];'
        )
    n = len(files)
    concat_inputs = ''.join(f'[v{i}][{i}:a]' for i in range(n))
    if out_h is not None:
        lines.append(f'    {concat_inputs}concat=n={n}:v=1:a=1[vc][a];')
        lines.append(f'    [vc]scale=-2:{out_h}[v]')
    else:
        lines.append(f'    {concat_inputs}concat=n={n}:v=1:a=1[v][a]')
    lines.append(
        "  ' -map '[v]' -map '[a]' -movflags +faststart -pix_fmt yuvj420p "
        f'-c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k {output}'
    )
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        epilog=epilog,
        description='Read video file names from stdin and print an ffmpeg command that concatenates them.',
    )
    parser.add_argument(
        '-o', '--output', default='out.mkv',
        help='output file name',
    )
    parser.add_argument(
        '--resolution', type=parse_resolution, default=None,
        help='downscale output height (e.g. 320 or 320p).',
    )
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')

    files = [pathlib.Path(line) for line in sys.stdin.read().splitlines() if line.strip()]
    if not files:
        logger.error('no input files on stdin')
        return 1
    logger.info(f'read {len(files)} file(s) from stdin')

    probes: list[ProbeResult] = []
    for i, f in enumerate(files, start=1):
        probes.append(probe(f, progress=f'[{i}/{len(files)}] '))
    for p, f in zip(probes, files):
        logger.info(f'  {p.width}x{p.height}\tfps={p.fps}\tsr={p.sample_rate}\t{f}')

    fps_set = {p.fps for p in probes}
    if len(fps_set) > 1:
        logger.error(f'frame rate mismatch: {sorted(fps_set)}')
        return 1
    sr_set = {p.sample_rate for p in probes}
    if len(sr_set) > 1:
        logger.error(f'audio sample rate mismatch: {sorted(sr_set)}')
        return 1

    resolutions = [(p.width, p.height) for p in probes]
    if len(set(resolutions)) == 1:
        cmd = build_concat_demuxer_cmd(files, args.resolution, args.output)
    else:
        max_w = max(w for w, _ in resolutions)
        max_h = max(h for _, h in resolutions)
        logger.info(f'target: {max_w}x{max_h}')
        cmd = build_filter_complex_cmd(files, max_w, max_h, args.resolution, args.output)

    print(cmd)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
