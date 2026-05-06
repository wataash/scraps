from __future__ import annotations

import argparse
import fractions
import typing as t


class TimeOrFrame(t.NamedTuple):
    kind: str
    value: fractions.Fraction | int


class FrameRange(t.NamedTuple):
    start: int
    end: int


class CutTimes(t.NamedTuple):
    start: fractions.Fraction | None
    duration: fractions.Fraction | None


def parse_time_seconds(value: str) -> fractions.Fraction:
    try:
        if ":" not in value:
            seconds = fractions.Fraction(value)
        else:
            fields = value.split(":")
            if len(fields) not in (2, 3):
                raise ValueError
            seconds = fractions.Fraction(0)
            for field in fields:
                if field == "":
                    raise ValueError
                seconds = seconds * 60 + fractions.Fraction(field)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError(f"invalid time: {value!r}") from exc

    if seconds < 0:
        raise argparse.ArgumentTypeError(f"time must be non-negative: {value!r}")
    return seconds


def parse_time_or_frame(value: str) -> TimeOrFrame:
    if value == "last":
        return TimeOrFrame(kind="last", value=0)
    if value.startswith("frame:"):
        frame_text = value.split(":", 1)[1]
        try:
            frame = int(frame_text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid frame: {value!r}") from exc
        if frame < 0:
            raise argparse.ArgumentTypeError(f"frame must be non-negative: {value!r}")
        return TimeOrFrame(kind="frame", value=frame)
    if value.startswith("f:"):
        return parse_time_or_frame("frame:" + value.split(":", 1)[1])
    if value.startswith("f") and value[1:].isdigit():
        return TimeOrFrame(kind="frame", value=int(value[1:]))
    return TimeOrFrame(kind="time", value=parse_time_seconds(value))


def parse_fps(value: str) -> fractions.Fraction:
    try:
        fps = fractions.Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError(f"invalid fps: {value!r}") from exc
    if fps <= 0:
        raise argparse.ArgumentTypeError(f"fps must be positive: {value!r}")
    return fps


def is_frame_ref(value: TimeOrFrame | None) -> bool:
    return value is not None and value.kind == "frame"


def is_last_ref(value: TimeOrFrame | None) -> bool:
    return value is not None and value.kind == "last"


def resolve_seconds(
    value: TimeOrFrame | None,
    fps: fractions.Fraction | None,
    duration: fractions.Fraction | None = None,
) -> fractions.Fraction | None:
    if value is None:
        return None
    if value.kind == "time":
        return t.cast(fractions.Fraction, value.value)
    if value.kind == "last":
        if duration is None:
            raise SystemExit("last needs video duration")
        return duration
    if fps is None:
        raise SystemExit("frame:N needs video fps")
    return fractions.Fraction(t.cast(int, value.value), 1) / fps


def resolve_cut_times(
    *,
    start: fractions.Fraction | None,
    end: fractions.Fraction | None,
    duration: fractions.Fraction | None,
    require_any: bool = True,
    start_name: str = "--start",
    end_name: str = "--end",
    duration_name: str = "--duration",
) -> CutTimes:
    specified = [value is not None for value in (start, end, duration)].count(True)
    if specified == 0:
        if require_any:
            raise SystemExit(f"at least one of {start_name}, {end_name}, {duration_name} is required")
        return CutTimes(start=None, duration=None)
    if specified == 3:
        raise SystemExit(f"specify at most two of {start_name}, {end_name}, {duration_name}")

    if start is not None and end is not None:
        if end <= start:
            raise SystemExit(f"{end_name} must be greater than {start_name}")
        return CutTimes(start=start, duration=end - start)

    if start is not None and duration is not None:
        if duration <= 0:
            raise SystemExit(f"{duration_name} must be positive")
        return CutTimes(start=start, duration=duration)

    if end is not None and duration is not None:
        if duration <= 0:
            raise SystemExit(f"{duration_name} must be positive")
        start = end - duration
        if start < 0:
            raise SystemExit(f"{end_name} minus {duration_name} must be non-negative")
        return CutTimes(start=start, duration=duration)

    if start is not None:
        return CutTimes(start=start, duration=None)

    if end is not None:
        if end <= 0:
            raise SystemExit(f"{end_name} must be positive")
        return CutTimes(start=None, duration=end)

    assert duration is not None
    if duration <= 0:
        raise SystemExit(f"{duration_name} must be positive")
    return CutTimes(start=None, duration=duration)


def resolve_frame_index(value: TimeOrFrame, fps: float | fractions.Fraction, frame_count: int) -> int:
    if value.kind == "last":
        return max(0, frame_count - 1)
    if value.kind == "frame":
        frame = int(value.value)
    else:
        frame = round(float(value.value) * float(fps))
    return min(max(0, frame), max(0, frame_count - 1))


def resolve_cut_boundary_frame(value: TimeOrFrame, fps: float | fractions.Fraction, frame_count: int) -> int:
    if value.kind == "last":
        return frame_count
    if value.kind == "frame":
        frame = int(value.value)
    else:
        frame = round(float(value.value) * float(fps))
    return min(max(0, frame), frame_count)


def resolve_cut_duration_frames(
    value: TimeOrFrame,
    fps: float | fractions.Fraction,
    *,
    duration_name: str = "--duration",
) -> int:
    if value.kind == "last":
        raise SystemExit(f"{duration_name} cannot be last")
    if value.kind == "frame":
        frames = int(value.value)
    else:
        frames = round(float(value.value) * float(fps))
    if frames <= 0:
        raise SystemExit(f"{duration_name} must be positive")
    return frames


def resolve_frame_cut_range(
    *,
    start: TimeOrFrame | None,
    end: TimeOrFrame | None,
    duration: TimeOrFrame | None,
    fps: float | fractions.Fraction,
    frame_count: int,
    start_name: str = "--start",
    end_name: str = "--end",
    duration_name: str = "--duration",
) -> FrameRange:
    specified = [value is not None for value in (start, end, duration)].count(True)
    if specified == 0:
        return FrameRange(start=0, end=max(0, frame_count - 1))
    if specified == 3:
        raise SystemExit(f"specify at most two of {start_name}, {end_name}, {duration_name}")

    if start is not None and end is not None:
        start_frame = resolve_cut_boundary_frame(start, fps, frame_count)
        end_boundary = resolve_cut_boundary_frame(end, fps, frame_count)
        if end_boundary <= start_frame:
            raise SystemExit(f"{end_name} must be greater than {start_name}")
        return FrameRange(start=start_frame, end=end_boundary - 1)

    if start is not None and duration is not None:
        start_frame = resolve_cut_boundary_frame(start, fps, frame_count)
        return FrameRange(
            start=start_frame,
            end=start_frame + resolve_cut_duration_frames(duration, fps, duration_name=duration_name) - 1,
        )

    if end is not None and duration is not None:
        end_boundary = resolve_cut_boundary_frame(end, fps, frame_count)
        duration_frames = resolve_cut_duration_frames(duration, fps, duration_name=duration_name)
        start_frame = end_boundary - duration_frames
        if start_frame < 0:
            raise SystemExit(f"{end_name} minus {duration_name} must be non-negative")
        return FrameRange(start=start_frame, end=end_boundary - 1)

    if start is not None:
        start_frame = resolve_cut_boundary_frame(start, fps, frame_count)
        if start_frame >= frame_count:
            raise SystemExit(f"{start_name} must be before the end of the video")
        return FrameRange(start=start_frame, end=frame_count - 1)

    if end is not None:
        end_boundary = resolve_cut_boundary_frame(end, fps, frame_count)
        if end_boundary <= 0:
            raise SystemExit(f"{end_name} must be positive")
        return FrameRange(start=0, end=end_boundary - 1)

    assert duration is not None
    return FrameRange(start=0, end=resolve_cut_duration_frames(duration, fps, duration_name=duration_name) - 1)
