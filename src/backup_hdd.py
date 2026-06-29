#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

epilog = r'''
Usage:
  backup_hdd.py backup_hdd    [-n] [-c] [--rsync_dry_run] [--bwlimit=RATE] [--ops=OPS] [-h | --help] {e14|e15}
  backup_hdd.py list_diff     [-n] [-c] [--ops=OPS] [-h | --help] {e14|e15}
  backup_hdd.py list_included [-n] [--ops=OPS] [-h | --help] {e14|e15}
  backup_hdd.py list_excluded [-n] [-h | --help] {e14|e15}
Examples:
  z_backup_hdd backup_hdd -n e15 | pr
  # sudo.ws: file:///home/wsh/d/arc/sudo-pipe-time-ctrlc.md
                         z_backup_hdd backup_hdd --rsync_dry_run e15 | pr  # ^C
                         z_backup_hdd backup_hdd                 e15 |& tee -a ~/gen/log/backup.$(date +%F).log | pr  # ^C
                    sudo z_backup_hdd backup_hdd --rsync_dry_run e15 | pr  # ^C
  time sudo.ws /bin/time z_backup_hdd backup_hdd    e15 |& tee -a ~/gen/log/backup.$(date +%F).log | pr
  # list what would change vs the backup (rsync -ni itemize-changes, dry-run); needs sudo to traverse the whole tree:
  time sudo.ws /bin/time z_backup_hdd list_diff     e15 |& tee -a ~/gen/log/backup_diff.$(date +%F).log | pr  # rsync itemize-changes lines (incl. *deleting)
  # list the files that would be backed up (rsync --list-only, dry-run); needs sudo to traverse the whole tree:
  time sudo.ws /bin/time z_backup_hdd list_included e15 |& tee -a ~/gen/log/backup_list.$(date +%F).log | pr  # rsync --list-only lines for each backed-up entry
  # list files excluded by op2 (the full backup: EXCLUDES / EXCLUDES_GENERIC); needs sudo to traverse the whole tree:
  time sudo.ws /bin/time z_backup_hdd list_excluded e15 |& tee -a ~/gen/log/backup_excluded.$(date +%F).log | pr  # absolute full path of each excluded entry (dirs get a trailing slash)
'''[1:]

import argparse
import dataclasses
import logging
import os
import pathlib
import shlex
import socket
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


class AppError(Exception):
    pass


IMPORTANT_FILES = [
    '/home/',
    '/home/wsh/',
    '/home/wsh/.git/***',
    '/home/wsh/d/***',
    '/home/wsh/docn/***',
]

# deleted with --delete-excluded
EXCLUDES_GENERIC = [
    '.next/',
    'buildDir/',  # CLion meson
    'cmake-build-*/',  # CLion cmake-build-debug/ cmake-build-release/ cmake-build-debug-coverage/
    'node_modules/',
]

# TODO: /var/lib/libvirt/ 必要

# deleted with --delete-excluded
EXCLUDES = [
    '/boot/',
    '/cdrom/', '/dev/', '/media/', '/mnt/', '/proc/', '/run/', '/snap/', '/sys/', '/tmp/',
    '/home/*/.android/',
    '/home/*/.buildroot-ccache/',
    '/home/*/.cache/',
    '/home/*/.cargo/registry/',
    '/home/*/.ccache/',
    '/home/*/.codex/tmp/arg0/',
    '/home/*/.config/code-oss-dev/',
    '/home/*/.config/Code/',
    '/home/*/.config/google-chrome/',
    '/home/*/.config/JetBrains/',  # home/wsh/.config/JetBrains/WebStorm2024.2/settingsSync/.git/objects/ce/534c63d654de85acee9af5cfbac56d0067d802
    '/home/*/.dropbox/',
    '/home/*/.gradle/',
    '/home/*/.java/',
    '/home/*/.local/share/JetBrains/',
    '/home/*/.local/share/nvm/',
    '/home/*/.local/share/pnpm/',
    '/home/*/.npm-global/',
    '/home/*/.npm/',
    '/home/*/.nvm/',
    '/home/*/.pyenv/',
    '/home/*/.rbenv/',
    '/home/*/.rustup/',
    '/home/*/.ssh/cm/',
    '/home/*/.vscode-server/',
    '/home/*/.vscode/extensions/',
    '/home/*/Android/',
    '/home/*/gen/log/',
    '/home/*/gen/logs/',
    '/home/*/go/pkg/',
    '/home/*/opt_/',
    '/home/*/qc/*/build/',
    '/home/*/snap/firefox/common/.cache/',
    '/home/linuxbrew/',
    '/mnts/',
    '/opt/',
    '/snap/',
    '/usr/',
    '/var/cache/',
    '/var/crash/',
    '/var/lib/',
    '/var/log/',
    '/var/snap/',
    '/var/tmp/',
]

# --list-only でファイルをリストできる
# /home/wsh/qc/netbsd/bin/sh/*** はこう指定する:
# rsync -va                 --include=/home/ --include=/home/wsh/ --include=/home/wsh/qc/ --include=/home/wsh/qc/netbsd/ --include=/home/wsh/qc/netbsd/bin/ --include=/home/wsh/qc/netbsd/bin/sh/"***" --exclude="*" -h --progress --list-only /
# rsync -va --exclude="*.h" --include=/home/ --include=/home/wsh/ --include=/home/wsh/qc/ --include=/home/wsh/qc/netbsd/ --include=/home/wsh/qc/netbsd/bin/ --include=/home/wsh/qc/netbsd/bin/sh/"***" --exclude="*" -h --progress --list-only /

@dataclasses.dataclass(frozen=True)
class BackupCommand:
    args: list[str]
    target: str
    required_path: str
    required_path_message: str


def parse_ops(value: str) -> tuple[int, ...]:
    ops: list[int] = []
    for raw_op in value.split(','):
        try:
            op = int(raw_op)
        except ValueError as e:
            raise argparse.ArgumentTypeError(f'expected comma-separated operation numbers 1,2: {value!r}') from e
        if op not in {1, 2}:
            raise argparse.ArgumentTypeError(f'operation must be 1 or 2: {op}')
        if op in ops:
            raise argparse.ArgumentTypeError(f'duplicate operation: {op}')
        ops.append(op)
    if not ops:
        raise argparse.ArgumentTypeError('expected at least one operation')
    return tuple(ops)


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('backup_hdd', formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparser.set_defaults(func=backup_hdd)
    subparser.add_argument('-n', '--dry_run', action='store_true', help='print commands without executing them')
    subparser.add_argument('--force-dry-run', action='store_true', help='continue dry-run command printing even when prechecks fail')
    subparser.add_argument('-c', '--checksum', action='store_true', help='use rsync checksum comparison with xxh3; implies --rsync_dry_run')
    subparser.add_argument('--rsync_dry_run', action='store_true', help="add rsync's own --dry-run (rsync runs but transfers nothing)")
    subparser.add_argument('--bwlimit', metavar='RATE', help='limit rsync transfer rate, e.g. 100M')
    subparser.add_argument('--ops', type=parse_ops, default=(1, 2), metavar='OPS', help='comma-separated rsync operation numbers to run: 1,2')
    subparser.add_argument('target', choices=['e14', 'e15'])

    subparser = subparsers.add_parser('list_diff', formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparser.set_defaults(func=list_diff)
    subparser.add_argument('-n', '--dry_run', action='store_true', help='print the rsync commands without executing them')
    subparser.add_argument('--force-dry-run', action='store_true', help='continue dry-run command printing even when prechecks fail')
    subparser.add_argument('-c', '--checksum', action='store_true', help='compare by xxh3 checksum instead of size/mtime')
    subparser.add_argument('--ops', type=parse_ops, default=(1, 2), metavar='OPS', help='comma-separated rsync operation numbers to diff: 1,2')
    subparser.add_argument('target', choices=['e14', 'e15'])

    subparser = subparsers.add_parser('list_included', formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparser.set_defaults(func=list_included)
    subparser.add_argument('-n', '--dry_run', action='store_true', help='print the rsync commands without executing them')
    subparser.add_argument('--ops', type=parse_ops, default=(1, 2), metavar='OPS', help='comma-separated rsync operation numbers to list: 1,2')
    subparser.add_argument('target', choices=['e14', 'e15'])

    subparser = subparsers.add_parser('list_excluded', formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparser.set_defaults(func=list_excluded)
    subparser.add_argument('-n', '--dry_run', action='store_true', help='print the rsync command without executing it')
    subparser.add_argument('target', choices=['e14', 'e15'])

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    try:
        return args.func(args)
    except AppError as e:
        logger.error(str(e))
        return 1


def backup_hdd(args: argparse.Namespace) -> int:
    if args.force_dry_run and not args.dry_run:
        raise AppError('--force-dry-run requires --dry-run')

    hostname = socket.gethostname()
    commands = build_backup_commands(
        hostname=hostname,
        target=args.target,
        checksum=args.checksum,
        rsync_dry_run=args.rsync_dry_run,
        bwlimit=args.bwlimit,
        ops=args.ops,
    )

    for command in commands:
        require_path(
            command.required_path,
            command.required_path_message,
            dry_run=args.dry_run,
            force_dry_run=args.force_dry_run,
        )
        run_command(command.args, dry_run=args.dry_run)
    return 0


def list_diff(args: argparse.Namespace) -> int:
    # Itemized diff between source and the backup HDD: the same rsync ops as
    # backup_hdd, but forced to rsync --dry-run with -i so nothing is written and
    # each would-be change is printed as an itemize-changes line (incl. *deleting).
    if args.force_dry_run and not args.dry_run:
        raise AppError('--force-dry-run requires --dry-run')

    hostname = socket.gethostname()
    commands = build_backup_commands(
        hostname=hostname,
        target=args.target,
        checksum=args.checksum,
        rsync_dry_run=True,
        bwlimit=None,
        ops=args.ops,
        itemize=True,
    )

    for command in commands:
        require_path(
            command.required_path,
            command.required_path_message,
            dry_run=args.dry_run,
            force_dry_run=args.force_dry_run,
        )
        run_stdout_command(command.args, dry_run=args.dry_run)
    return 0


def list_included(args: argparse.Namespace) -> int:
    # List the files that would be backed up: the same rsync ops as backup_hdd, but
    # with rsync --list-only (and --dry-run), so each source entry that passes the
    # op's filter rules is printed and nothing is written. --list-only ignores the
    # destination, so the backup HDD need not be mounted (no require_path precheck).
    hostname = socket.gethostname()
    commands = build_backup_commands(
        hostname=hostname,
        target=args.target,
        checksum=False,
        rsync_dry_run=True,
        bwlimit=None,
        ops=args.ops,
        list_only=True,
    )

    for command in commands:
        run_stdout_command(command.args, dry_run=args.dry_run)
    return 0


def build_backup_commands(
    *,
    hostname: str,
    target: str,
    checksum: bool,
    rsync_dry_run: bool,
    bwlimit: str | None,
    ops: tuple[int, ...],
    itemize: bool = False,
    list_only: bool = False,
) -> list[BackupCommand]:
    hostname_target = f'{hostname}.{target}'
    match hostname_target:
        case 'wsh24b.e14' | 'wsh24b.e15':
            # / -> /mnts/{target}/r1/r2/w24br/
            def ops_commands(*, target_r: str, source: str) -> list[BackupCommand]:
                commands_by_op = {
                    1: rsync_cmd(target=target, target_r=target_r, checksum=checksum, rsync_dry_run=rsync_dry_run, bwlimit=bwlimit, source=source, itemize=itemize, list_only=list_only, rsync_opts=['--delete', *exclude_opts(EXCLUDES_GENERIC), *include_opts(IMPORTANT_FILES), '--exclude=*']),
                    2: rsync_cmd(target=target, target_r=target_r, checksum=checksum, rsync_dry_run=rsync_dry_run, bwlimit=bwlimit, source=source, itemize=itemize, list_only=list_only, rsync_opts=['--delete', '--delete-excluded', *exclude_opts(EXCLUDES), *exclude_opts(EXCLUDES_GENERIC)]),
                }
                return [commands_by_op[op] for op in ops]

            target_r = f'{target}/r1/r2/w24br'
            logger.info(f'{hostname} / -> {target_r}/')
            return ops_commands(target_r=target_r, source='/')
        case _:
            raise AppError(f'unknown hostname.target: {hostname_target}')


def list_excluded(args: argparse.Namespace) -> int:
    hostname = socket.gethostname()
    commands = build_list_excluded_commands(hostname=hostname, target=args.target)
    for command in commands:
        run_list_command(command, dry_run=args.dry_run)
    return 0


def build_list_excluded_commands(*, hostname: str, target: str) -> list[str]:
    # List the real on-disk files dropped by op2 (the full backup), mirroring
    # build_backup_commands' sources and op2's filter rules:
    #   op2: full tree minus EXCLUDES / EXCLUDES_GENERIC
    # The --delete / --delete-excluded flags are dropped (receiver-side; meaningless
    # for a listing). op1 is not listed (it includes only IMPORTANT_FILES, so its
    # exclude set is "almost everything" -- not useful for auditing).
    #
    # `rsync -n --dry-run --list-only --debug=FILTER` per source, reusing op2's filter
    # rules. rsync prints `[sender] hiding <file|directory> <path> because of pattern
    # <pat>` for each excluded path (it does not descend into an excluded dir, so this
    # is per-excluded-entry, not per leaf file). Output: the absolute full path of each
    # excluded entry (source-prefixed, pattern stripped); directories get a trailing
    # slash (e.g. /sys/).
    hostname_target = f'{hostname}.{target}'
    match hostname_target:
        case 'wsh24b.e14' | 'wsh24b.e15':
            def full_cmd(*, source: str) -> str:
                op_filter = [*exclude_opts(EXCLUDES), *exclude_opts(EXCLUDES_GENERIC)]
                args = ['rsync', '-n', '--dry-run', '-aAHSX', '--list-only', '--debug=FILTER', *op_filter, source]
                # --debug=FILTER may write to stdout or stderr; merge then keep only
                # the `hiding` lines (each carries the matching pattern).
                # --line-buffered / sed -u: stream each match as rsync emits it
                # (grep/sed block-buffer when their stdout is a pipe, which delays
                # output for the whole tree scan).
                hiding = f"{shlex.join(args)} 2>&1 | grep -F --line-buffered 'hiding '"
                # strip the `[sender] hiding <file|directory> ` prefix and the
                # ` because of pattern ...` suffix, appending a trailing slash for a
                # directory; then prefix the source so each entry is an absolute path.
                strip = (
                    r"sed -u -E 's#^.*hiding directory (.*) because of pattern .*#\1/#;"
                    r" t; s#^.*hiding file (.*) because of pattern .*#\1#'"
                )
                prefix = f"sed -u {shlex.quote(f's#^#{source}#')}"
                return f"{hiding} | {strip} | {prefix} || true"

            logger.info(f'{hostname} list excluded: /')
            return [full_cmd(source='/')]
        case _:
            raise AppError(f'unknown hostname.target: {hostname_target}')


def run_list_command(runnable: str, *, dry_run: bool) -> None:
    if dry_run:
        print(runnable)
        return
    logger.info(runnable)
    subprocess.run(runnable, shell=True, executable='/bin/bash', check=True)


def run_stdout_command(args: list[str], *, dry_run: bool) -> None:
    # Print to stdout (pipe to `pr`); unlike backup, no tee to the backup log.
    runnable = shlex.join(args)
    if dry_run:
        print(runnable)
        return
    logger.info(runnable)
    subprocess.run(args, check=True)


def require_path(path: str, message: str, *, dry_run: bool, force_dry_run: bool) -> None:
    if not pathlib.Path(path).exists():
        if dry_run and force_dry_run:
            logger.warning(f'{message} (continuing because --force-dry-run was specified)')
            return
        raise AppError(f'{message} (use --force-dry-run to print commands anyway)')
    logger.debug(f'required path exists: {path}')


def exclude_opts(paths: list[str]) -> list[str]:
    return [f'--exclude={path}' for path in paths]


def include_opts(paths: list[str]) -> list[str]:
    return [f'--include={path}' for path in paths]


def rsync_cmd(*, target: str, target_r: str, checksum: bool, rsync_dry_run: bool, bwlimit: str | None, rsync_opts: list[str], source: str = '/', required_subpath: str = 'home/wsh/', itemize: bool = False, list_only: bool = False) -> BackupCommand:
    # -c/--checksum implies --rsync_dry_run (checksum_opts already carries --dry-run)
    checksum_opts = ['-c', '--cc=xxh3', '-n', '--dry-run'] if checksum else []
    dry_run_opts = ['-n', '--dry-run'] if rsync_dry_run and not checksum else []
    bwlimit_opts = [f'--bwlimit={bwlimit}'] if bwlimit else []
    # itemize (-i) prints one change line per entry for a diff listing; --list-only
    # prints every source entry passing the filters. For either, drop the human
    # progress output (-hPv / --info=progress2) so only the listing lines show.
    itemize_opts = ['-i'] if itemize else []
    list_only_opts = ['--list-only'] if list_only else []
    progress_opts = [] if (itemize or list_only) else ['-hPv', '--info=progress2']
    required_path = f'/mnts/{target_r}/{required_subpath}'
    return BackupCommand(
        args=[
            'rsync',
            '-aAHSX',
            '-@-1',  # --modify-window=-1: compare mtimes with nanosecond precision
            *itemize_opts,
            *list_only_opts,
            *progress_opts,
            *checksum_opts,
            *dry_run_opts,
            *bwlimit_opts,
            *rsync_opts,
            source,
            f'/mnts/{target_r}/',
        ],
        target=target,
        required_path=required_path,
        required_path_message=f'target:{target} but {required_path} not found',
    )


def run_command(args: list[str], *, dry_run: bool) -> None:
    command_display = shlex.join(args)
    target = args_target(args)
    runnable = f'PS4=\'+ \\e[32m\'\'cmd: \\e[0m\'; (set -x; time /bin/time {command_display})'
    if dry_run:
        print(runnable)
        return
    logger.info(runnable)
    subprocess.run(runnable, shell=True, executable='/bin/bash', check=True)


def args_target(args: list[str]) -> str:
    destination = args[-1]
    if destination.startswith('/mnts/') and destination.endswith('/'):
        return destination.removeprefix('/mnts/').split('/', maxsplit=1)[0]
    raise AppError(f'failed to parse target from command: {shlex.join(args)}')


if __name__ == '__main__':
    raise SystemExit(main())
