#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

r"""
"""

epilog = r'''
usage:
pip install -U playwright
playwright install
google-chrome --remote-debugging-port=59222 --user-data-dir=/var/tmp/pw.59222/ https://www.editor.guitarscientist.com/new
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --help
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --fret_count=24 --fret_width=50  # XXX: inaccurate → 25 45
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --fret_count=23 --fret_width=54  # XXX: inaccurate → 25 50
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --fret_count=22 --fret_width=54  # XXX: inaccurate → 23 50
# [0] 1 | R | 8 [1] ♭2 | ♭9 | ♯1 | ♯8 [2] 2 | 9 | 𝄫3 [3] ♭3 | ♯2 | ♯9 | ♭10 [4] 3 | 10 | ♭4 [5] 4 | 11 | ♯3 | P4 [6] ♭5 | ♯4 | ♯11 | ♭12 [7] 5 | P5 | ×4 [8] ♭6 | ♯5 | ♭13 [9] 6 | 13 | 𝄫7 [10] ♭7 | ♯6 | ♯13 | 7_ [11] 7 | Δ | Δ7 | ×6
# [0] 1
# [1] ♭9
# [2] 9
# [3] ♭3 ♯9
# [4] 3
# [5] 11
# [6] ♭5 ♯11
# [7] 5
# [8] ♭13
# [9] 13
# [10] ♭7 ♯13
# [11] Δ7
# XΔ7 .1 ♭9 9 ♯9 .3 11 ♯11 .5 ♭13 13 ♯13 .Δ7
# X7  .1 ♭9 9 ♯9 .3 11 ♯11 .5 ♭13 13 .♭7 Δ7
# Xm7 .1 ♭9 9 .♭3 3 11 ♯11 .5 ♭13 13 .♭7 Δ7
# XØ  .1 ♭9 9 .♭3 3 11 .♭5 5 ♭13 13 .♭7 Δ7
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --title='A♭Δ7' --key=Ab --intervs .1 ♭9 9 ♯9 .3 11 ♯11 .5 ♭13 13 ♯13 .Δ7 --out=/tmp/abmaj7.png
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --title='A♭7' --key=Ab --intervs .1 ♭9 9 ♯9 .3 11 ♯11 .5 ♭13 13 .♭7 Δ7 --out=/tmp/ab7.png
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --title='A♭m7' --key=Ab --intervs .1 ♭9 9 .♭3 3 11 ♯11 .5 ♭13 13 .♭7 Δ7 --out=/tmp/abm7.png
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --title='A♭Ø' --key=Ab --intervs .1 ♭9 9 .♭3 3 11 .♭5 5 ♭13 13 .♭7 Δ7 --out=/tmp/abhdim.png
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --title='A♭o' --key=Ab --intervs .1 ♭9 9 .♭3 3 11 .♭5 5 ♭13 .𝄫7 ♭7 Δ7 --out=/tmp/abdim.png
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --title='A♭alt.' --key=Ab --intervs .1 .♭9 9 .♯9 .3 11 .♯11 5 .♭13 13 .♯13 Δ7 --out=/tmp/abalt.png
'''

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

from playwright.sync_api import expect, Page, Playwright, sync_playwright


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

"""
<select class="no-arrow" interv="0"><option value="1">1</option><option value="R">R</option><option value="8">8</option>
<select class="no-arrow" interv="1"><option value="♭2">♭2</option><option value="♭9">♭9</option><option value="♯1">♯1</option><option value="♯8">♯8</option>
<select class="no-arrow" interv="2"><option value="2">2</option><option value="9">9</option><option value="𝄫3">𝄫3</option>
<select class="no-arrow" interv="3"><option value="♭3">♭3</option><option value="♯2">♯2</option><option value="♯9">♯9</option><option value="♭10">♭10</option>
<select class="no-arrow" interv="4"><option value="3">3</option><option value="10">10</option><option value="♭4">♭4</option>
<select class="no-arrow" interv="5"><option value="4">4</option><option value="11">11</option><option value="♯3">♯3</option><option value="P4">P4</option>
<select class="no-arrow" interv="6"><option value="♭5">♭5</option><option value="♯4">♯4</option><option value="♯11">♯11</option><option value="♭12">♭12</option>
<select class="no-arrow" interv="7"><option value="5">5</option><option value="P5">P5</option><option value="×4">×4</option>
<select class="no-arrow" interv="8"><option value="♭6">♭6</option><option value="♯5">♯5</option><option value="♭13">♭13</option>
<select class="no-arrow" interv="9"><option value="6">6</option><option value="13">13</option><option value="𝄫7">𝄫7</option>
<select class="no-arrow" interv="10"><option value="♭7">♭7</option><option value="♯6">♯6</option><option value="♯13">♯13</option><option value="7">7</option>
<select class="no-arrow" interv="11"><option value="7">7</option><option value="Δ">Δ</option><option value="Δ7">Δ7</option><option value="×6">×6</option>
"""

pairs_interv_index = {
    '1': 0, 'R': 0, '8': 0,
    '♭2': 1, '♭9': 1, '♯1': 1, '♯8': 1,
    '2': 2, '9': 2, '𝄫3': 2,
    '♭3': 3, '♯2': 3, '♯9': 3, '♭10': 3,
    '3': 4, '10': 4, '♭4': 4,
    '4': 5, '11': 5, '♯3': 5, 'P4': 5,
    '♭5': 6, '♯4': 6, '♯11': 6, '♭12': 6,
    '5': 7, 'P5': 7, '×4': 7,
    '♭6': 8, '♯5': 8, '♭13': 8,
    '6': 9, '13': 9, '𝄫7': 9,
    '♭7': 10, '♯6': 10, '♯13': 10, '7_': -1,  # '7': 10,
    '7': 11, 'Δ': 11, 'Δ7': 11, '×6': 11,
}
pairs_interv_index.update({f'.{k}': v for k, v in pairs_interv_index.copy().items()})
intervs_help = '[0] 1 | R | 8 [1] ♭2 | ♭9 | ♯1 | ♯8 [2] 2 | 9 | 𝄫3 [3] ♭3 | ♯2 | ♯9 | ♭10 [4] 3 | 10 | ♭4 [5] 4 | 11 | ♯3 | P4 [6] ♭5 | ♯4 | ♯11 | ♭12 [7] 5 | P5 | ×4 [8] ♭6 | ♯5 | ♭13 [9] 6 | 13 | 𝄫7 [10] ♭7 | ♯6 | ♯13 | 7_ [11] 7 | Δ | Δ7 | ×6'


def make_int_range_parser(name: str, min_val: int, max_val: int):
    """Create a parser function for integer values within a specified range."""
    def parser(value: str) -> int:
        try:
            num = int(value)
            if min_val <= num <= max_val:
                return num
            raise argparse.ArgumentTypeError(f'{name} must be {min_val}-{max_val}, got {num}')
        except ValueError:
            raise argparse.ArgumentTypeError(f'{name} must be an integer, got {value!r}')
    return parser


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    parser.add_argument('--title')
    parser.add_argument('--key', choices=('C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B'))
    parser.add_argument('--intervs', nargs='+', choices=pairs_interv_index.keys(), help=intervs_help)
    parser.add_argument('--fret_count', type=lambda v: make_int_range_parser('fret_count', 1, 25)(v), help='XXX: inaccurate')
    parser.add_argument('--fret_width', type=lambda v: make_int_range_parser('fret_width', 40, 120)(v), help='XXX: inaccurate')
    parser.add_argument('--out', help='output png file path')

    args = parser.parse_args()
    logger.debug(f'{args=}')
    with sync_playwright() as playwright:
        return main2(playwright, args)


def main2(playwright: Playwright, args: argparse.Namespace) -> int:
    browser = playwright.chromium.connect_over_cdp('http://localhost:59222')
    assert len(browser.contexts) == 1
    context = browser.contexts[0]
    page: Page
    for p in context.pages:
        if p.url == 'https://www.editor.guitarscientist.com/new':
            page = p
            break
    else:
        raise Exception('tab https://www.editor.guitarscientist.com/new not found')

    # page.pause(); return 0

    # open NOTATION
    if 'selected' not in page.locator('div[open_id="automatic_notation"]').get_attribute('class'):
        page.locator('div[open_id="automatic_notation"]').click(timeout=1000)
    # open FINGERINGS
    if 'selected' not in page.locator('div[open_id="fingerings"]').get_attribute('class'):
        page.locator('div[open_id="fingerings"]').click(timeout=1000)
    # open OPTIONS
    if 'selected' not in page.locator('div[open_id="fretboard_settings"]').get_attribute('class'):
        page.locator('div[open_id="fretboard_settings"]').click(timeout=1000)

    # NOTATION > AUTOMATIC NOTATION
    if args.intervs is not None:
        for i, interv in enumerate(args.intervs):
            if interv == '7_' or interv == '.7_':
                logger.debug(f'--interv[{i}]: {interv} mapped to 10(♭7/♯6/♯13/7)')
                interv = interv.removesuffix('_')
            elif interv == '7' or interv == '.7':
                logger.debug(f'--interv[{i}]: {interv} mapped to 11(7/Δ/Δ7/×6)')
            logger.debug(f'{interv=} {pairs_interv_index[interv]=}')
            page.locator(f'#interv_selector select[interv="{pairs_interv_index[interv]}"]').select_option(interv.removeprefix('.'), timeout=1000)

    # FINGERINGS > Scales/Arpeggios > Select key and scale/arpeggio type
    if args.key is not None:
        page.locator('div.tab_title').get_by_text('Scales/Arpeggios', exact=True).click(timeout=1000)
        key_num = {
            'C': '3',
            'C#': '4',
            'Db': '4',
            'D': '5',
            'D#': '6',
            'Eb': '6',
            'E': '7',
            'F': '8',
            'F#': '9',
            'Gb': '9',
            'G': '10',
            'G#': '11',
            'Ab': '11',
            'A': '0',
            'A#': '1',
            'Bb': '1',
            'B': '2',
        }[args.key]
        # page.locator('select[hint="h_select_key"]').highlight()
        page.locator('select[hint="h_select_key"]').first.select_option(key_num, timeout=1000)

    """
    Select structure ::
    Clear all
    - MAJOR SCALE AND ITS MODES - ::
    Ionian | Dorian | Phrygian | Lydian | Mixolydian | Aeolian | Locrian
    - HARMONIC MINOR SCALE AND ITS MODES - ::
    Harmonic Minor | Locrian ♮6 | Ionian #5 | Ukrainian Dorian | Phrygian Dominant | Lydian #2 | Altered Diminished
    - MELODIC MINOR SCALE AND ITS MODES - ::
    Ascending Melodic Minor | Phrygian ♮6 / Dorian b2 | Lydian Augmented | Lydian Dominant | Mixolydian b6 | Half-Diminished | Altered dominant
    - DOUBLE HARMONIC MINOR SCALE AND ITS MODES - ::
    Double Harmonic | Lydian #2 #6 | Phrygian bb7 b4 | Hungarian Minor | Locrian ♮6 ♮3 / Mixolydian b5 b2 | Ionian #5 #2 | Locrian bb3 bb7
    ----- PENTATONIC ---- ::
    Minor pentatonic (Mode V) | Major pentatonic (Mode I) | Pentatonic (Mode II) | Pentatonic (Mode III) | Pentatonic (Mode IV)
    ----- QUADRIADS ---- ::
    Maj 7 | Min 7 | Dominant 7 | Diminished | Min Δ
    ----- TRIADS ---- ::
    Maj | Min | Dim
    ----- OTHER ---- ::
    Blues scale | Gypsy scale | Acoustic scale | Augmented scale | Bebop dominant scale | Enigmatic scale | Flamenco mode |
    Half diminished scale | Harmonic major scale | Hirajoshi scale | Hungarian minor scale | Hungarian major scale |
    In scale | Insen scale | Istrian scale | Iwato scale | Major bebop scale | Major Locrian scale |
    Neapolitan major scale | Neapolitan minor scale | Persian scale | Prometheus scale | Scale of harmonics |
    Tritone scale | Two-semitone tritone scale | Ukrainian Dorian scale | Vietnamese scale of harmonics | Whole tone scale | Yo scale
    """
    page.locator('#scale_structures').select_option('Clear all', timeout=1000)
    # page.locator('#scale_structures').select_option('Lydian', timeout=1000)
    # page.locator('#scale_structures').select_option('Maj 7', timeout=1000)

    # FINGERINGS > Scales/Arpeggios > or input scale structure manually
    if args.intervs is not None:
        for i, interv in enumerate(args.intervs):
            if not interv.startswith('.'):
                continue
            if interv == '7_' or interv == '.7_':
                logger.debug(f'--interv[{i}]: {interv} mapped to 10(♭7/♯6/♯13/7)')
                interv = interv.removesuffix('_')
            elif interv == '7' or interv == '.7':
                logger.debug(f'--interv[{i}]: {interv} mapped to 11(7/Δ/Δ7/×6)')
            logger.debug(f'{interv=}: div.structure-selector[nota="{pairs_interv_index[interv]=}"]')
            page.locator(f'div.structure-selector[nota="{pairs_interv_index[interv]}"]').click(timeout=1000)

    page.get_by_text('Make Full Fretboard Diagram').click(timeout=1000)

    # OPTIONS > Size > LAST FRET
    # OPTIONS > Size > FRET WIDTH
    page.locator('div.tab_title').get_by_text('Size', exact=True).click(timeout=1000)
    if args.fret_count is not None:
        # page.locator('input#fretCount').fill(str(args.fret_count), timeout=1000)  # not work; needs drag
        # Trigger UI update by simulating a drag that reflects the actual value
        box = page.locator('input#fretCount').bounding_box()
        assert box is not None
        # Calculate drag position based on fret_count value (range: 1-25)
        min_, max_ = 1, 25
        ratio = (args.fret_count - min_) / (max_ - min_)
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        page.mouse.down()
        page.mouse.move(box['x'] + box['width'] * ratio, box['y'] + box['height'] / 2)  # XXX: inaccurate
        page.mouse.up()
    if args.fret_width is not None:
        # page.locator('input#fretWidth').fill(str(args.fret_width), timeout=1000)  # not work; needs drag
        # Trigger UI update by simulating a drag that reflects the actual value
        box = page.locator('input#fretWidth').bounding_box()
        assert box is not None
        # Calculate drag position based on fret_width value (range: 40-120)
        min_, max_ = 40, 120
        ratio = (args.fret_width - min_) / (max_ - min_)
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        page.mouse.down()
        page.mouse.move(box['x'] + box['width'] * ratio, box['y'] + box['height'] / 2)  # XXX: inaccurate
        page.mouse.up()

    # OPTIONS > Appearance > FRETBOARD STYLES: 3
    page.locator('div.tab_title').get_by_text('Appearance', exact=True).click(timeout=1000)
    page.locator('div.style_selector[fb_style_n="1"]').click(timeout=1000)

    # OPTIONS > Appearance > Apply black and white filter
    if 'selected-square' not in page.locator('div#black-n-white').get_attribute('class'):
        page.locator('div#black-n-white').click(timeout=1000)

    if args.title is not None:
        page.locator('p.fretboard_title').fill(args.title, timeout=1000)

    if args.out is not None:
        # pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        # page.locator('div.fretboard').highlight()
        # page.locator('div.fretboard').locator('..').highlight()
        page.locator('div.fretboard').locator('..').screenshot(path=args.out, timeout=1000)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
