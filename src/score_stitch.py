#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import logging
import pathlib
import sys
import typing as t

import numpy as np
from PIL import Image


epilog = r'''
Examples:
  score_stitch.py stitch feel feel.webp
  score_stitch.py stitch feel feel.webp --kmax 600 --threshold 12
  score_stitch.py stitch feel feel.webp -n
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


def default_kmax(width: int) -> int:
    return min(width - 1, max(400, int(width * 0.75)))


def find_overlap(
        a: np.ndarray,
        b: np.ndarray,
        kmin: int,
        kmax: int,
        score_margin: float,
        larger_min_gap: int,
        threshold: float,
) -> tuple[int, float, int, float]:
    h_a, w_a, _ = a.shape
    h_b, w_b, _ = b.shape
    if h_a != h_b:
        raise RuntimeError(f'height mismatch: {h_a} vs {h_b}')
    upper = min(kmax, w_a, w_b)
    if kmin > upper:
        raise RuntimeError(f'kmin={kmin} exceeds searchable overlap upper bound={upper}')

    scores: list[tuple[float, int]] = []
    a32 = a.astype(np.int32)
    b32 = b.astype(np.int32)
    for k in range(kmin, upper + 1):
        score = float(np.abs(a32[:, w_a - k:] - b32[:, :k]).mean())
        scores.append((score, k))

    best_score, best_k = min(scores)
    candidate_limit = min(best_score + score_margin, threshold)
    larger_score, larger_k = max(
        ((score, k) for score, k in scores if score <= candidate_limit),
        key=lambda item: item[1],
    )
    if larger_k - best_k >= larger_min_gap:
        candidate_score, candidate_k = larger_score, larger_k
    else:
        candidate_score, candidate_k = best_score, best_k
    return candidate_k, candidate_score, best_k, best_score


def wrap_image(out: np.ndarray, wrap_width: int) -> np.ndarray:
    if wrap_width <= 0:
        raise RuntimeError(f'wrap width must be positive: {wrap_width}')

    height, width, channels = out.shape
    if wrap_width >= width:
        return out

    rows = (width + wrap_width - 1) // wrap_width
    wrapped = np.full((rows * height, wrap_width, channels), 255, dtype=out.dtype)
    for row in range(rows):
        src_x0 = row * wrap_width
        src_x1 = min(src_x0 + wrap_width, width)
        dst_y0 = row * height
        wrapped[dst_y0:dst_y0 + height, :src_x1 - src_x0] = out[:, src_x0:src_x1]
    return wrapped


def stitch(args: argparse.Namespace) -> int:
    paths = sorted(p for p in args.input_dir.glob(args.pattern) if p.is_file())
    if len(paths) < 2:
        raise SystemExit(f'need at least 2 input images, found {len(paths)}: {args.input_dir / args.pattern}')

    imgs = [np.array(Image.open(p).convert('RGB')) for p in paths]
    h, w, _ = imgs[0].shape
    for p, im in zip(paths, imgs):
        if im.shape[0] != h or im.shape[2] != 3:
            raise RuntimeError(f'unexpected shape for {p}: {im.shape}, expected height={h} channels=3')

    kmax = args.kmax if args.kmax is not None else default_kmax(w)
    logger.info('overlap search range: kmin=%d kmax=%d score_margin=%.3f larger_min_gap=%d',
                args.kmin, kmax, args.score_margin, args.larger_min_gap)

    overlaps: list[int] = [0]
    for i in range(len(imgs) - 1):
        k, score, best_k, best_score = find_overlap(
            imgs[i], imgs[i + 1], args.kmin, kmax, args.score_margin, args.larger_min_gap, args.threshold)
        if best_score >= args.threshold:
            logger.warning('%s <-> %s: best k=%d MAE=%.3f >= threshold %.3f, treating as no overlap',
                           paths[i].name, paths[i + 1].name, best_k, best_score, args.threshold)
            overlaps.append(0)
        else:
            if k == best_k:
                logger.info('%s <-> %s: overlap=%d MAE=%.3f',
                            paths[i].name, paths[i + 1].name, k, score)
            else:
                logger.info('%s <-> %s: overlap=%d MAE=%.3f (best k=%d MAE=%.3f)',
                            paths[i].name, paths[i + 1].name, k, score, best_k, best_score)
            overlaps.append(k)

    parts = [imgs[i][:, overlaps[i]:] for i in range(len(imgs))]
    out = np.concatenate(parts, axis=1)
    logger.info('total inputs=%d sum_overlap=%d output_size=%dx%d',
                len(imgs), sum(overlaps), out.shape[1], out.shape[0])
    if args.wrap_width is not None:
        original_width, original_height = out.shape[1], out.shape[0]
        out = wrap_image(out, args.wrap_width)
        logger.info('wrapped output: %dx%d -> %dx%d',
                    original_width, original_height, out.shape[1], out.shape[0])

    if args.dry_run:
        print(f'save {args.output_file} size={out.shape[1]}x{out.shape[0]} lossless={args.lossless}')
        return 0

    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    out_path = args.output_file
    webp_limit = 16383
    if out_path.suffix.lower() == '.webp' and (out.shape[1] > webp_limit or out.shape[0] > webp_limit):
        png_path = out_path.with_suffix('.png')
        logger.warning('output %dx%d exceeds WebP limit %d; saving as PNG: %s',
                       out.shape[1], out.shape[0], webp_limit, png_path)
        out_path = png_path

    save_kwargs: dict[str, t.Any] = {}
    if out_path.suffix.lower() == '.webp':
        save_kwargs = {'lossless': args.lossless, 'quality': 100}
    Image.fromarray(out).save(out_path, **save_kwargs)
    logger.info('wrote %s', out_path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('stitch', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=stitch)
    subparser.add_argument('input_dir', type=pathlib.Path)
    subparser.add_argument('output_file', type=pathlib.Path)
    subparser.add_argument('--pattern', default='*.webp')
    subparser.add_argument('--kmin', type=int, default=5)
    subparser.add_argument('--kmax', type=int, default=None,
                           help='maximum overlap width to consider; defaults to min(width - 1, max(400, width * 0.75))')
    subparser.add_argument('--score-margin', type=float, default=2.6,
                           help='prefer the largest overlap whose MAE is within this margin of the best MAE')
    subparser.add_argument('--larger-min-gap', type=int, default=100,
                           help='only prefer a larger near-tie overlap when it is at least this many pixels larger')
    subparser.add_argument('--threshold', type=float, default=12.0)
    subparser.add_argument('--wrap-width', type=int,
                           help='wrap the stitched image into rows of this width before saving')
    subparser.add_argument('--lossless', type=lambda v: v.lower() in ('1', 'true', 'yes'), default=True)
    subparser.add_argument('-n', '--dry_run', action='store_true')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return t.cast(t.Callable[[argparse.Namespace], int], args.func)(args)


if __name__ == '__main__':
    raise SystemExit(main())
