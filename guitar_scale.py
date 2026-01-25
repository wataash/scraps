# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
"""
python guitar_scale.py gen -h
python guitar_scale.py gen --key=A --scale=m7 --out=Am7.svg
"""

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
import inspect
import io
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
import signal
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tty
import types
import typing as t

import requests


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
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('gen', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=gen)
    subparser.add_argument('--key', required=True, choices=list(ENHARMONICS), type=key_type, help='key')
    group = subparser.add_mutually_exclusive_group(required=True)
    group.add_argument('--notes', nargs=12, help='12 note labels; e.g. .1 ♭9 9 .♭3 3 11 #11 .5 ♭13 13 .♭7 Δ7')
    group.add_argument('--scale', choices=list(SCALE_PRESETS) + list(SCALE_ALIASES), help='scale preset name')
    subparser.add_argument('--out', required=True, help='output file path')

    args = parser.parse_args()
    return args.func(args)


def gen(args: argparse.Namespace) -> int:
    root_key_index = NOTE_INDICES[args.key]
    note_labels_by_index = resolve_notes(args)
    board = build_fretboard()
    render_svg(board, args.out, args.key, args.scale, note_labels_by_index, root_key_index)
    logger.info('wrote %s', args.out)
    return 0


NoteName = t.Literal['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
NoteIndex = int  # 0 ('A') - 11 ('G#')
OPEN_NOTE_INDICES: list[NoteIndex] = [7, 2, 10, 5, 0, 7]
NOTE_INDICES: dict[NoteName, NoteIndex] = {
    'A': 0,
    'A#': 1,
    'B': 2,
    'C': 3,
    'C#': 4,
    'D': 5,
    'D#': 6,
    'E': 7,
    'F': 8,
    'F#': 9,
    'G': 10,
    'G#': 11,
}
ENHARMONICS: dict[str, NoteName] = {
    'Ab': 'G#',
    'A': 'A',
    'A#': 'A#',
    'Bb': 'A#',
    'B': 'B',
    'B#': 'C',
    'Cb': 'B',
    'C': 'C',
    'C#': 'C#',
    'Db': 'C#',
    'D': 'D',
    'D#': 'D#',
    'Eb': 'D#',
    'E': 'E',
    'E#': 'F',
    'Fb': 'E',
    'F': 'F',
    'F#': 'F#',
    'Gb': 'F#',
    'G': 'G',
    'G#': 'G#',
}

def key_type(raw: str) -> NoteName:
    if raw not in ENHARMONICS:
        raise argparse.ArgumentTypeError(f'unknown key: {raw}')
    return ENHARMONICS[raw]

ScaleName = str
# pylint: disable=bad-whitespace
# @formatter:off
SCALE_PRESETS: dict[ScaleName, list[str]] = {
    'M'    : shlex.split(' .1  ♭9  9  ♯9 .3     11  ♯11 .5  ♭13  13  ♭7   Δ7'),
    '6'    : shlex.split(' .1  ♭9  9  ♯9 .3     11  ♯11 .5  ♭6  .6   ♯6   Δ7'),
    '69'   : shlex.split(' .1  ♭9 .9  ♯9 .3     11  ♯11 .5  ♭6  .6   ♯6   Δ7'),
    'M7'   : shlex.split(' .1  ♭9  9  ♯9 .3     11  ♯11 .5  ♭13  13  ♯13 .Δ7'),
    '7'    : shlex.split(' .1  ♭9  9  ♯9 .3     11  ♯11 .5  ♭13  13 .♭7   Δ7'),
    '9'    : shlex.split(' .1  ♭9 .9  ♯9 .3     11  ♯11 .5  ♭13  13 .♭7   Δ7'),
    'm'    : shlex.split(' .1  ♭9  9 .♭3  3     11  ♯11 .5  ♭13  13  ♭7   Δ7'),
    'm6'   : shlex.split(' .1  ♭9  9 .♭3  3     11  ♯11 .5  ♭6  .6   ♯6   Δ7'),
    'm7'   : shlex.split(' .1  ♭9  9 .♭3  3     11  ♯11 .5  ♭13  13 .♭7   Δ7'),
    'mM7'  : shlex.split(' .1  ♭9  9 .♭3  3     11  ♯11 .5  ♭13  13 .♭7  .Δ7'),
    'm9'   : shlex.split(' .1  ♭9 .9 .♭3  3     11  ♯11 .5  ♭13  13 .♭7   Δ7'),
    'hdim' : shlex.split(' .1  ♭9  9 .♭3  3     11 .♭5   5  ♭13  13 .♭7   Δ7'),
    'dim'  : shlex.split(' .1  ♭9  9 .♭3  3     11 .♭5   5  ♭13 .𝄫7  ♭7   Δ7'),
    'mP'   : shlex.split(' .1  ♭9  9 .♭3  3    .4   ♭5  .5  ♭13  13 .♭7   Δ7'),
    'MP'   : shlex.split(' .1  ♭9 .9  ♯9 .3     11  ♯11 .5  ♭13 .13  ♯13  Δ7'),
    'hp5b' : shlex.split(' .1 .♭9  9  ♯9 .3    .11  ♯11 .5 .♭13  13 .♭7   Δ7'),
    'lyd7' : shlex.split(' .1  ♭9 .9  ♯9 .3     11 .♯11 .5  ♭13 .13 .♭7   Δ7'),
    'alt'  : shlex.split(' .1 .♭9  9 .♯9 .3     11 .♯11  5 .♭13  13 .♯13  Δ7'),
    'sloc' : shlex.split(' .1 .♭9  9 .♭3 .♭11  11 .♭5   5 .♭13  13 .♭7   Δ7'),
    'cdim' : shlex.split(' .1 .♭9  9 .♯9 .3     11 .♯11 .5  ♭13 .13 .♭7   Δ7'),
}
# @formatter:on
# pylint: enable=bad-whitespace

SCALE_ALIASES: dict[str, ScaleName] = {
    'hp5': 'hp5b',
    'HP5': 'hp5b',
    'hp5↓': 'hp5b',
    'HP5↓': 'hp5b',
    'maj 7': 'M7',
    'Maj 7': 'M7',
    'maj7': 'M7',
    'Maj7': 'M7',
    'major 7': 'M7',
    'Major 7': 'M7',
    'major pentatonic': 'MP',
    'Major pentatonic': 'MP',
    'Major Pentatonic': 'MP',
    'major7': 'M7',
    'Major7': 'M7',
    'min 7': 'm7',
    'min7': 'm7',
    'minor 7': 'm7',
    'Minor 7': 'm7',
    'minor pentatonic': 'mP',
    'Minor pentatonic': 'mP',
    'Minor Pentatonic': 'mP',
    'minor7': 'm7',
    'Minor7': 'm7',
}


@dataclasses.dataclass(frozen=True)
class NoteLabel:
    text: str
    strong: bool


@dataclasses.dataclass(frozen=True)
class Fretboard:
    normalized_fret_positions: list[float]  # 0.0-1.0
    note_indices: list[list[NoteIndex]]  # [string index (0-5)][fret index (0-24)]


def resolve_notes(args: argparse.Namespace) -> dict[NoteIndex, NoteLabel]:
    if args.notes:
        assert len(args.notes) == 12, f'BUG: {args.notes=}'
        tokens = args.notes
    else:
        scale_key = SCALE_ALIASES.get(args.scale, args.scale)
        tokens = SCALE_PRESETS[scale_key]
    parsed: dict[NoteIndex, NoteLabel] = {}
    for offset, token in enumerate(tokens):
        strong = token.startswith('.')
        text = token[1:] if strong else token
        parsed[offset] = NoteLabel(text=text, strong=strong)
    return parsed


def build_fretboard() -> Fretboard:
    note_indices: list[list[NoteIndex]] = []
    for fret0_index in OPEN_NOTE_INDICES:
        note_indices.append([(fret0_index + fret) % 12 for fret in range(0, 24 + 1)])
    return Fretboard(normalized_fret_positions=calc_normalized_fret_positions(24), note_indices=note_indices)


def calc_normalized_fret_positions(fret_count: int) -> list[float]:
    scale_len = 1.0
    # n フレットまでの距離: L - L / 2^(n/12)。比率で扱うので 0〜(fret_count+1) を計算して正規化する。
    positions = [scale_len - scale_len / (2 ** (n / 12)) for n in range(fret_count + 2)]
    total = positions[-1]
    return [p / total for p in positions]


def render_svg(board: Fretboard, out_path: str, key: str, scale: str | None, note_labels_by_index: dict[NoteIndex, NoteLabel], root_key_index: NoteIndex) -> None:
    fret_label_font_size = 14
    nut_w = 40
    board_w = 1400
    string_gap = 40
    note_radius = 13

    board_h = string_gap * (len(board.note_indices) - 1)
    nut_h = board_h + 30
    label_h = fret_label_font_size + note_radius
    canvas_w = nut_w + board_w
    canvas_h = label_h + board_h + label_h

    fret_xs = [nut_w + board_w * x for x in board.normalized_fret_positions]
    string_ys = [label_h + string_gap * i for i in range(len(board.note_indices))]

    note_color_strong = '#555'
    note_color_weak = '#eee'
    strong_text = '#fff'
    weak_text = '#888'

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}">')
    parts.append('<style>text{font-family:Arial,sans-serif;}</style>')

    parts.append('<!-- nut -->')
    nut_y = (string_ys[0] + string_ys[-1] - nut_h) / 2
    parts.append(f'<rect x="0" y="{nut_y}" width="{nut_w}" height="{nut_h}" fill="#ddd" />')

    parts.append('<!-- frets -->')
    for fret_index, x in enumerate(fret_xs[:-1]):
        if fret_index in {12, 24}:
            parts.append(f'<line x1="{x}" y1="{string_ys[0]}" x2="{x}" y2="{string_ys[-1]}" stroke="#666" stroke-width="3" />')
        else:
            parts.append(f'<line x1="{x}" y1="{string_ys[0]}" x2="{x}" y2="{string_ys[-1]}" stroke="#bbb" stroke-width="1" />')

    parts.append('<!-- fret numbers (top) -->')
    # fret_label_font_size
    top_y = label_h / 2 - note_radius / 2
    # parts.append(f'<rect x="0" y="0" width="{canvas_w}" height="{label_h}" fill="#088" />')  # debug
    for fret_index, x in enumerate(fret_xs[:-1], start=0):
        parts.append(f'<text x="{x}" y="{top_y}" text-anchor="middle" dominant-baseline="middle" fill="#aaa" font-size="{fret_label_font_size}" font-weight="600">{fret_index}</text>')

    parts.append('<!-- fret numbers (bottom) -->')
    bottom_y = label_h + board_h + label_h / 2 + note_radius / 2
    for fret_index, x in enumerate(fret_xs[:-1], start=0):
        parts.append(f'<text x="{x}" y="{bottom_y}" text-anchor="middle" dominant-baseline="middle" fill="#aaa" font-size="{fret_label_font_size}" font-weight="600">{fret_index}</text>')

    parts.append('<!-- strings -->')
    for y in string_ys:
        parts.append(f'<line x1="{fret_xs[0]}" y1="{y}" x2="{fret_xs[-2]}" y2="{y}" stroke="#bbb" stroke-width="1" />')

    parts.append('<!-- inlays -->')
    parts.extend(build_inlays_svg(board, fret_xs, string_ys))

    parts.append('<!-- notes -->')
    for string_index, string_note_indices in enumerate(board.note_indices):
        for note_index, fret_note_index in enumerate(string_note_indices):
            offset = (fret_note_index - root_key_index) % 12
            note = note_labels_by_index[offset]
            if note_index == 0:
                cx = fret_xs[0] - nut_w / 2
            else:
                fret = note_index
                cx = (fret_xs[fret - 1] + fret_xs[fret]) / 2
            cy = string_ys[string_index]
            fill = note_color_strong if note.strong else note_color_weak
            txt_color = strong_text if note.strong else weak_text
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{note_radius}" fill="{fill}" />')
            parts.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" fill="{txt_color}" font-size="16" font-weight="700">{note.text}</text>')

    parts.append('</svg>')
    with open(out_path, 'w') as f:
        f.write('\n'.join(parts))


def build_inlays_svg(board: Fretboard, fret_xs: list[float], string_ys: list[float]) -> list[str]:
    single = {3, 5, 7, 9, 15, 17, 19, 21}
    double = {12, 24}
    y_mid = (string_ys[0] + string_ys[-1]) / 2
    y_spread = string_ys[1] - string_ys[0]
    parts: list[str] = []
    for fret in single:
        cx = (fret_xs[fret - 1] + fret_xs[fret]) / 2
        parts.append(f'<circle cx="{cx}" cy="{y_mid}" r="7" fill="#888" />')
    for fret in double:
        cx = (fret_xs[fret - 1] + fret_xs[fret]) / 2
        parts.append(f'<circle cx="{cx}" cy="{y_mid - y_spread}" r="7" fill="#888" />')
        parts.append(f'<circle cx="{cx}" cy="{y_mid + y_spread}" r="7" fill="#888" />')
    return parts


if __name__ == '__main__':
    raise SystemExit(main())
