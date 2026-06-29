# fish_history.py

[fish_history.py](fish_history.py)

Parses a fish shell history file.

## Subcommands

### plot

Plots accumulated command count over time (x-axis: date, y-axis: cumulative commands).

```sh
fish_history.py plot
fish_history.py plot --history ~/.local/share/fish/fish_history
fish_history.py plot --output out.png
```

| Option           | Description                                                      |
| ---------------- | ---------------------------------------------------------------- |
| `--history PATH` | Path to `fish_history` file. Default: `~/.local/share/fish/fish_history` |
| `--output PATH`  | Save plot to file (PNG/PDF/…) instead of opening an interactive window. |

### extract

Extracts entries on or after `--since` and writes them as a new fish history file.

```sh
fish_history.py extract --since '2024-01-01T00:00:00+09:00' -o /tmp/fish_history_recent
fish_history.py extract --history ~/.local/share/fish/fish_history --since '2024-01-01T00:00:00+09:00' -o /tmp/fish_history_recent
```

| Option           | Description                                                      |
| ---------------- | ---------------------------------------------------------------- |
| `--history PATH` | Path to `fish_history` file. Default: `~/.local/share/fish/fish_history` |
| `--since DATETIME` | ISO 8601 datetime with timezone (required). Entries with `when` ≥ this value are extracted. |
| `-o OUTPUT`      | Output file path (required).                                     |

### merge

Merges two fish history files with deduplication, sorted by `when`.

Rules applied in order:
1. **(cmd, when) exact duplicates** → kept once
2. **Same cmd, different when** → only the newest `when` entry is kept
3. **Same when, different cmd** → FILE_A entry comes first, FILE_B entry second

```sh
fish_history.py merge -o /tmp/merged FILE_A FILE_B
fish_history.py merge -o /tmp/merged ~/.local/share/fish/fish_history /tmp/old_fish_history_recent
```

| Option        | Description              |
| ------------- | ------------------------ |
| `FILE_A`      | First history file (positional, takes priority on ties). |
| `FILE_B`      | Second history file (positional). |
| `-o OUTPUT`   | Output file path (required). |
