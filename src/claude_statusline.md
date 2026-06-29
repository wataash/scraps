# claude_statusline.bash

[claude_statusline.bash](claude_statusline.bash)

Claude Code `statusLine` wrapper that prints:

```
🤖 Opus 4.8 | 💰 $26.84 session / $61.27 today / $1.75 block (4h 26m left) | 🔥 $6.84/hr | 🧠 411,636 (41%)
⟳ $1.75 | claude-opus-4-8: 143 in, 8.8k out, 2.8m cr, 11.0k cw ($1.7513)
Σ $26.84 | claude-opus-4-8: 8.0k in, 75.3k out, 25.9m cr, 1.2m cw ($26.8359)
session [░░░░░░░░░░] 3%  week [██░░░░░░░░] 21%
```

- **ccusage line** — from [`ccusage`](https://github.com/ryoppippi/ccusage)
  (`ccusage statusline`): session / today / current 5-hour block cost, burn
  rate, and context-window remaining.
- **`⟳` line** — the most recent prompt round-trip (turn): total cost plus a
  per-model breakdown. When only one model was used, the total and breakdown
  collapse into a single `|`-joined line.
- **`Σ` line** — cumulative whole-session usage. Its total matches `ccusage`'s
  session cost, except that subagent usage is not counted (it is logged to
  separate transcripts — see [claude_turn_usage.md](claude_turn_usage.md)), so
  `Σ` runs lower than `ccusage` in sessions that ran subagents. Both usage
  lines come from a single `claude_turn_usage.py -m --both` invocation (one
  transcript read per render).
- **rate-limit bars** — subscription session (5-hour) and week (7-day) usage on
  one line, from [claude_rate_limits.py](claude_rate_limits.md). These read the
  `rate_limits` object in the statusLine payload; the Fable-specific weekly bar
  that `/usage` shows is not in that payload and so cannot be rendered.

See [claude_turn_usage.md](claude_turn_usage.md) for the token/cost model
(per-model grouping, `message.id` de-duplication, per-model pricing) and
[claude_rate_limits.md](claude_rate_limits.md) for the rate-limit bars.

The `statusLine` hook pipes one JSON object on stdin, and stdin can only be read
once, so the wrapper captures it and feeds the same payload to each command.
Each command is guarded with `|| true` so a failure in one still lets the
others print.

## Setup

Point the status line at the wrapper in `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "bash /home/wsh/d/s/claude_statusline.bash"
}
```

Restart Claude Code for the change to take effect (the `statusLine` command is
read at startup).

## Requirements

- `ccusage` on `PATH` for the first line (e.g. `bun add -g ccusage`). If the
  status line runs with a `PATH` that lacks it, that line is silently skipped;
  use the absolute path to `ccusage` in the wrapper if needed.
- `python3` for the `⟳` / `Σ` lines and the rate-limit bars. The wrapper calls
  the two `.py` scripts by its own directory, so they work regardless of the
  caller's `PATH`. Each command is guarded with `|| true`, so any one missing
  still lets the others print.

The `⟳` per-turn line alone (no `ccusage` dependency) is available by pointing
`statusLine` directly at `claude_turn_usage.py` — see
[claude_turn_usage.md](claude_turn_usage.md).
