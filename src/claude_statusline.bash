#!/usr/bin/env bash
# [](file:///home/wsh/d/s/claude_statusline.bash)
# [](file:///home/wsh/d/s/claude_turn_usage.py)
#
# Claude Code statusLine wrapper. Emits, in order:
#   ccusage session/block usage                    (ccusage statusline)
#   turn (⟳) and session (Σ) cost + per-model      (claude_turn_usage.py -m --both)
#   subscription rate-limit bars (session / week)  (claude_rate_limits.py)
# The statusLine hook pipes one JSON object on stdin; it can only be read
# once, so capture it and feed the same payload to each command.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
input="$(cat)"

printf '%s' "$input" | ccusage statusline || true
printf '%s' "$input" | python3 "$here/claude_turn_usage.py" -q -m --both || true
printf '%s' "$input" | python3 "$here/claude_rate_limits.py" -q || true
