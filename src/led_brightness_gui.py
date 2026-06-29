#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
epilog = r"""
python led_brightness_gui.py -h
sudo -E python led_brightness_gui.py         # run as root (-E keeps DISPLAY/Wayland env)
"""[1:]

import argparse
import logging
import os
import sys
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


LEDS_DIR = Path("/sys/class/leds")


class ArgumentDefaultsRawTextHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass


def discover_leds() -> list[Path]:
    """
    >>> isinstance(discover_leds(), list)
    True
    """
    if not LEDS_DIR.exists():
        return []
    return sorted(p for p in LEDS_DIR.iterdir() if (p / "brightness").exists())


def read_int(path: Path) -> int:
    return int(path.read_text().strip() or "0")


def write_brightness(path: Path, value: int) -> str | None:
    """Write `value` to `path`. Return None on success, else an error string."""
    try:
        path.write_text(f"{value}\n")
        return None
    except PermissionError:
        return "permission denied (run as root)"
    except OSError as e:
        return str(e)


class LedRow:
    def __init__(self, app: "App", parent, led_dir: Path, row: int) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.app = app
        self.brightness_path = led_dir / "brightness"
        self.max = read_int(led_dir / "max_brightness")
        cur = read_int(self.brightness_path)
        self.initial = cur
        self._after_id: str | None = None

        ttk.Label(parent, text=led_dir.name, width=30, anchor="w").grid(row=row, column=0, sticky="w", padx=(4, 8), pady=2)

        self.var = tk.IntVar(value=cur)
        self.scale = ttk.Scale(
            parent, from_=0, to=max(self.max, 1), orient="horizontal", length=260,
            command=self._on_slide,
        )
        self.scale.set(cur)
        self.scale.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        self.scale.bind("<Button-1>", self._on_click, add="+")

        self.value_label = ttk.Label(parent, textvariable=self.var, width=4, anchor="e")
        self.value_label.grid(row=row, column=2, padx=4)
        ttk.Label(parent, text=f"/ {self.max}", width=7, anchor="w").grid(row=row, column=3, sticky="w", padx=(0, 4))

        ttk.Button(parent, text="0", width=2, command=lambda: self.set_value(0)).grid(row=row, column=4, padx=1)
        ttk.Button(parent, text="max", width=4, command=lambda: self.set_value(self.max)).grid(row=row, column=5, padx=1)
        ttk.Button(parent, text="toggle", width=6, command=self.toggle).grid(row=row, column=6, padx=(1, 4))

    def _on_click(self, event) -> str | None:
        # Clicking the slider itself: let the default drag handle it.
        if "slider" in str(self.scale.identify(event.x, event.y)):
            return None
        # Clicking the trough: jump to the clicked position instead of paging.
        width = self.scale.winfo_width()
        if width <= 1:
            return None
        frac = min(max(event.x / width, 0.0), 1.0)
        self.set_value(int(round(frac * self.max)))
        return "break"

    def _on_slide(self, raw: str) -> None:
        value = int(round(float(raw)))
        if value == self.var.get():
            return
        self.var.set(value)
        # debounce writes while dragging
        if self._after_id is not None:
            self.scale.after_cancel(self._after_id)
        self._after_id = self.scale.after(60, lambda: self._commit(value))

    def _commit(self, value: int) -> None:
        self._after_id = None
        err = write_brightness(self.brightness_path, value)
        if err is not None:
            self.app.set_status(f"{self.brightness_path.name}: {err}", error=True)
        else:
            self.app.set_status(f"{self.brightness_path.parent.name} = {value}")

    def set_value(self, value: int) -> None:
        value = max(0, min(value, self.max))
        self.var.set(value)
        self.scale.set(value)
        self._commit(value)

    def refresh(self) -> None:
        cur = read_int(self.brightness_path)
        self.var.set(cur)
        self.scale.set(cur)

    def reset(self) -> None:
        self.set_value(self.initial)

    def toggle(self) -> None:
        self.set_value(0 if self.var.get() > 0 else self.max)


class App:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root = tk.Tk()
        self.root.title("LED brightness")
        self.root.minsize(560, 200)
        self.root.protocol("WM_DELETE_WINDOW", self.root.quit)

        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(toolbar, text="toggle 0/max all", command=self.toggle_all).pack(side="left")
        ttk.Button(toolbar, text="Refresh", command=self.refresh_all).pack(side="left", padx=(4, 0))
        ttk.Button(toolbar, text="Reset", command=self.reset_all).pack(side="left", padx=(4, 0))
        mode = "root: writable" if os.geteuid() == 0 else "NOT root: writes will fail"
        ttk.Label(toolbar, text=mode).pack(side="right")

        # scrollable body
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=6, pady=6)
        canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        inner.columnconfigure(1, weight=1)

        self.rows: list[LedRow] = []
        leds = discover_leds()
        if not leds:
            ttk.Label(inner, text=f"No LEDs found in {LEDS_DIR}").grid(row=0, column=0)
        for i, led in enumerate(leds):
            self.rows.append(LedRow(self, inner, led, i))

        self.status = tk.StringVar(value=f"{len(leds)} LED(s)")
        ttk.Label(self.root, textvariable=self.status, anchor="w", relief="sunken").pack(fill="x", side="bottom")

    def set_status(self, msg: str, error: bool = False) -> None:
        self.status.set(msg)
        (logger.error if error else logger.info)(msg)

    def refresh_all(self) -> None:
        for r in self.rows:
            r.refresh()
        self.set_status("refreshed")

    def reset_all(self) -> None:
        for r in self.rows:
            r.reset()
        self.set_status("reset to initial values")

    def toggle_all(self) -> None:
        # if any LED is on, turn all off; otherwise turn all to max
        turn_off = any(r.var.get() > 0 for r in self.rows)
        for r in self.rows:
            r.set_value(0 if turn_off else r.max)
        self.set_status("all -> 0" if turn_off else "all -> max")

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            # restore every LED to its value at startup
            for r in self.rows:
                write_brightness(r.brightness_path, r.initial)
            logger.info("restored LEDs to initial values on exit")


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=ArgumentDefaultsRawTextHelpFormatter, epilog=epilog)
    parser.add_argument("-q", "--quiet", action="count", default=0,
                        help="decrease verbosity; default: debug, -q: info, -qq: warning, -qqq: error")
    args = parser.parse_args()
    logger.setLevel({0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}.get(args.quiet, logging.ERROR))
    logger.debug(f"{args=}")

    if os.geteuid() != 0:
        logger.warning("not running as root; writes to brightness will fail. Use: sudo -E python led_brightness_gui.py")
    App().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
