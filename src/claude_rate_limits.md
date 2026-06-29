# claude_rate_limits.py

[claude_rate_limits.py](claude_rate_limits.py)

Renders subscription **rate-limit usage bars** from a Claude Code `statusLine`
payload (read as JSON on stdin), on one line:

```
session [█░░░░░░░░░] 7%  week [██░░░░░░░░] 21%
```

- **session** — the 5-hour usage window (`rate_limits.five_hour`), the same
  "Current session" bar shown by `/usage`.
- **week** — the 7-day, all-models window (`rate_limits.seven_day`), the same
  "Current week (all models)" bar.

Percentages come straight from the `rate_limits` object that Claude Code
passes to the `statusLine` command — no API call is made.

> **Not shown: "Current week (Fable)".** `/usage` has a third, Fable-specific
> weekly bar, but the `statusLine` payload only carries `five_hour` and
> `seven_day`. That figure is only available through `/usage` itself.

## Usage

```sh
# From a statusLine payload on stdin
echo '{"rate_limits":{"five_hour":{"used_percentage":7}}}' \
  | python claude_rate_limits.py
```

Intended to run inside the [claude_statusline.bash](claude_statusline.md)
wrapper, which feeds it the same payload it gives to the other status-line
commands. If the payload has no `rate_limits` (older Claude Code), nothing is
printed.

## Options

| Option        | Description                                                    |
| ------------- | ------------------------------------------------------------- |
| `-w, --width` | Progress-bar width in characters (default 10).                |
| `-q, --quiet` | Decrease verbosity (`-q` info, `-qq` warning, `-qqq` error).  |
| `-h, --help`  | Show help and exit.                                           |
