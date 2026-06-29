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
import sys
import tkinter as tk


try:
    from _colorize import get_colors  # Python 3.13+ (private API)
except ImportError:
    class _NoColors:
        RED = YELLOW = BLUE = WHITE = RESET = ""

    def get_colors(colorize=False, *, file=None):  # type: ignore[misc]
        return _NoColors


class MyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        c = get_colors(file=sys.stderr)
        color = {
            logging.CRITICAL: c.RED,
            logging.ERROR: c.RED,
            logging.WARNING: c.YELLOW,
            logging.INFO: c.BLUE,
            logging.DEBUG: c.WHITE,
        }[record.levelno]
        fn = '' if record.funcName == '<module>' else f' {record.funcName}()'
        fmt = f'{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s{c.RESET}'
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
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    parser.add_argument('text', help='window content text')
    parser.add_argument('--font-size', type=int, default=48)
    parser.add_argument('--title', default='title.py', help='window title')
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return show(args)


def show(args: argparse.Namespace) -> int:
    root = tk.Tk()
    root.title(args.title)
    try:
        root.attributes('-type', 'utility')
    except tk.TclError as e:
        logger.warning(f'-type utility not applied (non-X11?): {e}')
    font = ('Sans', args.font_size)
    label = tk.Label(root, text=args.text, font=font)
    entry = tk.Entry(root, font=font, borderwidth=0, highlightthickness=0, justify='center')
    label.pack(padx=40, pady=40)

    def to_edit(_event: tk.Event) -> None:
        entry.delete(0, tk.END)
        entry.insert(0, label.cget('text'))
        label.pack_forget()
        entry.pack(padx=40, pady=40)
        entry.focus_set()
        entry.select_range(0, tk.END)

    def to_label(_event: tk.Event) -> None:
        label.config(text=entry.get())
        entry.pack_forget()
        label.pack(padx=40, pady=40)

    label.bind('<Button-1>', to_edit)
    entry.bind('<Return>', to_label)
    entry.bind('<Escape>', to_label)
    entry.bind('<FocusOut>', to_label)

    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
