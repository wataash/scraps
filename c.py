#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2020-2025 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""
mini clis

requires python3.13
PyCharm: Doctests in c
or:
DEBUG=1 pytest -v --doctest-modules ~/qpy/tespy/c.py
DEBUG=1 pytest -v --doctest-modules ~/qpy/tespy/c_smux.py
DEBUG=1 pytest -v --doctest-modules ~/qpy/tespy/c_txt.py
"""

import os

if os.environ.get('DEBUG') == '1':
    import pydevd_pycharm
    # Path mappings: /home/wsh/qpy/tespy/c.py=/home/wsh/bin/c.py
    pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True, suspend=False)

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
import pickle
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
# command: a_template

# noinspection PyPep8Naming
class a_template(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        pass

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('a_template', help='', formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
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
        proc = subprocess.run('DEBUG=0 c.py a_template', shell=True, capture_output=True, text=True, check=True)
        assert proc.stdout == ''
        # [D 22:24:48 c.py:998 main()] CLI.args_global=CLI.ArgsGlobal(...)
        assert re.search(r'^\[D \d{2}:\d{2}:\d{2} c.py:\d+ main\(\)] CLI.args_global=CLI.ArgsGlobal\(.+\)\r?\n', proc.stderr) is not None


# -----------------------------------------------------------------------------
# command: fs

import c_fs


# -----------------------------------------------------------------------------
# command: smux

import c_smux

# -----------------------------------------------------------------------------
# command: txt

import c_txt


# -----------------------------------------------------------------------------
# command: yt0

# noinspection PyPep8Naming
class yt0(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        client_secret_json: str
        token_json: str
        video_id: str
        title: str | None
        desc: str | None

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('yt0', help='', formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--client_secret_json', metavar='PATH')
        subparser.add_argument('--token_json', metavar='PATH')
        subparser.add_argument('--video_id', metavar='ID', required=True)
        subparser.add_argument('--title', metavar='TITLE')
        subparser.add_argument('--desc', metavar='DESCRIPTION')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'yt0.Args') -> None:
        logger.debug(f'{args=}')

        if not os.path.exists(args.token_json):
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                args.client_secret_json,
                scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
            )
            credentials = flow.run_local_server(port=0)
            pathlib.Path(args.token_json).write_text(flow.credentials.to_json())
            breakpoint_ = 1
        logger.debug(f'using token_json={args.token_json}')

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        # https://googleapis.github.io/google-api-python-client/docs/oauth.html
        credentials = Credentials.from_authorized_user_file(args.token_json, scopes=["https://www.googleapis.com/auth/youtube.force-ssl"])
        youtube = build("youtube", "v3", credentials=credentials)

        video_response = youtube.videos().list(
            part='snippet',
            id=args.video_id
        ).execute()
        logger.debug(f'{video_response=}')

        if args.title is not None: video_response['items'][0]['snippet']['title'] = args.title
        if args.desc is not None: video_response['items'][0]['snippet']['description'] = args.desc
        update_response = youtube.videos().update(
            part='snippet',
            body={
                'id': args.video_id,
                'snippet': video_response['items'][0]['snippet'],
            }
        ).execute()
        logger.debug(f'{update_response=}')
        logger.info(f'{update_response['snippet']['title']=}')
        logger.info(f'{update_response['snippet']['description']=}')

        sys.exit(0)


# -----------------------------------------------------------------------------
# command: z_meta_command_list

# noinspection PyPep8Naming
class z_meta_command_list(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        pass

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('z_meta_command_list', help='')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'z_meta_command_list.Args') -> None:
        [print(name) for name in CLI.subparsers.choices if name != '----------c_v1.py----------']
        sys.exit(0)

    @staticmethod
    def test_this() -> None:
        """
        >>> z_meta_command_list.test_this()
        """
        proc = subprocess.run('DEBUG=0 c.py -q z_meta_command_list', shell=True, capture_output=True, text=True, check=True)
        assert proc.stdout.startswith('a_template\n')
        assert proc.stderr == ''


# -----------------------------------------------------------------------------
# main

def main():
    import c_archives
    import c_v1  # CLI.subparsers.add_parser() v1 commands

    args = CLI.parser.parse_args()
    CLI.args_global = CLI.ArgsGlobal(**{k: v for k, v in vars(args).items() if k in inspect.signature(CLI.ArgsGlobal).parameters}, parser=CLI.parser)
    if CLI.args_global.quiet == 1:
        logger.level = logging.INFO
    elif CLI.args_global.quiet == 2:
        logger.level = logging.WARNING
    elif CLI.args_global.quiet == 3:
        logger.level = logging.ERROR
    elif CLI.args_global.quiet >= 4:
        logger.level = logging.CRITICAL
    logger.debug(f'{CLI.args_global=}')
    del args.quiet
    args.func({k: v for k, v in vars(args).items() if k not in [*inspect.signature(CLI.ArgsGlobal).parameters, 'func']})


def test_v1_command():
    """
    >>> test_v1_command()
    """
    if os.environ.get('DEBUG') == '1':
        # PyCharm remote debug: どこかで固まってる
        return

    # c.py txt_diff2bp
    proc = subprocess.run('echo | c.py txt_diff2bp', shell=True, capture_output=True, text=True, check=True)
    assert proc.stdout == ''
    # [D 22:24:48 c.py:998 main()] CLI.args_global=CLI.ArgsGlobal(...)
    assert re.search(r'^\[D \d{2}:\d{2}:\d{2} c.py:\d+ main\(\)] CLI.args_global=CLI.ArgsGlobal\(.+\)\r?\n', proc.stderr) is not None


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
