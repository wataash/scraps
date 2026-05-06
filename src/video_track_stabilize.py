from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

import video_track as vt


DEFAULT_SMOOTH_SECONDS = 8.0


def default_stabilized_mp4v_path(src: Path) -> Path:
    return src.with_name(f"{src.stem}.stabilized.mp4v.mkv")


def default_stabilized_h264_path(src: Path) -> Path:
    return src.with_name(f"{src.stem}.stabilized.h264.mkv")


def build_h264_writer_command(src: Path, dst: Path, fps: float, width: int, height: int) -> list[str]:
    return [
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


def open_h264_writer(
    src: Path,
    dst: Path,
    fps: float,
    width: int,
    height: int,
    dry_run: bool,
) -> subprocess.Popen[bytes] | None:
    cmd = build_h264_writer_command(src, dst, fps, width, height)
    cmd_text = vt.shell_join(cmd)
    if dry_run:
        print(cmd_text)
        return None
    vt.logger.info(cmd_text)
    vt.logger.info("stabilize h264 video: %s", dst)
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def close_h264_writer(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return
    if process.stdin is not None:
        process.stdin.close()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg h264 stabilize writer failed with exit code {return_code}")


def crop_with_soft_pad(frame: vt.np.ndarray, center: vt.np.ndarray, crop_w: int, crop_h: int) -> vt.np.ndarray:
    h, w = frame.shape[:2]
    cx, cy = center
    x0 = int(round(cx - crop_w / 2))
    y0 = int(round(cy - crop_h / 2))
    x1 = x0 + crop_w
    y1 = y0 + crop_h

    base = vt.cv2.resize(frame, (crop_w, crop_h), interpolation=vt.cv2.INTER_LINEAR)
    base = vt.cv2.GaussianBlur(base, (0, 0), 18)
    base = vt.cv2.addWeighted(base, 0.82, vt.np.zeros_like(base), 0.18, 0)

    src_x0 = max(0, x0)
    src_y0 = max(0, y0)
    src_x1 = min(w, x1)
    src_y1 = min(h, y1)
    dst_x0 = src_x0 - x0
    dst_y0 = src_y0 - y0
    dst_x1 = dst_x0 + (src_x1 - src_x0)
    dst_y1 = dst_y0 + (src_y1 - src_y0)

    if src_x1 > src_x0 and src_y1 > src_y0:
        base[dst_y0:dst_y1, dst_x0:dst_x1] = frame[src_y0:src_y1, src_x0:src_x1]

    return base


def make_background(frame: vt.np.ndarray, out_w: int, out_h: int) -> vt.np.ndarray:
    bg = vt.cv2.resize(frame, (out_w, out_h), interpolation=vt.cv2.INTER_LINEAR)
    bg = vt.cv2.GaussianBlur(bg, (0, 0), 24)
    return vt.cv2.addWeighted(bg, 0.78, vt.np.zeros_like(bg), 0.22, 0)


def stabilize_bbox_to_output(
    bbox: vt.np.ndarray,
    center: vt.np.ndarray,
    crop_w: int,
    crop_h: int,
    out_w: int,
    out_h: int,
) -> tuple[tuple[int, int], tuple[int, int]]:
    crop_x0 = center[0] - crop_w / 2
    crop_y0 = center[1] - crop_h / 2
    scale_x = out_w / crop_w
    scale_y = out_h / crop_h
    x0 = int(round((bbox[0] - crop_x0) * scale_x))
    y0 = int(round((bbox[1] - crop_y0) * scale_y))
    x1 = int(round((bbox[2] - crop_x0) * scale_x))
    y1 = int(round((bbox[3] - crop_y0) * scale_y))
    return (x0, y0), (x1, y1)


def stabilize_crop_sizes(
    bboxes: vt.np.ndarray,
    margin: float,
    aspect: float,
    radius: int,
) -> vt.np.ndarray:
    bbox_w = bboxes[:, 2] - bboxes[:, 0]
    bbox_h = bboxes[:, 3] - bboxes[:, 1]
    target_w = vt.np.maximum(bbox_w * margin, bbox_h * margin * aspect)
    target_h = target_w / aspect
    too_short = target_h < bbox_h * margin
    target_h[too_short] = bbox_h[too_short] * margin
    target_w[too_short] = target_h[too_short] * aspect
    sizes = vt.np.column_stack([target_w, target_h])
    sizes = vt.smooth(sizes, radius=radius)
    sizes[:, 0] = vt.np.maximum(2, vt.np.round(sizes[:, 0]))
    sizes[:, 1] = vt.np.maximum(2, vt.np.round(sizes[:, 1]))
    return sizes.astype(vt.np.int32)


def stabilize_smooth_radius(fps: float, smooth_seconds: float) -> int:
    if smooth_seconds < 0:
        raise ValueError("--smooth-seconds must be non-negative")
    radius = round(fps * smooth_seconds)
    if smooth_seconds == DEFAULT_SMOOTH_SECONDS:
        radius = max(5, radius)
    return max(0, radius)


def compute_stabilize_crop_geometry(
    bboxes: vt.np.ndarray,
    fps: float,
    frame_width: int,
    frame_height: int,
    margin: float,
    smooth_seconds: float = DEFAULT_SMOOTH_SECONDS,
) -> tuple[vt.np.ndarray, vt.np.ndarray, vt.np.ndarray, int]:
    aspect = frame_width / frame_height
    smooth_radius = stabilize_smooth_radius(fps, smooth_seconds)
    centers = vt.np.column_stack([(bboxes[:, 0] + bboxes[:, 2]) / 2, (bboxes[:, 1] + bboxes[:, 3]) / 2])
    centers = vt.smooth(centers, radius=smooth_radius)
    crop_sizes = stabilize_crop_sizes(bboxes, margin, aspect, smooth_radius)
    half_sizes = crop_sizes.astype(vt.np.float64) / 2
    crop_bboxes = vt.np.column_stack(
        [
            centers[:, 0] - half_sizes[:, 0],
            centers[:, 1] - half_sizes[:, 1],
            centers[:, 0] + half_sizes[:, 0],
            centers[:, 1] + half_sizes[:, 1],
        ]
    )
    return centers, crop_sizes, crop_bboxes, smooth_radius


def stabilize_video(
    src: Path,
    mp4v_video: Path,
    h264_video: Path,
    bboxes: vt.np.ndarray,
    margin: float,
    smooth_seconds: float,
    preview: bool,
    dry_run: bool,
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
    if preview:
        vt.open_preview_window("video_track stabilize", src_w, src_h)

    out_w, out_h = src_w, src_h
    centers, crop_sizes, _crop_bboxes, smooth_radius = compute_stabilize_crop_geometry(
        bboxes,
        fps,
        out_w,
        out_h,
        margin,
        smooth_seconds,
    )
    writer = vt.cv2.VideoWriter(
        str(mp4v_video),
        vt.cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (out_w, out_h),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not write {mp4v_video}")
    h264_process = open_h264_writer(src, h264_video, fps, out_w, out_h, dry_run)

    vt.logger.info(
        "stabilize start: %s frames, %.3f fps, %sx%s -> %sx%s, smooth=%.3fs radius=%s frames, dynamic_crop=%sx%s..%sx%s",
        frame_count,
        fps,
        src_w,
        src_h,
        out_w,
        out_h,
        smooth_seconds,
        smooth_radius,
        int(vt.np.min(crop_sizes[:, 0])),
        int(vt.np.min(crop_sizes[:, 1])),
        int(vt.np.max(crop_sizes[:, 0])),
        int(vt.np.max(crop_sizes[:, 1])),
    )
    index = 0
    try:
        with vt.tqdm_progress(total=frame_count, desc="stabilize", unit="frame") as progress:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                crop_w = int(crop_sizes[index, 0])
                crop_h = int(crop_sizes[index, 1])
                crop = crop_with_soft_pad(frame, centers[index], crop_w, crop_h)
                foreground = vt.cv2.resize(crop, (out_w, out_h), interpolation=vt.cv2.INTER_CUBIC)
                background = make_background(frame, out_w, out_h)
                frame_out = vt.cv2.addWeighted(foreground, 0.94, background, 0.06, 0)
                writer.write(frame_out)
                if h264_process is not None and h264_process.stdin is not None:
                    h264_process.stdin.write(frame_out.tobytes())
                if preview:
                    preview_frame = frame_out.copy()
                    style = vt.preview_style(preview_frame)
                    if index < len(bboxes):
                        pt1, pt2 = stabilize_bbox_to_output(bboxes[index], centers[index], crop_w, crop_h, out_w, out_h)
                        vt.cv2.rectangle(preview_frame, pt1, pt2, (0, 255, 0), style.box_thickness)
                    pct = (index / max(1, frame_count - 1) * 100.0) if frame_count else 100.0
                    status_text = vt.detect_preview_status(
                        index,
                        fps,
                        pct,
                        frame_count,
                        0,
                        max(0, frame_count - 1),
                    )
                    vt.draw_preview_text(
                        preview_frame,
                        f"{status_text}\nq/esc: kill",
                        style.margin,
                        style.line_y,
                        style.text_scale,
                        style.text_thickness,
                        (255, 255, 255),
                    )
                    vt.cv2.imshow("video_track stabilize", preview_frame)
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
            vt.cv2.destroyWindow("video_track stabilize")
    vt.logger.info("stabilize done: %s frames in %.1fs", index, time.monotonic() - started_at)


def stabilize(args: argparse.Namespace) -> int:
    vt.load_video_modules()

    src = Path(args.input)
    track_json = Path(args.track_json)
    mp4v_dst = Path(args.mp4v_output) if args.mp4v_output is not None else default_stabilized_mp4v_path(src)
    h264_dst = Path(args.h264_output) if args.h264_output is not None else default_stabilized_h264_path(src)
    if args.margin <= 0:
        raise ValueError("--margin must be positive")
    if args.smooth_seconds < 0:
        raise ValueError("--smooth-seconds must be non-negative")

    track_data = vt.read_track_data(track_json)
    bboxes = vt.xywh_list_to_xyxy_array(track_data["frames"])

    vt.logger.info("stabilize mp4v no-audio video: %s", mp4v_dst)
    stabilize_video(src, mp4v_dst, h264_dst, bboxes, args.margin, args.smooth_seconds, args.preview_gui, args.dry_run)
    return 0
