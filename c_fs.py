#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 Wataru Ashihara <wataash0607@gmail.com>
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
# command: divcat

# noinspection PyPep8Naming
class divcat(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        sep: str
        # arguments
        concatenated_path: str
        each_path: list[str]

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('divcat', help='', formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--sep', default='# {}', metavar='SEPARATOR_TEMPLATE', help='_')  # help='(non-empty)' を入力しないと (default: value) が表示されない
        subparser.add_argument('concatenated_path')
        subparser.add_argument('each_path', nargs='+')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @dataclasses.dataclass(frozen=True)
    class File:
        path: str
        sha1: bytes
        content: str

    @staticmethod
    def main(args: 'divcat.Args') -> None:
        logger.debug(f'{args=}')
        each_files: dict[str, divcat.File] = {}
        for path in args.each_path:
            content = pathlib.Path(path).read_text()
            sha1 = hashlib.sha1(content.encode()).digest()
            file = divcat.File(path, sha1, content)
            each_files[path] = file
            del path, content, sha1, file

        with open(args.concatenated_path, 'w') as f:
            for i, file in enumerate(each_files.values()):
                # assume LF
                f.write(args.sep.format(f'DIVCAT_V0:BEGIN:{file.path}') + '\n')
                f.write(file.content)
                if not file.content.endswith('\n'):
                    f.write('\n' + args.sep.format('DIVCAT_V0:NO_NEWLINE_AT_END_OF_FILE') + '\n')
                f.write(args.sep.format(f'DIVCAT_V0:END:{file.path}') + '\n')
                del i, file
            del f

        # -e move -e delete: not implemented
        # TODO: git checkout -p すると DELETE_SELF; その後の CREATE,MODIFY は観測できない; inotifywait を再起動しないといけない
        inotify_cmd = ['inotifywait', '-mq', '--format=%e %w', '--', args.concatenated_path, *args.each_path]
        logger.debug(f'{shlex.join(inotify_cmd)=}')
        process = subprocess.Popen(inotify_cmd, stdout=subprocess.PIPE, encoding='utf-8')
        sel = selectors.DefaultSelector()
        assert process.stdout is not None
        sel.register(process.stdout, selectors.EVENT_READ)

        modified_paths = lib.OrderedSet[str]()

        while True:
            if process.poll() is not None:
                raise MyException(f'inotifywait exited unexpectedly: {process.poll()}')
            pairs_key_mask = sel.select(timeout=0.1 if modified_paths else None)
            if pairs_key_mask == []:
                # timeout
                assert each_files
                divcat.divcat_modified_paths(each_files=each_files, sep=args.sep, concatenated_path=args.concatenated_path, modified_paths=modified_paths)
                # discard inotify events during divcat
                process.terminate()
                returncode = process.wait()
                # assert returncode == -15  # on Linux
                sel.unregister(process.stdout)
                process = subprocess.Popen(inotify_cmd, stdout=subprocess.PIPE, encoding='utf-8')
                sel.register(process.stdout, selectors.EVENT_READ)
                modified_paths = lib.OrderedSet[str]()
                del returncode
                continue

            assert len(pairs_key_mask) == 1
            line = process.stdout.readline()
            # logger.debug(f'{line=}')
            m = re.search(r'^(?P<event>[^ ]+) (?P<path>.+)$', line)
            assert m is not None
            # logger.debug(f'{m.group("event")=}, {m.group("path")=}')
            # TODO: m['event']
            if m.group('event') in [
                'ACCESS',
                'OPEN',
                'CLOSE_NOWRITE,CLOSE',
                'CLOSE_WRITE,CLOSE',
            ]:
                # ignore
                continue
            if m.group('event') != 'MODIFY':
                logger.error(f'not implemented: {m.group("event")=}')
            modified_paths.add(m.group('path'))
            del line, m
        logger.error('NOTREACHED')
        sys.exit(1)

    @staticmethod
    def divcat_modified_paths(*, each_files: dict[str, File], sep: str, concatenated_path: str, modified_paths: lib.OrderedSet[str]) -> None:
        logger.debug(f'{modified_paths=}')
        modified_each_paths = modified_paths - {concatenated_path}
        if concatenated_path in modified_paths and len(modified_each_paths) > 0:
            breakpoint()
            logger.warning(f'{concatenated_path=} and {modified_each_paths=} are modified; ignoring {concatenated_path=}')
            raise  # TODO: backup
        if len(modified_each_paths) > 0:
            divcat.cat(each_files=each_files, sep=sep, concatenated_path=concatenated_path, modified_each_paths=modified_each_paths)
        else:
            divcat.div(each_files=each_files, sep=sep, concatenated_path=concatenated_path)
        return

    @dataclasses.dataclass(frozen=True)
    class ContentWithHeader:
        path: str
        content: str
        eof_no_newline: bool

    @staticmethod
    def cat(*, each_files: dict[str, File], sep: str, concatenated_path: str, modified_each_paths: lib.OrderedSet[str]) -> None:
        logger.debug(f'cat ({modified_each_paths=} -> {concatenated_path=})')
        changed = False
        for modified_path in modified_each_paths:
            assert modified_path in each_files
            content = pathlib.Path(modified_path).read_text()
            sha1 = hashlib.sha1(content.encode()).digest()
            file_old = each_files[modified_path]
            if sha1 != file_old.sha1:
                logger.debug(f'changed: {modified_path=}')
                changed = True
                each_files[modified_path] = divcat.File(modified_path, sha1, content)
            del content, sha1, file_old
            continue
        if not changed:
            logger.debug('no changes')
            return
        logger.info(f'cat {len(each_files)=} into {concatenated_path=}')
        with open(concatenated_path, 'w') as f:
            for i, file in enumerate(each_files.values()):
                # assume LF
                f.write(sep.format(f'DIVCAT_V0:BEGIN:{file.path}') + '\n')
                f.write(file.content)
                if not file.content.endswith('\n'):
                    f.write('\n' + sep.format('DIVCAT_V0:NO_NEWLINE_AT_END_OF_FILE') + '\n')
                f.write(sep.format(f'DIVCAT_V0:END:{file.path}') + '\n')
                del i, file
            del f
        return

    # TODO: div/cat 先の中身がオリジナルと変わっていたら警告してバックアップ
    @staticmethod
    def div(*, each_files: dict[str, File], sep: str, concatenated_path: str) -> None:
        content = pathlib.Path(concatenated_path).read_text()
        chs: list[divcat.ContentWithHeader] = []
        # TODO: sep に改行入れられない
        # TODO: BEGIN...END 外に文字列にあれば警告
        # TODO: BEGIN にマッチする END が無ければ警告
        # for match in re.finditer(r'^/\* DIVCAT_V0:BEGIN:(.+)__ \*/$\n', content, re.MULTILINE):
        pat_begin = re.escape(sep).replace(r'\{\}', r'DIVCAT_V0:BEGIN:(?P<path>.+)')
        pat_end = re.escape(sep).replace(r'\{\}', r'DIVCAT_V0:END:(?P=path)')
        for match in re.finditer(fr'^{pat_begin}(\r?\n)(?P<content>[\s\S]*?(\r?\n)){pat_end}(?=\r?$)', content, re.MULTILINE):
            content = match.group('content')  # TODO: m['content']
            eof_no_newline = False
            if content.endswith('\n' + sep.format('DIVCAT_V0:NO_NEWLINE_AT_END_OF_FILE') + '\n'):
                eof_no_newline = True
                content = content.removesuffix('\n' + sep.format('DIVCAT_V0:NO_NEWLINE_AT_END_OF_FILE') + '\n')
            chs.append(divcat.ContentWithHeader(match.group('path'), content, eof_no_newline))
            del match, content, eof_no_newline
        del pat_begin
        del pat_end

        logger.debug(f'div ({concatenated_path=} {len(chs)=} -> {len(each_files)=})')
        for ch in chs:
            sha1 = hashlib.sha1(ch.content.encode()).digest()
            if ch.path not in each_files:
                breakpoint()
                logger.info(f'create: {ch.path=} {sha1.hex()=}')
                each_files[ch.path] = divcat.File(ch.path, sha1, ch.content)
                pathlib.Path(ch.path).write_text(ch.content)
            elif sha1 != each_files[ch.path].sha1:
                logger.info(f'update: {ch.path=} {sha1.hex()=}')
                each_files[ch.path] = divcat.File(ch.path, sha1, ch.content)
                pathlib.Path(ch.path).write_text(ch.content)
            else:
                # logger.debug(f'nop: {ch.path=} {sha1.hex()=}')
                pass
            del ch
        removed_paths_in_cat_file = set(each_files.keys()) - set(ch.path for ch in chs)
        for path in removed_paths_in_cat_file:
            logger.warning(f'in {concatenated_path=}: removed {path=}; to really remove, run: rm {shlex.quote(path)}')
        return

    @staticmethod
    def test_this() -> None:
        # old
        if False:
            if 'PYCHARM_HOSTED' in os.environ:
                sys.argv.append('-vv')
                sys.argv.append('--sep=/* {} */')
                # sys.argv.append('--sep=// {}')
                # sys.argv.append('--sep=# {}')
                # sys.argv.append('--')
                sys.argv.append('/tmp/catfs/cat.c')
                sys.argv.append('/tmp/catfs/aaa.c')
                sys.argv.append('/tmp/catfs/bbb.c')


# -----------------------------------------------------------------------------
# command: fs_sha1

epilog = r'''\
5ffadbc4ec89b562651ae7e04c72de3c5ab34e21 040755 2025-05-02.08:52:12.781842+09:00 569887267676 /

head ~/sha/xxh3.txt | sed -E 's/^(\S+) (\S+) (\S+) ( *\S+) (.+)$/1:\1|2:\2|3:\3|4:\4|5:\5/'
head ~/sha/xxh3.txt | sed -E 's/^(\S+) (\S+) (\S+) ( *\S+) (.+)$/\1 \2 \3 \4 \5/'
# @bv
old: c.py fs_sha1_all ...
.
wsh24 2025-05-10 Sat 12:44:13:
713.02user 508.24system 22:50.02elapsed 89%CPU ==end:sha1==
277.76user 524.63system 15:40.70elapsed 85%CPU ==end:xxh32==
187.34user 537.17system 15:04.16elapsed 80%CPU ==end:xxh64==
152.41user 534.03system 14:34.07elapsed 78%CPU ==end:xxh3==
154.61user 539.93system 14:27.78elapsed 80%CPU ==end:xxh128==
.
wsh79 2025-05-10 Sat 10:09:16:
2.31user 1.36system 0:03.70elapsed ==end:sha1==
1.30user 1.21system 0:02.52elapsed ==end:xxh32==
1.05user 1.25system 0:02.32elapsed ==end:xxh64==
1.06user 1.16system 0:02.23elapsed ==end:xxh3==
1.03user 1.19system 0:02.22elapsed ==end:xxh128==
# @bv
'''

# noinspection PyPep8Naming
class fs_sha1(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        alg: str
        hash_txt: str
        files_txt: str

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('fs_sha1', aliases=['fs_hash'], help='', epilog=epilog, formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--alg', choices=['sha1', 'xxh32', 'xxh64', 'xxh3', 'xxh128'], default='xxh3')
        subparser.add_argument('--hash_txt', required=True)
        subparser.add_argument('--files_txt', required=True)
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'fs_sha1.Args') -> None:
        logger.debug(f'{args=}')
        import xxhash

        hash_fn = hashlib.sha1
        if args.alg in ['xxh32', 'xxh64', 'xxh3', 'xxh128']:
            import xxhash
            hash_fn = {
                'xxh32': xxhash.xxh32,
                'xxh64': xxhash.xxh64,
                'xxh3': xxhash.xxh3_64,
                'xxh128': xxhash.xxh3_128,
            }[args.alg]

        files_scanned: dict[str, fs_sha1.File] = {}

        for line in pathlib.Path(args.files_txt).read_text().splitlines():
            # drwxr-xr-x             37 2025/05/02 08:52:12 .
            # drwxr-xr-x              5 2024/09/13 11:24:03 home
            # drwxr-x---            219 2025/08/11 19:27:43 home/wsh
            # drwx------             17 2025/08/07 15:27:32 home/wsh/.ssh
            # -rw-rw-r--         11,463 2025/08/07 15:27:32 home/wsh/.ssh/config
            m = re.match(r'^(?P<mode>[\w-]+)\s+(?P<size>[\d,]+)\s+(?P<mdate>\d{4}/\d\d/\d\d \d\d:\d\d:\d\d)\s+(?P<path>.+)$', line)
            if m is None:
                logger.warning(f'{args.files_txt}: discard invalid line: {line}')
                continue
            m.groupdict()
            if m['mode'][0] == 'd':
                logger.debug(f'skip directory: {m['path']=}')
                del line, m
                continue
            if not m['path'].startswith('home/'):
                logger.warning(f'{args.files_txt}: not start with "home/": {m['path']=}')
                del line, m
                continue

            path_ = f'/{m['path']}'
            logger.debug(f'{path_=}')
            stat = os.stat(path_, follow_symlinks=False)

            if os.path.isfile(path_):
                h = hash_fn()
                with open(path_, 'rb') as f:
                    while chunk := f.read(65536):  # https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
                        h.update(chunk)
                del f
                dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone()
                mdate = dt.strftime('%Y-%m-%d.%H:%M:%S.%f') + dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
                files_scanned[path_] = fs_sha1.File(hash_val=h.hexdigest(), mode=f'{stat.st_mode:06o}', mdate=mdate, size=stat.st_size, path=path_)
                del line, m, path_, stat, h, chunk, dt, mdate
                continue
            if os.path.islink(path_):
                logger.warning(f'not tested {path_=}')
                # realpath = os.path.realpath(path_)
                target_path = os.readlink(path_)
                h = hash_fn()
                h.update(target_path.encode())
                dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone()
                mdate = dt.strftime('%Y-%m-%d.%H:%M:%S.%f') + dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
                files_scanned[path_] = fs_sha1.File(hash_val=h.hexdigest(), mode=f'{stat.st_mode:06o}', mdate=mdate, size=0, path=path_)
                del line, m, path_, stat, target_path, h, dt, mdate
                continue
            logger.warning(f'unsupported file type: {path_=}')

        assert set(locals().keys()) == {'args', 'xxhash', 'hash_fn', 'files_scanned'}, f'{locals().keys()=} != { {'args', 'hash_fn', 'files_scanned'} }'

        files_scanned = dict(sorted(files_scanned.items()))
        with open(f'{args.hash_txt}.lock', 'w') as f_lock:
            logger.info(f'flock {f_lock.name}')
            fcntl.flock(f_lock, fcntl.LOCK_EX)
            logger.info(f'got flock {f_lock.name}')
            files_from_txt = fs_sha1.read_hash_txt(txt_path=args.hash_txt)
            files_from_txt.update(files_scanned)
            del files_scanned
            files_from_txt = dict(sorted(files_from_txt.items()))
            logger.info(f'write {args.hash_txt}')
            fs_sha1.write_hash_txt(txt_path=args.hash_txt, files=files_from_txt)
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
    def read_hash_txt(*, txt_path: str) -> dict[str, 'fs_sha1.File']:
        try:
            files: dict[str, fs_sha1.File] = {}
            for line in pathlib.Path(txt_path).read_text().splitlines():
                cols = line.split(None, 4)
                if len(cols) < 5:
                    logger.warning(f'discard invalid line: {line}')
                    continue
                hash_val, mode, mdate, size, path = cols[:5]
                if mode[0:3] == '040':
                    assert path[-1] == '/'
                    if path != '/':
                        path = path[:-1]
                assert path == '/' or path[-1] != '/'
                files[path] = fs_sha1.File(hash_val=hash_val, mode=mode, mdate=mdate, size=int(size), path=path)
            return dict(sorted(files.items()))
        except FileNotFoundError as e:
            return {}
        # NOTREACHED

    @staticmethod
    def write_hash_txt(*, txt_path: str, files: dict[str, 'fs_sha1.File']) -> None:
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
    def test_this() -> None:
        """
        >>> fs_sha1.test_this()
        """
        with tempfile.NamedTemporaryFile('w+') as f_hash, tempfile.NamedTemporaryFile('w+') as f_files:
            proc = subprocess.run(f'DEBUG=0 c.py -qq fs_sha1 --alg=sha1 --hash_txt={f_hash.name} --files_txt={f_files.name}', shell=True, capture_output=True, text=True, check=True)
            assert proc.stdout == ''
            assert proc.stderr == ''
            txt = f_hash.read()
            # assert txt == textwrap.dedent('''\
            #     ...
            # ''')
            # print(txt, file=open('/dev/pts/0', 'w'))
            assert txt == ''

# -----------------------------------------------------------------------------
# EOF
