#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  jsonc_record_grep.sh [-i] [-r RECORD_START_RE] PATTERN [FILE...]

Print whole multi-line records of a JSONC array whose text matches PATTERN
(an AWK ERE). A "record" begins at a line matching RECORD_START_RE
(default: a line starting with `{`, optionally indented) and runs until the
next such line or a line starting with `]`. Reads stdin when no FILE is given.

Unlike line-based grep, the entire record is printed, so multi-line entries
(e.g. VSCode keybindings: key / command / when / args + a trailing
`// comment`) come out intact, preserving the original formatting and
comments that `jq` would strip.

Options:
  -i, --ignore-case          Case-insensitive match.
  -r, --record-start REGEX   Override the record-start pattern.
  -h, --help                 Show this help.

Examples:
  jsonc_record_grep.sh -i group keybindings.jsonc
  jsonc_record_grep.sh 'terminal\.focus' keybindings.jsonc
  cat keybindings.jsonc | jsonc_record_grep.sh -i group
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

ignore_case=0
record_start='^[[:space:]]*[{]'

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -i|--ignore-case) ignore_case=1; shift ;;
    -r|--record-start)
      [ "$#" -ge 2 ] || die "missing argument for $1"
      record_start=$2; shift 2 ;;
    --) shift; break ;;
    -*) die "unknown option: $1" ;;
    *) break ;;
  esac
done

[ "$#" -ge 1 ] || { usage >&2; exit 2; }

pattern=$1; shift

# A record is the block from a record-start line up to (but not including) the
# next record-start line or a closing `]` line. `hit` tracks whether any line
# of the current record matched PATTERN; the whole record is printed if so.
# PATTERN/RECORD_START_RE are passed via the environment (not -v) so awk does
# not run backslash escapes through string-literal processing (which warns on
# e.g. `\.` and would otherwise require double-escaping in the regex).
JSONC_PAT=$pattern JSONC_RS=$record_start \
awk -v ic="$ignore_case" '
BEGIN { pat=ENVIRON["JSONC_PAT"]; rs=ENVIRON["JSONC_RS"] }
function matches(s) { return ic ? (tolower(s) ~ tolower(pat)) : (s ~ pat) }
function flush()    { if (buf != "" && hit) print buf; buf=""; hit=0 }
FNR == 1            { flush() }                       # reset across files
$0 ~ rs             { flush(); buf=$0; hit=matches($0); next }
/^[[:space:]]*\]/   { flush(); next }                 # array close; drop
                    { if (buf == "") {                # outside any record:
                        if (matches($0)) print $0      #   emit the lone line
                        next }                         #   (e.g. `// - cmd` lists)
                      buf = buf "\n" $0
                      if (matches($0)) hit=1 }
END                 { flush() }
' "$@"
