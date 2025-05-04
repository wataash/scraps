#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2020-2025 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""
mini clis

requires python3.13
"""

import os
if os.environ.get('DEBUG') == '1':
    import pydevd_pycharm
    pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True, suspend=False)

from typing import Any, Callable, Iterable, Iterator, Literal
import argparse
import asyncio
import base64
import collections
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
# argparse

@dataclasses.dataclass(frozen=True, kw_only=True)
class ArgsGlobal:
    parser: argparse.ArgumentParser
    quiet: int


ARGS_GLOBAL: ArgsGlobal
parser = argparse.ArgumentParser()
parser.add_argument('-q', '--quiet', action='count', default=0, help='-q to suppress debug; -qq to suppress info; -qqq to suppress warn, -qqqq to suppress error')
subparsers = parser.add_subparsers(required=True)


class Cmd:
    classes = []

    def __init_subclass__(cls, **kwargs):
        cls.classes.append(cls)
        cls.add_parser()


# -----------------------------------------------------------------------------
# command: a_template 

# noinspection PyPep8Naming
class a_template(Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        pass

    @classmethod
    def add_parser(cls):
        subparser = subparsers.add_parser('a_template', help='')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'a_template.Args') -> None:
        logger.debug(f'{args=}')
        sys.exit(0)

    @staticmethod
    def test_this() -> None:
        """
        >>> a_template.test_this()
        """
        proc = subprocess.run('c.py a_template', shell=True, capture_output=True, text=True, check=True)
        assert proc.stdout == ''
        # [D 22:24:48 c.py:998 main()] ARGS_GLOBAL=ArgsGlobal(...)
        assert re.search(r'^\[D \d{2}:\d{2}:\d{2} c.py:\d+ main\(\)] ARGS_GLOBAL=ArgsGlobal\(.+\)\r?\n', proc.stderr) is not None


# -----------------------------------------------------------------------------
# command: divcat 

# noinspection PyPep8Naming
class divcat(Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        sep: str
        # arguments
        concatenated_path: str
        each_path: list[str]

    @classmethod
    def add_parser(cls):
        subparser = subparsers.add_parser('divcat', help='', formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
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
            with open(path) as f:
                content = f.read()
                sha1 = hashlib.sha1(content.encode()).digest()
                file = divcat.File(path, sha1, content)
                each_files[path] = file
                del content, sha1, file
                del f
            del path

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
            with open(modified_path) as f:
                content = f.read()
                del f
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
        with open(concatenated_path) as f:
            content = f.read()
            del f
        chs: list[divcat.ContentWithHeader] = []
        # TODO: sep に改行入れられない
        # TODO: BEGIN...END 外に文字列にあれば警告
        # TODO: BEGIN にマッチする END が無ければ警告
        # for match in re.finditer(r'^/\* DIVCAT_V0:BEGIN:(.+)__ \*/$\n', content, re.MULTILINE):
        pat_begin = re.escape(sep).replace(r'\{\}', r'DIVCAT_V0:BEGIN:(?P<path>.+)')
        pat_end = re.escape(sep).replace(r'\{\}', r'DIVCAT_V0:END:(?P=path)')
        for match in re.finditer(fr'^{pat_begin}(\r?\n)(?P<content>[\s\S]*?(\r?\n)){pat_end}(?=\r?$)', content, re.MULTILINE):
            content = match.group('content')
            eof_no_newline = False
            if content.endswith('\n' + sep.format('DIVCAT_V0:NO_NEWLINE_AT_END_OF_FILE') + '\n'):
                breakpoint()
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
                with open(ch.path, 'w') as f:
                    f.write(ch.content)
            elif sha1 != each_files[ch.path].sha1:
                logger.info(f'update: {ch.path=} {sha1.hex()=}')
                each_files[ch.path] = divcat.File(ch.path, sha1, ch.content)
                with open(ch.path, 'w') as f:
                    f.write(ch.content)
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

epilog = '''\
5ffadbc4ec89b562651ae7e04c72de3c5ab34e21 040755 2025-05-02.08:52:12.781842+09:00 569887267676 /
'''
# head ~/sha/sha1.txt  | sed -E 's/^(\S+) (\S+) (\S+) ( *\S+) (.+)$/1:\1|2:\2|3:\3|4:\4|5:\5/'
# head ~/sha/xxh64.txt | sed -E 's/^(\S+) (\S+) (\S+) ( *\S+) (.+)$/1:\1|2:\2|3:\3|4:\4|5:\5/'
# head ~/sha/sha1.txt  | sed -E 's/^(\S+) (\S+) (\S+) ( *\S+) (.+)$/\1 \2 \3 \4 \5/'
# head ~/sha/xxh64.txt | sed -E 's/^(\S+) (\S+) (\S+) ( *\S+) (.+)$/\1 \2 \3 \4 \5/'

# noinspection PyPep8Naming
class fs_sha1(Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        alg: str
        txt: str
        exclude: list[str]
        path: str

    @classmethod
    def add_parser(cls):
        subparser = subparsers.add_parser('fs_sha1', aliases=['fs_hash'], help='', epilog=epilog, formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--alg', choices=['sha1', 'xxh32', 'xxh64', 'xxh3', 'xxh128'], default='sha1')
        subparser.add_argument('--txt', default=f'{os.path.expanduser('~/sha/sha1.txt')}', help='_')  # help='(non-empty)' を入力しないと (default: value) が表示されない
        subparser.add_argument('-e', '--exclude', nargs='+', default=[], type=cls.validate_exclude)
        subparser.add_argument('path')
        subparser.set_defaults(func=lambda args: cls(**args))

    @staticmethod
    def validate_exclude(path: str) -> str:
        if path == '':
            raise argparse.ArgumentTypeError(f'invalid path: {path}')
        if path == '/':
            raise argparse.ArgumentTypeError(f'invalid path: {path}')
        if path[0] != '/':
            raise argparse.ArgumentTypeError(f'invalid path: {path}; must start with /')
        return path

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'fs_sha1.Args') -> None:
        logger.debug(f'{args=}')
        import xxhash
        path_root = os.path.abspath(args.path)  # trailing slash removed
        excludes = {os.path.abspath(f'{path_root}{x}') for x in args.exclude}

        hash_fn = hashlib.sha1
        if args.alg in ['xxh32', 'xxh64', 'xxh3', 'xxh128']:
            import xxhash
            hash_fn = {
                'xxh32': xxhash.xxh32,
                'xxh64': xxhash.xxh64,
                'xxh3': xxhash.xxh3_64,
                'xxh128': xxhash.xxh3_128,
            }[args.alg]

        files = fs_sha1.scan(path_=path_root, excludes=excludes, hash_fn=hash_fn)
        assert list(sorted(files.keys())) == list(files.keys())
        with open(f'{args.txt}.lock', 'w') as f_lock:
            logger.info(f'flock {f_lock.name}')
            fcntl.flock(f_lock, fcntl.LOCK_EX)
            logger.info(f'got flock {f_lock.name}')
            for file in fs_sha1.read_txt(txt_path=args.txt).values():
                if file.path == args.path:
                    logger.info(f'discard {file.path}')
                    continue
                if file.path.startswith(f'{path_root}/'):
                    logger.debug(f'discard {file.path}')
                    continue
                files[file.path] = file
            files.update(files)
            if '/' in files:
                del files['/']
            files = dict(sorted(files.items()))
            dir_ = os.path.dirname(args.path)
            while True:
                stat = os.stat(dir_, follow_symlinks=False)  # symlink not tested
                size, hash_val = fs_sha1.calc_dir(dir_=dir_, files=files, hash_fn=hash_fn)
                dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone()
                mdate = dt.strftime('%Y-%m-%d.%H:%M:%S.%f') + dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
                file = fs_sha1.File(hash_val=hash_val, mode=f'{stat.st_mode:06o}', mdate=mdate, size=size, path=dir_)
                logger.info(f'{file}')
                files[dir_] = file
                files = dict(sorted(files.items()))
                if dir_ == '/':
                    break
                dir_ = os.path.dirname(dir_)
            logger.info(f'write {args.txt}')
            fs_sha1.write_txt(txt_path=args.txt, files=files)
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
    def scan(*, path_: str, excludes: set[str], hash_fn, depth=0) -> dict[str, 'fs_sha1.File']:
        if path_ in excludes:
            logger.debug(f'{'  ' * depth}--exclude: {path_=}')
            return {}
        logger.debug(f'{'  ' * depth}{path_=}')
        assert path_ == os.path.abspath(path_)
        stat = os.stat(path_, follow_symlinks=False)

        if os.path.isfile(path_):
            h = hash_fn()
            with open(path_, 'rb') as f:
                while chunk := f.read(65536):  # https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
                    h.update(chunk)
            dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone()
            mdate = dt.strftime('%Y-%m-%d.%H:%M:%S.%f') + dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
            file = fs_sha1.File(hash_val=h.hexdigest(), mode=f'{stat.st_mode:06o}', mdate=mdate, size=stat.st_size, path=path_)
            logger.debug(f'{'  ' * depth}{file}')
            return {path_: file}
        if os.path.islink(path_):
            # realpath = os.path.realpath(path_)
            target_path = os.readlink(path_)
            h = hash_fn()
            h.update(target_path.encode())
            dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone()
            mdate = dt.strftime('%Y-%m-%d.%H:%M:%S.%f') + dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
            file = fs_sha1.File(hash_val=h.hexdigest(), mode=f'{stat.st_mode:06o}', mdate=mdate, size=0, path=path_)
            logger.debug(f'{'  ' * depth}{file}')
            return {path_: file}

        if not os.path.isdir(path_):
            logger.warning(f'unsupported file type: {path_}')
            return {}

        # I know sortedcontainers.SortedDict, but I don't want to add a dependency
        files: dict[str, fs_sha1.File] = {}
        for entry in os.scandir(path_):
            tmp_files = fs_sha1.scan(path_=entry.path, excludes=excludes, hash_fn=hash_fn, depth=depth + 1)
            files.update(tmp_files)
        files = dict(sorted(files.items()))
        size, hash_val = fs_sha1.calc_dir(dir_=path_, files=files, hash_fn=hash_fn)
        dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).astimezone()
        mdate = dt.strftime('%Y-%m-%d.%H:%M:%S.%f') + dt.strftime('%z')[:3] + ':' + dt.strftime('%z')[3:]
        files[path_] = fs_sha1.File(hash_val=hash_val, mode=f'{stat.st_mode:06o}', mdate=mdate, size=size, path=path_)
        files = dict(sorted(files.items()))
        logger.debug(f'{'  ' * depth}{files[path_]}')
        return files

    @staticmethod
    def calc_dir(*, dir_: str, files: dict[str, 'fs_sha1.File'], hash_fn) -> tuple[int, str]:
        assert dir_ == os.path.abspath(dir_)
        assert list(sorted(files.keys())) == list(files.keys())
        size = 0
        h = hash_fn()
        for file in files.values():
            if os.path.dirname(file.path) != dir_:
                continue
            size += file.size
            h.update(f'{file.hash_val}{file.mode}{file.path}'.encode())
        return size, h.hexdigest()

    @staticmethod
    def read_txt(*, txt_path: str) -> dict[str, 'fs_sha1.File']:
        try:
            with open(txt_path) as f:
                files: dict[str, fs_sha1.File] = {}
                for line in f:
                    line = line.rstrip('\n')
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
    def write_txt(*, txt_path: str, files: dict[str, 'fs_sha1.File']) -> None:
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
        with tempfile.NamedTemporaryFile('w+') as f:
            proc = subprocess.run(f'c.py -qq fs_sha1 --alg sha1 --txt {f.name} {f.name}', shell=True, capture_output=True, text=True, check=True)
            assert proc.stdout == ''
            assert proc.stderr == ''
            txt = f.read()
            # assert txt == textwrap.dedent('''\
            #     1de2200bc7efe4c88f3063fba9b9debace9e1ec2 040755 2006-01-02.15:04:05.123456+09:00            0 /
            #     51cce55d5a7f5da354cb1d9ab5bf4724830a0b82 041777 2006-01-02.15:04:05.123456+09:00            0 /tmp
            #     da39a3ee5e6b4b0d3255bfef95601890afd80709 100600 2006-01-02.15:04:05.123456+09:00            0 /tmp/tmpar94entd
            # ''')
            # print(txt, file=open('/dev/pts/0', 'w'))
            assert txt != ''


# -----------------------------------------------------------------------------
# command: smux 

# noinspection PyPep8Naming
class smux(Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        sock: str

    @classmethod
    def add_parser(cls):
        subparser = subparsers.add_parser('smux', help='', formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--sock', required=True)
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'smux.Args') -> None:
        logger.debug(f'{args=}')
        logger.info(f'smux: {os.ttyname(sys.stdin.fileno())} {os.getpid()}')
        if not (sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()):
            logger.error('stdin, stdout, and stderr must be TTYs\n')
            sys.exit(1)

        sel = selectors.DefaultSelector()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(args.sock)
        buf_ref = [b'']
        sel.register(sock, selectors.EVENT_READ, lambda key, mask: smux.read_from_server(key=key, mask=mask, sock=sock, buf_ref=buf_ref))

        sock.send((json.dumps({'type': 'connect', 'pid': os.getpid()}) + '\n').encode())
        sel.register(sys.stdin.fileno(), selectors.EVENT_READ, lambda key, mask: smux.read_local_stdin(key=key, mask=mask, sock=sock))

        old_term = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())

        def restore_tty():
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_term)  # ai-generated

        try:
            while True:
                for key, mask in sel.select():
                    callback = key.data
                    callback(key, mask)
        except KeyboardInterrupt:
            logger.info('^C')
        finally:
            restore_tty()
            sock.close()

    @staticmethod
    def read_local_stdin(*, key: selectors.SelectorKey, mask: int, sock: socket.socket) -> None:
        data = os.read(sys.stdin.fileno(), 1024)
        assert len(data) > 0
        msg = json.dumps({'type': 'stdin', 'data': (base64.b64encode(data).decode())}) + '\n'
        sock.send(msg.encode())

    @staticmethod
    def read_from_server(*, key: selectors.SelectorKey, mask: int, sock: socket.socket, buf_ref: list[bytes]) -> None:
        data = sock.recv(4096)
        assert len(data) > 0
        buf = buf_ref[0]
        buf += data
        beg = 0
        while beg < len(buf):
            end = buf.find(b'\n', beg)
            if end < 0:
                # in the middle of the next line
                break
            line = buf[beg:end]
            beg = end + 1
            msg = json.loads(line.decode())
            if msg['type'] == 'stdout':
                sys.stdout.buffer.write(base64.b64decode(msg['data']))
                sys.stdout.buffer.flush()
            elif msg['type'] == 'close':
                logger.info(f'{msg=} {buf=} {buf_ref=}')
                sys.exit(0)
            buf_ref[0] = buf[beg:]


# -----------------------------------------------------------------------------
# command: smux_server 

# noinspection PyPep8Naming
class smux_server(Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        sock: str
        cmd: list[str]

    @classmethod
    def add_parser(cls):
        subparser = subparsers.add_parser('smux_server', help='', formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--sock', required=True)
        subparser.add_argument('cmd', nargs='+')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'smux_server.Args') -> None:
        logger.debug(f'{args=}')
        logger.info(f'smux_server: {os.ttyname(sys.stdin.fileno())} {os.getpid()}')
        if not (sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()):
            logger.error('stdin, stdout, and stderr must be TTYs\n')
            sys.exit(1)

        sel = selectors.DefaultSelector()
        clients = {}
        clients_buf: dict[socket.socket, bytes] = {}

        logger.info(f'child: {' '.join(args.cmd)}')
        child_pid, ptmx_fd = pty.fork()
        if child_pid == 0:
            os.execvp(args.cmd[0], args.cmd)
        sel.register(ptmx_fd, selectors.EVENT_READ, lambda key, mask: smux_server.read_from_child(key=key, mask=mask, sel=sel, clients=clients, clients_buf=clients_buf))
        logger.info(f'child: {os.ptsname(ptmx_fd)} {child_pid}; connect with:\n'
                    f'c.py smux --sock {args.sock}\n'
                    f'{sys.executable} {sys.argv[0]} smux --sock {args.sock}')

        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if os.path.exists(args.sock):
            logger.warning(f'rm {args.sock=}')
            os.unlink(args.sock)
        server_sock.bind(args.sock)
        server_sock.listen()
        # server_sock.setblocking(False)
        sel.register(server_sock, selectors.EVENT_READ, lambda key, mask: smux_server.accept(key=key, mask=mask, server_sock=server_sock, sel=sel, clients=clients, ptmx_fd=ptmx_fd, clients_buf=clients_buf))

        signal.signal(signal.SIGWINCH, lambda signum, frame: smux_server.forward_winch(signum=signum, frame=frame, ptmx_fd=ptmx_fd, child_pid=child_pid))

        try:
            exitcode = smux_server.main2(child_pid=child_pid, sel=sel)
        finally:
            logger.info('finally')
            os.close(ptmx_fd)
            for conn, client_pid in clients.items():
                # send: type=close
                logger.info(f'conn.send() {conn.fileno()}, {{"type": "close"}}')
                conn.send((json.dumps({'type': 'close'}) + '\n').encode())
                sel.unregister(conn)
                conn.close()
            server_sock.close()
            os.unlink(args.sock)
        logger.info(f'exit({exitcode=})')
        sys.exit(exitcode)

    @staticmethod
    def main2(*, child_pid: int, sel: selectors.BaseSelector) -> int:
        def loop():
            while True:
                for key, mask in sel.select():
                    # logger.debug(f'{key=}, {mask=}')
                    callback = key.data
                    end_reason = callback(key, mask)
                    if end_reason is not None:
                        logger.info(f'{end_reason=}')
                        return

        try:
            loop()
            logger.info(f'waitpid {child_pid=}')
            pid_waitstatus = os.waitpid(child_pid, 0)
            assert pid_waitstatus[0] == child_pid
            child_exitcode = os.waitstatus_to_exitcode(pid_waitstatus[1])
            logger.info(f'{child_exitcode=}')

            # logger.info(f'kill {child_pid=}, close({ptmx_fd=})')
            # os.kill(child_pid, signal.SIGTERM)
            return child_exitcode
        except KeyboardInterrupt as _e:
            # logger.info('KeyboardInterrupt', exc_info=True)
            logger.info('KeyboardInterrupt')
            # exc = traceback.format_exc()
            # logger.info(exc)
            return 1
        breakpoint_ = 1

    @staticmethod
    def forward_winch(*, signum: int, frame: types.FrameType | None, ptmx_fd: int, child_pid: int) -> None:
        # ai-generated
        winsize = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, struct.pack('hhhh', 0, 0, 0, 0))
        logger.info(f'{signum=} {frame=} {winsize.hex()=}')
        fcntl.ioctl(ptmx_fd, termios.TIOCSWINSZ, winsize)
        os.kill(child_pid, signal.SIGWINCH)

    @staticmethod
    def read_from_child(*, key: selectors.SelectorKey, mask: int, sel: selectors.BaseSelector, clients: dict[socket.socket, int], clients_buf: dict[socket.socket, bytes]) -> str | None:
        logger.debug(f'{key=} {mask=}')
        logger.debug(f'os.read(fd={key.fd}, 1024)')
        try:
            out = os.read(key.fd, 1024)
        except OSError as e:
            # e=OSError(5, 'Input/output error') process finished?
            logger.info(f'{e=} process finished?')
            return f'read_from_child:{e}'
        logger.debug(f'{len(out)=}')
        assert len(out) > 0
        dead = []
        for conn, client_pid in clients.items():
            try:
                data = base64.b64encode(out).decode()
                logger.debug(f'conn.send() {conn.fileno()}, {{"type": "stdout", "data": {len(data)=}}}')
                conn.send((json.dumps({'type': 'stdout', 'data': data}) + '\n').encode())
            except Exception as _e:
                logger.warning(f'{_e=}')
                dead.append((conn, client_pid))
        for conn, client_pid in dead:
            del clients[conn]
            del clients_buf[conn]
            sel.unregister(conn)
            conn.close()
            logger.info(f'Client {client_pid} disconnected')
        return None

    @staticmethod
    def accept(*, key: selectors.SelectorKey, mask: int, server_sock: socket.socket, sel: selectors.BaseSelector, clients: dict[socket.socket, int], ptmx_fd: int, clients_buf: dict[socket.socket, bytes]) -> str | None:
        conn, _addr = server_sock.accept()
        # conn.setblocking(False)
        clients[conn] = -1
        clients_buf[conn] = b''
        logger.info(f'{key=} {mask=} {ptmx_fd=} {conn.fileno()=} {_addr=}')
        sel.register(conn, selectors.EVENT_READ, lambda key, mask: smux_server.read_from_client(key=key, mask=mask, conn=conn, sel=sel, clients=clients, ptmx_fd=ptmx_fd, clients_buf=clients_buf))
        return None

    def read_from_client(*, key: selectors.SelectorKey, mask: int, conn: socket.socket, sel: selectors.BaseSelector, clients: dict[socket.socket, int], ptmx_fd: int, clients_buf: dict[socket.socket, bytes]) -> str | None:
        client_pid = clients[conn]
        logger.debug(f'{key=} {mask=} {conn.fileno()=} {client_pid=}')
        data = conn.recv(4096)
        if len(data) == 0:
            # client disconnected
            logger.info(f'{client_pid=} disconnected; {clients_buf[conn]=}')
            del clients[conn]
            del clients_buf[conn]
            sel.unregister(conn)
            conn.close()
            return None
        buf = clients_buf[conn] + data
        beg = 0
        while beg < len(buf):
            end = buf.find(b'\n', beg)
            if end < 0:
                # in the middle of the next line
                logger.warning(f'short read: {client_pid=} {len(buf)=} {beg=} {end=}')
                break
            line = buf[beg:end]
            beg = end + 1
            try:
                msg = json.loads(line.decode())
                if msg['type'] == 'connect':
                    clients[conn] = client_pid = msg['pid']
                    logger.debug(f'{client_pid=} connected')
                    continue
                elif msg['type'] == 'stdin':
                    os.write(ptmx_fd, base64.b64decode(msg['data']))
                    continue
                logger.warning(f'unknown type from {client_pid=}: {msg=}')
            except json.JSONDecodeError as e:
                logger.warning(f'invalid json from {client_pid=}: {e=} {line=}')
                continue
        clients_buf[conn] = buf[beg:]
        return None


# -----------------------------------------------------------------------------
# command: z_meta_command_list 

# noinspection PyPep8Naming
class z_meta_command_list(Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        pass

    @classmethod
    def add_parser(cls):
        subparser = subparsers.add_parser('z_meta_command_list', help='')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'z_meta_command_list.Args') -> None:
        [print(name) for name in subparsers.choices if name != '----------c_v1.py----------']
        sys.exit(0)

    @staticmethod
    def test_this() -> None:
        """
        >>> z_meta_command_list.test_this()
        """
        proc = subprocess.run('c.py -q z_meta_command_list', shell=True, capture_output=True, text=True, check=True)
        assert proc.stdout.startswith('a_template\n')
        assert proc.stderr == ''


# -----------------------------------------------------------------------------
# command: z_meta_publish_self 

# noinspection PyPep8Naming
class z_meta_publish_self(Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        pass

    @classmethod
    def add_parser(cls):
        subparser = subparsers.add_parser('z_meta_publish_self', help='')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'z_meta_publish_self.Args') -> None:
        # txt =
        with open('/home/wsh/qpy/tespy/c.py') as f:
            txt = f.read()
        txt = re.sub(r'^# -+\n# .*@private.*\n[\s\S]*?(?=# -+)', '', txt, flags=re.MULTILINE)
        txt = re.sub(r'(^# .*)@pub$', r'\1', txt, flags=re.MULTILINE)
        print(txt, end='')
        sys.exit(0)

    @staticmethod
    def test_this() -> None:
        """
        >>> z_meta_publish_self.test_this()
        """
        proc = subprocess.run('c.py -q z_meta_publish_self', shell=True, capture_output=True, text=True, check=True)
        assert proc.stdout.startswith('a_template\n')
        assert proc.stderr == ''


# -----------------------------------------------------------------------------
# main

def main():
    lib.globals_['subparsers'] = subparsers  # export to c_v1.py
    import c_v1  # subparsers.add_parser() v1 commands

    global parser, ARGS_GLOBAL
    args = parser.parse_args()
    ARGS_GLOBAL = ArgsGlobal(**{k: v for k, v in vars(args).items() if k in inspect.signature(ArgsGlobal).parameters}, parser=parser)
    del parser
    if ARGS_GLOBAL.quiet == 1:
        logger.level = logging.INFO
    elif ARGS_GLOBAL.quiet == 2:
        logger.level = logging.WARNING
    elif ARGS_GLOBAL.quiet == 3:
        logger.level = logging.ERROR
    elif ARGS_GLOBAL.quiet >= 4:
        logger.level = logging.CRITICAL
    logger.debug(f'{ARGS_GLOBAL=}')
    del args.quiet
    args.func({k: v for k, v in vars(args).items() if k not in [*inspect.signature(ArgsGlobal).parameters, 'func']})


def test_v1_command():
    """
    >>> test_v1_command()
    """
    # c.py txt_diff2bp
    proc = subprocess.run('echo | c.py txt_diff2bp', shell=True, capture_output=True, text=True, check=True)
    assert proc.stdout == ''
    # [D 22:24:48 c.py:998 main()] ARGS_GLOBAL=ArgsGlobal(...)
    assert re.search(r'^\[D \d{2}:\d{2}:\d{2} c.py:\d+ main\(\)] ARGS_GLOBAL=ArgsGlobal\(.+\)\r?\n', proc.stderr) is not None


if __name__ == '__main__':
    try:
        main()
    # except MyException as e:  # with pydevd_pycharm.settrace(): IndexError: list index out of range
    #     logger.error(e)
    #     sys.exit(1)
    except Exception as e:
        if not isinstance(e, MyException):
            raise e
        logger.error(e)
        sys.exit(1)
