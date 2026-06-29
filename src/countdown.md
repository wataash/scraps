# countdown.py

[countdown.py](countdown.py)

Counts down from the given duration to 1, printing each remaining second on the
same line (`5 4 3 2 1`) with a 1-second sleep between updates, then a trailing
newline.

## Usage

```sh
python countdown.py 300
python countdown.py '3hour 4min 5sec'
```

The duration argument accepts either a plain integer (seconds) or any string
that GNU `date(1)` understands as a relative time. Non-integer values are
resolved by invoking `date -d '19700101 <value>' -u +%s`, so the host needs GNU
date on `$PATH`.

## Options

| Option       | Description                                          |
| ------------ | ---------------------------------------------------- |
| `duration`   | Seconds (`300`) or GNU date(1) style (`3min 5sec`).  |
| `-h, --help` | Show help and exit.                                  |
