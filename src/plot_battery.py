#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
python plot_battery.py -h

# build a degradation history by snapshotting sysfs periodically (cron / systemd timer / loop)
python plot_battery.py collect battery.jsonl
python plot_battery.py collect battery.jsonl -n
while true; do python plot_battery.py collect battery.jsonl; sleep 3600; done

# plot the collected degradation history (capacity health %, full-charge Wh, cycle count)
python plot_battery.py plot battery.jsonl battery.png

# plot upower's already-recorded charge history (state-of-charge %, rate, voltage)
python plot_battery.py charge battery_charge.png
python plot_battery.py charge battery_charge.png --dat /var/lib/upower/history-charge-MODEL-x-y.dat
'''[1:]

import argparse
import glob
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


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


POWER_SUPPLY_DIR = Path('/sys/class/power_supply')
UPOWER_HISTORY_DIR = Path('/var/lib/upower')

# sysfs attributes captured per snapshot. numeric ones are stored as int (raw sysfs
# units: energy_* in uWh, charge_* in uAh, voltage_* in uV); the rest as str.
NUMERIC_ATTRS = [
    'capacity',
    'cycle_count',
    'energy_full', 'energy_full_design', 'energy_now',
    'charge_full', 'charge_full_design', 'charge_now',
    'voltage_now', 'voltage_min_design',
    'power_now',
]
STRING_ATTRS = ['status', 'capacity_level']


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-q', '--quiet', action='count', default=0,
                        help='decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error')
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser(
        'collect',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='append one battery sysfs snapshot to a JSONL log (run periodically to build a degradation history)',
    )
    subparser.set_defaults(func=collect)
    subparser.add_argument('log', type=Path,
                           help='output JSONL log file path (appended)')
    subparser.add_argument('--bat', default=None,
                           help='power_supply battery name (default: first BAT* under /sys/class/power_supply)')
    subparser.add_argument('-n', '--dry_run', action='store_true',
                           help='print the shell-equivalent commands and exit without writing')

    subparser = subparsers.add_parser(
        'plot',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='render the collected degradation history (capacity health %%, full-charge Wh, cycle count) to a PNG',
    )
    subparser.set_defaults(func=plot)
    subparser.add_argument('log', type=Path,
                           help='input JSONL log file path (from `collect`)')
    subparser.add_argument('out', type=Path,
                           help='output PNG path')

    subparser = subparsers.add_parser(
        'charge',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help="render upower's already-recorded charge history (state-of-charge %%, rate, voltage) to a PNG",
    )
    subparser.set_defaults(func=charge)
    subparser.add_argument('out', type=Path,
                           help='output PNG path')
    subparser.add_argument('--dat', type=Path, default=None,
                           help='path to a upower history-charge-*.dat file\n'
                                '(default: auto-detect the laptop battery under /var/lib/upower)')

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f'{args=}')
    return args.func(args)


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def find_battery(name: str | None) -> Path:
    if name is not None:
        p = POWER_SUPPLY_DIR / name
        if not p.is_dir():
            raise SystemExit(f'no such power_supply: {p}')
        return p
    cands = sorted(POWER_SUPPLY_DIR.glob('BAT*'))
    if not cands:
        raise SystemExit(f'no BAT* found under {POWER_SUPPLY_DIR}')
    return cands[0]


def read_attr(bat_dir: Path, attr: str) -> str | None:
    try:
        return (bat_dir / attr).read_text().strip()
    except OSError:
        return None


def snapshot(bat_dir: Path) -> dict:
    snap: dict = {'timestamp': datetime.now().astimezone().isoformat(timespec='seconds')}
    for attr in NUMERIC_ATTRS:
        raw = read_attr(bat_dir, attr)
        if raw is not None:
            try:
                snap[attr] = int(raw)
            except ValueError:
                pass
    for attr in STRING_ATTRS:
        raw = read_attr(bat_dir, attr)
        if raw is not None:
            snap[attr] = raw
    return snap


def collect(args: argparse.Namespace) -> int:
    bat_dir = find_battery(args.bat)
    log_path: Path = args.log.expanduser()

    if args.dry_run:
        print(f"# battery: {bat_dir}")
        for attr in NUMERIC_ATTRS + STRING_ATTRS:
            print(f"cat {bat_dir / attr}")
        print(f"# ... assembled into one JSON object and appended to {log_path}")
        return 0

    snap = snapshot(bat_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a') as f:
        f.write(json.dumps(snap) + '\n')
    logger.info(f'appended snapshot to {log_path}: {snap}')
    return 0


# ---------------------------------------------------------------------------
# plot (degradation history from collected JSONL)
# ---------------------------------------------------------------------------


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open() as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning(f'{path}:{i}: skipping unparseable line')
    rows.sort(key=lambda r: r.get('timestamp', ''))
    return rows


def _series(rows: list[dict], key: str) -> tuple[list[datetime], list[float]]:
    xs: list[datetime] = []
    ys: list[float] = []
    for r in rows:
        if key in r and 'timestamp' in r:
            xs.append(datetime.fromisoformat(r['timestamp']))
            ys.append(float(r[key]))
    return xs, ys


def _full_design_pair(rows: list[dict]) -> tuple[str, str, float]:
    '''pick energy_* (uWh->Wh) or charge_* (uAh->Ah) depending on what was collected.'''
    if any('energy_full' in r for r in rows):
        return 'energy_full', 'energy_full_design', 1e6  # uWh -> Wh
    return 'charge_full', 'charge_full_design', 1e6      # uAh -> Ah


def plot(args: argparse.Namespace) -> int:
    log_path: Path = args.log.expanduser()
    rows = load_jsonl(log_path)
    if not rows:
        raise SystemExit(f'no snapshots in {log_path} (run `collect` first)')
    logger.info(f'loaded {len(rows)} snapshots ({rows[0].get("timestamp")} .. {rows[-1].get("timestamp")})')

    full_key, design_key, unit = _full_design_pair(rows)
    is_energy = full_key.startswith('energy')
    cap_unit = 'Wh' if is_energy else 'Ah'

    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)

    # Panel 1: capacity health % = full / design * 100
    hx: list[datetime] = []
    hy: list[float] = []
    for r in rows:
        if full_key in r and design_key in r and r[design_key]:
            hx.append(datetime.fromisoformat(r['timestamp']))
            hy.append(r[full_key] / r[design_key] * 100)
    if hx:
        axes[0].plot(hx, hy, marker='.', linewidth=1, color='#4c78a8')
    axes[0].set_ylabel('health %')
    axes[0].set_title(f'Capacity health ({full_key} / {design_key} * 100)')
    axes[0].grid(True, alpha=0.3)

    # Panel 2: full-charge capacity (and design as reference)
    fx, fy = _series(rows, full_key)
    if fx:
        axes[1].plot(fx, [v / unit for v in fy], marker='.', linewidth=1, label=full_key, color='#54a24b')
    dx, dy = _series(rows, design_key)
    if dy:
        axes[1].axhline(dy[-1] / unit, color='grey', linestyle=':', linewidth=0.8, label=f'{design_key} (={dy[-1] / unit:.2f} {cap_unit})')
    axes[1].set_ylabel(cap_unit)
    axes[1].set_title('Full-charge capacity')
    axes[1].legend(loc='upper right', fontsize=8)
    axes[1].grid(True, alpha=0.3)

    # Panel 3: charge cycles
    cx, cy = _series(rows, 'cycle_count')
    if cx:
        axes[2].plot(cx, cy, marker='.', linewidth=1, color='#e45756')
    axes[2].set_ylabel('cycles')
    axes[2].set_title('Charge cycle count')
    axes[2].grid(True, alpha=0.3)

    _finalize(fig, axes[-1], args.out.expanduser())
    return 0


# ---------------------------------------------------------------------------
# charge (upower history-*.dat)
# ---------------------------------------------------------------------------


def detect_battery_dat(name_hint: str | None) -> Path:
    '''find the laptop battery's upower history-charge-*.dat.

    Prefer a file matching the sysfs model_name; otherwise pick the largest one
    (mice/keyboards have tiny histories compared with the laptop battery).'''
    dats = glob.glob(str(UPOWER_HISTORY_DIR / 'history-charge-*.dat'))
    if not dats:
        raise SystemExit(f'no history-charge-*.dat under {UPOWER_HISTORY_DIR} (is upower installed/running?)')
    if name_hint:
        for d in dats:
            if name_hint in os.path.basename(d):
                return Path(d)
    return Path(max(dats, key=lambda d: os.path.getsize(d)))


def parse_upower_dat(path: Path) -> tuple[list[datetime], list[float]]:
    '''upower .dat lines: "<unixtime>\\t<value>\\t<state>". value 0 with state
    "unknown" is a sentinel emitted on resume; drop it.'''
    xs: list[datetime] = []
    ys: list[float] = []
    try:
        text = path.read_text()
    except OSError as e:
        raise SystemExit(f'cannot read {path}: {e}')
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            t = int(parts[0])
            v = float(parts[1])
        except ValueError:
            continue
        state = parts[2] if len(parts) >= 3 else ''
        if v == 0.0 and state == 'unknown':
            continue
        xs.append(datetime.fromtimestamp(t).astimezone())
        ys.append(v)
    return xs, ys


def charge(args: argparse.Namespace) -> int:
    dat = args.dat.expanduser() if args.dat else None
    if dat is None:
        model = read_attr(find_battery(None), 'model_name')
        dat = detect_battery_dat(model)
    logger.info(f'reading upower history from {dat}')

    base = os.path.basename(str(dat))
    suffix = base[len('history-charge-'):] if base.startswith('history-charge-') else None

    def sibling(kind: str) -> Path | None:
        if suffix is None:
            return None
        p = dat.parent / f'history-{kind}-{suffix}'
        return p if p.exists() else None

    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)

    cx, cy = parse_upower_dat(dat)
    if not cx:
        raise SystemExit(f'no usable data points in {dat}')
    logger.info(f'{len(cx)} charge points ({cx[0]} .. {cx[-1]})')
    axes[0].plot(cx, cy, linewidth=1, color='#4c78a8')
    axes[0].set_ylabel('charge %')
    axes[0].set_ylim(0, 100)
    axes[0].set_title(f'State of charge ({base})')
    axes[0].grid(True, alpha=0.3)

    rate = sibling('rate')
    if rate:
        rx, ry = parse_upower_dat(rate)
        if rx:
            axes[1].plot(rx, ry, linewidth=1, color='#f58518')
    axes[1].set_ylabel('rate (W)')
    axes[1].set_title('Charge/discharge rate' + ('' if rate else ' (no history-rate file)'))
    axes[1].grid(True, alpha=0.3)

    volt = sibling('voltage')
    if volt:
        vx, vy = parse_upower_dat(volt)
        if vx:
            axes[2].plot(vx, vy, linewidth=1, color='#54a24b')
    axes[2].set_ylabel('voltage (V)')
    axes[2].set_title('Voltage' + ('' if volt else ' (no history-voltage file)'))
    axes[2].grid(True, alpha=0.3)

    _finalize(fig, axes[-1], args.out.expanduser())
    return 0


# ---------------------------------------------------------------------------


def _finalize(fig, last_ax, out_path: Path) -> None:
    last_ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    last_ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M'))
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    logger.info(f'wrote {out_path}')


if __name__ == '__main__':
    raise SystemExit(main())
