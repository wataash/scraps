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
# EOF
