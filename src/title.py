#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
GDK_BACKEND=x11 python title.py HELLO
GDK_BACKEND=x11 python title.py 'good morning' --font-size 96
'''[1:]

# Wayland/mutter ではクライアントから alt-tab 除外を指示する標準的手段がないため
# XWayland 経由 (GDK_BACKEND=x11) で _NET_WM_WINDOW_TYPE_UTILITY を付ける。
# mutter は utility/dock/splash 型を alt-tab から除外する。

import argparse
import logging
import tkinter as tk


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
    parser.add_argument('text', help='window content text')
    parser.add_argument('--font-size', type=int, default=48)
    parser.add_argument('--title', default='title.py', help='window title')
    args = parser.parse_args()
    logger.debug(f'{args=}')
    return show(args)


def show(args: argparse.Namespace) -> int:
    root = tk.Tk()
    root.title(args.title)
    try:
        root.attributes('-type', 'utility')
    except tk.TclError as e:
        logger.warning(f'-type utility not applied (non-X11?): {e}')
    tk.Label(root, text=args.text, font=('Sans', args.font_size)).pack(padx=40, pady=40)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
