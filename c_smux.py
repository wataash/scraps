#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2023-2025 Wataru Ashihara <wataash0607@gmail.com>
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
# command: smux

# noinspection PyPep8Naming
class smux(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        sock: str

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('smux', help='', formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--sock', required=True)
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    @staticmethod
    def main(args: 'smux.Args') -> None:
        logger.debug(f'{args=}')
        if not (sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()):
            logger.error('stdin, stdout, and stderr must be TTYs')
            sys.exit(1)
        logger.info(f'smux: {os.ttyname(sys.stdin.fileno())} {os.getpid()}')
        with lib.tty_raw():
            sys.exit(smux.main1(args=args))

    # OCRNL でないので logger.*() に \r つける

    @staticmethod
    def main1(*, args: 'smux.Args') -> int:
        sel = selectors.DefaultSelector()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(args.sock)
        buf_ref = [b'']
        sel.register(sock, selectors.EVENT_READ, lambda key, mask: smux.read_from_server(key=key, mask=mask, sock=sock, buf_ref=buf_ref))

        sock.send((json.dumps({'type': 'connect', 'pid': os.getpid()}) + '\n').encode())
        sel.register(sys.stdin.fileno(), selectors.EVENT_READ, lambda key, mask: smux.read_local_stdin(key=key, mask=mask, sock=sock))

        signal.signal(signal.SIGWINCH, lambda signum, frame: smux.forward_sigwinch(signum=signum, frame=frame, sock=sock))
        smux.forward_sigwinch(signum=signal.SIGWINCH, frame=None, sock=sock)  # on startup

        try:
            while True:
                for key, mask in sel.select():
                    callback = key.data
                    callback(key, mask)
        finally:
            logger.debug('finally\r')
            sock.close()
            return 0

    @staticmethod
    def forward_sigwinch(*, signum: int, frame: types.FrameType | None, sock: socket.socket) -> None:
        winsize = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, struct.pack('hhhh', 0, 0, 0, 0))
        # logger.info(f'{signum=} {frame=} {winsize.hex()=}')
        data = base64.b64encode(winsize).decode()
        msg = json.dumps({'type': 'winsize', 'data': data}) + '\n'
        sock.send(msg.encode())

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
class smux_server(CLI.Cmd):
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Args:
        sock: str
        cmd: list[str]

    @classmethod
    def add_parser(cls):
        subparser = CLI.subparsers.add_parser('smux_server', help='', formatter_class=CLI.ArgumentDefaultsRawTextHelpFormatter)
        subparser.add_argument('--sock', required=True)
        subparser.add_argument('cmd', nargs='+')
        subparser.set_defaults(func=lambda args: cls(**args))

    def __init__(self, **kwargs):
        self.args = self.Args(**kwargs)
        self.__class__.main(self.args)

    SmuxServerMsg = NewType('SmuxServerMsg', str)

    @staticmethod
    def main(args: 'smux_server.Args') -> None:
        logger.debug(f'{args=}')
        if not (sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()):
            logger.error('stdin, stdout, and stderr must be TTYs')
            sys.exit(1)
        logger.info(f'smux_server: {os.ttyname(sys.stdin.fileno())} {os.getpid()}')
        with lib.tty_raw():
            ref_exitcode = []
            with lib.pty_fork(args.cmd, ref_exitcode) as (child_pid, ptmx_fd):
                smux_server.main1(args=args, ptmx_fd=ptmx_fd, child_pid=child_pid)
            sys.exit(ref_exitcode[0])

    # OCRNL でないので logger.*() に \r つける

    @staticmethod
    def main1(*, args: 'smux_server.Args', ptmx_fd: int, child_pid: int) -> None:
        clients = {}
        clients_buf: dict[socket.socket, bytes] = {}
        sel = selectors.DefaultSelector()

        server_socks = [socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)]
        if os.path.exists(args.sock):
            logger.warning(f'rm {args.sock=}\r')
            os.unlink(args.sock)
        server_socks[0].bind(args.sock)
        server_socks[0].listen()
        # server_socks[0].setblocking(False)

        sel.register(server_socks[0], selectors.EVENT_READ, lambda key, mask: smux_server.accept(
            key=key,
            mask=mask,
            server_sock=server_socks[0],
            sel=sel,
            clients=clients,
            ptmx_fd=ptmx_fd,
            clients_buf=clients_buf,
            child_pid=child_pid))

        sel.register(ptmx_fd, selectors.EVENT_READ, lambda key, mask: smux_server.ev_read_from_child(key=key, mask=mask, sel=sel, clients=clients, clients_buf=clients_buf))
        logger.info(f'child: {os.ptsname(ptmx_fd)} {child_pid}; connect with:\r\n'
                    f'c.py smux --sock {args.sock}\r\n'
                    f'{sys.executable} {sys.argv[0]} smux --sock {args.sock}\r')

        sel.register(sys.stdin.fileno(), selectors.EVENT_READ, lambda key, mask: smux_server.ev_stdin(key=key, mask=mask))

        signal.signal(signal.SIGWINCH, lambda signum, frame: smux_server.apply_sigwinch(signum=signum, frame=frame, ptmx_fd=ptmx_fd, child_pid=child_pid))

        msg = smux_server.SmuxServerMsg('__BUG_IF_SEE_THIS__')

        def loop():
            while True:
                for key, mask in sel.select():
                    # logger.debug(f'{key=}, {mask=}\r')
                    callback = key.data
                    nonlocal msg
                    msg = callback(key, mask)
                    if msg is None:
                        continue
                    logger.info(f'{msg=}\r')
                    if msg.startswith('end:'):
                        logger.info(f'end\r')
                        return
                    if msg.startswith('clients_close_all:'):
                        logger.info(f'clients_close_all\r')
                        for conn, client_pid in clients.items():
                            # send: type=close
                            logger.info(f'conn.send() {conn.fileno()}, {{"type": "close"}}\r')
                            conn.send((json.dumps({'type': 'close'}) + '\n').encode())
                            sel.unregister(conn)
                            conn.close()
                        clients.clear()
                        clients_buf.clear()
                        continue
                    if msg.startswith('clients_list:'):
                        logger.info(f'clients_list\r')
                        for conn, client_pid in clients.items():
                            logger.info(f'{client_pid=} {conn=}\r')
                        continue
                    if msg.startswith('recreate_sock:'):
                        logger.info(f'recreate_sock: {args.sock}\r')
                        # sel.unregister(server_sock)  # TODO: do this if all the clients disconnected from this socket
                        # server_sock.close()  # TODO: ditto
                        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        if os.path.exists(args.sock):
                            logger.warning(f'rm {args.sock=}\r')
                            os.unlink(args.sock)
                        server_sock.bind(args.sock)
                        server_sock.listen()
                        sel.register(server_sock, selectors.EVENT_READ, lambda key, mask: smux_server.accept(
                            key=key,
                            mask=mask,
                            server_sock=server_sock,
                            sel=sel,
                            clients=clients,
                            ptmx_fd=ptmx_fd,
                            clients_buf=clients_buf,
                            child_pid=child_pid))
                        continue
                    lib.unreachable()

        try:
            loop()
            logger.debug('loop() end\r')
        finally:
            logger.debug('finally\r')
            for conn, client_pid in clients.items():
                # send: type=close
                logger.info(f'conn.send() {conn.fileno()}, {{"type": "close"}}\r')
                conn.send((json.dumps({'type': 'close'}) + '\n').encode())
                sel.unregister(conn)
                conn.close()
            for s in server_socks:
                sel.unregister(s)
                s.close()
            os.unlink(args.sock)

        return

    @staticmethod
    def apply_sigwinch(*, signum: int, frame: types.FrameType | None, ptmx_fd: int, child_pid: int) -> None:
        # ai-generated
        winsize = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, struct.pack('hhhh', 0, 0, 0, 0))
        logger.info(f'{signum=} {frame=} {winsize.hex()=}\r')
        fcntl.ioctl(ptmx_fd, termios.TIOCSWINSZ, winsize)
        os.kill(child_pid, signal.SIGWINCH)

    @staticmethod
    def ev_read_from_child(*, key: selectors.SelectorKey, mask: int, sel: selectors.BaseSelector, clients: dict[socket.socket, int], clients_buf: dict[socket.socket, bytes]) -> SmuxServerMsg | None:
        logger.debug(f'{key=} {mask=}\r')
        logger.debug(f'os.read(fd={key.fd}, 1024)\r')
        try:
            out = os.read(key.fd, 1024)
        except OSError as e:
            # e=OSError(5, 'Input/output error') process finished?
            logger.info(f'{e=} process finished?\r')
            return smux_server.SmuxServerMsg(f'end:ev_read_from_child:{e}')
        logger.debug(f'{len(out)=}\r')
        assert len(out) > 0
        dead = []
        for conn, client_pid in clients.items():
            try:
                data = base64.b64encode(out).decode()
                logger.debug(f'conn.send() {conn.fileno()}, {{"type": "stdout", "data": {len(data)=}}}\r')
                conn.send((json.dumps({'type': 'stdout', 'data': data}) + '\n').encode())
            except Exception as _e:
                logger.warning(f'{_e=}\r')
                dead.append((conn, client_pid))
        for conn, client_pid in dead:
            del clients[conn]
            del clients_buf[conn]
            sel.unregister(conn)
            conn.close()
            logger.info(f'Client {client_pid} disconnected\r')
        return None

    # ^C       -> print "^C ^X ^C to exit"
    # ^C ^K ^K -> clients_close_all
    # ^C ^L    -> clients_list
    # ^C ^S    -> recreate_sock
    # ^C ^X ^C -> end
    stdin_state: Literal['init', 'C', 'CK', 'CX', '__BUG_IF_SEE_THIS__'] = 'init'

    @classmethod
    def ev_stdin(cls, *, key: selectors.SelectorKey, mask: int) -> SmuxServerMsg | None:
        assert cls.stdin_state != '__BUG_IF_SEE_THIS__'
        data = os.read(sys.stdin.fileno(), 1)
        if cls.stdin_state == 'CX' and data == b'\x03':
            logger.debug(f'{data=} {cls.stdin_state=} -> CXC; exit\r')
            cls.stdin_state = '__BUG_IF_SEE_THIS__'
            return smux_server.SmuxServerMsg('end:ev_stdin:^C^X^C')
        # ^C ^K
        if cls.stdin_state == 'C' and data == b'\x0b':
            logger.debug(f'{data=} {cls.stdin_state=} -> CK\r')
            cls.stdin_state = 'CK'
            return None
        # ^C ^K ^K
        if cls.stdin_state == 'CK' and data == b'\x0b':
            logger.debug(f'{data=} {cls.stdin_state=} -> CKK; close all clients\r')
            cls.stdin_state = 'init'
            return smux_server.SmuxServerMsg('clients_close_all:ev_stdin:^C^K^K')
        # ^C ^L
        if cls.stdin_state == 'C' and data == b'\x0c':
            logger.debug(f'{data=} {cls.stdin_state=} -> CL; list clients\r')
            cls.stdin_state = 'init'
            return smux_server.SmuxServerMsg('clients_list:ev_stdin:^C^L')
        # ^C ^S
        if cls.stdin_state == 'C' and data == b'\x13':
            logger.debug(f'{data=} {cls.stdin_state=} -> CS; recreate the unix socket\r')
            cls.stdin_state = 'init'
            return smux_server.SmuxServerMsg('recreate_sock:ev_stdin:^C^S')
        # ^C ^X
        if cls.stdin_state == 'C' and data == b'\x18':
            logger.debug(f'{data=} {cls.stdin_state=} -> CX\r')
            cls.stdin_state = 'CX'
            return None
        if data == b'\x03':
            logger.debug(f'{data=} {cls.stdin_state=} -> C\r')
            logger.info(f'^C^K^K to clients_close_all\r')
            logger.info(f'^C^L to clients_list\r')
            logger.info(f'^C^S to recreate_sock\r')
            logger.info(f'^C^X^C to end\r')
            cls.stdin_state = 'C'
            return None
        logger.debug(f'{data=} {cls.stdin_state=} -> init\r')
        cls.stdin_state = 'init'
        return None

    @staticmethod
    def accept(
            *,
            key: selectors.SelectorKey,
            mask: int,
            server_sock: socket.socket,
            sel: selectors.BaseSelector,
            clients: dict[socket.socket, int],
            ptmx_fd: int,
            clients_buf: dict[socket.socket, bytes],
            child_pid: int,
    ) -> str | None:
        conn, _addr = server_sock.accept()
        # conn.setblocking(False)
        clients[conn] = -1
        clients_buf[conn] = b''
        logger.info(f'{key=} {mask=} {ptmx_fd=} {conn.fileno()=} {_addr=}\r')
        sel.register(conn, selectors.EVENT_READ, lambda key, mask: smux_server.read_from_client(
            key=key,
            mask=mask,
            conn=conn,
            sel=sel,
            clients=clients,
            ptmx_fd=ptmx_fd,
            clients_buf=clients_buf,
            child_pid=child_pid))
        return None

    def read_from_client(
            *,
            key: selectors.SelectorKey,
            mask: int,
            conn: socket.socket,
            sel: selectors.BaseSelector,
            clients: dict[socket.socket, int],
            ptmx_fd: int,
            clients_buf: dict[socket.socket, bytes],
            child_pid: int,
    ) -> str | None:
        client_pid = clients[conn]
        logger.debug(f'{key=} {mask=} {conn.fileno()=} {client_pid=}\r')
        data = conn.recv(4096)
        if len(data) == 0:
            # client disconnected
            logger.info(f'{client_pid=} disconnected; {clients_buf[conn]=}\r')
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
                logger.warning(f'short read: {client_pid=} {len(buf)=} {beg=} {end=}\r')
                break
            line = buf[beg:end]
            beg = end + 1
            try:
                msg = json.loads(line.decode())
                if msg['type'] == 'connect':
                    clients[conn] = client_pid = msg['pid']
                    logger.debug(f'{client_pid=} connected\r')
                    continue
                elif msg['type'] == 'stdin':
                    os.write(ptmx_fd, base64.b64decode(msg['data']))
                    continue
                elif msg['type'] == 'winsize':
                    winsize = base64.b64decode(msg['data'])
                    logger.info(f'{client_pid=} winsize update: {winsize.hex()}\r')
                    fcntl.ioctl(ptmx_fd, termios.TIOCSWINSZ, winsize)
                    os.kill(child_pid, signal.SIGWINCH)
                    continue

                    os.kill(os.getpgid(ptmx_fd), signal.SIGWINCH)
                    continue
                logger.warning(f'unknown type from {client_pid=}: {msg=}\r')
            except json.JSONDecodeError as e:
                logger.warning(f'invalid json from {client_pid=}: {e=} {line=}\r')
                continue
        clients_buf[conn] = buf[beg:]
        return None

    @staticmethod
    def test_this() -> None:
        """
        >>> smux_server.test_this()
        """
        if os.environ.get('DEBUG') == '1':
            # PyCharm remote debug: os.read(master_fd, 65536) が返ってこない
            return

        # ^C^X^C

        pid, master_fd = pty.fork()
        if pid == pty.CHILD:
            os.execlp('sh', 'sh', '-c', 'env DEBUG=0 c.py smux_server --sock=/tmp/c.py.test.smux.sock -- cat')
        b = b''
        while re.search(rb'connect with:[\s\S]*smux --sock /tmp/c.py.test.smux.sock', b) is None:
            b += os.read(master_fd, 65536)

        # ^X -> stdin_state='init' -> init
        os.write(master_fd, b'\x18')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='init' -> init" in b

        # ^C -> stdin_state='init' -> C
        os.write(master_fd, b'\x03')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='init' -> C" in b

        # ^C -> stdin_state='C' -> C
        os.write(master_fd, b'\x03')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='C' -> C" in b

        # ^X -> stdin_state='C' -> CX
        os.write(master_fd, b'\x18')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='C' -> CX" in b

        # ^X -> stdin_state='CX' -> init
        os.write(master_fd, b'\x18')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='CX' -> init" in b

        os.write(master_fd, b'\x03')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='init' -> C" in b
        os.write(master_fd, b'\x18')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='C' -> CX" in b
        # ^C -> stdin_state='CX' -> CXC; exit
        os.write(master_fd, b'\x03')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='CX' -> CXC; exit" in b

        pid_waitstatus = os.waitpid(pid, 0)
        assert pid_waitstatus[0] == pid
        assert os.waitstatus_to_exitcode(pid_waitstatus[1]) == 128 + signal.SIGHUP  # 129

        # clients_list clients_close_all

        pid, master_fd = pty.fork()
        if pid == pty.CHILD:
            os.execlp('sh', 'sh', '-c', 'env DEBUG=0 c.py smux_server --sock=/tmp/c.py.test.smux.sock -- cat')
        b = b''
        while re.search(rb'connect with:[\s\S]*smux --sock /tmp/c.py.test.smux.sock', b) is None:
            b += os.read(master_fd, 65536)
        client_pid, client_master_fd = pty.fork()
        if client_pid == pty.CHILD:
            os.execlp('sh', 'sh', '-c', 'env DEBUG=0 c.py smux --sock=/tmp/c.py.test.smux.sock')
        b = b''
        while re.search(rb'main', b) is None:
            b += os.read(client_master_fd, 65536)

        b = os.read(master_fd, 65536)
        assert rb'accept' in b

        os.write(master_fd, b'\x03\x0c')  # ^C ^L
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='C' -> CL" in b
        assert rb'clients_list' in b
        assert rb'client_pid=' in b

        os.write(master_fd, b'\x03\x0b\x0b')  # ^C ^K ^K
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='C' -> CK" in b
        assert rb'clients_close_all:ev_stdin:^C^K^K' in b

        os.write(master_fd, b'\x03\x0c')  # ^C ^L
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='C' -> CL" in b
        assert rb'clients_list' in b
        assert not rb'client_pid=' in b

        pid_waitstatus = os.waitpid(client_pid, 0)
        assert pid_waitstatus[0] == client_pid
        assert os.waitstatus_to_exitcode(pid_waitstatus[1]) == 0

        os.write(master_fd, b'\x03\x18\x03')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='CX' -> CXC; exit" in b
        pid_waitstatus = os.waitpid(pid, 0)
        assert pid_waitstatus[0] == pid
        assert os.waitstatus_to_exitcode(pid_waitstatus[1]) == 128 + signal.SIGHUP  # 129

        # recreate_sock

        pid, master_fd = pty.fork()
        if pid == pty.CHILD:
            os.execlp('sh', 'sh', '-c', 'env DEBUG=0 c.py smux_server --sock=/tmp/c.py.test.smux.sock -- cat')
        b = b''
        while re.search(rb'connect with:[\s\S]*smux --sock /tmp/c.py.test.smux.sock', b) is None:
            b += os.read(master_fd, 65536)
        assert os.path.exists('/tmp/c.py.test.smux.sock')
        os.unlink('/tmp/c.py.test.smux.sock')
        assert not os.path.exists('/tmp/c.py.test.smux.sock')
        os.write(master_fd, b'\x03\x13')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb'recreate_sock: /tmp/c.py.test.smux.sock' in b
        assert os.path.exists('/tmp/c.py.test.smux.sock')

        os.write(master_fd, b'\x03\x18\x03')
        time.sleep(0.01)
        b = os.read(master_fd, 65536)
        assert rb"stdin_state='CX' -> CXC; exit" in b
        pid_waitstatus = os.waitpid(pid, 0)
        assert pid_waitstatus[0] == pid
        assert os.waitstatus_to_exitcode(pid_waitstatus[1]) == 128 + signal.SIGHUP  # 129

        breakpoint_ = 1

# -----------------------------------------------------------------------------
# EOF
