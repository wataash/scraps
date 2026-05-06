#!/home/wsh/opt_/pyvenv2/bin/python
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

epilog = r'''
Usage:
  backup_hdd.py backup_hdd [-n] [-c] [--bwlimit=RATE] [--ops=OPS] [-h | --help] {e14|e15}
Examples:
       backup_hdd.py backup_hdd -n --ops=1,2 --bwlimit=100M e14 | bat -pp -l log
       backup_hdd.py backup_hdd -n --ops=1,2 --bwlimit=100M e15 | bat -pp -l log
  sudo -v
  sudo backup_hdd.py backup_hdd    --ops=1,2 --bwlimit=100M e14 | bat -pp -l log
  sudo backup_hdd.py backup_hdd    --ops=1,2 --bwlimit=100M e15 | bat -pp -l log
  # logs: ~/logs/backup.${target}.$(date +%F).log
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


class AppError(Exception):
    pass


IMPORTANT_FILES = [
    '/home/',
    '/home/wsh/',
    '/home/wsh/.git/***',
    '/home/wsh/d/***',
    '/home/wsh/doc/***',
    '/home/wsh/docn/***',
]

# deleted with --delete-excluded
EXCLUDES_GENERIC = [
    '.next/',
    'buildDir/',  # CLion meson
    'cmake-build-*/',  # CLion cmake-build-debug/ cmake-build-release/ cmake-build-debug-coverage/
    'node_modules/',
]

# deleted with --delete-excluded
EXCLUDES = [
    '/boot/',
    '/cdrom/', '/dev/', '/media/', '/mnt/', '/proc/', '/run/', '/snap/', '/sys/', '/tmp/',
    '/home/*/.android/',
    '/home/*/.buildroot-ccache/',
    '/home/*/.cache/',
    '/home/*/.cargo/registry/',
    '/home/*/.ccache/',
    '/home/*/.config/code-oss-dev/',
    '/home/*/.config/Code/',
    '/home/*/.config/google-chrome/',
    '/home/*/.config/JetBrains/',  # home/wsh/.config/JetBrains/WebStorm2024.2/settingsSync/.git/objects/ce/534c63d654de85acee9af5cfbac56d0067d802
    '/home/*/.gradle/',
    '/home/*/.gradle/caches/',
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
    '/home/*/go/pkg/',
    '/home/*/logs_archive/',
    '/home/*/logs/',
    '/home/*/mnt/',
    '/home/*/opt_/',
    '/home/*/opt/',
    '/home/*/qc/*/build/',
    '/home/*/snap/firefox/common/.cache/',
    '/home/linuxbrew/',
    '/mnt.*/',
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
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('backup_hdd', formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparser.set_defaults(func=backup_hdd)
    subparser.add_argument('-n', '--dry_run', action='store_true', help='print commands without executing them')
    subparser.add_argument('--force-dry-run', action='store_true', help='continue dry-run command printing even when prechecks fail')
    subparser.add_argument('-c', '--checksum', action='store_true', help='use rsync checksum comparison with xxh3 in dry-run mode')
    subparser.add_argument('--bwlimit', metavar='RATE', help='limit rsync transfer rate, e.g. 100M')
    subparser.add_argument('--ops', type=parse_ops, default=(1, 2), metavar='OPS', help='comma-separated rsync operation numbers to run: 1,2')
    subparser.add_argument('target', choices=['e14', 'e15'])

    args = parser.parse_args()
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


def build_backup_commands(
    *,
    hostname: str,
    target: str,
    checksum: bool,
    bwlimit: str | None,
    ops: tuple[int, ...],
) -> list[BackupCommand]:
    hostname_target = f'{hostname}.{target}'
    match hostname_target:
        case 'wsh24.e14' | 'wsh24.e15':
            target_r = f'{target}/w24r'
            logger.info(f'{hostname} -> {target_r}/')
            # no -S  : du -h /mnt.e14/w24r/home/wsh/20240907_x24_sda.dd  # 239G	/mnt.e14/w24r/home/wsh/20240907_x24_sda.dd
            # -S     : du -h /mnt.e14/w24r/home/wsh/20240907_x24_sda.dd  # 239G	/mnt.e14/w24r/home/wsh/20240907_x24_sda.dd
            # rm, -S : du -h /mnt.e14/w24r/home/wsh/20240907_x24_sda.dd  # 33G	/mnt.e14/w24r/home/wsh/20240907_x24_sda.dd
            #          du -h ~/20240907_x24_sda.dd                       # 22G	/home/wsh/20240907_x24_sda.dd  # zfs の方が sparse file の効率いいのかな
            commands_by_op = {
                1: rsync_cmd(target=target, target_r=target_r, checksum=checksum, bwlimit=bwlimit, rsync_opts=['--delete', *exclude_opts(EXCLUDES_GENERIC), *include_opts(IMPORTANT_FILES), '--exclude=*']),
                2: rsync_cmd(target=target, target_r=target_r, checksum=checksum, bwlimit=bwlimit, rsync_opts=['--delete', '--delete-excluded', *exclude_opts(EXCLUDES), *exclude_opts(EXCLUDES_GENERIC)]),
            }
            return [commands_by_op[op] for op in ops]
        case _:
            raise AppError(f'unknown hostname.target: {hostname_target}')


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


def rsync_cmd(*, target: str, target_r: str, checksum: bool, bwlimit: str | None, rsync_opts: list[str]) -> BackupCommand:
    checksum_opts = ['-c', '--cc=xxh3', '--dry-run'] if checksum else []
    bwlimit_opts = [f'--bwlimit={bwlimit}'] if bwlimit else []
    required_path = f'/mnt.{target_r}/home/wsh/'
    return BackupCommand(
        args=[
            'rsync',
            '-ahPSv',
            *checksum_opts,
            *bwlimit_opts,
            *rsync_opts,
            '/',
            f'/mnt.{target_r}/',
        ],
        target=target,
        required_path=required_path,
        required_path_message=f'target:{target} but {required_path} not found',
    )


def run_command(args: list[str], *, dry_run: bool) -> None:
    command_display = shlex.join(args)
    target = args_target(args)
    runnable = f'PS4=\'+ \\e[32m\'\'cmd: \\e[0m\'; (set -x; time /bin/time {command_display}) |& sudo -u wsh -- tee -a "/home/wsh/logs/backup.{target}.$(date +%F).log"'
    if dry_run:
        print(runnable)
        return
    logger.info(runnable)
    subprocess.run(runnable, shell=True, executable='/bin/bash', check=True)


def args_target(args: list[str]) -> str:
    destination = args[-1]
    if destination.startswith('/mnt.') and destination.endswith('/'):
        return destination.removeprefix('/mnt.').split('/', maxsplit=1)[0]
    raise AppError(f'failed to parse target from command: {shlex.join(args)}')


if __name__ == '__main__':
    raise SystemExit(main())
