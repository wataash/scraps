#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
python loadavg_wait.py
python loadavg_wait.py --threshold 0.5 --interval 30
python loadavg_wait.py --field 5
'''[1:]

import argparse
import logging
import sys
import time


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


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    parser.add_argument('--threshold', type=float, default=1.0, help='break once the watched load average drops below this')
    parser.add_argument('--interval', type=float, default=60.0, help='seconds between samples')
    parser.add_argument('--field', type=int, choices=(1, 5, 15), default=1, help='which load average to compare against --threshold (1/5/15 min)')
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return loadavg_wait(args)


def read_loadavg() -> tuple[float, float, float]:
    with open('/proc/loadavg') as f:
        load1, load5, load15 = (float(x) for x in f.read().split()[:3])
    return load1, load5, load15


def loadavg_wait(args: argparse.Namespace) -> int:
    field_index = {1: 0, 5: 1, 15: 2}[args.field]
    print('loadavg 1/5/15:')
    while True:
        loads = read_loadavg()
        now = time.strftime('%F %T')
        print(f'{now} {loads[0]:.2f} {loads[1]:.2f} {loads[2]:.2f}', flush=True)
        if loads[field_index] < args.threshold:
            break
        time.sleep(args.interval)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
