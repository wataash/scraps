#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
ls *.mp4 | video_timeline.py
printf '%s\n' a.mp4 b.mp4 c.mp4 | video_timeline.py
video_timeline.py -n < list.txt
'''[1:]

import argparse
import logging
import shlex
import subprocess
import sys


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


def fmt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds - h * 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f'{h}:{m:02d}:{s:06.3f}'


def fmt_mmss(seconds: float) -> str:
    total = int(seconds)
    return f'{total // 60}:{total % 60:02d}'


def probe_duration(path: str) -> float:
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=nw=1:nk=1', path]
    logger.debug(f'$ {shlex.join(cmd)}')
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        epilog=epilog,
        description='Read video filenames from stdin (one per line) and print cumulative timeline.',
    )
    parser.add_argument('-n', '--dry_run', action='store_true',
                        help='print ffprobe commands instead of executing')
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')

    files = [line.strip() for line in sys.stdin if line.strip()]
    if not files:
        logger.error('no filenames given on stdin')
        return 1

    if args.dry_run:
        for f in files:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                   '-of', 'default=nw=1:nk=1', f]
            print(shlex.join(cmd))
        return 0

    t = 0.0
    for f in files:
        d = probe_duration(f)
        start, end = t, t + d
        logger.info(f'{fmt(start)} - {fmt(end)} ({fmt(d)}) {f}')
        print(f'{fmt_mmss(start)} {f}')
        t = end
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
