#!/usr/bin/env python
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import logging
import pathlib
import typing as t


epilog = r'''
ff_vmaf_plot.py plot encoded/*.json --output vmaf.png
ff_vmaf_plot.py plot encoded/crf18.mp4.vmaf.json encoded/crf23.mp4.vmaf.json -o vmaf.png
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


class ArgumentDefaultsRawTextHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawTextHelpFormatter,
):
    pass


class VmafSeries(t.NamedTuple):
    path: pathlib.Path
    frames: list[int]
    values: list[float]


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        epilog=epilog,
    )
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser(
        'plot',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='Plot per-frame VMAF values from JSON files',
    )
    subparser.set_defaults(func=cmd_plot)
    subparser.add_argument('files', nargs='+', type=pathlib.Path)
    subparser.add_argument(
        '-o',
        '--output',
        type=pathlib.Path,
        help='write plot image to this path instead of opening an interactive window',
    )
    subparser.add_argument(
        '--title',
        default='VMAF by frame',
        help='plot title',
    )
    subparser.add_argument(
        '--dpi',
        type=int,
        default=150,
        help='output image DPI',
    )
    args = parser.parse_args()
    return args.func(args)


def cmd_plot(args: argparse.Namespace) -> int:
    if args.dpi <= 0:
        logger.error('--dpi must be positive')
        return 2

    series_list = [load_vmaf_series(path) for path in args.files]
    plot_vmaf_series(
        series_list,
        output=args.output,
        title=args.title,
        dpi=args.dpi,
    )
    return 0


def load_vmaf_series(path: pathlib.Path) -> VmafSeries:
    with path.open(encoding='utf-8') as f:
        data = json.load(f)

    frames_json = data.get('frames')
    if not isinstance(frames_json, list):
        raise SystemExit(f'{path}: expected top-level "frames" list')

    frames: list[int] = []
    values: list[float] = []
    for fallback_frame, frame in enumerate(frames_json):
        if not isinstance(frame, dict):
            continue

        metrics = frame.get('metrics')
        if not isinstance(metrics, dict) or 'vmaf' not in metrics:
            continue

        frame_num = frame.get('frameNum', fallback_frame)
        try:
            frames.append(int(frame_num))
            values.append(float(metrics['vmaf']))
        except (TypeError, ValueError) as exc:
            raise SystemExit(f'{path}: invalid VMAF frame entry: {frame!r}') from exc

    if not values:
        raise SystemExit(f'{path}: no frames[].metrics.vmaf values found')

    return VmafSeries(path=path, frames=frames, values=values)


def plot_vmaf_series(
    series_list: list[VmafSeries],
    *,
    output: pathlib.Path | None,
    title: str,
    dpi: int,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit('matplotlib is required for plotting') from exc

    fig, ax = plt.subplots(figsize=(12, 6))
    for series in series_list:
        ax.plot(series.frames, series.values, label=series.path.name, linewidth=1.2)

    ax.set_xlabel('Frame')
    ax.set_ylabel('VMAF')
    ax.set_title(title)
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    if len(series_list) > 1:
        ax.legend()
    fig.tight_layout()

    if output is None:
        plt.show()
        return

    fig.savefig(output, dpi=dpi)
    logger.info('wrote %s', output)


if __name__ == '__main__':
    raise SystemExit(main())
