#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

epilog = r'''
usage:
pip install -U playwright
playwright install
google-chrome --remote-debugging-port=9222 --user-data-dir=/var/tmp/pw_google_photos/ https://photos.google.com/  # login
pw_google_photos.py -h
pw_google_photos.py set_descr --connect_url="http://localhost:9222" --video=/tmp/pw_video/$(date +%y%m%d%H%M%S).webm --connect_use_tab_url_start=https://photos.google.com/ 'https://photos.google.com/photo/...' 'new description'
pw_google_photos.py get_info --connect_url="http://localhost:9222" --connect_use_tab_url_start=https://photos.google.com/ 'https://photos.google.com/photo/...'
pw_google_photos.py get_info_date --connect_url="http://localhost:9222" --connect_use_tab_url_start=https://photos.google.com/ 2006-01-02 out_dir/
pw_google_photos.py new_shared_album --connect_url="http://localhost:9222" --connect_use_tab_url_start=https://photos.google.com/ 'album name'
pw_google_photos.py add_to_album --connect_url="http://localhost:9222" --connect_use_tab_url_start=https://photos.google.com/ 'https://photos.google.com/photo/...' 'album name 1' 'album name 2'
'''[1:]

import argparse
import datetime
import json
import logging
import pathlib
import re
import sys
import typing as t
import urllib.parse

from playwright.sync_api import Browser, Locator, Page, Playwright
import playwright.sync_api as sync_api


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

    subparser = subparsers.add_parser('set_descr', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Update Google Photos description by browser automation')
    subparser.set_defaults(func=set_descr)
    group = subparser.add_mutually_exclusive_group(required=False)
    group.add_argument('--connect_url', metavar='URL', help='Connect to browser via CDP (e.g. http://localhost:9222)')
    group.add_argument('--launch_opt', metavar='JSON', type=arg_parse_json_obj, help='Launch new browser with Playwright launch options JSON (e.g. {"headless":false})')
    subparser.add_argument('--connect_opt', metavar='JSON', type=arg_parse_json_obj, help='Playwright connect_over_cdp options JSON')
    subparser.add_argument('--connect_use_tab_url_start', metavar='URL_PREFIX', help='Use existing tab whose URL startswith this string when connecting')
    subparser.add_argument('--video', metavar='PATH', help='Video filename or directory; trailing "/" means directory')
    subparser.add_argument('photo_url', help='Google Photos photo URL')
    subparser.add_argument('description', help='New description text')

    subparser = subparsers.add_parser('get_info', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Get Google Photos info pane as JSON')
    subparser.set_defaults(func=get_info)
    group = subparser.add_mutually_exclusive_group(required=False)
    group.add_argument('--connect_url', metavar='URL', help='Connect to browser via CDP (e.g. http://localhost:9222)')
    group.add_argument('--launch_opt', metavar='JSON', type=arg_parse_json_obj, help='Launch new browser with Playwright launch options JSON (e.g. {"headless":false})')
    subparser.add_argument('--connect_opt', metavar='JSON', type=arg_parse_json_obj, help='Playwright connect_over_cdp options JSON')
    subparser.add_argument('--connect_use_tab_url_start', metavar='URL_PREFIX', help='Use existing tab whose URL startswith this string when connecting')
    subparser.add_argument('--video', metavar='PATH', help='Video filename or directory; trailing "/" means directory')
    subparser.add_argument('photo_url', help='Google Photos photo URL')

    subparser = subparsers.add_parser('get_info_date', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Save info JSON of all photos/videos on DATE to OUT_DIR/<ID>.json')
    subparser.set_defaults(func=get_info_date)
    group = subparser.add_mutually_exclusive_group(required=False)
    group.add_argument('--connect_url', metavar='URL', help='Connect to browser via CDP (e.g. http://localhost:9222)')
    group.add_argument('--launch_opt', metavar='JSON', type=arg_parse_json_obj, help='Launch new browser with Playwright launch options JSON (e.g. {"headless":false})')
    subparser.add_argument('--connect_opt', metavar='JSON', type=arg_parse_json_obj, help='Playwright connect_over_cdp options JSON')
    subparser.add_argument('--connect_use_tab_url_start', metavar='URL_PREFIX', help='Use existing tab whose URL startswith this string when connecting')
    subparser.add_argument('--video', metavar='PATH', help='Video filename or directory; trailing "/" means directory')
    subparser.add_argument('date', type=datetime.date.fromisoformat, help='Date (YYYY-MM-DD)')
    subparser.add_argument('out_dir', help='Output directory; <ID>.json is written for each photo/video')

    subparser = subparsers.add_parser('new_shared_album', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Create a new shared album and print its share URL')
    subparser.set_defaults(func=new_shared_album)
    group = subparser.add_mutually_exclusive_group(required=False)
    group.add_argument('--connect_url', metavar='URL', help='Connect to browser via CDP (e.g. http://localhost:9222)')
    group.add_argument('--launch_opt', metavar='JSON', type=arg_parse_json_obj, help='Launch new browser with Playwright launch options JSON (e.g. {"headless":false})')
    subparser.add_argument('--connect_opt', metavar='JSON', type=arg_parse_json_obj, help='Playwright connect_over_cdp options JSON')
    subparser.add_argument('--connect_use_tab_url_start', metavar='URL_PREFIX', help='Use existing tab whose URL startswith this string when connecting')
    subparser.add_argument('--video', metavar='PATH', help='Video filename or directory; trailing "/" means directory')
    subparser.add_argument('album_name', help='Album title')

    subparser = subparsers.add_parser('add_to_album', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Add a photo/video to albums (skip albums it already belongs to)')
    subparser.set_defaults(func=add_to_album)
    group = subparser.add_mutually_exclusive_group(required=False)
    group.add_argument('--connect_url', metavar='URL', help='Connect to browser via CDP (e.g. http://localhost:9222)')
    group.add_argument('--launch_opt', metavar='JSON', type=arg_parse_json_obj, help='Launch new browser with Playwright launch options JSON (e.g. {"headless":false})')
    subparser.add_argument('--connect_opt', metavar='JSON', type=arg_parse_json_obj, help='Playwright connect_over_cdp options JSON')
    subparser.add_argument('--connect_use_tab_url_start', metavar='URL_PREFIX', help='Use existing tab whose URL startswith this string when connecting')
    subparser.add_argument('--video', metavar='PATH', help='Video filename or directory; trailing "/" means directory')
    subparser.add_argument('photo_url', help='Google Photos photo URL')
    subparser.add_argument('album_names', nargs='+', help='Album titles to add the photo/video to')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    if args.subcommand_name in ['set_descr', 'get_info', 'get_info_date', 'new_shared_album', 'add_to_album']:
        if args.connect_opt is not None:
            assert args.connect_url is not None, '--connect_opt requires --connect_url'
        if args.connect_use_tab_url_start is not None:
            assert args.connect_url is not None, '--connect_use_tab_url_start requires --connect_url'
        if args.connect_url is None and args.launch_opt is None:
            args.launch_opt = {}
    logger.debug(f'{args=}')
    with sync_api.sync_playwright() as playwright:
        return args.func(playwright, args)


def arg_parse_json_obj(value: str) -> dict[str, t.Any]:
    try:
        jsn = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f'invalid JSON: {exc}') from exc
    if not isinstance(jsn, dict):
        raise argparse.ArgumentTypeError(f'JSON must be object, got {type(jsn).__name__}')
    return jsn


def get_browser(playwright: Playwright, args: argparse.Namespace) -> t.Tuple[Browser, Page, t.Optional[sync_api.BrowserContext], t.Optional[str]]:
    video_dir_path: pathlib.Path | None = None
    video_name: str | None = None
    if args.video:
        if args.video.endswith('/'):
            video_dir_path = pathlib.Path(args.video)
        else:
            video_dir_path = pathlib.Path(args.video).parent
            video_name = pathlib.Path(args.video).name
    video_dir = video_dir_path

    if args.launch_opt is not None:
        browser = playwright.chromium.launch(**args.launch_opt)
        # Enable video recording only if video_dir is specified
        context_opts = {}
        if video_dir is not None:
            context_opts['record_video_dir'] = str(video_dir)
        context = browser.new_context(**context_opts)
        page = context.new_page()
        return browser, page, context, video_name

    assert args.connect_url is not None
    browser = playwright.chromium.connect_over_cdp(args.connect_url, **(args.connect_opt or {}))
    assert len(browser.contexts) == 1, f'Expected one browser context, got {len(browser.contexts)}'
    context = browser.contexts[0]
    if args.connect_use_tab_url_start is not None:
        if video_dir is not None:
            logger.warning(f'Video recording not available when using existing tab ({video_dir=})')
        for page in context.pages:
            if page.url.startswith(args.connect_use_tab_url_start):
                return browser, page, None, video_name
        else:
            raise Exception(f'tab starting with {args.connect_use_tab_url_start=} not found')

    # Create new context with video recording (if video_dir is specified)
    context_opts = {}
    if video_dir is not None:
        context_opts['record_video_dir'] = str(video_dir)
    new_context = browser.new_context(**context_opts)
    page = new_context.new_page()
    return browser, page, new_context, video_name


def set_descr(playwright: Playwright, args: argparse.Namespace) -> int:
    browser, page, context, video_name = get_browser(playwright, args)
    try:
        page.set_default_timeout(5000)
        logger.debug(f'goto start {args.photo_url=}')
        page.goto(args.photo_url, wait_until='domcontentloaded')
        logger.debug(f'goto done {page.url=}')
        wait_for_photo_page_ready(page)
        open_photo_info(page)
        description_editor = get_description_editor(page)
        fill_description(page, description_editor, args.description)
        commit_description(page)
        verify_description(page, args.description)
    finally:
        finalize_browser(context, page, video_name)
        browser.close()
    return 0


def get_info(playwright: Playwright, args: argparse.Namespace) -> int:
    browser, page, context, video_name = get_browser(playwright, args)
    try:
        page.set_default_timeout(5000)
        logger.debug(f'goto start {args.photo_url=}')
        page.goto(args.photo_url, wait_until='domcontentloaded')
        logger.debug(f'goto done {page.url=}')
        wait_for_photo_page_ready(page)
        open_info_panel(page)
        info = get_photo_info(page, args.photo_url)
        print(json.dumps(info, ensure_ascii=False, indent=2))
    finally:
        finalize_browser(context, page, video_name)
        browser.close()
    return 0


def get_info_date(playwright: Playwright, args: argparse.Namespace) -> int:
    browser, page, context, video_name = get_browser(playwright, args)
    try:
        page.set_default_timeout(5000)
        out_dir = pathlib.Path(args.out_dir).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        photo_urls = collect_photo_urls_for_date(page, args.date)
        logger.info(f'{len(photo_urls)} photos/videos found for {args.date}')
        for i, photo_url in enumerate(photo_urls):
            photo_id = photo_url.rstrip('/').rsplit('/', 1)[-1]
            out_path = out_dir / f'{photo_id}.json'
            if out_path.exists():
                logger.info(f'[{i + 1}/{len(photo_urls)}] skip existing {out_path}')
                continue
            logger.info(f'[{i + 1}/{len(photo_urls)}] {photo_url}')
            logger.debug(f'goto start {photo_url=}')
            page.goto(photo_url, wait_until='domcontentloaded')
            logger.debug(f'goto done {page.url=}')
            wait_for_photo_page_ready(page)
            open_info_panel(page)
            info = get_photo_info(page, photo_url)
            if not date_matches_detail(args.date, info['details'].get('date')):
                logger.warning(f'date mismatch: {info["details"].get("date")!r} does not look like {args.date}; saving anyway')
            out_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n')
            logger.info(f'saved {out_path}')
    finally:
        finalize_browser(context, page, video_name)
        browser.close()
    return 0


def new_shared_album(playwright: Playwright, args: argparse.Namespace) -> int:
    browser, page, context, video_name = get_browser(playwright, args)
    try:
        page.set_default_timeout(5000)
        logger.debug('goto start https://photos.google.com/albums')
        page.goto('https://photos.google.com/albums', wait_until='domcontentloaded')
        logger.debug(f'goto done {page.url=}')
        wait_for_photo_page_ready(page)
        click_create_album(page)
        fill_album_title(page, args.album_name)
        click_album_done(page)
        open_album_share_dialog(page)
        share_url = create_share_link(page)
        print(share_url)
    finally:
        finalize_browser(context, page, video_name)
        browser.close()
    return 0


def add_to_album(playwright: Playwright, args: argparse.Namespace) -> int:
    browser, page, context, video_name = get_browser(playwright, args)
    try:
        page.set_default_timeout(5000)
        page.set_default_navigation_timeout(15000)
        logger.debug(f'goto start {args.photo_url=}')
        page.goto(args.photo_url, wait_until='domcontentloaded')
        logger.debug(f'goto done {page.url=}')
        wait_for_photo_page_ready(page)
        open_info_panel(page)
        existing = [album['title'] for album in get_visible_albums(page)]
        logger.debug(f'{existing=}')
        for album_name in args.album_names:
            if album_name in existing:
                logger.info(f'already in album: {album_name}')
                continue
            pick_album_in_add_dialog(page, album_name)
            logger.info(f'added to album: {album_name}')
        verify_albums(page, args.photo_url, args.album_names)
    finally:
        finalize_browser(context, page, video_name)
        browser.close()
    return 0


def open_add_to_album_dialog(page: Page) -> None:
    logger.debug('open_add_to_album_dialog start')
    page.mouse.move(600, 100)  # the toolbar auto-hides; hidden duplicates of its buttons exist
    page.wait_for_timeout(500)
    for locator in [
        page.locator('[aria-label="More options"]:visible').first,
        page.locator('[aria-label="More options"]').first,
        page.get_by_role('button', name=re.compile('more options', re.I)).first,
    ]:
        if click_if_visible(locator):
            break
    else:
        raise AssertionError('"More options" button was not found')
    page.wait_for_timeout(500)
    for locator in [
        page.get_by_role('menuitem', name=re.compile('add to album', re.I)).first,
        page.get_by_text('Add to album', exact=True).first,
    ]:
        if click_if_visible(locator):
            page.wait_for_timeout(1000)
            logger.debug('open_add_to_album_dialog done')
            return
    raise AssertionError('"Add to album" menu item was not found')


def pick_album_in_add_dialog(page: Page, album_name: str) -> None:
    logger.debug(f'pick_album_in_add_dialog start {album_name=}')
    open_add_to_album_dialog(page)
    dialog = page.locator('[role="dialog"]').last
    for locator in [
        dialog.locator('input[placeholder="Search albums"]').first,
        dialog.get_by_placeholder(re.compile('search albums', re.I)).first,
        dialog.locator('input[type="text"]').first,
    ]:
        if is_visible(locator):
            locator.fill(album_name)
            logger.debug(f'pick_album_in_add_dialog searched {album_name=}')
            page.wait_for_timeout(700)  # wait for the album list to be filtered
            break
    else:
        raise AssertionError('"Search albums" input was not found in the add-to-album dialog')
    for locator in [
        dialog.get_by_role('option', name=album_name).first,  # <li role="option" aria-label="<name> · N items · Shared">
        dialog.get_by_text(album_name, exact=True).locator('xpath=ancestor::li').first,
    ]:
        if click_if_visible(locator):
            page.wait_for_timeout(1500)  # wait for the "Added to ..." toast and dialog close
            logger.debug(f'pick_album_in_add_dialog done {album_name=}')
            return
    raise AssertionError(f'Album {album_name!r} was not found in the add-to-album dialog')


def verify_albums(page: Page, photo_url: str, album_names: list[str]) -> None:
    logger.debug('verify_albums start')
    logger.debug(f'goto start {photo_url=}')
    page.goto(photo_url, wait_until='domcontentloaded')
    logger.debug(f'goto done {page.url=}')
    wait_for_photo_page_ready(page)
    open_info_panel(page)
    page.wait_for_timeout(1000)
    titles = [album['title'] for album in get_visible_albums(page)]
    missing = [name for name in album_names if name not in titles]
    assert not missing, f'Failed to add to albums: {missing=} {titles=}'
    logger.debug(f'verify_albums done {titles=}')


def click_create_album(page: Page) -> None:
    logger.debug('click_create_album start')
    page.wait_for_timeout(1000)
    for locator in [
        page.get_by_role('button', name=re.compile('create album', re.I)).first,
        page.get_by_role('link', name=re.compile('create album', re.I)).first,
        page.locator('[aria-label*="Create album" i]').first,
        page.get_by_text('Create album', exact=True).first,
    ]:
        if click_if_visible(locator):
            logger.debug(f'click_create_album done {locator=}')
            return
    raise AssertionError('"Create album" button was not found. Check login state and current UI.')


def fill_album_title(page: Page, album_name: str) -> None:
    logger.debug(f'fill_album_title start {album_name=}')
    page.wait_for_timeout(1000)
    for locator in [
        page.locator('textarea[aria-label="Edit album name"]').first,
        page.locator('textarea[placeholder="Add a title"]').first,
        page.get_by_role('textbox', name=re.compile('album name|title', re.I)).first,
        page.locator('textarea[aria-label*="album name" i]').first,
    ]:
        if is_visible(locator):
            locator.click()
            locator.fill(album_name)
            logger.debug(f'fill_album_title done {locator=}')
            return
    raise AssertionError('Album title input was not found')


def click_album_done(page: Page) -> None:
    logger.debug('click_album_done start')
    for locator in [
        page.get_by_role('button', name=re.compile(r'^done$', re.I)).first,
        page.locator('[aria-label="Done"]').first,
        page.locator('[aria-label*="done" i]').first,
    ]:
        if click_if_visible(locator):
            page.wait_for_timeout(1000)
            logger.debug(f'click_album_done done {locator=}')
            return
    raise AssertionError('"Done" button was not found')


def open_album_share_dialog(page: Page) -> None:
    logger.debug('open_album_share_dialog start')
    for locator in [
        page.locator('[aria-label="Share album"]').first,
        page.get_by_role('button', name=re.compile(r'^share', re.I)).first,
        page.locator('[aria-label*="share" i]').first,
    ]:
        if click_if_visible(locator):
            page.wait_for_timeout(1000)
            logger.debug(f'open_album_share_dialog done {locator=}')
            return
    raise AssertionError('Share button was not found')


def create_share_link(page: Page) -> str:
    logger.debug('create_share_link start')
    for _ in range(2):  # "Create link" option, then "Create link" confirmation
        for locator in [
            page.get_by_role('button', name=re.compile('create link', re.I)).first,
            page.locator('[aria-label*="Create link" i]').first,
            page.get_by_text('Create link', exact=True).first,
        ]:
            if click_if_visible(locator):
                logger.debug(f'create_share_link clicked {locator=}')
                page.wait_for_timeout(1000)
                break
        else:
            break  # no more "Create link" to click; the URL may already be shown
    return wait_for_share_url(page)


def wait_for_share_url(page: Page) -> str:
    logger.debug('wait_for_share_url start')
    for _ in range(20):
        url = page.evaluate(r"""
() => {
  const re = /https:\/\/photos\.app\.goo\.gl\/[\w-]+/;
  const m = document.body.innerText.match(re);
  if (m) return m[0];
  for (const el of document.querySelectorAll('input, textarea')) {
    const m2 = (el.value || '').match(re);
    if (m2) return m2[0];
  }
  return null;
}
""")
        if url:
            logger.debug(f'wait_for_share_url done {url=}')
            return url
        page.wait_for_timeout(500)
    raise AssertionError('Share URL (https://photos.app.goo.gl/...) was not found')


def collect_photo_urls_for_date(page: Page, date: datetime.date) -> list[str]:
    query = date.strftime('%B %-d, %Y')  # e.g. January 2, 2006
    search_url = 'https://photos.google.com/search/' + urllib.parse.quote(query)
    logger.debug(f'goto start {search_url=}')
    page.goto(search_url, wait_until='domcontentloaded')
    logger.debug(f'goto done {page.url=}')
    wait_for_photo_page_ready(page)
    page.wait_for_timeout(2000)
    urls: dict[str, None] = {}  # ordered set
    stable_rounds = 0
    for _round in range(200):
        hrefs = page.evaluate("""
() => Array.from(document.querySelectorAll('a[href*="/photo/"]')).map(a => a.getAttribute('href'))
""")
        n_before = len(urls)
        for href in hrefs:
            match = re.search(r'/photo/([A-Za-z0-9_-]+)', href)
            if match is not None:
                urls.setdefault(f'https://photos.google.com/photo/{match.group(1)}', None)
        if len(urls) == n_before:
            stable_rounds += 1
            if stable_rounds >= 3:
                break
        else:
            stable_rounds = 0
        page.mouse.move(600, 400)
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(700)
    logger.debug(f'collect done {len(urls)=}')
    if not urls:
        raise AssertionError(f'No photos found for {date} ({search_url=}). Check login state and search results.')
    return list(urls)


def date_matches_detail(date: datetime.date, detail_date: str | None) -> bool:
    if detail_date is None:
        return False
    month_names = [date.strftime('%b'), date.strftime('%B')]
    if not (any(m in detail_date for m in month_names) and re.search(rf'\b{date.day}\b', detail_date) is not None):
        return False
    if str(date.year) in detail_date:
        return True
    # current-year photos omit the year in the info pane (e.g. "Jun 9")
    return date.year == datetime.date.today().year


def wait_for_photo_page_ready(page: Page) -> None:
    try:
        page.wait_for_load_state('load')
        logger.debug('load event observed')
    except sync_api.TimeoutError:
        logger.debug('load event timeout; continue with current DOM')


def open_photo_info(page: Page) -> None:
    logger.debug('open_photo_info start')
    try:
        get_description_editor(page)
        logger.debug('description editor already visible')
        return
    except AssertionError:
        logger.debug('description editor not yet visible')
    open_info_panel(page)
    get_description_editor(page)
    logger.debug('open_photo_info done')


def open_info_panel(page: Page) -> None:
    logger.debug('open_info_panel start')
    if has_visible_info_pane(page):
        logger.debug('info pane already visible')
        return
    for locator in [
        page.get_by_role('button', name='Open info'),
        page.locator('[aria-label="Open info"]').first,
        page.get_by_role('button', name=re.compile('details|information|info|詳細|情報', re.I)),
        page.locator('[aria-label*="info" i]'),
        page.locator('[aria-label*="details" i]'),
        page.locator('[aria-label*="詳細"]'),
        page.locator('[aria-label*="情報"]'),
    ]:
        if click_if_visible(locator):
            logger.debug(f'clicked info trigger {locator=}')
            wait_for_info_pane(page)
            break
    else:
        raise AssertionError('Failed to open Google Photos info panel')
    logger.debug('open_info_panel done')


def get_description_editor(page: Page) -> Locator:
    logger.debug('get_description_editor start')
    candidates = [
        page.locator('textarea[aria-label="Description"][placeholder="Add a description"]').locator(':visible').first,
        page.locator('textarea[aria-label="Description"]').locator(':visible').first,
        page.get_by_role('textbox', name=re.compile('description|caption|説明', re.I)).locator(':visible').first,
        page.locator('textarea[aria-label*="escription" i]').first,
        page.locator('textarea[aria-label*="aption" i]').first,
        page.locator('textarea[aria-label*="説明"]').first,
        page.locator('[contenteditable="true"][aria-label*="escription" i]').first,
        page.locator('[contenteditable="true"][aria-label*="aption" i]').first,
        page.locator('[contenteditable="true"][aria-label*="説明"]').first,
        page.locator('[contenteditable="true"][placeholder*="escription" i]').first,
        page.locator('[contenteditable="true"][placeholder*="caption" i]').first,
        page.locator('textarea[placeholder*="escription" i]').first,
        page.locator('textarea[placeholder*="caption" i]').first,
    ]
    for locator in candidates:
        if is_visible(locator):
            logger.debug(f'description editor found {locator=}')
            return locator
    raise AssertionError('Google Photos description editor was not found. Check login state and current UI.')


def wait_for_info_pane(page: Page) -> None:
    logger.debug('wait_for_info_pane start')
    page.wait_for_timeout(1500)
    for locator in [
        page.locator('textarea[aria-label="Description"]').locator(':visible').first,
        page.locator('div.kmqzh').locator(':visible').first,
        page.locator('[aria-label="Close info"]').locator(':visible').first,
    ]:
        if is_visible(locator):
            logger.debug(f'wait_for_info_pane done {locator=}')
            return
    raise AssertionError('Info pane did not become visible')


def has_visible_info_pane(page: Page) -> bool:
    for locator in [
        page.locator('textarea[aria-label="Description"]').locator(':visible').first,
        page.locator('div.kmqzh').locator(':visible').first,
        page.locator('[aria-label="Close info"]').locator(':visible').first,
    ]:
        if is_visible(locator):
            return True
    return False


def get_photo_info(page: Page, photo_url: str) -> dict[str, t.Any]:
    pane_lines = get_visible_info_pane_lines(page)
    description = get_visible_description(page)
    location = get_visible_location(page)
    albums = get_visible_albums(page)
    duration = get_video_duration(page)
    details = parse_info_details(pane_lines, location, duration)
    return {
        'photo_url': photo_url,
        'page_url': page.url,
        'description': description,
        'location': location,
        'albums': albums,
        'details': details,
        'pane_lines': pane_lines,
    }


def get_visible_info_pane_lines(page: Page) -> list[str]:
    pane_text = page.evaluate(
        """
() => {
  const vw = window.innerWidth;
  const candidates = Array.from(document.querySelectorAll('div')).map(e => {
    const r = e.getBoundingClientRect();
    const text = (e.innerText || '').trim();
    const isVisible = r.width > 300 && r.height > 400 && r.right > vw - 420 && text.includes('Details');
    return {text, area: r.width * r.height, isVisible};
  }).filter(x => x.isVisible).sort((a, b) => b.area - a.area);
  return candidates.length ? candidates[0].text : null;
}
"""
    )
    assert pane_text is not None, 'Visible Google Photos info pane text was not found'
    return [line.strip() for line in pane_text.splitlines() if line.strip()]


def get_visible_description(page: Page) -> str:
    try:
        return get_description_editor(page).input_value().strip()
    except AssertionError:
        return ''


def get_visible_location(page: Page) -> str | None:
    locator = page.locator('[aria-label="Edit location"]').locator(':visible').first
    if is_visible(locator):
        text = (locator.inner_text() or '').strip()
        return text or None
    return None


def parse_info_details(pane_lines: list[str], location: str | None, duration: dict[str, t.Any] | None) -> dict[str, t.Any]:
    details_idx = pane_lines.index('Details') if 'Details' in pane_lines else -1
    detail_lines = pane_lines[details_idx + 1:] if details_idx >= 0 else []
    details: dict[str, t.Any] = {'detail_lines': detail_lines}
    if detail_lines:
        details['date'] = detail_lines[0]
    if len(detail_lines) >= 2:
        details['time'] = detail_lines[1]
    if len(detail_lines) >= 3 and re.match(r'^(GMT|UTC)[+-]', detail_lines[2]):
        details['timezone'] = detail_lines[2]
    for line in detail_lines:
        if re.search(r'\.(jpg|jpeg|png|gif|webp|heic|mp4|mov|avi|mkv)$', line, re.I):
            details['filename'] = line
        elif re.search(r'^\d+(\.\d+)?MP$', line):
            details['megapixels'] = line
        elif '×' in line or re.search(r'^\d+\s*x\s*\d+$', line, re.I):
            details['dimensions'] = line
        elif line.startswith('Uploaded from '):
            details['upload_source'] = line
        elif line.startswith('Backed up'):
            details['backup_status'] = line
        elif line.endswith('Learn more'):
            details['quality'] = line
    if location is not None:
        details['location'] = location
    elif 'Map data ©2026 Google' in detail_lines:
        map_idx = detail_lines.index('Map data ©2026 Google')
        if map_idx >= 1:
            details['location'] = detail_lines[map_idx - 1]
    if duration is not None:
        details['duration'] = duration['text']
        details['duration_seconds'] = duration['seconds']
    return details


def get_visible_albums(page: Page) -> list[dict[str, str | None]]:
    albums = page.evaluate(
        """
() => Array.from(document.querySelectorAll('a.rugHuc')).map(a => {
  const r = a.getBoundingClientRect();
  const text = (a.innerText || '').trim();
  if (!(r.width > 0 && r.height > 0 && r.x > window.innerWidth - 420 && text)) return null;
  const lines = text.split('\\n').map(x => x.trim()).filter(Boolean);
  const href = a.getAttribute('href');
  const url = href ? new URL(href, 'https://photos.google.com/').href : null;
  return {
    title: lines[0] ?? null,
    summary: lines.slice(1).join(' ') || null,
    url,
  };
}).filter(Boolean)
"""
    )
    return albums


def get_video_duration(page: Page) -> dict[str, t.Any] | None:
    youtube_frame = next((frame for frame in page.frames if 'youtube.googleapis.com/embed/' in frame.url), None)
    if youtube_frame is None:
        return None
    try:
        page.mouse.move(600, 500)
        page.wait_for_timeout(500)
        duration_text = youtube_frame.locator('.ytp-time-duration').first.text_content(timeout=2000)
        duration_seconds = youtube_frame.locator('video').first.evaluate('video => video.duration')
    except Exception:
        return None
    assert duration_text is not None
    return {'text': duration_text.strip(), 'seconds': duration_seconds}


def fill_description(page: Page, description_editor: Locator, description: str) -> None:
    logger.debug(f'fill_description start {len(description)=}')
    description_editor.click()
    tag_name = description_editor.evaluate('(node) => node.tagName.toLowerCase()')
    is_contenteditable = description_editor.evaluate('(node) => node.getAttribute("contenteditable") === "true"')
    logger.debug(f'fill_description target {tag_name=} {is_contenteditable=}')
    if tag_name in ['input', 'textarea']:
        description_editor.fill(description)
        logger.debug('fill_description done by fill()')
        return
    assert is_contenteditable, f'Unsupported editor element {tag_name=}'
    modifier = 'Meta' if page.evaluate('() => navigator.platform').lower().startswith('mac') else 'Control'
    page.keyboard.press(f'{modifier}+A')
    page.keyboard.insert_text(description)
    logger.debug('fill_description done by keyboard')


def commit_description(page: Page) -> None:
    logger.debug('commit_description start')
    for locator in [
        page.get_by_role('button', name=re.compile('save|done|完了|保存', re.I)),
        page.locator('[aria-label*="save" i]'),
        page.locator('[aria-label*="done" i]'),
        page.locator('[aria-label*="完了"]'),
        page.locator('[aria-label*="保存"]'),
    ]:
        if click_if_visible(locator):
            logger.debug(f'commit_description clicked explicit button {locator=}')
            page.wait_for_timeout(500)
            return
    logger.debug('commit_description fallback to Tab')
    page.keyboard.press('Tab')
    page.wait_for_timeout(500)
    logger.debug('commit_description done')


def verify_description(page: Page, expected_description: str) -> None:
    logger.debug('verify_description start')
    description_editor = get_description_editor(page)
    tag_name = description_editor.evaluate('(node) => node.tagName.toLowerCase()')
    if tag_name in ['input', 'textarea']:
        actual_description = description_editor.input_value()
    else:
        actual_description = description_editor.text_content() or ''
    logger.debug(f'verify_description compare {actual_description=!r} {expected_description=!r}')
    assert actual_description.strip() == expected_description.strip(), f'Failed to update description {actual_description=!r} {expected_description=!r}'
    logger.debug('verify_description done')


def finalize_browser(context: sync_api.BrowserContext | None, page: Page, video_name: str | None) -> None:
    video_path: pathlib.Path | None = None
    if page.video:
        video_path = pathlib.Path(page.video.path())
    if context is not None:
        context.close()
    if video_path is not None and video_name is not None:
        target = video_path.parent / video_name
        video_path.replace(target)
        logger.info(f'Video saved to: {target}')


def click_if_visible(locator: Locator) -> bool:
    if not is_visible(locator):
        return False
    locator.click()
    return True


def is_visible(locator: Locator) -> bool:
    try:
        locator.wait_for(state='visible', timeout=1000)
        logger.debug(f'is_visible true {locator=}')
        return True
    except sync_api.TimeoutError:
        return False


if __name__ == '__main__':
    raise SystemExit(main())
