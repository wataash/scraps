# fs_link

Deduplicates a file tree by content (SHA1), replacing each original location
with a symlink.

## Usage

```sh
fs_link [--absolute] [--jobs n] <dir> <dirSHA1>
```

- `<dir>`: the tree to deduplicate.
- `<dirSHA1>`: store directory that holds the content blobs (created if it does
  not exist). Blobs are **sharded** by the first two hex characters of their
  sha1: a blob lives at `<dirSHA1>/<ab>/<sha1>` (see *Store layout*).
- `--absolute`: write absolute symlink targets. **Relative by default**
  (relative to the symlink's own location).
- `--jobs n`: number of files to process concurrently (default: number of
  CPUs). Use `--jobs 1` for fully sequential processing. See *Concurrency*.

```sh
fs_link /data/ /sha1_store/             # run with relative links
fs_link --absolute /data/ /sha1_store/
fs_link --jobs 1 /data/ /sha1_store/    # sequential
```

## Behavior

Walks `<dir>` recursively and handles each entry by type:

- **Regular file**: computes its SHA1.
  - New content (SHA1 not in the store): copies the file to its blob path
    `<dirSHA1>/<ab>/<sha1>`, then replaces the original path with a symlink to it.
  - Duplicate content (SHA1 already present): drops the copy and replaces the
    original path with a symlink to the existing blob.
- **Directory**: recurses into it.
- **Existing symlink**: ignored.
- **Any other type**: exits with an error.

As a result, identical content is stored once in the store, and every original
location becomes a symlink pointing at that single blob.

### Store layout

Blobs are sharded into subdirectories named by the first two hex characters of
the sha1, so a blob lives at `<dirSHA1>/<ab>/<sha1>` (e.g.
`<dirSHA1>/60/606ec6e9…`). All 256 shard directories are created up front. This
keeps any single directory small and, more importantly, spreads concurrent blob
creation across directories so workers do not all contend on one directory's
inode lock (see *Concurrency*). The shard prefix is purely derived from the
sha1; nothing else about the blob changes.

### Concurrency

Files are processed by a pool of `--jobs` workers; directory traversal itself
stays single-threaded (it only feeds file paths to the workers). The work is
I/O- and syscall-bound, so concurrency mainly overlaps `symlink`/`rename`/`stat`
latency — the speedup depends on the underlying storage.

The outcome does not depend on processing order. For each content the first
worker to reach it creates the single store blob; other workers that hit the
same content wait until that blob exists before linking to it, so a blob is
never observed half-written and identical content is never stored twice. The
"oldest mtime/permissions wins" rule (see *Timestamps* / *Permissions*) is
order-independent and therefore unaffected by the number of jobs.

### Link target resolution

- Default (relative): the symlink target is the path from the symlink's own
  directory to the store blob, e.g.
  `src/sub/a.txt -> ../../sha1_store/<ab>/<sha1>`. Moving the whole tree keeps
  the links valid as long as the relative position of `<dir>` and `<dirSHA1>` is
  preserved.
- `--absolute`: the symlink target is the absolute path of the store blob.

### Timestamps

The original file's modification time (and access time) is preserved onto the
replacement symlink, so a directory listing keeps reflecting the original file
dates after deduplication. The time is set on the symlink itself (without
following it), leaving the shared store blob's own timestamp untouched.

This preservation is **atomic**: the times are applied to the temporary link
(and, for a new blob, the temporary file) *before* it is renamed into place, so
the published symlink/blob already carries the correct times. An interruption
(e.g. `^C`) therefore never leaves a symlink stamped with the current time.

A store blob (`<dirSHA1>/<sha1>`) takes the **oldest** modification time among
all source files that share its content: the first file stored sets the blob's
mtime/atime, and each later duplicate lowers them if it is older. So the blob
ends up with the earliest date seen for that content. (The blob's access time
follows the same oldest file.)

### Permissions

A store blob takes the **permission bits of the oldest** source file that shares
its content (the same file that determines its mtime, above); umask does not
apply. The first file stored sets the mode, and a later duplicate overrides it
only when that duplicate is older. Other files' modes are not recorded. Symlink
permission bits themselves are not meaningful on Linux (a symlink always reports
`lrwxrwxrwx`), so access is governed by the blob's mode — in particular the
execute bit is carried on the blob, so an executable file stays executable
through its symlink.

### Crash safety

For **new content**, the file is copied into the store (written to a temp name
and renamed into place, so a store blob never appears half-written) while the
original is left in place; the symlink replacement then removes the original
atomically. At every instant the original path holds either the real file or
the symlink, so an interruption (e.g. `^C`) loses nothing — at the cost of
temporarily holding both the original and the store copy on disk.

Duplicate content is handled the same way: the original is only ever removed by
the atomic symlink replacement, never unlinked beforehand.

### Atomicity

Each symlink is created under a temporary name in the same directory and then
renamed over the real path, so the target path is never momentarily missing.
This avoids the partial-state hazard of unlinking the original first and being
interrupted before the symlink is created (leaving the path gone).

## Notes / limitations

- Deduplication is by **content** (SHA1); empty files and other identical
  content collapse to a single blob.
- Existing filenames in the store `<dirSHA1>` are treated as SHA1s and loaded
  as the known set at startup.
- Since blobs are shared, editing through a link affects every location that
  had the same content — keep this in mind before writing through a link.
- Currently a single command equivalent to deduplicating with symlinks. A
  hard-link variant (store the blob and hard-link the originals) is a natural
  extension; adding it would call for a subcommand structure.
