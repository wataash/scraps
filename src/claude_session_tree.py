#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
python claude_session_tree.py -h
python claude_session_tree.py show -h

# show all projects (default)
python claude_session_tree.py show

# show one project
python claude_session_tree.py show ~/path/to/project

# show one session's lineage (ancestors + descendants) by session-id prefix
python claude_session_tree.py show 01e93746
'''[1:]

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path


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


CLAUDE_PROJECTS = Path.home() / '.claude' / 'projects'


# ANSI color codes. Populated by setup_colors() / blanked when --color=never.
C = {
    'reset': '', 'dim': '', 'bold': '',
    'sid': '', 'title': '', 'uuid': '',
    'prompt': '', 'sep': '', 'tree': '', 'dir': '',
}


def setup_colors(enabled: bool) -> None:
    if not enabled:
        for k in C:
            C[k] = ''
        return
    C.update(
        reset='\033[0m', dim='\033[2m', bold='\033[1m',
        sid='\033[96m',        # bright cyan: session leaf id
        title='\033[33m',      # yellow: aiTitle
        uuid='\033[2;37m',     # dim: ~<sid> for chain heads
        prompt='\033[97m',     # bright white: prompt text
        sep='\033[2;37m',      # dim: ' | '
        tree='\033[2m',        # dim: bullets / indent
        dir='\033[1;36m',      # bold cyan: directory header
    )


def encode_path(real: Path) -> str:
    s = str(real.resolve())
    return s.replace('/', '-').replace('.', '-')


def resolve_project_dir(arg: str) -> Path:
    p = Path(arg).expanduser()
    if p.is_dir() and p.parent.resolve() == CLAUDE_PROJECTS.resolve():
        return p
    if p.is_dir():
        candidate = CLAUDE_PROJECTS / encode_path(p)
        if candidate.is_dir():
            return candidate
    direct = CLAUDE_PROJECTS / arg
    if direct.is_dir():
        return direct
    raise SystemExit(f'project dir not found: {arg}')


def extract_prompt_text(msg: dict) -> str | None:
    """Return the displayable text of a user prompt, or None to skip."""
    if msg.get('type') != 'user':
        return None
    if msg.get('isSidechain') or msg.get('isMeta'):
        return None
    inner = msg.get('message') or {}
    if inner.get('role') != 'user':
        return None
    content = inner.get('content')
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'tool_result':
                return None
            if block.get('type') == 'text':
                parts.append(block.get('text', ''))
        text = '\n'.join(parts)
    else:
        return None
    text = text.strip()
    if not text:
        return None
    skip_prefixes = (
        '<command-name>', '<local-command-stdout>', '<local-command-stderr>',
        '<local-command-caveat>', 'Caveat:', '<system-reminder>',
        'This session is being continued from a previous conversation',
        '[Request interrupted',
    )
    if text.startswith(skip_prefixes):
        return None
    return text


def load_sessions(project_dir: Path):
    """Return (nodes, children, sessions)."""
    nodes: dict[str, dict] = {}
    sessions: dict[str, dict] = {}
    session_prompts: dict[str, list[str]] = defaultdict(list)
    edge_parent: dict[str, str | None] = {}

    for jsonl in sorted(project_dir.glob('*.jsonl')):
        session_id = jsonl.stem
        sessions[session_id] = {
            'title': '', 'leaf': None, 'file': jsonl,
            'mtime': jsonl.stat().st_mtime,
        }
        try:
            with jsonl.open(encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get('type') == 'ai-title':
                        title = rec.get('aiTitle') or ''
                        if title:
                            sessions[session_id]['title'] = title
                        continue
                    uuid = rec.get('uuid')
                    if not uuid:
                        continue
                    if uuid not in edge_parent:
                        edge_parent[uuid] = rec.get('parentUuid')
                    text = extract_prompt_text(rec)
                    if text is None:
                        continue
                    if uuid not in nodes:
                        nodes[uuid] = {
                            'parent': None,
                            'text': text,
                            'first_ts': rec.get('timestamp', ''),
                        }
                    session_prompts[session_id].append(uuid)
        except OSError as exc:
            logger.warning(f'cannot read {jsonl}: {exc}')

    # Resolve each prompt's effective parent: walk up through assistant/tool
    # messages until we hit another prompt or run out of ancestors.
    for uuid in nodes:
        cur = edge_parent.get(uuid)
        seen: set[str] = set()
        while cur is not None and cur in edge_parent and cur not in nodes:
            if cur in seen:
                cur = None
                break
            seen.add(cur)
            cur = edge_parent.get(cur)
        if cur is not None and cur not in nodes:
            cur = None
        nodes[uuid]['parent'] = cur

    for sid, prompts in session_prompts.items():
        if prompts:
            sessions[sid]['leaf'] = prompts[-1]

    # uuid -> session ids whose jsonl contains this prompt (oldest first).
    uuid_to_sessions: dict[str, list[str]] = defaultdict(list)
    for sid in sorted(session_prompts, key=lambda s: sessions[s]['mtime']):
        for uuid in session_prompts[sid]:
            if sid not in uuid_to_sessions[uuid]:
                uuid_to_sessions[uuid].append(sid)
    for uuid, sids in uuid_to_sessions.items():
        nodes[uuid]['sessions'] = sids

    children: dict[str | None, list[str]] = defaultdict(list)
    seen_edges: set[tuple[str | None, str]] = set()
    for sid in sorted(session_prompts, key=lambda s: sessions[s]['mtime']):
        for uuid in session_prompts[sid]:
            parent_key = nodes[uuid]['parent']
            key = (parent_key, uuid)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            children[parent_key].append(uuid)

    return nodes, children, sessions


def truncate(s: str, n: int) -> str:
    s = ' '.join(s.split())
    if len(s) <= n:
        return s
    return s[: n - 1] + '…'


SID_PREFIX_RE = re.compile(r'^[0-9a-fA-F]{4,}(-[0-9a-fA-F]+)*$')


def looks_like_sid(arg: str) -> bool:
    if Path(arg).expanduser().is_dir():
        return False
    if (CLAUDE_PROJECTS / arg).is_dir():
        return False
    return bool(SID_PREFIX_RE.match(arg))


def find_session_by_prefix(prefix: str) -> tuple[Path, str]:
    if not CLAUDE_PROJECTS.is_dir():
        raise SystemExit(f'no projects dir: {CLAUDE_PROJECTS}')
    matches: list[tuple[Path, str]] = []
    for project_dir in CLAUDE_PROJECTS.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl in project_dir.glob('*.jsonl'):
            if jsonl.stem.startswith(prefix):
                matches.append((project_dir, jsonl.stem))
    if not matches:
        raise SystemExit(f'no session matches prefix: {prefix}')
    if len(matches) > 1:
        listing = '\n'.join(f'  {p}/{sid}.jsonl' for p, sid in matches)
        raise SystemExit(f'ambiguous prefix {prefix!r}; matches:\n{listing}')
    return matches[0]


def filter_lineage(nodes, children, anchor_uuid):
    """Restrict to ancestors and descendants of `anchor_uuid`."""
    keep: set[str] = set()
    cur = anchor_uuid
    while cur is not None:
        keep.add(cur)
        cur = nodes[cur]['parent']
    stack = [anchor_uuid]
    while stack:
        u = stack.pop()
        for c in children.get(u, []):
            if c not in keep:
                keep.add(c)
                stack.append(c)
    new_nodes = {u: nodes[u] for u in keep}
    new_children: dict[str | None, list[str]] = defaultdict(list)
    for parent, kids in children.items():
        if parent is not None and parent not in keep:
            continue
        for k in kids:
            if k in keep:
                new_children[parent].append(k)
    return new_nodes, new_children


def print_tree(nodes, children, sessions, project_dir, max_prompt, orig_children=None):
    leaf_to_sessions: dict[str, list[str]] = defaultdict(list)
    for sid, info in sessions.items():
        if info['leaf'] is not None:
            leaf_to_sessions[info['leaf']].append(sid)

    real_path = project_dir.name.replace('-', '/')
    print(f"{C['dir']}directory: {real_path}{C['reset']}  {C['dim']}({project_dir}){C['reset']}")

    # Preserve original fork points when filtering, so ancestor labels that
    # had siblings in the unfiltered tree remain visible as their own line.
    fork_uuids: set[str] = set()
    if orig_children is not None:
        for parent, kids in orig_children.items():
            if parent is not None and len(kids) > 1:
                fork_uuids.add(parent)

    def walk(uuid: str, depth: int) -> None:
        chain: list[str] = []
        cur: str | None = uuid
        while cur is not None:
            chain.append(cur)
            kids = children.get(cur, [])
            if len(kids) != 1:
                break
            if cur in leaf_to_sessions:
                break
            if cur in fork_uuids:
                break
            cur = kids[0]

        head = chain[0]
        labels: list[str] = []
        for node_uuid in chain:
            for sid in leaf_to_sessions.get(node_uuid, []):
                title = sessions[sid]['title']
                sid_col = f"{C['sid']}{sid}{C['reset']}"
                if title:
                    labels.append(f"{sid_col} {C['title']}({title}){C['reset']}")
                else:
                    labels.append(sid_col)

        sep = f"{C['sep']} | {C['reset']}"
        prompts = sep.join(
            f"{C['prompt']}{truncate(nodes[u]['text'], max_prompt)}{C['reset']}"
            for u in chain
        )
        indent = f"{C['tree']}{'  ' * depth}{C['reset']}"
        prefix = f"{C['tree']}- {C['reset']}"
        if labels:
            label_part = ' '.join(labels) + ' '
        else:
            resume_sids = nodes[head].get('sessions') or []
            if resume_sids:
                label_part = f"{C['uuid']}~{resume_sids[0]}{C['reset']} "
            else:
                label_part = ''
        print(f'{indent}{prefix}{label_part}{prompts}')

        tail = chain[-1]
        for kid in children.get(tail, []):
            walk(kid, depth + 1)

    for root in children.get(None, []):
        walk(root, 0)


def show(args: argparse.Namespace) -> int:
    if args.color == 'always':
        enable_color = True
    elif args.color == 'never':
        enable_color = False
    else:
        enable_color = sys.stdout.isatty()
    setup_colors(enable_color)

    sid_filter: str | None = None
    if args.target is None:
        if not CLAUDE_PROJECTS.is_dir():
            logger.error(f'no projects dir: {CLAUDE_PROJECTS}')
            return 1
        project_dirs = sorted(
            (p for p in CLAUDE_PROJECTS.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
        )
        if not project_dirs:
            logger.error(f'no projects under {CLAUDE_PROJECTS}')
            return 1
    elif looks_like_sid(args.target):
        project_dir, full_sid = find_session_by_prefix(args.target)
        sid_filter = full_sid
        project_dirs = [project_dir]
    else:
        project_dirs = [resolve_project_dir(args.target)]

    first = True
    for project_dir in project_dirs:
        nodes, children, sessions = load_sessions(project_dir)
        if not nodes:
            continue
        orig_children = None
        if sid_filter is not None:
            anchor = sessions.get(sid_filter, {}).get('leaf')
            if anchor is None:
                logger.error(f'session {sid_filter} has no prompts')
                return 1
            orig_children = children
            nodes, children = filter_lineage(nodes, children, anchor)
        if not first:
            print()
        first = False
        print_tree(
            nodes, children, sessions, project_dir, args.max_prompt,
            orig_children=orig_children,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser(
        'show',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='print session history tree',
    )
    subparser.set_defaults(func=show)
    subparser.add_argument(
        'target',
        nargs='?',
        help='project directory (real or encoded) OR session-id prefix '
             '(hex, >=4 chars). default: show all projects',
    )
    subparser.add_argument('--max-prompt', type=int, default=60,
                           help='truncate each prompt to N chars')
    subparser.add_argument('--color', choices=('auto', 'always', 'never'),
                           default='auto', help='colorize output')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
