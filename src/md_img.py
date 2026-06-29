#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
md_img.py mv -h
md_img.py mv input.md ../dst/renamed.md
md_img.py mv -n input.md ../dst/renamed.md
md_img.py normalize_image_names -h
md_img.py normalize_image_names input.md
md_img.py normalize_image_names -n input.md
md_img.py img_mv -h
md_img.py img_mv old.png new.png
md_img.py img_mv -n --md_scan_dir ~/d old.png new.png
'''[1:]

import argparse
import logging
import os
import pathlib
import re
import shlex
import subprocess
import sys

# Directories never worth scanning for Markdown references (used by the
# os.walk fallback; the git path already excludes anything .gitignore'd).
PRUNE_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.mypy_cache', '.pnpm'}


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


# Matches a Markdown inline image: ![alt](link) or ![alt](link "title").
# Captures the alt text and the link (path/URL) portion.
IMAGE_RE = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<link>[^)\s]+)(?P<title>\s+"[^"]*")?\)')

URL_RE = re.compile(r'^(?:[a-z][a-z0-9+.\-]*:|//|#)', re.IGNORECASE)


def is_local_link(link: str) -> bool:
    """True if link refers to a local file (not a URL / anchor / data URI)."""
    return not URL_RE.match(link)


def resolve_link(base_dir: pathlib.Path, link: str) -> pathlib.Path:
    """Resolve a local image link relative to the dir of its containing file."""
    p = pathlib.Path(link)
    if not p.is_absolute():
        p = base_dir / p
    # resolve() normalizes .. and symlinks; strict=False so a missing file still resolves.
    return p.resolve()


def find_image_links(text: str) -> list[str]:
    return [m.group('link') for m in IMAGE_RE.finditer(text)]


def git_root(path: pathlib.Path) -> pathlib.Path | None:
    try:
        out = subprocess.check_output(
            ['git', '-C', str(path.parent), 'rev-parse', '--show-toplevel'],
            text=True, stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return pathlib.Path(out.strip())


def sed_escape_pattern(s: str) -> str:
    # BRE special chars + the '#' delimiter we use in s#...#...# (not '/', it is
    # not special and we never use it as the delimiter).
    return re.sub(r'([\\.\[\]*^$#])', r'\\\1', s)


def sed_subst(old: str, new: str) -> str:
    """A `s#OLD#NEW#g` sed expression replacing literal `old` with literal `new`."""
    return f's#{sed_escape_pattern(old)}#{sed_escape_repl(new)}#g'


def tilde_form(p: pathlib.Path, home: pathlib.Path) -> str | None:
    """`~/...` form of an absolute path under home, else None."""
    try:
        return '~/' + str(p.relative_to(home))
    except ValueError:
        return None


def sed_escape_repl(s: str) -> str:
    # In the replacement, escape backslash, the delimiter, and '&' (whole-match ref).
    return re.sub(r'([\\&#])', r'\\\1', s)


def run_cmd(cmd: str, dry_run: bool) -> None:
    if dry_run:
        print(cmd)
        return
    logger.info(cmd)
    subprocess.run(cmd, shell=True, check=True)


def mv(args: argparse.Namespace) -> int:
    src: pathlib.Path = args.src
    dst: pathlib.Path = args.dst

    if not src.is_file():
        logger.error(f'source markdown not found: {src}')
        return 1
    if dst.suffix.lower() != '.md':
        logger.warning(f'destination does not end with .md: {dst}')
    if not dst.parent.is_dir():
        logger.error(f'destination directory does not exist: {dst.parent}')
        return 1
    if dst.exists():
        logger.error(f'destination already exists: {dst}')
        return 1

    text = src.read_text(encoding='utf-8')
    links = find_image_links(text)
    plan, errors = build_image_rename_plan(links, src, dst.stem, dst.parent)
    if errors:
        logger.error('missing image file(s):\n' + '\n'.join(errors))
        return 1

    plan_errs = validate_image_plan(plan, src.resolve(), args.root)
    if plan_errs:
        logger.error('\n'.join(plan_errs))
        return 1

    # Path strings to rewrite in other files: both absolute and ~ forms.
    home = pathlib.Path.home()
    abs_old, abs_new = str(src.resolve()), str(dst.parent.resolve() / dst.name)
    path_repls: list[tuple[str, str]] = [(abs_old, abs_new)]
    tilde_old, tilde_new = tilde_form(pathlib.Path(abs_old), home), tilde_form(pathlib.Path(abs_new), home)
    if tilde_old is not None and tilde_new is not None:
        path_repls.append((tilde_old, tilde_new))

    # 4. rewrite references to the markdown's path across the repo (abs + ~ forms)
    path_cmds = build_path_rewrite_cmds(args.root, src.resolve(), path_repls) if args.path_rewrite else []

    cmds: list[str] = []
    # 1. move the markdown file
    cmds.append(f'mv {shlex.quote(str(src))} {shlex.quote(str(dst))}')
    # 2. move each referenced image, 3. rewrite the image links inside the moved markdown
    cmds += image_cmds(plan, dst)
    cmds += path_cmds

    logger.info(f'{src} -> {dst} ({len(plan)} image(s), {len(path_cmds)} path-ref file(s))')

    for cmd in cmds:
        run_cmd(cmd, args.dry_run)

    return 0


def normalize_image_names(args: argparse.Namespace) -> int:
    md: pathlib.Path = args.file

    if not md.is_file():
        logger.error(f'markdown not found: {md}')
        return 1

    text = md.read_text(encoding='utf-8')
    links = find_image_links(text)
    # Rename each local image to "<md stem>.<image name>" in place; idempotent
    # (images already carrying that prefix are left alone).
    plan, errors = build_image_rename_plan(links, md, md.stem, md.parent, skip_prefixed=True)
    if errors:
        logger.error('missing image file(s):\n' + '\n'.join(errors))
        return 1

    if not plan:
        logger.info(f'{md}: nothing to rename (no un-normalized local images)')
        return 0

    plan_errs = validate_image_plan(plan, md.resolve(), args.root)
    if plan_errs:
        logger.error('\n'.join(plan_errs))
        return 1

    logger.info(f'{md}: normalize {len(plan)} image(s)')
    for cmd in image_cmds(plan, md):
        run_cmd(cmd, args.dry_run)

    return 0


def img_mv(args: argparse.Namespace) -> int:
    src: pathlib.Path = args.src
    dst: pathlib.Path = args.dst

    if not src.is_file():
        logger.error(f'source image not found: {src}')
        return 1
    if not dst.parent.is_dir():
        logger.error(f'destination directory does not exist: {dst.parent}')
        return 1
    if dst.exists():
        logger.error(f'destination already exists: {dst}')
        return 1

    refs = find_image_link_refs(args.md_scan_dir, src.resolve())

    cmds: list[str] = []
    # 1. move the image
    cmds.append(f'mv {shlex.quote(str(src))} {shlex.quote(str(dst))}')
    # 2. rewrite the link in each referencing markdown
    for md, old_link in refs:
        new_link = new_image_link(old_link, md.parent, dst)
        cmds.append(
            f'sed -i -e {shlex.quote(sed_subst(f"]({old_link})", f"]({new_link})"))} {shlex.quote(str(md))}')

    logger.info(f'{src} -> {dst} ({len(refs)} reference(s))')
    for cmd in cmds:
        run_cmd(cmd, args.dry_run)

    return 0


def new_image_link(old_link: str, md_dir: pathlib.Path, dst: pathlib.Path) -> str:
    """New link string for dst, preserving the old link's style: an absolute old
    link stays absolute; a relative one becomes relative to the markdown's dir."""
    if pathlib.Path(old_link).is_absolute():
        return str(dst.resolve())
    return os.path.relpath(dst.resolve(), md_dir.resolve())


def find_image_link_refs(
    scan_dir: pathlib.Path,
    target_img: pathlib.Path,
) -> list[tuple[pathlib.Path, str]]:
    """Return (md_file, link) for each distinct local image link under scan_dir
    that resolves to target_img. Links are resolved relative to each md's dir."""
    refs: list[tuple[pathlib.Path, str]] = []
    for md in sorted(iter_md_files(scan_dir)):
        try:
            content = md.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        seen: set[str] = set()
        for m in IMAGE_RE.finditer(content):
            link = m.group('link')
            if not is_local_link(link) or link in seen:
                continue
            if resolve_link(md.parent, link) == target_img:
                seen.add(link)
                refs.append((md, link))
    return refs


# plan item: (old_link, new_link, src_img_path, dst_img_path)
Plan = list[tuple[str, str, pathlib.Path, pathlib.Path]]


def build_image_rename_plan(
    links: list[str],
    src_md: pathlib.Path,
    target_stem: str,
    target_dir: pathlib.Path,
    skip_prefixed: bool = False,
) -> tuple[Plan, list[str]]:
    """Plan renaming each local image link to "<target_stem>.<image name>" in
    target_dir. Image links are resolved relative to src_md's directory.
    Returns (plan, errors); errors lists missing image files.
    With skip_prefixed, images whose name already starts with "<target_stem>."
    are left as-is (keeps the operation idempotent)."""
    plan: Plan = []
    seen_links: set[str] = set()
    errors: list[str] = []
    for link in links:
        if not is_local_link(link):
            logger.debug(f'skip non-local link: {link}')
            continue
        if link in seen_links:
            continue
        seen_links.add(link)
        src_img = resolve_link(src_md.parent, link)
        if not src_img.is_file():
            errors.append(f'  image referenced in {src_md} not found: {link} -> {src_img}')
            continue
        if skip_prefixed and src_img.name.startswith(f'{target_stem}.'):
            logger.debug(f'skip already-normalized image: {link}')
            continue
        new_link = f'{target_stem}.{src_img.name}'
        dst_img = target_dir / new_link
        plan.append((link, new_link, src_img, dst_img))
    return plan, errors


def validate_image_plan(plan: Plan, src_md: pathlib.Path, root: pathlib.Path) -> list[str]:
    """Return error message block(s) for an image-rename plan (empty = ok):
    destination collisions and images referenced by other markdown files."""
    errs: list[str] = []
    collisions = [str(dst_img) for _, _, _, dst_img in plan if dst_img.exists()]
    if collisions:
        errs.append('destination image already exists:\n  ' + '\n  '.join(collisions))
    src_img_set = {src_img for _, _, src_img, _ in plan}
    if src_img_set:
        conflicts = find_other_references(root, src_md, src_img_set)
        if conflicts:
            errs.append(
                'image(s) are also referenced by other file(s); refusing to rename:\n  '
                + '\n  '.join(conflicts)
            )
    return errs


def image_cmds(plan: Plan, md: pathlib.Path) -> list[str]:
    """Shell commands to move each image and rewrite its link inside md."""
    cmds: list[str] = []
    for _, _, src_img, dst_img in plan:
        cmds.append(f'mv {shlex.quote(str(src_img))} {shlex.quote(str(dst_img))}')
    for old_link, new_link, _, _ in plan:
        cmds.append(f'sed -i -e {shlex.quote(sed_subst(f"]({old_link})", f"]({new_link})"))} {shlex.quote(str(md))}')
    return cmds


def build_path_rewrite_cmds(
    root: pathlib.Path,
    src_md: pathlib.Path,
    path_repls: list[tuple[str, str]],
) -> list[str]:
    """For each file under root that contains an old path string, build a sed
    command applying every matching replacement. The moved file itself (src_md)
    is skipped since its old self-path is gone."""
    cmds: list[str] = []
    for f in iter_repo_files(root):
        if f.resolve() == src_md:
            continue
        try:
            content = f.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable
        exprs = [sed_subst(old, new) for old, new in path_repls if old in content]
        if not exprs:
            continue
        args_str = ' '.join(f'-e {shlex.quote(e)}' for e in exprs)
        cmds.append(f'sed -i {args_str} {shlex.quote(str(f))}')
    return cmds


def iter_repo_files(root: pathlib.Path) -> list[pathlib.Path]:
    """List files under root. Prefer `git ls-files` (honors .gitignore, so
    node_modules etc. are skipped); fall back to os.walk with pruned dirs."""
    try:
        out = subprocess.check_output(
            ['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
            text=True, stderr=subprocess.DEVNULL,
        )
        return [root / p for p in out.split('\0') if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    result: list[pathlib.Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        for fn in filenames:
            result.append(pathlib.Path(dirpath) / fn)
    return result


def iter_md_files(root: pathlib.Path) -> list[pathlib.Path]:
    return [f for f in iter_repo_files(root) if f.suffix == '.md']


def find_other_references(
    root: pathlib.Path,
    src_md: pathlib.Path,
    src_imgs: set[pathlib.Path],
) -> list[str]:
    """Return 'file:line: link' for image links in *other* .md files under root
    that resolve to one of src_imgs."""
    conflicts: list[str] = []
    for md in sorted(iter_md_files(root)):
        if md.resolve() == src_md:
            continue
        try:
            content = md.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(content.splitlines(), start=1):
            for m in IMAGE_RE.finditer(line):
                link = m.group('link')
                if not is_local_link(link):
                    continue
                if resolve_link(md.parent, link) in src_imgs:
                    conflicts.append(f'{md}:{i}: {link}')
    return conflicts


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        epilog=epilog,
        description='Move/rename a Markdown file together with its embedded local images.',
    )
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    sp = subparsers.add_parser(
        'mv',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        description=(
            'Move SRC markdown to DST, moving each embedded local image\n'
            'alongside it renamed to "<DST stem>.<image name>", and rewriting\n'
            'the image links in the moved markdown.'
        ),
    )
    sp.set_defaults(func=mv)
    sp.add_argument('-n', '--dry_run', action='store_true', help='print the commands instead of running them')
    sp.add_argument('--no-path-rewrite', dest='path_rewrite', action='store_false',
                    help='do not rewrite references to SRC\'s path in other files under --root')
    sp.add_argument('--root', type=pathlib.Path, default=None,
                    help='root dir to scan for other references (default: git root of SRC, else SRC dir)')
    sp.add_argument('src', type=pathlib.Path, help='source markdown file')
    sp.add_argument('dst', type=pathlib.Path, help='destination markdown file')

    sp = subparsers.add_parser(
        'normalize_image_names',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        description=(
            'Rename each embedded local image of FILE in place to\n'
            '"<FILE stem>.<image name>" and rewrite the image links in FILE.\n'
            'Idempotent: images already carrying that prefix are left alone.'
        ),
    )
    sp.set_defaults(func=normalize_image_names)
    sp.add_argument('-n', '--dry_run', action='store_true', help='print the commands instead of running them')
    sp.add_argument('--root', type=pathlib.Path, default=None,
                    help='root dir to scan for other references (default: git root of FILE, else FILE dir)')
    sp.add_argument('file', type=pathlib.Path, help='markdown file to normalize in place')

    sp = subparsers.add_parser(
        'img_mv',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        description=(
            'Move/rename an image file SRC to DST, and rewrite every local image\n'
            'link under --md_scan_dir that resolves to SRC so it points to DST.\n'
            'A relative link is rewritten relative to its markdown\'s dir; an\n'
            'absolute link is rewritten as the absolute path of DST.'
        ),
    )
    sp.set_defaults(func=img_mv)
    sp.add_argument('-n', '--dry_run', action='store_true', help='print the commands instead of running them')
    sp.add_argument('--md_scan_dir', type=pathlib.Path, default=None,
                    help='root dir to scan for markdown referencing SRC (default: git root of SRC, else SRC dir)')
    sp.add_argument('src', type=pathlib.Path, help='source image file')
    sp.add_argument('dst', type=pathlib.Path, help='destination image file')

    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')

    base: pathlib.Path = getattr(args, 'src', None) or getattr(args, 'file', None)
    # 'root' (mv/normalize) and 'md_scan_dir' (img_mv) both default to base's git root.
    for attr in ('root', 'md_scan_dir'):
        if getattr(args, attr, None) is None and hasattr(args, attr):
            setattr(args, attr, git_root(base) or base.resolve().parent)
            logger.debug(f'reference scan {attr}: {getattr(args, attr)}')

    return args.func(args)


# ---------------------------------------------------------------------------
# tests (pytest)
# ---------------------------------------------------------------------------


def _ns(**kw) -> argparse.Namespace:
    kw.setdefault('dry_run', False)
    return argparse.Namespace(**kw)


def _write(p: pathlib.Path, text: str) -> pathlib.Path:
    p.write_text(text, encoding='utf-8')
    return p


def test_is_local_link():
    assert is_local_link('image.png')
    assert is_local_link('./sub/a.png')
    assert is_local_link('/abs/a.png')
    assert not is_local_link('https://x/y.png')
    assert not is_local_link('http://x/y.png')
    assert not is_local_link('data:image/png;base64,AAAA')
    assert not is_local_link('#anchor')
    assert not is_local_link('//host/x.png')


def test_find_image_links():
    text = '![a](image.png) text ![b](https://x/y.png) ![c](sub/z.png "title")'
    assert find_image_links(text) == ['image.png', 'https://x/y.png', 'sub/z.png']


def test_resolve_link(tmp_path):
    base = tmp_path / 'd'
    base.mkdir()
    assert resolve_link(base, 'a.png') == (base / 'a.png').resolve()
    assert resolve_link(base, '../a.png') == (tmp_path / 'a.png').resolve()
    abs_p = tmp_path / 'x.png'
    assert resolve_link(base, str(abs_p)) == abs_p.resolve()


def test_sed_escape_and_subst():
    assert sed_escape_pattern('a.b*c') == r'a\.b\*c'
    assert sed_escape_pattern('x#y') == r'x\#y'
    assert sed_subst('](image.png)', '](n.image.png)') == r's#\](image\.png)#](n.image.png)#g'
    assert sed_subst('a', 'b&c') == r's#a#b\&c#g'  # '&' escaped in replacement


def test_tilde_form(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    assert tilde_form(home / 'notes' / 'a.md', home) == '~/notes/a.md'
    assert tilde_form(tmp_path / 'other' / 'a.md', home) is None


def test_build_image_rename_plan(tmp_path):
    (tmp_path / 'image.png').write_bytes(b'png')
    md = _write(tmp_path / 'note.md', '![a](image.png) ![b](https://x/y.png)')
    plan, errors = build_image_rename_plan(find_image_links(md.read_text()), md, 'note', tmp_path)
    assert errors == []
    assert plan == [('image.png', 'note.image.png',
                     (tmp_path / 'image.png').resolve(), tmp_path / 'note.image.png')]


def test_build_image_rename_plan_missing(tmp_path):
    md = _write(tmp_path / 'note.md', '![a](nope.png)')
    plan, errors = build_image_rename_plan(find_image_links(md.read_text()), md, 'note', tmp_path)
    assert plan == []
    assert len(errors) == 1


def test_build_image_rename_plan_skip_prefixed(tmp_path):
    (tmp_path / 'note.image.png').write_bytes(b'png')
    md = _write(tmp_path / 'note.md', '![a](note.image.png)')
    plan, errors = build_image_rename_plan(
        find_image_links(md.read_text()), md, 'note', tmp_path, skip_prefixed=True)
    assert plan == [] and errors == []


def test_mv_moves_md_and_images(tmp_path):
    (tmp_path / 'image.png').write_bytes(b'png')
    md = _write(tmp_path / 'src.md', '![a](image.png)\n![b](https://x/y.png)\n')
    dst_dir = tmp_path / 'dst'
    dst_dir.mkdir()
    dst = dst_dir / 'renamed.md'
    assert mv(_ns(src=md, dst=dst, root=tmp_path, path_rewrite=True)) == 0
    assert not md.exists() and dst.exists()
    assert (dst_dir / 'renamed.image.png').exists()
    assert not (tmp_path / 'image.png').exists()
    content = dst.read_text()
    assert '![a](renamed.image.png)' in content
    assert '![b](https://x/y.png)' in content  # url left untouched


def test_mv_refuses_existing_dst(tmp_path):
    md = _write(tmp_path / 'src.md', 'hi')
    dst = _write(tmp_path / 'dst.md', 'exists')
    assert mv(_ns(src=md, dst=dst, root=tmp_path, path_rewrite=True)) == 1
    assert md.exists()


def test_mv_rewrites_path_references(tmp_path):
    (tmp_path / 'image.png').write_bytes(b'png')
    md = _write(tmp_path / 'src.md', '![a](image.png)')
    index = _write(tmp_path / 'index.md', f'see {md.resolve()} for details')
    dst = tmp_path / 'renamed.md'
    assert mv(_ns(src=md, dst=dst, root=tmp_path, path_rewrite=True)) == 0
    assert str(dst.resolve()) in index.read_text()
    assert str(md.resolve()) not in index.read_text()


def test_mv_no_path_rewrite(tmp_path):
    (tmp_path / 'image.png').write_bytes(b'png')
    md = _write(tmp_path / 'src.md', '![a](image.png)')
    index = _write(tmp_path / 'index.md', f'see {md.resolve()} for details')
    dst = tmp_path / 'renamed.md'
    assert mv(_ns(src=md, dst=dst, root=tmp_path, path_rewrite=False)) == 0
    assert str(md.resolve()) in index.read_text()  # left untouched


def test_normalize_renames_in_place(tmp_path):
    (tmp_path / 'image.png').write_bytes(b'png')
    (tmp_path / 'image-1.png').write_bytes(b'png')
    md = _write(tmp_path / 'note.md', '![a](image.png)\n![b](image-1.png)\n')
    assert normalize_image_names(_ns(file=md, root=tmp_path)) == 0
    assert (tmp_path / 'note.image.png').exists()
    assert (tmp_path / 'note.image-1.png').exists()
    assert not (tmp_path / 'image.png').exists()
    content = md.read_text()
    assert '![a](note.image.png)' in content
    assert '![b](note.image-1.png)' in content


def test_normalize_idempotent(tmp_path):
    (tmp_path / 'image.png').write_bytes(b'png')
    md = _write(tmp_path / 'note.md', '![a](image.png)\n')
    assert normalize_image_names(_ns(file=md, root=tmp_path)) == 0
    before = md.read_text()
    assert normalize_image_names(_ns(file=md, root=tmp_path)) == 0
    assert md.read_text() == before
    assert (tmp_path / 'note.image.png').exists()
    assert not (tmp_path / 'note.note.image.png').exists()


def test_normalize_refuses_shared_image(tmp_path):
    (tmp_path / 'image.png').write_bytes(b'png')
    md = _write(tmp_path / 'note.md', '![a](image.png)')
    _write(tmp_path / 'other.md', '![a](image.png)')  # references the same file
    assert normalize_image_names(_ns(file=md, root=tmp_path)) == 1
    assert (tmp_path / 'image.png').exists()
    assert not (tmp_path / 'note.image.png').exists()


def test_normalize_missing_image(tmp_path):
    md = _write(tmp_path / 'note.md', '![a](nope.png)')
    assert normalize_image_names(_ns(file=md, root=tmp_path)) == 1


def test_new_image_link(tmp_path):
    dst = tmp_path / 'sub' / 'new.png'
    assert new_image_link('old.png', tmp_path, dst) == 'sub/new.png'
    assert new_image_link('x/old.png', tmp_path / 'sub', dst) == 'new.png'
    assert new_image_link(str(tmp_path / 'old.png'), tmp_path, dst) == str(dst.resolve())


def test_find_image_link_refs(tmp_path):
    img = tmp_path / 'image.png'
    img.write_bytes(b'png')
    a = _write(tmp_path / 'a.md', '![x](image.png) ![x](image.png) ![y](https://x/y.png)')
    sub = tmp_path / 'sub'
    sub.mkdir()
    b = _write(sub / 'b.md', '![z](../image.png)')
    _write(tmp_path / 'c.md', '![w](other.png)')  # resolves elsewhere
    refs = find_image_link_refs(tmp_path, img.resolve())
    assert refs == [(a, 'image.png'), (b, '../image.png')]  # deduped, sorted by md path


def test_img_mv_renames_and_rewrites(tmp_path):
    img = tmp_path / 'old.png'
    img.write_bytes(b'png')
    md = _write(tmp_path / 'note.md', '![a](old.png)\n![b](https://x/y.png)\n')
    dst = tmp_path / 'new.png'
    assert img_mv(_ns(src=img, dst=dst, md_scan_dir=tmp_path)) == 0
    assert dst.exists() and not img.exists()
    content = md.read_text()
    assert '![a](new.png)' in content
    assert '![b](https://x/y.png)' in content


def test_img_mv_rewrites_relative_across_dirs(tmp_path):
    img = tmp_path / 'old.png'
    img.write_bytes(b'png')
    sub = tmp_path / 'sub'
    sub.mkdir()
    md = _write(sub / 'note.md', '![a](../old.png)')
    dst = tmp_path / 'new.png'
    assert img_mv(_ns(src=img, dst=dst, md_scan_dir=tmp_path)) == 0
    assert '![a](../new.png)' in md.read_text()


def test_img_mv_refuses_existing_dst(tmp_path):
    img = tmp_path / 'old.png'
    img.write_bytes(b'png')
    (tmp_path / 'new.png').write_bytes(b'png')
    assert img_mv(_ns(src=img, dst=tmp_path / 'new.png', md_scan_dir=tmp_path)) == 1
    assert img.exists()


def test_img_mv_missing_src(tmp_path):
    assert img_mv(_ns(src=tmp_path / 'nope.png', dst=tmp_path / 'new.png', md_scan_dir=tmp_path)) == 1


if __name__ == '__main__':
    raise SystemExit(main())
