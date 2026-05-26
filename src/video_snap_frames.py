#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import logging
import pathlib
import re
import shlex
import shutil
import subprocess
import typing as t


epilog = r'''
Examples:
  video_snap_frames.py in.webm out/ --crop WIDTH:HEIGHT:X:Y < times.txt
  video_snap_frames.py in.webm out/ --crop WIDTH:HEIGHT:X:Y <<'TIMES'
  frame:0 time=00:00:00.000
  frame:1059 time=00:00:17.650
  TIMES
  video_snap_frames.py in.webm out/ --crop WIDTH:HEIGHT:X:Y --times_file times.txt
  video_snap_frames.py in.webm out/ --crop WIDTH:HEIGHT:X:Y -n < times.txt
'''[1:]


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


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


def shell_join(cmd: list[str]) -> str:
    return shlex.join(cmd)


def run_cmd(cmd: list[str], *, dry_run: bool) -> None:
    rendered = shell_join(cmd)
    if dry_run:
        print(rendered)
        return
    logger.info(rendered)
    subprocess.run(cmd, check=True)


def parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = value.split(':')
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f'invalid crop, expected WIDTH:HEIGHT:X:Y: {value}')
    try:
        width, height, x, y = [int(p) for p in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'invalid crop, expected integer WIDTH:HEIGHT:X:Y: {value}') from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError(f'invalid crop size: {value}')
    if x < 0 or y < 0:
        raise argparse.ArgumentTypeError(f'invalid crop offset: {value}')
    return width, height, x, y


def parse_snap_times(lines: t.Iterable[str]) -> list[str]:
    """Parse timestamps from lines.

    Accepts:
      - ``frame:N time=HH:MM:SS.sss`` (mpv term-status-msg format)
      - plain ``HH:MM:SS.sss`` or ``HH:MM:SS``
    Blank lines and lines starting with ``#`` are ignored.
    """
    times: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.search(r'time=(\d{2}:\d{2}:\d{2}(?:\.\d+)?)', line)
        if m:
            times.append(m.group(1))
            continue
        if re.fullmatch(r'\d{2}:\d{2}:\d{2}(?:\.\d+)?', line):
            times.append(line)
    return times


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('input', type=pathlib.Path, help='input video file readable by ffmpeg')
    parser.add_argument('output', metavar='OUTPUT_DIR', type=pathlib.Path, help='output directory for numbered .webp files')
    parser.add_argument('--crop', required=True, help='crop expression: width:height:x:y')
    parser.add_argument('--times_file', type=argparse.FileType('r'), default='-',
                        metavar='FILE', help='file of timestamps (default: stdin); accepts mpv frame:N time=HH:MM:SS.sss or plain HH:MM:SS.sss lines')
    parser.add_argument('--quality', type=int, default=95, help='WebP quality')
    parser.add_argument('--method', type=int, default=6, help='WebP encoder method')
    parser.add_argument('--digits', type=int, default=3, help='zero-padding width for output filenames')
    parser.add_argument('--clean', action=argparse.BooleanOptionalAction, default=True,
                        help='remove existing output .webp files first')
    parser.add_argument('-n', '--dry_run', action='store_true', help='print commands without executing')

    args = parser.parse_args()
    logger.debug('args=%r', args)

    if not shutil.which('ffmpeg'):
        logger.error('ffmpeg was not found in PATH')
        return 1
    args.input = args.input.expanduser()
    args.output = args.output.expanduser()
    if not args.input.exists():
        logger.error('input does not exist: %s', args.input)
        return 1
    try:
        crop = parse_crop(args.crop)
    except argparse.ArgumentTypeError as exc:
        logger.error('%s', exc)
        return 1

    times = parse_snap_times(args.times_file)
    if not times:
        logger.error('no timestamps found in input')
        return 1

    if not args.dry_run:
        args.output.mkdir(parents=True, exist_ok=True)
        if args.clean:
            for path in args.output.glob('*.webp'):
                path.unlink()

    w, h, x, y = crop
    for i, t in enumerate(times):
        dst = args.output / f'{i + 1:0{args.digits}d}.webp'
        cmd = [
            'ffmpeg', '-hide_banner', '-v', 'error', '-y',
            '-ss', t,
            '-i', str(args.input),
            '-vframes', '1',
            '-vf', f'crop={w}:{h}:{x}:{y}',
            str(dst),
        ]
        run_cmd(cmd, dry_run=args.dry_run)

    if not args.dry_run:
        logger.info('saved %d files in %s', len(times), args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
