#!/home/wsh/opt_/pyvenv2/bin/python
# SPDX-License-Identifier: Apache-2.0

import argparse
import glob
import logging
import pathlib
import re
import typing as t

from PIL import Image, ImageColor


epilog = r'''
Examples:
  images_to_a4_pdf.py build 'score/*.webp' score.pdf
  images_to_a4_pdf.py build 'images/*.png' out.pdf --margin_x 120 --margin_y 140 --gap 24
  images_to_a4_pdf.py build 'score/*.webp' score.pdf -n
'''[1:]


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
logger.setLevel(logging.INFO)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


def natural_key(path: pathlib.Path) -> list[tuple[int, int | str]]:
    parts = re.split(r'(\d+)', str(path))
    key: list[tuple[int, int | str]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return key


def page_pixels(page_size: str, orientation: str, dpi: int) -> tuple[int, int]:
    if page_size != 'a4':
        raise ValueError(f'unsupported page size: {page_size}')

    # ISO A4: 210 x 297 mm.
    width = round(dpi * 210 / 25.4)
    height = round(dpi * 297 / 25.4)
    if orientation == 'landscape':
        width, height = height, width
    return width, height


def parse_background(value: str) -> tuple[int, int, int]:
    try:
        r, g, b = ImageColor.getrgb(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'invalid color: {value}') from exc
    if not isinstance(r, int) or not isinstance(g, int) or not isinstance(b, int):
        raise argparse.ArgumentTypeError(f'invalid RGB color: {value}')
    return r, g, b


def expand_input_pattern(pattern: str) -> list[pathlib.Path]:
    matches = [pathlib.Path(path) for path in glob.glob(pattern, recursive=True)]
    return sorted((path for path in matches if path.is_file()), key=natural_key)


def make_blank_page(size: tuple[int, int], background: tuple[int, int, int]) -> Image.Image:
    return Image.new('RGB', size, background)


def image_target_size(img: Image.Image, content_width: int, *, no_upscale: bool) -> tuple[int, int]:
    if no_upscale and img.width <= content_width:
        return img.width, img.height

    scale = content_width / img.width
    return content_width, round(img.height * scale)


def build_pages(
    files: list[pathlib.Path],
    *,
    page_size_px: tuple[int, int],
    margin_x: int,
    margin_y: int,
    gap: int,
    background: tuple[int, int, int],
    no_upscale: bool,
) -> list[Image.Image]:
    page_width, page_height = page_size_px
    content_width = page_width - margin_x * 2
    content_height = page_height - margin_y * 2
    if content_width <= 0 or content_height <= 0:
        raise SystemExit('margins are too large for the page size')

    pages: list[Image.Image] = []
    page = make_blank_page(page_size_px, background)
    y = margin_y
    count_on_page = 0

    for path in files:
        with Image.open(path) as src:
            img = src.convert('RGB')
        target_width, target_height = image_target_size(img, content_width, no_upscale=no_upscale)
        if target_height > content_height:
            scale = content_height / target_height
            target_width = round(target_width * scale)
            target_height = content_height
        resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        if count_on_page and y + target_height > margin_y + content_height:
            pages.append(page)
            page = make_blank_page(page_size_px, background)
            y = margin_y
            count_on_page = 0

        x = (page_width - target_width) // 2
        page.paste(resized, (x, y))
        y += target_height + gap
        count_on_page += 1

    pages.append(page)
    return pages


def estimate_page_count(
    files: list[pathlib.Path],
    *,
    page_size_px: tuple[int, int],
    margin_x: int,
    margin_y: int,
    gap: int,
    no_upscale: bool,
) -> int:
    page_width, page_height = page_size_px
    content_width = page_width - margin_x * 2
    content_height = page_height - margin_y * 2
    if content_width <= 0 or content_height <= 0:
        raise SystemExit('margins are too large for the page size')

    pages = 1
    y = margin_y
    count_on_page = 0
    for path in files:
        with Image.open(path) as img:
            target_width, target_height = image_target_size(img, content_width, no_upscale=no_upscale)
        if target_height > content_height:
            scale = content_height / target_height
            target_height = content_height
            target_width = round(target_width * scale)
        _ = target_width

        if count_on_page and y + target_height > margin_y + content_height:
            pages += 1
            y = margin_y
            count_on_page = 0
        y += target_height + gap
        count_on_page += 1
    return pages


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'expected integer: {value}') from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f'expected positive integer: {value}')
    return parsed


def non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'expected integer: {value}') from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError(f'expected non-negative integer: {value}')
    return parsed


def cmd_build(args: argparse.Namespace) -> int:
    files = expand_input_pattern(args.input_pattern)
    if not files:
        raise SystemExit(f'no input images matched: {args.input_pattern}')

    page_size_px = page_pixels(args.page_size, args.orientation, args.dpi)
    output_pdf = pathlib.Path(args.output_pdf)

    if args.dry_run:
        page_count = estimate_page_count(
            files,
            page_size_px=page_size_px,
            margin_x=args.margin_x,
            margin_y=args.margin_y,
            gap=args.gap,
            no_upscale=args.no_upscale,
        )
        print(f'input_images={len(files)}')
        print(f'page_size_px={page_size_px[0]}x{page_size_px[1]}')
        print(f'estimated_pages={page_count}')
        print(f'output_pdf={output_pdf}')
        return 0

    pages = build_pages(
        files,
        page_size_px=page_size_px,
        margin_x=args.margin_x,
        margin_y=args.margin_y,
        gap=args.gap,
        background=args.background,
        no_upscale=args.no_upscale,
    )

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    logger.info('write %s (%d images, %d pages)', output_pdf, len(files), len(pages))
    pages[0].save(output_pdf, 'PDF', resolution=float(args.dpi), save_all=True, append_images=pages[1:])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('build', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=cmd_build)
    subparser.add_argument('input_pattern', help='input image glob pattern')
    subparser.add_argument('output_pdf', help='output PDF path')
    subparser.add_argument('--page_size', choices=['a4'], default='a4')
    subparser.add_argument('--orientation', choices=['portrait', 'landscape'], default='portrait')
    subparser.add_argument('--dpi', type=positive_int, default=300)
    subparser.add_argument('--margin_x', type=non_negative_int, default=140)
    subparser.add_argument('--margin_y', type=non_negative_int, default=160)
    subparser.add_argument('--gap', type=non_negative_int, default=32)
    subparser.add_argument('--background', type=parse_background, default=parse_background('white'))
    subparser.add_argument('--sort', choices=['natural'], default='natural')
    subparser.add_argument('--no_upscale', action='store_true')
    subparser.add_argument('-n', '--dry_run', action='store_true')

    args = parser.parse_args()
    logger.debug(f'{args=}')
    return t.cast(t.Callable[[argparse.Namespace], int], args.func)(args)


if __name__ == '__main__':
    raise SystemExit(main())
