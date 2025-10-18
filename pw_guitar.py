#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""
usage:
pip install playwright
playwright install
google-chrome --remote-debugging-port=59222 --user-data-dir=/var/tmp/pw.59222/ https://www.editor.guitarscientist.com/new
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --help
# [0]1 [1]b9 [2]9 [3]#9/m3 [4]3 [5]11 [6]#11/b5 [7]5 [8]b13 [9]13 [10]#13/m7 [11]^7
# X△7 [0]1 [4]3 [7]5 [11]^7
# X7  [0]1 [4]3 [7]5 [10]m7
# Xm7 [0]1 [3]m3 [7]5 [10]m7
# XØ  [0]1 [3]m3 [6]b5 [7]5 [10]m7
python /home/wsh/qpy/tespy/tespy/pw/pw_guitar.py --title='Ab△7' --key=Ab --nota 0 4 7 11 --out=/tmp/abmaj7.png
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


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


def main() -> None:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    parser.add_argument('--title')
    parser.add_argument('--key', required=True, choices=['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'])
    parser.add_argument('--nota', type=int, nargs='+', required=True, choices=range(12), help='[0]1 [1]b9 [2]9 [3]#9 [4]3 [5]11 [6]#11 [7]5 [8]b13 [9]13 [10]#13 [11]^7')
    parser.add_argument('--fret_count', type=int, default=24, help=argparse.SUPPRESS)  # BUG: not changed
    parser.add_argument('--fret_width', type=int, default=50, help=argparse.SUPPRESS)  # BUG: not changed
    parser.add_argument('--out', help='output png file path')
    args = parser.parse_args()

    with sync_playwright() as playwright:
        main2(playwright, args.title, args.key, args.nota, args.fret_count, args.fret_width, args.out)


def main2(playwright: Playwright, title: str | None, key: t.Literal['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'],
          nota_indices: list[int], fret_count: int, fret_width: int, output_path: str | None) -> None:
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

    # page.pause(); sys.exit(0)

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
    # <div id="interv_selector">
    #   <div class="black_keys">             <select interv="1"> <select interv="3">                      <select interv="6"> <select interv="8">  <select interv="10">
    #   <div class="white_keys"> <select interv="0"> <select interv="2">  <select interv="4"> <select interv="5"> <select interv="7"> <select interv="9"> <select interv="11">
    #  b9 #9 #9  #11 b13  #13
    # 1  9  3  11   5   13   △7
    page.locator('#interv_selector select[interv="0"]').select_option('1', timeout=1000)
    page.locator('#interv_selector select[interv="1"]').select_option('♭9', timeout=1000)
    page.locator('#interv_selector select[interv="2"]').select_option('9', timeout=1000)
    page.locator('#interv_selector select[interv="3"]').select_option('♯9', timeout=1000)
    page.locator('#interv_selector select[interv="4"]').select_option('3', timeout=1000)
    page.locator('#interv_selector select[interv="5"]').select_option('11', timeout=1000)
    page.locator('#interv_selector select[interv="6"]').select_option('♯11', timeout=1000)
    page.locator('#interv_selector select[interv="7"]').select_option('5', timeout=1000)
    page.locator('#interv_selector select[interv="8"]').select_option('♭13', timeout=1000)
    page.locator('#interv_selector select[interv="9"]').select_option('13', timeout=1000)
    page.locator('#interv_selector select[interv="10"]').select_option('♯13', timeout=1000)
    page.locator('#interv_selector select[interv="11"]').select_option('Δ7', timeout=1000)

    # FINGERINGS > Scales/Arpeggios > Select key and scale/arpeggio type
    page.locator('div.tab_title').get_by_text('Scales/Arpeggios', exact=True).click(timeout=1000)
    key_num = {
        'C': '3',
        'Db': '4',
        'D': '5',
        'Eb': '6',
        'E': '7',
        'F': '8',
        'F#': '9',
        'Gb': '9',
        'G': '10',
        'Ab': '11',
        'A': '0',
        'Bb': '1',
        'B': '2',
    }[key]
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
    for ni in nota_indices:
        page.locator(f'div.structure-selector[nota="{ni}"]').click(timeout=1000)

    page.get_by_text('Make Full Fretboard Diagram').click(timeout=1000)

    if False:
        # BUG: not changed
        # OPTIONS > Size > LAST FRET
        # OPTIONS > Size > FRET WIDTH
        page.locator('div.tab_title').get_by_text('Size', exact=True).click(timeout=1000)
        page.locator('input#fretCount').fill(str(fret_count), timeout=1000)
        page.locator('input#fretWidth').fill(str(fret_width), timeout=1000)

    # OPTIONS > Appearance > FRETBOARD STYLES: 3
    page.locator('div.tab_title').get_by_text('Appearance', exact=True).click(timeout=1000)
    page.locator('div.style_selector[fb_style_n="1"]').click(timeout=1000)

    # OPTIONS > Appearance > Apply black and white filter
    if 'selected-square' not in page.locator('div#black-n-white').get_attribute('class'):
        page.locator('div#black-n-white').click(timeout=1000)

    if title is not None:
        page.locator('p.fretboard_title').fill(title, timeout=1000)

    if output_path is not None:
        # pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        # page.locator('div.fretboard').highlight()
        # page.locator('div.fretboard').locator('..').highlight()
        page.locator('div.fretboard').locator('..').screenshot(path=output_path, timeout=1000)


if __name__ == '__main__':
    main()
    sys.exit(0)
