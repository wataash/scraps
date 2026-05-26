#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
br.py install jq
br.py install --min_age_hours 24 jq
br.py -n install jq
br.py -n upgrade
br.py upgrade --min_age_hours 24
'''[1:]

import argparse
import datetime
import json
import logging
import shlex
import subprocess
import sys
import urllib.error
import urllib.request


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


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-n', '--dry_run', action='store_true', help='print commands instead of executing')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('install', formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help='install a formula only if its latest version has aged enough')
    subparser.set_defaults(func=install)
    subparser.add_argument('pkg', help='formula name (casks are not supported)')
    subparser.add_argument('--min_age_hours', type=float, default=24.0 * 7,
                           help='minimum age (hours) since the formula was last updated on homebrew-core')

    subparser = subparsers.add_parser('upgrade', formatter_class=ArgumentDefaultsRawTextHelpFormatter,
                                      help='upgrade outdated formulae whose latest version has aged enough')
    subparser.set_defaults(func=upgrade)
    subparser.add_argument('--min_age_hours', type=float, default=24.0 * 7,
                           help='minimum age (hours) since the formula was last updated on homebrew-core')

    args = parser.parse_args()
    logger.debug(f'{args=}')
    return args.func(args)


def _http_get_json(url: str) -> object:
    logger.debug(f'GET {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'br.py'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _formula_source_path(pkg: str) -> str:
    try:
        data = _http_get_json(f'https://formulae.brew.sh/api/formula/{pkg}.json')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SystemExit(f'error: formula not found: {pkg}')
        raise
    assert isinstance(data, dict)
    path = data.get('ruby_source_path')
    if not isinstance(path, str):
        raise SystemExit(f'error: ruby_source_path missing for {pkg}')
    return path


def _last_commit_datetime(path: str) -> datetime.datetime:
    url = f'https://api.github.com/repos/Homebrew/homebrew-core/commits?path={path}&per_page=1'
    data = _http_get_json(url)
    assert isinstance(data, list)
    if not data:
        raise SystemExit(f'error: no commits found for {path}')
    date_str = data[0]['commit']['committer']['date']
    return datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))


def install(args: argparse.Namespace) -> int:
    pkg: str = args.pkg
    source_path = _formula_source_path(pkg)
    last_commit = _last_commit_datetime(source_path)
    now = datetime.datetime.now(datetime.timezone.utc)
    age = now - last_commit
    age_hours = age.total_seconds() / 3600
    min_hours: float = args.min_age_hours
    logger.info(f'{pkg}: last updated {last_commit.isoformat()} ({age_hours:.2f}h ago); threshold {min_hours}h')
    if age_hours < min_hours:
        logger.error(f'refusing to install {pkg}: age {age_hours:.2f}h < {min_hours}h')
        return 1
    cmd = ['brew', 'install', pkg]
    if args.dry_run:
        print(shlex.join(cmd))
        return 0
    logger.info(f'$ {shlex.join(cmd)}')
    return subprocess.call(cmd)


def upgrade(args: argparse.Namespace) -> int:
    min_hours: float = args.min_age_hours
    cmd = ['brew', 'outdated', '--json=v2', '--formula']
    logger.info(f'$ {shlex.join(cmd)}')
    out = subprocess.check_output(cmd, text=True)
    outdated = json.loads(out).get('formulae', [])
    if not outdated:
        logger.info('no outdated formulae')
        return 0

    now = datetime.datetime.now(datetime.timezone.utc)
    ready: list[str] = []
    skipped: list[tuple[str, float]] = []
    for entry in outdated:
        pkg = entry['name']
        if entry.get('pinned'):
            logger.info(f'{pkg}: pinned, skipping')
            continue
        source_path = _formula_source_path(pkg)
        last_commit = _last_commit_datetime(source_path)
        age_hours = (now - last_commit).total_seconds() / 3600
        if age_hours >= min_hours:
            logger.info(f'{pkg}: age {age_hours:.2f}h >= {min_hours}h, eligible')
            ready.append(pkg)
        else:
            logger.info(f'{pkg}: age {age_hours:.2f}h < {min_hours}h, skipping')
            skipped.append((pkg, age_hours))

    if not ready:
        logger.info('no formulae are old enough to upgrade')
        return 0

    cmd = ['brew', 'upgrade', '--formula', *ready]
    if args.dry_run:
        print(shlex.join(cmd))
        return 0
    logger.info(f'$ {shlex.join(cmd)}')
    return subprocess.call(cmd)


if __name__ == '__main__':
    raise SystemExit(main())
