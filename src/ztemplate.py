#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r"""
python ztemplate.py -h
python ztemplate.py cmd1 -h
"""[1:]

import argparse
import logging
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
        fn = "" if record.funcName == "<module>" else f" {record.funcName}()"
        fmt = f"{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s{c.RESET}"
        return logging.Formatter(fmt=fmt, datefmt="%T").format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument("-q", "--quiet", action="count", default=0,
                        help="decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error")
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    subparser = subparsers.add_parser("cmd1", formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=cmd1)
    group = subparser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pass")
    group.add_argument("--pass_file", type=argparse.FileType("r"))

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f"{args=}")
    return args.func(args)


def cmd1(args: argparse.Namespace) -> int:
    fn1()
    return 0


def test_cmd1():
    args = argparse.Namespace()
    assert cmd1(args) == 0


def fn1():
    """
    >>> fn1()
    'hello'
    """
    return "hello"


if __name__ == "__main__":
    raise SystemExit(main())
