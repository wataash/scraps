#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
vscode_keybindings_annotate.py -h
vscode_keybindings_annotate.py dump-titles > titles.json
vscode_keybindings_annotate.py annotate --titles titles.json keybindings_default.jsonc > annotated.jsonc
vscode_keybindings_annotate.py annotate --titles titles.json -i keybindings_default.jsonc
'''[1:]

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import time
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


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser('dump-titles', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='extract command-id -> title from a running VS Code at runtime (via the DevTools protocol); JSON to stdout')
    subparser.set_defaults(func=dump_titles)
    subparser.add_argument('--code', default='code', help='VS Code executable to launch')
    subparser.add_argument('--port', type=int, default=9222, help='Chromium remote-debugging port')
    subparser.add_argument('--extensions_dir', type=Path, default=Path.home() / '.vscode/extensions',
                           help='load installed extensions so their command titles are captured too (settings are not touched)')
    subparser.add_argument('-n', '--dry_run', action='store_true', help='print the VS Code launch command instead of running it')

    subparser = subparsers.add_parser('annotate', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='append "// Category: Title" comments to a VS Code default-keybindings JSON dump')
    subparser.set_defaults(func=annotate)
    subparser.add_argument('keybindings_json', type=Path, help='file saved from "Preferences: Open Default Keyboard Shortcuts (JSON)"')
    subparser.add_argument('--titles', type=Path, required=True, help='command-id -> title JSON produced by "dump-titles"')
    subparser.add_argument('-i', '--in_place', action='store_true', help='rewrite keybindings_json instead of printing to stdout')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return args.func(args)


# -----------------------------------------------------------------------------
# Runtime extraction via the Chrome DevTools Protocol
#
# VS Code's command titles live in the renderer's MenuRegistry / editor-action registries, which are bundled
# and not reachable from the DevTools console. So we attach over CDP, set *non-pausing* conditional breakpoints
# (e.g. `globalThis.__mr=this,false`) on registry methods to stash the singletons on globalThis, reload the
# window so registrations re-run, then read them from global scope. This reflects exactly what the keybindings
# editor shows, including runtime-computed titles (e.g. "Show Search").

class CDP:
    def __init__(self, ws_url: str):
        import websocket  # pip install websocket-client
        self.ws = websocket.create_connection(ws_url, max_size=None, suppress_origin=True)
        self._id = 0

    def call(self, method: str, **params) -> dict:
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:  # skip interleaved CDP events until our response arrives
            msg = json.loads(self.ws.recv())
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise RuntimeError(f'{method}: {msg["error"]}')
                return msg.get('result', {})

    def evaluate(self, expr: str):
        r = self.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'):
            raise RuntimeError(f'eval failed: {r["exceptionDetails"].get("text")}')
        return r['result'].get('value')

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# JS run in global scope after the registry instances are stashed: build {command id -> "Category: Title"}.
# Precedence mirrors KeybindingsEditorModel.getCommandsLabels: editor-action labels are the base, CommandPalette
# menu-item titles override them, and MenuRegistry command titles override those (the three sources, last wins).
_EXTRACT_JS = r'''
(() => {
  const out = {};
  const catTitle = c => {
    const t = typeof c.title === 'string' ? c.title : c.title.value;
    const cat = c.category ? (typeof c.category === 'string' ? c.category : c.category.value) : '';
    return (cat && !t.startsWith(cat + ': ')) ? cat + ': ' + t : t;
  };
  const ea = globalThis.__ea;
  if (ea && ea.editorActions) for (const a of ea.editorActions) {
    if (a && a.id && a.label) out[a.id] = a.label;
  }
  const m = globalThis.__mr;
  if (m && m._menuItems) for (const [menuId, list] of m._menuItems) {
    if (!menuId || menuId.id !== 'CommandPalette') continue;
    for (const item of list) {
      const c = item && item.command;
      if (c && c.id && c.title) out[c.id] = catTitle(c);
    }
  }
  if (m && m.getCommands) for (const [id, c] of m.getCommands()) {
    if (c && c.title) out[id] = catTitle(c);
  }
  return JSON.stringify(out);
})()
'''

# anchors into the (minified, but method-name-preserving) workbench bundle. Each is a non-pausing conditional
# breakpoint that stashes `this` (a module-scoped registry singleton) onto globalThis so it can be read later.
_BREAKPOINTS = [
    # MenuRegistry.addCommand(a){ return this._commands.set(a.id,a), ... }  -> commands + CommandPalette menu items
    ('addCommand(a){return this._commands.set(a.id,a)', 'globalThis.__mr=this,false'),
    # EditorContributionRegistry.getEditorActions(){ return this.editorActions }  -> editor-action labels
    ('getEditorActions(){return this.editorActions}', 'globalThis.__ea=this,false'),
]


def _bundle_breakpoints(code_exe: str) -> tuple[str, list[tuple[int, int, str]]]:
    """Locate each anchor in the workbench bundle; return (url_regex, [(line, column, condition), ...])."""
    app_out = Path(code_exe).resolve()
    candidates = [
        Path('/usr/share/code/resources/app/out'),
        app_out.parent.parent / 'resources' / 'app' / 'out',
    ]
    bundle = next((c / 'vs/workbench/workbench.desktop.main.js' for c in candidates
                   if (c / 'vs/workbench/workbench.desktop.main.js').exists()), None)
    if not bundle:
        raise RuntimeError('could not locate workbench.desktop.main.js; pass --code pointing at the VS Code binary')
    text = bundle.read_text(encoding='utf-8', errors='replace')
    bps = []
    for anchor, condition in _BREAKPOINTS:
        off = text.find(anchor)
        if off == -1 or text.find(anchor, off + 1) != -1:
            raise RuntimeError(f'anchor not found uniquely in {bundle.name} (VS Code version changed?): {anchor!r}')
        off = text.find('return', off)  # break at the `return` statement, where `this` is bound
        line = text.count('\n', 0, off)
        col = off - (text.rfind('\n', 0, off) + 1)
        logger.info(f'breakpoint at workbench.desktop.main.js:{line}:{col} ({condition})')
        bps.append((line, col, condition))
    return r'workbench\.desktop\.main\.js', bps


def dump_titles(args: argparse.Namespace) -> int:
    import urllib.request

    user_data = Path(tempfile.mkdtemp(prefix='vscode_dump_titles_'))
    cmd = [args.code, f'--remote-debugging-port={args.port}', f'--user-data-dir={user_data}',
           '--no-first-run', '--disable-workspace-trust', '--skip-release-notes']
    if args.extensions_dir and args.extensions_dir.exists():
        cmd.append(f'--extensions-dir={args.extensions_dir}')
    if args.dry_run:
        print(' '.join(cmd))
        return 0

    url_regex, bps = _bundle_breakpoints(args.code)
    logger.info(f'launching: {" ".join(cmd)}')
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp = None
    try:
        ws_url = None  # poll the CDP target list until the workbench renderer page appears
        for _ in range(60):
            try:
                targets = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{args.port}/json/list', timeout=1).read())
                ws_url = next((t['webSocketDebuggerUrl'] for t in targets
                               if t.get('type') == 'page' and 'workbench.html' in t.get('url', '')), None)
            except Exception:
                ws_url = None
            if ws_url:
                break
            time.sleep(1)
        if not ws_url:
            raise RuntimeError('workbench renderer target not found; is the VS Code window opening?')
        logger.info('connected to renderer; arming breakpoints and reloading')

        cdp = CDP(ws_url)
        cdp.call('Debugger.enable')
        cdp.call('Runtime.enable')
        cdp.call('Page.enable')
        for line, col, condition in bps:
            cdp.call('Debugger.setBreakpointByUrl', urlRegex=url_regex, lineNumber=line, columnNumber=col,
                     condition=condition)
        cdp.call('Page.reload', ignoreCache=False)

        size = 0  # wait until registrations have run and the command count stabilises
        for _ in range(60):
            time.sleep(1)
            try:
                cur = cdp.evaluate('globalThis.__mr ? globalThis.__mr.getCommands().size : 0') or 0
            except Exception:
                cur = 0
            if cur and cur == size:
                break
            size = cur
        if not size:
            raise RuntimeError('MenuRegistry was never captured (breakpoint condition did not fire)')

        data = cdp.evaluate(_EXTRACT_JS)
        titles = json.loads(data) if data else {}
        logger.info(f'extracted {len(titles)} command titles')
        print(json.dumps(titles, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    finally:
        if cdp:
            cdp.close()
        proc.terminate()
        subprocess.run(['pkill', '-f', str(user_data)], stderr=subprocess.DEVNULL)
        shutil.rmtree(user_data, ignore_errors=True)


# -----------------------------------------------------------------------------
# keybindings JSON annotation

def skip_string(s: str, i: int) -> int:
    """s[i] is a '"'; return index just past the closing quote (handles escapes)."""
    i += 1
    while i < len(s):
        if s[i] == '\\':
            i += 2
            continue
        if s[i] == '"':
            return i + 1
        i += 1
    return i


def count_braces_outside_strings(line: str) -> int:
    depth = 0
    i = 0
    while i < len(line):
        if line[i] == '"':
            i = skip_string(line, i)
            continue
        if line.startswith('//', i):
            break
        if line[i] == '{':
            depth += 1
        elif line[i] == '}':
            depth -= 1
        i += 1
    return depth


RE_COMMAND = re.compile(r'"command":\s*"([^"]+)"')
# trailing "// Here are other available commands:" block lists keybinding-less commands as "// - <id>"
# (allow an already-appended "// title" so re-runs are idempotent)
RE_AVAILABLE = re.compile(r'^(// - (\S+))(?:\s*//.*)?\s*$')
# a previously-appended "// title" after an entry's closing "}" / "}," (for idempotent re-runs)
RE_PRIOR_NOTE = re.compile(r'(\}\s*,?)\s*//.*$')


def annotate(args: argparse.Namespace) -> int:
    lines = args.keybindings_json.read_text(encoding='utf-8').splitlines()
    wanted_ids = {m.group(1).lstrip('-') for line in lines if (m := RE_COMMAND.search(line))}
    wanted_ids |= {m.group(2) for line in lines if (m := RE_AVAILABLE.match(line))}
    labels = {k: v for k, v in json.loads(args.titles.read_text()).items() if v}
    logger.info(f'loaded {len(labels)} titles from {args.titles} ({len(labels.keys() & wanted_ids)} of {len(wanted_ids)} wanted)')

    out: list[str] = []
    depth = 0
    in_array = False
    cur_command: str | None = None
    unmapped: set[str] = set()
    n_entries = n_annotated = 0
    for line in lines:
        if not in_array:
            if m := RE_AVAILABLE.match(line):  # "// - <id>" in the trailing available-commands block
                n_entries += 1
                if label := labels.get(m.group(2)):
                    line = f'{m.group(1)} // {label}'
                    n_annotated += 1
                else:
                    unmapped.add(m.group(2))
            out.append(line)
            if line.strip() == '[':
                in_array = True
            continue
        if depth == 0 and line.strip() == ']':
            in_array = False
            out.append(line)
            continue
        if m := RE_COMMAND.search(line):
            cur_command = m.group(1).lstrip('-')
        start_depth = depth
        d = count_braces_outside_strings(line)
        depth = start_depth + d
        # an entry closes on this line if depth returns to 0 either from inside a multi-line entry
        # (start_depth > 0) or from a single-line entry whose braces balance out on one line (d == 0 with a '{')
        if depth == 0 and (start_depth > 0 or '{' in line):  # this line closes an entry
            n_entries += 1
            line = RE_PRIOR_NOTE.sub(r'\1', line.rstrip())  # drop any annotation from a previous run
            label = labels.get(cur_command or '')
            if label:
                line = f'{line.rstrip()} // {label}'
                n_annotated += 1
            elif cur_command:
                unmapped.add(cur_command)
            cur_command = None
        out.append(line)

    if unmapped:
        logger.warning(f'{len(unmapped)} commands without a title (left unannotated): {" ".join(sorted(unmapped))}')
    logger.info(f'annotated {n_annotated}/{n_entries} entries')

    text = '\n'.join(out) + '\n'
    if args.in_place:
        args.keybindings_json.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
