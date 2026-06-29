#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  git_squash_to.sh <revision>

Squash (fixup) <revision>..HEAD into a single commit at <revision>.
The resulting commit keeps the tree of HEAD but reuses <revision>'s author
(name, email, author date) and commit log message. The committer is the
current user/time as usual.

Examples:
  git_squash_to.sh HEAD~     # combine HEAD~ and HEAD into one
  git_squash_to.sh HEAD~3    # combine HEAD~3 HEAD~2 HEAD~1 HEAD into one

Notes:
  The working tree and index are left untouched (only the branch pointer
  moves), so staged/unstaged changes are preserved.
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

if [ "$#" -ne 1 ]; then
  usage >&2
  exit 2
fi

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
  die "not inside a Git work tree"

rev=$(git rev-parse --verify "$1^{commit}" 2>/dev/null) ||
  die "not a valid revision: $1"
head=$(git rev-parse --verify HEAD^{commit})

[ "$rev" != "$head" ] ||
  die "<revision> resolves to HEAD; nothing to squash"

git merge-base --is-ancestor "$rev" "$head" ||
  die "<revision> ($1) is not an ancestor of HEAD"

# Parent of <revision> becomes the base of the new commit. If <revision> is the
# root commit, there is no parent and the new commit is a root commit too.
parent_args=()
if parent=$(git rev-parse --verify "${rev}^" 2>/dev/null); then
  parent_args=(-p "$parent")
fi

tree=$(git rev-parse "${head}^{tree}")

GIT_AUTHOR_NAME=$(git show -s --format=%an "$rev")
GIT_AUTHOR_EMAIL=$(git show -s --format=%ae "$rev")
GIT_AUTHOR_DATE=$(git show -s --format=%aI "$rev")
export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_AUTHOR_DATE

new=$(git show -s --format=%B "$rev" |
  git commit-tree "$tree" "${parent_args[@]}")

git reset --soft "$new"

printf 'squashed %s..%s into %s\n' "$1" "$head" "$(git rev-parse --short HEAD)"
