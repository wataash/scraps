#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import glob
import logging
import pathlib
import re

from PIL import Image, ImageColor


epilog = r'''
Examples:
  images_to_a4_pdf.py build 'score/*.webp' score.pdf
  images_to_a4_pdf.py build 'images/*.png' out.pdf --margin_x 40 --margin_y 40 --gap 24
  images_to_a4_pdf.py build 'score/*.webp' score.pdf --align_x left --scale 1.3
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
logger.setLevel(logging.DEBUG)
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


def content_size(page_size_px: tuple[int, int], margin_x: int, margin_y: int) -> tuple[int, int]:
    width = page_size_px[0] - margin_x * 2
    height = page_size_px[1] - margin_y * 2
    if width <= 0 or height <= 0:
        raise SystemExit('margins are too large for the page size')
    return width, height


def image_target_size(
    img: Image.Image,
    content_width: int,
    content_height: int,
    *,
    no_upscale: bool,
    scale: float | None,
) -> tuple[int, int]:
    if scale is not None:
        return round(img.width * scale), round(img.height * scale)

    if no_upscale and img.width <= content_width:
        target_width = img.width
        target_height = img.height
    else:
        ratio = content_width / img.width
        target_width = content_width
        target_height = round(img.height * ratio)

    if target_height > content_height:
        ratio = content_height / target_height
        target_width = round(target_width * ratio)
        target_height = content_height
    return target_width, target_height


def image_x(page_width: int, margin_x: int, target_width: int, align_x: str) -> int:
    if align_x == 'left':
        return margin_x
    if align_x == 'right':
        return page_width - margin_x - target_width
    if align_x == 'center':
        return (page_width - target_width) // 2
    raise ValueError(f'unsupported align_x: {align_x}')


def build_pages(
    files: list[pathlib.Path],
    *,
    page_size_px: tuple[int, int],
    margin_x: int,
    margin_y: int,
    gap: int,
    background: tuple[int, int, int],
    no_upscale: bool,
    align_x: str,
    scale: float | None,
) -> list[Image.Image]:
    page_width, _ = page_size_px
    content_width, content_height = content_size(page_size_px, margin_x, margin_y)

    pages: list[Image.Image] = []
    page = make_blank_page(page_size_px, background)
    y = margin_y
    count_on_page = 0

    for path in files:
        with Image.open(path) as src:
            img = src.convert('RGB')
        target_width, target_height = image_target_size(
            img,
            content_width,
            content_height,
            no_upscale=no_upscale,
            scale=scale,
        )
        resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        if count_on_page and y + target_height > margin_y + content_height:
            pages.append(page)
            page = make_blank_page(page_size_px, background)
            y = margin_y
            count_on_page = 0

        x = image_x(page_width, margin_x, target_width, align_x)
        page.paste(resized, (x, y))
        y += target_height + gap
        count_on_page += 1

    pages.append(page)
    return pages


def estimate_layout(
    files: list[pathlib.Path],
    *,
    page_size_px: tuple[int, int],
    margin_x: int,
    margin_y: int,
    gap: int,
    no_upscale: bool,
    scale: float | None,
) -> tuple[int, list[float]]:
    content_width, content_height = content_size(page_size_px, margin_x, margin_y)

    pages = 1
    y = margin_y
    count_on_page = 0
    effective_scales: list[float] = []
    for path in files:
        with Image.open(path) as img:
            target_width, target_height = image_target_size(
                img,
                content_width,
                content_height,
                no_upscale=no_upscale,
                scale=scale,
            )
            effective_scales.append(target_width / img.width)

        if count_on_page and y + target_height > margin_y + content_height:
            pages += 1
            y = margin_y
            count_on_page = 0
        y += target_height + gap
        count_on_page += 1
    return pages, effective_scales


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'expected integer: {value}') from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f'expected positive integer: {value}')
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'expected float: {value}') from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f'expected positive float: {value}')
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
    content_width, content_height = content_size(page_size_px, args.margin_x, args.margin_y)
    output_pdf = pathlib.Path(args.output_pdf)

    if args.dry_run:
        page_count, effective_scales = estimate_layout(
            files,
            page_size_px=page_size_px,
            margin_x=args.margin_x,
            margin_y=args.margin_y,
            gap=args.gap,
            no_upscale=args.no_upscale,
            scale=args.scale,
        )
        print(f'input_images={len(files)}')
        print(f'page_size_px={page_size_px[0]}x{page_size_px[1]}')
        print(f'content_size_px={content_width}x{content_height}')
        print(f'estimated_pages={page_count}')
        print(f'align_x={args.align_x}')
        print(f'scale={args.scale}')
        print(f'effective_scale_range={min(effective_scales):.3g}..{max(effective_scales):.3g}')
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
        align_x=args.align_x,
        scale=args.scale,
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
    subparser.add_argument('--margin_x', type=non_negative_int, default=40, help='horizontal page margin in pixels')
    subparser.add_argument('--margin_y', type=non_negative_int, default=40, help='vertical page margin in pixels')
    subparser.add_argument('--gap', type=non_negative_int, default=32)
    subparser.add_argument('--background', type=parse_background, default=parse_background('white'))
    subparser.add_argument('--sort', choices=['natural'], default='natural')
    subparser.add_argument('--no_upscale', action='store_true')
    subparser.add_argument('--align_x', choices=['left', 'center', 'right'], default='center', help='horizontal placement of each image')
    subparser.add_argument(
        '--scale',
        type=positive_float,
        help='scale each image exactly; output may overflow the page',
    )
    subparser.add_argument('-n', '--dry_run', action='store_true')

    args = parser.parse_args()
    logger.debug(f'{args=}')
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
