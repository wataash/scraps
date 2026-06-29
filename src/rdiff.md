# rdiff.py

[rdiff.py](rdiff.py)

Always-dry-run `rsync` wrapper. Runs:

```
rsync -n -aAHSX --delete -@-1 -i SRC... DST
```

`-n` is hardcoded, so it never modifies the destination — it only previews what
would be transferred. Useful as a quick "what would change?" check.

## Usage

```bash
python rdiff.py src/ dst/        # rsync -n -aAHSX --delete -@-1 -i src/ dst/
python rdiff.py -ii src/ dst/    # rsync -n -aAHSX --delete -@-1 -ii src/ dst/
python rdiff.py -c src/ dst/     # rsync -n -aAHSX --delete -@-1 -i -c src/ dst/
python rdiff.py -n src/ dst/     # only print the rsync command, do not run
python rdiff.py src1/ src2/ dst/ # multiple SRC, last PATH is DST
```

Fixed rsync flags: `-n` (dry run), `-aAHSX` (archive + ACLs/hardlinks/sparse/xattrs),
`--delete` (delete extraneous files on DST), `-@-1` (exact mtime comparison).

## Options

| Option              | Description                                                      |
| ------------------- | ---------------------------------------------------------------- |
| `-i`, `--itemize`   | itemize-changes verbosity; `-i` (default) or `-ii` (pass twice). |
| `-c`, `--checksum`  | pass rsync `-c` (skip based on checksum, not mod-time & size).    |
| `-n`, `--dry_run`   | only print the rsync command, do not execute it.                 |
| `PATH ...`          | one or more SRC followed by a single DST (rsync semantics).      |

Note: `-n`/`--dry_run` controls only whether *this wrapper* runs rsync; the
generated rsync command is itself always a dry run (`rsync -n`).
