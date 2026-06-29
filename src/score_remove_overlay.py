#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import logging
import pathlib
import statistics
import sys
import typing as t

from PIL import Image


epilog = r'''
Examples:
  score_remove_overlay.py process just_img just_img_clean
  score_remove_overlay.py process just_img just_img_clean --pattern '*.webp'
  score_remove_overlay.py process just_img just_img_clean --min_chroma 14 --cursor_min_column_pixels 20
'''[1:]


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


def luma(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def chroma(rgb: tuple[int, int, int]) -> int:
    return max(rgb) - min(rgb)


def neutralize(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    y = int(round(luma(rgb)))
    # Score backgrounds are white or pale gray. Push colored overlay backgrounds
    # back toward neutral paper without making antialiased ink disappear.
    if y >= 215:
        y = 255
    return (y, y, y)


def is_colored_overlay(rgb: tuple[int, int, int], args: argparse.Namespace) -> bool:
    if luma(rgb) < args.min_overlay_luma:
        return False
    return chroma(rgb) >= args.min_chroma


def is_cursor_pixel(rgb: tuple[int, int, int], args: argparse.Namespace) -> bool:
    if luma(rgb) < args.min_cursor_luma:
        return False
    return chroma(rgb) >= args.cursor_min_chroma


def expand_columns(columns: set[int], width: int, radius: int) -> set[int]:
    expanded: set[int] = set()
    for x in columns:
        for nx in range(max(0, x - radius), min(width, x + radius + 1)):
            expanded.add(nx)
    return expanded


def contiguous_groups(values: set[int]) -> list[list[int]]:
    groups: list[list[int]] = []
    for value in sorted(values):
        if not groups or value != groups[-1][-1] + 1:
            groups.append([value])
        else:
            groups[-1].append(value)
    return groups


def detect_cursor_columns(src: Image.Image, args: argparse.Namespace) -> set[int]:
    width, height = src.size
    pix = src.load()
    candidate_columns: set[int] = set()
    min_pixels = args.cursor_min_column_pixels
    if min_pixels <= 0:
        min_pixels = max(8, height // 12)
    for x in range(width):
        ys = [y for y in range(height) if is_cursor_pixel(pix[x, y], args)]
        if len(ys) < min_pixels:
            continue
        span = ys[-1] - ys[0] + 1
        if span >= args.cursor_min_vertical_span:
            candidate_columns.add(x)
    columns: set[int] = set()
    for group in contiguous_groups(candidate_columns):
        if len(group) <= args.cursor_max_width:
            columns.update(group)
    return expand_columns(columns, width, args.cursor_expand)


def detect_vertical_artifact_columns(img: Image.Image, args: argparse.Namespace) -> set[int]:
    width, height = img.size
    pix = img.load()
    candidate_columns: set[int] = set()
    min_pixels = max(8, int(height * args.artifact_min_column_ratio))
    for x in range(width):
        ys: list[int] = []
        values: list[float] = []
        for y in range(height):
            value = luma(pix[x, y])
            if args.artifact_min_luma <= value <= args.artifact_max_luma:
                ys.append(y)
                values.append(value)
        if len(ys) < min_pixels:
            continue
        if ys[-1] - ys[0] + 1 < args.cursor_min_vertical_span:
            continue
        if statistics.median(values) <= args.artifact_max_median_luma:
            candidate_columns.add(x)
    columns: set[int] = set()
    for group in contiguous_groups(candidate_columns):
        if len(group) <= args.cursor_max_width:
            columns.update(group)
    return expand_columns(columns, width, args.cursor_expand)


def column_neighbor_color(img: Image.Image, x: int, y: int, cursor_columns: set[int]) -> tuple[int, int, int]:
    width, _height = img.size
    pix = img.load()
    samples: list[tuple[int, int, int]] = []
    for direction in (-1, 1):
        nx = x + direction
        while 0 <= nx < width and nx in cursor_columns:
            nx += direction
        if 0 <= nx < width:
            samples.append(pix[nx, y])
    if len(samples) == 2:
        return tuple(int(round(statistics.mean(values))) for values in zip(*samples))
    if samples:
        return samples[0]
    return (255, 255, 255)


def process_image(path: pathlib.Path, out_path: pathlib.Path, args: argparse.Namespace) -> tuple[int, int]:
    src = Image.open(path).convert('RGB')
    dst = src.copy()
    src_pix = src.load()
    dst_pix = dst.load()
    width, height = src.size

    cursor_columns = detect_cursor_columns(src, args)
    overlay_pixels = 0
    cursor_pixels = 0

    for y in range(height):
        for x in range(width):
            rgb = src_pix[x, y]
            if is_colored_overlay(rgb, args):
                dst_pix[x, y] = neutralize(rgb)
                overlay_pixels += 1

    cursor_columns.update(detect_vertical_artifact_columns(dst, args))
    # Run cursor repair after broad overlay neutralization so a thin playback
    # line or its compression shadow is replaced from already-clean neighbors.
    for y in range(height):
        for x in cursor_columns:
            dst_pix[x, y] = column_neighbor_color(dst, x, y, cursor_columns)
            cursor_pixels += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    dst.save(out_path)
    return overlay_pixels, cursor_pixels


def iter_images(input_dir: pathlib.Path, pattern: str) -> list[pathlib.Path]:
    return sorted(path for path in input_dir.glob(pattern) if path.is_file())


def process(args: argparse.Namespace) -> int:
    input_dir = args.input_dir
    output_dir = args.output_dir
    paths = iter_images(input_dir, args.pattern)
    if not paths:
        raise SystemExit(f'no files matched: {input_dir / args.pattern}')
    total_overlay = 0
    total_cursor = 0
    for path in paths:
        out_path = output_dir / path.name
        overlay_pixels, cursor_pixels = process_image(path, out_path, args)
        total_overlay += overlay_pixels
        total_cursor += cursor_pixels
        logger.info('%s -> %s overlay=%d cursor=%d', path, out_path, overlay_pixels, cursor_pixels)
    logger.info('processed=%d overlay=%d cursor=%d', len(paths), total_overlay, total_cursor)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('process', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=process)
    subparser.add_argument('input_dir', type=pathlib.Path)
    subparser.add_argument('output_dir', type=pathlib.Path)
    subparser.add_argument('--pattern', default='*.webp')
    subparser.add_argument('--min_chroma', type=int, default=14)
    subparser.add_argument('--min_overlay_luma', type=float, default=25)
    subparser.add_argument('--cursor_min_chroma', type=int, default=12)
    subparser.add_argument('--min_cursor_luma', type=float, default=25)
    subparser.add_argument('--cursor_min_column_pixels', type=int, default=0)
    subparser.add_argument('--cursor_min_vertical_span', type=int, default=80)
    subparser.add_argument('--cursor_max_width', type=int, default=12)
    subparser.add_argument('--cursor_expand', type=int, default=1)
    subparser.add_argument('--artifact_min_column_ratio', type=float, default=0.65)
    subparser.add_argument('--artifact_min_luma', type=float, default=70)
    subparser.add_argument('--artifact_max_luma', type=float, default=245)
    subparser.add_argument('--artifact_max_median_luma', type=float, default=235)

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    return t.cast(t.Callable[[argparse.Namespace], int], args.func)(args)


if __name__ == '__main__':
    raise SystemExit(main())
