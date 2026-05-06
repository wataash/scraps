#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  git_uncommit_path_keep_worktree.sh <path> [<path> ...]
  git_uncommit_path_keep_worktree.sh -- <path> [<path> ...]

Remove the given path changes from the current HEAD commit while keeping the
current working-tree contents. After the amend, git diff for the paths should
match the old HEAD patch for those paths.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

if [ "$#" -eq 1 ] && { [ "$1" = "-h" ] || [ "$1" = "--help" ]; }; then
  usage
  exit 0
fi

if [ "$#" -gt 0 ] && [ "$1" = "--" ]; then
  shift
elif [ "$#" -gt 0 ] && [[ "$1" == -* ]]; then
  printf 'error: unknown option: %s\n' "$1" >&2
  usage >&2
  exit 2
fi

if [ "$#" -lt 1 ]; then
  usage >&2
  exit 2
fi

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
  die "not inside a Git work tree"

old_head=$(git rev-parse HEAD)
parent=$(git rev-parse "${old_head}^" 2>/dev/null) ||
  die "HEAD has no parent; cannot remove path changes from the initial commit"

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/git-uncommit-path.XXXXXX")
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

old_patch="$tmp_dir/old.patch"
new_patch="$tmp_dir/new.patch"

# The final diff can match the old HEAD patch only when the current working
# tree already matches old HEAD for the selected paths.
if ! git diff --quiet "$old_head" -- "$@"; then
  git diff "$old_head" -- "$@" >&2 || true
  die "selected paths have working-tree changes after HEAD; refusing to amend"
fi

git show --format= --no-ext-diff "$old_head" -- "$@" >"$old_patch"

for path in "$@"; do
  if git cat-file -e "${parent}:${path}" 2>/dev/null; then
    git restore --source="$parent" --staged -- "$path"
  else
    git rm --cached --quiet -- "$path"
    git add -N -- "$path"
  fi
done

git commit --amend --no-edit --allow-empty

git diff --no-ext-diff -- "$@" >"$new_patch"

if ! diff -u "$old_patch" "$new_patch"; then
  die "verification failed: git diff does not match the old HEAD patch"
fi

printf 'removed selected path changes from old HEAD %s\n' "$old_head"
