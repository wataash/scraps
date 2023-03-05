#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2022-2023 Wataru Ashihara <wataash@wataash.com>
# SPDX-License-Identifier: Apache-2.0

# shellcheck disable=SC2317  # Command appears to be unreachable. Check usage (or ignore if invoked indirectly).

: <<'DOC'
mini CLIs

test: bats ~/sh/c.bash

usage error -> exit 2
https://git.savannah.gnu.org/cgit/bash.git/tree/shell.h?h=bash-5.2#n71 EX_USAGE - EX_SHERRBASE == 2 bash -c 'help --foo' -> 2
https://salsa.debian.org/kernel-team/initramfs-tools/-/blob/v0.142/mkinitramfs#L36                  mkinitramfs --foo    -> 2
https://go.googlesource.com/go/+/refs/tags/go1.20.1/src/cmd/go/main.go#235                          go foo               -> 2
DOC

mkdir -p /tmp/c.bash.d/

if false; then
  # bats ~/sh/c.bash
  # #$0                /usr/local/libexec/bats-core/bats-exec-file
  # #${BASH_SOURCE[@]} /tmp/bats-run-ajyNME/bats.657971.src /usr/local/libexec/bats-core/bats-exec-file /usr/local/libexec/bats-core/bats-exec-file
  # #$0                /usr/local/libexec/bats-core/bats-exec-test
  # #${BASH_SOURCE[@]} /tmp/bats-run-ajyNME/bats.657971.src /usr/local/lib/bats-core/preprocessing.bash /usr/local/libexec/bats-core/bats-exec-test
  # #$0                /home/wsh/sh/c.bash
  # #${BASH_SOURCE[@]} /home/wsh/sh/c.bash
  {
    echo "# \$0                $0"
    echo "# \${BASH_SOURCE[0]} ${BASH_SOURCE[0]}"
    echo "# \${BASH_SOURCE[*]} ${BASH_SOURCE[*]}"
  } >&3

  # ln -s c.bash /tmp/c
  # /tmp/c
  # # $0          : /tmp/c
  # # realpath $0 : .../c.bash
fi
[ "$(basename "$(realpath "$0")")" = 'c.bash' ] && IN_BATS='no' || IN_BATS='yes'

if [[ $IN_BATS = 'no' ]]; then

set -eu

PS4='+ \e[37m''cmd: \e[0m'

fi

# ------------------------------------------------------------------------------
# lib

PROG=$(basename "$0")

# array_copy::by_elems "dst_array" "elem1" "elem2" ...
array_copy::by_elems() {
  if [[ $1 != "nameref" ]]; then
    local -n nameref="$1"
    shift
    nameref=("$@")
  else  # see [nameref_avoid_conflict_name]
    local -n _nameref="$1"
    shift
    _nameref=("$@")
  fi
}

# array_copy "src_array" "dst_array"
array_copy() {
  [[ $1 == "$2" ]] && log_warning "src_array == dst_array == \"$1\" (caller: $(caller1))" && return 1

  # see [nameref_avoid_conflict_name]

  if [[ $1 != "nameref" && $2 != "nameref" ]]; then
    # shellcheck disable=SC2178  # Variable was used as an array but is now assigned a string
    local -n nameref="$1"
    array_copy::by_elems "$2" "${nameref[@]}"
    return 0
  fi

  # $1 == "nameref" || $2 == "nameref"

  if [[ $1 != "_nameref" && $2 != "_nameref" ]]; then
    # shellcheck disable=SC2178  # Variable was used as an array but is now assigned a string
    local -n _nameref="$1"
    array_copy::by_elems "$2" "${_nameref[@]}"
    return 0
  fi

  # $1 == "nameref" && $2 == "_nameref" || $1 == "_nameref" && $2 == "nameref"

  local -n __nameref="$1"
  array_copy::by_elems "$2" "${__nameref[@]}"
  return 0
}

# shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
# shellcheck disable=SC2154  # output is referenced but not assigned
test_array_copy() { #@test
  local -a dst_array       && array_copy::by_elems "dst_array" "a" "b" >&3 && [[ $output == "" ]] && [[ $stderr == "" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a dst_array=(x)   && array_copy::by_elems "dst_array" "a" "b" >&3 && [[ $output == "" ]] && [[ $stderr == "" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref         && array_copy::by_elems "nameref"   "a" "b" >&3 && [[ $output == "" ]] && [[ $stderr == "" ]] && [[ ${nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref=(x)     && array_copy::by_elems "nameref"   "a" "b" >&3 && [[ $output == "" ]] && [[ $stderr == "" ]] && [[ ${nameref[*]} == "a b" ]] || bats_run_debug_fail >&3

  # shellcheck disable=SC2076  # Remove quotes from right-hand side of =~ to match as a regex rather than literally
  run -1 --separate-stderr array_copy "arr" "arr" && [[ $output = "" ]] && [[ $stderr =~ "array_copy(): src_array == dst_array == \"arr\"" ]] || bats_run_debug_fail >&3

  local -a __nameref=(a b) _nameref  && array_copy "__nameref" "_nameref" >&3 && [[ ${__nameref[*]} == "a b" ]] && [[ ${_nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a __nameref=(a b) dst_array && array_copy "__nameref" "dst_array" >&3 && [[ ${__nameref[*]} == "a b" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a __nameref=(a b) nameref   && array_copy "__nameref" "nameref" >&3 && [[ ${__nameref[*]} == "a b" ]] && [[ ${nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a _nameref=(a b)  __nameref && array_copy "_nameref"  "__nameref" >&3 && [[ ${_nameref[*]} == "a b" ]] && [[ ${__nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a _nameref=(a b)  dst_array && array_copy "_nameref"  "dst_array" >&3 && [[ ${_nameref[*]} == "a b" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a _nameref=(a b)  nameref   && array_copy "_nameref"  "nameref" >&3 && [[ ${_nameref[*]} == "a b" ]] && [[ ${nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref=(a b)   __nameref && array_copy "nameref"   "__nameref" >&3 && [[ ${nameref[*]} == "a b" ]] && [[ ${__nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref=(a b)   _nameref  && array_copy "nameref"   "_nameref" >&3 && [[ ${nameref[*]} == "a b" ]] && [[ ${_nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref=(a b)   dst_array && array_copy "nameref"   "dst_array" >&3 && [[ ${nameref[*]} == "a b" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a src_array=(a b) __nameref && array_copy "src_array" "__nameref" >&3 && [[ ${src_array[*]} == "a b" ]] && [[ ${__nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a src_array=(a b) _nameref  && array_copy "src_array" "_nameref" >&3 && [[ ${src_array[*]} == "a b" ]] && [[ ${_nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a src_array=(a b) dst_array && array_copy "src_array" "dst_array" >&3 && [[ ${src_array[*]} == "a b" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a src_array=(a b) nameref   && array_copy "src_array" "nameref" >&3 && [[ ${src_array[*]} == "a b" ]] && [[ ${nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
}

# array_subtract "result_array" "left_array" "right_array"
# result_array = left_array - right_array
array_subtract() {
  [[ $1 == "$2" ]] && log_warning "\$1 == \$2 == \"$1\" (caller: $(caller1))" && return 1
  [[ $1 == "$3" ]] && log_warning "\$1 == \$3 == \"$1\" (caller: $(caller1))" && return 1
  [[ $2 == "$3" ]] && log_warning "\$2 == \$3 == \"$2\" (caller: $(caller1))" && return 1

  local -a left_array
  array_copy "$2" "left_array"
  local -a right_array
  array_copy "$3" "right_array"

  result_array=()
  local left right
  for left in "${left_array[@]}"; do
    local append=1
    for right in "${right_array[@]}"; do
      if [ "$left" = "$right" ]; then
        append=0
        break
      fi
    done
    [ $append = 1 ] && result_array+=("$left")
  done

  if [[ $1 != "nameref" ]]; then
    local -n nameref="$1"
    nameref=("${result_array[@]}")
  else  # see [nameref_avoid_conflict_name]
    local -n _nameref="$1"
    _nameref=("${result_array[@]}")
  fi
  return 0
}

# shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
test_array_subtract() { #@test
  local -a result left=(a b c) right=(b   z) && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} = "a c" ]] || bats_run_debug_fail >&3
  local -a result left=(a b c) right=(b c z) && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} = "a" ]] || bats_run_debug_fail >&3
  local -a result left=(a b c) right=(b   z) && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} = "a c" ]] || bats_run_debug_fail >&3
  local -a result left=()      right=(b c z) && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} = "" ]] || bats_run_debug_fail >&3
  local -a result left=(a b c) right=()      && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} = "a b c" ]] || bats_run_debug_fail >&3

  local -a nameref left=(a b c) right=(b z) && array_subtract "nameref" "left" "right" >&3 && [[ ${nameref[*]} = "a c" ]] || bats_run_debug_fail >&3
  local -a result nameref=(a b c) right=(b z) && array_subtract "result" "nameref" "right" >&3 && [[ ${result[*]} = "a c" ]] || bats_run_debug_fail >&3
  local -a result left=(a b c) nameref=(b z) && array_subtract "result" "left" "nameref" >&3 && [[ ${result[*]} = "a c" ]] || bats_run_debug_fail >&3
}

# not implemented yet
#
# local var=
# assert_variable_local "$(caller0)" "var"
assert_variable_local() {
  if false; then
    # cannot detect a
    # c == d
    local a b=xxx c="" d=
    [[ ${a+defined} = defined ]] && echo a defined  # not defined
    [[ ${b+defined} = defined ]] && echo b defined
    [[ ${c+defined} = defined ]] && echo c defined
    [[ ${d+defined} = defined ]] && echo d defined
    # b=xxx
    # c=
    # d=
    local
    local -p

    fn() {
      [[ ${outer_a+defined} = defined ]] && echo outer_a defined  # not defined
      [[ ${outer_b+defined} = defined ]] && echo outer_b defined
      [[ ${outer_c+defined} = defined ]] && echo outer_c defined
      [[ ${outer_d+defined} = defined ]] && echo outer_d defined
      # prints nothing
      local
      local -p
    }
    local outer_a outer_b=xxx outer_c="" outer_d=
    fn
  fi

  local caller=$1 && shift
  local name=$1 && shift
  not_yet
  # cannot implement?
  [[ ${!name+defined} = defined ]]  # true for both locals and globals
  declare -p "$name"  # only globals (and current scope locals)
}

test_assert_variable_local() { #@test
  return # not yet
  local a= && assert_variable_local "$LINENO ${FUNCNAME[0]}" "a"
  b="" && assert_variable_local "$LINENO ${FUNCNAME[0]}" "b"
}

# shellcheck disable=SC2154  # * is referenced but not assigned.
bats_run_debug() {
  echo "BATS_RUN_COMMAND $BATS_RUN_COMMAND"
  echo "status: $status"
  echo -en '\e[37m'
  echo "output: $output"
  local i
  echo "lines: ${lines[*]}" | cat -A
  for ((i=0; i <= "${#lines[@]}"; i++)); do echo "lines[$i]: ${lines[$i]}"; done
  echo "stderr: ${stderr[*]}" | cat -A
  for ((i=0; i <= "${#stderr_lines[@]}"; i++)); do echo "stderr_lines[$i]: ${stderr_lines[$i]}"; done
  echo -en '\e[0m'
}

bats_run_debug_fail() {
  echo -e "\e[31m$(caller1)\e[0m"
  bats_run_debug
  false
}

# line, funcname of this line
#
# de-lib: "$LINENO ${FUNCNAME[0]}"
caller0() {
  echo "${BASH_LINENO[0]} ${FUNCNAME[1]}()"
}

# de-lib: "${BASH_LINENO[0]} ${FUNCNAME[1]}"
caller1() {
  echo "${BASH_LINENO[1]} ${FUNCNAME[2]}()"
}

die() {
  local exit_code=$1 && shift
  echo -e "\e[31m$*\e[0m" >&2
  exit "$exit_code"
}

# echo_array ARG...
# Tips: maybe you need just: declare -p INDEXED_ARRAY
echo_array() {
  for ((i=1; i <= $#; i++)); do
    echo -e "\$$i: ${!i}"
  done
}

# echo_array_name VARNAME
echo_array_name() {
  if [[ $1 != "nameref" ]]; then
    local -n nameref=$1
    echo -e "\$$1:\n$(echo_array "${nameref[@]}")"
  else  # see [nameref_avoid_conflict_name]: without this `else`: echo_array_name "nameref" -> /home/wsh/bin/c.bash: line 205: local: warning: nameref: circular name reference
    local -n _nameref=$1
    echo -e "\$$1:\n$(echo_array "${_nameref[@]}")"
  fi
}

test_echo_array_name() { #@test
  local -a arr=(a b)
  run -0 --separate-stderr echo_array_name "arr"     && [[ $stderr == "" ]] && [[ $output == $'$arr:\n$1: a\n$2: b' ]] || bats_run_debug_fail >&3
  local -a nameref=(a b)
  run -0 --separate-stderr echo_array_name "nameref" && [[ $stderr == "" ]] && [[ $output == $'$nameref:\n$1: a\n$2: b' ]] || bats_run_debug_fail >&3
}

echo_popup() {
  echo "$@"
  # notify-send -u normal "$@"  # possibly: Invalid number of options
  notify-send -u normal "$*"
}

err() {
  local rc=$1 && shift
  echo -e "\e[31m$*\e[0m" >&2
  return "$rc"
}

err_popup() {
  local rc=$1 && shift
  echo -e "\e[31m$*\e[0m" >&2
  notify-send -u normal "$*"
  return "$rc"
}

# <sys/syslog.h>
# LOG_EMERG=0    # /* system is unusable */
# LOG_ALERT=1    # /* action must be taken immediately */
# LOG_CRIT=2     # /* critical conditions */
LOG_ERR=3      # /* error conditions */
LOG_WARNING=4  # /* warning conditions */
# LOG_NOTICE=5   # /* normal but significant condition */
LOG_INFO=6     # /* informational */
LOG_DEBUG=7    # /* debug-level messages */

log_setlevel() {
  LOG_LEVEL=$1

  log_error() { :;}
  log_warning() { :;}
  log_info() { :;}
  log_debug() { :;}

  (( LOG_LEVEL >= LOG_ERR )) || return 0
  log_error() { printf '\e[31m[E] %s: %s\e[0m\n' "$(caller1)" "$*" >&2; }
  (( LOG_LEVEL >= LOG_WARNING )) || return 0
  log_warning() { printf '\e[33m[W] %s: %s\e[0m\n' "$(caller1)" "$*" >&2; }
  (( LOG_LEVEL >= LOG_INFO )) || return 0
  log_info() { printf '\e[34m[I] %s: %s\e[0m\n' "$(caller1)" "$*" >&2; }
  (( LOG_LEVEL >= LOG_DEBUG )) || return 0
  log_debug() { printf '\e[37m[D] %s: %s\e[0m\n' "$(caller1)" "$*" >&2; }
}

LOG_LEVEL=$LOG_WARNING
log_setlevel $LOG_LEVEL

not_yet() { false; }

self_real_path() {
  if false; then
    set +u
    echo --
    # /home/wsh/bin/c.bash -> /home/wsh/sh/c.bash
    # cd /home/wsh/bin/ ;                       ./c.bash ;                 bash c.bash ;  bash ./c.bash
    # cd /home/wsh/sh/  ;                       ./c.bash ;                 bash c.bash ;  bash ./c.bash
    echo "0:              $0"                 # /home/wsh/{bin,sh}/c.bash  c.bash         ./c.bash
    echo "BASH_SOURCE[0]: ${BASH_SOURCE[0]}"  # /home/wsh/{bin,sh}/c.bash  c.bash         ./c.bash
    echo "BASH_SOURCE[1]: ${BASH_SOURCE[1]}"  # /home/wsh/{bin,sh}/c.bash  c.bash         ./c.bash
    echo "BASH_SOURCE[2]: ${BASH_SOURCE[2]}"  #
    realpath "${BASH_SOURCE[0]}"  # /home/wsh/sh/c.bash
    readlink -f "${BASH_SOURCE[0]}"  # /home/wsh/sh/c.bash
    exit 42
  fi
  # ref: /usr/local/bin/bats
  readlink -f "${BASH_SOURCE[0]}"
}

# https://stackoverflow.com/questions/1527049/how-can-i-join-elements-of-an-array-in-bash
function str_join_by {
  local d=${1-} f=${2-}
  if shift 2; then
    printf %s "$f" "${@/#/$d}"
  fi
}

top_usage() {
  shopt -s lastpipe
  for k in "${!_commands[@]}"; do
    echo "$k"
  done | sort | mapfile -t
  cat <<EOS
usage:
  $PROG [-h | --help] [-q] [-v[v]] {$(str_join_by " | " "${MAPFILE[@]}")} [-h | --help]
EOS
}

unreachable() {
  die 1 "unreachable: $(caller1): $(sed -n "${BASH_LINENO[0]}"p "$(self_real_path)")"
}

# ------------------------------------------------------------------------------
# bats setup

[[ $IN_BATS == "yes" ]] && bats_require_minimum_version 1.8.0

[[ $IN_BATS == "yes" ]] && [ -z "$BATS_TEST_NUMBER" ] && {
  [ -z "$BATS_SUITE_TEST_NUMBER" ] || echo -e "# \e[31m""BUG: BATS_SUITE_TEST_NUMBER defined: $BATS_SUITE_TEST_NUMBER\e[0m"
  [ -z "$BATS_TEST_NAME" ]         || echo -e "# \e[31m""BUG: BATS_TEST_NAME defined: $BATS_TEST_NAME\e[0m"
} >&3

setup() {
  [ -z "$BATS_TEST_NUMBER" ] && echo -e "# \e[31m""BUG: setup(): BATS_TEST_NUMBER not defined\e[0m"
  [ "$BATS_SUITE_TEST_NUMBER" = "$BATS_TEST_NUMBER" ] || echo -e "# \e[31m""BUG: BATS_SUITE_TEST_NUMBER: $BATS_SUITE_TEST_NUMBER BATS_TEST_NUMBER: $BATS_TEST_NUMBER\e[0m"
} >&3

# ------------------------------------------------------------------------------
# commands

declare -A _commands
define_command() {
  _commands[$1]+='defined'
}

# local name="" ... && local -a arr=() && arg_parse "$usage" "name..." "$@"
# TODO: arg_parse "$usage" "NAME [--] [CMD...]"
arg_parse() {
  local -r usage=$1 && shift
  local -r names=$1 && shift

  local -a names2
  IFS=" " read -ra names2 <<<"$(arg_parse::_parse_names "${BASH_LINENO[1]} ${FUNCNAME[2]}" "$names")"
  local -r kind=${names2[0]}
  names2=("${names2[@]:1}")

  [[ $# != 0 ]] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && echo "$usage" && exit 0

  local name

  # required names
  while true; do
    name=${names2[0]}
    # TODO: assert_variable_local "$caller" "$name"
    names2=("${names2[@]:1}")
    [[ $name = "%%" ]] && break
    [[ $# = 0 ]] && err 0 "error: required argument: \"$name\" missing" && echo "$usage" >&2 && return 2
    # https://stackoverflow.com/questions/9938649/indirect-variable-assignment-in-bash
    printf -v "$name" '%s' "$1" && shift
  done

  case $kind in
  "NO_ARGV")
    # optional arguments
    while [[ ${#names2[@]} != 0 ]]; do
      name=${names2[0]}
      names2=("${names2[@]:1}")
      [[ $name = "%%" ]] && unreachable
      # TODO: assert_variable_local "$caller" "$name"
      (( $# == 0 )) && return 0
      printf -v "$name" '%s' "$1" && shift
    done
    [[ $# != 0 ]] && err 0 "error: excess argument(s): $*" && echo "$usage" >&2 && exit 2
    return 0
    ;;
  "HAS_ARGV")
    # variadic argument; must be the last
    [[ ${#names2[@]} = 1 ]] || unreachable
    name=${names2[0]}
    [ $# = 0 ] && err 0 "error: required argument: \"$name...\" missing" && echo "$usage" >&2 && return 2
    # TODO: [nameref_avoid_conflict_name]
    local -n argv_nameref=${names2[0]}
    argv_nameref=("$@")
    return 0
    ;;
  "MAY_ARGV")
    # optional arguments
    while true; do
      name=${names2[0]}
      names2=("${names2[@]:1}")
      # TODO: assert_variable_local "$caller" "$name"
      (( $# == 0 )) && return 0
      [[ $name = "%%" ]] && break
      printf -v "$name" '%s' "$1" && shift
    done
    # optional variadic argument; must be the last
    [[ ${#names2[@]} = 1 ]] || unreachable
    # TODO: [nameref_avoid_conflict_name]
    # shellcheck disable=SC2178  # Variable was used as an array but is now assigned a string
    local -n argv_nameref=${names2[0]}
    # shellcheck disable=SC2034  # argv_nameref appears unused. Verify use (or export if used externally)
    argv_nameref=("$@")
    return 0;
    ;;
  *)
    unreachable
    ;;
  esac

  unreachable
}

# arg_parse::_parse_names "$(caller0)" "names..."
#
# no variadic argument                       "ARG1 ARG2 [ARG3] "           -> echo "NO_ARGV ARG1 ARG2 %% ARG3"
# has variadic argument (ARGV...)            "ARG1 ARG2 ARGV..."           -> echo "HAS_ARGV ARG1 ARG2 %% ARGV"
# has optional variadic argument ([ARGV...]) "ARG1 ARG2 [ARG3] [ARGV...] " -> echo "MAY_ARGV ARG1 ARG2 %% ARG3 %% ARGV"
arg_parse::_parse_names() {
  [ $# != 2 ] && die 1 "$(caller0): usage: arg_parse::_parse_names \"\$(caller0)\" \"names...\""
  local -r caller=$1 && shift

  # v required v variadic
  # ARG1       ARGV...
  #
  # v required v optional v variadic_o
  # ARG1       [ARG2]     [ARGV...]
  local required=()
  local optional=()
  local variadic=""
  local variadic_o=""
  for name in $1; do
    # [[:alnum:]_] : [0-9A-Za-z_]

    # ARGV.../[ARGV...] any -> error
    [[ $variadic = "" ]] || die 1 "$caller: variadic name: \"$variadic...\" must be the last (in: $*)"
    [[ $variadic_o = "" ]] || die 1 "$caller: variadic name: \"[$variadic_o...]\" must be the last (in: $*)"

    # optional?
    [[ $name =~ ^"["([[:alnum:]_]+)"]"$ ]] && optional+=("${BASH_REMATCH[1]}") && continue
    # optional variadic?
    [[ $name =~ ^"["([[:alnum:]_]+)"...]"$ ]] && variadic_o=${BASH_REMATCH[1]} && continue

    # [optional] non-optional -> error
    [[ ${#optional[@]} != 0 ]] && die 1 "$caller: cannot give non-optional name: \"$name\" after optional name(s): \"${optional[*]}\" (in: $*)"

    # variadic?
    [[ $name =~    ^([[:alnum:]_]+)"..."$  ]] && variadic=${BASH_REMATCH[1]} && continue
    # required?
    [[ $name =~    ^([[:alnum:]_]+)$    ]] && required+=("${BASH_REMATCH[1]}") && continue

    die 1 "$caller: invalid name:$name (in: $*)"
  done

  [[ $variadic != "" ]]   && echo "HAS_ARGV ${required[*]} %% ${variadic}" && return 0
  [[ $variadic_o != "" ]] && echo "MAY_ARGV ${required[*]} %% ${optional[*]} %% ${variadic_o}" && return 0
                             echo "NO_ARGV ${required[*]} %% ${optional[*]}" && return 0
  unreachable
}

# shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
# shellcheck disable=SC2076  # Remove quotes from right-hand side of =~ to match as a regex rather than literally
test_arg_parse() { #@test
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" ""          && [[ $stderr = "" ]] && [[ $output = "NO_ARGV  %% "          ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1"      && [[ $stderr = "" ]] && [[ $output = "NO_ARGV ARG1 %% "      ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1]"    && [[ $stderr = "" ]] && [[ $output = "NO_ARGV  %% ARG1"      ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARGV..."   && [[ $stderr = "" ]] && [[ $output = "HAS_ARGV  %% ARGV"     ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARGV...]" && [[ $stderr = "" ]] && [[ $output = "MAY_ARGV  %%  %% ARGV" ]] || bats_run_debug_fail >&3

  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 ARG2"        && [[ $stderr = "" ]] && [[ $output = "NO_ARGV ARG1 ARG2 %% "     ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 [ARG2]"      && [[ $stderr = "" ]] && [[ $output = "NO_ARGV ARG1 %% ARG2"      ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 ARGV..."     && [[ $stderr = "" ]] && [[ $output = "HAS_ARGV ARG1 %% ARGV"     ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 [ARGV...]"   && [[ $stderr = "" ]] && [[ $output = "MAY_ARGV ARG1 %%  %% ARGV" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] [ARG2]"    && [[ $stderr = "" ]] && [[ $output = "NO_ARGV  %% ARG1 ARG2"     ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] [ARGV...]" && [[ $stderr = "" ]] && [[ $output = "MAY_ARGV  %% ARG1 %% ARGV" ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] ARG2"      && [[ $output = "" ]] && [[ $stderr =~ ": cannot give non-optional name: \"ARG2\" after optional name(s): \"ARG1\" (in: [ARG1] ARG2)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] ARGV..."   && [[ $output = "" ]] && [[ $stderr =~ ": cannot give non-optional name: \"ARGV...\" after optional name(s): \"ARG1\" (in: [ARG1] ARGV...)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARGV... any"      && [[ $output = "" ]] && [[ $stderr =~ ": variadic name: \"ARGV...\" must be the last (in: ARGV... any)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARGV...] any"    && [[ $output = "" ]] && [[ $stderr =~ ": variadic name: \"[ARGV...]\" must be the last (in: [ARGV...] any)"$'\e[0m'$ ]] || bats_run_debug_fail >&3

  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 [ARG2] ARGV..."   && [[ $output = "" ]] && [[ $stderr =~ ": cannot give non-optional name: \"ARGV...\" after optional name(s): \"ARG2\" (in: ARG1 [ARG2] ARGV...)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] [ARG2] ARGV..." && [[ $output = "" ]] && [[ $stderr =~ ": cannot give non-optional name: \"ARGV...\" after optional name(s): \"ARG1 ARG2\" (in: [ARG1] [ARG2] ARGV...)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 [ARG2] [ARGV...]" && [[ $stderr = "" ]] && [[ $output = "MAY_ARGV ARG1 %% ARG2 %% ARGV" ]] || bats_run_debug_fail >&3

  local usage="usage: $PROG 0template [-h | --help] ???"

  # NO_ARGV
  set -- "arg1" "arg2" && local ARG1="" ARG2="" &&   arg_parse "$usage" "ARG1 ARG2"   "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = "arg2" ]]                                                                                           || bats_run_debug_fail >&3
  set -- "arg1"        && run -2 --separate-stderr   arg_parse "$usage" "ARG1 ARG2"   "$@"          && [[ $output = "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG2" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set --               && run -2 --separate-stderr   arg_parse "$usage" "ARG1 ARG2"   "$@"          && [[ $output = "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG1" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set -- "arg1" "arg2" && local ARG1="" ARG2="" &&   arg_parse "$usage" "ARG1 [ARG2]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = "arg2" ]]                                                                                           || bats_run_debug_fail >&3
  set -- "arg1"        && local ARG1="" ARG2="" &&   arg_parse "$usage" "ARG1 [ARG2]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = ""     ]]                                                                                           || bats_run_debug_fail >&3
  set --               && run -2 --separate-stderr   arg_parse "$usage" "ARG1 [ARG2]" "$@"          && [[ $output = "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG1" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3

  # HAS_ARGV
  set -- "arg1" "arg2" "argv1" "argv2" && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = "arg2" ]] && [[ ${#ARGV[@]} = 2 ]] && [[ ${ARGV[*]} = "argv1 argv2" ]]                                 || bats_run_debug_fail >&3
  set -- "arg1" "arg2" "argv1"         && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = "arg2" ]] && [[ ${#ARGV[@]} = 1 ]] && [[ ${ARGV[*]} = "argv1"       ]]                                 || bats_run_debug_fail >&3
  set -- "arg1" "arg2"                 && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output = "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARGV..." missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set -- "arg1"                        && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output = "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG2" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]]    || bats_run_debug_fail >&3
  set -- "arg1" ""                     && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output = "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARGV..." missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set -- "arg1" "" ""                  && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = ""     ]] && [[ ${#ARGV[@]} = 1 ]] && [[ ${ARGV[*]} = ""            ]]                                 || bats_run_debug_fail >&3
  set -- "arg1" "" "" ""               && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = ""     ]] && [[ ${#ARGV[@]} = 2 ]] && [[ ${ARGV[*]} = " "           ]]                                 || bats_run_debug_fail >&3

  # MAY_ARGV
  set -- "arg1" "arg2" "argv1" "argv2" && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = "arg2" ]] && [[ ${#ARGV[@]} = 2 ]] && [[ ${ARGV[*]} = "argv1 argv2" ]] || bats_run_debug_fail >&3
  set -- "arg1" "arg2" "argv1"         && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = "arg2" ]] && [[ ${#ARGV[@]} = 1 ]] && [[ ${ARGV[*]} = "argv1"       ]] || bats_run_debug_fail >&3
  set -- "arg1" "arg2"                 && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = "arg2" ]] && [[ ${#ARGV[@]} = 0 ]] && [[ ${ARGV[*]} = ""            ]] || bats_run_debug_fail >&3
  set -- "arg1"                        && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = ""     ]] && [[ ${#ARGV[@]} = 0 ]] && [[ ${ARGV[*]} = ""            ]] || bats_run_debug_fail >&3
  set -- "arg1" ""                     && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = ""     ]] && [[ ${#ARGV[@]} = 0 ]] && [[ ${ARGV[*]} = ""            ]] || bats_run_debug_fail >&3
  set -- "arg1" "" ""                  && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = ""     ]] && [[ ${#ARGV[@]} = 1 ]] && [[ ${ARGV[*]} = ""            ]] || bats_run_debug_fail >&3
  set -- "arg1" "" "" ""               && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 = "arg1" ]] && [[ $ARG2 = ""     ]] && [[ ${#ARGV[@]} = 2 ]] && [[ ${ARGV[*]} = " "           ]] || bats_run_debug_fail >&3
}

# ------------------------------------------------------------------------------
# command - 0template @pub

define_command 0template
0template() {
  local -r usage="usage: $PROG 0template [-h | --help]"
  arg_parse "$usage" "" "$@"
  echo 'code here'
  exit 0
}

define_command 0template_arg
0template_arg() {
  local -r usage="usage: $PROG 0template_arg [-h | --help] ARG"
  local ARG="" && arg_parse "$usage" "ARG" "$@"
  echo "ARG: $ARG"
  exit 0
}

# without arg_parse:
false && _() {
  # short usage
  local -r usage="usage: $PROG 0template [-h | --help]"
  [[ $# != 0 ]] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && echo "$usage" && exit 0
  [[ $# != 0 ]] && err 0 "error: excess argument(s): $*" && echo "$usage" >&2 && exit 2

  # long usage
  local -r usage=$(cat <<EOS
usage: $PROG 0template [-h | --help]
EOS
)
  # ...
}

# ------------------------------------------------------------------------------
# command - discharging_checker @pub

# upower -i /org/freedesktop/UPower/devices/battery_BAT0
#  native-path:          BAT0
#  vendor:               SMP
#  model:                5B10W13900
#  serial:               1135
#  power supply:         yes
#  updated:              2022年12月24日 20時05分21秒 (103 seconds ago)
#  has history:          yes
#  has statistics:       yes
#  battery
#    present:             yes
#    rechargeable:        yes
#    state:               pending-charge                   discharging              charging                          pending-charge
#    warning-level:       none
#    energy:              53 Wh                            52.63 Wh                 50.93 Wh                          57.58 Wh  USE THIS to determine the charging state
#    energy-empty:        0 Wh
#    energy-full:         72.42 Wh
#    energy-full-design:  80.4 Wh
#    energy-rate:         20.86 W                          3.238 W                  20.303 W                          7.809 W
#    time to full:                                                                  1.1 hours
#    voltage:             16.247 V                         16.032 V                 15.879 V                          16.554 V  might be used to determine the charging state, but I think it might go down sharply when charging -> pending-charge
#    percentage:          73%                              72%                      70%                               79%
#    capacity:            87.0771%
#    technology:          lithium-polymer
#    icon-name:          'battery-full-charging-symbolic'  'battery-full-symbolic'  'battery-full-charging-symbolic'  'battery-full-charging-symbolic'
#  History (charge):
#    ...
#  History (rate):
#    ...
define_command discharging_checker
discharging_checker() {
  local -r usage="usage: $PROG discharging_checker [-h | --help]"
  arg_parse "$usage" "" "$@"
  local -ir BASE_INTERVAL=240  # 4min, 8min, 16min, 32min, 64min, ...

  # without this: notify-send: Cannot autolaunch D-Bus without X11 $DISPLAY
  # @ref:no-X11-DBUS_SESSION_BUS_ADDRESS
  DBUS_SESSION_BUS_ADDRESS=$(grep -z DBUS_SESSION_BUS_ADDRESS /proc/"$(pgrep -u wsh gnome-session | head -1)"/environ | cut -d= -f2- | tr -d '\0\n')
  export DBUS_SESSION_BUS_ADDRESS

  local interval=$BASE_INTERVAL
  local energy_prev;
  local energy_curr;
  local state_prev;
  local state_curr;
  local percentage_;
  energy_prev=$(upower -i /org/freedesktop/UPower/devices/battery_BAT0 | grep -P -o '(?<=energy:)\s+\S+(?= Wh)' | tr -d ' ')
  state_prev=$(upower -i /org/freedesktop/UPower/devices/battery_BAT0 | grep -P -o '(?<=state:)\s+\S+' | tr -d ' ')
  percentage_=$(upower -i /org/freedesktop/UPower/devices/battery_BAT0 | grep -P -o '(?<=percentage:)\s+\S+' | tr -d ' ')

  echo "$energy_prev Wh ($percentage_) $state_prev"

  while true; do
    sleep "$interval"

    energy_curr=$(upower -i /org/freedesktop/UPower/devices/battery_BAT0 | grep -P -o '(?<=energy:)\s+\S+(?= Wh)' | tr -d ' ')
    state_curr=$(upower -i /org/freedesktop/UPower/devices/battery_BAT0 | grep -P -o '(?<=state:)\s+\S+' | tr -d ' ')
    discharging="false"
    [ "$state_curr" != 'pending-charge' ] && [ "$(echo "$energy_curr < $energy_prev" | bc)" = 1 ] && discharging="true"  # energy slowly decreases in 'pending-charge' state; notify only in 'charging' state
    [ "$state_curr" = 'discharging' ]                                                             && discharging="true"
    if [ "$discharging" = "true" ]; then
      percentage_=$(upower -i /org/freedesktop/UPower/devices/battery_BAT0 | grep -P -o '(?<=percentage:)\s+\S+' | tr -d ' ')
      echo "discharging: $energy_prev Wh -> $energy_curr Wh, $state_prev -> $state_curr ($percentage_)"
      bash /home/wsh/sh/debug_notify.bash "discharging: $energy_prev Wh -> $energy_curr Wh ($percentage_), $state_prev -> $state_curr"
      interval=$((interval * 2))
      echo "recheck in $interval seconds..."
    else
      # charging
      (( interval > BASE_INTERVAL )) && echo 'charging'
      interval=$BASE_INTERVAL
    fi
    energy_prev=$energy_curr
    state_prev=$state_curr
  done
  unreachable
}

if false; then
sudo vim /etc/systemd/system/my-discharging_checker.service
sudo systemctl enable --now my-discharging_checker.service
journalctl -x -u my-discharging_checker.service
journalctl -x -u my-discharging_checker.service -f
: <<'EOF'
[Unit]
Description=my discharging checker
After=graphical.target
[Service]
Type=simple
User=wsh
ExecStart=/home/wsh/sh/c.bash discharging_checker
Restart=always
RestartSec=10s
[Install]
WantedBy=multi-user.target
EOF
fi

# ------------------------------------------------------------------------------
# command - file_timestamp @pub

define_command file_timestamp
file_timestamp() {
  local -r usage="usage: $PROG file_timestamp [-h | --help] FILE"
  local FILE="" && arg_parse "$usage" "FILE" "$@"

  local -r FILE_TS="$FILE.ts"
  local -r FILE_RAWTS="$FILE.rawts"

  # TODO: 存在だけでなくプロセスが生きているかどうかもチェック
  if [[ ! -e $FILE_TS ]]; then
    tail -F "$FILE" | cat -A 2>&1 | ts '%F %T' >"$FILE_TS"    &
  fi
  if [[ ! -e $FILE_RAWTS ]]; then
    tail -F "$FILE" | cat    2>&1 | ts '%F %T' >"$FILE_RAWTS" &
  fi

  wait
}

# ------------------------------------------------------------------------------
# command - gm @pub
# grep mutli-line

# c.bash gm -P -m1 "^define_command gm" "cat" < /home/wsh/sh/c.bash
# c.bash gm -P -m1 "^define_command gm" "cat" < /home/wsh/sh/c.bash | sed '1d;$d'

define_command gm
gm() {
  local -r usage="usage: ... | $PROG gm [-h | --help] -P -m1 PATTERN_BEGIN PATTERN_END [| sed '1d;\$d']"
  local P="" m="" PATTERN_BEGIN="" PATTERN_END="" && arg_parse "$usage" "P m PATTERN_BEGIN PATTERN_END" "$@"
  [[ $P != "-P" ]] && err 0 "error: \"$P\" != \"-P\" (in $*)" && echo "$usage" >&2 && exit 2
  [[ $m != "-m1" ]] && err 0 "error: \"$m\" != \"-m1\" (in $*)" && echo "$usage" >&2 && exit 2
  local txt
  txt=$(cat)
  set -x
  grep -P -m1 -q "$PATTERN_BEGIN" <<< "$txt"
  local -i lineno_begin
  lineno_begin="$(grep -P -m1 -n "$PATTERN_BEGIN" <<< "$txt" | cut -d":" -f1)"
  grep -P -m1 -q "$PATTERN_END" <<< "$txt"
  # lineno_end="$(grep -P -m1 -n "$PATTERN_END" <<< "$txt" | cut -d":" -f1)"
  set +x
  local -i lineno_end
  grep -P -n "$PATTERN_END" <<< "$txt" | cut -d":" -f1 | while IFS= read -r lineno_end; do  # IFS= : prevent removeing preceding spaces
    log_debug "lineno_end: $lineno_end"
    if (( lineno_end > lineno_begin )); then
      sed -n "${lineno_begin},${lineno_end}p" <<< "$txt"
      exit 0
    fi
  done
  exit 1
}

# ------------------------------------------------------------------------------
# command - gm_greedy @pub

# c.bash gm_greedy -P "^define_command gm_greedy" "cat" < /home/wsh/sh/c.bash

define_command gm_greedy
gm_greedy() {
  local -r usage="usage: ... | $PROG gm_greedy [-h | --help] -P PATTERN_BEGIN PATTERN_END [| sed '1d;\$d']"
  local P="" PATTERN_BEGIN="" PATTERN_END="" && arg_parse "$usage" "P PATTERN_BEGIN PATTERN_END" "$@"
  [[ $P != "-P" ]] && err 0 "error: \"$P\" != \"-P\" (in $*)" && echo "$usage" >&2 && exit 2
  local txt
  txt=$(cat)
  set -x
  grep -P -m1 -q "$PATTERN_BEGIN" <<< "$txt"
  local -i lineno_begin
  lineno_begin="$(grep -P -m1 -n "$PATTERN_BEGIN" <<< "$txt" | cut -d":" -f1)"
  grep -P -q "$PATTERN_END" <<< "$txt"
  lineno_end="$(grep -P -n "$PATTERN_END" <<< "$txt" | cut -d":" -f1 | tail -1)"
  if (( lineno_end <= lineno_begin )); then
    exit 1
  fi
  sed -n "${lineno_begin},${lineno_end}p" <<< "$txt"
  exit 0
}

# ------------------------------------------------------------------------------
# command - kill_clangd @pub

define_command kill_clangd
kill_clangd() {
  local -r usage="usage: $PROG kill_clangd [-h | --help]"
  arg_parse "$usage" "" "$@"
  # ps じゃなくて1秒間隔のCPU使用率が見れるプログラムに置き換えたい @ref:linux-ps-pcpu
  : <<'EOS'
ps -e u -ww | grep -E '[U]SER|[/]clangd'
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
wsh       584400  149  0.1 244784 66720 ?        Sl   22:29   0:37 /home/wsh/.local/share/JetBrains/Toolbox/apps/CLion/ch-0/223.8617.54/bin/clang/linux/x64/clangd --clion-mode=clion-main -update-debounce=0 -index=false -include-ineligible-results -clang-tidy=0 -resource-dir=/home/wsh/.local/share/JetBrains/Toolbox/apps/CLion/ch-0/223.8617.54/bin/clang/linux/x64 -keep-asts=99 -recovery-ast -ranking-model=heuristics -header-extensions=h;h;cuh;
wsh       611349 10.8  0.1 244784 66840 ?        Sl   03:30   0:00 /home/wsh/.local/share/JetBrains/Toolbox/apps/CLion/ch-0/223.8617.54/bin/clang/linux/x64/clangd --clion-mode=clion-main -update-debounce=0 -index=false -include-ineligible-results -clang-tidy=0 -resource-dir=/home/wsh/.local/share/JetBrains/Toolbox/apps/CLion/ch-0/223.8617.54/bin/clang/linux/x64 -keep-asts=99 -recovery-ast -ranking-model=heuristics -header-extensions=h;h;cuh;

ps -C ion.clangd.main -o pid=,pcpu=
584400  149
611349 10.8
EOS
  local -r processes=$(ps -C ion.clangd.main -o pid=,pcpu=)

  local line
  oIFS=$IFS
  IFS=$'\n'
  for line in $processes; do
    log_debug "$line"
    local fields
    # read -ar -> fields: unbound variable
    IFS=" " read -ra fields <<<"$line"
    local pid=${fields[0]}
    local pcpu=${fields[1]}
    echo "$pcpu > 110" | bc | grep -q '1' || continue
    echo "kill $pid"
    kill "$pid"
  done
  IFS=$oIFS

  local line
  oIFS=$IFS
  IFS=$'\n'
  for _ in {1..4}; do
    local alive_pids=()
    for line in $processes; do
      local fields
      IFS=" " read -ra fields <<<"$line"
      local pid=${fields[0]}
      local pcpu=${fields[1]}
      echo "$pcpu > 110" | bc | grep -q '1' || continue
      log_debug "kill -0 $pid"
      kill -0 "$pid" && alive_pids+=("$pid")
    done
    [[ ${#alive_pids[@]} = 0 ]] && return 0
    log_info "alive: ${alive_pids[*]}"
    sleep 1
  done
  IFS=$oIFS

  local line
  oIFS=$IFS
  IFS=$'\n'
  for line in $processes; do
    local fields
    IFS=" " read -ra fields <<<"$line"
    pid=${fields[0]}
    echo "kill -9 $pid"
    kill -9 "$pid"
  done
  IFS=$oIFS
}

# ------------------------------------------------------------------------------
# command - linux_dmesg_time0 @pub

define_command linux_dmesg_time0
linux_dmesg_time0() {
  local -r usage="usage: dmesg | $PROG linux_dmesg_time0 [-h | --help]"
  arg_parse "$usage" "" "$@"
  sed -E s'/\[[0-9 ]{4}[0-9]\.[0-9]{6}\]/[    0.000000]/'
}

# ------------------------------------------------------------------------------
# command - net_if_rename @pub

# variable_diff: usage:
# variable_diff_1
# some commands...
# variable_diff_2

variable_diff_1() {
  declare -p > /tmp/c.bash.d/variable_diff.1
}

variable_diff_2() {
  declare -p > /tmp/c.bash.d/variable_diff.2
  delta /tmp/c.bash.d/variable_diff.1 /tmp/c.bash.d/variable_diff.2
}

define_command net_if_rename
net_if_rename() {
  local -r usage="usage: $PROG net_if_rename [-h | --help] MAC_ADDRESS NEW_NAME"
  local MAC_ADDRESS="" NEW_NAME="" && arg_parse "$usage" "MAC_ADDRESS NEW_NAME" "$@"

  # 42: enx00005e005300: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
  #     link/ether 00:00:5e:00:53:00 brd ff:ff:ff:ff:ff:ff
  shopt -s lastpipe
  ip a | grep -B1 "$MAC_ADDRESS" | grep -P -o '(?<=\d: )\w+(?=: <)' | read -r old_name
  set -x
  sudo ip link set "$old_name" down
  sudo ip link set "$old_name" name "$NEW_NAME"
  sudo ip link set "$NEW_NAME" up
}

# ------------------------------------------------------------------------------
# command - netbsd_makefile_expand_vars @pub

define_command netbsd_makefile_expand_vars
netbsd_makefile_expand_vars() {
  local -r usage="usage: $PROG netbsd_makefile_expand_vars [-h | --help] MAKE_COMMAND <Makefile"
  local MAKE_COMMAND="" && arg_parse "$usage" "MAKE_COMMAND" "$@"

  local -A pairs_name_value
  local line
  while IFS= read -r line; do  # IFS= : prevent removeing preceding spaces
    local line2=$line
    # e.g. ${VAR_0}
    while [[ "$line2" =~ \$\{([_0-9A-Za-z]+)\} ]]; do
      local name="${BASH_REMATCH[1]}"
      local value
      if [[ -v pairs_name_value[$name] ]]; then
        value=${pairs_name_value[$name]}
        log_debug "using cache: $name -> $value}"
      else
        value=$($MAKE_COMMAND -v "$name")
        [[ -z $value ]] && value="!!!EMPTY_VARIABLE_$name!!!"  # ${UNDEFINED} -> !!!EMPTY_VARIABLE_UNDEFINED!!!
        log_info "$MAKE_COMMAND -v $name -> $value"
        pairs_name_value[$name]=$value
      fi

      line2=${line2/"${BASH_REMATCH[0]}"/$value}
    done
    while [[ "$line2" =~ !!!EMPTY_VARIABLE_([_0-9A-Za-z]+)!!! ]]; do
      log_info "restore empty variable: ${BASH_REMATCH[0]} -> \${${BASH_REMATCH[1]}}"
      line2=${line2/${BASH_REMATCH[0]}/"\${${BASH_REMATCH[1]}}"}
    done

    if [ "$line" = "$line2" ]; then
      echo "$line2"
    else
      echo "$line2$(echo -e '\t')# $line"
    fi
  done
}

# ------------------------------------------------------------------------------
# command - replace @pub

# c.bash replace "$(c.bash gm -P -m1 "^define_command gm" "cat" < /home/wsh/sh/c.bash)" "hi there" < /home/wsh/sh/c.bash > /tmp/c.bash.d/replace.test.bash
# delta /home/wsh/sh/c.bash /tmp/c.bash.d/replace.test.bash

define_command replace
replace() {
  local -r usage="usage: ... | $PROG replace [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  # XXX: only one? replace(from, to, 1) ?
  python -c "import sys; print(sys.stdin.read().replace(sys.argv[1], sys.argv[2]), end='')" "$FROM" "$TO"
}

# ------------------------------------------------------------------------------
# command - smux @pub

# @ref:socat-pty-exec-mux

define_command smux
smux() {
  local -r usage=$(cat <<EOS
usage:
  $PROG smux [-h | --help]
  $PROG smux NAME -- CMD...
  $PROG smux NAME
  # systemd-run --user -- "$(which c.js)" -v smux-server --name=NAME CMD...
  # pgrep -afi smux
  #   pgrep -af '^socat .+smux'
  #   pgrep -af '^tail .+smux'
  #   pgrep -af 'smux-server'
  # rm -v /home/wsh/.cache/wataash/c.ts-nodejs/smux.* ; pkill -f '^socat .+smux' ; pkill -f '^tail .+smux' ; pkill -f 'smux-server'
EOS
)
  # TODO: arg_parse "$usage" "NAME [--] [CMD...]"
  local NAME="" SEP="" && local -a CMD=() && arg_parse "$usage" "NAME [SEP] [CMD...]" "$@"
  [[ $SEP = "" ]] || [[ $SEP = "--" ]] || { err 0 "error: \"--\" missing; you may wanted to: smux $NAME -- $SEP ${CMD[*]}" && echo "$usage" >&2 && exit 2; }

  local -r IN_PTY="/home/wsh/.cache/wataash/c.ts-nodejs/smux.$NAME.in"                 # /home/wsh/.cache/wataash/c.ts-nodejs/smux.${name}.in -> /dev/pts/0
  local -r OUT_FILE="/home/wsh/.cache/wataash/c.ts-nodejs/smux.$NAME.out"              # /home/wsh/.cache/wataash/c.ts-nodejs/smux.${name}.out
  local -r OUT_FILE_TS="/home/wsh/.cache/wataash/c.ts-nodejs/smux.$NAME.out.ts"        # /home/wsh/.cache/wataash/c.ts-nodejs/smux.${name}.out.ts
  local -r OUT_FILE_RAWTS="/home/wsh/.cache/wataash/c.ts-nodejs/smux.$NAME.out.rawts"  # /home/wsh/.cache/wataash/c.ts-nodejs/smux.${name}.out.rawts

  # -e は symbolik link 先が存在するかチェックしてくれるらしい
  if [[ -e $IN_PTY ]]; then
    log_info "$IN_PTY exists: $IN_PTY -> $(realpath "$IN_PTY")"
    set -x
  else
    # array element in CMD
    [[ ${#CMD[@]} = 0 ]] && die 1 "smux-server not found; CMD needed"
    set -x
    systemd-run --user -- "$(which c.js)" -v smux-server --name="$NAME" -- "${CMD[@]}" && sleep 0.1
  fi

  [[ ! -e $OUT_FILE_TS ]] && [[ ! -e $OUT_FILE_RAWTS ]] && systemd-run --user -- "$(which c.bash)" -vv file_timestamp "$OUT_FILE"

  function stty_size() {
    stty --file="$IN_PTY" cols "$(tput cols)" rows "$(tput lines)"
    log_debug "$IN_PTY size: $(stty --file="$IN_PTY" size)"  # C R of c.bash's pty
  }

  if false; then
    # log_debug "$IN_PTY size: $(stty --file="$IN_PTY" size)"  # 0 0
    stty_size
    trap stty_size SIGWINCH  # TODO: not fired while ↓ ssh...
    # log_debug "$IN_PTY size: $(stty --file="$IN_PTY" size)"  # C R of c.bash's pty
  fi

  # `ssh` to use ~.
  ssh -t localhost "tail -F $OUT_FILE & socat -d -u STDIN,rawer OPEN:$IN_PTY"
  # 最初のセッションだけflushが遅い; ~. して繋ぎ直すと速くなる; TODO: 原因調べる

  # lsof -nP $(tty)  # commands above should not exist (so I added so many </dev/null >FILE 2>&1)
  # update: fd 0 1 2 は持っていなくても、controlling terminal は pts 持っちゃってるのか
  #   nohup shell command | shell command... として実装している限り 避けられないわ
  #   daemonize "cmd..." 必須か？
  #   TODO: daemonize "$(which c.bash)" file_ts "$OUT_FILE"
}

# ------------------------------------------------------------------------------
# command - spotify_code_to_token @pub

: <<'EOS'
c.bash -v spotify_http_server &
----------
set -lx SPOTIFY_APP_AUTH ...
while true
    google-chrome "https://accounts.spotify.com/authorize?client_id=c78a65c5fb94462997b01eeeaf524324&response_type=code&redirect_uri=http://localhost:15350&scope=user-read-currently-playing"
    inotifywait -e create -e modify /tmp/c.bash.d/spotify_http_server.code.txt
    c.bash -vv spotify_code_to_token "http://localhost:15350" "$(cat /tmp/c.bash.d/spotify_http_server.code.txt)"
    set -lx SPOTIFY_TOKEN "$(cat /tmp/c.bash.d/spotify_code_to_token.access_token.txt)"
    c.bash -vv spotify_say_song
end
EOS

define_command spotify_code_to_token
spotify_code_to_token() {
  local -r usage="usage: $PROG spotify_code_to_token [-h | --help] REDIRECT_URI CODE"
  local REDIRECT_URI="" CODE="" && arg_parse "$usage" "REDIRECT_URI CODE" "$@"
  [[ ${SPOTIFY_APP_AUTH+defined} = defined ]] || die 1 'environment variable SPOTIFY_APP_AUTH is not set'
  curl -fSs -X POST -H "Authorization: Basic $SPOTIFY_APP_AUTH" -d code="$CODE" -d redirect_uri="$REDIRECT_URI" -d grant_type=authorization_code "https://accounts.spotify.com/api/token" >/tmp/c.bash.d/spotify_code_to_token.json
  # jq < /tmp/c.bash.d/spotify_code_to_token.json
  log_debug "$(jq < /tmp/c.bash.d/spotify_code_to_token.json)"
  log_info "/tmp/c.bash.d/spotify_code_to_token.access_token.txt"
  log_info "/tmp/c.bash.d/spotify_code_to_token.refresh_token.txt"
  jq -er < /tmp/c.bash.d/spotify_code_to_token.json ".access_token" > /tmp/c.bash.d/spotify_code_to_token.access_token.txt
  jq -er < /tmp/c.bash.d/spotify_code_to_token.json ".refresh_token" > /tmp/c.bash.d/spotify_code_to_token.refresh_token.txt
}

# ------------------------------------------------------------------------------
# command - spotify_http_server @pub

# google-chrome https://accounts.spotify.com/authorize?client_id=c78a65c5fb94462997b01eeeaf524324&response_type=code&redirect_uri=http://localhost:15350&scope=user-read-currently-playing
# -> http://localhost:15350/?code={CODE}

define_command spotify_http_server
spotify_http_server() {
  local -r usage="usage: $PROG spotify_http_server [-h | --help] [PORT]"
  local PORT="" && arg_parse "$usage" "[PORT]" "$@"
  # s  p  o  t  i  f  y
  # S  P  O  T  I  F  Y
  # 73 70 6f 74 69 66 79
  # 53 50 4f 54 49 46 59
  [[ -z $PORT ]] && PORT=15350  # 1 S P

  log_info "listening on $PORT"
  while true; do
    local resp
    resp=$(cat <<'EOS'
HTTP/1.0 200 OK
Content-Type: text/plain

ok
EOS
)
    local req
    req=$(nc -l $PORT -w 1 <<< "$resp")
    log_debug "request: $req"
    [[ $req =~ ^"GET /?code="(.+)" HTTP/1.1" ]] || continue  # drop: GET /favicon.ico HTTP/1.1
    log_debug "> /tmp/c.bash.d/spotify_http_server.req.txt"
    echo "$req" > "/tmp/c.bash.d/spotify_http_server.req.txt"
    log_info "code: ${BASH_REMATCH[1]} > /tmp/c.bash.d/spotify_http_server.code.txt"
    echo "${BASH_REMATCH[1]}" > "/tmp/c.bash.d/spotify_http_server.code.txt"
  done
  unreachable
}

# ------------------------------------------------------------------------------
# command - spotify_say_song @pub

define_command spotify_say_song
spotify_say_song() {
  local -r usage="usage: $PROG spotify_say_song [-h | --help]"
  arg_parse "$usage" "" "$@"
  [[ ${SPOTIFY_TOKEN+defined} = defined ]] || die 1 'environment variable SPOTIFY_TOKEN is not set'

  local rest_secs
  local artist_prev="" album_prev="" name_prev=""
  while true; do
    curl -fSs -X "GET" "https://api.spotify.com/v1/me/player/currently-playing" -H "Accept: application/json" -H "Content-Type: application/json" -H "Authorization: Bearer $SPOTIFY_TOKEN" > /tmp/c.bash.d/spotify_say_song.json

    local artist name
    artist="$(jq -e -r < /tmp/c.bash.d/spotify_say_song.json ".item.artists[0].name")"
    album="$(jq -e -r < /tmp/c.bash.d/spotify_say_song.json ".item.album.name")"
    name="$(jq -e -r < /tmp/c.bash.d/spotify_say_song.json ".item.name")"
    [[ -z $artist ]] && [[ -z $album ]] && [[ -z $name ]] && log_debug "not playing" && sleep 10 && continue
    [[ $artist == "$artist_prev" ]] && [[ $album == "$album_prev" ]] && [[ $name == "$name_prev" ]] && log_debug "$artist - $album - $name; not changed; retry" && sleep 1 && continue
    log_debug "$artist - $album - $name"

    local say_name_begin say_name_secs
    spotify_say_song::say() {
      if [[ $artist != "$artist_prev" ]]; then
        echo "artist" | espeak -v f2
        # echo "$artist" | kakasi -i utf8 -JH | timeout 2 espeak -s120 -v ja+f3 &
        # echo "$artist"                      | timeout 2 espeak -s120 -v f1 || true
        # wait
        if LANG=C grep '[^[:cntrl:][:print:]]' <<< "$artist"; then
          echo "$artist" | kakasi -i utf8 -JH | timeout 2 espeak -s120 -v ja+f3
        else
          echo "$artist"                      | timeout 2 espeak -s120 -v f1 || true
        fi
      fi
      if [[ $album != "$album_prev" ]]; then
        echo "album" | espeak -v f2
        for _ in {1..2}; do
          if LANG=C grep '[^[:cntrl:][:print:]]' <<< "$album"; then
            echo "$album" | kakasi -i utf8 -JH | timeout 2 espeak -s120 -v ja+f3 || true
        else
            echo "$album"                      | timeout 2 espeak -s120 -v f1 || true
        fi
        done
      fi
      say_name_begin=$(date +%s.%N)
      for _ in {1..2}; do
        if LANG=C grep '[^[:cntrl:][:print:]]' <<< "$name"; then
          echo "$name" | kakasi -i utf8 -JH | timeout 2 espeak -s120 -v ja+f3 || true
        else
          echo "$name"                      | timeout 2 espeak -s120 -v f1 || true
        fi
      done
      say_name_secs=$(echo "$(date +%s.%N) - $say_name_begin" | bc)
    }

    spotify_say_song::say
    artist_prev=$artist && album_prev=$album && name_prev=$name

    curl -fSs -X "GET" "https://api.spotify.com/v1/me/player/currently-playing" -H "Accept: application/json" -H "Content-Type: application/json" -H "Authorization: Bearer $SPOTIFY_TOKEN" > /tmp/c.bash.d/spotify_say_song.json
    [[ $name != "$name_prev" ]] && continue  # song changed while speaking
    rest_secs=$(jq -e < /tmp/c.bash.d/spotify_say_song.json "(.item.duration_ms - .progress_ms) / 1000")

    # re-say just before the end of the song
    if (( $(echo "$say_name_secs < $rest_secs - 1" | bc) )); then
      local sleep_secs
      sleep_secs=$(echo "$rest_secs - 1 - $say_name_secs" | bc)
      log_debug "sleep $sleep_secs (then re-say)"
      sleep "$sleep_secs"
      spotify_say_song::say
      continue
    fi

    log_debug "sleep: $rest_secs (no re-say)"
    sleep "$rest_secs"
  done

  unreachable
}

# ------------------------------------------------------------------------------
# command - txt_begin_end @pub
#
# prints:
# c.bash:begin:NAME
# HERE
# c.bash:end:NAME

define_command txt_begin_end
txt_begin_end() {
  local -r usage="usage: [... |] $PROG txt_begin_end [-h | --help] NAME [FILE]"
  local NAME="" FILE="" && arg_parse "$usage" "NAME [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"

  local in_section="false"
  txt_begin_end::process_line() {
    if [[ $in_section == "false" ]]; then
      log_debug "$line"
      [[ $line =~ ^.*"c.bash:begin:$NAME".*$ ]] && in_section="true" && log_info "[in_section: false->true] $line" || true
    else
      log_debug "[in_section] $line"
      [[ $line =~ ^.*"c.bash:end:$NAME".*$ ]] && in_section="false" && log_info "[in_section: true->false] $line" && return
      echo "$line"
    fi
  }

  local line
  while IFS= read -r line; do txt_begin_end::process_line; done <"$FILE"  # IFS= : prevent removeing preceding spaces

  exit 0
}

# ------------------------------------------------------------------------------
# command - pty_qemu @pub

# @ref:qemu-pty

define_command pty_qemu
pty_qemu() {
  local -r usage=$(cat <<EOS
usage:
  $PROG pty_qemu {-h | --help}
  $PROG pty_qemu QEMU_PID
  $PROG pty_qemu netbsd  # "\$(pgrep -f 'qemu-system-x86_64 .+/netbsd.qcow2')"
EOS
)
  local QEMU_PID="" && arg_parse "$usage" "QEMU_PID" "$@"
  [[ $QEMU_PID = 'netbsd' ]] && QEMU_PID=$(pgrep -f 'qemu-system-x86_64 .+/netbsd.qcow2')

  [[ $QEMU_PID =~ ^[0-9]+$ ]] || die 1 "invalid QEMU_PID: $QEMU_PID"

  local -r IN_PTY="/tmp/c.bash.d/pty.qemu.$QEMU_PID"                    # /tmp/c.bash.d/pty.qemu.0
  local -r OUT_FILE="/tmp/c.bash.d/pty.qemu.$QEMU_PID.out"              # /tmp/c.bash.d/pty.qemu.0.out
  local -r OUT_FILE_TS="/tmp/c.bash.d/pty.qemu.$QEMU_PID.out.ts"        # /tmp/c.bash.d/pty.qemu.0.out.ts
  local -r OUT_FILE_RAWTS="/tmp/c.bash.d/pty.qemu.$QEMU_PID.out.rawts"  # /tmp/c.bash.d/pty.qemu.0.out.rawts

  realpath "/proc/$QEMU_PID/exe" | grep -q '/qemu-system-' || die 1 "QEMU_PID $QEMU_PID is not a qemu process; /proc/$QEMU_PID/exe: $(realpath "/proc/$QEMU_PID/exe")"
  ln -fsv "/dev/pts/$(grep -r tty-index "/proc/$QEMU_PID/fdinfo" | cut -f2)" "$IN_PTY"
  set -x
  # shellcheck disable=SC2046  # Quote this to prevent word splitting
  if [ ! -f "$OUT_FILE" ]; then
    nohup </dev/null >"$OUT_FILE" 2>&1 cat "$IN_PTY" & disown
    nohup </dev/null $(: '1>pipe') 2>&1 tail -F "$OUT_FILE" | cat -A 2>&1 | ts "%F %T" >"$OUT_FILE_TS" 2>&1 & disown
    nohup </dev/null $(: '1>pipe') 2>&1 tail -F "$OUT_FILE" | cat    2>&1 | ts "%F %T" >"$OUT_FILE_RAWTS" 2>&1 & disown
  fi
  ssh -t localhost "tail -F $OUT_FILE & socat -d -u STDIN,rawer OPEN:$IN_PTY"
}

# ------------------------------------------------------------------------------
# command - pty_usb @pub

define_command pty_usb
pty_usb() {
  local -r usage=$(cat <<EOS
usage:
  $PROG pty_usb {-h | --help}
  $PROG pty_usb DEVICE BAUD
  $PROG pty_usb /dev/ttyUSB0 115200
EOS
)
  local DEVICE BAUD="" && arg_parse "$usage" "DEVICE BAUD" "$@"

  local -r IN_PTY="/tmp/c.bash.d/pty.$(basename "$DEVICE")"                    # /tmp/c.bash.d/pty.ttyUSB0
  local -r OUT_FILE="/tmp/c.bash.d/pty.$(basename "$DEVICE").out"              # /tmp/c.bash.d/pty.ttyUSB0.out
  local -r OUT_FILE_TS="/tmp/c.bash.d/pty.$(basename "$DEVICE").out.ts"        # /tmp/c.bash.d/pty.ttyUSB0.out.ts
  local -r OUT_FILE_RAWTS="/tmp/c.bash.d/pty.$(basename "$DEVICE").out.rawts"  # /tmp/c.bash.d/pty.ttyUSB0.out.rawts

  set -x
  lsof -nP "$OUT_FILE" | grep '^cat' || rm -fv "$OUT_FILE"
  if [ ! -f "$OUT_FILE" ]; then
    # @ref:stty-tty-usb
    # stty: /dev/ttyUSB0: unable to perform all requested operations というエラーで失敗することがあるが、もう一回実行すれば通る; 謎
    sudo stty --file="$DEVICE" 1:0:80001cb2:0:3:1c:7f:15:4:5:1:0:11:13:1a:0:12:f:17:16:0:0:0:0:0:0:0:0:0:0:0:0:0:0:0:0 ||
      sudo stty --file="$DEVICE" 1:0:80001cb2:0:3:1c:7f:15:4:5:1:0:11:13:1a:0:12:f:17:16:0:0:0:0:0:0:0:0:0:0:0:0:0:0:0:0
    sudo stty --file="$DEVICE" "$BAUD"
    # sudo not needed:
    # ls -l /dev/ttyUSB0  # crw-rw---- 1 root dialout 188, 0  2月 27 13:56 /dev/ttyUSB0
    # groups              # dialout
    nohup </dev/null >"$OUT_FILE" 2>&1 cat "$DEVICE" & disown
    # shellcheck disable=SC2046  # Quote this to prevent word splitting
    nohup </dev/null $(: '1>pipe') 2>&1 tail -F "$OUT_FILE" | cat -A 2>&1 | ts "%F %T" > "$OUT_FILE_TS" 2>&1 & disown
    # shellcheck disable=SC2046  # Quote this to prevent word splitting
    nohup </dev/null $(: '1>pipe') 2>&1 tail -F "$OUT_FILE" | cat    2>&1 | ts "%F %T" > "$OUT_FILE_RAWTS" 2>&1 & disown
  fi
  ssh -t localhost "tail -F $OUT_FILE & socat -d -u STDIN,rawer OPEN:$DEVICE"
}

# ------------------------------------------------------------------------------
# command - qemu_net_setup @pub

# TODO: 安定したらsystemd oneshot

define_command qemu_net_setup
qemu_net_setup() {
  local -r usage="usage: $PROG qemu_net_setup [-h | --help]"
  arg_parse "$usage" "" "$@"
  [ "$(cat /proc/sys/net/ipv4/ip_forward)" = 1 ] || die 1 "/proc/sys/net/ipv4/ip_forward: $(cat /proc/sys/net/ipv4/ip_forward) != 1"

  set -x

  # @ref:qemu-bridge @ref:iptables-bridge

  sudo ip link add br100 type bridge; sudo ip link set br100 up; sudo ip address add 172.31.100.100/24 dev br100
  sudo ip link add br101 type bridge; sudo ip link set br101 up; sudo ip address add 172.31.101.100/24 dev br101
  sudo ip link add br102 type bridge; sudo ip link set br102 up; sudo ip address add 172.31.102.100/24 dev br102

  sudo nft add table ip nat0
  sudo nft 'add chain nat0 postrouting0 { type nat hook postrouting priority 100 ; }'
  sudo nft add rule ip nat0 postrouting0 ip saddr 172.31.100.0/24 counter masquerade

  # sudo iptables -t nat -A POSTROUTING -s 172.31.100.0/24 ! -d 172.31.100.0/24 -j MASQUERADE
  # @ref:iptables-bridge
  # ! -d 172.31.100.0/24 が無いとguest間通信に問題がある
  #   172.31.100.85->172.31.100.38:
  #     qemu-ubu 172.31.100.85->172.31.100.38 -> tap0 -> br0 MASQUERADE 172.31.100.100->172.31.100.38 -> tap1 -> qemu .38: .38 から見ると .100 から来たように見える

  sudo systemctl start isc-dhcp-server.service
}

# ------------------------------------------------------------------------------
# command - qemu_pty @pub

# compat

define_command qemu_pty
qemu_pty() {
  pty_qemu "${@}"
}

# ------------------------------------------------------------------------------
# command - xargs_delay @pub

define_command xargs_delay
xargs_delay() {
  local -r usage="usage: ... | $PROG xargs_delay [-h | --help] [-L1] [-I III] COMMAND..."
  local -a COMMAND=() && arg_parse "$usage" "COMMAND..." "$@"
  local -a lines=()
  local -A line_latest_epochs=()
  while true; do
    local line
    IFS= read -r -t0.1 line || true
    if [[ $line != "" ]]; then
      if ! [[ -v line_latest_epochs[$line] ]]; then
        log_info "$line"
        lines+=("$line")
      fi
      line_latest_epochs[$line]=$(date "+%s.%N")
    fi

    log_debug "scanning lines..."
    local -a lines_next=()
    for line_ in "${lines[@]}"; do
      now=$(date "+%s.%N")
      log_debug "$line_: $now - ${line_latest_epochs[$line_]} = $(echo "$now - ${line_latest_epochs[$line_]}" | bc)"
      if [[ $(echo "$now - ${line_latest_epochs[$line_]} > 1" | bc) = 1 ]]; then
        log_info "$line_: one second elapsed since the last seen; fire: ${COMMAND[*]} $line_"
        echo "$line_" | xargs "${COMMAND[@]}"
        unset "line_latest_epochs[$line_]"
      else
        lines_next+=("$line_")
      fi
    done
    [[ ${#lines_next[@]} != "0" ]] && log_debug "not fired: ${lines_next[*]}"
    lines=("${lines_next[@]}")
  done
  echo 'code here'
  exit 0
}

# ------------------------------------------------------------------------------
# command - z_meta_publish_self @pub

: <<'DOC'
c.bash -v z_meta_publish_self > ~/src/scraps/c.bash
cd ~/src/scraps/
git ...
DOC

define_command z_meta_publish_self
z_meta_publish_self() {
  local -r usage="usage: $PROG z_meta_publish_self [-h | --help]"
  arg_parse "$usage" "" "$@"
  local public="true"
  while IFS= read -r line; do  # IFS= : prevent removeing preceding spaces
    # # section @pub
    if [[ $line =~ ^#.+@pub$ ]]; then
      log_info "[public: $public -> true] $line"
      public="true"
    # # command - COMMAND  (private unless explicitly marked as @pub)
    # # section @private
    elif [[ $line =~ ^"# command - " ]] || [[ $line =~ ^#.+[@]private$ ]]; then
      log_info "[public: $public -> false] $line"
      public="false"
    else
      log_debug "$line"
    fi
    [[ $public = "false" ]] && continue
    [[ $line =~ [@]private_line ]] && continue
    echo "$line"
  done < "$(self_real_path)"

  return 0
}

# ------------------------------------------------------------------------------
# archilves

archives() {
  # 0 references

  # /usr/local/bin/bats               [](file:///usr/local/bin/bats)
  # /usr/local/libexec/bats-core/bats [](file:///usr/local/libexec/bats-core/bats)

  # path - parent directories

  # ref: /usr/local/bin/bats
  FILE_PATH=$(readlink -f "${BASH_SOURCE[0]}")
  echo "$FILE_PATH"              # /home/wsh/sh/c.bash
  echo "${FILE_PATH%/*}"         # /home/wsh/sh
  echo "${FILE_PATH%/*/*}"       # /home/wsh
  echo "${FILE_PATH%/*/*/*}"     # /home
  echo "${FILE_PATH%/*/*/*/*}"   #
  echo "${FILE_PATH%/*/*/*/*/*}" # /home/wsh/sh/c.bash

  # shell arguments array to sh -c

  # https://stackoverflow.com/questions/73722324/convert-bash-array-to-a-single-stringified-shell-argument-list-handable-by-sh
  shell_arguments=(echo "foo bar" baz)
  sh -c "${shell_arguments[*]@Q}"
  sh -c "${*@Q}"  # not tested
  sh -c "${@@Q}"  # not tested
}

# ------------------------------------------------------------------------------
# main tests

# shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
# shellcheck disable=SC2154  # * is referenced but not assigned.
test_help_usage() { #@test
  run -0 --separate-stderr bash ~/sh/c.bash -h
  [[ ${lines[0]} = 'usage:' ]] && [[ $stderr = '' ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -h --
  [[ ${lines[0]} = 'usage:' ]] && [[ $stderr = '' ]] || bats_run_debug_fail >&3

  run -2 --separate-stderr bash ~/sh/c.bash
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = $'\e[31m'$'command not specified\e[0m' ]] && [[ ${stderr_lines[1]} = 'usage:' ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash --
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = $'\e[31m'$'command not specified\e[0m' ]] && [[ ${stderr_lines[1]} = 'usage:' ]] || bats_run_debug_fail >&3

  run -2 --separate-stderr bash ~/sh/c.bash -x
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = *': illegal option -- x' ]] && [[ ${stderr_lines[1]} = 'usage:' ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -x --
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = *': illegal option -- x' ]] && [[ ${stderr_lines[1]} = 'usage:' ]] || bats_run_debug_fail >&3

  run -2 --separate-stderr bash ~/sh/c.bash    no_such_command
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = $'\e[31m'$'no such command: no_such_command\e[0m' ]] && [[ ${stderr_lines[1]} = 'usage:' ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -- no_such_command
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = $'\e[31m'$'no such command: no_such_command\e[0m' ]] && [[ ${stderr_lines[1]} = 'usage:' ]] || bats_run_debug_fail >&3

  # 0template

  run -0 --separate-stderr bash ~/sh/c.bash -v    0template
  [[ $output = 'code here' ]] && [[ $stderr = '' ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -v -- 0template
  [[ $output = 'code here' ]] && [[ $stderr = '' ]] || bats_run_debug_fail >&3

  run -0 --separate-stderr bash ~/sh/c.bash -v    0template -h
  [[ $output = 'usage: c.bash 0template [-h | --help]' ]] && [[ $stderr = '' ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -v -- 0template -h
  [[ $output = 'usage: c.bash 0template [-h | --help]' ]] && [[ $stderr = '' ]] || bats_run_debug_fail >&3

  run -2 --separate-stderr bash ~/sh/c.bash -v    0template -z
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = $'\e[31m'$'error: excess argument(s): -z\e[0m' ]] && [[ ${stderr_lines[1]} = 'usage: c.bash 0template [-h | --help]' ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -v -- 0template -z
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = $'\e[31m'$'error: excess argument(s): -z\e[0m' ]] && [[ ${stderr_lines[1]} = 'usage: c.bash 0template [-h | --help]' ]] || bats_run_debug_fail >&3

  # 0template_arg

  run -2 --separate-stderr bash ~/sh/c.bash -v    0template_arg
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = $'\e[31m'$'error: required argument: \"ARG\" missing\e[0m' ]] && [[ ${stderr_lines[1]} = 'usage: c.bash 0template_arg [-h | --help] ARG' ]] || bats_run_debug_fail >&3

  run -0 --separate-stderr bash ~/sh/c.bash -v    0template_arg -h
  [[ $output = 'usage: c.bash 0template_arg [-h | --help] ARG' ]] && [[ $stderr = '' ]] || bats_run_debug_fail >&3

  run -0 --separate-stderr bash ~/sh/c.bash -v    0template_arg arg1
  [[ $output = 'ARG: arg1' ]] && [[ $stderr = '' ]] || bats_run_debug_fail >&3

  run -2 --separate-stderr bash ~/sh/c.bash -v    0template_arg arg1 arg2 arg3
  [[ $output = '' ]] && [[ ${stderr_lines[0]} = $'\e[31m'$'error: excess argument(s): arg2 arg3\e[0m' ]] && [[ ${stderr_lines[1]} = 'usage: c.bash 0template_arg [-h | --help] ARG' ]] || bats_run_debug_fail >&3
}

# ------------------------------------------------------------------------------
# main

[[ $IN_BATS == "yes" ]] && return 0

if [[ ${HAVE_UTIL_LINUX_GETOPT+defined} != defined ]]; then
  if getopt --version 2>/dev/null | grep -q util-linux; then
    HAVE_UTIL_LINUX_GETOPT='yes'
  else
    HAVE_UTIL_LINUX_GETOPT='no'
  fi
fi

OPT_q="false"
OPT_v=0

if not_yet && [ "$HAVE_UTIL_LINUX_GETOPT" = 'yes' ]; then
  # TODO:
  #   c.bash -v 0template -z
  #   prevent parsing -z !
  OPTIONS=$(getopt -o hqv --longoptions help -n "$0" -- "$@") || { top_usage >&2 && exit 2; }
  eval set -- "$OPTIONS"
  while true; do
    case $1 in
    -h|--help) top_usage; exit 0;;
    -q) OPT_q="true"; shift;;
    -v) ((OPT_v+=1)); shift;;
    --) shift; break;;
    -*) unreachable;;
    *) break;;  # COMMAND
    esac
  done
else
  [ $# != 0 ] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && top_usage && exit 0
  OPT_q="false"
  OPT_v=0
  while getopts hqv- OPT; do
    case $OPT in
    h) top_usage; exit 0;;
    q) OPT_q="true";;
    v) ((OPT_v+=1));;
    -) break;;  # COMMAND
    ?) top_usage >&2 && exit 2;;
    *) unreachable;;
    esac
  done
  shift $((OPTIND - 1))
fi

[[ $OPT_q == "true" ]] && (( OPT_v > 0 )) && die 1 "-q and -v are mutually exclusive"
[[ $OPT_q == "true" ]] && log_setlevel $LOG_ERR
(( OPT_v == 1 )) && log_setlevel $LOG_INFO
(( OPT_v > 1 )) && log_setlevel $LOG_DEBUG

if (( $# == 0 )); then
  err 0 "command not specified"
  top_usage >&2
  exit 2
else
  COMMAND_=$1 && shift
fi

if ! [[ -v _commands[$COMMAND_] ]]; then
  err 0 "no such command: $COMMAND_"
  top_usage >&2
  exit 2
fi

"$COMMAND_" "$@"
exit $?
