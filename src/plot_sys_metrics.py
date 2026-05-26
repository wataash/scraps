#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
python plot_sys_metrics.py -h
python plot_sys_metrics.py collect -h
python plot_sys_metrics.py collect sys_metrics.log
python plot_sys_metrics.py plot -h
python plot_sys_metrics.py plot sys_metrics.log sys_metrics.png
python plot_sys_metrics.py plot sys_metrics.log sys_metrics.png --list-ids
python plot_sys_metrics.py plot sys_metrics.log sys_metrics.png --panel loadavg_load1,loadavg_load5 --panel stat_cpu_user,stat_cpu_system,stat_cpu_iowait
'''[1:]

import argparse
import logging
import re
import subprocess
import time
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

warnings.filterwarnings('ignore', category=pd.errors.PerformanceWarning)


class MyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = {
            logging.CRITICAL: '\x1b[31m',
            logging.ERROR: '\x1b[31m',
            logging.WARNING: '\x1b[33m',
            logging.INFO: '\x1b[34m',
            logging.DEBUG: '\x1b[37m',
        }[record.levelno]
        fn = '' if record.funcName == '<module>' else f' {record.funcName}()'
        fmt = f'{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s\x1b[m'
        return logging.Formatter(fmt=fmt, datefmt='%T').format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


SECTION_RE = re.compile(r'^===== (\S+) (\S+) =====$')
PSI_FIELD_RE = re.compile(r'(\w+)=([\d.]+)')

CPU_FIELDS = [
    'user', 'nice', 'system', 'idle', 'iowait',
    'irq', 'softirq', 'steal', 'guest', 'guest_nice',
]
SOFTIRQ_NAMES = [
    'hi', 'timer', 'net_tx', 'net_rx', 'block',
    'irq_poll', 'tasklet', 'sched', 'hrtimer', 'rcu',
]
IOSTAT_DEV_SKIP_PREFIX = ('loop', 'zd')
IOSTAT_RATE_FIELDS = {
    'tps': 'tps_rate',
    'kB_read/s': 'kb_read_rate',
    'kB_wrtn/s': 'kb_wrtn_rate',
    'kB_dscd/s': 'kb_dscd_rate',
}
MPSTAT_CPU_FIELDS = {
    '%usr': 'user',
    '%nice': 'nice',
    '%sys': 'system',
    '%iowait': 'iowait',
    '%irq': 'irq',
    '%soft': 'softirq',
    '%steal': 'steal',
    '%guest': 'guest',
    '%gnice': 'guest_nice',
    '%idle': 'idle',
}
VMSTAT_INSTANT_FIELDS = ('r', 'b', 'swpd', 'free', 'buff', 'cache')
VMSTAT_RATE_FIELDS = ('si', 'so', 'bi', 'bo', 'in', 'cs')
VMSTAT_CPU_FIELDS = {
    'us': 'user',
    'sy': 'system',
    'id': 'idle',
    'wa': 'iowait',
    'st': 'steal',
    'gu': 'guest',
}


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)

    subparser = subparsers.add_parser(
        'collect',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='periodically append /proc and iostat/mpstat/vmstat snapshots to a log',
    )
    subparser.set_defaults(func=collect)
    subparser.add_argument('log', type=Path,
                           help='output log file path (appended)')
    subparser.add_argument('--interval', type=float, default=60,
                           help='seconds between snapshots')
    subparser.add_argument('-n', '--dry_run', action='store_true',
                           help='print shell-equivalent commands for one iteration and exit')

    subparser = subparsers.add_parser(
        'plot',
        formatter_class=ArgumentDefaultsRawTextHelpFormatter,
        help='parse sys_metrics.log and render trends to a PNG',
    )
    subparser.set_defaults(func=plot)
    subparser.add_argument('log', type=Path,
                           help='input log file path')
    subparser.add_argument('out', type=Path,
                           help='output PNG path (ignored with --list-ids)')
    subparser.add_argument('--ncpu', type=int, default=14,
                           help='number of CPUs (for the loadavg reference line and derived_cpu_saturation)')
    subparser.add_argument('--panel', action='append', default=[],
                           help='comma-separated IDs to render as one panel (repeatable). without this, the 4 default panels are rendered.')
    subparser.add_argument('--list-ids', action='store_true', dest='list_ids',
                           help='print available IDs (parsed from the log) and exit')

    args = parser.parse_args()
    logger.debug(f'{args=}')
    return args.func(args)


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------

COLLECT_PROC_FILES = ['/proc/loadavg', '/proc/pressure/cpu', '/proc/stat']
COLLECT_CMDS = [
    ['iostat', '1', '2'],
    ['mpstat', '1', '2'],
    ['vmstat', '1', '2'],
]


def collect(args: argparse.Namespace) -> int:
    log_path: Path = args.log.expanduser()

    if args.dry_run:
        ts = datetime.now().astimezone().isoformat(timespec='seconds')
        for p in COLLECT_PROC_FILES:
            print(f"echo '===== {ts} {p} =====' >> {log_path}")
            print(f"cat {p} >> {log_path}")
        for cmd in COLLECT_CMDS:
            c = cmd[0]
            print(f"echo '===== {ts} {c} =====' >> {log_path}")
            print(f"{' '.join(cmd)} >> {log_path} 2>&1")
        print(f"sleep {args.interval}")
        return 0

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f'appending to {log_path} every {args.interval}s')
    while True:
        ts = datetime.now().astimezone().isoformat(timespec='seconds')
        with log_path.open('a') as f:
            for p in COLLECT_PROC_FILES:
                f.write(f'===== {ts} {p} =====\n')
                f.write(Path(p).read_text())
            for cmd in COLLECT_CMDS:
                c = cmd[0]
                f.write(f'===== {ts} {c} =====\n')
                f.flush()
                logger.info(' '.join(cmd))
                subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=False)
        time.sleep(args.interval)


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


def parse_loadavg(buf: list[str], snap: dict) -> None:
    parts = buf[0].split()
    snap['loadavg_load1'] = float(parts[0])
    snap['loadavg_load5'] = float(parts[1])
    snap['loadavg_load15'] = float(parts[2])
    if '/' in parts[3]:
        r, t = parts[3].split('/', 1)
        snap['loadavg_nr_runnable'] = int(r)
        snap['loadavg_nr_threads'] = int(t)
    snap['loadavg_last_pid_cum'] = int(parts[4])


def parse_pressure(buf: list[str], snap: dict) -> None:
    for line in buf:
        if not line.strip():
            continue
        kind = line.split(None, 1)[0]
        for key, val in PSI_FIELD_RE.findall(line):
            if key.startswith('avg'):
                snap[f'psi_cpu_{kind}_{key[3:]}'] = float(val)
            elif key == 'total':
                snap[f'psi_cpu_{kind}_total_cum'] = int(val)


def parse_stat(buf: list[str], snap: dict) -> None:
    for line in buf:
        parts = line.split()
        if not parts:
            continue
        head = parts[0]
        if head == 'cpu':
            for name, val in zip(CPU_FIELDS, parts[1:]):
                snap[f'stat_cpu_{name}_cum'] = int(val)
        elif head.startswith('cpu') and head != 'cpu':
            for name, val in zip(CPU_FIELDS, parts[1:]):
                snap[f'stat_{head}_{name}_cum'] = int(val)
        elif head == 'ctxt':
            snap['stat_ctxt_cum'] = int(parts[1])
        elif head == 'processes':
            snap['stat_processes_cum'] = int(parts[1])
        elif head == 'procs_running':
            snap['stat_procs_running'] = int(parts[1])
        elif head == 'procs_blocked':
            snap['stat_procs_blocked'] = int(parts[1])
        elif head == 'intr':
            snap['stat_intr_total_cum'] = int(parts[1])
            for i, v in enumerate(parts[2:]):
                snap[f'stat_intr_{i}_cum'] = int(v)
        elif head == 'softirq':
            snap['stat_softirq_total_cum'] = int(parts[1])
            for name, val in zip(SOFTIRQ_NAMES, parts[2:]):
                snap[f'stat_softirq_{name}_cum'] = int(val)


def parse_iostat(buf: list[str], snap: dict) -> None:
    header: list[str] | None = None
    rows: list[list[str]] = []
    for line in buf:
        if line.lstrip().startswith('Device'):
            header = line.split()
            rows = []
            continue
        if header is None:
            continue
        parts = line.split()
        if len(parts) != len(header):
            continue
        rows.append(parts)

    if header is None:
        return

    for parts in rows:
        cols = dict(zip(header, parts))
        dev = cols.get('Device')
        if not dev:
            continue
        if dev.startswith(IOSTAT_DEV_SKIP_PREFIX):
            continue
        for src, dst in IOSTAT_RATE_FIELDS.items():
            if src in cols:
                try:
                    snap[f'iostat_{dst}_{dev}'] = float(cols[src])
                except ValueError:
                    pass


def parse_mpstat(buf: list[str], snap: dict) -> None:
    header: list[str] | None = None
    for line in buf:
        parts = line.split()
        if not parts:
            continue
        if 'CPU' in parts and '%usr' in parts:
            header = parts
            continue
        if header is None or len(parts) != len(header):
            continue
        cols = dict(zip(header, parts))
        cpu = cols.get('CPU')
        if cpu != 'all':
            continue
        for src, dst in MPSTAT_CPU_FIELDS.items():
            if src in cols:
                try:
                    snap[f'mpstat_cpu_{dst}'] = float(cols[src])
                except ValueError:
                    pass


def parse_vmstat(buf: list[str], snap: dict) -> None:
    rows = [l for l in buf if l.strip()]
    if len(rows) < 3:
        return
    header = rows[1].split()
    data = rows[-1].split()
    if len(header) != len(data):
        return
    cols = dict(zip(header, data))
    for col in VMSTAT_INSTANT_FIELDS:
        if col in cols:
            try:
                snap[f'vmstat_{col}'] = int(cols[col])
            except ValueError:
                pass
    for col in VMSTAT_RATE_FIELDS:
        if col in cols:
            try:
                snap[f'vmstat_{col}_rate'] = float(cols[col])
            except ValueError:
                pass
    for src, dst in VMSTAT_CPU_FIELDS.items():
        if src in cols:
            try:
                snap[f'vmstat_cpu_{dst}'] = float(cols[src])
            except ValueError:
                pass


SECTION_HANDLERS = {
    '/proc/loadavg': parse_loadavg,
    '/proc/pressure/cpu': parse_pressure,
    '/proc/stat': parse_stat,
    'iostat': parse_iostat,
    'mpstat': parse_mpstat,
    'vmstat': parse_vmstat,
}


def parse_log(path: Path) -> pd.DataFrame:
    snapshots: dict[str, dict] = {}
    current_ts: str | None = None
    current_section: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if current_ts is None or current_section is None:
            return
        handler = SECTION_HANDLERS.get(current_section)
        if handler is None:
            return
        snap = snapshots.setdefault(current_ts, {})
        handler(buf, snap)

    with path.open() as f:
        for raw in f:
            line = raw.rstrip('\n')
            m = SECTION_RE.match(line)
            if m:
                flush()
                current_ts, current_section = m.group(1), m.group(2)
                buf = []
            else:
                buf.append(line)
        flush()

    df = pd.DataFrame.from_dict(snapshots, orient='index')
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


# ---------------------------------------------------------------------------
# augment: compute deltas / rates / pcts / derived metrics
# ---------------------------------------------------------------------------


def augment(df: pd.DataFrame, ncpu: int) -> pd.DataFrame:
    # Drop stat_intr_<i>_cum columns that never changed (sparse/zero IRQs) so they
    # don't pollute --list-ids and the rate computation.
    drop_cols = []
    for c in df.columns:
        if c.startswith('stat_intr_') and c.endswith('_cum') and c != 'stat_intr_total_cum':
            if df[c].nunique(dropna=True) <= 1:
                drop_cols.append(c)
    if drop_cols:
        df = df.drop(columns=drop_cols)

    secs = df.index.to_series().diff().dt.total_seconds()

    # Aggregate CPU%
    agg_cum_cols = [f'stat_cpu_{f}_cum' for f in CPU_FIELDS if f'stat_cpu_{f}_cum' in df.columns]
    if agg_cum_cols:
        deltas = df[agg_cum_cols].diff()
        total = deltas.sum(axis=1).replace(0, float('nan'))
        for f in CPU_FIELDS:
            col = f'stat_cpu_{f}_cum'
            if col in df.columns:
                df[f'stat_cpu_{f}'] = deltas[col].div(total) * 100

    # Per-CPU CPU%
    percpu_prefixes: set[str] = set()
    for c in df.columns:
        m = re.match(r'^(stat_cpu\d+)_\w+_cum$', c)
        if m:
            percpu_prefixes.add(m.group(1))
    for prefix in percpu_prefixes:
        cum_cols = [f'{prefix}_{f}_cum' for f in CPU_FIELDS if f'{prefix}_{f}_cum' in df.columns]
        if not cum_cols:
            continue
        deltas = df[cum_cols].diff()
        total = deltas.sum(axis=1).replace(0, float('nan'))
        for f in CPU_FIELDS:
            col = f'{prefix}_{f}_cum'
            if col in df.columns:
                df[f'{prefix}_{f}'] = deltas[col].div(total) * 100

    # PSI total → rate (μs/sec)
    for kind in ('some', 'full'):
        col = f'psi_cpu_{kind}_total_cum'
        if col in df.columns:
            df[f'psi_cpu_{kind}_total_rate'] = df[col].diff() / secs

    # loadavg last_pid → rate
    if 'loadavg_last_pid_cum' in df.columns:
        df['loadavg_last_pid_rate'] = df['loadavg_last_pid_cum'].diff() / secs

    # /proc/stat scalar rate columns
    rate_map = {
        'stat_ctxt_cum': 'stat_ctxt_rate',
        'stat_processes_cum': 'stat_processes_rate',
        'stat_intr_total_cum': 'stat_intr_total_rate',
        'stat_softirq_total_cum': 'stat_softirq_total_rate',
    }
    for name in SOFTIRQ_NAMES:
        rate_map[f'stat_softirq_{name}_cum'] = f'stat_softirq_{name}_rate'
    for src, dst in rate_map.items():
        if src in df.columns:
            df[dst] = df[src].diff() / secs

    # Per-IRQ rates
    for c in [c for c in df.columns if c.startswith('stat_intr_') and c.endswith('_cum') and c != 'stat_intr_total_cum']:
        dst = c[:-len('_cum')] + '_rate'
        df[dst] = df[c].diff() / secs

    # iostat per-device rates + totals.
    rate_read_devs: list[str] = []
    rate_wrtn_devs: list[str] = []
    for c in list(df.columns):
        if c.startswith('iostat_kb_read_rate_'):
            rate_read_devs.append(c)
        elif c.startswith('iostat_kb_wrtn_rate_'):
            rate_wrtn_devs.append(c)
    if rate_read_devs:
        df['iostat_kb_read_rate_total'] = df[rate_read_devs].sum(axis=1, min_count=1)
    if rate_wrtn_devs:
        df['iostat_kb_wrtn_rate_total'] = df[rate_wrtn_devs].sum(axis=1, min_count=1)

    # Derived
    if 'loadavg_load1' in df.columns:
        df['derived_cpu_saturation'] = df['loadavg_load1'] / ncpu
    if 'stat_ctxt_rate' in df.columns and 'stat_procs_running' in df.columns:
        df['derived_ctxt_per_task'] = df['stat_ctxt_rate'] / df['stat_procs_running'].replace(0, float('nan'))
    if {'stat_cpu_iowait', 'iostat_kb_read_rate_total', 'iostat_kb_wrtn_rate_total'}.issubset(df.columns):
        io_total = df['iostat_kb_read_rate_total'] + df['iostat_kb_wrtn_rate_total']
        df['derived_iowait_per_iobyte'] = df['stat_cpu_iowait'] / io_total.replace(0, float('nan'))
    if 'vmstat_swpd' in df.columns:
        df['derived_mem_pressure_warning'] = (df['vmstat_swpd'] > 0).astype(int)

    return df


def available_ids(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if not c.endswith('_cum') and '_cum_' not in c]


# ---------------------------------------------------------------------------
# plot
# ---------------------------------------------------------------------------


def plot(args: argparse.Namespace) -> int:
    log_path: Path = args.log.expanduser()
    logger.info(f'reading {log_path}')
    df = parse_log(log_path)
    logger.info(f'parsed {len(df)} snapshots ({df.index.min()} .. {df.index.max()})')
    df = augment(df, args.ncpu)

    if args.list_ids:
        for c in sorted(available_ids(df)):
            print(c)
        return 0

    out_path: Path = args.out.expanduser()
    if args.panel:
        panels: list[list[str]] = []
        all_ids = set(available_ids(df))
        for spec in args.panel:
            ids = [s.strip() for s in spec.split(',') if s.strip()]
            unknown = [i for i in ids if i not in all_ids]
            if unknown:
                ok = sorted(available_ids(df))
                logger.error(f'unknown ID(s): {unknown}')
                logger.error(f'use --list-ids to see all {len(ok)} available IDs')
                return 2
            panels.append(ids)
        render_custom_panels(df, panels, out_path)
    else:
        render_default_panels(df, args.ncpu, out_path)
    return 0


def render_default_panels(df: pd.DataFrame, ncpu: int, out_path: Path) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

    stack_fields = [
        'stat_cpu_user', 'stat_cpu_system', 'stat_cpu_iowait', 'stat_cpu_irq',
        'stat_cpu_softirq', 'stat_cpu_steal', 'stat_cpu_idle',
    ]
    colors = ['#4c78a8', '#f58518', '#e45756', '#72b7b2', '#54a24b', '#b279a2', '#dddddd']
    stack_df = df[stack_fields].dropna()
    axes[0].stackplot(
        stack_df.index,
        [stack_df[f] for f in stack_fields],
        labels=stack_fields,
        colors=colors,
    )
    axes[0].set_ylabel('CPU %')
    axes[0].set_ylim(0, 100)
    axes[0].legend(loc='upper right', ncol=4, fontsize=8)
    axes[0].set_title('CPU usage (from /proc/stat diffs)')

    for col in ['loadavg_load1', 'loadavg_load5', 'loadavg_load15']:
        axes[1].plot(df.index, df[col], label=col, linewidth=1)
    axes[1].axhline(ncpu, color='grey', linestyle=':', linewidth=0.8, label=f'ncpu={ncpu}')
    axes[1].set_ylabel('load avg')
    axes[1].legend(loc='upper right', fontsize=8)
    axes[1].set_title('Load average (/proc/loadavg)')

    for col in ['psi_cpu_some_10', 'psi_cpu_some_60', 'psi_cpu_some_300']:
        axes[2].plot(df.index, df[col], label=col, linewidth=1)
    for col in ['psi_cpu_full_10', 'psi_cpu_full_60', 'psi_cpu_full_300']:
        axes[2].plot(df.index, df[col], label=col, linewidth=1, linestyle='--')
    axes[2].set_ylabel('PSI %')
    axes[2].set_ylim(bottom=0)
    axes[2].legend(loc='upper right', ncol=2, fontsize=8)
    axes[2].set_title('Pressure Stall Information (/proc/pressure/cpu)')

    axes[3].plot(df.index, df['stat_procs_running'], label='stat_procs_running', linewidth=1)
    axes[3].plot(df.index, df['stat_procs_blocked'], label='stat_procs_blocked', linewidth=1)
    axes[3].set_ylabel('procs')
    axes[3].legend(loc='upper right', fontsize=8)
    axes[3].set_title('Runnable / blocked processes (/proc/stat)')

    _finalize(fig, axes[-1], out_path)


def render_custom_panels(df: pd.DataFrame, panels: list[list[str]], out_path: Path) -> None:
    n = len(panels)
    fig, axes = plt.subplots(n, 1, figsize=(14, max(3 * n, 4)), sharex=True, squeeze=False)
    for i, ids in enumerate(panels):
        ax = axes[i][0]
        for id_ in ids:
            ax.plot(df.index, df[id_], label=id_, linewidth=1)
        ax.legend(loc='upper right', fontsize=8, ncol=max(1, len(ids) // 4))
        ax.set_title(', '.join(ids))
        ax.grid(True, alpha=0.3)
    _finalize(fig, axes[-1][0], out_path)


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
