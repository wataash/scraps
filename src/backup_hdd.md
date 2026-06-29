# backup_hdd.py

[backup_hdd.py](backup_hdd.py)

rsync `/` to an external HDD mounted under `/mnts/{target}/`.

Two rsync operations:

1. important files only (`IMPORTANT_FILES`), `--delete`
2. full tree minus `EXCLUDES`, `--delete --delete-excluded`

Both use `-@-1` (`--modify-window=-1`) to compare mtimes with nanosecond precision.

Subcommands:

- `backup_hdd` — run the backup.
- `list_diff` — list what would change vs the backup HDD (rsync `-i` itemize, dry-run).
- `list_included` — list the files that *would* be backed up (rsync `--list-only`, dry-run).
- `list_excluded` — list the real on-disk files dropped by op2 (the full backup).

## Usage

```
backup_hdd.py backup_hdd [-n] [-c] [--rsync_dry_run] [--bwlimit=RATE] [--ops=OPS] {e14|e15}
```

```bash
# preview the commands (script-level dry-run)
backup_hdd.py backup_hdd -n --ops=1,2 --bwlimit=100M e14 | pr

# actually run
sudo -v
sudo backup_hdd.py backup_hdd --ops=1,2 --bwlimit=100M e14 | pr
# logs: ~/logs/backup.${target}.$(date +%F).log
```

## List diff

Show what would change if you ran the backup now, without writing anything. Runs the
same op1/op2 rsync commands as `backup_hdd`, but forced to rsync `--dry-run` with `-i`
(`--itemize-changes`), so each would-be change is printed as one itemize line —
including `*deleting` lines for entries `--delete` / `--delete-excluded` would remove
from the destination. Use `-c` to compare by xxh3 checksum instead of size/mtime.

Output goes to stdout (no backup log). Like the backup, traversing the whole tree
needs root, so run it under `sudo`.

```bash
# preview the commands (script-level dry-run)
backup_hdd.py list_diff -n e14 | pr

# list the diff
sudo backup_hdd.py list_diff e14 | pr
```

## List included files

List the files that *would* be backed up — every source entry that passes each op's
filter rules. Runs the same op1/op2 rsync commands as `backup_hdd`, but with rsync
`--list-only` (and `--dry-run`), so each matching entry is printed as one listing line
(`<perms> <size> <mtime> <path>`) and nothing is written. Use `--ops` to list a single
op (op1 = `IMPORTANT_FILES`; op2 = the full tree minus `EXCLUDES` / `EXCLUDES_GENERIC`).

`--list-only` ignores the destination, so the backup HDD does not need to be mounted.
Output goes to stdout (no backup log). Traversing the whole tree (op2) needs root, so
run it under `sudo`.

```bash
# preview the commands (script-level dry-run)
backup_hdd.py list_included -n e14 | pr

# list the files that would be backed up
sudo backup_hdd.py list_included e14 | pr
```

## List excluded files

List the real on-disk files that op2 (the full backup) drops — `EXCLUDES` /
`EXCLUDES_GENERIC`, also deleted from the destination by `--delete-excluded` — using
the same filter rules as the backup (so the output reflects exactly what is *not*
backed up). Useful for auditing the exclude lists. (op1 is not listed: it includes
only `IMPORTANT_FILES`, so its exclude set is "almost everything".)

It runs `rsync -n --dry-run --list-only --debug=FILTER`, using op2's
filter rules. rsync prints `[sender] hiding <file|directory> <path> because of
pattern <pat>` for each excluded path; it does not descend into an excluded
directory, so this is one line per excluded entry, not per leaf file. The output is
the absolute full path of each excluded entry (source-prefixed, pattern stripped);
directories get a trailing slash:

```
/home/wsh/proj/node_modules/
/sys/
```

Like the backup, traversing the whole tree needs root, so run it under `sudo`.

```bash
# preview the commands (script-level dry-run)
backup_hdd.py list_excluded -n e14 | pr

# list excluded entries
sudo backup_hdd.py list_excluded e14 | pr
```

## Options (`backup_hdd`)

`list_diff` takes `target`, `-n`/`--dry_run`, `--force-dry-run`, `-c`/`--checksum`, and
`--ops`. `list_included` takes `target`, `-n`/`--dry_run`, and `--ops`. `list_excluded`
takes only `target` and `-n`/`--dry_run`.

| Option | Description |
| --- | --- |
| `target` | `e14` or `e15` (HDD mounted at `/mnts/{target}/`) |
| `-n`, `--dry_run` | print commands without executing them (script-level) |
| `--force-dry-run` | continue dry-run printing even when prechecks fail (requires `-n`) |
| `-c`, `--checksum` | rsync checksum compare with xxh3; implies `--rsync_dry_run` |
| `--rsync_dry_run` | add rsync's own `--dry-run`: rsync runs but transfers nothing |
| `--bwlimit RATE` | limit rsync transfer rate, e.g. `100M` |
| `--ops OPS` | comma-separated rsync operation numbers to run: `1,2` (default both) |
