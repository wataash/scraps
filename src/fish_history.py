#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
fish_history.py plot
fish_history.py plot --history ~/.local/share/fish/fish_history
fish_history.py plot --output out.png

fish_history.py extract --since '2024-01-01T00:00:00+09:00' -o /tmp/fish_history_recent
fish_history.py extract --history ~/.local/share/fish/fish_history --since '2024-01-01T00:00:00+09:00' -o /tmp/fish_history_recent

fish_history.py merge -o /tmp/merged ~/.local/share/fish/fish_history /tmp/old_fish_history_recent
'''[1:]

import argparse
import datetime
import logging
import pathlib
import re

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
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


_DEFAULT_HISTORY = pathlib.Path('~/.local/share/fish/fish_history').expanduser()


def parse_iso8601(s: str) -> datetime.datetime:
    # datetime.fromisoformat handles timezone offsets only in Python 3.11+
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            raise ValueError(f'timezone required: {s!r}')
        return dt
    except ValueError:
        pass
    # fallback: strip ±HH:MM suffix and reattach as tzinfo
    m = re.match(r'^(.+?)([+-])(\d{2}):(\d{2})$', s)
    if not m:
        raise ValueError(f'cannot parse datetime: {s!r}')
    dt = datetime.datetime.fromisoformat(m.group(1))
    sign = 1 if m.group(2) == '+' else -1
    tz = datetime.timezone(sign * datetime.timedelta(hours=int(m.group(3)), minutes=int(m.group(4))))
    return dt.replace(tzinfo=tz)


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    # -- plot --
    sp_plot = subparsers.add_parser('plot', formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                    help='plot accumulated command count over time')
    sp_plot.set_defaults(func=cmd_plot)
    sp_plot.add_argument('--history', type=pathlib.Path, default=_DEFAULT_HISTORY,
                         help='path to fish_history file')
    sp_plot.add_argument('--output', type=pathlib.Path, default=None,
                         help='save plot to file instead of showing')

    # -- extract --
    sp_ex = subparsers.add_parser('extract', formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                  help='extract entries on or after --since into a new history file')
    sp_ex.set_defaults(func=cmd_extract)
    sp_ex.add_argument('--history', type=pathlib.Path, default=_DEFAULT_HISTORY,
                       help='path to fish_history file')
    sp_ex.add_argument('--since', required=True, metavar='DATETIME',
                       help='ISO 8601 datetime with timezone, e.g. 2024-01-01T00:00:00+09:00')
    sp_ex.add_argument('-o', required=True, type=pathlib.Path, metavar='OUTPUT',
                       help='output file path')

    # -- merge --
    sp_mg = subparsers.add_parser('merge', formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                  help='merge two history files, dedup, and sort by when')
    sp_mg.set_defaults(func=cmd_merge)
    sp_mg.add_argument('files', nargs=2, type=pathlib.Path, metavar=('FILE_A', 'FILE_B'))
    sp_mg.add_argument('-o', required=True, type=pathlib.Path, metavar='OUTPUT',
                       help='output file path')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return args.func(args)


def cmd_plot(args: argparse.Namespace) -> int:
    logger.info(f'reading {args.history}')
    text = args.history.read_text(errors='replace')

    timestamps = [int(m) for m in re.findall(r'^\s+when:\s+(\d+)', text, re.MULTILINE)]
    logger.info(f'{len(timestamps)} commands found')

    dates = [datetime.date.fromtimestamp(ts) for ts in timestamps]
    dates.sort()

    date_min, date_max = dates[0], dates[-1]
    logger.info(f'range: {date_min} – {date_max}')

    day0 = date_min
    n_days = (date_max - day0).days + 1
    counts = np.zeros(n_days, dtype=np.int64)
    for d in dates:
        counts[(d - day0).days] += 1

    cumulative = np.cumsum(counts)
    x = [day0 + datetime.timedelta(days=i) for i in range(n_days)]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(x, cumulative, linewidth=1)
    ax.set_xlabel('Date')
    ax.set_ylabel('Accumulated commands')
    ax.set_title('fish shell: accumulated command count over time')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_minor_locator(mdates.MonthLocator())
    fig.autofmt_xdate()
    ax.grid(True, which='major', alpha=0.4)
    ax.grid(True, which='minor', alpha=0.1)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{int(v):,}'))

    plt.tight_layout()
    if args.output:
        fig.savefig(args.output, dpi=150)
        logger.info(f'saved to {args.output}')
    else:
        plt.show()

    return 0


def parse_entries(path: pathlib.Path, src: int) -> list[dict]:
    text = path.read_text(errors='replace')
    result = []
    for raw in re.split(r'(?=^- cmd:)', text, flags=re.MULTILINE):
        if not raw.strip():
            continue
        cm = re.match(r'^- cmd: (.*)', raw)
        wm = re.search(r'^\s+when:\s+(\d+)', raw, re.MULTILINE)
        if cm and wm:
            result.append({'cmd': cm.group(1).strip(), 'when': int(wm.group(1)), 'raw': raw, 'src': src})
    return result


def cmd_extract(args: argparse.Namespace) -> int:
    since_dt = parse_iso8601(args.since)
    since_ts = since_dt.timestamp()
    logger.info(f'since: {since_dt.isoformat()} (unix {since_ts:.0f})')

    logger.info(f'reading {args.history}')
    text = args.history.read_text(errors='replace')

    # Each entry starts with "- cmd:"; split on that boundary
    # The first split may be empty if the file starts with "- cmd:"
    raw_entries = re.split(r'(?=^- cmd:)', text, flags=re.MULTILINE)

    matched = []
    for entry in raw_entries:
        if not entry.strip():
            continue
        m = re.search(r'^\s+when:\s+(\d+)', entry, re.MULTILINE)
        if m and int(m.group(1)) >= since_ts:
            matched.append(entry)

    logger.info(f'{len(matched)} entries since {since_dt.isoformat()}')

    output = ''.join(matched)
    if output and not output.endswith('\n'):
        output += '\n'

    args.o.write_text(output)
    logger.info(f'written to {args.o}')
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    file_a, file_b = args.files
    logger.info(f'reading {file_a}')
    entries_a = parse_entries(file_a, src=0)
    logger.info(f'reading {file_b}')
    entries_b = parse_entries(file_b, src=1)
    logger.info(f'{len(entries_a)} + {len(entries_b)} entries before dedup')

    # Step 1: (cmd, when) 完全一致 uniq
    seen: set[tuple[str, int]] = set()
    deduped = []
    for e in entries_a + entries_b:
        key = (e['cmd'], e['when'])
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    # Step 2: 同 cmd → max when のみ残す
    cmd_max: dict[str, int] = {}
    for e in deduped:
        cmd_max[e['cmd']] = max(cmd_max.get(e['cmd'], -1), e['when'])
    deduped = [e for e in deduped if e['when'] == cmd_max[e['cmd']]]

    # Step 3+4: (when, src) 昇順ソート
    deduped.sort(key=lambda e: (e['when'], e['src']))
    logger.info(f'{len(deduped)} entries after dedup')

    output = ''.join(e['raw'] for e in deduped)
    if output and not output.endswith('\n'):
        output += '\n'

    args.o.write_text(output)
    logger.info(f'written to {args.o}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
