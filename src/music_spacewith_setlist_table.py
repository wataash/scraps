#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
music_spacewith_setlist_table.py -h
music_spacewith_setlist_table.py md -h
music_spacewith_setlist_table.py md --photos_json_dir=photos_json/ < setlist.md
music_spacewith_setlist_table.py gen_photos_update_cmds --photos_json_dir=photos_json/ --shared_album_map=albums.tsv --connect_url=http://localhost:59222 --title='{yt_url}{NL}2026-06-09 Tue {entry}' --setlist_md=setlist.md
music_spacewith_setlist_table.py messages --shared_album_map=albums.tsv --setlist_md=setlist.md
music_spacewith_setlist_table.py gen_yt_update_cmds --title='2026-06-09 Tue {entry}' --desc='2026-06-09 Tue session{NL}{entry}{NL}{parts}' < setlist.md
'''[1:]

import argparse
import json
import logging
import pathlib
import re
import shlex
import sys
import typing as t
import unicodedata
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
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('md', help='read setlist from stdin, print markdown table to stdout', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=md)
    subparser.add_argument('--photos_json_dir', required=True, help='directory of <photo_id>.json (with "photo_url" and "details"."duration");\nused for the photos_len column')

    subparser = subparsers.add_parser('gen_photos_update_cmds', help='print pw_google_photos.py commands to update photo descriptions and albums', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=gen_photos_update_cmds)
    subparser.add_argument('--photos_json_dir', required=True, help='directory of <photo_id>.json (with "photo_url" and "details"."duration");\nalso the redirect target of the generated get_info commands')
    subparser.add_argument('--shared_album_map', required=True, help='TSV with a header row: shared_album_url<TAB>band_name<TAB>shared_album_name;\nused for the generated add_to_album commands')
    subparser.add_argument('--connect_url', required=True, help='passed through to pw_google_photos.py --connect_url (e.g. http://localhost:59222)')
    subparser.add_argument('--connect_use_tab_url_start', default='https://photos.google.com/', help='passed through to pw_google_photos.py --connect_use_tab_url_start')
    subparser.add_argument('--title', required=True, help="description template; {length} {entry} {photos_url} {yt_len} {yt_url} {parts} {NL} (newline) are replaced\n(e.g. '{yt_url}{NL}2026-06-09 Tue {entry}')")
    subparser.add_argument('--setlist_md', required=True, help='setlist file (markdown table)')

    subparser = subparsers.add_parser('messages', help='print a message for each shared album (album name, share URL, then "yt_url entry" lines)', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=messages)
    subparser.add_argument('--shared_album_map', required=True, help='TSV with a header row: shared_album_url<TAB>band_name<TAB>shared_album_name')
    subparser.add_argument('--setlist_md', required=True, help='setlist file (markdown table)')

    subparser = subparsers.add_parser('gen_yt_update_cmds', help='read setlist from stdin, print yt_.py commands to update video titles and descriptions', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=gen_yt_update_cmds)
    subparser.add_argument('--title', required=True, help="title template; {length} {entry} {photos_url} {yt_len} {yt_url} {parts} {NL} (newline) are replaced\n(e.g. '2026-06-09 Tue {entry}')")
    subparser.add_argument('--desc', required=True, help="description template; same placeholders as --title\n(e.g. '2026-06-09 Tue session{NL}{entry}{NL}{parts}')")

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return args.func(args)


INSTRUMENTS = ('vo', 'gt', 'ba', 'dr', 'key')


def disp_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


def to_seconds(mmss: str) -> int:
    seconds = 0
    for part in mmss.split(':'):
        seconds = seconds * 60 + int(part)
    return seconds


def parse_setlist(photos_json_dir: str | None, file: t.TextIO) -> tuple[list[tuple[str, str, str, str, str, str, dict[str, list[str]]]], bool]:
    durations: dict[str, str] = {}  # photo_url -> duration ('5:20')
    for path in sorted(pathlib.Path(photos_json_dir).expanduser().glob('*.json')) if photos_json_dir is not None else []:
        data = json.loads(path.read_text())
        if 'photo_url' not in data:
            logger.warning(f'{path}: no "photo_url" key; skipping')
            continue
        durations[data['photo_url']] = data.get('details', {}).get('duration') or ''

    rows: list[tuple[str, str, str, str, str, str, dict[str, list[str]]]] = []
    ok = True
    header_seen = False
    for lineno, line in enumerate(file, 1):
        line = line.rstrip('\n')
        if line.strip() == '':
            continue
        if not header_seen:  # first non-blank line is the header row
            header_seen = True
            continue
        if re.fullmatch(r'[-| :]+', line):  # separator row
            continue
        parts = line.removeprefix('|').split('|')
        if len(parts) != 6:
            logger.error(f'line {lineno}: expected "| length | entry | photos_url | yt_len | yt_url | parts": {line!r}')
            ok = False
            continue
        length, entry, photos_url, yt_len, yt_url, members = parts
        length = length.strip()
        entry = entry.strip()
        photos_url = photos_url.strip()
        yt_len = yt_len.strip()
        yt_url = yt_url.strip()
        if re.fullmatch(r'(\d+:\d{2})?', length) is None:
            logger.error(f'line {lineno}: invalid length (expected M:SS or empty): {length!r}')
            ok = False
            continue
        if ' ' in photos_url:
            logger.error(f'line {lineno}: photos_url contains whitespace: {photos_url!r}')
            ok = False
            continue
        if re.fullmatch(r'(\d+:\d{2}:\d{2})?', yt_len) is None:
            logger.error(f'line {lineno}: invalid yt_len (expected H:MM:SS or empty): {yt_len!r}')
            ok = False
            continue
        if ' ' in yt_url:
            logger.error(f'line {lineno}: yt_url contains whitespace: {yt_url!r}')
            ok = False
            continue
        photos_len = ''
        if photos_url != '' and photos_json_dir is not None:
            if photos_url in durations:
                photos_len = durations[photos_url]
            else:
                logger.warning(f'line {lineno}: no json for {photos_url}')
        if length != '' and photos_len != '':
            if to_seconds(length) > to_seconds(photos_len):
                logger.error(f'line {lineno}: length {length} > photos_len {photos_len}')
                ok = False
            elif to_seconds(photos_len) - to_seconds(length) > 1:
                logger.error(f'line {lineno}: photos_len {photos_len} - length {length} > 1s')
                ok = False
        if length != '' and yt_len != '':
            if to_seconds(length) > to_seconds(yt_len):
                logger.error(f'line {lineno}: length {length} > yt_len {yt_len}')
                ok = False
            elif to_seconds(yt_len) - to_seconds(length) > 1:
                logger.error(f'line {lineno}: yt_len {yt_len} - length {length} > 1s')
                ok = False
        insts: dict[str, list[str]] = {inst: [] for inst in INSTRUMENTS}
        prev_idx = -1
        for token in members.split():
            inst, sep, name = token.partition(':')
            if sep == '' or inst not in INSTRUMENTS or name == '':
                logger.error(f'line {lineno}: unknown instrument: {token!r}')
                ok = False
                continue
            idx = INSTRUMENTS.index(inst)
            if idx < prev_idx:
                logger.error(f'line {lineno}: instruments not in {" ".join(INSTRUMENTS)} order: {members.strip()!r}')
                ok = False
            prev_idx = idx
            insts[inst].append(name)
        rows.append((length, entry, photos_len, photos_url, yt_len, yt_url, insts))
    return rows, ok


def md(args: argparse.Namespace) -> int:
    rows, ok = parse_setlist(args.photos_json_dir, sys.stdin)
    if not ok:
        return 1

    n_cols = {inst: max([len(insts[inst]) for *_, insts in rows] + [1]) for inst in INSTRUMENTS}
    header = ['length', 'entry'] + [inst for inst in INSTRUMENTS for _ in range(n_cols[inst])] + ['photos_len', 'photos_url', 'yt_len', 'yt_url']
    cell_rows = []
    for length, entry, photos_len, photos_url, yt_len, yt_url, insts in rows:
        cells = [length, entry]
        for inst in INSTRUMENTS:
            cells += insts[inst] + [''] * (n_cols[inst] - len(insts[inst]))
        cells += [photos_len, photos_url, yt_len, yt_url]
        cell_rows.append(cells)

    widths = [max(disp_width(cell) for cell in col) for col in zip(header, *cell_rows)]

    def fmt(cells: list[str]) -> str:
        return '| ' + ' | '.join(cell + ' ' * (w - disp_width(cell)) for cell, w in zip(cells, widths)) + ' |'

    print(fmt(header))
    print('|' + '|'.join('-' * (w + 2) for w in widths) + '|')
    for cells in cell_rows:
        print(fmt(cells))
    return 0


def youtube_video_id(yt_url: str) -> str | None:
    parsed = urllib.parse.urlparse(yt_url)
    if parsed.netloc in ('youtu.be', 'www.youtu.be'):
        return parsed.path.removeprefix('/') or None
    if parsed.netloc in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        return urllib.parse.parse_qs(parsed.query).get('v', [None])[0]
    return None


def google_photos_photo_id(photos_url: str) -> str | None:
    parts = [part for part in urllib.parse.urlparse(photos_url).path.split('/') if part]
    if len(parts) >= 2 and parts[0] == 'photo':
        return parts[1]
    return None


def sh_quote_multiline(s: str) -> str:
    segments = s.split('\n')
    if len(segments) == 1:
        return shlex.quote(s)
    return '"$(printf "%s\\n" ' + ' '.join(shlex.quote(segment) for segment in segments) + ')"'  # $(...) strips the trailing newline


def format_template(template: str, length: str, entry: str, photos_url: str, yt_len: str, yt_url: str, insts: dict[str, list[str]]) -> str:
    parts = ' '.join(f'{inst}:{name}' for inst in INSTRUMENTS for name in insts[inst])
    return template.format(NL='\n', length=length, entry=entry, photos_url=photos_url, yt_len=yt_len, yt_url=yt_url, parts=parts)


def read_shared_album_map(path: str) -> dict[str, tuple[str, str, str]]:  # band_name -> (shared_album_url, shared_album_name, message_via)
    album_map: dict[str, tuple[str, str, str]] = {}
    lines = pathlib.Path(path).expanduser().read_text().splitlines()
    for lineno, line in enumerate(lines[1:], 2):  # skip the header row
        if line.strip() == '':
            continue
        parts = line.split('\t')
        assert len(parts) == 4, f'{path}:{lineno}: expected "shared_album_url<TAB>band_name<TAB>shared_album_name<TAB>message_via": {line!r}'
        shared_album_url, band_name, shared_album_name, message_via = parts
        album_map[band_name] = (shared_album_url, shared_album_name, message_via)
    return album_map


def gen_photos_update_cmds(args: argparse.Namespace) -> int:
    album_map = read_shared_album_map(args.shared_album_map)
    with open(pathlib.Path(args.setlist_md).expanduser()) as file:
        rows, ok = parse_setlist(args.photos_json_dir, file)
    if not ok:
        return 1

    lines = []
    warned_names = set()
    for length, entry, photos_len, photos_url, yt_len, yt_url, insts in rows:
        if photos_url == '':
            continue
        photo_id = google_photos_photo_id(photos_url)
        if photo_id is None:
            logger.error(f'cannot extract photo id: {photos_url!r}')
            ok = False
            continue
        try:
            title = format_template(args.title, length, entry, photos_url, yt_len, yt_url, insts)
        except (KeyError, IndexError) as e:
            logger.error(f'--title: unknown placeholder: {e}')
            return 1
        albums = []
        for inst in INSTRUMENTS:
            for name in insts[inst]:
                if name not in album_map:
                    if name not in warned_names:
                        logger.warning(f'no shared album for: {name}')
                        warned_names.add(name)
                elif album_map[name][1] not in albums:
                    albums.append(album_map[name][1])
        common = f'--connect_url={shlex.quote(args.connect_url)} --connect_use_tab_url_start={shlex.quote(args.connect_use_tab_url_start)}'
        json_path = args.photos_json_dir.rstrip('/') + '/' + photo_id + '.json'  # not shlex.quote()d to keep ~ expandable
        lines.append(f'pw_google_photos.py {"set_descr".ljust(12)} {common} {shlex.quote(photos_url)} {sh_quote_multiline(title)}')
        if albums:
            lines.append(f'pw_google_photos.py {"add_to_album".ljust(12)} {common} {shlex.quote(photos_url)} ' + ' '.join(shlex.quote(album) for album in albums))
        lines.append(f'pw_google_photos.py {"get_info".ljust(12)} {common} {shlex.quote(photos_url)} > {json_path}')
    if not ok:
        return 1
    for line in lines:
        print(line)
    return 0


def messages(args: argparse.Namespace) -> int:
    album_map = read_shared_album_map(args.shared_album_map)
    with open(pathlib.Path(args.setlist_md).expanduser()) as file:
        rows, ok = parse_setlist(None, file)
    if not ok:
        return 1

    blocks = []
    for band_name, (album_url, album_name, message_via) in album_map.items():
        songs = []
        for length, entry, photos_len, photos_url, yt_len, yt_url, insts in rows:
            if yt_url == '':
                continue
            if any(band_name in names for names in insts.values()):
                songs.append(f'{yt_url} {entry}')
        if songs:
            blocks.append('\n'.join([f'# {album_name} | {message_via}', album_url] + songs + ['（非公開アップロードです）']))
    print('\n\n'.join(blocks))
    return 0


def gen_yt_update_cmds(args: argparse.Namespace) -> int:
    rows, ok = parse_setlist(None, sys.stdin)
    if not ok:
        return 1

    lines = []
    for length, entry, photos_len, photos_url, yt_len, yt_url, insts in rows:
        if yt_url == '':
            continue
        video_id = youtube_video_id(yt_url)
        if video_id is None:
            logger.error(f'cannot extract video id: {yt_url!r}')
            ok = False
            continue
        try:
            title = format_template(args.title, length, entry, photos_url, yt_len, yt_url, insts)
            desc = format_template(args.desc, length, entry, photos_url, yt_len, yt_url, insts)
        except (KeyError, IndexError) as e:
            logger.error(f'--title/--desc: unknown placeholder: {e}')
            return 1
        lines.append(f'yt_.py set_meta --video_id={shlex.quote(video_id)} --title={sh_quote_multiline(title)} --desc={sh_quote_multiline(desc)}')
    if not ok:
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
