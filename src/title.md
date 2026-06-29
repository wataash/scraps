# title.py

[title.py](title.py)

Shows a small always-visible window displaying the given text. Intended as a
per-workspace label: GNOME has 9 workspaces in this environment and it is easy
to lose track of what each one is for, so placing a `title.py HELLO` window on a
workspace acts as a sticky note ("this workspace is HELLO").

The window is shown as `_NET_WM_WINDOW_TYPE_UTILITY` to keep it out of the
Alt+Tab list. Click the text to edit it inline; press Enter/Escape or click
elsewhere to commit the change.

## Usage

```sh
GDK_BACKEND=x11 python title.py HELLO
GDK_BACKEND=x11 python title.py 'good morning' --font-size 96
```

`GDK_BACKEND=x11` forces XWayland. On native Wayland / GNOME mutter there is no
client-side way to opt a window out of Alt+Tab (`skip_taskbar` is X11-only and
wlr-layer-shell is not implemented in mutter), so we route through XWayland and
let mutter honor the X11 window-type hint, which it excludes from Alt+Tab.

## Options

| Option        | Description                              |
| ------------- | ---------------------------------------- |
| `text`        | Text shown in the window.                |
| `--font-size` | Font size in points (default 48).        |
| `--title`     | X11 window title (default `title.py`).   |
| `-h, --help`  | Show help and exit.                      |
