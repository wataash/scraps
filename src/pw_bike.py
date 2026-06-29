#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
prerequisites:
  pip install -U playwright
  playwright install
  google-chrome --remote-debugging-port=9222 --user-data-dir=/var/tmp/chrome.pw/

examples:
  pw_bike.py -h
  pw_bike.py --date=2026-05-27 --id=TYO12345 \
             --name=YourName --email=you@example.com \
             --user_id=yourid --phone=000-0000-0000
'''[1:]

import argparse
import logging

import playwright.sync_api as sync_api
from playwright.sync_api import Playwright
import sys


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
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog,
        description='Fill the docomo-cycle contact form for a non-returned bike.')
    parser.add_argument('--connect_url', default='http://localhost:9222')
    parser.add_argument('--date', required=True, metavar='YYYY-MM-DD')
    parser.add_argument('--id', required=True, metavar='TYO1234', help='bike id')
    parser.add_argument('--name', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--user_id', required=True)
    parser.add_argument('--phone', required=True, metavar='090-0000-0000')
    parser.add_argument('--body', default='自転車の返却ボタンを押しても返却できなかったため、施錠記録をご確認頂き、料金の補正をお願いします。')
    parser.add_argument('--pause', action='store_true', help='call page.pause() before filling')

    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    with sync_api.sync_playwright() as pw:
        return bike(pw, args)


def bike(pw: Playwright, args: argparse.Namespace) -> int:
    browser = pw.chromium.connect_over_cdp(args.connect_url)
    assert len(browser.contexts) == 1, f'Expected one context, got {len(browser.contexts)}'
    ctx = browser.contexts[0]
    try:
        page = ctx.new_page()
        page.goto('https://faq.docomo-cycle.jp/contact-other')
        if args.pause:
            page.pause()

        page.get_by_label('お問い合わせ内容を選択してください。').select_option('返却できていない')
        page.get_by_label('エリア').select_option('東京')
        page.get_by_label('お問い合わせ（ご意見）内容').fill(args.body)
        page.get_by_label('車両番号').fill(args.id)
        page.get_by_label('お名前').fill(args.name)
        page.get_by_label('メールアドレス').fill(args.email)
        page.get_by_label('会員種別').select_option('月額会員')
        page.get_by_label('ユーザID').fill(args.user_id)
        page.get_by_label('登録電話番号').fill(args.phone)
        page.get_by_label('連絡先お電話番号').fill(args.phone)
        page.get_by_label('ご利用開始日').fill(args.date)
        page.get_by_label('ご返信の要否').select_option('必要')
    finally:
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
