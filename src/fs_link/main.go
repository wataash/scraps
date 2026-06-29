// Command fs_link deduplicates a directory tree by file content.
//
// It walks <dir>; for every regular file it computes the SHA1 of the contents:
//
//   - new content: the file is copied to <dirSHA1>/<sha1>, then the original
//     path is atomically replaced with a symlink to it.
//   - duplicate content: the original path is replaced with a symlink to the
//     existing <dirSHA1>/<sha1>.
//
// Directories are recursed into; existing symlinks are skipped; any other file
// type is an error.
//
// Symlink targets are relative by default (resolved from the symlink's own
// location); pass --absolute for absolute targets. Files are processed by a
// pool of --jobs workers (default: NumCPU); the result is order-independent.
//
// Usage:
//
//	fs_link [--absolute] [--jobs n] <dir> <dirSHA1>
package main

import (
	"crypto/sha1"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"runtime/pprof"
	"sync"
	"sync/atomic"
	"syscall"

	"golang.org/x/sys/unix"
)

func main() {
	// log.SetFlags(0)

	absolute := flag.Bool("absolute", false, "write absolute symlink targets (default: relative)")
	jobs := flag.Int("jobs", runtime.NumCPU(), "number of files to process concurrently")
	cpuprofile := flag.String("cpuprofile", "", "write a CPU profile to `file`")
	memprofile := flag.String("memprofile", "", "write a memory profile to `file`")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "usage: %s [--absolute] [--jobs n] [--cpuprofile file] [--memprofile file] <dir> <dirSHA1>\n", filepath.Base(os.Args[0]))
		flag.PrintDefaults()
	}
	flag.Parse()
	if flag.NArg() != 2 {
		flag.Usage()
		os.Exit(2)
	}

	if *cpuprofile != "" {
		f, err := os.Create(*cpuprofile)
		if err != nil {
			log.Fatalf("create cpu profile: %v", err)
		}
		if err := pprof.StartCPUProfile(f); err != nil {
			log.Fatalf("start cpu profile: %v", err)
		}
	}

	// stopProfiling flushes the CPU profile and writes the heap profile. It must
	// be called on every exit path, including ^C, because Go does not run defers
	// when a signal terminates the process. It is idempotent.
	stopProfiling := func() {
		if *cpuprofile != "" {
			pprof.StopCPUProfile() // flushes the buffered CPU profile to the file
		}
		if *memprofile != "" {
			f, err := os.Create(*memprofile)
			if err != nil {
				log.Printf("create mem profile: %v", err)
				return
			}
			defer f.Close()
			runtime.GC()
			if err := pprof.WriteHeapProfile(f); err != nil {
				log.Printf("write mem profile: %v", err)
			}
		}
	}

	// On SIGINT/SIGTERM, write out whatever profile we have so far, then exit.
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	go func() {
		sig := <-sigCh
		log.Printf("received %v, writing profiles and exiting", sig)
		stopProfiling()
		os.Exit(130)
	}()

	if err := run(flag.Arg(0), flag.Arg(1), *absolute, *jobs); err != nil {
		stopProfiling()
		log.Fatalf("error: %v", err)
	}
	stopProfiling()
}

func run(dir, dirSHA1 string, absolute bool, jobs int) error {
	if jobs < 1 {
		jobs = 1
	}
	if err := os.MkdirAll(dirSHA1, 0o755); err != nil {
		return err
	}

	dirSHA1Abs, err := filepath.Abs(dirSHA1)
	if err != nil {
		return err
	}

	l := &linker{
		dirSHA1:    dirSHA1,
		dirSHA1Abs: dirSHA1Abs,
		absolute:   absolute,
		sha1s:      map[string]*blob{},
		work:       make(chan string, jobs*2),
	}

	// Pre-create the 256 shard directories (<dirSHA1>/<2 hex chars>) and seed the
	// known-sha1 set from blobs already present in them. Sharding by sha1 prefix
	// spreads blob creation across directories, so concurrent renames into the
	// store no longer all contend on a single directory's inode lock. The blobs
	// already exist on disk, so their "ready" is closed immediately.
	for _, sh := range shardNames() {
		shardDir := filepath.Join(dirSHA1, sh)
		if err := os.MkdirAll(shardDir, 0o755); err != nil {
			return err
		}
		es, err := os.ReadDir(shardDir)
		if err != nil {
			return err
		}
		for _, e := range es {
			b := &blob{ready: make(chan struct{})}
			close(b.ready)
			l.sha1s[e.Name()] = b
		}
	}

	for i := 0; i < jobs; i++ {
		l.wg.Add(1)
		go l.worker()
	}
	walkErr := l.walk(dir) // producer: feeds file paths to the workers
	close(l.work)
	l.wg.Wait()

	if walkErr != nil {
		return walkErr
	}
	if l.err != nil {
		return l.err
	}
	log.Println("done")
	return nil
}

// shardLen is the number of leading sha1 hex characters used as the store
// subdirectory name, giving 16^shardLen shards (shardLen=2 -> 256).
const shardLen = 2

// shardNames returns every possible shard directory name ("00".."ff").
func shardNames() []string {
	const hexDigits = "0123456789abcdef"
	names := make([]string, 0, len(hexDigits)*len(hexDigits))
	for i := 0; i < len(hexDigits); i++ {
		for j := 0; j < len(hexDigits); j++ {
			names = append(names, string([]byte{hexDigits[i], hexDigits[j]}))
		}
	}
	return names
}

type linker struct {
	dirSHA1    string
	dirSHA1Abs string
	absolute   bool

	work chan string    // file paths from the walker to the workers
	wg   sync.WaitGroup // worker goroutines

	mu    sync.Mutex       // guards sha1s and serializes adoptIfOlder
	sha1s map[string]*blob // content sha1 -> store blob state

	errFlag atomic.Bool // set once any worker fails; read concurrently
	errOnce sync.Once
	err     error // first worker error; read only in run after wg.Wait
}

// blob tracks one content-addressed store entry across concurrent workers. The
// first worker to see a sha1 creates the entry and the blob file, then closes
// ready (with err set on failure); duplicates wait on ready before touching the
// blob, so they never observe a half-written store file.
type blob struct {
	ready chan struct{}
	err   error // set by the creator before closing ready; read-only afterwards
}

// fail records the first worker error; subsequent ones are dropped. It also
// signals (via errFlag) the producer and other workers to stop.
func (l *linker) fail(err error) {
	l.errOnce.Do(func() { l.err = err })
	l.errFlag.Store(true)
}

func (l *linker) failed() bool { return l.errFlag.Load() }

func (l *linker) worker() {
	defer l.wg.Done()
	buf := make([]byte, 128*1024) // per-worker copy buffer (no shared state)
	for path := range l.work {
		if l.failed() { // best-effort early drain once something failed
			continue
		}
		if err := l.handleFile(path, buf); err != nil {
			l.fail(err)
		}
	}
}

// walk is the producer: it recurses dir and sends regular-file paths to the
// workers. Directory reads stay single-threaded (cheap); the per-file work runs
// on the worker pool.
func (l *linker) walk(dir string) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}
	for _, e := range entries {
		if l.failed() { // a worker failed; stop producing
			return nil
		}
		path := filepath.Join(dir, e.Name())
		switch typ := e.Type(); {
		case typ.IsRegular():
			l.work <- path
		case typ.IsDir():
			log.Printf("walk into %s", path)
			if err := l.walk(path); err != nil {
				return err
			}
		case typ&fs.ModeSymlink != 0:
			// ignore existing symbolic links
		default:
			return fmt.Errorf("unexpected file type: %s (%s)", path, typ)
		}
	}
	return nil
}

func (l *linker) handleFile(path string, buf []byte) error {
	// Open the file once and reuse the descriptor for stat, hashing and the copy
	// into the store. This saves a separate Lstat and a second open per file.
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	// fstat the open fd rather than Lstat-ing the path; the entry is a regular
	// file (walk dispatches on type), so this equals lstat. It captures the
	// original timestamps before the file is replaced, for the symlink below.
	fi, err := f.Stat()
	if err != nil {
		return err
	}

	sum, err := sha1Reader(f, buf)
	if err != nil {
		return err
	}
	storePath := l.storePath(sum)

	// Decide, under the lock, whether this worker creates the blob or reuses an
	// existing/in-flight one. Only the map operation is locked; the slow copy
	// happens after releasing it.
	l.mu.Lock()
	b, exists := l.sha1s[sum]
	if !exists {
		b = &blob{ready: make(chan struct{})}
		l.sha1s[sum] = b
	}
	l.mu.Unlock()

	if !exists {
		// New content: this worker owns the blob. Copy it into the store,
		// leaving the original in place; the atomic replace below removes it, so
		// the original path is never momentarily missing. The blob takes this
		// file's permission bits and times; later duplicates may lower them to
		// an older file's (see adoptIfOlder).
		if _, err := f.Seek(0, io.SeekStart); err != nil { // rewind after hashing
			b.err = err
			close(b.ready)
			return err
		}
		err := copyToStore(f, storePath, fi)
		b.err = err
		close(b.ready) // publish: waiters may now touch the blob
		if err != nil {
			return err
		}
	} else {
		// Duplicate content: wait until the blob exists, then keep it reflecting
		// the OLDEST source seen for this content. adoptIfOlder is serialized so
		// concurrent duplicates apply the min mtime/mode deterministically.
		<-b.ready
		if b.err != nil {
			return fmt.Errorf("store blob %s: %w", sum, b.err)
		}
		l.mu.Lock()
		err := adoptIfOlder(storePath, fi)
		l.mu.Unlock()
		if err != nil {
			return err
		}
	}

	// symlink also installs the preserved mtime/atime atomically with the link.
	return l.symlink(storePath, path, fi)
}

// symlink atomically replaces path with a symlink pointing at storePath, with
// the original file's mtime/atime (taken from fi) already applied. The link is
// created under a temporary name in the same directory, has its times set, and
// is then renamed over path. So path is never left missing (addressing the
// partial-state hazard noted in the original TypeScript implementation), and it
// never appears with a current-time stamp: an interruption leaves either the
// original file or the finished symlink, never a half-set intermediate.
func (l *linker) symlink(storePath, path string, fi os.FileInfo) error {
	target, err := l.linkTarget(storePath, path)
	if err != nil {
		return err
	}

	tmp := path + ".fs_link.tmp"
	if err := os.Symlink(target, tmp); err != nil {
		// A stale temp link from a previously interrupted run on this exact path
		// is the only expected cause; clear it and retry. Avoiding an
		// unconditional Remove saves one syscall per file in the common case.
		if !errors.Is(err, fs.ErrExist) {
			return err
		}
		log.Printf("removing stale temp link from a previous interrupted run: %s", tmp)
		if err := os.Remove(tmp); err != nil {
			return err
		}
		if err := os.Symlink(target, tmp); err != nil {
			return err
		}
	}
	// Set the preserved times on the temp link before publishing it, so the
	// rename installs a symlink that already carries the original's mtime/atime.
	if err := lchtimes(tmp, fi); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	return nil
}

// storePath returns the sharded blob path for a content sha1:
// <dirSHA1>/<first shardLen hex chars>/<sha1>.
func (l *linker) storePath(sum string) string {
	return filepath.Join(l.dirSHA1, sum[:shardLen], sum)
}

// linkTarget computes the symlink target string for a link located at path
// pointing to storePath: an absolute path when --absolute, otherwise relative
// to the link's own directory.
func (l *linker) linkTarget(storePath, path string) (string, error) {
	sum := filepath.Base(storePath)
	targetAbs := filepath.Join(l.dirSHA1Abs, sum[:shardLen], sum)
	if l.absolute {
		return targetAbs, nil
	}
	pathAbs, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	return filepath.Rel(filepath.Dir(pathAbs), targetAbs)
}

// lchtimes sets path's access and modification times to those of fi, operating
// on the symlink itself (it does not follow it). It is a no-op on platforms
// whose stat does not expose the timestamps.
func lchtimes(path string, fi os.FileInfo) error {
	st, ok := fi.Sys().(*syscall.Stat_t)
	if !ok {
		return nil
	}
	ts := []unix.Timespec{ // [0]=atime, [1]=mtime
		{Sec: st.Atim.Sec, Nsec: st.Atim.Nsec},
		{Sec: st.Mtim.Sec, Nsec: st.Mtim.Nsec},
	}
	return unix.UtimesNanoAt(unix.AT_FDCWD, path, ts, unix.AT_SYMLINK_NOFOLLOW)
}

// blobChtimes sets the store blob's access and modification times to those of
// fi (the source file). Unlike lchtimes it follows nothing special: the blob is
// a regular file. It is a no-op where stat does not expose the timestamps.
func blobChtimes(storePath string, fi os.FileInfo) error {
	st, ok := fi.Sys().(*syscall.Stat_t)
	if !ok {
		return nil
	}
	ts := []unix.Timespec{ // [0]=atime, [1]=mtime
		{Sec: st.Atim.Sec, Nsec: st.Atim.Nsec},
		{Sec: st.Mtim.Sec, Nsec: st.Mtim.Nsec},
	}
	return unix.UtimesNanoAt(unix.AT_FDCWD, storePath, ts, 0)
}

// adoptIfOlder makes the store blob adopt fi's modification/access times and
// permission bits when fi is older (by mtime) than what the blob currently
// records. This keeps a blob shared by several source files carrying the
// oldest file's mtime and that same file's permissions.
func adoptIfOlder(storePath string, fi os.FileInfo) error {
	bfi, err := os.Lstat(storePath)
	if err != nil {
		return err
	}
	if !fi.ModTime().Before(bfi.ModTime()) {
		return nil
	}
	if err := os.Chmod(storePath, fi.Mode().Perm()); err != nil {
		return err
	}
	return blobChtimes(storePath, fi)
}

// copyToStore copies everything readable from src into storePath, giving the
// blob fi's permission bits and mtime/atime. It writes to a temporary file in
// the store directory, sets its mode and times, and renames it into place, so
// storePath only ever appears as a complete blob already carrying the right
// metadata. src is the caller's already-open source file (positioned at its
// start); passing the concrete *os.File lets the copy use copy_file_range.
func copyToStore(src io.Reader, storePath string, fi os.FileInfo) error {
	tmp, err := os.CreateTemp(filepath.Dir(storePath), ".fs_link.*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	if _, err := io.Copy(tmp, src); err != nil {
		tmp.Close()
		_ = os.Remove(tmpName)
		return err
	}
	// Chmod rather than relying on the 0600 from CreateTemp; chmod ignores
	// umask, so the blob gets exactly the original file's permission bits.
	if err := tmp.Chmod(fi.Mode().Perm()); err != nil {
		tmp.Close()
		_ = os.Remove(tmpName)
		return err
	}
	if err := tmp.Close(); err != nil {
		_ = os.Remove(tmpName)
		return err
	}
	// Set the times on the temp file before publishing it, so the rename
	// installs a blob that already carries the original's mtime/atime.
	if err := blobChtimes(tmpName, fi); err != nil {
		_ = os.Remove(tmpName)
		return err
	}
	if err := os.Rename(tmpName, storePath); err != nil {
		_ = os.Remove(tmpName)
		return err
	}
	return nil
}

// sha1Reader returns the hex SHA1 of everything readable from r, using the
// caller-provided buffer. r is wrapped in onlyReader so its WriterTo is hidden
// and io does not allocate a fresh buffer per file (os.File.WriteTo otherwise
// dominated allocations and GC).
func sha1Reader(r io.Reader, buf []byte) (string, error) {
	h := sha1.New()
	if _, err := io.CopyBuffer(h, onlyReader{r}, buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// onlyReader hides any io.WriterTo (or other) methods of the wrapped reader so
// io.CopyBuffer uses the supplied buffer instead of a per-call allocation.
type onlyReader struct{ io.Reader }
