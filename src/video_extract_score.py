#!/home/wsh/opt_/pyvenv2/bin/python
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import fractions
import logging
import pathlib
import shlex
import shutil
import subprocess
import tempfile
import typing as t

from lib_ import video_time
from PIL import Image, ImageStat


epilog = r'''
Examples:
  video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y
  video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y --start 00:01 --end 00:10
  video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y --start 00:01 --duration 00:09
  video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y --fps 1 --distance_threshold 18
  video_extract_score.py extract INPUT_VIDEO OUTPUT_DIR --crop WIDTH:HEIGHT:X:Y --start 00:01 --end 00:10 -n
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


class VideoProbe(t.NamedTuple):
    duration: fractions.Fraction | None
    fps: fractions.Fraction | None


def shell_join(cmd: list[str]) -> str:
    return shlex.join(cmd)


def run_cmd(cmd: list[str], *, dry_run: bool) -> None:
    rendered = shell_join(cmd)
    if dry_run:
        print(rendered)
        return
    logger.info(rendered)
    subprocess.run(cmd, check=True)


def dhash(img: Image.Image, size: int) -> int:
    gray = img.convert('L').resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for y in range(size):
        row = pixels[y * (size + 1):(y + 1) * (size + 1)]
        for x in range(size):
            value = (value << 1) | (1 if row[x] > row[x + 1] else 0)
    return value


def hdist(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = value.split(':')
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f'invalid crop, expected WIDTH:HEIGHT:X:Y: {value}')
    try:
        width, height, x, y = [int(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'invalid crop, expected integer WIDTH:HEIGHT:X:Y: {value}') from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError(f'invalid crop size: {value}')
    if x < 0 or y < 0:
        raise argparse.ArgumentTypeError(f'invalid crop offset: {value}')
    return width, height, x, y


def frame_time(frame: pathlib.Path, fps: fractions.Fraction, start: fractions.Fraction | None) -> float:
    index = int(frame.stem.rsplit('_', 1)[1])
    at = fractions.Fraction(index - 1, 1) / fps
    if start is not None:
        at += start
    return float(at)


def crop_image(img: Image.Image, crop: tuple[int, int, int, int]) -> Image.Image:
    width, height, x, y = crop
    return img.crop((x, y, x + width, y + height))


def format_time_arg(value: fractions.Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f'{float(value):.9f}'.rstrip('0').rstrip('.')


def parse_rate(value: str | None) -> fractions.Fraction | None:
    if value in (None, 'N/A', '0/0', '0'):
        return None
    try:
        rate = fractions.Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    if rate <= 0:
        return None
    return rate


def load_video_probe(path: pathlib.Path, *, dry_run: bool) -> VideoProbe | None:
    cmd = [
        'ffprobe',
        '-v',
        'error',
        '-select_streams',
        'v:0',
        '-show_entries',
        'format=duration:stream=avg_frame_rate,r_frame_rate',
        '-of',
        'json',
        str(path),
    ]
    if dry_run:
        print(shell_join(cmd))
        return None
    logger.info(shell_join(cmd))
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SystemExit('ffprobe not found in PATH') from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise SystemExit(stderr or f'ffprobe failed for {path}') from exc
    data = json.loads(res.stdout)
    duration_text = data.get('format', {}).get('duration')
    duration = None
    if duration_text not in (None, 'N/A'):
        duration = fractions.Fraction(duration_text)

    stream = (data.get('streams') or [{}])[0]
    fps = parse_rate(stream.get('avg_frame_rate')) or parse_rate(stream.get('r_frame_rate'))
    return VideoProbe(duration=duration, fps=fps)


def resolve_extract_times(args: argparse.Namespace, fps: fractions.Fraction) -> video_time.CutTimes:
    duration = None
    frame_fps = fps
    needs_video_probe = any(
        (
            video_time.is_last_ref(args.start),
            video_time.is_last_ref(args.end),
            video_time.is_frame_ref(args.start),
            video_time.is_frame_ref(args.end),
            video_time.is_frame_ref(args.duration),
        )
    )
    if video_time.is_last_ref(args.duration):
        raise SystemExit('--duration cannot be last')
    if needs_video_probe:
        probe = load_video_probe(args.input, dry_run=args.dry_run)
        if probe is None:
            if args.dry_run:
                raise SystemExit('last/frame refs need video metadata; rerun without -n to resolve them')
            raise SystemExit('last/frame refs need video metadata')
        duration = probe.duration
        if (video_time.is_last_ref(args.start) or video_time.is_last_ref(args.end)) and duration is None:
            raise SystemExit('last needs video duration')
        if (
            video_time.is_frame_ref(args.start)
            or video_time.is_frame_ref(args.end)
            or video_time.is_frame_ref(args.duration)
        ):
            if probe.fps is None:
                raise SystemExit('frame refs need video fps')
            frame_fps = probe.fps
    return video_time.resolve_cut_times(
        start=video_time.resolve_seconds(args.start, frame_fps, duration),
        end=video_time.resolve_seconds(args.end, frame_fps, duration),
        duration=video_time.resolve_seconds(args.duration, frame_fps, duration),
        require_any=False,
        start_name='--start',
        end_name='--end',
        duration_name='--duration',
    )


def extract_frames(args: argparse.Namespace, tmp_dir: pathlib.Path, times: video_time.CutTimes) -> None:
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-v',
        'error',
        '-y',
    ]
    if times.start is not None:
        cmd.extend(['-ss', format_time_arg(times.start)])
    cmd.extend([
        '-i',
        str(args.input),
    ])
    if times.duration is not None:
        cmd.extend(['-t', format_time_arg(times.duration)])
    cmd.extend([
        '-vf',
        f'fps={args.fps}',
        str(tmp_dir / 'frame_%04d.png'),
    ])
    run_cmd(cmd, dry_run=args.dry_run)


def output_start_index(args: argparse.Namespace) -> int:
    if args.clean:
        return 1
    max_index = 0
    for path in args.output.glob('*.webp'):
        if path.stem.isdigit():
            max_index = max(max_index, int(path.stem))
    return max_index + 1


def save_unique_scores(args: argparse.Namespace, tmp_dir: pathlib.Path, crop: tuple[int, int, int, int], fps: fractions.Fraction, start: fractions.Fraction | None) -> int:
    args.output.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for path in args.output.glob('*.webp'):
            path.unlink()

    saved = output_start_index(args) - 1
    initial_saved = saved
    last_hash = None
    for frame in sorted(tmp_dir.glob('frame_*.png')):
        at = frame_time(frame, fps, start)
        with Image.open(frame) as img:
            score_img = crop_image(img, crop)
            gray_mean = ImageStat.Stat(score_img.convert('L')).mean[0]
            if gray_mean < args.min_mean:
                continue
            current_hash = dhash(score_img, args.hash_size)
            if last_hash is not None and hdist(current_hash, last_hash) <= args.distance_threshold:
                continue
            saved += 1
            dst = args.output / f'{saved:0{args.digits}d}.webp'
            score_img.save(dst, 'WEBP', quality=args.quality, method=args.method)
            last_hash = current_hash
            logger.info('saved %s from %s at=%.3f crop=%s mean=%.1f', dst, frame.name, at, crop, gray_mean)
    return saved - initial_saved


def cmd_extract(args: argparse.Namespace) -> int:
    if not shutil.which('ffmpeg'):
        logger.error('ffmpeg was not found in PATH')
        return 1
    args.input = args.input.expanduser()
    args.output = args.output.expanduser()
    if not args.input.exists():
        logger.error('input does not exist: %s', args.input)
        return 1
    try:
        crop = parse_crop(args.crop)
        times = resolve_extract_times(args, args.fps)
    except argparse.ArgumentTypeError as exc:
        logger.error('%s', exc)
        return 1

    if args.dry_run:
        tmp_dir = pathlib.Path('${TMPDIR:-/tmp}') / 'video_extract_score_frames'
        extract_frames(args, tmp_dir, times)
        print(f'# would remove existing {args.output}/*.webp: {args.clean}')
        print(f'# start: {format_time_arg(times.start) if times.start is not None else None}')
        print(f'# duration: {format_time_arg(times.duration) if times.duration is not None else None}')
        print(f'# crop: {args.crop}')
        print(f'# first output index: {output_start_index(args)}')
        print(f'# would write unique score strips to {args.output}')
        return 0

    with tempfile.TemporaryDirectory(prefix='video_extract_score_') as tmp:
        tmp_dir = pathlib.Path(tmp)
        extract_frames(args, tmp_dir, times)
        count = save_unique_scores(args, tmp_dir, crop, args.fps, times.start)
    logger.info('saved %d files in %s', count, args.output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('extract', formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=cmd_extract)
    subparser.add_argument('input', type=pathlib.Path, help='input video file readable by ffmpeg')
    subparser.add_argument('output', metavar='OUTPUT_DIR', type=pathlib.Path, help='output directory for numbered .webp files')
    subparser.add_argument('--crop', required=True, help='initial crop expression: width:height:x:y')
    subparser.add_argument('--start', type=video_time.parse_time_or_frame, help='extract start time; see lib_/video_time.md')
    subparser.add_argument('--end', type=video_time.parse_time_or_frame, help='extract end time; see lib_/video_time.md')
    subparser.add_argument('--duration', type=video_time.parse_time_or_frame, help='extract duration; see lib_/video_time.md')
    subparser.add_argument('--fps', type=video_time.parse_fps, default=fractions.Fraction(1), help='sampling rate passed to ffmpeg fps filter; not used for frame refs')
    subparser.add_argument('--min_mean', type=float, default=90.0, help='skip dark/blank crops below this grayscale mean')
    subparser.add_argument('--hash_size', type=int, default=16, help='dHash side length')
    subparser.add_argument('--distance_threshold', type=int, default=18, help='maximum dHash distance treated as duplicate')
    subparser.add_argument('--quality', type=int, default=95, help='WebP quality')
    subparser.add_argument('--method', type=int, default=6, help='WebP encoder method')
    subparser.add_argument('--digits', type=int, default=3, help='zero-padding width for output filenames')
    subparser.add_argument('--clean', action=argparse.BooleanOptionalAction, default=True, help='remove existing output .webp files first')
    subparser.add_argument('-n', '--dry_run', action='store_true', help='print commands and planned actions without executing')

    args = parser.parse_args()
    logger.debug('args=%r', args)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
