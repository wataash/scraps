#!/home/wsh/opt_/pyvenv2/bin/python
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

epilog = r'''
ff_sub.py -h
ff_sub.py burn_subtitles -h
'''[1:]

import argparse
import ast
import csv
import dataclasses
import logging
import pathlib
import shlex
import subprocess
import tempfile
import typing as t


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


@dataclasses.dataclass(frozen=True)
class Subtitle:
    text: str
    start_frame: int
    end_frame: int
    y_expr: str


@dataclasses.dataclass(frozen=True)
class VideoGeometry:
    width: int
    height: int


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('burn_subtitles', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=burn_subtitles)
    subparser.add_argument('input', type=pathlib.Path, help='input video path')
    subparser.add_argument('output', type=pathlib.Path, help='output video path')
    subparser.add_argument(
        '--fontfile',
        type=pathlib.Path,
        default=pathlib.Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
        help='font file used by ffmpeg drawtext',
    )
    subparser.add_argument(
        '--height',
        type=int,
        help='scale video to this height while preserving the aspect ratio',
    )
    subparser.add_argument(
        '--subtitle',
        action='append',
        type=parse_subtitle,
        required=True,
        metavar='START_FRAME,END_FRAME,Y_EXPR,TEXT',
        help='subtitle CSV row; repeat this option for multiple subtitles; legacy TEXT,START_FRAME,END_FRAME,Y_EXPR is also accepted',
    )
    subparser.add_argument(
        '--text_size',
        default='h*0.060',
        help='ffmpeg drawtext fontsize value or expression',
    )
    subparser.add_argument(
        '--renderer',
        choices=('auto', 'drawtext', 'pango'),
        default='auto',
        help='subtitle renderer; pango supports emoji font fallback',
    )
    subparser.add_argument('--ffprobe', default='ffprobe', help='ffprobe executable')
    subparser.add_argument('--pango-view', default='pango-view', help='pango-view executable')
    subparser.add_argument('--ffmpeg', default='ffmpeg', help='ffmpeg executable')
    subparser.add_argument('-n', '--dry-run', action='store_true', help='print the ffmpeg command without running it')

    args = parser.parse_args()
    logger.debug(f'{args=}')
    return args.func(args)


def burn_subtitles(args: argparse.Namespace) -> int:
    subtitles = tuple(args.subtitle)
    use_pango = args.renderer == 'pango' or (
        args.renderer == 'auto' and any(contains_emoji(subtitle.text) for subtitle in subtitles)
    )
    if use_pango:
        if args.dry_run:
            print('# pango renderer selected; run without -n to generate temporary subtitle PNG overlays')
            return 0
        with tempfile.TemporaryDirectory(prefix='ff_sub_') as tmpdir:
            command = build_pango_ffmpeg_command(
                ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe,
                pango_view=args.pango_view,
                infile=args.input,
                outfile=args.output,
                height=args.height,
                subtitles=subtitles,
                text_size=args.text_size,
                tmpdir=pathlib.Path(tmpdir),
            )
            command_text = shlex.join(command)
            logger.info(command_text)
            subprocess.run(command, check=True)
    else:
        command = build_ffmpeg_command(
            ffmpeg=args.ffmpeg,
            infile=args.input,
            outfile=args.output,
            fontfile=args.fontfile,
            height=args.height,
            subtitles=subtitles,
            text_size=args.text_size,
        )
        command_text = shlex.join(command)
        if args.dry_run:
            print(command_text)
            return 0

        logger.info(command_text)
        subprocess.run(command, check=True)
    return 0


def build_ffmpeg_command(
    *,
    ffmpeg: str,
    infile: pathlib.Path,
    outfile: pathlib.Path,
    fontfile: pathlib.Path,
    height: int | None,
    subtitles: tuple[Subtitle, ...],
    text_size: str,
) -> list[str]:
    vf = build_video_filter(fontfile=fontfile, subtitles=subtitles, height=height, text_size=text_size)
    return [
        ffmpeg,
        '-hide_banner',
        '-y',
        '-i',
        str(infile),
        '-vf',
        vf,
        '-c:v',
        'libx264',
        '-preset',
        'medium',
        '-crf',
        '18',
        '-c:a',
        'copy',
        str(outfile),
    ]


def build_pango_ffmpeg_command(
    *,
    ffmpeg: str,
    ffprobe: str,
    pango_view: str,
    infile: pathlib.Path,
    outfile: pathlib.Path,
    height: int | None,
    subtitles: tuple[Subtitle, ...],
    text_size: str,
    tmpdir: pathlib.Path,
) -> list[str]:
    geometry = probe_video_geometry(ffprobe=ffprobe, infile=infile, height=height)
    font_size = round(eval_numeric_expr(text_size, h=geometry.height))
    overlay_paths = [
        render_pango_overlay(
            pango_view=pango_view,
            subtitle=subtitle,
            geometry=geometry,
            font_size=font_size,
            tmpdir=tmpdir,
            index=index,
        )
        for index, subtitle in enumerate(subtitles)
    ]
    filter_complex = build_pango_filter_complex(subtitles=subtitles, height=height)
    command = [
        ffmpeg,
        '-hide_banner',
        '-y',
        '-i',
        str(infile),
    ]
    for overlay_path in overlay_paths:
        command.extend(['-i', str(overlay_path)])
    command.extend(
        [
            '-filter_complex',
            filter_complex,
            '-map',
            '[outv]',
            '-map',
            '0:a?',
            '-c:v',
            'libx264',
            '-preset',
            'medium',
            '-crf',
            '18',
            '-c:a',
            'copy',
            str(outfile),
        ]
    )
    return command


def probe_video_geometry(*, ffprobe: str, infile: pathlib.Path, height: int | None) -> VideoGeometry:
    command = [
        ffprobe,
        '-hide_banner',
        '-v',
        'error',
        '-select_streams',
        'v:0',
        '-show_entries',
        'stream=width,height',
        '-of',
        'csv=p=0:s=x',
        str(infile),
    ]
    logger.info(shlex.join(command))
    result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE)
    width_text, height_text = result.stdout.strip().split('x')
    width = int(width_text)
    source_height = int(height_text)
    if height is None:
        return VideoGeometry(width=width, height=source_height)

    scaled_width = round(width * height / source_height)
    if scaled_width % 2:
        scaled_width += 1
    return VideoGeometry(width=scaled_width, height=height)


def render_pango_overlay(
    *,
    pango_view: str,
    subtitle: Subtitle,
    geometry: VideoGeometry,
    font_size: int,
    tmpdir: pathlib.Path,
    index: int,
) -> pathlib.Path:
    text_path = tmpdir / f'subtitle_text_{index}.png'
    overlay_path = tmpdir / f'subtitle_overlay_{index}.png'
    command = [
        pango_view,
        '--no-display',
        '--background=transparent',
        '--foreground=white',
        '--antialias=gray',
        f'--font=Noto Sans CJK JP {font_size}',
        f'--text={subtitle.text}',
        f'--output={text_path}',
    ]
    logger.info(shlex.join(command))
    subprocess.run(command, check=True)
    compose_overlay_image(
        text_path=text_path,
        overlay_path=overlay_path,
        geometry=geometry,
        y_expr=subtitle.y_expr,
    )
    return overlay_path


def compose_overlay_image(
    *,
    text_path: pathlib.Path,
    overlay_path: pathlib.Path,
    geometry: VideoGeometry,
    y_expr: str,
) -> None:
    from PIL import Image, ImageDraw

    text_image = Image.open(text_path).convert('RGBA')
    bbox = text_image.getbbox()
    if bbox is None:
        raise RuntimeError(f'pango rendered an empty subtitle image: {text_path}')
    text_image = text_image.crop(bbox)
    overlay = Image.new('RGBA', (geometry.width, geometry.height), (0, 0, 0, 0))
    x = round((geometry.width - text_image.width) / 2)
    y = round(eval_numeric_expr(y_expr, h=geometry.height, text_h=text_image.height))
    padding_x = max(2, round(text_image.height * 0.18))
    padding_y = max(1, round(text_image.height * 0.08))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(
        (
            x - padding_x,
            y - padding_y,
            x + text_image.width + padding_x,
            y + text_image.height + padding_y,
        ),
        fill=(0, 0, 0, round(255 * 0.45)),
    )
    overlay.alpha_composite(text_image, dest=(x, y))
    overlay.save(overlay_path)


def build_pango_filter_complex(*, subtitles: tuple[Subtitle, ...], height: int | None) -> str:
    filters = []
    input_label = '[0:v]'
    if height is not None:
        filters.append(f'{input_label}scale=-2:{height}[v0]')
    else:
        filters.append(f'{input_label}null[v0]')

    for index, subtitle in enumerate(subtitles):
        filters.append(
            ''.join(
                [
                    f'[v{index}][{index + 1}:v]',
                    f"overlay=0:0:enable='between(n,{subtitle.start_frame},{subtitle.end_frame})'",
                    f'[v{index + 1}]',
                ]
            )
        )
    filters.append(f'[v{len(subtitles)}]format=yuv420p[outv]')
    return ';'.join(filters)


def build_video_filter(
    *,
    fontfile: pathlib.Path,
    subtitles: t.Iterable[Subtitle],
    height: int | None,
    text_size: str,
) -> str:
    filters = []
    if height is not None:
        filters.append(f'scale=-2:{height}')
    drawtext_filters = [
        build_drawtext_filter(fontfile=fontfile, subtitle=subtitle, text_size=text_size)
        for subtitle in subtitles
    ]
    return ','.join([*filters, *drawtext_filters, 'format=yuv420p'])


def parse_subtitle(value: str) -> Subtitle:
    try:
        row = next(csv.reader([value]))
    except csv.Error as e:
        raise argparse.ArgumentTypeError(f'invalid subtitle CSV: {e}') from e

    if len(row) < 4:
        raise argparse.ArgumentTypeError('subtitle must have at least 4 CSV fields: start_frame,end_frame,y_expr,text')

    subtitle = parse_subtitle_new_order(row)
    if subtitle is not None:
        return subtitle

    if len(row) != 4:
        raise argparse.ArgumentTypeError(
            'legacy subtitle format must have 4 CSV fields: text,start_frame,end_frame,y_expr'
        )

    text, start_frame_text, end_frame_text, y_expr = row
    return build_subtitle(
        text=text,
        start_frame_text=start_frame_text,
        end_frame_text=end_frame_text,
        y_expr=y_expr,
    )


def parse_subtitle_new_order(row: list[str]) -> Subtitle | None:
    try:
        int(row[0])
        int(row[1])
    except ValueError:
        return None

    return build_subtitle(
        text=','.join(row[3:]),
        start_frame_text=row[0],
        end_frame_text=row[1],
        y_expr=row[2],
    )


def build_subtitle(*, text: str, start_frame_text: str, end_frame_text: str, y_expr: str) -> Subtitle:
    if text == '':
        raise argparse.ArgumentTypeError('subtitle text must not be empty')
    if y_expr == '':
        raise argparse.ArgumentTypeError('subtitle y_expr must not be empty')

    try:
        start_frame = int(start_frame_text)
        end_frame = int(end_frame_text)
    except ValueError as e:
        raise argparse.ArgumentTypeError('subtitle start_frame and end_frame must be integers') from e

    return Subtitle(text=text, start_frame=start_frame, end_frame=end_frame, y_expr=y_expr)


def build_drawtext_filter(*, fontfile: pathlib.Path, subtitle: Subtitle, text_size: str) -> str:
    return ':'.join(
        [
            f'drawtext=fontfile={fontfile}',
            f'text={subtitle.text}',
            f"enable='between(n,{subtitle.start_frame},{subtitle.end_frame})'",
            f'fontsize={text_size}',
            'fontcolor=white',
            'box=1',
            'boxcolor=black@0.45',
            'x=(w-text_w)/2',
            f'y={subtitle.y_expr}',
        ]
    )


def contains_emoji(value: str) -> bool:
    return any(
        '\U0001f000' <= char <= '\U0001faff'
        or '\U00002600' <= char <= '\U000027bf'
        or char == '\ufe0f'
        for char in value
    )


def eval_numeric_expr(expr: str, **names: float) -> float:
    tree = ast.parse(expr, mode='eval')
    return float(eval_numeric_node(tree.body, names))


def eval_numeric_node(node: ast.AST, names: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in names:
        return float(names[node.id])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -eval_numeric_node(node.operand, names)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return eval_numeric_node(node.operand, names)
    if isinstance(node, ast.BinOp):
        left = eval_numeric_node(node.left, names)
        right = eval_numeric_node(node.right, names)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError(f'unsupported numeric expression: {ast.unparse(node)}')


if __name__ == '__main__':
    raise SystemExit(main())
