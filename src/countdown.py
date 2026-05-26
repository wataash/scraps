#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
python countdown.py 5
python countdown.py '3hour 4min 5sec'
'''[1:]

import argparse
import logging
import re
import shlex
import subprocess
import sys
import time


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


def parse_duration(value: str) -> int:
    if re.fullmatch(r'\d+', value):
        return int(value)
    cmd = ['date', '-d', f'19700101 {value}', '-u', '+%s']
    logger.info(f'$ {shlex.join(cmd)}')
    secs = int(subprocess.check_output(cmd, text=True).strip())
    if secs < 0:
        raise argparse.ArgumentTypeError(f'value: {value} < 0 (cmd: {shlex.join(cmd)})')
    return secs


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('duration', type=parse_duration, help='e.g. 300, 3hour 4min 5sec (GNU date(1) style)')
    args = parser.parse_args()
    logger.debug(f'{args=}')
    return countdown(args)


def countdown(args: argparse.Namespace) -> int:
    duration = args.duration
    some_outputted = False
    while duration > 0:
        if duration == 1:
            sys.stdout.write('1')
        else:
            sys.stdout.write(f'{duration} ')
        sys.stdout.flush()
        some_outputted = True
        duration -= 1
        time.sleep(1)
    if some_outputted:
        sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
