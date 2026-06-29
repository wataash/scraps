# led_brightness_gui

[led_brightness_gui.py](led_brightness_gui.py)

A small Tkinter GUI to list every `/sys/class/leds/*/brightness` and change each
one with a slider (knob). Useful for finding and exercising laptop LEDs
(keyboard lock LEDs, ThinkPad logo dot, mute/micmute, Wi-Fi, etc.).

Each row shows the LED name, a 0..`max_brightness` slider, the current value,
and `0` / `max` / `toggle` shortcut buttons (`toggle` flips between 0 and max).
**toggle 0/max all** turns every LED off if any is on, otherwise drives them all
to max. **Refresh** re-reads all current values from sysfs; **Reset** restores
every LED to the value it had when the GUI started.

## Usage

Run as root (writing to sysfs `brightness` requires it). `-E` keeps the
`DISPLAY`/Wayland env so the window can open:

```sh
sudo -E python led_brightness_gui.py
```

Running as a normal user opens the window (reading values works) but slider
changes fail with "permission denied"; the toolbar shows the warning.

## Options

| Option       | Description         |
| ------------ | ------------------- |
| `-h, --help` | Show help and exit. |

## Notes

- Writes go directly to the sysfs `brightness` file (root assumed). No `sudo`
  fallback.
- The toolbar shows `root: writable` or `NOT root: writes will fail`.
- Slider writes are debounced (~60 ms) so dragging doesn't spam sysfs.
- On exit (window close or quit) every LED is restored to the value it had when
  the GUI started.
- Some LEDs are driven by a kernel trigger (e.g. capslock, mute). The trigger
  may immediately overwrite a manual value; set the LED's `trigger` to `none`
  first if you want a value to stick.
