# Repository Guidelines

This directory contains many independent Python utility scripts. Keep global instructions here short and avoid adding rules that only apply to one script family.

## Script-Specific Guides

Before answering questions about a script or editing it, check for a matching guide in this directory and follow it for that script only. Do not apply a script-specific guide to unrelated scripts.

For example: `video_extract_score.py`, read `video_extract_score.md`.

## General Instructions

- Do not revert unrelated local changes.
- Use `rg` for searching files and text.
- Preserve existing CLI behavior unless the requested change explicitly alters it.
- Keep reusable helpers in `lib_/` only when they are broadly useful across scripts.
- Make new scripts executable with `chmod +x`.
