#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
adb_pull.py diff_dir sdcard/DCIM/Camera/ ./
adb_pull.py diff_dir sdcard/DCIM/Camera/ ./ | sh
'''[1:]

import argparse
import datetime
import logging
import os
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


# Unlikely to appear in a path; used to delimit stat(1) output fields.
SEP = '|'


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('diff_dir', formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help='print "adb pull / chmod / touch" commands for files that are missing locally or whose attributes differ')
    subparser.set_defaults(func=diff_dir)
    subparser.add_argument('remote', help='remote directory on the device, e.g. sdcard/DCIM/Camera/')
    subparser.add_argument('local', help='local destination directory, e.g. ./')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return args.func(args)


def _remote_entries(remote: str) -> list[tuple[str, str, int, str, str]]:
    """Return [(mode, size, mtime_epoch, mtime_human, name), ...] for regular files in the remote dir."""
    # %a octal mode, %s size, %Y mtime epoch (s), %y mtime human (ns), %F file type, %n name.
    # %y contains spaces but never SEP, and name (%n) is last, so SEP-splitting is safe.
    fmt = SEP.join(['%a', '%s', '%Y', '%y', '%F', '%n'])
    # Quote only the directory so the '*' is expanded by the device shell, not stat(1).
    cmd = ['adb', 'shell', f"stat -c '{fmt}' {shlex.quote(remote.rstrip('/'))}/* 2>/dev/null"]
    logger.debug(f'$ {" ".join(cmd)}')
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    entries = []
    for line in out.replace('\r', '').splitlines():
        parts = line.split(SEP, 5)
        if len(parts) != 6:
            continue
        mode, size, epoch, human, ftype, name = parts
        if ftype != 'regular file':
            continue
        entries.append((mode, int(size), int(epoch), human, name))
    return entries


def _remote_mdate(human: str) -> str:
    # '2026-04-21 14:37:17.811573786 +0900' -> '2026-04-21.14:37:17.811573786'
    return human.rsplit(' ', 1)[0].replace(' ', '.', 1)


def _local_mdate(mtime_ns: int) -> str:
    dt = datetime.datetime.fromtimestamp(mtime_ns // 1_000_000_000)
    return dt.strftime('%Y-%m-%d.%H:%M:%S') + f'.{mtime_ns % 1_000_000_000:09d}'


def _remote_frac(human: str) -> str:
    # nanosecond fraction from '2026-04-21 14:37:17.811573786 +0900' -> '811573786'
    timepart = human.split(' ')[1]
    frac = timepart.split('.', 1)[1] if '.' in timepart else '0'
    return frac.ljust(9, '0')[:9]


def _remote_ns(human: str, epoch: int) -> int:
    return epoch * 1_000_000_000 + int(_remote_frac(human))


def diff_dir(args: argparse.Namespace) -> int:
    remote: str = args.remote
    local: str = args.local

    entries = _remote_entries(remote)
    if not entries:
        logger.warning(f'no regular files under {remote!r} (device offline? wrong path?)')

    for mode, size, epoch, human, name in entries:
        base = name.rsplit('/', 1)[-1]
        remote_path = remote.rstrip('/') + '/' + base
        local_path = os.path.join(local, base)
        # Quote every path: the commands are meant to be piped to sh, and names
        # may contain spaces or shell metacharacters.
        q_remote, q_local, q_file = shlex.quote(remote_path), shlex.quote(local), shlex.quote(local_path)
        # 'adb pull -a' restores mode but only second-resolution mtime, so the
        # full nanosecond mtime is reapplied with touch ('@epoch.frac' is exact
        # and timezone-independent). chmod/touch alone fix attribute-only diffs.
        chmod_cmd = f'chmod {mode} {q_file}'
        touch_cmd = f"touch -d '@{epoch}.{_remote_frac(human)}' {q_file}"

        try:
            st = os.stat(local_path)
        except FileNotFoundError:
            print(f'adb pull -a {q_remote} {q_local} && {chmod_cmd} && {touch_cmd}  # new')
            continue

        diffs: list[str] = []
        parts: list[str] = []
        mode_diff = int(mode, 8) != (st.st_mode & 0o777)
        size_diff = size != st.st_size
        mdate_diff = _remote_ns(human, epoch) != st.st_mtime_ns

        if mode_diff:
            diffs.append(f'mode:{mode}:{format(st.st_mode & 0o777, "o")}')
        if size_diff:
            diffs.append(f'size:{size}:{st.st_size}')
        if mdate_diff:
            diffs.append(f'mdate:{_remote_mdate(human)}:{_local_mdate(st.st_mtime_ns)}')

        if size_diff:
            # content changed: re-pull, then reset mode and full nanosecond mtime
            parts = [f'adb pull -a {q_remote} {q_local}', chmod_cmd, touch_cmd]
        else:
            # same content: fix only the attributes that differ, no transfer
            if mode_diff:
                parts.append(chmod_cmd)
            if mdate_diff:
                parts.append(touch_cmd)

        if parts:
            print(f'{" && ".join(parts)}  # {" ".join(diffs)}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
