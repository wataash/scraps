#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

epilog = r'''
'''[1:]

import argparse
import csv
import logging
import os
import pathlib
import re
import sys
import typing as t

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


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

    subparser = subparsers.add_parser('list', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='List own YouTube uploaded videos as TSV')
    subparser.set_defaults(func=list_videos)
    subparser.add_argument('--client_secret_json', metavar='PATH')
    subparser.add_argument('--token_json', metavar='PATH')

    subparser = subparsers.add_parser('set_meta', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Update YouTube video title and description')
    subparser.set_defaults(func=set_meta)
    subparser.add_argument('--client_secret_json', metavar='PATH')
    subparser.add_argument('--token_json', metavar='PATH')
    subparser.add_argument('--video_id', metavar='ID', required=True)
    subparser.add_argument('--title', metavar='TITLE')
    subparser.add_argument('--desc', metavar='DESCRIPTION')

    args = parser.parse_args()
    logger.debug(f'{args=}')
    return args.func(args)


def list_videos(args: argparse.Namespace) -> int:
    youtube = get_youtube_client(args)
    uploads_playlist_id = get_uploads_playlist_id(youtube)
    rows = get_youtube_video_rows(youtube, uploads_playlist_id)
    writer = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
    writer.writerow(['video_id', 'published_at', 'privacy_status', 'duration', 'title', 'url'])
    writer.writerows(rows)
    return 0


def set_meta(args: argparse.Namespace) -> int:
    youtube = get_youtube_client(args)
    video_response = youtube.videos().list(part='snippet', id=args.video_id).execute()
    logger.debug(f'{video_response=}')
    items = video_response.get('items', [])
    assert len(items) == 1, f'Expected one video for {args.video_id=}, got {len(items)}'
    snippet = items[0]['snippet']
    if args.title is not None:
        snippet['title'] = args.title
    if args.desc is not None:
        snippet['description'] = args.desc
    update_response = youtube.videos().update(part='snippet', body={'id': args.video_id, 'snippet': snippet}).execute()
    logger.debug(f'{update_response=}')
    logger.info(f'{update_response["snippet"]["title"]=}')
    logger.info(f'{update_response["snippet"]["description"]=}')
    return 0


def get_youtube_client(args: argparse.Namespace) -> t.Any:
    if not os.path.exists(args.token_json):
        flow = InstalledAppFlow.from_client_secrets_file(args.client_secret_json, scopes=['https://www.googleapis.com/auth/youtube.force-ssl'])
        credentials = flow.run_local_server(port=0)
        pathlib.Path(args.token_json).write_text(credentials.to_json())
    logger.debug(f'using token_json={args.token_json}')
    credentials = Credentials.from_authorized_user_file(args.token_json, scopes=['https://www.googleapis.com/auth/youtube.force-ssl'])
    return build('youtube', 'v3', credentials=credentials)


def get_uploads_playlist_id(youtube: t.Any) -> str:
    response = youtube.channels().list(part='contentDetails', mine=True).execute()
    logger.debug(f'{response=}')
    items = response.get('items', [])
    assert len(items) == 1, f'Expected exactly one channel for mine=True, got {len(items)}'
    uploads_playlist_id = items[0]['contentDetails']['relatedPlaylists']['uploads']
    assert uploads_playlist_id, f'uploads playlist not found {response=}'
    return uploads_playlist_id


def get_youtube_video_rows(youtube: t.Any, uploads_playlist_id: str) -> list[list[str]]:
    rows: list[list[str]] = []
    page_token: str | None = None
    while True:
        response = youtube.playlistItems().list(part='snippet,contentDetails', playlistId=uploads_playlist_id, maxResults=50, pageToken=page_token).execute()
        logger.debug(f'playlist page items={len(response.get("items", []))} {page_token=}')
        video_ids = [item['contentDetails']['videoId'] for item in response.get('items', [])]
        details = get_video_detail_map(youtube, video_ids)
        for item in response.get('items', []):
            video_id = item['contentDetails']['videoId']
            snippet = item['snippet']
            detail = details[video_id]
            rows.append([video_id, snippet['publishedAt'], detail['status']['privacyStatus'], format_youtube_duration(detail['contentDetails']['duration']), snippet['title'], f'https://youtu.be/{video_id}'])
        page_token = response.get('nextPageToken')
        if page_token is None:
            return rows


def get_video_detail_map(youtube: t.Any, video_ids: list[str]) -> dict[str, dict[str, t.Any]]:
    if not video_ids:
        return {}
    response = youtube.videos().list(part='status,contentDetails', id=','.join(video_ids), maxResults=50).execute()
    logger.debug(f'videos detail items={len(response.get("items", []))}')
    detail_map = {item['id']: item for item in response.get('items', [])}
    missing_ids = sorted(set(video_ids) - set(detail_map))
    assert not missing_ids, f'Missing video details for ids {missing_ids}'
    return detail_map


def format_youtube_duration(duration: str) -> str:
    if duration == 'P0D':
        return '0:00:00'
    match = re.fullmatch(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    assert match is not None, f'Unsupported YouTube duration {duration=}'
    days, hours, minutes, seconds = (int(value or 0) for value in match.groups())
    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}'


if __name__ == '__main__':
    raise SystemExit(main())
