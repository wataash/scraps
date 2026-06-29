#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r"""
python claude_rate_limits.py -h
echo '{"rate_limits":{"five_hour":{"used_percentage":1,"resets_at":0}}}' | python claude_rate_limits.py
"""[1:]

import argparse
import json
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


# (payload key, label). "Current week (Fable)" from /usage is intentionally
# absent: the statusLine payload only carries five_hour + seven_day, so it
# can't be rendered here.
LIMITS = [
    ("five_hour", "session"),
    ("seven_day", "week"),
]


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument("-q", "--quiet", action="count", default=0,
                        help="decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error")
    parser.add_argument("-w", "--width", type=int, default=10, help="progress bar width in chars")
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f"{args=}")

    try:
        # bytes in, so decoding is UTF-8 regardless of locale
        payload = json.loads(sys.stdin.buffer.read())
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"stdin is not JSON: {e}")
        return 1
    out = format_limits(payload, width=args.width)
    if out:
        print(out)
    return 0


def bar(pct: float, width: int = 10) -> str:
    """A filled/empty block bar for a 0-100 percentage.

    >>> bar(0)
    '░░░░░░░░░░'
    >>> bar(100)
    '██████████'
    >>> bar(25, width=8)
    '██░░░░░░'
    """
    pct = max(0.0, min(100.0, pct))
    fill = round(pct / 100 * width)
    return "█" * fill + "░" * (width - fill)


def format_limits(payload: dict, width: int = 10) -> str:
    """Render available rate-limit bars from a statusLine payload, on one line.

    Returns "" when the payload carries no ``rate_limits`` (older Claude Code).

    >>> p = {"rate_limits": {
    ...   "five_hour": {"used_percentage": 7, "resets_at": 0},
    ...   "seven_day": {"used_percentage": 21, "resets_at": 0}}}
    >>> format_limits(p)
    'session [█░░░░░░░░░] 7%  week [██░░░░░░░░] 21%'

    A limit whose used_percentage is null/non-numeric is skipped rather than
    crashing (which would lose the whole line — the caller swallows failures):

    >>> format_limits({"rate_limits": {"five_hour": {"used_percentage": None},
    ...                                "seven_day": {"used_percentage": 21}}})
    'week [██░░░░░░░░] 21%'
    """
    rl = payload.get("rate_limits") or {}
    parts = []
    for key, label in LIMITS:
        d = rl.get(key)
        if not d:
            continue
        pct = d.get("used_percentage", 0)
        if not isinstance(pct, (int, float)):
            continue
        parts.append(f"{label} [{bar(pct, width)}] {pct:.0f}%")
    return "  ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
