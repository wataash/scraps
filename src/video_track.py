#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
import typing as t
from pathlib import Path

from lib_ import video_time

# これが無いと /home/wsh/d/s/video_track_draw_box.py : import video_track で再びここに到達してしまう
# see in debugger:
# [sys.modules.get('__main__'), sys.modules.get('video_track'), sys.modules.get('video_track_draw_box')]
sys.modules.setdefault("video_track", sys.modules[__name__])

epilog = r"""
video_track.py -h
video_track.py list_class_names -h
video_track.py list_class_names --model yolo26n.pt  # These class names can be used with --class-name
video_track.py plan_detect b.mp4 b.detect.jsonl --interval 60 --stride 10
video_track.py detect -h
video_track.py finalize -h
video_track.py draw_box -h
video_track.py stabilize -h
video_track.py detect short.mp4 short.detect.jsonl --init-bbox 120:260:360:70 --preview_gui
video_track.py detect short.mp4 short.detect.jsonl --start f:10 --end 0:01.700 --init-bbox 120:260:360:70 --preview_gui
video_track.py detect short.mp4 short.detect.jsonl --start f:20 --duration f:-10 --init-bbox 120:260:360:70 --preview_gui
video_track.py finalize short.mp4 short.detect.jsonl short.detect.json
video_track.py draw_box short.mp4 short.detect.json --preview_gui
video_track.py stabilize short.mp4 short.detect.json --preview_gui
ff.py -h  # for other --start/--end/--duration formats
"""[1:]


class MyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = {
            logging.CRITICAL: "\x1b[31m",
            logging.ERROR: "\x1b[31m",
            logging.WARNING: "\x1b[33m",
            logging.INFO: "\x1b[34m",
            logging.DEBUG: "\x1b[37m",
        }[record.levelno]
        fn = "" if record.funcName == "<module>" else f" {record.funcName}()"
        fmt = f"{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s\x1b[m"
        return logging.Formatter(fmt=fmt, datefmt="%T").format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


class VideoInfo(t.NamedTuple):
    fps: float
    frame_count: int
    width: int
    height: int


class PreviewStyle(t.NamedTuple):
    text_scale: float
    label_scale: float
    text_thickness: int
    label_thickness: int
    box_thickness: int
    target_box_thickness: int
    margin: int
    line_y: int


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def shell_join_copyable(cmd: list[str]) -> str:
    def quote(part: str) -> str:
        if re.fullmatch(r"~?/[A-Za-z0-9_./:+@=%,-]+", part):
            return part
        if re.fullmatch(r"[A-Za-z0-9_./:+@=%,-]+", part):
            return part
        return shlex.quote(part)

    return " ".join(quote(part) for part in cmd)


def tqdm_progress(*args: object, **kwargs: object) -> object:
    from tqdm import tqdm

    kwargs.setdefault("dynamic_ncols", False)
    kwargs.setdefault("ncols", 96)
    kwargs.setdefault("bar_format", "{l_bar}{bar:24}{r_bar}")
    kwargs.setdefault("mininterval", 0.5)
    return tqdm(*args, **kwargs)


def load_video_modules() -> None:
    global cv2, np

    import cv2 as cv2_module
    import numpy as np_module

    cv2 = cv2_module
    np = np_module


def is_valid_frame_count(frame_count: int) -> bool:
    return 0 < frame_count < 1_000_000_000


def ffprobe_frame_count(src: Path) -> int | None:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-count_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=nb_read_frames,nb_frames",
        "-of",
        "json",
        str(src),
    ]
    try:
        result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    except FileNotFoundError:
        logger.warning("ffprobe not found; cannot recover invalid frame count")
        return None
    if result.returncode != 0:
        logger.warning("ffprobe frame count failed: %s", result.stderr.strip())
        return None
    try:
        data = json.loads(result.stdout)
        stream = data["streams"][0]
    except (KeyError, IndexError, json.JSONDecodeError):
        logger.warning("ffprobe frame count returned no video stream")
        return None
    for key in ("nb_read_frames", "nb_frames"):
        value = stream.get(key)
        if value is None or value == "N/A":
            continue
        try:
            frame_count = int(value)
        except ValueError:
            continue
        if is_valid_frame_count(frame_count):
            return frame_count
    return None


def load_video_info(src: Path) -> VideoInfo:
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {src}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if not is_valid_frame_count(frame_count):
        logger.info("OpenCV returned invalid frame count %s for %s; probing with ffprobe", frame_count, src)
        probed_frame_count = ffprobe_frame_count(src)
        if probed_frame_count is None:
            raise RuntimeError(f"Could not determine frame count for {src}")
        frame_count = probed_frame_count
        logger.info("ffprobe frame count: %s", frame_count)

    return VideoInfo(fps=fps, frame_count=frame_count, width=width, height=height)


def smooth(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return values
    kernel = np.hanning(radius * 2 + 1)
    kernel /= kernel.sum()
    padded = np.pad(values, ((radius, radius), (0, 0)), mode="edge")
    out = np.empty_like(values, dtype=np.float64)
    for col in range(values.shape[1]):
        out[:, col] = np.convolve(padded[:, col], kernel, mode="valid")
    return out


def parse_crop(value: str) -> tuple[float, float, float, float]:
    try:
        parts = [float(part) for part in value.split(":")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("crop must be W:H:X:Y") from exc
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be W:H:X:Y")
    w, h, x, y = parts
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("crop width and height must be positive")
    return w, h, x, y


def crop_to_xywh(crop: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    w, h, x, y = crop
    return x, y, w, h


def parse_detect_duration(value: str) -> video_time.TimeOrFrame:
    if value.startswith("frame:-"):
        frame_text = value.split(":", 1)[1]
        try:
            frame = int(frame_text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid frame duration: {value!r}") from exc
        return video_time.TimeOrFrame(kind="frame", value=frame)
    if value.startswith("f:-"):
        return parse_detect_duration("frame:" + value.split(":", 1)[1])
    sign = -1 if value.startswith("-") else 1
    unsigned = value[1:] if sign < 0 else value
    if unsigned == "":
        raise argparse.ArgumentTypeError("duration must be a time or frame:N/f:N")
    if sign < 0 and (unsigned.startswith("frame:") or unsigned.startswith("f:") or (unsigned.startswith("f") and unsigned[1:].isdigit())):
        raise argparse.ArgumentTypeError("negative frame duration must be frame:-N")
    parsed = video_time.parse_time_or_frame(unsigned)
    if parsed.kind == "last":
        raise argparse.ArgumentTypeError("duration cannot be last")
    return video_time.TimeOrFrame(kind=parsed.kind, value=parsed.value * sign)


def detect_offset_to_frames(value: video_time.TimeOrFrame, fps: float) -> int:
    if value.kind == "frame":
        return int(value.value)
    if value.kind == "last":
        raise SystemExit("--duration cannot be last")
    return round(float(value.value) * fps)


def resolve_detect_range(
    *,
    start: video_time.TimeOrFrame | None,
    end: video_time.TimeOrFrame | None,
    duration: video_time.TimeOrFrame | None,
    fps: float,
    frame_count: int,
) -> tuple[int, int]:
    return resolve_time_frame_range(
        start=start,
        end=end,
        duration=duration,
        fps=fps,
        frame_count=frame_count,
        command_name="detect",
    )


def resolve_time_frame_range(
    *,
    start: video_time.TimeOrFrame | None,
    end: video_time.TimeOrFrame | None,
    duration: video_time.TimeOrFrame | None,
    fps: float,
    frame_count: int,
    command_name: str,
) -> tuple[int, int]:
    specified = [value is not None for value in (start, end, duration)].count(True)
    if specified < 2:
        raise SystemExit(f"{command_name} range needs two of --start, --end, --duration")
    if specified > 2:
        raise SystemExit("specify at most two of --start, --end, --duration")

    if start is not None and end is not None:
        return (
            video_time.resolve_frame_index(start, fps, frame_count),
            video_time.resolve_frame_index(end, fps, frame_count),
        )
    if start is not None and duration is not None:
        start_frame = video_time.resolve_frame_index(start, fps, frame_count)
        end_frame = start_frame + detect_offset_to_frames(duration, fps)
        return start_frame, min(max(0, end_frame), max(0, frame_count - 1))
    if end is not None and duration is not None:
        end_frame = video_time.resolve_frame_index(end, fps, frame_count)
        start_frame = end_frame - detect_offset_to_frames(duration, fps)
        return min(max(0, start_frame), max(0, frame_count - 1)), end_frame

    raise SystemExit(f"unsupported {command_name} range")


def sample_frame_indices(start_frame: int, end_frame: int, stride: int) -> list[int]:
    if stride <= 0:
        raise ValueError("--stride must be positive")
    step = stride if end_frame >= start_frame else -stride
    frame_indices: list[int] = []
    frame = start_frame
    while (frame <= end_frame if step > 0 else frame >= end_frame):
        frame_indices.append(frame)
        frame += step
    if not frame_indices or frame_indices[-1] != end_frame:
        frame_indices.append(end_frame)
    return frame_indices


def format_frame_time(frame_index: int, fps: float) -> str:
    if fps <= 0:
        return "00:00:00.000"
    total_ms = max(0, int(round(frame_index / fps * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def frame_time_label(frame_index: int, fps: float) -> str:
    return f"{frame_index}({format_frame_time(frame_index, fps)})"


def frame_range_label(start_frame: int, end_frame: int, fps: float) -> str:
    return f"{frame_time_label(start_frame, fps)}-{frame_time_label(end_frame, fps)}"


def format_seconds_arg(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    whole_seconds, milliseconds = divmod(total_ms, 1000)
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    text = f"{hours}:{minutes:02d}:{secs:02d}"
    if milliseconds:
        text += f".{milliseconds:03d}".rstrip("0")
    return text


def interval_center_times(duration_seconds: float, interval_seconds: float) -> list[float]:
    if interval_seconds <= 0:
        raise SystemExit("--interval must be positive")
    times: list[float] = []
    n = 1
    while True:
        center = (n - 0.5) * interval_seconds
        if center >= duration_seconds:
            break
        times.append(center)
        n += 1
    if not times:
        raise RuntimeError(
            f"video is too short for interval centers: duration={duration_seconds:.3f}, interval={interval_seconds:.3f}"
        )
    return times


def format_bbox_placeholder(template: str, *, n: int, start: str, start_seconds: float) -> str:
    try:
        return template.format(n=n, start=start, time=start, seconds=format_seconds_arg(start_seconds))
    except (KeyError, IndexError, ValueError) as exc:
        raise SystemExit(f"invalid --bbox-placeholder format string: {template!r}") from exc


def append_ai_commands_log(commands: list[str]) -> None:
    with Path("/tmp/ai_cmds.bash").open("a", encoding="utf-8") as handle:
        for command in commands:
            handle.write(command)
            handle.write("\n\n")


def detect_preview_status(
    frame_index: int,
    fps: float,
    pct: float,
    frame_count: int,
    start_frame: int,
    end_frame: int,
) -> str:
    return (
        f"frame {frame_time_label(frame_index, fps)} ({pct:.1f}% of {frame_count} frames)\n"
        f"processing {frame_time_label(start_frame, fps)}->{frame_time_label(end_frame, fps)}"
    )


def detect_saved_preview_status(frame_index: int, fps: float) -> str:
    return f"frame {frame_time_label(frame_index, fps)}"


def detect_saved_preview_control_text() -> str | None:
    return None


def default_detect_preview_mp4v_path(src: Path) -> Path:
    return Path(f"{src}.detect.preview.mp4v.mkv")


def default_detect_preview_h264_path(src: Path) -> Path:
    return Path(f"{src}.detect.preview.h264.mkv")


def resize_preview_frame(frame: np.ndarray, max_height: int) -> np.ndarray:
    if max_height <= 0:
        return frame
    height, width = frame.shape[:2]
    if height <= max_height or height <= 0:
        return frame
    scale = max_height / height
    resized_width = max(1, int(round(width * scale)))
    return cv2.resize(frame, (resized_width, max_height), interpolation=cv2.INTER_AREA)


def resize_preview_video_frame(frame: np.ndarray, max_height: int) -> np.ndarray:
    output = resize_preview_frame(frame, max_height)
    height, width = output.shape[:2]
    pad_bottom = height % 2
    pad_right = width % 2
    if pad_bottom or pad_right:
        output = cv2.copyMakeBorder(output, 0, pad_bottom, 0, pad_right, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return output


def detect_preview_video_fps(source_fps: float, frame_indices: list[int] | None) -> float:
    if frame_indices is None or len(frame_indices) < 2:
        return source_fps
    diffs = sorted(abs(b - a) for a, b in zip(frame_indices, frame_indices[1:]) if b != a)
    if not diffs:
        return source_fps
    median_step = diffs[len(diffs) // 2]
    return source_fps / max(1, median_step)


def open_detect_preview_video_writers(
    dst: Path,
    h264_dst: Path,
    fps: float,
    first_frame: np.ndarray,
    max_height: int,
) -> tuple[object, subprocess.Popen[bytes], np.ndarray]:
    output_frame = resize_preview_video_frame(first_frame, max_height)
    height, width = output_frame.shape[:2]
    logger.info("detect preview mp4v video: %s (%.3f fps, %sx%s)", dst, fps, width, height)
    writer = cv2.VideoWriter(
        str(dst),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not write detect preview video: {dst}")
    logger.info("detect preview h264 video: %s (%.3f fps, %sx%s)", h264_dst, fps, width, height)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.6f}",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(h264_dst),
    ]
    logger.info(shell_join(cmd))
    h264_process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    return writer, h264_process, output_frame


def close_detect_preview_video_writers(writer: object | None, h264_process: subprocess.Popen[bytes] | None) -> None:
    if writer is not None:
        writer.release()
    if h264_process is not None:
        if h264_process.stdin is not None:
            h264_process.stdin.close()
        return_code = h264_process.wait()
        if return_code != 0:
            raise RuntimeError(f"ffmpeg h264 preview writer failed with exit code {return_code}")


def xywh_to_xyxy(bbox: tuple[float, float, float, float]) -> np.ndarray:
    x, y, w, h = bbox
    return np.array([x, y, x + w, y + h], dtype=np.float64)


def ensure_preview_available() -> None:
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return
    raise RuntimeError("--preview_gui needs a GUI display; DISPLAY/WAYLAND_DISPLAY is not set")


def preview_window_size(frame_width: int, frame_height: int) -> tuple[int, int]:
    if frame_width <= 0 or frame_height <= 0:
        return 1280, 720
    scale = min(1280 / frame_width, 960 / frame_height)
    return max(1, round(frame_width * scale)), max(1, round(frame_height * scale))


def open_preview_window(window_name: str, frame_width: int, frame_height: int) -> None:
    ensure_preview_available()
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    window_width, window_height = preview_window_size(frame_width, frame_height)
    cv2.resizeWindow(window_name, window_width, window_height)


def preview_style(frame: np.ndarray) -> PreviewStyle:
    height, width = frame.shape[:2]
    scale = max(1.0, min(width, height) / 720.0)
    return PreviewStyle(
        text_scale=0.6 * scale,
        label_scale=0.5 * scale,
        text_thickness=max(2, int(round(2 * scale))),
        label_thickness=max(1, int(round(1 * scale))),
        box_thickness=max(2, int(round(2 * scale))),
        target_box_thickness=max(3, int(round(3 * scale))),
        margin=max(6, int(round(10 * scale))),
        line_y=max(24, int(round(24 * scale))),
    )


def draw_preview_text(
    frame: np.ndarray,
    text: str,
    x: int,
    y: int,
    scale: float,
    thickness: int,
    color: tuple[int, int, int],
) -> None:
    height, width = frame.shape[:2]
    available_width = max(1, width - x * 2)
    line_height = max(1, int(round(28 * scale)))
    for line_index, line in enumerate(text.splitlines() or [""]):
        line_scale = scale
        text_width = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, line_scale, thickness)[0][0]
        if text_width > available_width:
            line_scale *= available_width / text_width
        line_y = min(height - 1, y + line_index * line_height)
        cv2.putText(
            frame,
            line,
            (x, line_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            line_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )


def draw_preview_frame(
    frame: np.ndarray,
    detections: list[tuple[int, np.ndarray]],
    init_bbox: tuple[float, float, float, float],
    frame_index: int,
    status_text: str | None = None,
    target_track_id: int | None = None,
    control_text: str | None = "q/esc: kill",
) -> np.ndarray:
    preview = frame.copy()
    style = preview_style(preview)
    for track_id, bbox in detections:
        x0, y0, x1, y1 = bbox
        is_target = target_track_id is not None and track_id == target_track_id
        color = (0, 0, 255) if is_target else (0, 255, 0)
        label = f"target id {track_id}" if is_target else f"id {track_id}"
        cv2.rectangle(
            preview,
            (int(round(x0)), int(round(y0))),
            (int(round(x1)), int(round(y1))),
            color,
            style.target_box_thickness if is_target else style.box_thickness,
        )
        cv2.putText(
            preview,
            label,
            (int(round(x0)), max(0, int(round(y0)) - style.margin)),
            cv2.FONT_HERSHEY_SIMPLEX,
            style.label_scale,
            color,
            style.label_thickness,
            cv2.LINE_AA,
        )
    text = status_text or f"frame {frame_index}"
    if control_text:
        text = f"{text}\n{control_text}"
    draw_preview_text(
        preview,
        text,
        style.margin,
        style.line_y,
        style.text_scale,
        style.text_thickness,
        (255, 255, 255),
    )
    return preview


def bbox_iou(a: np.ndarray, b: np.ndarray) -> float:
    ix0 = max(a[0], b[0])
    iy0 = max(a[1], b[1])
    ix1 = min(a[2], b[2])
    iy1 = min(a[3], b[3])
    iw = max(0.0, ix1 - ix0)
    ih = max(0.0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    denom = area_a + area_b - inter
    return 0.0 if denom <= 0 else inter / denom


def select_preview_target_track(
    detections: list[tuple[int, np.ndarray]],
    init_xyxy: np.ndarray,
) -> int | None:
    best_track_id: int | None = None
    best_iou = 0.0
    for track_id, bbox in detections:
        iou = bbox_iou(init_xyxy, bbox)
        if iou > best_iou:
            best_iou = iou
            best_track_id = track_id
    return best_track_id


def keep_preview_target_track(
    current_track_id: int | None,
    detections: list[tuple[int, np.ndarray]],
    init_xyxy: np.ndarray,
) -> int | None:
    if current_track_id is not None:
        return current_track_id
    return select_preview_target_track(detections, init_xyxy)


def resolve_class_id(detector: YOLO, class_name: str | None, class_id: int | None) -> int | None:
    if class_id is not None:
        return class_id
    if not class_name:
        return None
    names = detector.names
    for candidate_id, candidate_name in names.items():
        if candidate_name == class_name:
            return int(candidate_id)
    known = ", ".join(str(name) for name in names.values())
    raise ValueError(f"Unknown class name {class_name!r}. Known classes: {known}")


def interpolate_bboxes(bboxes: np.ndarray) -> tuple[np.ndarray, int]:
    valid = ~np.isnan(bboxes[:, 0])
    valid_count = int(valid.sum())
    if valid_count == 0:
        raise RuntimeError("Target was never detected")

    frames = np.arange(len(bboxes))
    out = bboxes.copy()
    for col in range(4):
        out[:, col] = np.interp(frames, frames[valid], bboxes[valid, col])
    return out, len(bboxes) - valid_count


def interpolate_bboxes_at_frames(
    sample_frames: list[int],
    sample_bboxes: np.ndarray,
    output_frames: np.ndarray,
) -> tuple[np.ndarray, int]:
    valid = ~np.isnan(sample_bboxes[:, 0])
    valid_count = int(valid.sum())
    if valid_count == 0:
        raise RuntimeError("Target was never detected")

    out = np.empty((len(output_frames), 4), dtype=np.float64)
    valid_frames = np.array(sample_frames, dtype=np.float64)[valid]
    for col in range(4):
        out[:, col] = np.interp(output_frames.astype(np.float64), valid_frames, sample_bboxes[valid, col])
    return out, len(sample_frames) - valid_count


def xyxy_to_xywh(bbox: np.ndarray) -> list[float]:
    return [
        float(bbox[0]),
        float(bbox[1]),
        float(bbox[2] - bbox[0]),
        float(bbox[3] - bbox[1]),
    ]


def live_detection_record(
    index: int,
    frame_detections: list[tuple[int, np.ndarray]],
    segment_id: str,
    revision: int,
    segment_n: int,
) -> dict[str, object]:
    detections = []
    for track_id, bbox in frame_detections:
        detections.append(
            {
                "track_id": int(track_id),
                "xyxy": [float(value) for value in bbox],
                "bbox": xyxy_to_xywh(bbox),
            }
        )
    return {
        "schema": "video_track.live.v1",
        "type": "frame",
        "segment_id": segment_id,
        "revision": revision,
        "n": index,
        "segment_n": segment_n,
        "bbox_order": "x:y:w:h",
        "detections": detections,
    }


def video_size(src: Path) -> tuple[int, int]:
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {src}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return width, height


def xywh_list_to_xyxy_array(frames: list[dict[str, object]]) -> np.ndarray:
    bboxes = np.empty((len(frames), 4), dtype=np.float64)
    for index, item in enumerate(frames):
        x, y, w, h = item["bbox"]
        bboxes[index] = [x, y, x + w, y + h]
    return bboxes


def select_target_track(
    detections_by_frame: list[list[tuple[int, np.ndarray]]],
    init_frame: int,
    init_bbox: tuple[float, float, float, float],
    fps: float,
) -> tuple[int, int, float]:
    init_xyxy = xywh_to_xyxy(init_bbox)
    max_offset = max(1, round(fps * 2))
    best: tuple[float, int, int] | None = None

    for offset in range(max_offset + 1):
        candidate_frames = [init_frame] if offset == 0 else [init_frame - offset, init_frame + offset]
        for frame_index in candidate_frames:
            if frame_index < 0 or frame_index >= len(detections_by_frame):
                continue
            for track_id, bbox in detections_by_frame[frame_index]:
                iou = bbox_iou(init_xyxy, bbox)
                score = iou - offset * 0.001
                if best is None or score > best[0]:
                    best = (score, track_id, frame_index)

    if best is None or best[0] <= 0:
        raise RuntimeError("No YOLO track overlapped --init-bbox near --init-time")
    score, track_id, frame_index = best
    return track_id, frame_index, max(0.0, score)


def select_target_bboxes_by_iou(
    detections_by_frame: list[list[tuple[int, np.ndarray]]],
    init_frame: int,
    init_bbox: tuple[float, float, float, float],
    fps: float,
) -> tuple[np.ndarray, int, int, float]:
    min_switch_iou = 0.20
    target_id, selected_frame, selected_iou = select_target_track(detections_by_frame, init_frame, init_bbox, fps)
    selected_bbox: np.ndarray | None = None
    for track_id, bbox in detections_by_frame[selected_frame]:
        if track_id == target_id:
            selected_bbox = bbox
            break
    if selected_bbox is None:
        raise RuntimeError("Selected YOLO track disappeared on selected frame")

    raw_bboxes = np.full((len(detections_by_frame), 4), np.nan, dtype=np.float64)
    raw_bboxes[selected_frame] = selected_bbox

    def fill(step: int) -> None:
        previous_bbox = selected_bbox
        frame_index = selected_frame + step
        while 0 <= frame_index < len(detections_by_frame):
            same_track_bbox: np.ndarray | None = None
            best_bbox: np.ndarray | None = None
            best_iou = 0.0
            for track_id, bbox in detections_by_frame[frame_index]:
                if track_id == target_id:
                    same_track_bbox = bbox
                    break
                iou = bbox_iou(previous_bbox, bbox)
                if best_bbox is None or iou > best_iou:
                    best_bbox = bbox
                    best_iou = iou
            if same_track_bbox is not None:
                raw_bboxes[frame_index] = same_track_bbox
                previous_bbox = same_track_bbox
            elif best_bbox is not None and best_iou >= min_switch_iou:
                raw_bboxes[frame_index] = best_bbox
                previous_bbox = best_bbox
            frame_index += step

    fill(-1)
    fill(1)
    return raw_bboxes, target_id, selected_frame, selected_iou


def detect_target_bboxes(
    src: Path,
    detector: YOLO,
    class_id: int | None,
    init_bbox: tuple[float, float, float, float],
    init_time: float,
    preview: bool,
    live_json: Path | None,
    live_meta_extra: dict[str, object] | None,
) -> tuple[np.ndarray, dict[str, object]]:
    started_at = time.monotonic()
    info = load_video_info(src)
    fps = info.fps
    frame_count = info.frame_count
    if preview:
        open_preview_window("video_track detect", info.width, info.height)
    init_frame = min(max(0, round(init_time * fps)), max(0, frame_count - 1))
    init_xyxy = xywh_to_xyxy(init_bbox)

    logger.info("detect start: %s frames, %.3f fps, init_frame=%s", frame_count, fps, init_frame)
    detections_by_frame: list[list[tuple[int, np.ndarray]]] = []
    index = 0
    live_file = None
    preview_target_track_id: int | None = None
    try:
        if live_json is not None:
            live_file = live_json.open("w", encoding="utf-8")
            live_meta = {
                "schema": "video_track.live.v1",
                "type": "meta",
                "source": str(src),
                "frame_count": frame_count,
                "fps": fps,
                **(live_meta_extra or {}),
                "init_time": init_time,
                "init_frame": init_frame,
                "init_bbox": list(init_bbox),
                "init_bbox_order": "x:y:w:h",
                "note": "Raw YOLO detections are written as they are processed. The final target track is written to track_json after detection completes.",
            }
            live_file.write(json.dumps(live_meta, separators=(",", ":")) + "\n")
            live_file.flush()
            logger.info("live detect JSONL start: %s", live_json)
        stream = detector.track(
            source=str(src),
            stream=True,
            classes=None if class_id is None else [class_id],
            verbose=False,
        )
        with tqdm_progress(total=frame_count, desc="detect", unit="frame") as progress:
            for result in stream:
                frame_detections: list[tuple[int, np.ndarray]] = []
                boxes = result.boxes
                if boxes is not None and boxes.id is not None:
                    ids = boxes.id.cpu().numpy().astype(int)
                    xyxy = boxes.xyxy.cpu().numpy().astype(np.float64)
                    frame_detections = [(int(track_id), bbox) for track_id, bbox in zip(ids, xyxy)]
                detections_by_frame.append(frame_detections)

                if live_file is not None:
                    live_file.write(
                        json.dumps(live_detection_record(index, frame_detections, "base", 0, index), separators=(",", ":"))
                        + "\n"
                    )
                    live_file.flush()

                if preview:
                    pct = index / max(1, frame_count - 1) * 100
                    status_text = detect_preview_status(
                        index,
                        fps,
                        pct,
                        frame_count,
                        0,
                        max(0, frame_count - 1),
                    )
                    preview_target_track_id = keep_preview_target_track(
                        preview_target_track_id,
                        frame_detections,
                        init_xyxy,
                    )
                    preview_frame = draw_preview_frame(
                        result.orig_img,
                        frame_detections,
                        init_bbox,
                        index,
                        status_text,
                        target_track_id=preview_target_track_id,
                    )
                    cv2.imshow("video_track detect", preview_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        raise KeyboardInterrupt("preview interrupted")

                index += 1
                progress.update(1)
    finally:
        if live_file is not None:
            live_file.close()
            logger.info("live detect JSONL written: %s", live_json)
        if preview:
            cv2.destroyWindow("video_track detect")

    if index == 0:
        raise RuntimeError(f"No frames read from {src}")

    target_id, selected_frame, selected_iou = select_target_track(detections_by_frame, init_frame, init_bbox, fps)
    raw_bboxes = np.full((index, 4), np.nan, dtype=np.float64)
    for frame_index, detections in enumerate(detections_by_frame):
        for track_id, bbox in detections:
            if track_id == target_id:
                raw_bboxes[frame_index] = bbox
                break

    bboxes, missing_count = interpolate_bboxes(raw_bboxes)
    bboxes = smooth(bboxes, radius=max(5, round(fps * 0.12)))
    logger.info(
        "detect done: target_id=%s selected_frame=%s iou=%.3f valid=%s missing=%s in %.1fs",
        target_id,
        selected_frame,
        selected_iou,
        index - missing_count,
        missing_count,
        time.monotonic() - started_at,
    )
    return bboxes, {
        "frame_count": index,
        "fps": fps,
        "init_frame": init_frame,
        "selected_frame": selected_frame,
        "selected_iou": selected_iou,
        "target_track_id": target_id,
        "valid_frame_count": index - missing_count,
        "missing_frame_count": missing_count,
    }


def write_live_detection_data(
    src: Path,
    detector: YOLO,
    class_id: int | None,
    init_crop: tuple[float, float, float, float],
    init_time: float,
    preview: bool,
    preview_video_max_height: int,
    live_json: Path,
    live_meta_extra: dict[str, object] | None,
    *,
    append: bool = False,
    segment_id: str = "base",
    revision: int = 0,
    frame_indices: list[int] | None = None,
    direction: str = "forward",
) -> None:
    started_at = time.monotonic()
    init_bbox = crop_to_xywh(init_crop)
    info = load_video_info(src)
    fps = info.fps
    source_frame_count = info.frame_count
    frame_count = source_frame_count if frame_indices is None else len(frame_indices)
    if preview:
        open_preview_window("video_track detect", info.width, info.height)
    preview_mp4v_path = default_detect_preview_mp4v_path(src)
    preview_h264_path = default_detect_preview_h264_path(src)
    preview_video_fps_value = detect_preview_video_fps(fps, frame_indices)
    init_frame = min(max(0, round(init_time * fps)), max(0, frame_count - 1))
    init_frame_original = frame_indices[init_frame] if frame_indices is not None else init_frame
    init_xyxy = xywh_to_xyxy(init_bbox)
    if frame_indices is None:
        logger.debug(
            "detect start: %s frames, %.3f fps, segment=%s revision=%s init_frame=%s",
            frame_count,
            fps,
            segment_id,
            revision,
            init_frame_original,
        )
    else:
        logger.debug(
            "detect start: %s frames, %.3f fps, segment=%s revision=%s init_frame=%s direction=%s",
            frame_count,
            fps,
            segment_id,
            revision,
            init_frame_original,
            direction,
        )
    index = 0
    preview_target_track_id: int | None = None
    preview_video_writer = None
    preview_h264_process: subprocess.Popen[bytes] | None = None
    try:
        with live_json.open("a" if append else "w", encoding="utf-8") as live_file:
            live_meta = {
                "schema": "video_track.live.v1",
                "type": "meta",
                "segment_id": segment_id,
                "revision": revision,
                "source": str(src),
                "frame_count": frame_count,
                "source_frame_count": source_frame_count,
                "segment_frame_count": frame_count,
                "fps": fps,
                **(live_meta_extra or {}),
                "init_time": init_time,
                "init_frame": init_frame_original,
                "segment_init_frame": init_frame,
                "direction": direction,
                "init_crop": list(init_crop),
                "init_crop_order": "w:h:x:y",
                "init_bbox": list(init_bbox),
                "init_bbox_order": "x:y:w:h",
            }
            if frame_indices is not None:
                live_meta["frame_range"] = [frame_indices[0], frame_indices[-1]]
            live_file.write(json.dumps(live_meta, separators=(",", ":")) + "\n")
            live_file.flush()
            logger.info("live detect JSONL start: %s", live_json)

            if frame_indices is None:
                stream = detector.track(
                    source=str(src),
                    stream=True,
                    classes=None if class_id is None else [class_id],
                    verbose=False,
                )
                with tqdm_progress(total=frame_count, desc=f"detect {segment_id}", unit="frame") as progress:
                    for result in stream:
                        frame_detections: list[tuple[int, np.ndarray]] = []
                        boxes = result.boxes
                        if boxes is not None and boxes.id is not None:
                            ids = boxes.id.cpu().numpy().astype(int)
                            xyxy = boxes.xyxy.cpu().numpy().astype(np.float64)
                            frame_detections = [(int(track_id), bbox) for track_id, bbox in zip(ids, xyxy)]

                        original_index = index
                        live_file.write(
                            json.dumps(
                                live_detection_record(original_index, frame_detections, segment_id, revision, index),
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                        live_file.flush()

                        preview_target_track_id = keep_preview_target_track(
                            preview_target_track_id,
                            frame_detections,
                            init_xyxy,
                        )
                        saved_status_text = detect_saved_preview_status(
                            original_index,
                            fps,
                        )
                        saved_preview_frame = draw_preview_frame(
                            result.orig_img,
                            frame_detections,
                            init_bbox,
                            original_index,
                            saved_status_text,
                            target_track_id=preview_target_track_id,
                            control_text=detect_saved_preview_control_text(),
                        )
                        if preview_video_writer is None:
                            preview_video_writer, preview_h264_process, output_preview_frame = open_detect_preview_video_writers(
                                preview_mp4v_path,
                                preview_h264_path,
                                preview_video_fps_value,
                                saved_preview_frame,
                                preview_video_max_height,
                            )
                        else:
                            output_preview_frame = resize_preview_video_frame(saved_preview_frame, preview_video_max_height)
                        preview_video_writer.write(output_preview_frame)
                        if preview_h264_process is not None and preview_h264_process.stdin is not None:
                            preview_h264_process.stdin.write(output_preview_frame.tobytes())

                        if preview:
                            pct = index / max(1, frame_count - 1) * 100
                            status_text = detect_preview_status(
                                original_index,
                                fps,
                                pct,
                                frame_count,
                                0,
                                max(0, frame_count - 1),
                            )
                            preview_frame = draw_preview_frame(
                                result.orig_img,
                                frame_detections,
                                init_bbox,
                                original_index,
                                status_text,
                                target_track_id=preview_target_track_id,
                            )
                            cv2.imshow("video_track detect", preview_frame)
                            key = cv2.waitKey(1) & 0xFF
                            if key in (27, ord("q")):
                                raise KeyboardInterrupt("preview interrupted")

                        index += 1
                        progress.update(1)
            else:
                cap = cv2.VideoCapture(str(src))
                if not cap.isOpened():
                    raise RuntimeError(f"Could not open {src}")
                try:
                    with tqdm_progress(total=frame_count, desc=f"detect {segment_id}", unit="frame") as progress:
                        for original_index in frame_indices:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, original_index)
                            ok, frame = cap.read()
                            if not ok:
                                if index:
                                    logger.warning(
                                        "could not read frame %s from %s; detect range truncated to %s frames ending at source frame %s",
                                        original_index,
                                        src,
                                        index,
                                        frame_indices[index - 1],
                                    )
                                    break
                                raise RuntimeError(f"Could not read frame {original_index} from {src}")

                            result = detector.track(
                                source=frame,
                                persist=True,
                                verbose=False,
                                classes=None if class_id is None else [class_id],
                            )[0]
                            frame_detections = []
                            boxes = result.boxes
                            if boxes is not None and boxes.id is not None:
                                ids = boxes.id.cpu().numpy().astype(int)
                                xyxy = boxes.xyxy.cpu().numpy().astype(np.float64)
                                frame_detections = [(int(track_id), bbox) for track_id, bbox in zip(ids, xyxy)]

                            live_file.write(
                                json.dumps(
                                    live_detection_record(original_index, frame_detections, segment_id, revision, index),
                                    separators=(",", ":"),
                                )
                                + "\n"
                            )
                            live_file.flush()

                            preview_target_track_id = keep_preview_target_track(
                                preview_target_track_id,
                                frame_detections,
                                init_xyxy,
                            )
                            saved_status_text = detect_saved_preview_status(
                                original_index,
                                fps,
                            )
                            saved_preview_frame = draw_preview_frame(
                                frame,
                                frame_detections,
                                init_bbox,
                                original_index,
                                saved_status_text,
                                target_track_id=preview_target_track_id,
                                control_text=detect_saved_preview_control_text(),
                            )
                            if preview_video_writer is None:
                                preview_video_writer, preview_h264_process, output_preview_frame = open_detect_preview_video_writers(
                                    preview_mp4v_path,
                                    preview_h264_path,
                                    preview_video_fps_value,
                                    saved_preview_frame,
                                    preview_video_max_height,
                                )
                            else:
                                output_preview_frame = resize_preview_video_frame(saved_preview_frame, preview_video_max_height)
                            preview_video_writer.write(output_preview_frame)
                            if preview_h264_process is not None and preview_h264_process.stdin is not None:
                                preview_h264_process.stdin.write(output_preview_frame.tobytes())

                            if preview:
                                pct = index / max(1, frame_count - 1) * 100
                                status_text = detect_preview_status(
                                    original_index,
                                    fps,
                                    pct,
                                    frame_count,
                                    frame_indices[0],
                                    frame_indices[-1],
                                )
                                preview_frame = draw_preview_frame(
                                    frame,
                                    frame_detections,
                                    init_bbox,
                                    original_index,
                                    status_text,
                                    target_track_id=preview_target_track_id,
                                )
                                cv2.imshow("video_track detect", preview_frame)
                                key = cv2.waitKey(1) & 0xFF
                                if key in (27, ord("q")):
                                    raise KeyboardInterrupt("preview interrupted")

                            index += 1
                            progress.update(1)
                finally:
                    cap.release()
    finally:
        close_detect_preview_video_writers(preview_video_writer, preview_h264_process)
        if preview:
            cv2.destroyWindow("video_track detect")

    if index == 0:
        raise RuntimeError(f"No frames read from {src}")
    logger.info("live detect JSONL written: %s", live_json)
    logger.info("detect preview mp4v video written: %s", preview_mp4v_path)
    logger.info("detect preview h264 video written: %s", preview_h264_path)


def write_segment_video(
    src: Path,
    dst: Path,
    start_frame: int,
    end_frame: int,
) -> tuple[list[int], float, tuple[int, int]]:
    started_at = time.monotonic()
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {src}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = 1 if end_frame >= start_frame else -1
    frame_map = list(range(start_frame, end_frame + step, step))
    logger.info(
        "segment video write start: %s frames %s..%s -> %s",
        len(frame_map),
        start_frame,
        end_frame,
        dst,
    )
    writer = cv2.VideoWriter(
        str(dst),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (src_w, src_h),
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Could not write {dst}")

    written_frame_map: list[int] = []
    try:
        with tqdm_progress(total=len(frame_map), desc="segment", unit="frame") as progress:
            for frame_index in frame_map:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = cap.read()
                if not ok:
                    if written_frame_map:
                        logger.warning(
                            "could not read frame %s from %s; segment truncated to %s frames ending at source frame %s",
                            frame_index,
                            src,
                            len(written_frame_map),
                            written_frame_map[-1],
                        )
                        break
                    raise RuntimeError(f"Could not read frame {frame_index} from {src}")
                writer.write(frame)
                written_frame_map.append(frame_index)
                progress.update(1)
    finally:
        writer.release()
        cap.release()

    if not written_frame_map:
        raise RuntimeError(f"No frames read from {src}")
    logger.info(
        "segment video written: %s frames %s..%s -> %s",
        len(written_frame_map),
        written_frame_map[0],
        written_frame_map[-1],
        dst,
    )
    return written_frame_map, fps, (src_w, src_h)


def next_revision(live_json: Path) -> int:
    if not live_json.exists():
        return 1
    highest = 0
    with live_json.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            highest = max(highest, int(record.get("revision", 0)))
    return highest + 1


def build_track_data(
    src: Path,
    detector: object,
    model: str,
    class_name: str | None,
    class_id: int | None,
    init_crop: tuple[float, float, float, float],
    init_time: float,
    preview: bool,
    live_json: Path | None,
) -> dict[str, object]:
    width, height = video_size(src)

    init_bbox = crop_to_xywh(init_crop)
    live_meta_extra = {
        "model": model,
        "class_name": class_name,
        "class_id": class_id,
    }
    bboxes, detect_meta = detect_target_bboxes(
        src,
        detector,
        class_id,
        init_bbox,
        init_time,
        preview,
        live_json,
        live_meta_extra,
    )
    frames: list[dict[str, object]] = []
    for index, bbox in enumerate(bboxes):
        frames.append({"n": index, "bbox": xyxy_to_xywh(bbox)})

    return {
        "schema": "video_track.v1",
        "source": str(src),
        "width": width,
        "height": height,
        "model": model,
        "class_name": class_name,
        "class_id": class_id,
        "init_crop": list(init_crop),
        "init_crop_order": "w:h:x:y",
        "init_bbox": list(init_bbox),
        "init_bbox_order": "x:y:w:h",
        **detect_meta,
        "bbox_order": "x:y:w:h",
        "frames": frames,
    }


def decode_live_frame_record(record: dict[str, object]) -> list[tuple[int, np.ndarray]]:
    frame_detections: list[tuple[int, np.ndarray]] = []
    for detection in record.get("detections", []):
        track_id = int(detection["track_id"])
        if "xyxy" in detection:
            bbox = np.array(detection["xyxy"], dtype=np.float64)
        else:
            x, y, w, h = detection["bbox"]
            bbox = np.array([x, y, x + w, y + h], dtype=np.float64)
        frame_detections.append((track_id, bbox))
    return frame_detections


def read_live_detection_segments(src: Path) -> list[dict[str, object]]:
    segments: dict[str, dict[str, object]] = {}
    order = 0

    with src.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("schema") != "video_track.live.v1":
                raise ValueError(f"Unsupported live JSON schema on line {line_number}: {record.get('schema')!r}")

            record_type = record.get("type")
            segment_id = str(record.get("segment_id", "base"))
            if segment_id not in segments:
                segments[segment_id] = {
                    "segment_id": segment_id,
                    "revision": int(record.get("revision", 0)),
                    "order": order,
                    "meta": None,
                    "frames": {},
                }
                order += 1
            if record_type == "meta":
                segments[segment_id]["meta"] = record
                segments[segment_id]["revision"] = int(record.get("revision", 0))
                continue
            if record_type != "frame":
                continue

            frame_index = int(record["n"])
            frames = segments[segment_id]["frames"]
            assert isinstance(frames, dict)
            frames[frame_index] = decode_live_frame_record(record)

    if not segments:
        raise ValueError(f"Live JSONL has no meta record: {src}")
    for segment in segments.values():
        if segment["meta"] is None:
            raise ValueError(f"Live JSONL segment has no meta record: {segment['segment_id']}")
        if not segment["frames"]:
            raise ValueError(f"Live JSONL segment has no frame records: {segment['segment_id']}")

    return sorted(segments.values(), key=lambda item: (int(item["revision"]), int(item["order"])))


def read_live_detection_data(src: Path) -> tuple[dict[str, object], list[list[tuple[int, np.ndarray]]]]:
    segments = read_live_detection_segments(src)
    meta = segments[0]["meta"]
    assert isinstance(meta, dict)
    frames_by_index: dict[int, list[tuple[int, np.ndarray]]] = {}
    for segment in segments:
        frames = segment["frames"]
        assert isinstance(frames, dict)
        for frame_index, frame_detections in frames.items():
            frames_by_index[int(frame_index)] = frame_detections

    if not frames_by_index:
        raise ValueError(f"Live JSONL has no frame records: {src}")

    last_index = max(frames_by_index)
    detections_by_frame: list[list[tuple[int, np.ndarray]]] = []
    for index in range(last_index + 1):
        detections_by_frame.append(frames_by_index.get(index, []))
    return meta, detections_by_frame


def compact_live_detection_data(src: Path) -> None:
    metas_by_segment: dict[str, tuple[int, dict[str, object]]] = {}
    frames_by_index: dict[int, tuple[int, int, dict[str, object]]] = {}
    line_order = 0
    with src.open("r", encoding="utf-8") as file:
        for line in file:
            line_order += 1
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("schema") != "video_track.live.v1":
                continue
            segment_id = str(record.get("segment_id", "base"))
            revision = int(record.get("revision", 0))
            if record.get("type") == "meta":
                metas_by_segment[segment_id] = (line_order, record)
                continue
            if record.get("type") != "frame":
                continue
            frame_index = int(record["n"])
            previous = frames_by_index.get(frame_index)
            if previous is None or (revision, line_order) >= (previous[0], previous[1]):
                frames_by_index[frame_index] = (revision, line_order, record)

    kept_segment_ids = {str(record.get("segment_id", "base")) for _, _, record in frames_by_index.values()}
    compact_records: list[dict[str, object]] = []
    for _, meta in sorted(metas_by_segment.values(), key=lambda item: (int(item[1].get("revision", 0)), item[0])):
        if str(meta.get("segment_id", "base")) in kept_segment_ids:
            compact_records.append(meta)
    for frame_index in sorted(frames_by_index):
        compact_records.append(frames_by_index[frame_index][2])

    tmp = src.with_suffix(src.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        for record in compact_records:
            file.write(json.dumps(record, separators=(",", ":")) + "\n")
    tmp.replace(src)
    logger.info("live JSONL compacted: %s records -> %s", len(compact_records), src)


def finalize_track_data(
    src: Path,
    live_json: Path,
    init_crop: tuple[float, float, float, float] | None,
    init_time: float | None,
) -> dict[str, object]:
    width, height = video_size(src)
    segments = read_live_detection_segments(live_json)
    first_meta = segments[0]["meta"]
    assert isinstance(first_meta, dict)

    fps = float(first_meta.get("fps", 0.0))
    if fps <= 0:
        raise ValueError("Live JSONL meta has invalid fps")

    total_frame_count = int(first_meta.get("source_frame_count") or first_meta.get("frame_count", 0))
    for segment in segments:
        meta = segment["meta"]
        assert isinstance(meta, dict)
        source_frame_count = int(meta.get("source_frame_count") or 0)
        if source_frame_count > 0:
            total_frame_count = max(total_frame_count, source_frame_count)
        frames = segment["frames"]
        assert isinstance(frames, dict)
        if frames:
            total_frame_count = max(total_frame_count, max(int(index) for index in frames) + 1)
    if total_frame_count <= 0:
        raise ValueError("Live JSONL has no usable frame records")

    merged_raw_bboxes = np.full((total_frame_count, 4), np.nan, dtype=np.float64)
    edits: list[dict[str, object]] = []

    for segment_position, segment in enumerate(segments):
        meta = segment["meta"]
        frames_by_index = segment["frames"]
        assert isinstance(meta, dict)
        assert isinstance(frames_by_index, dict)
        frame_numbers = sorted(int(index) for index in frames_by_index)
        detections_by_frame = [frames_by_index[index] for index in frame_numbers]
        if segment_position == 0 and init_crop is not None:
            segment_init_crop = init_crop
            segment_init_bbox = crop_to_xywh(segment_init_crop)
        else:
            if meta.get("init_bbox_order") != "x:y:w:h":
                raise ValueError("Live JSONL meta has no supported init_bbox; pass --init-bbox W:H:X:Y")
            init_bbox_values = meta.get("init_bbox")
            if not isinstance(init_bbox_values, list) or len(init_bbox_values) != 4:
                raise ValueError("Live JSONL meta has no init_bbox; pass --init-bbox W:H:X:Y")
            segment_init_bbox = tuple(float(value) for value in init_bbox_values)
            x, y, w, h = segment_init_bbox
            segment_init_crop = (w, h, x, y)

        if segment_position == 0 and init_time is not None:
            segment_init_frame = round(init_time * fps)
            segment_init_time = init_time
        else:
            segment_init_frame = int(meta.get("init_frame", frame_numbers[0]))
            segment_init_time = float(meta.get("init_time", segment_init_frame / fps))
        local_init_frame = min(
            range(len(frame_numbers)),
            key=lambda index: abs(frame_numbers[index] - segment_init_frame),
        )

        raw_bboxes, target_id, selected_local_frame, selected_iou = select_target_bboxes_by_iou(
            detections_by_frame,
            local_init_frame,
            segment_init_bbox,
            fps,
        )
        range_meta = meta.get("range")
        if isinstance(range_meta, dict) and "start_frame" in range_meta and "end_frame" in range_meta:
            range_start = int(range_meta["start_frame"])
            range_end = int(range_meta["end_frame"])
            dense_start = min(range_start, range_end)
            dense_end = max(range_start, range_end)
        else:
            dense_start = min(frame_numbers)
            dense_end = max(frame_numbers)
        dense_start = min(max(0, dense_start), total_frame_count - 1)
        dense_end = min(max(0, dense_end), total_frame_count - 1)
        dense_frame_numbers = np.arange(dense_start, dense_end + 1, dtype=np.int64)
        segment_bboxes, segment_missing_count = interpolate_bboxes_at_frames(
            frame_numbers,
            raw_bboxes,
            dense_frame_numbers,
        )
        segment_bboxes = smooth(segment_bboxes, radius=max(1, min(round(fps * 0.12), len(dense_frame_numbers) // 2)))
        for local_index, frame_index in enumerate(dense_frame_numbers):
            merged_raw_bboxes[int(frame_index)] = segment_bboxes[local_index]

        selected_frame = frame_numbers[selected_local_frame]
        logger.info(
            "finalize segment: segment=%s revision=%s target_id=%s selected_frame=%s iou=%.3f valid=%s missing=%s",
            meta.get("segment_id", "base"),
            meta.get("revision", 0),
            target_id,
            selected_frame,
            selected_iou,
            len(frame_numbers) - segment_missing_count,
            segment_missing_count,
        )
        edit = {
            "type": "detect" if segment_position == 0 else "detect_range",
            "segment_id": meta.get("segment_id", "base"),
            "revision": int(meta.get("revision", 0)),
            "direction": meta.get("direction", "forward"),
            "start_frame": dense_start,
            "end_frame": dense_end,
            "sample_start_frame": frame_numbers[0],
            "sample_end_frame": frame_numbers[-1],
            "sample_frame_count": len(frame_numbers),
            "init_crop": list(segment_init_crop),
            "init_crop_order": "w:h:x:y",
            "init_frame": segment_init_frame,
            "init_time": segment_init_time,
            "selected_frame": selected_frame,
            "selected_iou": selected_iou,
            "target_track_id": target_id,
            "valid_frame_count": len(frame_numbers) - segment_missing_count,
            "missing_frame_count": segment_missing_count,
        }
        edits.append(edit)

    bboxes, missing_count = interpolate_bboxes(merged_raw_bboxes)
    bboxes = smooth(bboxes, radius=max(5, round(fps * 0.12)))
    frames: list[dict[str, object]] = []
    for index, bbox in enumerate(bboxes):
        frames.append({"n": index, "bbox": xyxy_to_xywh(bbox)})

    logger.info(
        "finalize: segments=%s valid=%s missing=%s",
        len(segments),
        total_frame_count - missing_count,
        missing_count,
    )
    return {
        "schema": "video_track.v1",
        "source": str(src),
        "width": width,
        "height": height,
        "model": first_meta.get("model"),
        "class_name": first_meta.get("class_name"),
        "class_id": first_meta.get("class_id"),
        "frame_count": total_frame_count,
        "fps": fps,
        "valid_frame_count": total_frame_count - missing_count,
        "missing_frame_count": missing_count,
        "bbox_order": "x:y:w:h",
        "edits": edits,
        "frames": frames,
    }


def write_track_data(track_data: dict[str, object], dst: Path) -> None:
    dst.write_text(json.dumps(track_data, indent=2) + "\n", encoding="utf-8")
    logger.info("track data written: %s", dst)


def read_track_data(src: Path) -> dict[str, object]:
    data = json.loads(src.read_text(encoding="utf-8"))
    if data.get("schema") != "video_track.v1":
        raise ValueError(f"Unsupported track data schema: {data.get('schema')!r}")
    if data.get("bbox_order") != "x:y:w:h":
        raise ValueError(f"Unsupported bbox order: {data.get('bbox_order')!r}")
    if not isinstance(data.get("frames"), list):
        raise ValueError("Track data has no frames list")
    return data


def mux_audio(
    src: Path,
    temp_video: Path,
    dst: Path,
    dry_run: bool,
    *,
    audio_start_seconds: float | None = None,
    audio_duration_seconds: float | None = None,
) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-i",
        str(temp_video),
    ]
    if audio_start_seconds is not None:
        cmd.extend(["-ss", f"{max(0.0, audio_start_seconds):.6f}"])
    if audio_duration_seconds is not None:
        cmd.extend(["-t", f"{max(0.0, audio_duration_seconds):.6f}"])
    use_shortest = audio_start_seconds is None and audio_duration_seconds is None
    cmd.extend(
        [
            "-i",
            str(src),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0?",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
        ]
    )
    if use_shortest:
        cmd.append("-shortest")
    cmd.append(str(dst))
    cmd_text = shell_join(cmd)
    if dry_run:
        print(cmd_text)
        return
    logger.info(cmd_text)
    logger.info("mux start: stream copy")
    subprocess.run(cmd, check=True)
    logger.info("mux done: %s", dst)


def main() -> int:
    from video_track_draw_box import draw_box, parse_color
    from video_track_stabilize import DEFAULT_SMOOTH_SECONDS, stabilize

    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    def add_detect_args(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--init-bbox",
            required=True,
            type=parse_crop,
            metavar="W:H:X:Y",
            help="Initial target crop in ffmpeg crop order: width:height:x:y",
        )

    def add_detect_options(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--init-time", type=float, default=0.0)
        subparser.add_argument("--model", default="yolo26n.pt")
        subparser.add_argument("--class-name", default="person")
        subparser.add_argument("--class-id", type=int)
        subparser.add_argument("--preview_gui", action="store_true")
        subparser.add_argument(
            "--preview_video_max_height",
            type=int,
            default=720,
            help="Maximum height in pixels for detect preview MKV videos. Use 0 to keep original size",
        )

    subparser = subparsers.add_parser("list_class_names", formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=list_class_names)
    subparser.add_argument("--model", default="yolo26n.pt")

    subparser = subparsers.add_parser("plan_detect", formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=plan_detect)
    subparser.add_argument("input")
    subparser.add_argument("live_json")
    subparser.add_argument("--interval", type=float, default=60.0)
    subparser.add_argument("--stride", type=int, default=10)
    subparser.add_argument("--script", default="video_track.py")
    subparser.add_argument("--bbox-placeholder", default="TODO_W:H:X:Y_AT_{start}")
    subparser.add_argument(
        "--no-ai-cmds-log",
        action="store_true",
        help="Do not append generated commands to /tmp/ai_cmds.bash",
    )

    subparser = subparsers.add_parser("detect", formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=detect)
    subparser.add_argument("input")
    subparser.add_argument("live_json")
    subparser.add_argument(
        "--start",
        type=video_time.parse_time_or_frame,
        help="Start frame/time, e.g. frame:10, f:10, 0:01.700, last",
    )
    subparser.add_argument("--end", type=video_time.parse_time_or_frame, help="End frame/time, e.g. frame:20, f:20, 0:02.400, last")
    subparser.add_argument(
        "--duration",
        type=parse_detect_duration,
        help="Duration as time or frame:N/f:N. Negative values reverse direction, e.g. --duration f:-10",
    )
    subparser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Detect every Nth frame and interpolate the rest later",
    )
    subparser.add_argument("--segment-id", help="Override JSONL segment id")
    add_detect_args(subparser)
    add_detect_options(subparser)

    subparser = subparsers.add_parser("stabilize", formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=stabilize)
    subparser.add_argument("input")
    subparser.add_argument("track_json")
    subparser.add_argument("--mp4v-output", help="Path for the OpenCV mp4v no-audio stabilized video")
    subparser.add_argument("--h264-output", help="Path for the real-time libx264 stabilized video with copied audio")
    subparser.add_argument("--margin", type=float, default=1.35, help="Crop size multiplier around the tracked bbox")
    subparser.add_argument(
        "--smooth-seconds",
        type=float,
        default=DEFAULT_SMOOTH_SECONDS,
        help="Temporal smoothing window in seconds for the stabilize crop center and size",
    )
    subparser.add_argument("--preview_gui", action="store_true", help="Show an OpenCV preview window while processing")
    subparser.add_argument("-n", "--dry_run", action="store_true")

    subparser = subparsers.add_parser("draw_box", formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=draw_box)
    subparser.add_argument("input")
    subparser.add_argument("track_json")
    subparser.add_argument("--mp4v-output", help="Path for the OpenCV mp4v no-audio boxed video")
    subparser.add_argument("--h264-output", help="Path for the real-time libx264 boxed video with copied audio")
    subparser.add_argument(
        "--start",
        type=video_time.parse_time_or_frame,
        help="Start frame/time, e.g. frame:10, f:10, 0:01.700, last. If used alone, --end defaults to last",
    )
    subparser.add_argument("--end", type=video_time.parse_time_or_frame, help="End frame/time, e.g. frame:20, f:20, 0:02.400, last")
    subparser.add_argument(
        "--duration",
        type=parse_detect_duration,
        help="Duration as time or frame:N/f:N, e.g. --duration f:300",
    )
    subparser.add_argument("--color", type=parse_color, default=(0, 255, 0), metavar="R:G:B")
    subparser.add_argument("--thickness", type=int, default=3, help="BBox line thickness in pixels")
    subparser.add_argument(
        "--show_stabilize_crop",
        action="store_true",
        help="Also draw the smoothed crop bbox used by stabilize",
    )
    subparser.add_argument(
        "--stabilize-margin",
        type=float,
        default=1.35,
        help="Crop size multiplier used when drawing the stabilize crop bbox",
    )
    subparser.add_argument(
        "--stabilize-smooth-seconds",
        type=float,
        default=DEFAULT_SMOOTH_SECONDS,
        help="Temporal smoothing window in seconds used when drawing the stabilize crop bbox",
    )
    subparser.add_argument("--stabilize-crop-color", type=parse_color, default=(0, 0, 255), metavar="R:G:B")
    subparser.add_argument("--preview_gui", action="store_true", help="Show an OpenCV preview window while processing")
    subparser.add_argument("-n", "--dry_run", action="store_true")

    subparser = subparsers.add_parser("finalize", formatter_class=ArgumentDefaultsRawTextHelpFormatter)
    subparser.set_defaults(func=finalize)
    subparser.add_argument("input")
    subparser.add_argument("live_json")
    subparser.add_argument("track_json")
    subparser.add_argument(
        "--init-bbox",
        type=parse_crop,
        metavar="W:H:X:Y",
        help="Override initial target crop in ffmpeg crop order: width:height:x:y",
    )
    subparser.add_argument("--init-time", type=float, help="Override initial target time in seconds")
    subparser.add_argument(
        "--no-compact-jsonl",
        action="store_true",
        help="Do not rewrite live_json with duplicate frame records removed after finalize",
    )

    args = parser.parse_args()
    logger.debug(f"{args=}")
    return args.func(args)


def list_class_names(args: argparse.Namespace) -> int:
    from ultralytics import YOLO

    logger.info("load model: %s", args.model)
    detector = YOLO(args.model)
    for class_id, name in detector.names.items():
        print(f"{class_id}\t{name}")
    return 0


def plan_detect(args: argparse.Namespace) -> int:
    if args.stride <= 0:
        raise SystemExit("--stride must be positive")
    if args.interval <= 0:
        raise SystemExit("--interval must be positive")

    load_video_modules()

    src = Path(args.input)
    info = load_video_info(src)
    if info.fps <= 0:
        raise RuntimeError(f"Could not determine fps for {src}")
    duration_seconds = info.frame_count / info.fps
    center_times = interval_center_times(duration_seconds, args.interval)
    half_interval = args.interval / 2

    commands: list[str] = []
    for index, center_seconds in enumerate(center_times, start=1):
        start_arg = format_seconds_arg(center_seconds)
        bbox = format_bbox_placeholder(args.bbox_placeholder, n=index, start=start_arg, start_seconds=center_seconds)
        backward_end = format_seconds_arg(max(0.0, center_seconds - half_interval))
        forward_end = (
            "last"
            if index == len(center_times) or center_seconds + half_interval >= duration_seconds
            else format_seconds_arg(center_seconds + half_interval)
        )

        for end_arg in (backward_end, forward_end):
            cmd = [
                args.script,
                "detect",
                str(src),
                str(args.live_json),
            ]
            cmd.extend(
                [
                    f"--stride={args.stride}",
                    f"--start={start_arg}",
                    f"--end={end_arg}",
                    "--init-bbox",
                    bbox,
                ]
            )
            commands.append(shell_join_copyable(cmd))

    for command in commands:
        print(command)
    if not args.no_ai_cmds_log:
        append_ai_commands_log(commands)
    return 0


def detect(args: argparse.Namespace) -> int:
    range_args = [args.start, args.end, args.duration]
    range_arg_count = sum(value is not None for value in range_args)
    has_range = range_arg_count > 0
    if range_arg_count not in (0, 2):
        raise SystemExit("detect range needs two of --start, --end, --duration")
    if args.segment_id and not has_range:
        raise SystemExit("--segment-id is only valid with --start/--end/--duration")
    if args.stride <= 0:
        raise SystemExit("--stride must be positive")

    load_video_modules()
    from ultralytics import YOLO

    src = Path(args.input)
    live_json = Path(args.live_json)

    logger.debug("load model: %s", args.model)
    detector = YOLO(args.model)
    class_id = resolve_class_id(detector, args.class_name, args.class_id)
    logger.debug("target class: %s", "all" if class_id is None else f"{class_id}:{detector.names[class_id]}")

    if not has_range:
        live_meta_extra = {
            "model": args.model,
            "class_name": args.class_name,
            "class_id": class_id,
            "stride": args.stride,
        }
        frame_indices = None
        if args.stride > 1:
            info = load_video_info(src)
            frame_indices = sample_frame_indices(0, max(0, info.frame_count - 1), args.stride)
        write_live_detection_data(
            src,
            detector,
            class_id,
            args.init_bbox,
            args.init_time,
            args.preview_gui,
            args.preview_video_max_height,
            live_json,
            live_meta_extra,
            frame_indices=frame_indices,
        )
        return 0

    info = load_video_info(src)
    fps = info.fps
    frame_count = info.frame_count

    start_frame, end_frame = resolve_detect_range(
        start=args.start,
        end=args.end,
        duration=args.duration,
        fps=fps,
        frame_count=frame_count,
    )
    revision = next_revision(live_json)
    segment_id = args.segment_id or f"fix-{revision:03d}"
    direction = "forward" if end_frame >= start_frame else "reverse"
    logger.debug(
        "detect range: segment=%s revision=%s direction=%s frames %s..%s (%s frames)",
        segment_id,
        revision,
        direction,
        start_frame,
        end_frame,
        abs(end_frame - start_frame) + 1,
    )
    frame_indices = sample_frame_indices(start_frame, end_frame, args.stride)
    live_meta_extra = {
        "model": args.model,
        "class_name": args.class_name,
        "class_id": class_id,
        "stride": args.stride,
        "range": {
            "start_frame": start_frame,
            "end_frame": end_frame,
        },
    }
    write_live_detection_data(
        src,
        detector,
        class_id,
        args.init_bbox,
        args.init_time,
        args.preview_gui,
        args.preview_video_max_height,
        live_json,
        live_meta_extra,
        append=True,
        segment_id=segment_id,
        revision=revision,
        frame_indices=frame_indices,
        direction=direction,
    )
    return 0


def finalize(args: argparse.Namespace) -> int:
    load_video_modules()

    src = Path(args.input)
    live_json = Path(args.live_json)
    track_json = Path(args.track_json)
    track_data = finalize_track_data(src, live_json, args.init_bbox, args.init_time)
    write_track_data(track_data, track_json)
    if not args.no_compact_jsonl:
        compact_live_detection_data(live_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
