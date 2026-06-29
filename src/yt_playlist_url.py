#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

epilog = r'''
usage:
python yt_playlist_url.py input.txt
python yt_playlist_url.py input1.txt input2.txt
printf '%s\n' 'https://youtu.be/70SIcpdk_Mo?si=example' | python yt_playlist_url.py
python yt_playlist_url.py --ids-only input.txt
'''[1:]

import argparse
import logging
import re
import sys
import typing as t
import urllib.parse


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
    parser.add_argument('--ids-only', action='store_true', help='Print comma-separated video IDs instead of a watch_videos URL')
    parser.add_argument('--keep-duplicates', action='store_true', help='Keep duplicate video IDs in the extracted order')
    parser.add_argument('--exclude', action='append', default=[], metavar='VIDEO_ID', help='Exclude this video ID from the output (may be repeated)')
    parser.add_argument('input_files', nargs='*', default=['-'], metavar='PATH', help='Text containing YouTube URLs, or - for standard input')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return make_playlist_url(args)


def make_playlist_url(args: argparse.Namespace) -> int:
    video_ids: list[str] = []
    for input_file in args.input_files:
        text = read_input_text(input_file)
        video_ids.extend(extract_youtube_video_ids(text))
    if not args.keep_duplicates:
        video_ids = dedupe_keep_order(video_ids)
    if args.exclude:
        excluded = set(args.exclude)
        video_ids = [v for v in video_ids if v not in excluded]
    if not video_ids:
        logger.error('No YouTube video URLs found')
        return 1
    if args.ids_only:
        print(','.join(video_ids))
    else:
        print(f'https://www.youtube.com/watch_videos?video_ids={",".join(video_ids)}')
    return 0


def read_input_text(input_file: str) -> str:
    if input_file == '-':
        return sys.stdin.read()
    with open(input_file, encoding='utf-8') as f:
        return f.read()


def extract_youtube_video_ids(text: str) -> list[str]:
    video_ids: list[str] = []
    for raw_url in find_url_like_strings(text):
        video_id = get_youtube_video_id(raw_url)
        if video_id is not None:
            video_ids.append(video_id)
    return video_ids


def find_url_like_strings(text: str) -> t.Iterator[str]:
    for match in re.finditer(r'https?://[^\s<>"\']+', text):
        yield match.group(0).rstrip('.,;:)]}')


def get_youtube_video_id(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc in ['youtu.be', 'www.youtu.be']:
        video_id = parsed.path.removeprefix('/').split('/', maxsplit=1)[0]
        return video_id or None
    if netloc in ['youtube.com', 'www.youtube.com', 'm.youtube.com']:
        if parsed.path == '/watch':
            return urllib.parse.parse_qs(parsed.query).get('v', [None])[0]
        if parsed.path.startswith('/shorts/'):
            return parsed.path.removeprefix('/shorts/').split('/', maxsplit=1)[0] or None
        if parsed.path.startswith('/embed/'):
            return parsed.path.removeprefix('/embed/').split('/', maxsplit=1)[0] or None
    return None


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
