#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r"""
# watch fprintd VerifyStatus and blink LEDs (must run as root to write sysfs):
sudo /usr/local/bin/fprint_feedback led

# watch fprintd VerifyStatus and flash the corner-blink GNOME extension (run as your user):
python fprint_feedback.py corner

# fire one success+fail feedback without touching the sensor (setup check):
sudo /usr/local/bin/fprint_feedback led    --self_test
python fprint_feedback.py corner --self_test

python fprint_feedback.py led -h
python fprint_feedback.py corner -h
"""[1:]

import argparse
import logging
import re
import subprocess
import sys
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
        fn = "" if record.funcName == "<module>" else f" {record.funcName}()"
        fmt = f"{color}[%(levelname)1.1s %(asctime)s %(filename)s:%(lineno)d{fn}] %(message)s{c.RESET}"
        return logging.Formatter(fmt=fmt, datefmt="%T").format(record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_handler = logging.StreamHandler()
logger_handler.setFormatter(MyFormatter())
logger.addHandler(logger_handler)


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


# --- feedback parameters (per spec) -----------------------------------------
# result -> (color, interval_ms, duration_ms)
FAIL = {"color": "red", "interval": 100, "duration": 500}
SUCCESS = {"color": "lime", "interval": 200, "duration": 1200}

# corner-blink dot size (px). Pushed via GSettings so the on-screen flash is
# visible regardless of the extension's own `size` default.
DOT_SIZE = 64

# LEDs to blink. Missing entries are skipped.
LED_DIRS = [
    Path("/sys/class/leds/platform::micmute"),
    Path("/sys/class/leds/platform::mute"),
    Path("/sys/class/leds/tpacpi::lid_logo_dot"),
    Path("/sys/class/leds/tpacpi::power"),
]

# corner-blink (GNOME extension) GSettings schema + local schema dir.
CB_SCHEMA = "org.gnome.shell.extensions.corner-blink"
CB_SCHEMADIR = Path.home() / ".local/share/gnome-shell/extensions/corner-blink@local/schemas"


# --- fprintd event source ----------------------------------------------------
# VerifyStatus is a broadcast D-Bus signal, so any client can receive it via a
# plain match rule (no BecomeMonitor / eavesdropping, no special privilege).
# `gdbus monitor` uses AddMatch, so it works for both root and the regular user.
_VERIFY_RE = re.compile(r"VerifyStatus \('([^']*)', (true|false)\)")


def iter_verify_results():
    """Yield (result: str, done: bool) for each fprintd VerifyStatus signal."""
    cmd = ["gdbus", "monitor", "--system", "--dest", "net.reactivated.Fprint"]
    logger.info("watching: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, bufsize=1)
    assert proc.stdout is not None
    for line in proc.stdout:
        m = _VERIFY_RE.search(line)
        if m:
            yield m.group(1), m.group(2) == "true"


def classify(result: str, done: bool) -> dict | None:
    """Map a VerifyStatus result to FAIL/SUCCESS params, or None to ignore."""
    if result == "verify-match":
        return SUCCESS
    if result == "verify-no-match":
        return FAIL
    # retry/transient statuses (verify-retry-scan, verify-swipe-too-short, ...)
    return None


# --- LED feedback (runs as root) --------------------------------------------
def read_int(path: Path) -> int:
    return int(path.read_text().strip() or "0")


def discover_leds() -> list[tuple[Path, int]]:
    """Return [(brightness_path, max_brightness), ...] for present LEDs."""
    leds = []
    for d in LED_DIRS:
        b = d / "brightness"
        if b.exists():
            leds.append((b, read_int(d / "max_brightness")))
        else:
            logger.warning("LED not found, skipping: %s", d)
    return leds


def blink_leds(leds: list[tuple[Path, int]], interval_ms: int, duration_ms: int, dry_run: bool) -> None:
    """Blink LEDs to max/0 for duration_ms, then restore original brightness."""
    orig = [read_int(b) for b, _ in leds]
    if dry_run:
        for (b, mx), o in zip(leds, orig):
            print(f"# blink {b} between {mx} and 0 every {interval_ms}ms for {duration_ms}ms, then restore {o}")
        return
    end = time.monotonic() + duration_ms / 1000
    on = False
    try:
        while time.monotonic() < end:
            on = not on
            for b, mx in leds:
                b.write_text(f"{mx if on else 0}\n")
            time.sleep(interval_ms / 1000)
    finally:
        for (b, _), o in zip(leds, orig):
            b.write_text(f"{o}\n")


# --- corner-blink feedback (runs as the user, in the GNOME session) ---------
def flash_corners(params: dict, dry_run: bool) -> None:
    """Bump the corner-blink extension's flash-trigger so it flashes once."""
    base = ["gsettings", "--schemadir", str(CB_SCHEMADIR), "set", CB_SCHEMA]
    try:
        cur = subprocess.run(
            ["gsettings", "--schemadir", str(CB_SCHEMADIR), "get", CB_SCHEMA, "flash-trigger"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        trigger = int(cur) + 1
    except (subprocess.CalledProcessError, ValueError):
        trigger = 1
    # Set parameters first, then bump the trigger last so the extension reads
    # consistent values when it reacts to the trigger change.
    sets = [
        ["size", str(DOT_SIZE)],
        ["flash-color", params["color"]],
        ["flash-interval", str(params["interval"])],
        ["flash-duration", str(params["duration"])],
        ["flash-trigger", str(trigger)],
    ]
    for key, val in sets:
        cmd = base + [key, val]
        if dry_run:
            print(" ".join(cmd))
        else:
            logger.debug("%s", " ".join(cmd))
            subprocess.run(cmd, check=False)


# --- subcommands -------------------------------------------------------------
def cmd_led(args: argparse.Namespace) -> int:
    leds = discover_leds()
    if not leds:
        logger.error("no target LEDs present")
        return 1
    if args.self_test:
        logger.info("self-test: SUCCESS feedback"); blink_leds(leds, SUCCESS["interval"], SUCCESS["duration"], args.dry_run)
        time.sleep(0.3)
        logger.info("self-test: FAIL feedback"); blink_leds(leds, FAIL["interval"], FAIL["duration"], args.dry_run)
        return 0
    for result, done in iter_verify_results():
        params = classify(result, done)
        logger.info("VerifyStatus %r done=%s -> %s", result, done,
                    "SUCCESS" if params is SUCCESS else "FAIL" if params is FAIL else "ignore")
        if params is not None:
            blink_leds(leds, params["interval"], params["duration"], args.dry_run)
    return 0


def cmd_corner(args: argparse.Namespace) -> int:
    if not CB_SCHEMADIR.exists():
        logger.warning("corner-blink schema dir not found: %s", CB_SCHEMADIR)
    if args.self_test:
        logger.info("self-test: SUCCESS feedback"); flash_corners(SUCCESS, args.dry_run)
        time.sleep(1.0)
        logger.info("self-test: FAIL feedback"); flash_corners(FAIL, args.dry_run)
        return 0
    for result, done in iter_verify_results():
        params = classify(result, done)
        logger.info("VerifyStatus %r done=%s -> %s", result, done,
                    "SUCCESS" if params is SUCCESS else "FAIL" if params is FAIL else "ignore")
        if params is not None:
            flash_corners(params, args.dry_run)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument("-q", "--quiet", action="count", default=0,
                        help="decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error")
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    for name, func, helptext in [
        ("led", cmd_led, "blink LEDs on fprintd VerifyStatus (run as root)"),
        ("corner", cmd_corner, "flash corner-blink on fprintd VerifyStatus (run as user)"),
    ]:
        sub = subparsers.add_parser(name, help=helptext, formatter_class=ArgumentDefaultsRawTextHelpFormatter)
        sub.set_defaults(func=func)
        sub.add_argument("-n", "--dry_run", action="store_true", help="print actions without executing")
        sub.add_argument("--self_test", action="store_true", help="fire one success+fail feedback then exit")

    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f"{args=}")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
