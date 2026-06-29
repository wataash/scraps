# plot_battery

[plot_battery.py](plot_battery.py)

Plot laptop battery history.

Two kinds of history exist, and they come from different places:

- **State of charge (%) over time** — already recorded by `upower` under
  `/var/lib/upower/history-charge-*.dat`. Use the `charge` subcommand to plot it;
  data is available immediately.
- **Degradation (capacity health: full-charge capacity vs design, cycle count)** —
  **not** recorded by the OS. Only the current value is exposed in sysfs. Run
  `collect` periodically to build this history yourself, then plot it with `plot`.

## Usage

```bash
# 1) start building a degradation history (run periodically; see "Scheduling")
plot_battery.py collect battery.jsonl

# 2) plot the collected degradation history
plot_battery.py plot battery.jsonl battery.png

# 3) plot upower's already-recorded charge history (no collection needed)
plot_battery.py charge battery_charge.png
```

`collect` appends one JSON object per line (JSONL) holding the raw sysfs values
(`energy_*` in µWh, `charge_*` in µAh, `voltage_*` in µV). Conversion to Wh/Ah/V
happens at plot time.

### Scheduling collection

Hourly via cron:

```cron
0 * * * * /home/you/d/s/plot_battery.py collect /home/you/battery.jsonl
```

or a `while` loop:

```bash
while true; do plot_battery.py collect battery.jsonl; sleep 3600; done
```

## Subcommands & options

### `collect <log>`

| option        | default                | description                                           |
| ------------- | ---------------------- | ----------------------------------------------------- |
| `log`         | (required)             | output JSONL file, appended                            |
| `--bat`       | first `BAT*` in sysfs  | power_supply battery name under `/sys/class/power_supply` |
| `-n`, `--dry_run` | off                | print the shell-equivalent `cat` commands, write nothing |

### `plot <log> <out>`

| option | default    | description                                  |
| ------ | ---------- | -------------------------------------------- |
| `log`  | (required) | input JSONL file from `collect`               |
| `out`  | (required) | output PNG path                               |

Renders three panels: capacity health % (full ÷ design × 100), full-charge
capacity (with design as a reference line), and charge cycle count.

### `charge <out>`

| option   | default                   | description                                           |
| -------- | ------------------------- | ----------------------------------------------------- |
| `out`    | (required)                | output PNG path                                        |
| `--dat`  | auto-detect laptop battery | path to a `history-charge-*.dat` under `/var/lib/upower` |

Renders three panels from upower's history files: state of charge %, charge/
discharge rate (W), and voltage (V). Auto-detection matches the sysfs
`model_name`, falling back to the largest `history-charge-*.dat` (peripheral
batteries like mice have tiny histories).

## Notes

- Uses `matplotlib` only (no `pandas`).
- Some laptops expose `charge_*` (µAh) instead of `energy_*` (µWh); both are
  handled, with the panel axis labelled Ah or Wh accordingly.
