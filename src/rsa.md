# rsa

[rsa](rsa)

`rsa` mirrors a local path to the same path on a remote host with `rsync`.
The `rs` means `rsync`; the `a` has no meaning and is only there because `rsa` is easy to type.

## Usage

```bash
rsa [OPTIONS] HOST PATH
```

Examples:

```bash
rsa    172.31.5.200 /a/b           # rsync -aAHSX -hPv --info=progress2 /a/b 172.31.5.200:/a/b
rsa    172.31.5.200 /a/b/          # rsync -aAHSX -hPv --info=progress2 /a/b/ 172.31.5.200:/a/b/
rsa    172.31.5.200 a/b            # rsync -aAHSX -hPv --info=progress2 $PWD/a/b 172.31.5.200:$PWD/a/b
rsa    172.31.5.200 a/b/           # rsync -aAHSX -hPv --info=progress2 $PWD/a/b/ 172.31.5.200:$PWD/a/b/
rsa    172.31.5.200 ../a/b         # rsync -aAHSX -hPv --info=progress2 $(realpath ../a/b) 172.31.5.200:$(realpath ../a/b)
rsa    172.31.5.200 ../a/b/        # rsync -aAHSX -hPv --info=progress2 $(realpath ../a/b)/ 172.31.5.200:$(realpath ../a/b)/
rsa    172.31.5.200 ./             # rsync -aAHSX -hPv --info=progress2 $PWD/ 172.31.5.200:$PWD/
rsa -d 172.31.5.200 /a/b           # rsync --mkpath -aAHSX -hPv --info=progress2 /a/b 172.31.5.200:/a/b
rsa -r 172.31.5.200 /path/to/file  # rsync -aAHSX -hPv --info=progress2 172.31.5.200:/path/to/file /path/to/file
rsa -p 2222 172.31.5.200 /a/b      # rsync -e 'ssh -p 2222' -aAHSX -hPv --info=progress2 /a/b 172.31.5.200:/a/b
```

## Options

| Option | Description |
| --- | --- |
| `-d`, `--make_dest_dirs` | Pass `--mkpath` to `rsync` so destination path directories are created. |
| `-r`, `--reverse` | Reverse direction: copy from `HOST:PATH` to the local mirrored path. |
| `-n`, `--dry_run` | Print the generated `rsync` command and do not execute it. |
| `-p`, `--port` PORT | Pass `-e 'ssh -p PORT'` to `rsync` to use a non-default ssh port. |
| `-h`, `--help` | Show help. |

## Path rules

Absolute paths are used as-is. Paths under the current directory are expanded as `$PWD/path`.
Parent-relative paths such as `../a` are expanded with `realpath`. A trailing slash on the input path is preserved.
