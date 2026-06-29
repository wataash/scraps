package main

import (
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
	"testing"
	"time"
)

func sha1Hex(b []byte) string {
	sum := sha1.Sum(b)
	return hex.EncodeToString(sum[:])
}

// setup creates a src tree with two unique blobs (one duplicated, one nested)
// and an empty store, returning their paths.
func setup(t *testing.T) (root, src, store string) {
	t.Helper()
	root = t.TempDir()
	src = filepath.Join(root, "src")
	store = filepath.Join(root, "sha1_store")
	mustMkdir(t, filepath.Join(src, "sub"))
	mustMkdir(t, store)
	mustWrite(t, filepath.Join(src, "a.txt"), "AAA")
	mustWrite(t, filepath.Join(src, "sub", "a2.txt"), "AAA") // duplicate of a.txt
	mustWrite(t, filepath.Join(src, "b.txt"), "BBB")
	return root, src, store
}

func mustMkdir(t *testing.T, dir string) {
	t.Helper()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
}

func mustWrite(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

// blobPath returns the sharded store path for a content sha1, matching the
// layout fs_link writes: <store>/<first 2 hex chars>/<sha1>.
func blobPath(store, sum string) string {
	return filepath.Join(store, sum[:2], sum)
}

// blobNames returns the set of blob sha1 names present across all shard
// subdirectories of the store.
func blobNames(t *testing.T, store string) map[string]bool {
	t.Helper()
	shards, err := os.ReadDir(store)
	if err != nil {
		t.Fatal(err)
	}
	names := map[string]bool{}
	for _, s := range shards {
		if !s.IsDir() {
			continue
		}
		es, err := os.ReadDir(filepath.Join(store, s.Name()))
		if err != nil {
			t.Fatal(err)
		}
		for _, e := range es {
			names[e.Name()] = true
		}
	}
	return names
}

// assertSymlink checks that path is a symlink whose target resolves to want.
func assertSymlink(t *testing.T, path, want string) {
	t.Helper()
	fi, err := os.Lstat(path)
	if err != nil {
		t.Fatal(err)
	}
	if fi.Mode()&os.ModeSymlink == 0 {
		t.Fatalf("%s: not a symlink (mode %v)", path, fi.Mode())
	}
	got, err := os.ReadFile(path) // follows the link
	if err != nil {
		t.Fatalf("%s: reading through link: %v", path, err)
	}
	if string(got) != want {
		t.Fatalf("%s: resolved content = %q, want %q", path, got, want)
	}
}

// TestRunRelative is the Go equivalent of the shell functional test below.
/*
t=$(mktemp -d); mkdir -p "$t/src/sub/" "$t/sha1_store/"
cd "$t"
printf AAA > "$t/src/a.txt"        # new
printf AAA > "$t/src/sub/a2.txt"   # duplicate of a.txt
printf BBB > "$t/src/b.txt"        # new
fs_link "$t/src/" "$t/sha1_store/"

find "$t/sha1_store/" -type f      # two <sha1> blobs under <ab> shard dirs
readlink "$t/src/a.txt"            # ../sha1_store/<ab>/<sha1> (relative)
readlink "$t/src/sub/a2.txt"       # ../../sha1_store/<ab>/<sha1> (relative)
cat "$t/src/sub/a2.txt"            # "AAA" (link resolves)
*/
func TestRunRelative(t *testing.T) {
	_, src, store := setup(t)

	if err := run(src, store, false, 4); err != nil {
		t.Fatal(err)
	}

	shaA := sha1Hex([]byte("AAA"))
	shaB := sha1Hex([]byte("BBB"))

	// Store holds exactly the two unique blobs (across shard subdirectories).
	got := blobNames(t, store)
	if len(got) != 2 || !got[shaA] || !got[shaB] {
		t.Fatalf("store blobs = %v, want {%s, %s}", got, shaA, shaB)
	}

	// Blob contents are correct.
	if b, _ := os.ReadFile(blobPath(store, shaA)); string(b) != "AAA" {
		t.Fatalf("blob %s = %q, want AAA", shaA, b)
	}

	// Originals became symlinks that resolve to the right content.
	assertSymlink(t, filepath.Join(src, "a.txt"), "AAA")
	assertSymlink(t, filepath.Join(src, "sub", "a2.txt"), "AAA")
	assertSymlink(t, filepath.Join(src, "b.txt"), "BBB")

	// Targets are relative and correct for their depth, including the shard dir.
	if target, _ := os.Readlink(filepath.Join(src, "a.txt")); target != filepath.Join("..", "sha1_store", shaA[:2], shaA) {
		t.Fatalf("a.txt target = %q, want ../sha1_store/%s/%s", target, shaA[:2], shaA)
	}
	if target, _ := os.Readlink(filepath.Join(src, "sub", "a2.txt")); target != filepath.Join("..", "..", "sha1_store", shaA[:2], shaA) {
		t.Fatalf("sub/a2.txt target = %q, want ../../sha1_store/%s/%s", target, shaA[:2], shaA)
	}
}

func TestRunAbsolute(t *testing.T) {
	_, src, store := setup(t)

	if err := run(src, store, true, 4); err != nil {
		t.Fatal(err)
	}

	shaA := sha1Hex([]byte("AAA"))
	storeAbs, _ := filepath.Abs(store)

	target, err := os.Readlink(filepath.Join(src, "a.txt"))
	if err != nil {
		t.Fatal(err)
	}
	if !filepath.IsAbs(target) {
		t.Fatalf("a.txt target = %q, want absolute", target)
	}
	if want := filepath.Join(storeAbs, shaA[:2], shaA); target != want {
		t.Fatalf("a.txt target = %q, want %q", target, want)
	}
	assertSymlink(t, filepath.Join(src, "a.txt"), "AAA")
}

func TestExistingSymlinkIgnored(t *testing.T) {
	_, src, store := setup(t)

	link := filepath.Join(src, "keep.link")
	if err := os.Symlink("/nonexistent", link); err != nil {
		t.Fatal(err)
	}

	if err := run(src, store, false, 4); err != nil {
		t.Fatal(err)
	}

	target, err := os.Readlink(link)
	if err != nil {
		t.Fatal(err)
	}
	if target != "/nonexistent" {
		t.Fatalf("pre-existing symlink changed: target = %q, want /nonexistent", target)
	}
}

func TestDedupReusesExistingStore(t *testing.T) {
	_, src, store := setup(t)

	// Pre-populate the store with the BBB blob (at its sharded path); run must
	// reuse it (symlink, not re-create) and the store must not gain a duplicate.
	shaB := sha1Hex([]byte("BBB"))
	mustMkdir(t, filepath.Join(store, shaB[:2]))
	mustWrite(t, blobPath(store, shaB), "BBB")

	if err := run(src, store, false, 4); err != nil {
		t.Fatal(err)
	}

	assertSymlink(t, filepath.Join(src, "b.txt"), "BBB")

	if n := len(blobNames(t, store)); n != 2 {
		t.Fatalf("store has %d blobs, want 2 (no duplicate blobs)", n)
	}
}

// TestStaleTempSymlinkReplaced checks that a leftover ".fs_link.tmp" symlink
// from a previously interrupted run does not break the run: symlink no longer
// removes the temp unconditionally, so it must fall back to remove+retry on the
// EEXIST it then hits.
func TestStaleTempSymlinkReplaced(t *testing.T) {
	_, src, store := setup(t)

	// Simulate a stale temp link beside a.txt.
	if err := os.Symlink("/nonexistent", filepath.Join(src, "a.txt.fs_link.tmp")); err != nil {
		t.Fatal(err)
	}

	if err := run(src, store, false, 4); err != nil {
		t.Fatal(err)
	}

	assertSymlink(t, filepath.Join(src, "a.txt"), "AAA")
}

func TestUnexpectedFileTypeErrors(t *testing.T) {
	root := t.TempDir()
	src := filepath.Join(root, "src")
	store := filepath.Join(root, "sha1_store")
	mustMkdir(t, src)
	mustMkdir(t, store)

	fifo := filepath.Join(src, "pipe")
	if err := syscall.Mkfifo(fifo, 0o644); err != nil {
		t.Skipf("cannot create fifo: %v", err)
	}

	if err := run(src, store, false, 4); err == nil {
		t.Fatal("expected error for unexpected file type, got nil")
	}
}

func TestPreservesMtime(t *testing.T) {
	_, src, store := setup(t)

	if !fsSupportsNanoMtime(t, src) {
		t.Skip("filesystem does not preserve sub-second mtime")
	}

	// Give the originals distinct, known mtimes, with non-zero nanoseconds so
	// the test actually exercises nanosecond-precision preservation.
	want := time.Date(2001, 9, 9, 1, 46, 40, 123456789, time.UTC) // 1_000_000_000.123456789
	wantDup := time.Date(2009, 2, 13, 23, 31, 30, 987654321, time.UTC)
	for path, mt := range map[string]time.Time{
		filepath.Join(src, "a.txt"):         want,
		filepath.Join(src, "sub", "a2.txt"): wantDup,
		filepath.Join(src, "b.txt"):         want,
	} {
		if err := os.Chtimes(path, mt, mt); err != nil {
			t.Fatal(err)
		}
	}

	if err := run(src, store, false, 4); err != nil {
		t.Fatal(err)
	}

	// Lstat reads the symlink's own mtime, which must match the original file.
	check := func(path string, mt time.Time) {
		fi, err := os.Lstat(path)
		if err != nil {
			t.Fatal(err)
		}
		if fi.Mode()&os.ModeSymlink == 0 {
			t.Fatalf("%s: not a symlink", path)
		}
		if !fi.ModTime().Equal(mt) {
			t.Fatalf("%s: symlink mtime = %v, want %v", path, fi.ModTime(), mt)
		}
	}
	check(filepath.Join(src, "a.txt"), want)
	check(filepath.Join(src, "sub", "a2.txt"), wantDup) // duplicate keeps its own mtime
	check(filepath.Join(src, "b.txt"), want)
}

func TestPreservesMode(t *testing.T) {
	_, src, store := setup(t)

	// Distinct, non-default modes on the originals.
	if err := os.Chmod(filepath.Join(src, "a.txt"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(filepath.Join(src, "b.txt"), 0o640); err != nil {
		t.Fatal(err)
	}
	// a.txt and sub/a2.txt share content "AAA"; the blob keeps the mode of the
	// OLDEST of them, so make a.txt strictly older to pin the expected mode
	// (otherwise the near-equal setup mtimes leave it order-dependent).
	old := time.Unix(1000000000, 0)
	newer := time.Unix(2000000000, 0)
	if err := os.Chtimes(filepath.Join(src, "a.txt"), old, old); err != nil {
		t.Fatal(err)
	}
	if err := os.Chtimes(filepath.Join(src, "sub", "a2.txt"), newer, newer); err != nil {
		t.Fatal(err)
	}

	if err := run(src, store, false, 4); err != nil {
		t.Fatal(err)
	}

	// The store blob must carry the (oldest) original file's permission bits.
	want := map[string]os.FileMode{
		sha1Hex([]byte("AAA")): 0o755,
		sha1Hex([]byte("BBB")): 0o640,
	}
	for sum, mode := range want {
		fi, err := os.Lstat(blobPath(store, sum))
		if err != nil {
			t.Fatal(err)
		}
		if fi.Mode().Perm() != mode {
			t.Fatalf("blob %s: mode = %o, want %o", sum, fi.Mode().Perm(), mode)
		}
	}
}

// TestBlobAdoptsOldest checks that a blob shared by several source files ends up
// with the mtime and permission bits of the OLDEST of them, regardless of the
// order they are walked in.
func TestBlobAdoptsOldest(t *testing.T) {
	root := t.TempDir()
	src := filepath.Join(root, "src")
	store := filepath.Join(root, "sha1_store")
	mustMkdir(t, filepath.Join(src, "sub"))
	mustMkdir(t, store)

	// Three copies of the same content; the middle-named one is the oldest, so
	// it is neither first nor last in the walk order.
	files := map[string]struct {
		mode os.FileMode
		mt   time.Time
	}{
		"a.txt":     {0o600, time.Unix(1234567890, 0).UTC()}, // 2009-02-13
		"m.txt":     {0o644, time.Unix(1000000000, 0).UTC()}, // 2001-09-09, oldest (1e9)
		"sub/z.txt": {0o755, time.Unix(2000000000, 0).UTC()}, // 2033-05-18 (2e9)
	}
	for name, meta := range files {
		p := filepath.Join(src, name)
		mustWrite(t, p, "AAA")
		if err := os.Chmod(p, meta.mode); err != nil {
			t.Fatal(err)
		}
		if err := os.Chtimes(p, meta.mt, meta.mt); err != nil {
			t.Fatal(err)
		}
	}

	if err := run(src, store, false, 4); err != nil {
		t.Fatal(err)
	}

	blob := blobPath(store, sha1Hex([]byte("AAA")))
	fi, err := os.Lstat(blob)
	if err != nil {
		t.Fatal(err)
	}
	oldest := files["m.txt"]
	if !fi.ModTime().Equal(oldest.mt) {
		t.Fatalf("blob mtime = %v, want %v (oldest source)", fi.ModTime(), oldest.mt)
	}
	if fi.Mode().Perm() != oldest.mode {
		t.Fatalf("blob mode = %o, want %o (oldest source)", fi.Mode().Perm(), oldest.mode)
	}
}

// TestConcurrentDedup stresses the parallel blob-coordination protocol with many
// files sharing a few contents at high concurrency: each unique content must end
// up as exactly one blob, every original must become a resolvable symlink, and
// the blob must still carry the OLDEST mtime among its sources. Run under -race
// this also guards the sha1s map / blob handshake against data races.
func TestConcurrentDedup(t *testing.T) {
	root := t.TempDir()
	src := filepath.Join(root, "src")
	store := filepath.Join(root, "sha1_store")
	mustMkdir(t, src)
	mustMkdir(t, store)

	const contents = 5
	const perContent = 40
	oldestMt := make(map[int]time.Time)
	for c := 0; c < contents; c++ {
		for i := 0; i < perContent; i++ {
			p := filepath.Join(src, fmt.Sprintf("c%d_f%d", c, i))
			mustWrite(t, p, fmt.Sprintf("content-%d", c))
			// Spread mtimes; the minimum per content is what the blob must keep.
			mt := time.Unix(1_000_000_000+int64(i*1000), 0).UTC()
			if err := os.Chtimes(p, mt, mt); err != nil {
				t.Fatal(err)
			}
			if cur, ok := oldestMt[c]; !ok || mt.Before(cur) {
				oldestMt[c] = mt
			}
		}
	}

	if err := run(src, store, false, 16); err != nil {
		t.Fatal(err)
	}

	// Exactly one blob per unique content.
	if n := len(blobNames(t, store)); n != contents {
		t.Fatalf("store has %d blobs, want %d (one per content)", n, contents)
	}

	for c := 0; c < contents; c++ {
		want := fmt.Sprintf("content-%d", c)
		// Every source for this content resolves through its symlink.
		for i := 0; i < perContent; i++ {
			assertSymlink(t, filepath.Join(src, fmt.Sprintf("c%d_f%d", c, i)), want)
		}
		// The blob keeps the oldest mtime among the sources.
		fi, err := os.Lstat(blobPath(store, sha1Hex([]byte(want))))
		if err != nil {
			t.Fatal(err)
		}
		if !fi.ModTime().Equal(oldestMt[c]) {
			t.Fatalf("content %d: blob mtime = %v, want %v (oldest)", c, fi.ModTime(), oldestMt[c])
		}
	}
}

// TestPreservedTimesNotCurrent guards the atomic time installation: both the new
// blob and the symlink must end up with the original file's (old) mtime, never
// the current time. The times are set on the temp objects before they are
// renamed into place, so a successful run can never leave a "now" stamp; this
// test fails if that ordering regresses and a stamp is left unset (= ~now).
func TestPreservedTimesNotCurrent(t *testing.T) {
	_, src, store := setup(t)

	old := time.Unix(1000000000, 0).UTC() // 2001-09-09, safely far from now
	bPath := filepath.Join(src, "b.txt")  // "BBB", unique content
	if err := os.Chtimes(bPath, old, old); err != nil {
		t.Fatal(err)
	}

	if err := run(src, store, false, 4); err != nil {
		t.Fatal(err)
	}

	// The symlink that replaced b.txt carries the original mtime.
	linkFi, err := os.Lstat(bPath)
	if err != nil {
		t.Fatal(err)
	}
	if linkFi.Mode()&os.ModeSymlink == 0 {
		t.Fatalf("%s: not a symlink", bPath)
	}
	if !linkFi.ModTime().Equal(old) {
		t.Fatalf("symlink mtime = %v, want %v (must not be ~now)", linkFi.ModTime(), old)
	}

	// The freshly created blob carries the original mtime too (not copy time).
	blobFi, err := os.Lstat(blobPath(store, sha1Hex([]byte("BBB"))))
	if err != nil {
		t.Fatal(err)
	}
	if !blobFi.ModTime().Equal(old) {
		t.Fatalf("blob mtime = %v, want %v (must not be copy time)", blobFi.ModTime(), old)
	}
}

// fsSupportsNanoMtime reports whether the filesystem holding dir preserves
// sub-second (nanosecond) modification times, so the nanosecond assertions can
// be skipped on filesystems with coarser granularity rather than failing.
func fsSupportsNanoMtime(t *testing.T, dir string) bool {
	t.Helper()
	probe := filepath.Join(dir, ".ns_probe")
	mustWrite(t, probe, "x")
	defer os.Remove(probe)
	mt := time.Date(2001, 9, 9, 1, 46, 40, 123456789, time.UTC)
	if err := os.Chtimes(probe, mt, mt); err != nil {
		t.Fatal(err)
	}
	fi, err := os.Lstat(probe)
	if err != nil {
		t.Fatal(err)
	}
	return fi.ModTime().Nanosecond() == mt.Nanosecond()
}

func TestSha1Reader(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "f")
	mustWrite(t, path, "hello")

	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()

	got, err := sha1Reader(f, make([]byte, 128*1024))
	if err != nil {
		t.Fatal(err)
	}
	if want := sha1Hex([]byte("hello")); got != want {
		t.Fatalf("sha1Reader = %q, want %q", got, want)
	}
}
