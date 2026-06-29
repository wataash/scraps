#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
警視庁 拾得物公表システム (https://www.ishitsu.keishicho.metro.tokyo.lg.jp/syutoku/)
の物品一覧を CSV に書き出す。

# カメラ類・上着類・ズボン類を、路上/建物と鉄道で、文京区・千代田区から、2026/05/25〜2026/05/28
python keishicho_lostfound.py \
    --category カメラ類,上着類,ズボン類 \
    --date_from 2026/05/25 --date_to 2026/05/28 \
    --place 路上・建物,鉄道 \
    --area 文京区,千代田区 \
    -o out.csv

# 拾得日付不明の物品を表示しない
python keishicho_lostfound.py --category 財布類 --date_from 2026/05/01 --date_to 2026/05/28 \
    --place 路上・建物 --area 新宿区 --no_include_unknown_date

# 指定できる分類・場所・地域名を一覧表示
python keishicho_lostfound.py --list
'''[1:]

import argparse
import csv
import io
import logging
import sys
import time
from itertools import product

import requests
from bs4 import BeautifulSoup


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


BASE_URL = 'https://www.ishitsu.keishicho.metro.tokyo.lg.jp/syutoku'
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) keishicho_lostfound.py'

# 場所区分 (拾得場所の種別): 名称 -> コード
PLACE_CODES = {
    '路上・建物': '1',
    '鉄道': '3',
    'バス': '4',
    'タクシー': '5',
    'その他交通機関': '6',
}

# 住所 (区市町村・都道府県): 名称 -> 住所コード
AREA_CODES = {
    # 23区
    '千代田区': '13101', '中央区': '13102', '港区': '13103', '新宿区': '13104',
    '文京区': '13105', '台東区': '13106', '墨田区': '13107', '江東区': '13108',
    '品川区': '13109', '目黒区': '13110', '大田区': '13111', '世田谷区': '13112',
    '渋谷区': '13113', '中野区': '13114', '杉並区': '13115', '豊島区': '13116',
    '北区': '13117', '荒川区': '13118', '板橋区': '13119', '練馬区': '13120',
    '足立区': '13121', '葛飾区': '13122', '江戸川区': '13123',
    # 23区外 (多摩・島しょ)
    '八王子市': '13201', '立川市': '13202', '武蔵野市': '13203', '三鷹市': '13204',
    '青梅市': '13205', '府中市': '13206', '昭島市': '13207', '調布市': '13208',
    '町田市': '13209', '小金井市': '13210', '小平市': '13211', '日野市': '13212',
    '東村山市': '13213', '国分寺市': '13214', '国立市': '13215', '福生市': '13218',
    '狛江市': '13219', '東大和市': '13220', '清瀬市': '13221', '東久留米市': '13222',
    '武蔵村山市': '13223', '多摩市': '13224', '稲城市': '13225', '羽村市': '13227',
    'あきる野市': '13228', '西東京市': '13229', '西多摩郡': '13300', '瑞穂町': '13303',
    '日の出町': '13305', '檜原村': '13307', '奥多摩町': '13308', '大島支庁': '13360',
    '大島町': '13361', '利島村': '13362', '新島村': '13363', '神津島村': '13364',
    '三宅支庁': '13380', '三宅村': '13381', '御蔵島村': '13382', '八丈支庁': '13400',
    '八丈町': '13401', '青ヶ島村': '13402', '小笠原支庁': '13420', '小笠原村': '13421',
    # 都道府県 (都内の警察署に提出された他府県拾得物)
    '北海道': '01000', '青森県': '02000', '岩手県': '03000', '宮城県': '04000',
    '秋田県': '05000', '山形県': '06000', '福島県': '07000', '茨城県': '08000',
    '栃木県': '09000', '群馬県': '10000', '埼玉県': '11000', '千葉県': '12000',
    '神奈川県': '14000', '新潟県': '15000', '富山県': '16000', '石川県': '17000',
    '福井県': '18000', '山梨県': '19000', '長野県': '20000', '岐阜県': '21000',
    '静岡県': '22000', '愛知県': '23000', '三重県': '24000', '滋賀県': '25000',
    '京都府': '26000', '大阪府': '27000', '兵庫県': '28000', '奈良県': '29000',
    '和歌山県': '30000', '鳥取県': '31000', '島根県': '32000', '岡山県': '33000',
    '広島県': '34000', '山口県': '35000', '徳島県': '36000', '香川県': '37000',
    '愛媛県': '38000', '高知県': '39000', '福岡県': '40000', '佐賀県': '41000',
    '長崎県': '42000', '熊本県': '43000', '大分県': '44000', '宮崎県': '45000',
    '鹿児島県': '46000', '沖縄県': '47000',
}

# 分類: 大分類名称 -> 大分類コード
MAJOR_CATEGORIES = {
    '現金': '10', 'かばん類': '12', '袋・封筒類': '14', '財布類': '16',
    'カードケース類': '18', 'カメラ類': '20', '時計類': '22', 'めがね類': '24',
    '電気製品類': '26', '携帯電話類': '28', '貴金属類': '30', '趣味・娯楽用品類': '32',
    '証明書類': '34', '有価証券類': '36', '著作品類': '38', '手帳・文具類': '40',
    '書類・紙類': '42', '小包・箱類': '44', '衣類・履物類': '46', 'かさ類': '48',
    '鍵類': '50', '生活用品類': '52', '医療・化粧品類': '54', '食料品類': '56',
    '動植物類': '58', 'その他': '99',
}

# 中分類: 中分類名称 -> (大分類コード, 大分類名称, 中分類コード)
MINOR_CATEGORIES = {
    '現金': ('10', '現金', '1'),
    '手提げかばん': ('12', 'かばん類', '1'), '肩掛けかばん': ('12', 'かばん類', '2'),
    '抱えかばん': ('12', 'かばん類', '3'), '小物入れ': ('12', 'かばん類', '4'),
    'その他かばん類': ('12', 'かばん類', '99'),
    '袋': ('14', '袋・封筒類', '1'), '封筒': ('14', '袋・封筒類', '2'),
    '財布': ('16', '財布類', '1'), 'がま口': ('16', '財布類', '2'), '小銭入れ': ('16', '財布類', '3'),
    'カードケース': ('18', 'カードケース類', '1'), '名刺入れ': ('18', 'カードケース類', '2'),
    'カメラ': ('20', 'カメラ類', '1'), 'ビデオカメラ': ('20', 'カメラ類', '2'),
    'カメラ付属品類': ('20', 'カメラ類', '3'),
    '腕時計': ('22', '時計類', '1'), 'その他時計類': ('22', '時計類', '99'),
    'めがね': ('24', 'めがね類', '1'), 'サングラス類': ('24', 'めがね類', '2'),
    'コンタクトレンズ': ('24', 'めがね類', '3'), '双眼鏡類': ('24', 'めがね類', '4'),
    '電気製品': ('26', '電気製品類', '1'), '携帯音響品': ('26', '電気製品類', '2'),
    '音響関連品': ('26', '電気製品類', '3'), '電子機器': ('26', '電気製品類', '4'),
    '電子玩具': ('26', '電気製品類', '5'), '外部記録媒体': ('26', '電気製品類', '6'),
    '電気製品類付属品': ('26', '電気製品類', '7'),
    '携帯電話機': ('28', '携帯電話類', '1'), 'その他通信機器類': ('28', '携帯電話類', '99'),
    'ネックレス': ('30', '貴金属類', '1'), '指輪': ('30', '貴金属類', '2'),
    'ブレスレット': ('30', '貴金属類', '3'), 'イヤリング類': ('30', '貴金属類', '4'),
    'ブローチ': ('30', '貴金属類', '5'), 'ペンダント': ('30', '貴金属類', '6'),
    'その他貴金属類': ('30', '貴金属類', '99'),
    'レジャー・スポーツ用品': ('32', '趣味・娯楽用品類', '1'), '楽器類': ('32', '趣味・娯楽用品類', '2'),
    'その他趣味・娯楽用品類': ('32', '趣味・娯楽用品類', '99'),
    '運転免許証': ('34', '証明書類', '1'), '身分証明書類': ('34', '証明書類', '2'),
    '健康保険証類': ('34', '証明書類', '3'), 'その他証明書類': ('34', '証明書類', '5'),
    '預貯金通帳類': ('34', '証明書類', '6'), 'キャッシュカード類': ('34', '証明書類', '7'),
    '会員証（カード）類': ('34', '証明書類', '8'),
    '有価証券': ('36', '有価証券類', '1'), 'プリペイドカード類': ('36', '有価証券類', '2'),
    '定期券類': ('36', '有価証券類', '3'), '乗車券類': ('36', '有価証券類', '4'),
    '馬券・宝くじ類': ('36', '有価証券類', '5'), '切手類': ('36', '有価証券類', '6'),
    'その他証券類': ('36', '有価証券類', '99'),
    '書籍類': ('38', '著作品類', '1'), 'ディスク・テープ類': ('38', '著作品類', '2'),
    '写真類': ('38', '著作品類', '3'), 'その他著作品類': ('38', '著作品類', '99'),
    '手帳・ノート類': ('40', '手帳・文具類', '1'), '印鑑類': ('40', '手帳・文具類', '2'),
    '整理収納用品類': ('40', '手帳・文具類', '3'), '筆箱・筆記用具類': ('40', '手帳・文具類', '4'),
    'その他文具類': ('40', '手帳・文具類', '99'),
    '書類': ('42', '書類・紙類', '1'), '図画類': ('42', '書類・紙類', '2'),
    '名刺': ('42', '書類・紙類', '3'), 'その他紙類': ('42', '書類・紙類', '99'),
    '小包・箱類': ('44', '小包・箱類', '1'),
    '帽子類': ('46', '衣類・履物類', '1'), '手袋': ('46', '衣類・履物類', '2'),
    'マフラー類': ('46', '衣類・履物類', '3'), '上着類': ('46', '衣類・履物類', '4'),
    'ズボン類': ('46', '衣類・履物類', '5'), '上下衣類': ('46', '衣類・履物類', '6'),
    'その他衣類': ('46', '衣類・履物類', '7'), '衣類付属品': ('46', '衣類・履物類', '8'),
    '履物類': ('46', '衣類・履物類', '9'),
    'かさ': ('48', 'かさ類', '1'),
    '鍵': ('50', '鍵類', '1'), '鍵（キーホルダー付）': ('50', '鍵類', '2'),
    '鍵（キーケース付）': ('50', '鍵類', '3'), 'カードキー': ('50', '鍵類', '4'),
    '生活用品': ('52', '生活用品類', '1'), '食器類': ('52', '生活用品類', '2'),
    '工具類': ('52', '生活用品類', '3'), '装飾品類': ('52', '生活用品類', '4'),
    '神仏具品類': ('52', '生活用品類', '5'), '自転車類': ('52', '生活用品類', '6'),
    'ケース・カバー類': ('52', '生活用品類', '7'),
    '薬類': ('54', '医療・化粧品類', '1'), '医療関連品類': ('54', '医療・化粧品類', '2'),
    '化粧品類': ('54', '医療・化粧品類', '3'),
    '食料品類': ('56', '食料品類', '1'),
    '動物': ('58', '動植物類', '1'), '植物': ('58', '動植物類', '2'),
    '動植物関連品': ('58', '動植物類', '3'),
    '所持禁止物品': ('99', 'その他', '1'),
}

CSV_HEADER = [
    '分類', '種類', '特徴', '在中品等', '拾得日付', '保管期間満了日',
    '拾得場所', '拾得場所種別', '問合せ先', '問合せ電話番号', '問合せ番号', '検索場所区分',
]


def resolve_category(name: str) -> tuple[str, str, str, str]:
    """分類名から (大分類コード, 大分類名称, 中分類コード, 中分類名称) を返す。"""
    if name in MAJOR_CATEGORIES:
        return MAJOR_CATEGORIES[name], name, '', ''
    if name in MINOR_CATEGORIES:
        major_code, major_name, minor_code = MINOR_CATEGORIES[name]
        return major_code, major_name, minor_code, name
    raise SystemExit(f'未知の分類名: {name!r} (--list で一覧を確認)')


def parse_date(s: str) -> tuple[str, str, str]:
    parts = s.replace('-', '/').split('/')
    if len(parts) != 3:
        raise SystemExit(f'日付は YYYY/MM/DD 形式で指定してください: {s!r}')
    year, month, day = (p.lstrip('0') or '0' for p in parts)
    return year, month, day


def fetch_page(session: requests.Session, params: dict, page_num: int, rows_per_page: int) -> str:
    query = dict(params)
    query['pageNum'] = str(page_num)
    query['rowsPerPage'] = str(rows_per_page)
    resp = session.get(f'{BASE_URL}/Result', params=query, timeout=30)
    logger.info(f'GET {resp.url}')
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    return resp.text


def parse_rows(html: str, search_place: str) -> tuple[list[list[str]], int]:
    """結果テーブルの行と総数を返す。"""
    soup = BeautifulSoup(html, 'html.parser')
    total = 0
    num_div = soup.find(id='result-num')
    if num_div:
        digits = ''.join(c for c in num_div.get_text() if c.isdigit())
        total = int(digits) if digits else 0

    rows = []
    table = soup.find('table', class_='tbody-scroll')
    if table and table.find('tbody'):
        for tr in table.find('tbody').find_all('tr'):
            cells = {td.get('class', [''])[0]: td for td in tr.find_all('td')}

            def text(cls: str) -> str:
                td = cells.get(cls)
                return td.get_text(' ', strip=True) if td else ''

            col6 = cells.get('col6')
            found_date, keep_until = '', ''
            if col6:
                lines = [t.strip() for t in col6.get_text('\n', strip=True).split('\n') if t.strip()]
                if len(lines) >= 1:
                    found_date = lines[0]
                if len(lines) >= 2:
                    keep_until = lines[1]

            rows.append([
                text('col2'), text('col3'), text('col4'), text('col5'),
                found_date, keep_until,
                text('col7'), text('col8'), text('col9'), text('col10'), text('col11'),
                search_place,
            ])
    return rows, total


def search_combo(session: requests.Session, base_params: dict, search_place: str,
                 rows_per_page: int, delay: float) -> list[list[str]]:
    all_rows: list[list[str]] = []
    page_num = 1
    while True:
        html = fetch_page(session, base_params, page_num, rows_per_page)
        rows, total = parse_rows(html, search_place)
        if not rows:
            break
        all_rows.extend(rows)
        if len(all_rows) >= total:
            break
        page_num += 1
        if delay:
            time.sleep(delay)
    return all_rows


def build_params(category: tuple[str, str, str, str], place_name: str, place_code: str,
                 area_name: str, area_code: str,
                 date_from: tuple[str, str, str], date_to: tuple[str, str, str],
                 include_unknown_date: bool) -> dict:
    major_code, major_name, minor_code, minor_name = category
    return {
        'Length': '0',
        '検索条件.日付.開始年': date_from[0], '検索条件.日付.開始月': date_from[1], '検索条件.日付.開始日': date_from[2],
        '検索条件.日付.終了年': date_to[0], '検索条件.日付.終了月': date_to[1], '検索条件.日付.終了日': date_to[2],
        '検索条件.日付.不明フラグ': 'True' if include_unknown_date else 'False',
        '検索条件.住所.住所コード': area_code, '検索条件.住所.住所名称': area_name,
        '検索条件.場所区分.場所区分コード': place_code, '検索条件.場所区分.場所区分名称': place_name,
        '検索条件.大分類.大分類コード': major_code, '検索条件.大分類.大分類名称': major_name,
        '検索条件.中分類.中分類コード': minor_code, '検索条件.中分類.中分類名称': minor_name,
    }


def print_lists() -> None:
    print('# 分類 (--category): 大分類名 または 中分類名')
    for major_name in MAJOR_CATEGORIES:
        minors = [n for n, v in MINOR_CATEGORIES.items() if v[1] == major_name]
        print(f'  {major_name}: {", ".join(minors)}')
    print('\n# 場所区分 (--place)')
    print('  ' + ', '.join(PLACE_CODES))
    print('\n# 地域 (--area)')
    print('  ' + ', '.join(AREA_CODES))


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    parser.add_argument('--list', action='store_true', help='指定できる分類・場所区分・地域名を一覧表示して終了')
    parser.add_argument('--category', help='分類名 (大分類または中分類)。カンマ区切りで複数指定可。例: カメラ類,上着類,ズボン類')
    parser.add_argument('--date_from', help='拾得日 開始 (YYYY/MM/DD)')
    parser.add_argument('--date_to', help='拾得日 終了 (YYYY/MM/DD)')
    parser.add_argument('--place', help='場所区分。カンマ区切りで複数指定可。例: 路上・建物,鉄道')
    parser.add_argument('--area', help='区市町村・都道府県名。カンマ区切りで複数指定可。例: 文京区,千代田区')
    flag = parser.add_mutually_exclusive_group()
    flag.add_argument('--include_unknown_date', dest='include_unknown_date', action='store_true',
                      default=True, help='拾得日付不明の物品も表示する (デフォルト)')
    flag.add_argument('--no_include_unknown_date', dest='include_unknown_date', action='store_false',
                      help='拾得日付不明の物品を表示しない')
    parser.add_argument('-o', '--output', help='出力 CSV パス (省略時は標準出力)')
    parser.add_argument('--rows_per_page', type=int, default=100, help='1リクエストあたりの取得件数')
    parser.add_argument('--delay', type=float, default=0.5, help='リクエスト間の待機秒数')
    parser.add_argument('-n', '--dry_run', action='store_true', help='リクエストせず、検索する組み合わせのみ表示')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')

    if args.list:
        print_lists()
        return 0

    missing = [n for n in ('category', 'date_from', 'date_to', 'place', 'area') if not getattr(args, n)]
    if missing:
        parser.error(f'次の引数が必要です: {", ".join("--" + m for m in missing)}')

    categories = [resolve_category(c.strip()) for c in args.category.split(',') if c.strip()]
    places = [p.strip() for p in args.place.split(',') if p.strip()]
    for p in places:
        if p not in PLACE_CODES:
            raise SystemExit(f'未知の場所区分: {p!r} (--list で一覧を確認)')
    areas = [a.strip() for a in args.area.split(',') if a.strip()]
    for a in areas:
        if a not in AREA_CODES:
            raise SystemExit(f'未知の地域名: {a!r} (--list で一覧を確認)')
    date_from = parse_date(args.date_from)
    date_to = parse_date(args.date_to)

    combos = list(product(categories, places, areas))

    if args.dry_run:
        for category, place_name, area_name in combos:
            params = build_params(category, place_name, PLACE_CODES[place_name],
                                  area_name, AREA_CODES[area_name],
                                  date_from, date_to, args.include_unknown_date)
            req = requests.Request('GET', f'{BASE_URL}/Result', params=params).prepare()
            print(f'curl -s {req.url!r}')
        return 0

    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})
    # セッション Cookie (ASP.NET_SessionId) を取得
    logger.info(f'GET {BASE_URL}/')
    session.get(f'{BASE_URL}/', timeout=30).raise_for_status()

    all_rows: list[list[str]] = []
    for category, place_name, area_name in combos:
        params = build_params(category, place_name, PLACE_CODES[place_name],
                              area_name, AREA_CODES[area_name],
                              date_from, date_to, args.include_unknown_date)
        rows = search_combo(session, params, place_name, args.rows_per_page, args.delay)
        logger.info(f'分類={category[1]}/{category[3] or "全種類"} 場所={place_name} 地域={area_name}: {len(rows)} 件')
        all_rows.extend(rows)
        if args.delay:
            time.sleep(args.delay)

    if args.output:
        f = open(args.output, 'w', newline='', encoding='utf-8-sig')
    else:
        f = io.TextIOWrapper(sys.stdout.buffer, newline='', encoding='utf-8')
    with f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(all_rows)

    logger.info(f'合計 {len(all_rows)} 件を書き出しました' + (f' -> {args.output}' if args.output else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
