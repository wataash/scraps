# adb_pull.py

[adb_pull.py](adb_pull.py)

## `diff_dir REMOTE_DIR LOCAL_DIR`

Compare every regular file in the remote directory (on an Android device, via
`adb`) against the local directory, and print the shell command needed to bring
each differing file into sync. Prints only; pipe to `sh` to run.

```sh
adb_pull.py diff_dir sdcard/DCIM/Camera/ ./
adb_pull.py diff_dir sdcard/DCIM/Camera/ ./ | sh
```

The printed command depends on what differs (comment lists `attr:REMOTE:LOCAL`
for the differing attributes, in the order `mode size mdate`):

```
adb pull -a REMOTE ./ && chmod MODE ./FILE && touch -d '@epoch.frac' ./FILE  # new
chmod 770 ./FILE                                                             # mode:770:600
touch -d '@1776749837.811573786' ./FILE                                      # mdate:2026-04-21.14:37:17.811573786:2000-01-02.12:04:05.000000000
chmod 770 ./FILE && touch -d '@...' ./FILE                                   # mode:770:600 mdate:...
adb pull -a REMOTE ./ && chmod MODE ./FILE && touch -d '@...' ./FILE         # mode:.. size:.. mdate:..
```

- **missing locally (`# new`) or size differs**: the content must be
  transferred, so `adb pull -a` runs, followed by `chmod` + `touch`.
- **only `mode` differs**: just `chmod`.
- **only `mdate` differs**: just `touch`.
- **`mode` and `mdate` differ (same size)**: `chmod && touch`, no transfer.
- **all attributes match**: nothing is printed.

## Why chmod / touch

`adb pull -a` restores the mode but only second-resolution mtime, so `touch`
reapplies the device's exact nanosecond mtime afterwards. `@epoch.frac` is
timezone-independent and was verified to round-trip bit-exact against `stat` on
the device, so `mdate` is compared at full nanosecond precision — once a file is
synced it reports no diff and is never re-pulled.

When only attributes (not content) differ, `chmod`/`touch` fix them locally
without re-downloading.

## Notes

- Remote attributes come from one `adb shell stat -c ...` call over the dir glob;
  only regular files are considered (subdirectories are skipped).
