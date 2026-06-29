#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
score_barlines.py -h
score_barlines.py detect_barlines a.webp
score_barlines.py detect_barlines a.webp --json --overlay a_barlines.webp
score_barlines.py detect_barlines a.webp --overlay a_barlines.png --wrap-width 2400
score_barlines.py detect_barlines a.webp --split-dir measures
score_barlines.py measures_pdf a.webp out.pdf --margin 40 --scale 1.0 --measure-numbers
'''[1:]

import argparse
import json
import logging
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Literal

import cv2
import numpy as np
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


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


@dataclass(frozen=True)
class Staff:
    y_lines: list[int]
    top: int
    bottom: int
    spacing: float


@dataclass(frozen=True)
class VerticalCandidate:
    x: int
    height: int
    width: int
    side_density: float
    side_pixels: int


@dataclass(frozen=True)
class Barline:
    x: int
    members: list[int]
    kind: Literal['single', 'double']
    score: float
    candidates: list[VerticalCandidate]


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('detect_barlines', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=detect_barlines)
    subparser.add_argument('image', type=Path)
    subparser.add_argument('--json', action='store_true')
    subparser.add_argument('--overlay', type=Path, help='Write a visual check image with detected x positions.')
    subparser.add_argument('--wrap-width', type=int,
                           help='Wrap the overlay image into rows of this width before saving.')
    subparser.add_argument('--split-dir', type=Path,
                           help='Write image slices split by detected barline x positions as numbered .webp files.')

    subparser = subparsers.add_parser('measures_pdf', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=measures_pdf)
    subparser.add_argument('source_image', type=Path,
                           help='Original full-width score image used to create measure slices.')
    subparser.add_argument('output_pdf', type=Path)
    subparser.add_argument('--margin', type=int, default=40, help='Page margin in output pixels.')
    subparser.add_argument('--scale', type=float, default=1.0, help='Measure image scale before layout.')
    subparser.add_argument('--dpi', type=int, default=300, help='PDF resolution; A4 pixels are derived from this.')
    subparser.add_argument('--row-gap', type=int, default=0, help='Vertical gap between laid-out rows in pixels.')
    subparser.add_argument('--page-orientation', choices=['portrait', 'landscape'], default='portrait')
    subparser.add_argument('--break-after', action='append', default=[],
                           help='Force a row break after measure numbers. Accepts comma lists and ranges, e.g. 4,10-12.')
    subparser.add_argument('--exclude', action='append', default=[],
                           help='Exclude measure numbers from the PDF. Accepts comma lists and ranges, e.g. 1,10-12.')
    subparser.add_argument('--measure-numbers', action='store_true',
                           help='Draw 3-digit measure numbers on the PDF for visual checking.')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    return args.func(args)


def detect_barlines(args: argparse.Namespace) -> int:
    image = cv2.imread(str(args.image), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f'Could not read image: {args.image}')
    binary = binarize(image)
    staff = detect_staff(binary, image)
    candidates = find_vertical_candidates(binary, staff)
    accepted = accept_barline_candidates(candidates, staff, image.shape[1])
    barlines = group_barlines(accepted, staff)

    if args.overlay:
        write_overlay(image, args.overlay, staff, barlines, args.wrap_width)

    if args.split_dir:
        write_splits(image, args.split_dir, barlines)

    if args.json:
        print(json.dumps({
            'image': str(args.image),
            'staff': asdict(staff),
            'barlines': [asdict(b) for b in barlines],
        }, ensure_ascii=False, indent=2))
    else:
        for idx, barline in enumerate(barlines, start=1):
            members = ','.join(str(x) for x in barline.members)
            print(f'{idx}\tx={barline.x}\t{barline.kind}\tmembers={members}\tscore={barline.score:.3f}')
    return 0


def measures_pdf(args: argparse.Namespace) -> int:
    if args.margin < 0:
        raise ValueError('--margin must be non-negative')
    if args.scale <= 0:
        raise ValueError('--scale must be positive')
    if args.dpi <= 0:
        raise ValueError('--dpi must be positive')
    if args.row_gap < 0:
        raise ValueError('--row-gap must be non-negative')

    page_width, page_height = a4_pixels(args.dpi, args.page_orientation)
    content_width = page_width - args.margin * 2
    content_height = page_height - args.margin * 2
    if content_width <= 0 or content_height <= 0:
        raise ValueError('margin is too large for the page size')

    source = cv2.imread(str(args.source_image), cv2.IMREAD_GRAYSCALE)
    if source is None:
        raise RuntimeError(f'Could not read source image: {args.source_image}')
    barlines = find_barlines(source)
    break_after = parse_measure_numbers(args.break_after)
    exclude = parse_measure_numbers(args.exclude)
    measures = make_measure_images(source, barlines, args.scale, content_width, args.measure_numbers, exclude)
    rows = layout_measure_rows(measures, content_width, break_after)
    pages = render_pdf_pages(rows, page_width, page_height, args.margin, args.row_gap)

    args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
    first, *rest = pages
    first.save(args.output_pdf, 'PDF', resolution=args.dpi, save_all=True, append_images=rest)
    logger.info(
        'wrote %s: %d measures, %d rows, %d pages',
        args.output_pdf,
        len(measures),
        len(rows),
        len(pages),
    )
    return 0


def parse_measure_numbers(values: list[str]) -> set[int]:
    numbers = set()
    for value in values:
        for part in value.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                start_text, end_text = part.split('-', 1)
                start = parse_measure_number(start_text)
                end = parse_measure_number(end_text)
                if end < start:
                    raise ValueError(f'Invalid descending measure range: {part}')
                numbers.update(range(start, end + 1))
            else:
                numbers.add(parse_measure_number(part))
    return numbers


def parse_measure_number(value: str) -> int:
    value = value.strip()
    if not value.isdecimal():
        raise ValueError(f'Invalid measure number: {value}')
    number = int(value)
    if number < 1:
        raise ValueError(f'Measure number must be >= 1: {value}')
    return number


def find_barlines(gray: np.ndarray) -> list[Barline]:
    binary = binarize(gray)
    staff = detect_staff(binary, gray)
    candidates = find_vertical_candidates(binary, staff)
    accepted = accept_barline_candidates(candidates, staff, gray.shape[1])
    return group_barlines(accepted, staff)


def a4_pixels(dpi: int, orientation: str) -> tuple[int, int]:
    width = round(210 / 25.4 * dpi)
    height = round(297 / 25.4 * dpi)
    if orientation == 'landscape':
        return height, width
    return width, height


def make_measure_images(
    gray: np.ndarray,
    barlines: list[Barline],
    scale: float,
    max_width: int,
    measure_numbers: bool,
    exclude: set[int],
) -> list[tuple[int, Image.Image]]:
    boundaries = [0, *[barline.x for barline in barlines], gray.shape[1]]
    measures = []
    for idx, (x0, x1) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        if x1 <= x0:
            continue
        if idx in exclude:
            continue
        measure = Image.fromarray(gray[:, x0:x1]).convert('RGB')
        if scale != 1.0:
            width = max(1, round(measure.width * scale))
            height = max(1, round(measure.height * scale))
            measure = measure.resize((width, height), Image.Resampling.LANCZOS)
        if measure.width > max_width:
            height = max(1, round(measure.height * max_width / measure.width))
            measure = measure.resize((max_width, height), Image.Resampling.LANCZOS)
        if measure_numbers:
            draw_measure_number(measure, idx)
        measures.append((idx, measure))
    return measures


def draw_measure_number(image: Image.Image, idx: int) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    label = f'{idx:03d}'
    bbox = draw.textbbox((0, 0), label, font=font)
    padding = 3
    x = 3
    y = 3
    rect = (
        x - padding,
        y - padding,
        x + bbox[2] - bbox[0] + padding,
        y + bbox[3] - bbox[1] + padding,
    )
    draw.rectangle(rect, fill='white', outline='black')
    draw.text((x, y), label, fill='red', font=font)


def layout_measure_rows(
    measures: list[tuple[int, Image.Image]],
    max_width: int,
    break_after: set[int],
) -> list[list[Image.Image]]:
    rows: list[list[Image.Image]] = []
    current: list[Image.Image] = []
    current_width = 0
    for idx, measure in measures:
        if current and current_width + measure.width > max_width:
            rows.append(current)
            current = []
            current_width = 0

        current.append(measure)
        current_width += measure.width

        if idx in break_after:
            rows.append(current)
            current = []
            current_width = 0

    if current:
        rows.append(current)
    return rows


def render_pdf_pages(
    rows: list[list[Image.Image]],
    page_width: int,
    page_height: int,
    margin: int,
    row_gap: int,
) -> list[Image.Image]:
    pages: list[Image.Image] = []
    page = Image.new('RGB', (page_width, page_height), 'white')
    y = margin
    max_y = page_height - margin

    for row in rows:
        row_height = max(image.height for image in row)
        if y > margin and y + row_height > max_y:
            pages.append(page)
            page = Image.new('RGB', (page_width, page_height), 'white')
            y = margin
        if y + row_height > max_y:
            raise RuntimeError(f'A row is too tall for the page: {row_height}px')

        x = margin
        for image in row:
            page.paste(image, (x, y))
            x += image.width
        y += row_height + row_gap

    pages.append(page)
    return pages


def binarize(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return binary


def detect_staff(binary: np.ndarray, gray: np.ndarray | None = None) -> Staff:
    try:
        return detect_staff_from_binary(binary)
    except RuntimeError:
        if gray is None:
            raise
        logger.info('falling back to light staff-line detection')
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, staff_binary = cv2.threshold(blur, 230, 255, cv2.THRESH_BINARY_INV)
        return detect_staff_from_binary(staff_binary, kernel_width_cap=600, min_row_fraction=0.08)


def detect_staff_from_binary(
        binary: np.ndarray,
        kernel_width_cap: int | None = None,
        min_row_fraction: float = 0.2,
) -> Staff:
    height, width = binary.shape
    kernel_width = max(40, width // 20)
    if kernel_width_cap is not None:
        kernel_width = min(kernel_width, kernel_width_cap)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    row_counts = (horizontal > 0).sum(axis=1)
    min_row_pixels = min(width * 0.2, max(200, width * min_row_fraction))
    rows = np.where(row_counts > min_row_pixels)[0]
    clusters = cluster_indices(rows, max_gap=2)
    y_lines = [weighted_center(cluster, row_counts) for cluster in clusters]

    if len(y_lines) < 5:
        raise RuntimeError(f'Could not find five staff lines; found {y_lines}')

    y_lines = choose_best_staff_five(y_lines, row_counts)
    spacing = float(np.median(np.diff(y_lines)))
    margin = max(4, int(round(spacing * 0.35)))
    return Staff(y_lines=y_lines, top=max(0, y_lines[0] - margin), bottom=min(height, y_lines[-1] + margin + 1),
                 spacing=spacing)


def choose_best_staff_five(y_lines: list[int], row_counts: np.ndarray) -> list[int]:
    best: tuple[float, list[int]] | None = None
    for start in range(0, len(y_lines) - 4):
        group = y_lines[start:start + 5]
        gaps = np.diff(group)
        if gaps.min() < 4:
            continue
        score = float(np.std(gaps) - np.mean(row_counts[group]) / max(1, row_counts.max()))
        if best is None or score < best[0]:
            best = (score, group)
    if best is None:
        raise RuntimeError(f'Could not choose a regular five-line staff from {y_lines}')
    return best[1]


def find_vertical_candidates(binary: np.ndarray, staff: Staff) -> list[VerticalCandidate]:
    roi = binary[staff.top:staff.bottom, :]
    staff_height = staff.y_lines[-1] - staff.y_lines[0]
    kernel_height = max(8, int(round(staff_height * 0.95)))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_height))
    vertical = cv2.morphologyEx(roi, cv2.MORPH_OPEN, vertical_kernel)
    col_counts = (vertical > 0).sum(axis=0)
    columns = np.where(col_counts >= max(8, staff_height * 0.55))[0]
    clusters = cluster_indices(columns, max_gap=3)

    staff_mask = np.zeros_like(roi, dtype=bool)
    for y in staff.y_lines:
        local_y = y - staff.top
        staff_mask[max(0, local_y - 1):min(roi.shape[0], local_y + 2), :] = True
    non_staff_ink = (roi > 0) & (~staff_mask)

    candidates = []
    for cluster in clusters:
        x = weighted_center(cluster, np.maximum(col_counts, 1))
        side_pixels, side_density = measure_side_ink(non_staff_ink, x, staff)
        candidates.append(VerticalCandidate(
            x=x,
            height=int(col_counts[x]),
            width=len(cluster),
            side_density=side_density,
            side_pixels=side_pixels,
        ))
    return candidates


def measure_side_ink(non_staff_ink: np.ndarray, x: int, staff: Staff) -> tuple[int, float]:
    half_window = max(12, int(round(staff.spacing * 1.2)))
    exclude = 2
    left = max(0, x - half_window)
    right = min(non_staff_ink.shape[1], x + half_window + 1)
    window = non_staff_ink[:, left:right].copy()
    ex_left = max(0, x - exclude - left)
    ex_right = min(window.shape[1], x + exclude + 1 - left)
    window[:, ex_left:ex_right] = False
    side_pixels = int(window.sum())
    return side_pixels, side_pixels / max(1, window.size)


def accept_barline_candidates(candidates: list[VerticalCandidate], staff: Staff, image_width: int) -> list[VerticalCandidate]:
    staff_height = staff.y_lines[-1] - staff.y_lines[0]
    edge_margin = int(round(staff.spacing * 3))
    repeat_candidate_ids = find_repeat_barline_candidate_ids(candidates, staff) if staff.spacing <= 12 else set()
    accepted = []
    for candidate in candidates:
        if candidate.height < staff_height * 0.95 or candidate.height > staff_height * 1.16:
            continue
        if id(candidate) in repeat_candidate_ids:
            accepted.append(candidate)
            continue
        near_edge = candidate.x < edge_margin or image_width - candidate.x < edge_margin
        if candidate.side_density > (0.05 if near_edge else 0.12):
            continue
        if (candidate.width >= 4
                or (candidate.width >= 3 and candidate.side_density <= 0.05)
                or (candidate.width >= 2
                    and candidate.side_density <= 0.05
                    and candidate.height <= staff_height * 1.08)
                or has_close_partner(candidate, candidates, staff)):
            accepted.append(candidate)
    return accepted


def find_repeat_barline_candidate_ids(candidates: list[VerticalCandidate], staff: Staff) -> set[int]:
    staff_height = staff.y_lines[-1] - staff.y_lines[0]
    full_height = [
        candidate for candidate in candidates
        if staff_height * 0.95 <= candidate.height <= staff_height * 1.16
    ]

    repeat_candidate_ids = set()
    groups: list[list[VerticalCandidate]] = []
    for candidate in sorted(full_height, key=lambda item: item.x):
        if not groups or candidate.x - groups[-1][-1].x > staff.spacing:
            groups.append([])
        groups[-1].append(candidate)

    for group in groups:
        if (len(group) >= 2
                and sum(candidate.width for candidate in group) >= 6
                and max(candidate.width for candidate in group) >= 4
                and group[-1].x - group[0].x <= staff.spacing * 2.0
                and max(candidate.side_density for candidate in group) <= 0.22):
            repeat_candidate_ids.update(id(candidate) for candidate in group)
    return repeat_candidate_ids


def has_close_partner(candidate: VerticalCandidate, candidates: list[VerticalCandidate], staff: Staff) -> bool:
    return any(
        other is not candidate
        and other.width >= 3
        and abs(other.x - candidate.x) <= staff.spacing
        for other in candidates
    )


def group_barlines(candidates: list[VerticalCandidate], staff: Staff) -> list[Barline]:
    if not candidates:
        return []
    max_gap = max(3, int(round(staff.spacing)))
    groups: list[list[VerticalCandidate]] = []
    for candidate in sorted(candidates, key=lambda item: item.x):
        if not groups or candidate.x - groups[-1][-1].x > max_gap:
            groups.append([])
        groups[-1].append(candidate)

    barlines = []
    for group in groups:
        kind = 'double' if len(group) >= 2 else 'single'
        x = min(c.x for c in group) if kind == 'double' else group[0].x
        density = float(np.mean([c.side_density for c in group]))
        score = float(np.mean([c.height for c in group]) / max(1.0, staff.y_lines[-1] - staff.y_lines[0]) - density)
        barlines.append(Barline(x=x, members=[c.x for c in group], kind=kind, score=score, candidates=group))
    return barlines


def cluster_indices(indices: np.ndarray, max_gap: int) -> list[np.ndarray]:
    if len(indices) == 0:
        return []
    boundaries = np.where(np.diff(indices) > max_gap)[0] + 1
    return np.split(indices, boundaries)


def weighted_center(indices: np.ndarray, weights: np.ndarray) -> int:
    return int(round(float(np.average(indices, weights=weights[indices]))))


def wrap_image(image: np.ndarray, wrap_width: int) -> np.ndarray:
    if wrap_width <= 0:
        raise RuntimeError(f'wrap width must be positive: {wrap_width}')

    height, width, channels = image.shape
    if wrap_width >= width:
        return image

    rows = (width + wrap_width - 1) // wrap_width
    wrapped = np.full((rows * height, wrap_width, channels), 255, dtype=image.dtype)
    for row in range(rows):
        src_x0 = row * wrap_width
        src_x1 = min(src_x0 + wrap_width, width)
        dst_y0 = row * height
        wrapped[dst_y0:dst_y0 + height, :src_x1 - src_x0] = image[:, src_x0:src_x1]
    return wrapped


def write_overlay(
        gray: np.ndarray,
        overlay_path: Path,
        staff: Staff,
        barlines: list[Barline],
        wrap_width: int | None,
) -> None:
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for y in staff.y_lines:
        cv2.line(image, (0, y), (image.shape[1] - 1, y), (255, 200, 0), 1)
    for idx, barline in enumerate(barlines, start=1):
        cv2.line(image, (barline.x, 0), (barline.x, image.shape[0] - 1), (0, 0, 255), 2)
        cv2.putText(image, str(idx), (barline.x + 4, max(15, staff.top - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 0, 255), 1, cv2.LINE_AA)
    if wrap_width is not None:
        original_shape = image.shape
        image = wrap_image(image, wrap_width)
        logger.info('wrapped overlay: %dx%d -> %dx%d',
                    original_shape[1], original_shape[0], image.shape[1], image.shape[0])
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(overlay_path), image)
    if not ok:
        raise RuntimeError(f'Could not write overlay: {overlay_path}')


def write_splits(gray: np.ndarray, split_dir: Path, barlines: list[Barline]) -> None:
    split_dir.mkdir(parents=True, exist_ok=True)
    for old_output in split_dir.glob('[0-9][0-9][0-9].webp'):
        old_output.unlink()
    boundaries = [0, *[barline.x for barline in barlines], gray.shape[1]]
    for idx, (x0, x1) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        if x1 <= x0:
            continue
        output = split_dir / f'{idx:03d}.webp'
        ok = cv2.imwrite(str(output), gray[:, x0:x1])
        if not ok:
            raise RuntimeError(f'Could not write split image: {output}')


if __name__ == '__main__':
    raise SystemExit(main())
