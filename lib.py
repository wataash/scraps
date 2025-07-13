#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2020-2025 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""
requires python3.13
"""

from typing import Any, Callable, Iterable, Iterator, Literal
import argparse
import asyncio
import base64
import codecs
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

__all__ = [
    # color
    'can_colorize',
    # logger
    'MyFormatter',
    'logger',
    # lib
    'MyException',
    'CLI',
    'globals_',
    'OrderedSet',
    'TailF',
    'Str',
]

# -----------------------------------------------------------------------------
# color

from typing import IO

# https://github.com/python/cpython/blob/v3.13.3/Lib/_colorize.py
# Copyright © 2001-2024 Python Software Foundation. All rights reserved.
# Copyright © 2000 BeOpen.com. All rights reserved.
# Copyright © 1995-2001 Corporation for National Research Initiatives. All rights reserved.
# Copyright © 1991-1995 Stichting Mathematisch Centrum. All rights reserved.
# Licensed under: https://github.com/python/cpython/blob/main/LICENSE

COLORIZE = True

# types
if False:
    from typing import IO


class ANSIColors:
    RESET = "\x1b[0m"

    BLACK = "\x1b[30m"
    BLUE = "\x1b[34m"
    CYAN = "\x1b[36m"
    GREEN = "\x1b[32m"
    MAGENTA = "\x1b[35m"
    RED = "\x1b[31m"
    WHITE = "\x1b[37m"  # more like LIGHT GRAY
    YELLOW = "\x1b[33m"

    BOLD_BLACK = "\x1b[1;30m"  # DARK GRAY
    BOLD_BLUE = "\x1b[1;34m"
    BOLD_CYAN = "\x1b[1;36m"
    BOLD_GREEN = "\x1b[1;32m"
    BOLD_MAGENTA = "\x1b[1;35m"
    BOLD_RED = "\x1b[1;31m"
    BOLD_WHITE = "\x1b[1;37m"  # actual WHITE
    BOLD_YELLOW = "\x1b[1;33m"

    # intense = like bold but without being bold
    INTENSE_BLACK = "\x1b[90m"
    INTENSE_BLUE = "\x1b[94m"
    INTENSE_CYAN = "\x1b[96m"
    INTENSE_GREEN = "\x1b[92m"
    INTENSE_MAGENTA = "\x1b[95m"
    INTENSE_RED = "\x1b[91m"
    INTENSE_WHITE = "\x1b[97m"
    INTENSE_YELLOW = "\x1b[93m"

    BACKGROUND_BLACK = "\x1b[40m"
    BACKGROUND_BLUE = "\x1b[44m"
    BACKGROUND_CYAN = "\x1b[46m"
    BACKGROUND_GREEN = "\x1b[42m"
    BACKGROUND_MAGENTA = "\x1b[45m"
    BACKGROUND_RED = "\x1b[41m"
    BACKGROUND_WHITE = "\x1b[47m"
    BACKGROUND_YELLOW = "\x1b[43m"

    INTENSE_BACKGROUND_BLACK = "\x1b[100m"
    INTENSE_BACKGROUND_BLUE = "\x1b[104m"
    INTENSE_BACKGROUND_CYAN = "\x1b[106m"
    INTENSE_BACKGROUND_GREEN = "\x1b[102m"
    INTENSE_BACKGROUND_MAGENTA = "\x1b[105m"
    INTENSE_BACKGROUND_RED = "\x1b[101m"
    INTENSE_BACKGROUND_WHITE = "\x1b[107m"
    INTENSE_BACKGROUND_YELLOW = "\x1b[103m"


NoColors = ANSIColors()

for attr in dir(NoColors):
    if not attr.startswith("__"):
        setattr(NoColors, attr, "")


def get_colors(
        colorize: bool = False, *, file: IO[str] | IO[bytes] | None = None
) -> ANSIColors:
    if colorize or can_colorize(file=file):
        return ANSIColors()
    else:
        return NoColors


def can_colorize(*, file: IO[str] | IO[bytes] | None = None) -> bool:
    if file is None:
        file = sys.stdout

    if not sys.flags.ignore_environment:
        if os.environ.get("PYTHON_COLORS") == "0":
            return False
        if os.environ.get("PYTHON_COLORS") == "1":
            return True
    if os.environ.get("NO_COLOR"):
        return False
    if not COLORIZE:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False

    if not hasattr(file, "fileno"):
        return False

    if sys.platform == "win32":
        try:
            import nt

            if not nt._supports_virtual_terminal():
                return False
        except (ImportError, AttributeError):
            return False

    try:
        return os.isatty(file.fileno())
    except io.UnsupportedOperation:
        return hasattr(file, "isatty") and file.isatty()


# -----------------------------------------------------------------------------
# logger

# https://docs.python.org/3/howto/logging.html

class MyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        colors = get_colors(file=sys.stderr)

        color = {
            logging.CRITICAL: colors.RED,
            logging.ERROR: colors.RED,
            logging.WARNING: colors.YELLOW,
            logging.INFO: colors.BLUE,
            logging.DEBUG: colors.WHITE,
        }[record.levelno]
        fn = '' if record.funcName == '<module>' else f' {record.funcName}()'
        fmt = f'{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s{colors.RESET}'
        return logging.Formatter(fmt=fmt, datefmt='%T').format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


# -----------------------------------------------------------------------------
# lib

class MyException(Exception):
    pass


class CLI:
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class ArgsGlobal:
        parser: argparse.ArgumentParser
        quiet: int

    args_global: ArgsGlobal

    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--quiet', action='count', default=0, help='-q to suppress debug; -qq to suppress info; -qqq to suppress warn, -qqqq to suppress error')
    subparsers = parser.add_subparsers(required=True)

    class Cmd:
        classes = []

        def __init_subclass__(cls, **kwargs):
            cls.classes.append(cls)
            cls.add_parser()

    class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
        pass

    @staticmethod
    def validator[T](typer: Callable[[str], T], validate: Callable[[T], bool], errmsg: str) -> Callable[[str], T]:
        r"""
        https://docs.python.org/ja/3/library/argparse.html
        > If the function raises ArgumentTypeError, TypeError, or ValueError, the exception is caught and a nicely formatted error message is displayed. Other exception types are not handled.
        """
        def typer_validate(value: str) -> T:
            value2: T = typer(value)
            if not validate(value2):
                raise argparse.ArgumentTypeError(f"{errmsg}: '{value2}'")
            return value2
        typer_validate.__name__ = typer.__name__  # shown as invalid int/float/etc... value
        return typer_validate

    @staticmethod
    def test_validator():
        """
        >>> CLI.test_validator()
        """
        parser = argparse.ArgumentParser(exit_on_error=False)
        parser.add_argument('--int____', type=int)
        parser.add_argument('--int_pos', type=CLI.validator(int, lambda x: x >= 0, 'must be positive'))
        parser.add_argument('--float_p', type=CLI.validator(float, lambda x: x >= 0, 'must be positive'))
        '''
        int('foo')  #                ValueError: invalid literal for int() with base 10: 'foo'
        --int____=foo  -> PROG.py: error: argument --int____: invalid int value: 'foo'
        --int_pos=foo  -> PROG.py: error: argument --int_pos: invalid int value: 'foo'
        --int_pos=-1   -> PROG.py: error: argument --int_pos: must be positive: '-1'
        --float_p=foo  -> PROG.py: error: argument --float_p: invalid float value: 'foo'
        --float_p=-1.0 -> PROG.py: error: argument --float_p: must be positive: '-1.0'
        '''
        try:
            int('foo')
        except ValueError as e:
            assert str(e) == "invalid literal for int() with base 10: 'foo'", e
        try:
            parser.parse_known_args(['--int____', 'foo'])
        except argparse.ArgumentError as e:
            assert str(e) == "argument --int____: invalid int value: 'foo'", e
        try:
            parser.parse_known_args(['--int_pos', 'foo'])
        except argparse.ArgumentError as e:
            assert str(e) == "argument --int_pos: invalid int value: 'foo'", e
        try:
            parser.parse_known_args(['--int_pos', '-1'])
        except argparse.ArgumentError as e:
            assert str(e) == "argument --int_pos: must be positive: '-1'", e
        try:
            parser.parse_known_args(['--float_p', 'foo'])
        except argparse.ArgumentError as e:
            assert str(e) == "argument --float_p: invalid float value: 'foo'", e
        try:
            parser.parse_known_args(['--float_p', '-1.0'])
        except argparse.ArgumentError as e:
            assert str(e) == "argument --float_p: must be positive: '-1.0'", e
        return

    @staticmethod
    def validate_sha(sha: str) -> str:
        if not re.match(r'^[0-9a-f]{4,40}$', sha):
            raise argparse.ArgumentTypeError(f'invalid sha: {sha}')
        return sha


globals_ = {}


class OrderedSet[T]:
    def __init__(self, iterable: Iterable[T] | None = None):
        self._dict: dict[T, None] = {}
        if iterable:
            for item in iterable:
                self.add(item)

    def __contains__(self, item: T) -> bool:
        return item in self._dict

    def __iter__(self) -> Iterator[T]:
        return iter(self._dict)

    def __len__(self) -> int:
        return len(self._dict)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self._dict)})"

    def __sub__(self, other: Iterable[T]) -> 'OrderedSet[T]':
        return self.difference(other)

    def add(self, item: T) -> None:
        self._dict[item] = None

    def discard(self, item: T) -> None:
        # not tested
        self._dict.pop(item, None)

    def difference(self, other: Iterable[T]) -> 'OrderedSet[T]':
        other_set = set(other)
        return OrderedSet(item for item in self if item not in other_set)

    def intersection(self, other: Iterable[T]) -> 'OrderedSet[T]':
        # not tested
        other_set = set(other)
        return OrderedSet(item for item in self if item in other_set)


    def issubset(self, other: Iterable[T]) -> bool:
        # not tested
        return all(item in other for item in self)

    def issuperset(self, other: Iterable[T]) -> bool:
        # not tested
        return all(item in self for item in other)

    def union(self, other: Iterable[T]) -> 'OrderedSet[T]':
        # not tested
        result = OrderedSet(self)
        for item in other:
            result.add(item)
        return result


# TODO: io.IOBase あたりを継承してフル実装する
class TailF:
    def __init__(self, filename, mode='r'):
        import inotify_simple
        self.filename = filename
        self.mode = mode
        self.f = open(self.filename, self.mode)
        # self.f.seek(0, os.SEEK_END)
        self._inotify = inotify_simple.INotify()
        self._watch = self._inotify.add_watch(self.filename, inotify_simple.flags.MODIFY)

    def __enter__(self):
        return self

    def read(self, size=-1):
        while True:
            data = self.f.read(size)
            if data:
                return data
            if size == 0:
                return data  # '' or b''
            self._inotify.read()

    def close(self):
        if self.f:
            self.f.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class Str:
    @staticmethod
    def snip(s: str, width=100) -> str:
        r"""
        >>> Str.snip('123456789', 3)
        Traceback (most recent call last):
            ...
        ValueError: width must be -1 or greater than 3

        >>> Str.snip('123456789', 4)
        '1...'
        >>> Str.snip('123456789', 5)
        '1...9'
        >>> Str.snip('123456789', 6)
        '12...9'
        >>> Str.snip('123456789', 7)
        '12...89'
        >>> Str.snip('123456789', 8)
        '123...89'
        >>> Str.snip('123456789', 9)
        '123456789'

        >>> Str.snip('123456789', -1)
        '123456789'

        >>> Str.snip('1\r\n3\r\n5\n7\n9', 8)
        '1␍⏎...⏎9'
        """
        # s = s.replace('\n', '␊').replace('\r', '␍')
        s = s.replace('\n', '⏎').replace('\r', '␍')
        if width == -1:
            return s
        if width <= 3:
            raise ValueError('width must be -1 or greater than 3')
        if len(s) <= width:
            return s
        width1 = ((width - len('...') + 1) // 2)
        width2 = ((width - len('...')) // 2)
        return s[:width1] + '...' + s[len(s) - width2:]


@contextlib.contextmanager
def pty_fork(cmd: list[str], ref_exitcode: list[int]) -> typing.Generator[tuple[int, int], None, None]:
        if len(ref_exitcode) != 0:
            raise ValueError('ref_exitcode must be empty list')
        child_pid, ptmx_fd = pty.fork()
        if child_pid == 0:
            os.execvp(cmd[0], cmd)
        try:
            yield child_pid, ptmx_fd
        finally:
            # logger.debug(f'close {ptmx_fd=}')
            os.close(ptmx_fd)
            time.sleep(0.1)
            # logger.info(f'waitpid {child_pid=}')
            pid_waitstatus = os.waitpid(child_pid, os.WNOHANG)
            if pid_waitstatus[0] == 0:
                # TODO: implement waitpid_with_timeout(); timeout まで wait, sleep 1ms, wait, sleep 2ms, wait, sleep 4ms, ...
                # logger.info(f'SIGTERM waitpid {child_pid=}')
                os.kill(child_pid, signal.SIGTERM)
                time.sleep(0.5)
                pid_waitstatus = os.waitpid(child_pid, os.WNOHANG)
                if pid_waitstatus[0] == 0:
                    # logger.info(f'SIGKILL waitpid {child_pid=}')
                    os.kill(child_pid, signal.SIGKILL)
                    time.sleep(0.5)
                    pid_waitstatus = os.waitpid(child_pid, 0)
            assert pid_waitstatus[0] == child_pid
            child_exitcode = os.waitstatus_to_exitcode(pid_waitstatus[1])
            # logger.debug(f'{child_exitcode=}')
            if child_exitcode < 0:
                child_exitcode = 128 + -child_exitcode  # convert signal to exit code
                # logger.debug(f'{child_exitcode=}')
        # ref_exitcode.clear()
        ref_exitcode.append(child_exitcode)
        # return child_exitcode  # contextlib.py: 返り値は捨てられる
        return


@contextlib.contextmanager
def tty_raw(io: typing.IO = sys.stdin) -> typing.Generator[None, None, None]:
    if not io.isatty():
        raise ValueError('io must be a TTY')

    old_tcattr = termios.tcgetattr(io.fileno())
    tty.setraw(io.fileno())

    # ONLCR (\n -> \r\n)
    # tty raw の場合効かないっぽい
    # # ai-generated
    # tmp = termios.tcgetattr(io.fileno())
    # tmp[1] |= termios.ONLCR
    # termios.tcsetattr(io.fileno(), termios.TCSANOW, tmp)
    # stty でも同様
    # subprocess.run('stty onlcr', shell=True, check=True, text=True)
    # stty sane で raw mode が解除されて ONLCR になる

    try:
        yield
    finally:
        termios.tcsetattr(io.fileno(), termios.TCSADRAIN, old_tcattr)


def unreachable() -> typing.Never:
    raise Exception('NOTREACHED')
