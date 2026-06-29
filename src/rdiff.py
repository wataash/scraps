#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
python rdiff.py src/ dst/
python rdiff.py -ii src/ dst/
python rdiff.py -n src/ dst/
python rdiff.py src1/ src2/ dst/
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


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        epilog=epilog,
        description='Always-dry-run rsync wrapper: rsync -n --dry-run -aAHSX --delete -@-1 -i SRC... DST',
    )
    parser.add_argument('-i', '--itemize', action='count', default=1,
                        help='itemize-changes verbosity; -i (default) or -ii')
    parser.add_argument('-c', '--checksum', action='store_true',
                        help='pass rsync -c (skip based on checksum, not mod-time & size)')
    parser.add_argument('-n', '--dry_run', action='store_true',
                        help='only print the rsync command, do not run it')
    parser.add_argument('paths', nargs='+', metavar='PATH',
                        help='one or more SRC followed by a single DST (rsync semantics)')
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return rdiff(args)


def rdiff(args: argparse.Namespace) -> int:
    if len(args.paths) < 2:
        logger.error('need at least one SRC and one DST')
        return 2

    itemize = '-' + 'i' * min(args.itemize, 2)
    cmd = ['rsync', '-n', '--dry-run', '-aAHSX', '--delete', '-@-1', itemize]
    if args.checksum:
        cmd.append('-c')
    cmd += args.paths

    if args.dry_run:
        print(shlex.join(cmd))
        return 0

    logger.info(shlex.join(cmd))
    return subprocess.run(cmd).returncode


if __name__ == '__main__':
    raise SystemExit(main())
