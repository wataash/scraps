# Repository Guidelines

This directory contains many independent Python utility scripts. Keep global instructions here short and avoid adding rules that only apply to one script family.

## Script-Specific Guides

Before answering questions about a script or editing it, check for a matching guide in this directory and follow it for that script only. Do not apply a script-specific guide to unrelated scripts.

- For `video_track.py`, `video_track_draw_box.py`, `video_track_stabilize.py`, or related helpers such as `lib_/video_time.py`, read `video_track.md`.
- For `video_extract_score.py`, read `video_extract_score.md`.
- For `images_to_a4_pdf.py`, read `images_to_a4_pdf.md`.
- When adding a new independent script family, prefer adding a separate `<script-family>.md` guide instead of expanding this global file with project-specific rules.

## General Instructions

- Do not revert unrelated local changes.
- Use `rg` for searching files and text.
- Preserve existing CLI behavior unless the requested change explicitly alters it.
- Keep reusable helpers in `lib_/` only when they are broadly useful across scripts.
