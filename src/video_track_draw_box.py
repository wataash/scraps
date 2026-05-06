from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

import video_track as vt
from video_track_stabilize import DEFAULT_SMOOTH_SECONDS, compute_stabilize_crop_geometry


def default_boxed_mp4v_path(src: Path) -> Path:
    return src.with_name(f"{src.stem}.boxed.mp4v.mkv")


def default_boxed_h264_path(src: Path) -> Path:
    return src.with_name(f"{src.stem}.boxed.h264.mkv")


def build_h264_writer_command(
    src: Path,
    dst: Path,
    fps: float,
    width: int,
    height: int,
    audio_start_seconds: float | None,
    audio_duration_seconds: float | None,
) -> list[str]:
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
    ]
    if audio_start_seconds is not None:
        cmd.extend(["-ss", f"{max(0.0, audio_start_seconds):.6f}"])
    if audio_duration_seconds is not None:
        cmd.extend(["-t", f"{max(0.0, audio_duration_seconds):.6f}"])
    cmd.extend(
        [
            "-i",
            str(src),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-shortest",
            str(dst),
        ]
    )
    return cmd


def open_h264_writer(
    src: Path,
    dst: Path,
    fps: float,
    width: int,
    height: int,
    dry_run: bool,
    audio_start_seconds: float | None,
    audio_duration_seconds: float | None,
) -> subprocess.Popen[bytes] | None:
    cmd = build_h264_writer_command(src, dst, fps, width, height, audio_start_seconds, audio_duration_seconds)
    cmd_text = vt.shell_join(cmd)
    if dry_run:
        print(cmd_text)
        return None
    vt.logger.info(cmd_text)
    vt.logger.info("draw_box h264 video: %s", dst)
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def close_h264_writer(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return
    if process.stdin is not None:
        process.stdin.close()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg h264 draw_box writer failed with exit code {return_code}")


def parse_color(value: str) -> tuple[int, int, int]:
    try:
        parts = [int(part) for part in value.split(":")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("color must be R:G:B") from exc
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("color must be R:G:B")
    if any(part < 0 or part > 255 for part in parts):
        raise argparse.ArgumentTypeError("color values must be 0..255")
    r, g, b = parts
    return b, g, r


def draw_video(
    src: Path,
    mp4v_video: Path,
    h264_video: Path,
    bboxes: object,
    color: tuple[int, int, int],
    thickness: int,
    preview: bool,
    dry_run: bool,
    audio_start_seconds: float | None,
    audio_duration_seconds: float | None,
    start_frame: int | None = None,
    end_frame: int | None = None,
    show_stabilize_crop: bool = False,
    stabilize_margin: float = 1.35,
    stabilize_smooth_seconds: float = DEFAULT_SMOOTH_SECONDS,
    stabilize_crop_color: tuple[int, int, int] = (0, 0, 255),
) -> None:
    started_at = time.monotonic()
    if preview:
        vt.ensure_preview_available()
    cap = vt.cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {src}")

    fps = cap.get(vt.cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(vt.cv2.CAP_PROP_FRAME_COUNT))
    src_w = int(cap.get(vt.cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(vt.cv2.CAP_PROP_FRAME_HEIGHT))
    range_start = 0 if start_frame is None else min(max(0, start_frame), max(0, frame_count - 1))
    range_end = max(0, frame_count - 1) if end_frame is None else min(max(0, end_frame), max(0, frame_count - 1))
    if range_end < range_start:
        range_start, range_end = range_end, range_start
    output_frame_count = max(0, range_end - range_start + 1)
    stabilize_crop_bboxes = None
    stabilize_smooth_radius = None
    if show_stabilize_crop:
        _centers, _crop_sizes, stabilize_crop_bboxes, stabilize_smooth_radius = compute_stabilize_crop_geometry(
            bboxes,
            fps,
            src_w,
            src_h,
            stabilize_margin,
            stabilize_smooth_seconds,
        )
    if preview:
        vt.open_preview_window("video_track draw_box", src_w, src_h)

    writer = vt.cv2.VideoWriter(
        str(mp4v_video),
        vt.cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (src_w, src_h),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not write {mp4v_video}")
    h264_process = open_h264_writer(
        src,
        h264_video,
        fps,
        src_w,
        src_h,
        dry_run,
        audio_start_seconds,
        audio_duration_seconds,
    )

    if range_start:
        cap.set(vt.cv2.CAP_PROP_POS_FRAMES, range_start)

    vt.logger.info(
        "draw_box start: frames %s..%s (%s frames), %.3f fps, %sx%s",
        range_start,
        range_end,
        output_frame_count,
        fps,
        src_w,
        src_h,
    )
    if show_stabilize_crop:
        vt.logger.info(
            "draw_box stabilize crop: margin=%.3f smooth=%.3fs radius=%s frames",
            stabilize_margin,
            stabilize_smooth_seconds,
            stabilize_smooth_radius,
        )
    index = range_start
    written = 0
    try:
        with vt.tqdm_progress(total=output_frame_count, desc="draw_box", unit="frame") as progress:
            while index <= range_end:
                ok, frame = cap.read()
                if not ok:
                    break
                if index < len(bboxes):
                    x0, y0, x1, y1 = bboxes[index]
                    pt1 = (int(round(x0)), int(round(y0)))
                    pt2 = (int(round(x1)), int(round(y1)))
                    vt.cv2.rectangle(frame, pt1, pt2, color, thickness)
                if stabilize_crop_bboxes is not None and index < len(stabilize_crop_bboxes):
                    x0, y0, x1, y1 = stabilize_crop_bboxes[index]
                    pt1 = (int(round(x0)), int(round(y0)))
                    pt2 = (int(round(x1)), int(round(y1)))
                    vt.cv2.rectangle(frame, pt1, pt2, stabilize_crop_color, thickness)
                writer.write(frame)
                if h264_process is not None and h264_process.stdin is not None:
                    h264_process.stdin.write(frame.tobytes())
                written += 1
                if preview:
                    style = vt.preview_style(frame)
                    pct = ((written - 1) / max(1, output_frame_count - 1) * 100.0) if output_frame_count else 100.0
                    status_text = vt.detect_preview_status(
                        index,
                        fps,
                        pct,
                        output_frame_count,
                        range_start,
                        range_end,
                    )
                    vt.draw_preview_text(
                        frame,
                        f"{status_text}\nq/esc: kill",
                        style.margin,
                        style.line_y,
                        style.text_scale,
                        style.text_thickness,
                        (255, 255, 255),
                    )
                    vt.cv2.imshow("video_track draw_box", frame)
                    key = vt.cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        raise KeyboardInterrupt("preview interrupted")
                index += 1
                progress.update(1)
    finally:
        cap.release()
        writer.release()
        close_h264_writer(h264_process)
        if preview:
            vt.cv2.destroyWindow("video_track draw_box")
    vt.logger.info("draw_box done: %s frames in %.1fs", written, time.monotonic() - started_at)


def draw_box(args: argparse.Namespace) -> int:
    vt.load_video_modules()

    src = Path(args.input)
    track_json = Path(args.track_json)
    mp4v_dst = Path(args.mp4v_output) if args.mp4v_output is not None else default_boxed_mp4v_path(src)
    h264_dst = Path(args.h264_output) if args.h264_output is not None else default_boxed_h264_path(src)
    if args.thickness <= 0:
        raise ValueError("--thickness must be positive")
    if args.stabilize_margin <= 0:
        raise ValueError("--stabilize-margin must be positive")
    if args.stabilize_smooth_seconds < 0:
        raise ValueError("--stabilize-smooth-seconds must be non-negative")

    range_args = [args.start, args.end, args.duration]
    range_arg_count = sum(value is not None for value in range_args)
    if range_arg_count > 2:
        raise SystemExit("specify at most two of --start, --end, --duration")

    track_data = vt.read_track_data(track_json)
    bboxes = vt.xywh_list_to_xyxy_array(track_data["frames"])
    info = vt.load_video_info(src)
    frame_range = vt.video_time.resolve_frame_cut_range(
        start=args.start,
        end=args.end,
        duration=args.duration,
        fps=info.fps,
        frame_count=info.frame_count,
    )
    range_start, range_end = frame_range.start, frame_range.end
    range_start = min(max(0, range_start), max(0, info.frame_count - 1))
    range_end = min(max(0, range_end), max(0, info.frame_count - 1))
    audio_start_seconds = range_start / info.fps
    audio_duration_seconds = (range_end - range_start + 1) / info.fps
    vt.logger.info(
        "draw_box range: frames %s..%s (%s)",
        range_start,
        range_end,
        vt.frame_range_label(range_start, range_end, info.fps),
    )

    vt.logger.info("draw_box mp4v no-audio video: %s", mp4v_dst)
    draw_video(
        src,
        mp4v_dst,
        h264_dst,
        bboxes,
        args.color,
        args.thickness,
        args.preview_gui,
        args.dry_run,
        audio_start_seconds,
        audio_duration_seconds,
        range_start,
        range_end,
        args.show_stabilize_crop,
        args.stabilize_margin,
        args.stabilize_smooth_seconds,
        args.stabilize_crop_color,
    )
    return 0
