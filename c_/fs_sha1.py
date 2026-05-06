#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""
imported by c.py
"""

from typing import Any, Callable, Iterable, Iterator, Literal, NewType
import argparse
import asyncio
import base64
import collections
import contextlib
import dataclasses
import datetime
import difflib
import enum
import fcntl
import fileinput
import functools
import hashlib
import heapq
import inspect
import io
import ipaddress
import itertools
import json
import logging
import os
import pathlib
import pty
import queue
import random
import re
import select
import selectors
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import textwrap
import threading
import time
import traceback
import tty
import types
import typing

import lib
from lib import CLI, logger, MyException

# -----------------------------------------------------------------------------
# command: fs_hash

epilog = r'''
4bdb2e2cfd83dd47 100664 2025-09-10.22:12:42.511661+09:00  23299441890 /home/wsh/Documents/downloaded/WinDev2407Eval.HyperV.zip

head ~/sha/xxh3.txt | sed -E 's/^(\S+) (\S+) (\S+) ( *\S+) (.+)$/1:\1|2:\2|3:\3|4:\4|5:\5/'
head ~/sha/xxh3.txt | sed -E 's/^(\S+) (\S+) (\S+) ( *\S+) (.+)$/\1 \2 \3 \4 \5/'
'''


# noinspection PyPep8Naming
class fs_hash(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        alg: str
        hash_txt: str
        files_txt: str

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('fs_hash', aliases=['fs_sha1'], help='', epilog=epilog, formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--alg', choices=['sha1', 'xxh32', 'xxh64', 'xxh3', 'xxh128'], default='xxh3')
        subparser.add_argument('--hash_txt', required=True)
        subparser.add_argument('--files_txt', required=True)
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'fs_hash.Args') -> None:
        logger.debug(f'{args=}')

        hash_fn = hashlib.sha1
        if args.alg in ['xxh32', 'xxh64', 'xxh3', 'xxh128']:
            import xxhash
            hash_fn = {
                'sha1': hashlib.sha1,
                'xxh32': xxhash.xxh32,
                'xxh64': xxhash.xxh64,
                'xxh3': xxhash.xxh3_64,
                'xxh128': xxhash.xxh3_128,
            }[args.alg]

        files_calced: dict[str, fs_hash.File] = {}

        for line in pathlib.Path(args.files_txt).read_text().splitlines():
            m = re.match(r'^(?P<mode>[\w-]+)\s+(?P<size>[\d,]+)\s+(?P<mdate>\d{4}/\d\d/\d\d \d\d:\d\d:\d\d)\s+(?P<path>.+)$', line)
            if m is None:
                logger.warning(f'{args.files_txt}: discard invalid line: {line}')
                continue
            m.groupdict()
            if m['mode'][0] == 'd':
                logger.debug(f'skip directory: {m['path']=}')
                del line, m
                continue

            path_ = f'/{m['path']}'
            logger.debug(f'{m.groupdict()=} {path_=}')
            file = fs_hash.calc_hash(path_=path_, hash_fn=hash_fn)
            logger.debug(f'{file=}')
            if file is not None:
                files_calced[path_] = file
            del line, m, path_, file

        # assert set(locals().keys()) == {'args', 'hash_fn', 'xxhash', 'files_calced'}, f'{locals().keys()=}'

        files_calced = dict(sorted(files_calced.items()))
        with open(f'{args.hash_txt}.lock', 'w') as f_lock:
            logger.info(f'flock {f_lock.name}')
            fcntl.flock(f_lock, fcntl.LOCK_EX)
            logger.info(f'got flock {f_lock.name}')
            files_from_txt = fs_hash.read_hash_txt(txt_path=args.hash_txt)
            files_from_txt.update(files_calced)
            del files_calced
            files_from_txt = dict(sorted(files_from_txt.items()))
            logger.info(f'write {args.hash_txt}')
            fs_hash.write_hash_txt(txt_path=args.hash_txt, files=files_from_txt)
            fcntl.flock(f_lock, fcntl.LOCK_UN)

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class File:
        """file/directory/symlink"""
        hash_val: str  # '0123456789012345678901234567890123456789'
        mode: str  # '0o100664'
        mdate: str
        size: int
        path: str  # absolute path; no trailing slash

    @staticmethod
    def read_hash_txt(*, txt_path: str) -> dict[str, 'fs_hash.File']:
        try:
            return fs_hash.read_hash_txt_str(txt=pathlib.Path(txt_path).read_text())
        except FileNotFoundError as e:
            return {}
        # NOTREACHED

    @staticmethod
    def read_hash_txt_str(*, txt: str) -> dict[str, 'fs_hash.File']:
        files: dict[str, fs_hash.File] = {}
        for line in txt.splitlines():
            file = fs_hash.read_hash_txt_str_line(line=line)
            if file is None:
                continue
            files[file.path] = file
        return dict(sorted(files.items()))

    @staticmethod
    def read_hash_txt_str_line(*, line: str) -> 'fs_hash.File | None':
        cols = line.split(None, 4)
        if len(cols) < 5:
            logger.warning(f'invalid line: {line}')
            return None
        hash_val, mode, mdate, size, path = cols[:5]
        if mode[0:3] == '040':
            assert path[-1] == '/'
            if path != '/':
                path = path[:-1]
        assert path == '/' or path[-1] != '/'
        return fs_hash.File(hash_val=hash_val, mode=mode, mdate=mdate, size=int(size), path=path)

    @staticmethod
    def write_hash_txt(*, txt_path: str, files: dict[str, 'fs_hash.File']) -> None:
        with open(txt_path, 'w') as f:
            for path, file in files.items():
                assert path == file.path
                assert os.path.abspath(path) == path
                if file.mode[0:3] == '040':
                    if path != '/':
                        assert path[-1] != '/'
                        path += '/'
                f.write(f'{file.hash_val} {file.mode} {file.mdate} {file.size:12} {path}\n')

    @staticmethod
    def calc_hash(*, path_: str, hash_fn: Callable[[], Any]) -> 'fs_hash.File | None':
        try:
            stat = os.stat(path_, follow_symlinks=False)
        except FileNotFoundError as e:
            logger.warning(f'file not found: {path_=}')
            return None
        if os.path.islink(path_):
            # realpath = os.path.realpath(path_)
            target_path = os.readlink(path_)
            h = hash_fn()
            h.update(target_path.encode())
            dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone()
            mdate = dt.strftime('%Y-%m-%d.%H:%M:%S.%f') + dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
            return fs_hash.File(hash_val=h.hexdigest(), mode=f'{stat.st_mode:06o}', mdate=mdate, size=stat.st_size, path=path_)
        elif os.path.isfile(path_):
            with open(path_, 'rb') as f:
                h = fs_hash.hash_file_with_progress(f=f, hash_fn=hash_fn, path_=path_)
            dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone()
            mdate = dt.strftime('%Y-%m-%d.%H:%M:%S.%f') + dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
            return fs_hash.File(hash_val=h.hexdigest(), mode=f'{stat.st_mode:06o}', mdate=mdate, size=stat.st_size, path=path_)
        logger.warning(f'unsupported file type: {path_=}')
        return None

    @staticmethod
    def hash_file_with_progress(*, f, hash_fn: Callable[[], Any], path_: str) -> Any:
        """Hash file and display progress every 10 seconds"""
        h = hash_fn()
        t0 = time.monotonic()
        t_last_progress = t0
        os.stat(path_)
        n = 0
        while chunk := f.read(65536):  # https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
            h.update(chunk)
            n += len(chunk)
            t = time.monotonic()
            if t - t_last_progress >= 10:
                elapsed = t - t0
                logger.debug(f'{path_=} {elapsed=:.1f} {n=}/{os.stat(path_).st_size=} ({n / os.stat(path_).st_size * 100:.2f}%)')
                t_last_progress = t
        return h

    @staticmethod
    def test_this() -> None:
        """
        >>> fs_hash.test_this()
        """
        with tempfile.NamedTemporaryFile('w+') as f_hash, tempfile.NamedTemporaryFile('w+') as f_files:
            proc = subprocess.run(f'DEBUG=0 c.py -qq fs_hash --alg=sha1 --hash_txt={f_hash.name} --files_txt={f_files.name}', shell=True, capture_output=True, text=True, check=True)
            assert proc.stdout == ''
            assert proc.stderr == ''
            txt = f_hash.read()
            # assert txt == textwrap.dedent('''\
            #     ...
            # ''')
            # print(txt, file=open('/dev/pts/0', 'w'))
            assert txt == ''


# -----------------------------------------------------------------------------
# command: fs_hash_dups
# generated by codex

epilog = r'''
fs_hash_dups

Show duplicate entries in hash_txt(s), sorted by size descending.
Show at most 100 duplicate groups by default.
Each line shows: hash mode mdate size source_hash_txt_path path
Each duplicate group is separated by a blank line.
'''


# noinspection PyPep8Naming
class fs_hash_dups(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        hash_txts: list[str]
        limit: int

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class SourceFile:
        hash_txt_path: str
        file: 'fs_hash.File'

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('fs_hash_dups', help='Show duplicate files from hash_txt(s) sorted by size descending', epilog=epilog, formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('hash_txts', nargs='+')
        subparser.add_argument('--limit', type=int, default=100, help='max duplicate groups to show')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'fs_hash_dups.Args') -> None:
        logger.debug(f'{args=}')
        if args.limit < 0:
            raise MyException(f'limit must be >= 0: {args.limit=}')

        groups_by_hash: dict[str, list[fs_hash_dups.SourceFile]] = collections.defaultdict(list)
        for hash_txt in args.hash_txts:
            hash_txt = os.path.expanduser(hash_txt)
            files = fs_hash.read_hash_txt(txt_path=hash_txt)
            for file in files.values():
                groups_by_hash[file.hash_val].append(fs_hash_dups.SourceFile(hash_txt_path=hash_txt, file=file))

        dup_groups = [sorted(group, key=lambda source_file: (source_file.file.path, source_file.hash_txt_path)) for group in groups_by_hash.values() if len(group) >= 2]
        dup_groups.sort(key=lambda group: (-group[0].file.size, group[0].file.hash_val, group[0].file.path))
        dup_groups = dup_groups[:args.limit]

        for i, group in enumerate(dup_groups):
            if i != 0:
                print()
            for source_file in group:
                file = source_file.file
                print(f'{file.hash_val} {file.mode} {file.mdate} {file.size:12} {source_file.hash_txt_path} {file.path}')

    @staticmethod
    def test_this() -> None:
        """
        >>> fs_hash_dups.test_this()
        """
        txt_a = textwrap.dedent('''\
            hash_c 100644 2006-01-02.15:04:05.999999+09:00          200 /home/wsh/c.txt
            hash_a 100644 2006-01-02.15:04:05.999999+09:00           10 /home/wsh/a1.txt
            hash_b 100644 2006-01-02.15:04:05.999999+09:00          100 /home/wsh/b1.txt
        ''')
        txt_b = textwrap.dedent('''\
            hash_a 100644 2006-01-02.15:04:05.999999+09:00           10 /home/wsh/a2.txt
            hash_b 100644 2006-01-02.15:04:05.999999+09:00          100 /home/wsh/b2.txt
            hash_d 100644 2006-01-02.15:04:05.999999+09:00            1 /home/wsh/d.txt
        ''')
        with tempfile.NamedTemporaryFile('w+') as f_hash_a, tempfile.NamedTemporaryFile('w+') as f_hash_b:
            f_hash_a.write(txt_a)
            f_hash_a.flush()
            f_hash_b.write(txt_b)
            f_hash_b.flush()
            proc = subprocess.run(f'DEBUG=0 c.py -qq fs_hash_dups {shlex.quote(f_hash_a.name)} {shlex.quote(f_hash_b.name)}', shell=True, capture_output=True, text=True, check=True)
            assert proc.stdout == textwrap.dedent(f'''\
                hash_b 100644 2006-01-02.15:04:05.999999+09:00          100 {f_hash_a.name} /home/wsh/b1.txt
                hash_b 100644 2006-01-02.15:04:05.999999+09:00          100 {f_hash_b.name} /home/wsh/b2.txt

                hash_a 100644 2006-01-02.15:04:05.999999+09:00           10 {f_hash_a.name} /home/wsh/a1.txt
                hash_a 100644 2006-01-02.15:04:05.999999+09:00           10 {f_hash_b.name} /home/wsh/a2.txt
            ''')
            assert proc.stderr == ''

            proc = subprocess.run(f'DEBUG=0 c.py -qq fs_hash_dups --limit=1 {shlex.quote(f_hash_a.name)} {shlex.quote(f_hash_b.name)}', shell=True, capture_output=True, text=True, check=True)
            assert proc.stdout == textwrap.dedent(f'''\
                hash_b 100644 2006-01-02.15:04:05.999999+09:00          100 {f_hash_a.name} /home/wsh/b1.txt
                hash_b 100644 2006-01-02.15:04:05.999999+09:00          100 {f_hash_b.name} /home/wsh/b2.txt
            ''')
            assert proc.stderr == ''

            proc = subprocess.run(f'DEBUG=0 c.py -qq fs_hash_dups --limit=0 {shlex.quote(f_hash_a.name)} {shlex.quote(f_hash_b.name)}', shell=True, capture_output=True, text=True, check=True)
            assert proc.stdout == ''
            assert proc.stderr == ''


# -----------------------------------------------------------------------------
# command: fs_hash_analyze_diff

epilog = r'''
git diff:

diff --git a/xxh3.txt b/xxh3.txt
index 84d06fc..aab8552 100644
--- a/xxh3.txt
+++ b/xxh3.txt
@@ -5119,7 +5118,6 @@ e01acaa659bb8690 100664 2006-01-02.15:04:05.999999+09:00         3746 /home/wsh/
...
-1111111111111111 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/mod.txt
-cccccccccccccccc 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/mv1.txt
-dddddddddddddddd 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/rm.txt
...
+2222222222222222 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/mod.txt
+cccccccccccccccc 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/mv2.txt
+aaaaaaaaaaaaaaaa 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/add.txt
...

$ git show -- xxh3.txt  | c.py fs_hash_analyze_diff
mod /home/wsh/mod.txt
c.py fs_hash_mv /home/wsh/mv1.txt /home/wsh/mv2.txt
add /home/wsh/add.txt
c.py fs_hash_rm /home/wsh/rm.txt
'''


# noinspection PyPep8Naming
class fs_hash_analyze_diff(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        git_diff_file: typing.TextIO

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('fs_hash_analyze_diff', aliases=['fs_hash_find_mv'], help='Analyze git diff and categorize file changes (mod/mv/add/rm)', epilog=epilog, formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('git_diff_file', type=argparse.FileType('r'), nargs='?', default='-', help='git diff file (if not given, read from stdin)')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'fs_hash_analyze_diff.Args') -> None:
        logger.debug(f'{args=}')

        removed_by_hash: dict[str, str] = {}  # hash_val -> path
        removed_by_path: dict[str, str] = {}  # path -> hash_val
        added_by_hash: dict[str, str] = {}  # hash_val -> path
        added_by_path: dict[str, str] = {}  # path -> hash_val

        for line in args.git_diff_file:
            line = line.rstrip('\r\n')
            if line.startswith('-') and not line.startswith('---'):
                # Parse removed line
                file = fs_hash.read_hash_txt_str_line(line=line[1:])
                if file is not None:
                    removed_by_hash[file.hash_val] = file.path
                    removed_by_path[file.path] = file.hash_val
            elif line.startswith('+') and not line.startswith('+++'):
                # Parse added line
                file = fs_hash.read_hash_txt_str_line(line=line[1:])
                if file is not None:
                    added_by_hash[file.hash_val] = file.path
                    added_by_path[file.path] = file.hash_val

        # Detect: mod (same path, different hash)
        for path in list(removed_by_path.keys()):
            if path not in added_by_path:
                continue
            removed_hash = removed_by_path[path]
            added_hash = added_by_path[path]
            if removed_hash == added_hash:
                logger.warning(f'(not tested) same path, but same hash: {path=}, {removed_hash=} (mode or mtime changed?)')
            print(f'mod {shlex.quote(path)}')
            del removed_by_hash[removed_hash]
            del removed_by_path[path]
            del added_by_hash[added_hash]
            del added_by_path[path]

        # Detect: mv (same hash, different path)
        for hash_val in list(removed_by_hash.keys()):
            if hash_val not in added_by_hash:
                continue
            removed_path = removed_by_hash[hash_val]
            added_path = added_by_hash[hash_val]
            if removed_path == added_path:
                logger.warning(f'(not tested) same hash, but same path (mode or mtime changed?): {removed_path=}, {hash_val=}')
            print(f'c.py fs_hash_mv {shlex.quote(removed_path)} {shlex.quote(added_path)}')
            del removed_by_hash[hash_val]
            del removed_by_path[removed_path]
            del added_by_hash[hash_val]
            del added_by_path[added_path]

        # Detect: add (added but not removed)
        for hash_val, added_path in added_by_hash.items():
            print(f'add {shlex.quote(added_path)}')

        # Detect: rm (removed but not added)
        for hash_val, removed_path in removed_by_hash.items():
            print(f'c.py fs_hash_rm {shlex.quote(removed_path)}')

    @staticmethod
    def test_this() -> None:
        """
        >>> fs_hash_analyze_diff.test_this()
        """
        git_diff = textwrap.dedent(r'''
            diff --git a/xxh3.txt b/xxh3.txt
            index 84d06fc..aab8552 100644
            --- a/xxh3.txt
            +++ b/xxh3.txt
            @@ -5119,7 +5118,6 @@ e01acaa659bb8690 100664 2006-01-02.15:04:05.999999+09:00         3746 /home/wsh/
            ...
            -1111111111111111 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/mod.txt
            -cccccccccccccccc 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/mv1.txt
            -dddddddddddddddd 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/rm.txt
            ...
            +2222222222222222 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/mod.txt
            +cccccccccccccccc 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/mv2.txt
            +aaaaaaaaaaaaaaaa 100664 2006-01-02.15:04:05.999999+09:00           42 /home/wsh/add.txt
            ...
        ''')[1:]

        proc = subprocess.run('DEBUG=0 c.py -qq fs_hash_analyze_diff', shell=True, input=git_diff, capture_output=True, text=True, check=True)

        lines = sorted(proc.stdout.strip().split('\n'))
        expected = sorted([
            'mod /home/wsh/mod.txt',
            'mv /home/wsh/mv1.txt /home/wsh/mv2.txt',
            'add /home/wsh/add.txt',
            'rm /home/wsh/rm.txt',
        ])
        assert lines == expected, f'{lines=} != {expected=}'
        assert proc.stderr == ''


# -----------------------------------------------------------------------------
# command: fs_hash_mv

epilog = r'''
fs_hash_mv path_a path_b
fs_hash_mv dir_a/ dir_b/
'''


# noinspection PyPep8Naming
class fs_hash_mv(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        hash_txt: str
        path_a: str
        path_b: str

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('fs_hash_mv', help='Rename and sort entries in the hash database', epilog=epilog, formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--hash_txt', required=True)
        subparser.add_argument('path_a', help='file or directory/ (use trailing slash for directories)')
        subparser.add_argument('path_b', help='file or directory/ (use trailing slash for directories)')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'fs_hash_mv.Args') -> None:
        logger.debug(f'{args=}')

        if (args.path_a.endswith('/') and not args.path_b.endswith('/')) or \
                (not args.path_a.endswith('/') and args.path_b.endswith('/')):
            raise MyException(f'both path_a and path_b must end with / or not end with /: {args.path_a=}, {args.path_b=}')

        with open(f'{args.hash_txt}.lock', 'w') as f_lock:
            logger.info(f'flock {f_lock.name}')
            fcntl.flock(f_lock, fcntl.LOCK_EX)
            logger.info(f'got flock {f_lock.name}')
            files_from_txt = fs_hash.read_hash_txt(txt_path=args.hash_txt)
            for file in list(files_from_txt.values()):
                if args.path_a.endswith('/'):
                    if not file.path.startswith(args.path_a):
                        continue
                    file2 = dataclasses.replace(file, path=args.path_b + file.path[len(args.path_a):])
                    logger.debug(f'{file.path=} -> {file2.path=}')
                    files_from_txt[file2.path] = file2
                    del files_from_txt[file.path], file2
                else:
                    if file.path != args.path_a:
                        continue
                    file2 = dataclasses.replace(file, path=args.path_b)
                    logger.debug(f'{file.path=} -> {file2.path=}')
                    files_from_txt[file2.path] = file2
                    del files_from_txt[file.path], file2
                del file
            files_from_txt = dict(sorted(files_from_txt.items()))
            logger.info(f'write {args.hash_txt}')
            fs_hash.write_hash_txt(txt_path=args.hash_txt, files=files_from_txt)
            fcntl.flock(f_lock, fcntl.LOCK_UN)

        return

    @staticmethod
    def test_this() -> None:
        """
        >>> fs_hash_mv.test_this()
        """
        pass


# -----------------------------------------------------------------------------
# command: fs_hash_rm

epilog = r'''
fs_hash_rm file
fs_hash_rm dir/
'''


# noinspection PyPep8Naming
class fs_hash_rm(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        hash_txt: str
        path_: str

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('fs_hash_rm', help='Remove and sort entries in the hash database', epilog=epilog, formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--hash_txt', required=True)
        subparser.add_argument('path_', help='file or directory/ (use trailing slash for directories)')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'fs_hash_rm.Args') -> None:
        logger.debug(f'{args=}')

        with open(f'{args.hash_txt}.lock', 'w') as f_lock:
            logger.info(f'flock {f_lock.name}')
            fcntl.flock(f_lock, fcntl.LOCK_EX)
            logger.info(f'got flock {f_lock.name}')
            files_from_txt = fs_hash.read_hash_txt(txt_path=args.hash_txt)
            for file in list(files_from_txt.values()):
                if args.path_.endswith('/'):
                    if not file.path.startswith(args.path_):
                        continue
                    logger.debug(f'rm {file.path=}')
                    del files_from_txt[file.path]
                else:
                    if file.path != args.path_:
                        continue
                    logger.debug(f'rm {file.path=}')
                    del files_from_txt[file.path]
                del file
            files_from_txt = dict(sorted(files_from_txt.items()))
            logger.info(f'write {args.hash_txt}')
            fs_hash.write_hash_txt(txt_path=args.hash_txt, files=files_from_txt)
            fcntl.flock(f_lock, fcntl.LOCK_UN)

        return

    @staticmethod
    def test_this() -> None:
        """
        >>> fs_hash_rm.test_this()
        """
        pass

# -----------------------------------------------------------------------------
# EOF
