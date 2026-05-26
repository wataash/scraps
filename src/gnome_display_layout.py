#!/home/wsh/opt_/pyvenv2/bin/python
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r'''
# シナリオを自動判定 + default variant を適用
gnome_display_layout.py apply

# variant を強制指定して適用 (ドライラン)
gnome_display_layout.py apply -p pR -n

# シナリオ・variant の一覧を表示
gnome_display_layout.py list
'''[1:]

import argparse
import json
import logging
import subprocess
import sys

# ==============================================================================
# プロファイル設定 (将来的な組み合わせもここに追記するだけで対応可能)
# ==============================================================================
# Role -> 製品コード (固定モニター)。"etc" は実行時に他の検出モニターへ割り当てる動的ロール。
ROLE_PRODUCTS = {
    "pc": "0x419f",            # PC内蔵液晶 (常に存在、メイン)
    "portable": "DP-FF164S-B", # ポータブルディスプレイ
}

# プロファイル = (シナリオ × variant)。
#   シナリオは "roles" (必要なロール集合) で判定。"etc" は wildcard で任意の第3モニター。
#   variant の layout は (X座標, Y座標, スケール, 回転, プライマリ) を role 名でキー指定。
PROFILES = {
    "pc+portable": {
        "roles": ["pc", "portable"],
        "default": "not_tested_yet.pL",
        "variants": {
            "not_tested_yet.pL": {
                "description": "portable | pc (pc=メイン)",
                "layout": {
                    "portable": (   0, 0, 1.0, 0, False),
                    "pc":       (1920, 0, 1.5, 0, True),
                },
            },
            "not_tested_yet.pR": {
                "description": "pc | portable (pc=メイン)",
                "layout": {
                    "pc":       (   0, 0, 1.5, 0, True),
                    "portable": (1920, 0, 1.0, 0, False),
                },
            },
        },
    },
    "pc+etc": {
        "roles": ["pc", "etc"],
        "default": "not_tested_yet.etcU",
        "variants": {
            "not_tested_yet.etcU": {
                "description": "etc / pc 縦並び (pc=メイン下)",
                "layout": {
                    "etc": (0,    0, 1.0, 0, False),
                    "pc":  (0, 1080, 1.5, 0, True),
                },
            },
            "not_tested_yet.etcL": {
                "description": "etc | pc (pc=メイン)",
                "layout": {
                    "etc": (   0, 0, 1.0, 0, False),
                    "pc":  (1920, 0, 1.5, 0, True),
                },
            },
            "not_tested_yet.etcR": {
                "description": "pc | etc (pc=メイン)",
                "layout": {
                    "pc":  (   0, 0, 1.5, 0, True),
                    "etc": (1920, 0, 1.0, 0, False),
                },
            },
        },
    },
    "pc+portable+etc": {
        "roles": ["pc", "portable", "etc"],
        "default": "pL",
        "variants": {
            "pL": {
                "description": "etc 右上 / portable pc 下段 (pc=メイン右下)",
                "layout": {
                    "etc":      (1920,    0, 1.0, 0, False),
                    "portable": (   0, 1080, 1.0, 0, False),
                    "pc":       (1920, 1080, 1.5, 0, True),
                },
            },
            "pR": {
                "description": "etc 左上 / pc portable 下段 (pc=メイン左下)",
                "layout": {
                    "etc":      (   0,    0, 1.0, 0, False),
                    "pc":       (   0, 1080, 1.5, 0, True),
                    "portable": (1920, 1080, 1.0, 0, False),
                },
            },
            "p_pc_etc": {
                "description": "portable pc etc 横一列 (pc=メイン中央)",
                "layout": {
                    "portable": (   0, 0, 1.0, 0, False),
                    "pc":       (1920, 0, 1.5, 0, True),
                    "etc":      (3840, 0, 1.0, 0, False),
                },
            },
            "etc_pc_p": {
                "description": "etc pc portable 横一列 (pc=メイン中央)",
                "layout": {
                    "etc":      (   0, 0, 1.0, 0, False),
                    "pc":       (1920, 0, 1.5, 0, True),
                    "portable": (3840, 0, 1.0, 0, False),
                },
            },
        },
    },
}


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


class DetectedMonitor:
    def __init__(self, connector: str, vendor: str, product: str, serial: str, best_mode: str):
        self.connector = connector
        self.vendor = vendor
        self.product = product
        self.serial = serial
        self.best_mode = best_mode


def get_current_state() -> list:
    cmd = [
        "busctl", "--user", "call",
        "org.gnome.Mutter.DisplayConfig",
        "/org/gnome/Mutter/DisplayConfig",
        "org.gnome.Mutter.DisplayConfig",
        "GetCurrentState",
        "--json=short"
    ]
    logger.debug(f"Running command to query state: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"Error getting current display state: {result.stderr}")
        sys.exit(1)
    
    res = json.loads(result.stdout)
    return res["data"]


def apply(args: argparse.Namespace) -> int:
    data = get_current_state()
    serial = data[0]
    monitors_data = data[1]
    
    detected_monitors = []
    detected_products = []
    
    for m in monitors_data:
        monitor_info = m[0]
        connector = monitor_info[0]
        vendor = monitor_info[1]
        product = monitor_info[2]
        modes = m[1]
        
        detected_products.append(product)
        
        preferred_mode = None
        current_mode = None
        for mode in modes:
            mode_id = mode[0]
            props = mode[6] if len(mode) > 6 else {}
            is_current = props.get("is-current", {}).get("data", False)
            is_preferred = props.get("is-preferred", {}).get("data", False)
            
            if is_current:
                current_mode = mode_id
            if is_preferred:
                preferred_mode = mode_id
                
        best_mode = current_mode or preferred_mode or (modes[0][0] if modes else None)
        detected_monitors.append(DetectedMonitor(connector, vendor, product, serial, best_mode))

    logger.info(f"Connected monitors (products): {detected_products}")

    # 検出モニターを role に分類 (pc / portable / etc)
    role_to_monitor: dict[str, DetectedMonitor] = {}
    etc_monitors: list[DetectedMonitor] = []
    for mon in detected_monitors:
        role = next((r for r, p in ROLE_PRODUCTS.items() if p == mon.product), None)
        if role:
            role_to_monitor[role] = mon
        else:
            etc_monitors.append(mon)
    if len(etc_monitors) == 1:
        role_to_monitor["etc"] = etc_monitors[0]
    elif len(etc_monitors) > 1:
        logger.error(f"Multiple non-pc/portable monitors detected, cannot assign 'etc' role unambiguously: {[m.product for m in etc_monitors]}")
        return 1

    detected_roles = set(role_to_monitor.keys())
    logger.info(f"Detected roles: {sorted(detected_roles)}")

    # シナリオ判定 (roles が完全一致するもの)
    scenario_name = next((n for n, s in PROFILES.items() if set(s["roles"]) == detected_roles), None)
    if not scenario_name:
        logger.error(f"No scenario matches detected roles {sorted(detected_roles)}.")
        logger.info(f"Available scenarios: {[(n, s['roles']) for n, s in PROFILES.items()]}")
        return 1
    scenario = PROFILES[scenario_name]
    logger.info(f"Matched scenario: '{scenario_name}' (roles={scenario['roles']})")

    # variant 選定
    variant_name = args.profile or scenario["default"]
    variant = scenario["variants"].get(variant_name)
    if not variant:
        logger.error(f"Variant '{variant_name}' not found in scenario '{scenario_name}'. Available: {list(scenario['variants'].keys())}")
        return 1
    logger.info(f"Applying variant '{variant_name}': {variant['description']}")

    # variant に従って logical_monitors 構造体を組み立て
    logical_monitors = []
    for role, layout_conf in variant["layout"].items():
        x, y, scale, transform, primary = layout_conf
        tgt_mon = role_to_monitor[role]
        logical_monitors.append(
            (x, y, scale, transform, primary, [(tgt_mon.connector, tgt_mon.best_mode, {})])
        )

    # gdbus コマンド用引数のシリアライズ
    lm_strings = []
    for lm in logical_monitors:
        x, y, scale, transform, primary, monitors = lm
        monitor_strings = []
        for m in monitors:
            connector, mode_id, props = m
            monitor_strings.append(f"('{connector}', '{mode_id}', {{}})")
        
        monitors_arr_str = "[" + ", ".join(monitor_strings) + "]"
        primary_str = "true" if primary else "false"
        lm_strings.append(f"({x}, {y}, {scale}, {transform}, {primary_str}, {monitors_arr_str})")
        
    lm_arg = "[" + ", ".join(lm_strings) + "]"
    
    cmd = [
        "gdbus", "call", "--session",
        "--dest", "org.gnome.Mutter.DisplayConfig",
        "--object-path", "/org/gnome/Mutter/DisplayConfig",
        "--method", "org.gnome.Mutter.DisplayConfig.ApplyMonitorsConfig",
        str(serial), "2", lm_arg, "{}"
    ]

    runnable_cmd_str = f"gdbus call --session --dest org.gnome.Mutter.DisplayConfig --object-path /org/gnome/Mutter/DisplayConfig --method org.gnome.Mutter.DisplayConfig.ApplyMonitorsConfig {serial} 2 \"{lm_arg}\" \"{{}}\""

    if args.dry_run:
        print(runnable_cmd_str)
        return 0
    else:
        logger.info(f"Executing command: {runnable_cmd_str}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            logger.error(f"Error applying configuration: {result.stderr}")
            return 1
        logger.info("Successfully applied display layout!")
        return 0


def list_profiles(args: argparse.Namespace) -> int:
    BOLD, DIM, RESET = '\x1b[1m', '\x1b[2m', '\x1b[m'
    CYAN, GREEN, YELLOW, MAGENTA, BLUE = '\x1b[36m', '\x1b[32m', '\x1b[33m', '\x1b[35m', '\x1b[34m'
    role_label = {r: f'{MAGENTA}{r}{RESET} ({p})' for r, p in ROLE_PRODUCTS.items()}
    role_label['etc'] = f'{MAGENTA}etc{RESET} (任意の第3モニター)'
    print(f'{BOLD}Available Scenarios & Variants:{RESET}')
    for scen_name, scen in PROFILES.items():
        roles = ', '.join(role_label[r] for r in scen['roles'])
        print(f'  {GREEN}■{RESET} {BOLD}{CYAN}{scen_name}{RESET}  {DIM}roles=[{RESET}{roles}{DIM}]{RESET}  {DIM}default={RESET}{BLUE}{scen["default"]}{RESET}')
        for vname, variant in scen['variants'].items():
            tag = f' {YELLOW}(default){RESET}' if vname == scen['default'] else ''
            print(f'      {GREEN}●{RESET} {BOLD}{BLUE}{vname}{RESET}{tag}  {DIM}—{RESET} {variant["description"]}')
            for role, (x, y, scale, transform, primary) in variant['layout'].items():
                primary_tag = f' {YELLOW}★primary{RESET}' if primary else ''
                print(f'          {MAGENTA}{role:<10}{RESET} {DIM}@{RESET} ({x:>4}, {y:>4})  scale={scale}  rot={transform}{primary_tag}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument('-n', '--dry_run', action='store_true', help='dry-run mode (print command without executing)')
    
    subparsers = parser.add_subparsers(dest='subcommand_name', required=True)
    
    subparser_apply = subparsers.add_parser('apply', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='Apply display layout')
    subparser_apply.set_defaults(func=apply)
    subparser_apply.add_argument('-p', '--profile', help='Force a specific profile name instead of auto-detecting')
    
    subparser_list = subparsers.add_parser('list', formatter_class=ArgumentDefaultsRawTextHelpFormatter, help='List all available profiles')
    subparser_list.set_defaults(func=list_profiles)
    
    args = parser.parse_args()
    logger.debug(f'{args=}')
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
