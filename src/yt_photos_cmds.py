#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

epilog = r'''
usage:
python yt_photos_cmds.py gen_update_cmds /tmp/in.txt
python yt_photos_cmds.py gen_update_cmds --yt_desc="$(printf "%s\n" "line1" "line2")" /tmp/in.txt
python yt_photos_cmds.py album_to_yt /tmp/in.txt
'''[1:]

import argparse
import json
import logging
import os
import pathlib
import shlex
import sys
import typing as t
import urllib.parse


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
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('gen_update_cmds', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Generate shell commands from photo/youtube/title lines')
    subparser.set_defaults(func=gen_update_cmds)
    subparser.add_argument('--connect_url', default='http://localhost:59222')
    subparser.add_argument('--connect_use_tab_url_start', default='https://photos.google.com/')
    subparser.add_argument('--info_out_dir', default='~/docn/photos')
    subparser.add_argument('--yt_desc', help='YouTube description to pass to yt_.py set_meta --desc')
    subparser.add_argument('input_file', nargs='?', type=argparse.FileType('r'), default=sys.stdin)

    subparser = subparsers.add_parser('album_to_yt', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Group photo/youtube/title lines by albums using ~/docn/photos JSON')
    subparser.set_defaults(func=album_to_yt)
    subparser.add_argument('--photos_json_dir', default=os.path.expanduser('~/docn/photos'))
    subparser.add_argument('input_file', nargs='?', type=argparse.FileType('r'), default=sys.stdin)

    args = parser.parse_args()
    logger.debug(f'{args=}')
    return args.func(args)


def gen_update_cmds(args: argparse.Namespace) -> int:
    records = []
    for line in args.input_file:
        if not line.strip():
            continue
        record = parse_update_line_relaxed(line)
        if record is None:
            logger.debug(f'skip unrelated line {line.rstrip()!r}')
            continue
        records.append(record)
    photo_script_path = 'pw_google_photos.py'
    youtube_script_path = 'yt_.py'
    for record in records:
        print(make_set_youtube_meta_cmd(youtube_script_path, args, record))
    print()
    for record in records:
        print(make_set_descr_cmd(photo_script_path, args, record))
    print()
    for record in records:
        print(make_get_info_cmd(photo_script_path, args, record))
    return 0


def album_to_yt(args: argparse.Namespace) -> int:
    album_records, photo_records = parse_album_and_photo_sections(args.input_file)
    photos_json_dir = pathlib.Path(args.photos_json_dir)
    photo_jsons = {}
    for record in photo_records:
        photo_json = load_photo_json(photos_json_dir, record['photo_id'])
        if photo_json is None:
            continue
        photo_jsons[record['photo_id']] = photo_json
    for album_idx, album_record in enumerate(album_records):
        if album_idx:
            print()
        print(album_record['title'])
        print(album_record['share_url'])
        for record in photo_records:
            photo_json = photo_jsons.get(record['photo_id'])
            if photo_json is None:
                continue
            album_titles = [album['title'] for album in photo_json.get('albums', [])]
            if album_record['title'] in album_titles:
                print(f'{record["youtube_url"]} {record["title"]}')
    return 0


def parse_album_and_photo_sections(input_file: t.TextIO) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    lines = [line.rstrip('\n') for line in input_file]
    split_idx = next((idx for idx, line in enumerate(lines) if not line.strip()), len(lines))
    album_lines = [line for line in lines[:split_idx] if line.strip()]
    photo_lines = [line for line in lines[split_idx + 1:] if line.strip()]
    album_records = [parse_album_line(line) for line in album_lines]
    photo_records = [parse_update_line(line) for line in photo_lines]
    assert album_records, 'No album lines found'
    assert photo_records, 'No photo lines found'
    return album_records, photo_records


def parse_album_line(line: str) -> dict[str, str]:
    fields = line.strip().split(maxsplit=1)
    assert len(fields) == 2, f'Expected 2 fields: album_share_url album_title {line=}'
    share_url, title = fields
    return {'share_url': share_url, 'title': title}


def parse_update_line(line: str) -> dict[str, str]:
    fields = line.strip().split(maxsplit=2)
    assert len(fields) == 3, f'Expected fields: photo_url youtube_url [duration] title {line=}'
    photo_url, youtube_url, rest = fields
    title = parse_update_title(rest)
    video_id = get_youtube_video_id(youtube_url)
    photo_id = get_google_photos_photo_id(photo_url)
    return {'photo_url': photo_url, 'youtube_url': youtube_url, 'title': title, 'video_id': video_id, 'photo_id': photo_id}


def parse_update_title(rest: str) -> str:
    title_prefix = 'title:'
    title_idx = rest.find(title_prefix)
    if title_idx >= 0:
        return rest[title_idx + len(title_prefix):].strip()
    return rest.strip()


def parse_update_line_relaxed(line: str) -> dict[str, str] | None:
    stripped = line.strip()
    if not stripped.startswith('https://photos.google.com/photo/'):
        return None
    fields = stripped.split(maxsplit=2)
    if len(fields) != 3:
        return None
    photo_url, youtube_url, _title = fields
    if not youtube_url.startswith('https://youtu.be/') and 'youtube.com/watch' not in youtube_url:
        return None
    return parse_update_line(stripped)


def load_photo_json(photos_json_dir: pathlib.Path, photo_id: str) -> dict[str, t.Any] | None:
    path = photos_json_dir / f'{photo_id}.json'
    assert path.exists(), f'Photo JSON not found {path=}'
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        logger.warning(f'Invalid photo JSON {path=}: {exc}')
        return None


def get_youtube_video_id(youtube_url: str) -> str:
    parsed = urllib.parse.urlparse(youtube_url)
    if parsed.netloc in ['youtu.be', 'www.youtu.be']:
        video_id = parsed.path.removeprefix('/')
        assert video_id, f'Invalid youtu.be URL {youtube_url=}'
        return video_id
    if parsed.netloc in ['youtube.com', 'www.youtube.com', 'm.youtube.com']:
        video_id = urllib.parse.parse_qs(parsed.query).get('v', [None])[0]
        assert video_id is not None, f'Invalid YouTube watch URL {youtube_url=}'
        return video_id
    raise AssertionError(f'Unsupported YouTube URL {youtube_url=}')


def get_google_photos_photo_id(photo_url: str) -> str:
    parsed = urllib.parse.urlparse(photo_url)
    parts = [part for part in parsed.path.split('/') if part]
    assert len(parts) >= 2 and parts[0] == 'photo', f'Unsupported Google Photos URL {photo_url=}'
    return parts[1]


def make_set_youtube_meta_cmd(script_path: str, args: argparse.Namespace, record: dict[str, str]) -> str:
    parts = [
        'python',
        script_path,
        'set_meta',
        f'--video_id={shlex.quote(record["video_id"])}',
        f'--title={shlex.quote(record["title"])}',
    ]
    if args.yt_desc is not None:
        parts.append(f'--desc={shlex.quote(args.yt_desc)}')
    return ' '.join(parts)


def make_set_descr_cmd(script_path: str, args: argparse.Namespace, record: dict[str, str]) -> str:
    printf_cmd = f'$(printf "%s\\n%s" {shlex.quote(record["youtube_url"])} {shlex.quote(record["title"])})'
    return f'python {script_path} set_descr --connect_url={shlex.quote(args.connect_url)} --connect_use_tab_url_start={shlex.quote(args.connect_use_tab_url_start)} {shlex.quote(record["photo_url"])} "{printf_cmd}"'


def make_get_info_cmd(script_path: str, args: argparse.Namespace, record: dict[str, str]) -> str:
    out_path = f'{args.info_out_dir.rstrip("/")}/{record["photo_id"]}.json'
    return f'python {script_path} get_info --connect_url={shlex.quote(args.connect_url)} --connect_use_tab_url_start={shlex.quote(args.connect_use_tab_url_start)} {shlex.quote(record["photo_url"])} > {out_path}'


if __name__ == '__main__':
    raise SystemExit(main())
