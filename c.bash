#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2022-2025 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

# shellcheck disable=SC2317  # Command appears to be unreachable. Check usage (or ignore if invoked indirectly).

: <<'DOC'
mini CLIs

test: bats ~/sh/c.bash

usage error -> exit 2
https://git.savannah.gnu.org/cgit/bash.git/tree/shell.h?h=bash-5.2#n71 EX_USAGE - EX_SHERRBASE == 2 bash -c 'help --foo' -> 2
https://salsa.debian.org/kernel-team/initramfs-tools/-/blob/v0.142/mkinitramfs#L36                  mkinitramfs --foo    -> 2
https://go.googlesource.com/go/+/refs/tags/go1.20.1/src/cmd/go/main.go#235                          go foo               -> 2
https://www.freedesktop.org/software/systemd/man/systemd.exec.html 2 EXIT_INVALIDARGUMENT
DOC

# TODO: /tmp/c.bash.d.$USER/ ? use XDG dir?
# TODO: multi-process safety
mkdir -pv /tmp/c.bash.d/

# [todo_test_main]
: <<'COMMENT'
# cwd: /tmp/cwd/
# /sh/c.bash
# /bin/c.bash (in PATH, symlink to /sh/c.bash)
# /tmp/s1     (#!/bin/bash \n source c.bash)
# /tmp/s2     (#!/bin/bash \n source /bin/../bin/c.bash)
# /tmp/s3     (#!/bin/bash \n source /sh/../sh/c.bash)
# /tmp/e1     (#!/bin/bash \n exec c.bash)
# /tmp/e2     (#!/bin/bash \n exec /bin/../bin/c.bash)
# /tmp/e3     (#!/bin/bash \n exec /sh/../sh/c.bash)

mkdir -p /tmp/cwd/ && cd /tmp/cwd/
sudo mkdir -p /sh/ && sudo cp ~/sh/c.bash /sh/c.bash && sudo chmod +x /sh/c.bash
sudo ln -fs /sh/c.bash /bin/c.bash
echo -e '#!/bin/bash\nsource c.bash'             >/tmp/s1 && chmod +x /tmp/s1
echo -e '#!/bin/bash\nsource /bin/../bin/c.bash' >/tmp/s2 && chmod +x /tmp/s2
echo -e '#!/bin/bash\nsource /sh/../sh/c.bash'   >/tmp/s3 && chmod +x /tmp/s3
echo -e '#!/bin/bash\nexec   c.bash'             >/tmp/e1 && chmod +x /tmp/e1
echo -e '#!/bin/bash\nexec   /bin/../bin/c.bash' >/tmp/e2 && chmod +x /tmp/e2
echo -e '#!/bin/bash\nexec   /sh/../sh/c.bash'   >/tmp/e3 && chmod +x /tmp/e3

# invocation                                  # $0                 | ${BASH_SOURCE[*]}          | $realpath $0              | $realpath ${BASH_SOURCE[0]}
PATH=/bin c.bash                              # /bin/c.bash        | /bin/c.bash                | /sh/c.bash                | /sh/c.bash                  [c.bash]
PATH=/bin bash c.bash                         # c.bash             | /bin/c.bash                | /tmp/cwd/c.bash (INVALID) | /sh/c.bash
PATH=/bin /bin/../bin/c.bash                  # /bin/../bin/c.bash | /bin/../bin/c.bash         | /sh/c.bash                | /sh/c.bash                  [/bin/c.bash]
PATH=/bin /sh/../sh/c.bash                    # /sh/../sh/c.bash   | /sh/../sh/c.bash           | /sh/c.bash                | /sh/c.bash                  [/sh/c.bash]
PATH=/bin /tmp/e1                             # /bin/c.bash        | /bin/c.bash                | /sh/c.bash                | /sh/c.bash                  [c.bash]
PATH=/bin /tmp/e2                             # /bin/../bin/c.bash | /bin/../bin/c.bash         | /sh/c.bash                | /sh/c.bash                  [/bin/c.bash]
PATH=/bin /tmp/e3                             # /sh/../sh/c.bash   | /sh/../sh/c.bash           | /sh/c.bash                | /sh/c.bash                  [/sh/c.bash]
PATH=/bin /tmp/s1                             # /tmp/s1            | /bin/c.bash /tmp/s1        | /tmp/s1                   | /sh/c.bash
PATH=/bin /tmp/s2                             # /tmp/s2            | /bin/../bin/c.bash /tmp/s2 | /tmp/s2                   | /sh/c.bash
PATH=/bin /tmp/s3                             # /tmp/s3            | /sh/../sh/c.bash /tmp/s3   | /tmp/s3                   | /sh/c.bash
PATH=/bin bash -s -- </sh/c.bash              # bash               |                            | /tmp/cwd/bash (INVALID)   | [err_arr], realpath: '': No such file or directory
PATH=/bin bash -c "source c.bash"             # bash               | /bin/c.bash                | /tmp/cwd/bash (INVALID)   | /sh/c.bash
PATH=/bin bash -c "source /bin/../bin/c.bash" # bash               | /bin/../bin/c.bash         | /tmp/cwd/bash (INVALID)   | /sh/c.bash
PATH=/bin bash -c "source /sh/../sh/c.bash"   # bash               | /sh/../sh/c.bash           | /tmp/cwd/bash (INVALID)   | /sh/c.bash
PATH=/bin bash -c "exec c.bash"               # /bin/c.bash        | /bin/c.bash                | /sh/c.bash                | /sh/c.bash                  [c.bash]
PATH=/bin bash -c "exec /bin/../bin/c.bash"   # /bin/../bin/c.bash | /bin/../bin/c.bash         | /sh/c.bash                | /sh/c.bash                  [/bin/c.bash]
PATH=/bin bash -c "exec /sh/../sh/c.bash"     # /sh/../sh/c.bash   | /sh/../sh/c.bash           | /sh/c.bash                | /sh/c.bash                  [/sh/c.bash]

# with/without "bash": no effect if $0 is absolute path:
(PATH=/bin; cmd=(/bin/../bin/c.bash); [[ $("${cmd[@]}") == "$(bash "${cmd[@]}")" ]] || echo "err: ${cmd[@]}")
(PATH=/bin; cmd=(/sh/../sh/c.bash  ); [[ $("${cmd[@]}") == "$(bash "${cmd[@]}")" ]] || echo "err: ${cmd[@]}")
(PATH=/bin; cmd=(/tmp/e1           ); [[ $("${cmd[@]}") == "$(bash "${cmd[@]}")" ]] || echo "err: ${cmd[@]}")
(PATH=/bin; cmd=(/tmp/e2           ); [[ $("${cmd[@]}") == "$(bash "${cmd[@]}")" ]] || echo "err: ${cmd[@]}")
(PATH=/bin; cmd=(/tmp/e3           ); [[ $("${cmd[@]}") == "$(bash "${cmd[@]}")" ]] || echo "err: ${cmd[@]}")
(PATH=/bin; cmd=(/tmp/s1           ); [[ $("${cmd[@]}") == "$(bash "${cmd[@]}")" ]] || echo "err: ${cmd[@]}")
(PATH=/bin; cmd=(/tmp/s2           ); [[ $("${cmd[@]}") == "$(bash "${cmd[@]}")" ]] || echo "err: ${cmd[@]}")
(PATH=/bin; cmd=(/tmp/s3           ); [[ $("${cmd[@]}") == "$(bash "${cmd[@]}")" ]] || echo "err: ${cmd[@]}")

[err_arr]: bash: line 42: BASH_SOURCE: bad array subscript
COMMENT
false && printf "# %-18s | %-26s | %-25s | %s\n" "$0" "${BASH_SOURCE[*]}" "$(realpath "$0")" "$(realpath "${BASH_SOURCE[0]}")" && exit 0

: <<'COMMENT'
bats ~/sh/c.bash

# $0                                          | ${BASH_SOURCE[*]}
# /usr/local/libexec/bats-core/bats-exec-file | /tmp/bats-run-ZiMPSb/bats.1465734.src /usr/local/libexec/bats-core/bats-exec-file /usr/local/libexec/bats-core/bats-exec-file
# /usr/local/libexec/bats-core/bats-exec-test | /tmp/bats-run-ZiMPSb/bats.1465734.src /usr/local/lib/bats-core/preprocessing.bash /usr/local/libexec/bats-core/bats-exec-test
COMMENT
false && {
  printf "# %s | %s\n" "$0" "${BASH_SOURCE[*]}" >&3
  d="$0"                 ; [[ "$d" == "$(realpath "$d")" ]] || { echo "BUG at line $LINENO" >&3; exit 1; }
  d="${BASH_SOURCE[-1]}" ; [[ "$d" == "$(realpath "$d")" ]] || { echo "BUG at line $LINENO" >&3; exit 1; }
}

#                    | C_BASH_DO_MAIN yes                   | C_BASH_DO_MAIN no
# -------------------+--------------------------------------+------------------
# C_BASH_IN_BATS yes |                                      | bats c.bash
# -------------------+--------------------------------------+--------------
# C_BASH_IN_BATS no  | c.bash                               | source c.bash
#                    | bash c.bash                          | bash -c "source /home/wsh/sh/c.bash"
#                    | bash <c.bash                         |
if [[ "${#BASH_SOURCE[@]}" == "0" ]]; then
  # bash <c.bash
  C_BASH_DO_MAIN="yes"
elif [[ "${#BASH_SOURCE[@]}" == "1" ]]; then
  C_BASH_DO_MAIN="yes"  # c.bash / bash c.bash
  [[ -v BASH_EXECUTION_STRING ]] && C_BASH_DO_MAIN="no"  # bash -c "source /home/wsh/sh/c.bash"
  # likely [[ $(realpath "${BASH_SOURCE[-1]}") == "/home/wsh/sh/c.bash" ]]
elif [[ "${#BASH_SOURCE[@]}" == "2" ]]; then
  # source c.bash
  C_BASH_DO_MAIN="no"
elif [[ "${#BASH_SOURCE[@]}" == "3" ]]; then
  # bats c.bash
  # source a -> source c.bash
  C_BASH_DO_MAIN="no"
else
  # source a -> source b -> ... source c.bash
  C_BASH_DO_MAIN="no"
fi

[[ "$0" =~ ^.+'/bats-core/'.+$ ]] && C_BASH_IN_BATS="yes" || C_BASH_IN_BATS="no"
# echo "$0 -> C_BASH_IN_BATS=$C_BASH_IN_BATS" >/dev/pts/0

[[ $C_BASH_DO_MAIN == "yes" ]] && [[ $C_BASH_IN_BATS == "yes" ]] && unreachable

if [[ $C_BASH_DO_MAIN == "yes" ]]; then
set -eu -o errtrace
trap 'echo -e "\e[31m""exit $? at ${BASH_SOURCE[0]} line $LINENO: [\$BASH_COMMAND: $BASH_COMMAND] $(sed -n "$LINENO"p "${BASH_SOURCE[0]}")\e[0m"' >&2 ERR
PS4='+ \e[37m''$LINENO: \e[0m'
fi

# de-lib: readlink -f "${BASH_SOURCE[0]}"
self_real_path() {
  readlink -f "${BASH_SOURCE[0]}"  # ref: https://github.com/bats-core/bats-core/blob/v1.10.0/bin/bats#L52
}

pre_main() { :; }
_pre_main() {
  [[ -v C_BASH_IN_PRE_MAIN ]] && return  # prevent infinite recursion when executed self with cmd()
  export C_BASH_IN_PRE_MAIN=1
  pre_main
}

# ------------------------------------------------------------------------------
# lib

# # C_BASH_FD_DEVNULL
# exec {C_BASH_FD_DEVNULL}<> /dev/null
# set -x
# BASH_XTRACEFD=$C_BASH_FD_DEVNULL echo foo
# BASH_XTRACEFD=$C_BASH_FD_DEVNULL echo foo  # /home/wsh/bin/c.bash: line 152: BASH_XTRACEFD: 10: invalid value for trace file descriptor
# # instead: (BASH_XTRACEFD=$fd_devnull set +x; echo foo) {fd_devnull}>/dev/null

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
  local -a dst_array       && array_copy::by_elems "dst_array" "a" "b" && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a dst_array=(x)   && array_copy::by_elems "dst_array" "a" "b" && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref         && array_copy::by_elems "nameref"   "a" "b" && [[ ${nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref=(x)     && array_copy::by_elems "nameref"   "a" "b" && [[ ${nameref[*]} == "a b" ]] || bats_run_debug_fail >&3

  # shellcheck disable=SC2076  # Remove quotes from right-hand side of =~ to match as a regex rather than literally
  run -1 --separate-stderr array_copy "arr" "arr" && [[ $output == "" ]] && [[ $stderr =~ "array_copy(): src_array == dst_array == \"arr\"" ]] || bats_run_debug_fail >&3

  local -a __nameref=(a b) _nameref  && array_copy "__nameref" "_nameref"  >&3 && [[ ${__nameref[*]} == "a b" ]] && [[ ${_nameref[*]}  == "a b" ]] || bats_run_debug_fail >&3
  local -a __nameref=(a b) dst_array && array_copy "__nameref" "dst_array" >&3 && [[ ${__nameref[*]} == "a b" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a __nameref=(a b) nameref   && array_copy "__nameref" "nameref"   >&3 && [[ ${__nameref[*]} == "a b" ]] && [[ ${nameref[*]}   == "a b" ]] || bats_run_debug_fail >&3
  local -a _nameref=(a b)  __nameref && array_copy "_nameref"  "__nameref" >&3 && [[ ${_nameref[*]}  == "a b" ]] && [[ ${__nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a _nameref=(a b)  dst_array && array_copy "_nameref"  "dst_array" >&3 && [[ ${_nameref[*]}  == "a b" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a _nameref=(a b)  nameref   && array_copy "_nameref"  "nameref"   >&3 && [[ ${_nameref[*]}  == "a b" ]] && [[ ${nameref[*]}   == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref=(a b)   __nameref && array_copy "nameref"   "__nameref" >&3 && [[ ${nameref[*]}   == "a b" ]] && [[ ${__nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref=(a b)   _nameref  && array_copy "nameref"   "_nameref"  >&3 && [[ ${nameref[*]}   == "a b" ]] && [[ ${_nameref[*]}  == "a b" ]] || bats_run_debug_fail >&3
  local -a nameref=(a b)   dst_array && array_copy "nameref"   "dst_array" >&3 && [[ ${nameref[*]}   == "a b" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a src_array=(a b) __nameref && array_copy "src_array" "__nameref" >&3 && [[ ${src_array[*]} == "a b" ]] && [[ ${__nameref[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a src_array=(a b) _nameref  && array_copy "src_array" "_nameref"  >&3 && [[ ${src_array[*]} == "a b" ]] && [[ ${_nameref[*]}  == "a b" ]] || bats_run_debug_fail >&3
  local -a src_array=(a b) dst_array && array_copy "src_array" "dst_array" >&3 && [[ ${src_array[*]} == "a b" ]] && [[ ${dst_array[*]} == "a b" ]] || bats_run_debug_fail >&3
  local -a src_array=(a b) nameref   && array_copy "src_array" "nameref"   >&3 && [[ ${src_array[*]} == "a b" ]] && [[ ${nameref[*]}   == "a b" ]] || bats_run_debug_fail >&3
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
      if [[ "$left" == "$right" ]]; then
        append=0
        break
      fi
    done
    [[ $append == "1" ]] && result_array+=("$left")
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
  local -a result left=(a b c) right=(b   z) && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} == "a c" ]] || bats_run_debug_fail >&3
  local -a result left=(a b c) right=(b c z) && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} == "a" ]] || bats_run_debug_fail >&3
  local -a result left=(a b c) right=(b   z) && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} == "a c" ]] || bats_run_debug_fail >&3
  local -a result left=()      right=(b c z) && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} == "" ]] || bats_run_debug_fail >&3
  local -a result left=(a b c) right=()      && array_subtract "result" "left" "right" >&3 && [[ ${result[*]} == "a b c" ]] || bats_run_debug_fail >&3

  local -a nameref left=(a b c) right=(b z) && array_subtract "nameref" "left" "right" >&3 && [[ ${nameref[*]} == "a c" ]] || bats_run_debug_fail >&3
  local -a result nameref=(a b c) right=(b z) && array_subtract "result" "nameref" "right" >&3 && [[ ${result[*]} == "a c" ]] || bats_run_debug_fail >&3
  local -a result left=(a b c) nameref=(b z) && array_subtract "result" "left" "nameref" >&3 && [[ ${result[*]} == "a c" ]] || bats_run_debug_fail >&3
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
    [[ ${a+defined} == "defined" ]] && echo a defined  # not defined
    [[ ${b+defined} == "defined" ]] && echo b defined
    [[ ${c+defined} == "defined" ]] && echo c defined
    [[ ${d+defined} == "defined" ]] && echo d defined
    # b=xxx
    # c=
    # d=
    local
    local -p

    fn() {
      [[ ${outer_a+defined} == "defined" ]] && echo outer_a defined  # not defined
      [[ ${outer_b+defined} == "defined" ]] && echo outer_b defined
      [[ ${outer_c+defined} == "defined" ]] && echo outer_c defined
      [[ ${outer_d+defined} == "defined" ]] && echo outer_d defined
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
  [[ ${!name+defined} == "defined" ]]  # true for both locals and globals
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

cmd() {
  (
    BASH_XTRACEFD=$fd_devnull set +x
    bash "$(self_real_path)" "${global_flags[@]}" "$@"
  ) {fd_devnull}>/dev/null
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
  run -0 echo_array_name "arr"     && [[ $output == $'$arr:\n$1: a\n$2: b' ]] || bats_run_debug_fail >&3
  local -a nameref=(a b)
  run -0 echo_array_name "nameref" && [[ $output == $'$nameref:\n$1: a\n$2: b' ]] || bats_run_debug_fail >&3
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

  if false; then  # slow
  log_error() { ( BASH_XTRACEFD=$fd_devnull : ) {fd_devnull}>/dev/null; }
  log_warning() { ( BASH_XTRACEFD=$fd_devnull : ) {fd_devnull}>/dev/null; }
  log_info() { ( BASH_XTRACEFD=$fd_devnull : ) {fd_devnull}>/dev/null; }
  log_debug() { ( BASH_XTRACEFD=$fd_devnull : ) {fd_devnull}>/dev/null; }
  fi
  log_error() { :; }
  log_warning() { :; }
  log_info() { :; }
  log_debug() { :; }

  ((LOG_LEVEL < LOG_ERR)) && return 0
  log_error() { ( BASH_XTRACEFD=$fd_devnull set +x; printf '\e[31m[E] %s: %s\e[0m\n' "$(caller1)" "$*" >&2 ) {fd_devnull}>/dev/null; }
  ((LOG_LEVEL < LOG_WARNING)) && return 0
  log_warning() { ( BASH_XTRACEFD=$fd_devnull set +x; printf '\e[33m[W] %s: %s\e[0m\n' "$(caller1)" "$*" >&2 ) {fd_devnull}>/dev/null; }
  ((LOG_LEVEL < LOG_INFO)) && return 0
  log_info() { ( BASH_XTRACEFD=$fd_devnull set +x; printf '\e[34m[I] %s: %s\e[0m\n' "$(caller1)" "$*" >&2 ) {fd_devnull}>/dev/null; }
  ((LOG_LEVEL < LOG_DEBUG)) && return 0
  log_debug() { ( BASH_XTRACEFD=$fd_devnull set +x; printf '\e[37m[D] %s: %s\e[0m\n' "$(caller1)" "$*" >&2 ) {fd_devnull}>/dev/null; }
}

LOG_LEVEL=$LOG_WARNING
log_setlevel $LOG_LEVEL

# set -x
# log_error "error"
# log_warning "warning"
# log_info "info"
# log_debug "debug"
# #( BASH_XTRACEFD=$fd_devnull set +x; log_error "error" ) {fd_devnull}>/dev/null
# #( BASH_XTRACEFD=$fd_devnull set +x; log_warning "warning" ) {fd_devnull}>/dev/null
# #( BASH_XTRACEFD=$fd_devnull set +x; log_info "info" ) {fd_devnull}>/dev/null
# #( BASH_XTRACEFD=$fd_devnull set +x; log_debug "debug" ) {fd_devnull}>/dev/null
# exit 42

net_connected_4() {
  curl -s --no-progress-meter -4 http://www.gstatic.com/generate_204
}

net_connected_6() {
  curl -s --no-progress-meter -6 http://www.gstatic.com/generate_204
}

not_yet() { false; }

# https://stackoverflow.com/questions/1527049/how-can-i-join-elements-of-an-array-in-bash
# or: $(IFS=,; echo "${arr[*]}")
function str_join_by {
  local d=${1-} f=${2-}
  if shift 2; then
    printf %s "$f" "${@/#/$d}"
  fi
}

top_usage() {
  shopt -s lastpipe && set +m  # set +m for interactive shell  TODO: restore -m
  for k in "${!_commands[@]}"; do
    echo "$k"
  done | sort | mapfile -t
  cat <<EOS
usage:
  $PROG [-h | --help] [-q] [-v[v]] {$(str_join_by " | " "${MAPFILE[@]}")} [-h | --help]
EOS
}

# assert assertion: [[ expr ]] || unreachable
unreachable() {
  die 1 "unreachable: $(caller1): $(sed -n "${BASH_LINENO[0]}"p "${BASH_SOURCE[1]}")"
}

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

# ------------------------------------------------------------------------------
# bats setup

[[ $C_BASH_IN_BATS == "yes" ]] && bats_require_minimum_version 1.8.0

[[ $C_BASH_IN_BATS == "yes" ]] && [[ -z "$BATS_TEST_NUMBER" ]] && {
  [ -z "$BATS_SUITE_TEST_NUMBER" ] || echo -e "# \e[31m""BUG: BATS_SUITE_TEST_NUMBER defined: $BATS_SUITE_TEST_NUMBER\e[0m"
  [ -z "$BATS_TEST_NAME" ]         || echo -e "# \e[31m""BUG: BATS_TEST_NAME defined: $BATS_TEST_NAME\e[0m"
} >&3

setup() {
  [ -z "$BATS_TEST_NUMBER" ] && echo -e "# \e[31m""BUG: setup(): BATS_TEST_NUMBER not defined\e[0m"
  [[ "$BATS_SUITE_TEST_NUMBER" == "$BATS_TEST_NUMBER" ]] || echo -e "# \e[31m""BUG: BATS_SUITE_TEST_NUMBER: $BATS_SUITE_TEST_NUMBER BATS_TEST_NUMBER: $BATS_TEST_NUMBER\e[0m"
} >&3

# ------------------------------------------------------------------------------
# commands

declare -A _commands                           # "${_commands[@]}": unstable (order is random)
declare -a _command_list_stable_no_deprecated  # "${_command_list_stable_no_deprecated[@]}": stable
declare -a _command_list_stable_no_deprecated_no_alias
define_command() {
  local cmd=$1; shift
  _commands[$cmd]=$cmd
  _command_list_stable_no_deprecated+=("$cmd")
  _command_list_stable_no_deprecated_no_alias+=("$cmd")
  local alias
  for alias in "$@"; do
    if [[ $alias =~ ^"DEPRECATED:" ]]; then
      alias=${alias#"DEPRECATED:"}
      _commands[$alias]=$cmd
      continue
    fi
    _commands[$alias]=$cmd
    _command_list_stable_no_deprecated+=("$alias")
  done
}

# local name="" ... && local -a arr=() && arg_parse "$usage" "name..." "$@"
# TODO: arg_parse "$usage" "NAME [--] [CMD...]"
arg_parse() {
  local -r usage=$1 && shift
  local -r names=$1 && shift

  local -a names2
  # FUNCNAME:
  #   arg_parse 0template main
  #   arg_parse 0template       (bash -s 0template arg1 </home/wsh/sh/c.bash)
  if [[ ${FUNCNAME[-1]} == "main" ]]; then
    IFS=" " read -ra names2 <<<"$(arg_parse::_parse_names "${BASH_LINENO[1]} ${FUNCNAME[2]}" "$names")"
  else
    IFS=" " read -ra names2 <<<"$(arg_parse::_parse_names "${BASH_LINENO[0]} ${FUNCNAME[1]}" "$names")"
  fi
  local -r kind=${names2[0]}
  names2=("${names2[@]:1}")

  [[ $# != "0" ]] && [[ $1 == "-h" || $1 == "-help" || $1 == "--help" ]] && echo "$usage" && exit 0

  local name

  # required names
  while true; do
    name=${names2[0]}
    # TODO: assert_variable_local "$caller" "$name"
    names2=("${names2[@]:1}")
    [[ $name == "%%" ]] && break
    [[ $# == "0" ]] && err 0 "error: required argument: \"$name\" missing" && echo "$usage" >&2 && return 2
    # https://stackoverflow.com/questions/9938649/indirect-variable-assignment-in-bash
    printf -v "$name" '%s' "$1" && shift
  done

  case $kind in
  "NO_ARGV")
    # optional arguments
    while [[ ${#names2[@]} != 0 ]]; do
      name=${names2[0]}
      names2=("${names2[@]:1}")
      [[ $name == "%%" ]] && unreachable
      # TODO: assert_variable_local "$caller" "$name"
      (($# == 0)) && return 0
      printf -v "$name" '%s' "$1" && shift
    done
    [[ $# != 0 ]] && err 0 "error: excess argument(s): $*" && echo "$usage" >&2 && exit 2
    return 0
    ;;
  "HAS_ARGV")
    # variadic argument; must be the last
    [[ ${#names2[@]} == "1" ]] || unreachable
    name=${names2[0]}
    [[ $# == "0" ]] && err 0 "error: required argument: \"$name...\" missing" && echo "$usage" >&2 && return 2
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
      (($# == 0)) && return 0
      [[ $name == "%%" ]] && break
      printf -v "$name" '%s' "$1" && shift
    done
    # optional variadic argument; must be the last
    [[ ${#names2[@]} == "1" ]] || unreachable
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
    [[ $variadic == "" ]] || die 1 "$caller: variadic name: \"$variadic...\" must be the last (in: $*)"
    [[ $variadic_o == "" ]] || die 1 "$caller: variadic name: \"[$variadic_o...]\" must be the last (in: $*)"

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
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" ""          && [[ $stderr == "" ]] && [[ $output == "NO_ARGV  %% "          ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1"      && [[ $stderr == "" ]] && [[ $output == "NO_ARGV ARG1 %% "      ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1]"    && [[ $stderr == "" ]] && [[ $output == "NO_ARGV  %% ARG1"      ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARGV..."   && [[ $stderr == "" ]] && [[ $output == "HAS_ARGV  %% ARGV"     ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARGV...]" && [[ $stderr == "" ]] && [[ $output == "MAY_ARGV  %%  %% ARGV" ]] || bats_run_debug_fail >&3

  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 ARG2"        && [[ $stderr == "" ]] && [[ $output == "NO_ARGV ARG1 ARG2 %% "     ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 [ARG2]"      && [[ $stderr == "" ]] && [[ $output == "NO_ARGV ARG1 %% ARG2"      ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 ARGV..."     && [[ $stderr == "" ]] && [[ $output == "HAS_ARGV ARG1 %% ARGV"     ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 [ARGV...]"   && [[ $stderr == "" ]] && [[ $output == "MAY_ARGV ARG1 %%  %% ARGV" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] [ARG2]"    && [[ $stderr == "" ]] && [[ $output == "NO_ARGV  %% ARG1 ARG2"     ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] [ARGV...]" && [[ $stderr == "" ]] && [[ $output == "MAY_ARGV  %% ARG1 %% ARGV" ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] ARG2"      && [[ $output == "" ]] && [[ $stderr =~ ": cannot give non-optional name: \"ARG2\" after optional name(s): \"ARG1\" (in: [ARG1] ARG2)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] ARGV..."   && [[ $output == "" ]] && [[ $stderr =~ ": cannot give non-optional name: \"ARGV...\" after optional name(s): \"ARG1\" (in: [ARG1] ARGV...)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARGV... any"      && [[ $output == "" ]] && [[ $stderr =~ ": variadic name: \"ARGV...\" must be the last (in: ARGV... any)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARGV...] any"    && [[ $output == "" ]] && [[ $stderr =~ ": variadic name: \"[ARGV...]\" must be the last (in: [ARGV...] any)"$'\e[0m'$ ]] || bats_run_debug_fail >&3

  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 [ARG2] ARGV..."   && [[ $output == "" ]] && [[ $stderr =~ ": cannot give non-optional name: \"ARGV...\" after optional name(s): \"ARG2\" (in: ARG1 [ARG2] ARGV...)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -1 --separate-stderr arg_parse::_parse_names "$(caller0)" "[ARG1] [ARG2] ARGV..." && [[ $output == "" ]] && [[ $stderr =~ ": cannot give non-optional name: \"ARGV...\" after optional name(s): \"ARG1 ARG2\" (in: [ARG1] [ARG2] ARGV...)"$'\e[0m'$ ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr arg_parse::_parse_names "$(caller0)" "ARG1 [ARG2] [ARGV...]" && [[ $stderr == "" ]] && [[ $output == "MAY_ARGV ARG1 %% ARG2 %% ARGV" ]] || bats_run_debug_fail >&3

  local usage="usage: $PROG 0template [-h | --help] ???"

  # NO_ARGV
  set -- "arg1" "arg2" && local ARG1="" ARG2="" &&   arg_parse "$usage" "ARG1 ARG2"   "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]]                                                                                          || bats_run_debug_fail >&3
  set -- "arg1"        && run -2 --separate-stderr   arg_parse "$usage" "ARG1 ARG2"   "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG2" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set --               && run -2 --separate-stderr   arg_parse "$usage" "ARG1 ARG2"   "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG1" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set -- "arg1" "arg2" && local ARG1="" ARG2="" &&   arg_parse "$usage" "ARG1 [ARG2]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]]                                                                                          || bats_run_debug_fail >&3
  set -- "arg1"        && local ARG1="" ARG2="" &&   arg_parse "$usage" "ARG1 [ARG2]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]]                                                                                          || bats_run_debug_fail >&3
  set --               && run -2 --separate-stderr   arg_parse "$usage" "ARG1 [ARG2]" "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG1" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3

  # HAS_ARGV
  set -- "arg1" "arg2" "argv1" "argv2" && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]] && [[ ${#ARGV[@]} == "2" ]] && [[ ${ARGV[*]} == "argv1 argv2" ]]                              || bats_run_debug_fail >&3
  set -- "arg1" "arg2" "argv1"         && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]] && [[ ${#ARGV[@]} == "1" ]] && [[ ${ARGV[*]} == "argv1"       ]]                              || bats_run_debug_fail >&3
  set -- "arg1" "arg2"                 && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARGV..." missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set -- "arg1"                        && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG2" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]]    || bats_run_debug_fail >&3
  set -- "arg1" ""                     && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARGV..." missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set -- "arg1" "" ""                  && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]] && [[ ${#ARGV[@]} == "1" ]] && [[ ${ARGV[*]} == ""            ]]                              || bats_run_debug_fail >&3
  set -- "arg1" "" "" ""               && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]] && [[ ${#ARGV[@]} == "2" ]] && [[ ${ARGV[*]} == " "           ]]                              || bats_run_debug_fail >&3

  # MAY_ARGV
  set -- "arg1" "arg2" "argv1" "argv2" && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]] && [[ ${#ARGV[@]} == "2" ]] && [[ ${ARGV[*]} == "argv1 argv2" ]] || bats_run_debug_fail >&3
  set -- "arg1" "arg2" "argv1"         && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]] && [[ ${#ARGV[@]} == "1" ]] && [[ ${ARGV[*]} == "argv1"       ]] || bats_run_debug_fail >&3
  set -- "arg1" "arg2"                 && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]] && [[ ${#ARGV[@]} == "0" ]] && [[ ${ARGV[*]} == ""            ]] || bats_run_debug_fail >&3
  set -- "arg1"                        && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]] && [[ ${#ARGV[@]} == "0" ]] && [[ ${ARGV[*]} == ""            ]] || bats_run_debug_fail >&3
  set -- "arg1" ""                     && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]] && [[ ${#ARGV[@]} == "0" ]] && [[ ${ARGV[*]} == ""            ]] || bats_run_debug_fail >&3
  set -- "arg1" "" ""                  && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]] && [[ ${#ARGV[@]} == "1" ]] && [[ ${ARGV[*]} == ""            ]] || bats_run_debug_fail >&3
  set -- "arg1" "" "" ""               && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 [ARG2] [ARGV...]" "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]] && [[ ${#ARGV[@]} == "2" ]] && [[ ${ARGV[*]} == " "           ]] || bats_run_debug_fail >&3
}

# ------------------------------------------------------------------------------
# command - 0template

define_command 0template
cmd::0template() {
  local -r usage="usage: $PROG 0template [-h | --help] ARG"
  local ARG="" && arg_parse "$usage" "ARG" "$@"
  echo "ARG: $ARG"
  exit 0
}

# without arg_parse:
false && _() {
  # short usage
  local -r usage="usage: $PROG 0template [-h | --help]"
  [[ $# != 0 ]] && [[ $1 == "-h" || $1 == "-help" || $1 == "--help" ]] && echo "$usage" && exit 0
  [[ $# != 0 ]] && err 0 "error: excess argument(s): $*" && echo "$usage" >&2 && exit 2

  # long usage
  local -r usage=$(cat <<EOS
usage: $PROG 0template [-h | --help]
EOS
)
  # ...
}

# ------------------------------------------------------------------------------
# command - apt_changelog

define_command apt_changelog
cmd::apt_changelog() {
  local -r usage="usage: $PROG apt_changelog [-h | --help] PKG..."
  local -a PKG=() && arg_parse "$usage" "PKG..." "$@"
  for pkg in $(IFS=$'\n'; sort <<<"${PKG[*]}"); do [ -f "/usr/share/doc/$pkg/changelog.Debian.gz" ] || continue ; echo ---------- ; echo "/usr/share/doc/$pkg/changelog.Debian.gz" ; zcat "/usr/share/doc/$pkg/changelog.Debian.gz" | head ; done >/tmp/c.bash.d/apt_changelog.changelog.Debian.gz.txt || true
  for pkg in $(IFS=$'\n'; sort <<<"${PKG[*]}"); do [ -f "/usr/share/doc/$pkg/changelog.gz"        ] || continue ; echo ---------- ; echo "/usr/share/doc/$pkg/changelog.gz"        ; zcat "/usr/share/doc/$pkg/changelog.gz"        | head ; done >/tmp/c.bash.d/apt_changelog.changelog.gz.txt        || true
  for pkg in $(IFS=$'\n'; sort <<<"${PKG[*]}"); do [ -f "/usr/share/doc/$pkg/NEWS.Debian.gz"      ] || continue ; echo ---------- ; echo "/usr/share/doc/$pkg/NEWS.Debian.gz"      ; zcat "/usr/share/doc/$pkg/NEWS.Debian.gz"      | head ; done >/tmp/c.bash.d/apt_changelog.NEWS.Debian.gz.txt      || true
  for pkg in $(IFS=$'\n'; sort <<<"${PKG[*]}"); do [ -f "/usr/share/doc/$pkg/NEWS.gz"             ] || continue ; echo ---------- ; echo "/usr/share/doc/$pkg/NEWS.gz"             ; zcat "/usr/share/doc/$pkg/NEWS.gz"             | head ; done >/tmp/c.bash.d/apt_changelog.NEWS.gz.txt             || true
  echo code /tmp/c.bash.d/apt_changelog.*.txt
  exit 0
}

# ------------------------------------------------------------------------------
# command - cfl - lib

cfl_env_check() {
  local ok="true"
  [[ ${CONFLUENCE_URL+defined} == "defined" ]] || err 1 "environment variable CONFLUENCE_URL is not set" || ok="false"
  [[ ${CONFLUENCE_USER+defined} == "defined" ]] || err 1 "environment variable CONFLUENCE_USER is not set" || ok="false"
  [[ ${CONFLUENCE_PASS+defined} == "defined" ]] || err 1 "environment variable CONFLUENCE_PASS is not set" || ok="false"
  [[ $ok == "true" ]] || exit 1
  [[ $CONFLUENCE_URL != "${CONFLUENCE_URL%/}" ]] && {
    log_debug "remove trailing slash in CONFLUENCE_URL: $CONFLUENCE_URL -> ${CONFLUENCE_URL%/}"
    CONFLUENCE_URL=${CONFLUENCE_URL%/}
  }
  return 0
}

# ------------------------------------------------------------------------------
# command - cfl_content_attachment_get

# saves to ~/.cache/wataash/c.bash/cfl_content_attachment_get/*
define_command cfl_content_attachment_get
cmd::cfl_content_attachment_get() {
  local -r usage="usage: $PROG cfl_content_attachment_get [-h | --help] ID"
  local ID="" && arg_parse "$usage" "ID" "$@"
  [[ $ID =~ ^[0-9]+$ ]] || err 1 "ID must be a number: $ID"
  cfl_env_check
  mkdir -p ~/.cache/wataash/c.bash/cfl_content_attachment_get/
  cmd cfl_content_attachment_get_json "$ID" >~/.cache/wataash/c.bash/cfl_content_attachment_get/tmp.json
  local removed_caches; removed_caches=$(find ~/.cache/wataash/c.bash/cfl_content_attachment_get/ -mtime +3 -xtype f -delete -print); [[ -n $removed_caches ]] && log_info "removed old caches: $removed_caches"
  jq -c '.results[] | { id, title, extensions, _links }' ~/.cache/wataash/c.bash/cfl_content_attachment_get/tmp.json | while IFS= read -r line; do  # `IFS=`: prevent removing leading/preceding spaces
    local id title size link
    id=$(jq -er '.id' <<<"$line")
    title=$(jq -er '.title' <<<"$line")
    size=$(jq -er '.extensions.fileSize' <<<"$line")
    link=$(jq -er '._links.download' <<<"$line")
    [[ -f ~/.cache/wataash/c.bash/cfl_content_attachment_get/$id ]] && [[ $(stat -c %s ~/.cache/wataash/c.bash/cfl_content_attachment_get/"$id") == "$size" ]] && log_debug "skip: $id $title" && continue
    (set -o pipefail; ((LOG_LEVEL >= LOG_DEBUG)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/$link" -o ~/.cache/wataash/c.bash/cfl_content_attachment_get/"$id")
  done
  jq '.' ~/.cache/wataash/c.bash/cfl_content_attachment_get/tmp.json
}

# ------------------------------------------------------------------------------
# command - cfl_content_attachment_get_json

define_command cfl_content_attachment_get_json
cmd::cfl_content_attachment_get_json() {
  local -r usage="usage: $PROG cfl_content_attachment_get_json [-h | --help] ID"
  local ID="" && arg_parse "$usage" "ID" "$@"
  [[ $ID =~ ^[0-9]+$ ]] || err 1 "ID must be a number: $ID"
  cfl_env_check
  local start=0 limit=50
  # local limit=5  # limit test
  mkdir -p /tmp/c.bash.d/cfl_content_attachment_get_json/
  echo '{"results":[]}' >/tmp/c.bash.d/cfl_content_attachment_get_json/all.json
  for try in {1..10}; do
    # log_debug "try: $try"
    (set -o pipefail; ((LOG_LEVEL >= LOG_DEBUG)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content/$ID/child/attachment?start=$start&limit=$limit" | jq >"/tmp/c.bash.d/cfl_content_attachment_get_json/$start.json")
    # jq -c '.results = "[\(.results | length) elements]"' "/tmp/c.bash.d/cfl_content_attachment_get_json/$start.json"; echo
    jq -n '{"results":[inputs.results[]]}' /tmp/c.bash.d/cfl_content_attachment_get_json/all.json "/tmp/c.bash.d/cfl_content_attachment_get_json/$start.json" | sponge /tmp/c.bash.d/cfl_content_attachment_get_json/all.json
    local next
    next=$(jq -e '._links.next' "/tmp/c.bash.d/cfl_content_attachment_get_json/$start.json") || break
    start=$((start + limit))
    [[ $next == "\"/rest/api/content/$ID/child/attachment?limit=$limit&start=$start\"" ]] || unreachable
    ((try == 10)) && die 1 "too many entries?"
  done
  jq '.' /tmp/c.bash.d/cfl_content_attachment_get_json/all.json
}

# ------------------------------------------------------------------------------
# command - cfl_content_attachment_post

define_command cfl_content_attachment_post
cmd::cfl_content_attachment_post() {
  local -r usage="usage: $PROG cfl_content_attachment_post [-h | --help] PAGE_ID FILE"
  local PAGE_ID="" && arg_parse "$usage" "PAGE_ID FILE" "$@"
  [[ $PAGE_ID =~ ^[0-9]+$ ]] || err 1 "PAGE_ID must be a number: $PAGE_ID"
  cfl_env_check
  # -F "minorEdit=true" -F "comment=aaa aaa"
  (set -o pipefail; ((LOG_LEVEL >= LOG_INFO)) && set -x; cmd cfl_curl -X POST -H "X-Atlassian-Token: nocheck" -F "file=@$FILE" "$CONFLUENCE_URL/rest/api/content/$PAGE_ID/child/attachment") | jq >/tmp/c.bash.d/cfl_content_attachment_post.json
  jq '.' /tmp/c.bash.d/cfl_content_attachment_post.json
}

# ------------------------------------------------------------------------------
# command - cfl_content_delete

define_command cfl_content_delete
cmd::cfl_content_delete() {
  local -r usage="usage: $PROG cfl_content_delete [-h | --help] ID"
  local ID="" && arg_parse "$usage" "ID" "$@"
  cfl_env_check
  ( ((LOG_LEVEL >= LOG_INFO)) && set -x; cmd cfl_curl -X DELETE "$CONFLUENCE_URL/rest/api/content/$ID")
}

# ------------------------------------------------------------------------------
# command - cfl_content_format_with_actual_update_abort

define_command cfl_content_format_with_actual_update_abort
cmd::cfl_content_format_with_actual_update_abort() {
  local -r usage="usage: $PROG cfl_content_format_with_actual_update_abort [-h | --help] [FILE]"
  local FILE="" && arg_parse "$usage" "[FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  cfl_env_check
  [[ ${DANGEROUS_PLEASE_UNDERSTAND_WHAT_THIS_DO_CONFLUENCE_UPDATE_CONTENT_ID+defined} == "defined" ]] || die 1 "environment variable DANGEROUS_PLEASE_UNDERSTAND_WHAT_THIS_DO_CONFLUENCE_UPDATE_CONTENT_ID is not set" || ok="false"
  local ID=$DANGEROUS_PLEASE_UNDERSTAND_WHAT_THIS_DO_CONFLUENCE_UPDATE_CONTENT_ID

  (set -o pipefail; ((LOG_LEVEL >= LOG_DEBUG)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content/$ID" | jq -e >/tmp/c.bash.d/cfl_content_format_with_actual_update_abort.json)
  local original_title
  original_title=$(jq -er ".title" /tmp/c.bash.d/cfl_content_format_with_actual_update_abort.json)
  # cmd cfl_content_update "$ID" "$original_title" "$FILE" | jq -e '.body.storage.value'  # not formatted yet
  cmd cfl_content_update "$ID" "$original_title" "$FILE" >/dev/null
  cmd cfl_content_get "$ID"  # not formatted! abort
}

# ------------------------------------------------------------------------------
# command - cfl_content_get

# echo:
# title
# storage
define_command cfl_content_get
cmd::cfl_content_get() {
  local -r usage="usage: $PROG cfl_content_get [-h | --help] ID"
  local ID="" && arg_parse "$usage" "ID" "$@"
  [[ $ID =~ ^[0-9]+$ ]] || err 1 "ID must be a number: $ID"
  cfl_env_check
  (set -o pipefail; ((LOG_LEVEL >= LOG_DEBUG)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content/$ID?expand=body.storage" | jq -e >/tmp/c.bash.d/cfl_content_get.json)
  jq -er </tmp/c.bash.d/cfl_content_get.json ".title"
  jq -er </tmp/c.bash.d/cfl_content_get.json ".body.storage.value"
}

# ------------------------------------------------------------------------------
# command - cfl_content_get_id

define_command cfl_content_get_id
cmd::cfl_content_get_id() {
  local -r usage="usage: $PROG cfl_content_get_id [-h | --help] SPACE_KEY TITLE"
  local SPACE_KEY="" TITLE="" && arg_parse "$usage" "SPACE_KEY TITLE" "$@"
  cfl_env_check
  (set -o pipefail; ( ((LOG_LEVEL >= LOG_INFO)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content?spaceKey=$SPACE_KEY&title=$TITLE") | jq -er ".results[0].id")
}
# ------------------------------------------------------------------------------
# command - cfl_content_update
# TODO: rename: cfl_content_update

# stdout: JSON from PUT "$CONFLUENCE_URL/rest/api/content/$ID"
define_command cfl_content_update
cmd::cfl_content_update() {
  local -r usage="usage: $PROG cfl_content_update [-h | --help] ID TITLE [FILE]"
  local ID="" TITLE="" FILE="" && arg_parse "$usage" "ID TITLE [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  [[ $ID =~ ^[0-9]+$ ]] || err 1 "ID must be a number: $ID"
  cfl_env_check
  ( ((LOG_LEVEL >= LOG_DEBUG)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content/$ID") | jq -e >/tmp/c.bash.d/cfl_content_update.1.json
  local -i ver
  ver=$(jq -er ".version.number" /tmp/c.bash.d/cfl_content_update.1.json)
  ((ver++))
  jo -p -d. -- version.number="$ver" title="$TITLE" type=page body.storage.value=@"$FILE" body.storage.representation=storage >/tmp/c.bash.d/cfl_content_update.put.json
  ( ((LOG_LEVEL >= LOG_DEBUG)) && set -x; cmd cfl_curl -X PUT -H "Content-Type: application/json" -d @/tmp/c.bash.d/cfl_content_update.put.json "$CONFLUENCE_URL/rest/api/content/$ID") | jq -e >/tmp/c.bash.d/cfl_content_update.2.json
  jq '.' /tmp/c.bash.d/cfl_content_update.2.json
}

# ------------------------------------------------------------------------------
# command - cfl_curl

define_command cfl_curl
cmd::cfl_curl() {
  cfl_env_check
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  (
    ((LOG_LEVEL >= LOG_DEBUG)) && set -x
    curl --fail-with-body -Ss -K<(BASH_XTRACEFD=$fd_devnull builtin echo "-u $CONFLUENCE_USER:$CONFLUENCE_PASS") {fd_devnull}>/dev/null "$@" >/tmp/c.bash.d/cfl_curl.out
  ) {fd_devnull}>/dev/null || die 1 "cfl_curl failed; body: $(cat /tmp/c.bash.d/cfl_curl.out)"
  jq -c '.' /tmp/c.bash.d/cfl_curl.out
}
false && pre_main() {
  cmd::cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content/1"
}

# ------------------------------------------------------------------------------
# command - cmd_intercept

: <<'DOC'
echo -e '#!/bin/sh\n/home/wsh/sh/c.bash -vv cmd_intercept bash "$@"' >~/bin/bash_
chmod +x ~/bin/bash_

echo -e '#!/bin/sh\n/home/wsh/sh/c.bash -vv cmd_intercept /home/wsh/opt/gdb/bin/gdb "$@"' >/home/wsh/bin/gdb_
chmod +x /home/wsh/bin/gdb_

tail -F /tmp/c.bash.d/cmd_intercept.log
bash_
DOC

define_command cmd_intercept
cmd::cmd_intercept() {
  local -r usage="usage: $PROG cmd_intercept [-h | --help] CMD..."
  local -a CMD=() && arg_parse "$usage" "CMD..." "$@"

  # cleanup background processses (&)
  # https://stackoverflow.com/questions/360201/how-do-i-kill-background-processes-jobs-when-my-shell-script-exits
  # trap "echo 'cmd_intercept: EXIT...' >&2 && pstree -p \$\$ >&2 && jobs -p | xargs -r --verbose kill >&2" EXIT  # doesn't kill subshell's children
  # trap "echo 'cmd_intercept: EXIT... ' >&2 && pstree -p \$\$ >&2 && kill 0 >&2" EXIT  # fish: Job 2, 'c.bash -vv cmd_intercept bash' terminated by signal SIGTERM (Polite quit request)
  trap "echo 'cmd_intercept: EXIT... ' >&2 && pstree -p \$\$ | grep -P --color '(?<=(sed|ail)\()\d+(?=\))' >&2 && pstree -p \$\$ | grep -Po '(?<=(sed|ail)\()\d+(?=\))' | xargs -r --verbose kill >&2" EXIT

  # TODO: get each pty for stdin/stdout/stderr if pty

  echo -n >/tmp/c.bash.d/cmd_intercept.log.in
  echo -n >/tmp/c.bash.d/cmd_intercept.log.out && tail -F /tmp/c.bash.d/cmd_intercept.log.out &
  echo -n >/tmp/c.bash.d/cmd_intercept.log.err && tail -F /tmp/c.bash.d/cmd_intercept.log.err >&2 &

  {
    log_info "intercept: ${CMD[*]}" 2>&1
    tail -F /tmp/c.bash.d/cmd_intercept.log.in  | sed -Eu -e 's/^/\x1b[37m''in: /' -e 's/$/\x1b[0m/' &
    tail -F /tmp/c.bash.d/cmd_intercept.log.out &
    tail -F /tmp/c.bash.d/cmd_intercept.log.err | sed -Eu -e 's/^/\x1b[31m''err: /' -e 's/$/\x1b[0m/' &
  } >/tmp/c.bash.d/cmd_intercept.log

  tee -a /tmp/c.bash.d/cmd_intercept.log.in | "${CMD[@]}" >/tmp/c.bash.d/cmd_intercept.log.out 2>/tmp/c.bash.d/cmd_intercept.log.err
  log_info "EOS"
}

# ------------------------------------------------------------------------------
# command - discharging_checker

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
cmd::discharging_checker() {
  local -r usage="usage: $PROG discharging_checker [-h | --help]"
  arg_parse "$usage" "" "$@"
  local -ir BASE_INTERVAL=240  # 4min, 8min, 16min, 32min, 64min, ...

  # without this: notify-send: Cannot autolaunch D-Bus without X11 $DISPLAY
  # @ref:no-X11-DBUS_SESSION_BUS_ADDRESS
  DBUS_SESSION_BUS_ADDRESS=$(strings /proc/"$(pgrep -u wsh gnome-session | head -1)"/environ | grep -P -o '(?<=DBUS_SESSION_BUS_ADDRESS=).+$')  # unix:path=/run/user/1000/bus
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
    [[ "$state_curr" != "pending-charge" ]] && [[ "$(echo "$energy_curr < $energy_prev" | bc)" == "1" ]] && discharging="true"  # energy slowly decreases in "pending-charge" state; notify only in "charging" state
    [[ "$state_curr" == "discharging" ]]                                                                 && discharging="true"
    if [[ "$discharging" == "true" ]]; then
      percentage_=$(upower -i /org/freedesktop/UPower/devices/battery_BAT0 | grep -P -o '(?<=percentage:)\s+\S+' | tr -d ' ')
      echo "discharging: $energy_prev Wh -> $energy_curr Wh, $state_prev -> $state_curr ($percentage_)"
      bash /home/wsh/sh/debug_notify.bash ← removed "discharging: $energy_prev Wh -> $energy_curr Wh ($percentage_), $state_prev -> $state_curr"
      interval=$((interval * 2))
      echo "recheck in $interval seconds..."
    else
      # charging
      ((interval > BASE_INTERVAL)) && echo 'charging'
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
# command - file_sync_watch

define_command file_sync_watch
cmd::file_sync_watch() {
  local -r usage="usage: $PROG file_sync_watch [-h | --help] HOST FILE..."
  local HOST="" && local -a FILE=() && arg_parse "$usage" "HOST FILE..." "$@"
  local -a files_abs=()
  for f in "${FILE[@]}"; do
    files_abs+=("$(realpath "$f")")
  done
  (
    set -x
    inotifywait -m -r -e modify -e move -e create -e delete --format='%w%f' "${files_abs[@]}" | cmd xargs_delay -I% --verbose rsync -va % "$HOST":%
  )
  unreachable
}

# ------------------------------------------------------------------------------
# command - file_timestamp

define_command file_timestamp
cmd::file_timestamp() {
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
# command - grep_multiline (gm)

# c.bash gm -P -m1 "^define_command grep_multiline" "cat" < /home/wsh/sh/c.bash
# c.bash gm -P -m1 "^define_command grep_multiline" "cat" < /home/wsh/sh/c.bash | sed '1d;$d'

define_command grep_multiline gm
cmd::grep_multiline() {
  local -r usage="usage: ... | $PROG grep_multiline (gm) [-h | --help] -P -m1 PATTERN_BEGIN PATTERN_END [| sed '1d;\$d']"
  local P="" m="" PATTERN_BEGIN="" PATTERN_END="" && arg_parse "$usage" "P m PATTERN_BEGIN PATTERN_END" "$@"
  [[ $P != "-P" ]] && err 0 "error: \"$P\" != \"-P\" (in $*)" && echo "$usage" >&2 && exit 2
  [[ $m != "-m1" ]] && err 0 "error: \"$m\" != \"-m1\" (in $*)" && echo "$usage" >&2 && exit 2
  local txt
  txt=$(cat)
  # set -x
  grep -P -m1 -q "$PATTERN_BEGIN" <<< "$txt"
  local -i lineno_begin
  lineno_begin="$(grep -P -m1 -n "$PATTERN_BEGIN" <<< "$txt" | cut -d":" -f1)"
  grep -P -m1 -q "$PATTERN_END" <<< "$txt"
  # lineno_end="$(grep -P -m1 -n "$PATTERN_END" <<< "$txt" | cut -d":" -f1)"
  # set +x
  local -i lineno_end
  grep -P -n "$PATTERN_END" <<< "$txt" | cut -d":" -f1 | while IFS= read -r lineno_end; do  # `IFS=`: prevent removing leading/preceding spaces
    log_debug "lineno_end: $lineno_end"
    if ((lineno_end > lineno_begin)); then
      sed -n "${lineno_begin},${lineno_end}p" <<< "$txt"
      exit 0
    fi
  done && exit 0
  exit 1
}

# ------------------------------------------------------------------------------
# command - grep_multiline_greedy (gm_greedy)

# c.bash gm_greedy -P "^define_command grep_multiline_greedy" "cat" < /home/wsh/sh/c.bash

define_command grep_multiline_greedy gm_greedy
cmd::grep_multiline_greedy() {
  local -r usage="usage: ... | $PROG grep_multiline_greedy (gm_greedy) [-h | --help] -P PATTERN_BEGIN PATTERN_END [| sed '1d;\$d']"
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
  if ((lineno_end <= lineno_begin)); then
    exit 1
  fi
  sed -n "${lineno_begin},${lineno_end}p" <<< "$txt"
  exit 0
}

# ------------------------------------------------------------------------------
# command - journalctl

: <<'DOC'
# Ubuntu 20.04:
echo -e '#!/bin/sh\n/home/wsh/sh/c.bash journalctl "$@"' > ~/bin/journalctl
chmod +x ~/bin/journalctl
journalctl -xb -f
DOC

define_command journalctl
cmd::journalctl() {
  # local -r usage="usage: $PROG journalctl [-h | --help]"
  # arg_parse "$usage" "" "$@"
  /usr/bin/journalctl "$@" | sed -E -e "s/^(--.+)/\1\x1b[0m/" -e "s/^--/\x1b[32m  /"
}

# ------------------------------------------------------------------------------
# command - kill_clangd

define_command kill_clangd
cmd::kill_clangd() {
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

  (
    IFS=$'\n'
    local line
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
  )

  (
    IFS=$'\n'
    local line
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
      [[ ${#alive_pids[@]} == "0" ]] && return 0
      log_info "alive: ${alive_pids[*]}"
      sleep 1
    done
  )

  (
    IFS=$'\n'
    local line
    for line in $processes; do
      local fields
      IFS=" " read -ra fields <<<"$line"
      pid=${fields[0]}
      echo "kill -9 $pid"
      kill -9 "$pid"
    done
  )
}

# ------------------------------------------------------------------------------
# command - kill_code_md_ext

define_command kill_code_md_ext
cmd::kill_code_md_ext() {
  local -r usage="usage: $PROG kill_code_md_ext [-h | --help]"
  arg_parse "$usage" "" "$@"
  # ps じゃなくて1秒間隔のCPU使用率が見れるプログラムに置き換えたい @ref:linux-ps-pcpu
  : <<'EOS'
ps -e -H $(: --headers) u -ww | grep -E '[U]SER|[m]arkdown-language-features'
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
wsh        91143 90.5  0.1 1177280496 81564 ?    Rl   13:53   7:26         /usr/share/code/code --ms-enable-electron-run-as-node /usr/share/code/resources/app/extensions/markdown-language-features/server/dist/node/workerMain --node-ipc --clientProcessId=79492
EOS
  local -i rc=1
  # shellcheck disable=SC2009  # Consider using pgrep instead of grepping ps output
  ps -e -H $(: --headers) u -ww | grep -E '[m]arkdown-language-features' | while IFS= read -r line; do  # `IFS=`: prevent removing leading/preceding spaces
    log_debug $'\n'"$line"
    local pcpu=$(awk '{print $3}' <<<"$line")
    echo "$pcpu >= 10.0" | bc | grep -q '1' || continue
    rc=0
    echo "$line"
    local pid=$(awk '{print $2}' <<<"$line")
    (set -x; kill "$pid")
  done
  exit "$rc"
}

# ------------------------------------------------------------------------------
# command - linux_dmesg_time0

define_command linux_dmesg_time0
cmd::linux_dmesg_time0() {
  local -r usage="usage: dmesg | $PROG linux_dmesg_time0 [-h | --help]"
  arg_parse "$usage" "" "$@"
  sed -E s'/\[[0-9 ]{4}[0-9]\.[0-9]{6}\]/[    0.000000]/'
}

# ------------------------------------------------------------------------------
# command - linux_kern_config

define_command linux_kern_config
cmd::linux_kern_config() {
  local -r usage="usage: $PROG linux_kern_config [-h | --help] [TARGET...]"
  local -a TARGET=() && arg_parse "$usage" "[TARGET...]" "$@"
  [[ ${#TARGET[@]} == "0" ]] && TARGET=(vmlinux modules compile_commands.json bindeb-pkg)
  KBUILD_OUTPUT=$(cmd::linux_kern_config::check_or_get_KBUILD_OUTPUT)
  export KBUILD_OUTPUT
  [[ $KBUILD_OUTPUT == "/home/wsh/qc/linux/focal-build-d" ]] && log_info "cd /home/wsh/qc/linux/focal-d" && cd /home/wsh/qc/linux/focal-d
  [[ $KBUILD_OUTPUT == "/home/wsh/qc/linux/focal-build-r" ]] && log_info "cd /home/wsh/qc/linux/focal-r" && cd /home/wsh/qc/linux/focal-r

  # make defconfig   # based on arch/x86/configs/x86_64_defconfig; creates $KBUILD_OUTPUT/.config
  cp -v /boot/config-5.19.0-43-generic $KBUILD_OUTPUT/.config
  cp -v /boot/config-5.19.0-43-generic $KBUILD_OUTPUT/.config-5.19.0-43-generic
  (set -x; make olddefconfig)  # V=1
  cp -v $KBUILD_OUTPUT/.config $KBUILD_OUTPUT/.config.olddefconfig

  log_info "code --diff $KBUILD_OUTPUT/.config-5.19.0-43-generic             $KBUILD_OUTPUT/.config.olddefconfig        : 5.19.0-43-generic -> 5.19.17"
  fish -c  "code --diff $KBUILD_OUTPUT/.config-5.19.0-43-generic             $KBUILD_OUTPUT/.config.olddefconfig"

  log_info "code --diff $KBUILD_OUTPUT-old/.config.olddefconfig              $KBUILD_OUTPUT/.config.olddefconfig        : (optional) check rebase-updates"
  fish -c  "code --diff $KBUILD_OUTPUT-old/.config.olddefconfig              $KBUILD_OUTPUT/.config.olddefconfig"

  log_info "fish ~/doc/t/linux_kernel_config.md.fish : should be no diff"
  fish ~/doc/t/linux_kernel_config.md.fish

  log_info "code --diff $KBUILD_OUTPUT/.config.olddefconfig                  $KBUILD_OUTPUT/.config                     : カスタムのcheck"
  fish -c  "code --diff $KBUILD_OUTPUT/.config.olddefconfig                  $KBUILD_OUTPUT/.config"

  cp -v $KBUILD_OUTPUT/.config $KBUILD_OUTPUT/.config.olddefconfig-hacked
  log_info "code --diff $KBUILD_OUTPUT-old/.config.olddefconfig-hacked       $KBUILD_OUTPUT/.config.olddefconfig-hacked : check rebase-updates"
  fish -c  "code --diff $KBUILD_OUTPUT-old/.config.olddefconfig-hacked       $KBUILD_OUTPUT/.config.olddefconfig-hacked"

  [[ $KBUILD_OUTPUT == "/home/wsh/qc/linux/focal-build-r" ]] && {
    log_info "code --diff ~/qc/linux/focal-build-d/.config                   $KBUILD_OUTPUT/.config.olddefconfig-hacked : debug vs release; BUG | GENERIC_BUG | GENERIC_BUG_RELATIVE_POINTERS | ACPI_PRMT | JUMP_LABEL | DEBUG_BUGVERBOSE"
    fish -c  "code --diff ~/qc/linux/focal-build-d/.config                   $KBUILD_OUTPUT/.config.olddefconfig-hacked"
  }
}

cmd::linux_kern_config::check_or_get_KBUILD_OUTPUT() {
  [[ ${KBUILD_OUTPUT+defined} == "defined" ]] || case $PWD in
    "/home/wsh/qc/linux/focal-d"*)       export KBUILD_OUTPUT=/home/wsh/qc/linux/focal-build-d;;
    "/home/wsh/qc/linux/focal-build-d"*) export KBUILD_OUTPUT=/home/wsh/qc/linux/focal-build-d;;
    "/home/wsh/qc/linux/focal-r"*)       export KBUILD_OUTPUT=/home/wsh/qc/linux/focal-build-r;;
    "/home/wsh/qc/linux/focal-build-r"*) export KBUILD_OUTPUT=/home/wsh/qc/linux/focal-build-r;;
    *) die 1 "environment variable KBUILD_OUTPUT is not set / unknown PWD";;
  esac
  [[ ${KBUILD_OUTPUT+defined} == "defined" ]] || die 1 "environment variable KBUILD_OUTPUT is not set"
  case $KBUILD_OUTPUT in
    "/home/wsh/qc/linux/focal-build-d") log_info "debug";;
    "/home/wsh/qc/linux/focal-build-r") log_warning "release";;
    *) die 1 "unknown KBUILD_OUTPUT: $KBUILD_OUTPUT";;
  esac
  echo "$KBUILD_OUTPUT"
}

# ------------------------------------------------------------------------------
# command - linux_kern_initramfs

: <<'DOC'
https://hernandigiorgi.com/how-to-create-an-initramfs-after-you-compile-a-linux-kernel/
https://www.busybox.net/downloads/binaries/
DOC

define_command linux_kern_initramfs
cmd::linux_kern_initramfs() {
  local -r usage="usage: $PROG linux_kern_initramfs [-h | --help]"
  arg_parse "$usage" "" "$@"
  KBUILD_OUTPUT=$(cmd::linux_kern_config::check_or_get_KBUILD_OUTPUT)
  export KBUILD_OUTPUT

  mkdir -pv "$KBUILD_OUTPUT/z_initramfs/initramfs_root/bin/"
  mkdir -pv "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/"
  mkdir -pv "$KBUILD_OUTPUT/z_initramfs/initramfs_root/proc/"
  mkdir -pv "$KBUILD_OUTPUT/z_initramfs/initramfs_root/sys/"
  mkdir -pv "$KBUILD_OUTPUT/z_initramfs/initramfs_root/tmp/"

  # https://www.busybox.net/downloads/binaries/
  [[ -f $KBUILD_OUTPUT/z_initramfs/initramfs_root/bin/busybox ]] || (set -x; curl "https://www.busybox.net/downloads/binaries/1.35.0-x86_64-linux-musl/busybox" -o "$KBUILD_OUTPUT/z_initramfs/initramfs_root/bin/busybox")
  chmod +x "$KBUILD_OUTPUT/z_initramfs/initramfs_root/bin/busybox"

  cat <<'EOS' >"$KBUILD_OUTPUT/z_initramfs/initramfs_root/init"
#!/bin/busybox sh
/bin/busybox --install /bin
mount -t  devtmpfs  devtmpfs  /dev
mount -t  proc      proc      /proc
mount -t  sysfs     sysfs     /sys
mount -t  debugfs   none      /sys/kernel/debug
mount -t  tmpfs     tmpfs     /tmp
# modprobe e1000
setsid cttyhack sh  # ? busybox(1)
exec /bin/sh
EOS
  chmod +x "$KBUILD_OUTPUT/z_initramfs/initramfs_root/init"

  if [[ $KBUILD_OUTPUT == "/home/wsh/qc/linux/focal-build-d" ]]; then
    (set -x; rsync -av --delete --max-delete=10 --prune-empty-dirs --exclude="/debian/" --exclude="/z_initramfs/" --include="*/" --include="*.ko" --exclude="*" "$KBUILD_OUTPUT/" "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/")
    du -h -d1     "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/"  # 2.8G
    # --strip-debug: INSTALL_MOD_STRIP=1 make -n V=1 modules_install の真似; --strip-debug でないとダメっぽい @ref:linux-kernel-module-strip-debug
    (set -x; find "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/" -name "*.ko" -exec strip --strip-debug "{}" ";")
    du -h -d1     "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/"  # 378M; --strip だともっと小さい
    false && { # debug
      # rm -frv $KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/
      mkdir -p $KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/lib/
      cp "$KBUILD_OUTPUT/lib/crc4.ko"                    "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/lib/"
      cp /home/wsh/qc/linux/z_module_tes_d/module_tes.ko "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/"  # @ref:linux-kernel-module-tes
      strip --strip-debug "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/lib/crc4.ko"    # 61Ki -> 5.5Ki
      strip --strip-debug "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/module_tes.ko"  # 60Ki -> 4.6Ki
    }
  fi
  if [[ $KBUILD_OUTPUT == "/home/wsh/qc/linux/focal-build-r" ]]; then
    # --delete?
    rsync -va -h --progress "$KBUILD_OUTPUT/debian/linux-image/lib/modules/5.19.17+/" "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/"
    false && du -h -d2 "$KBUILD_OUTPUT/debian/linux-image/lib/modules/5.19.17+/"  # 497M
  fi

  # ↑ の代わりにmodules最小限だけ入れる (aborted)
  false && {
    mkdir -pv "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/drivers/net/ethernet/intel/e1000/"
    mkdir -pv "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/drivers/gpu/drm/bochs/"
    cp -v "$KBUILD_OUTPUT/drivers/net/ethernet/intel/e1000/e1000.ko" "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/drivers/net/ethernet/intel/e1000/"
    cp -v "$KBUILD_OUTPUT/drivers/gpu/drm/bochs/bochs-drm.ko"        "$KBUILD_OUTPUT/z_initramfs/initramfs_root/lib/modules/5.19.17+/kernel/drivers/gpu/drm/bochs/"
    # あと modules.dep.bin 入れて、依存 .ko 入れないとか
    # $KBUILD_OUTPUT/debian/linux-image/lib/modules/5.19.17+/modules.dep
    #   これは scripts/depmod.sh で作れるのかな？
    # 他にもなんか必要だったりして
    # やっぱmkinitramfsデバッグして使えるようにするか…
  }

  cd "$KBUILD_OUTPUT/z_initramfs/initramfs_root/"
  (set -x; find . | cpio -o $(: -v) --format=newc | gzip >../initramfs)

  log_info "lsinitramfs -l $KBUILD_OUTPUT/z_initramfs/initramfs | head/tail"
  lsinitramfs -l $KBUILD_OUTPUT/z_initramfs/initramfs | head
  echo ...
  lsinitramfs -l $KBUILD_OUTPUT/z_initramfs/initramfs | tail
}

# ------------------------------------------------------------------------------
# command - linux_kern_make

define_command linux_kern_make
cmd::linux_kern_make() {
  local -r usage="usage: $PROG linux_kern_make [-h | --help] [TARGET...]"
  local -a TARGET=() && arg_parse "$usage" "[TARGET...]" "$@"
  [[ ${#TARGET[@]} == "0" ]] && TARGET=(vmlinux modules compile_commands.json bindeb-pkg)
  KBUILD_OUTPUT=$(cmd::linux_kern_config::check_or_get_KBUILD_OUTPUT)
  export KBUILD_OUTPUT
  # TODO: on fail: log: debug!: cp -v $KBUILD_OUTPUT/compile_commands.json.bear /home/wsh/qc/linux/focal-d/compile_commands.json
  set -o pipefail
  set -x
  for target in "${TARGET[@]}"; do
    case $target in
      vmlinux)               command time make vmlinux               -j16 |& tee -a "$KBUILD_OUTPUT/make_vmlinux.log"               || make vmlinux               V=1 -j8 || make vmlinux               V=1 -j4 || make vmlinux               V=1 -j2 || bear --output "$KBUILD_OUTPUT/compile_commands.json.bear" -- make vmlinux               V=1 -j1 ;;  # 2m26s 3m30s
      modules)               command time make modules               -j16 |& tee -a "$KBUILD_OUTPUT/make_modules.log"               || make modules               V=1 -j8 || make modules               V=1 -j4 || make modules               V=1 -j2 || bear --output "$KBUILD_OUTPUT/compile_commands.json.bear" -- make modules               V=1 -j1 ;;  # 12m20s 15m08s
      compile_commands.json) command time make compile_commands.json -j16 |& tee -a "$KBUILD_OUTPUT/make_compile_commands.json.log" || make compile_commands.json V=1 -j8 || make compile_commands.json V=1 -j4 || make compile_commands.json V=1 -j2 || bear --output "$KBUILD_OUTPUT/compile_commands.json.bear" -- make compile_commands.json V=1 -j1 ;;  # 10s 10s
      bindeb-pkg)            command time make bindeb-pkg            -j16 |& tee -a "$KBUILD_OUTPUT/make_bindeb-pkg.log"            || make bindeb-pkg            V=1 -j8 || make bindeb-pkg            V=1 -j4 || make bindeb-pkg            V=1 -j2 || bear --output "$KBUILD_OUTPUT/compile_commands.json.bear" -- make bindeb-pkg            V=1 -j1 ;;  # 5m27s 4m11s
      *) die 1 "unknown target: $target";;
    esac
  done
}

# ------------------------------------------------------------------------------
# command - linux_kern_make_summary

define_command linux_kern_make_summary
cmd::linux_kern_make_summary() {
  local -r usage="usage: $PROG linux_kern_make_summary [-h | --help]"
  arg_parse "$usage" "" "$@"
  KBUILD_OUTPUT=$(cmd::linux_kern_config::check_or_get_KBUILD_OUTPUT)
  export KBUILD_OUTPUT

  # shellcheck disable=SC2045  # Iterating over ls output is fragile. Use globs
  for f in $(ls -tr "$KBUILD_OUTPUT/make"*".log"); do
    printf "%-45s" "$(basename $f)"; tail -n2 "$f" | python3 ~/qpy/tespy/tespy/txt/time_fmt.py | ruby -e 'puts(ARGF.read.sub(/(?<!\n)\z/, "?:??\n"))'
  done
  echo

  local last_log
  # shellcheck disable=SC2012  # Use find instead of ls to better handle non-alphanumeric filenames
  last_log=$(ls -t "$KBUILD_OUTPUT/make"*".log" | head -1)
  printf "\e[32m""last_log: %s\e[0m\n\n%s\n\n\e[32m""last_log: %s\e[0m" "$last_log" "$(tail -40 <"$last_log")" "$last_log"
}

# ------------------------------------------------------------------------------
# command - md_code_b64

# @depracated use c.js txtMarkdownCodeB64
define_command md_code_b64
cmd::md_code_b64() {
  local -r usage="usage: $PROG md_code_b64 [-h | --help]"
  arg_parse "$usage" "" "$@"
  c.js txtMarkdownCodeB64
}

test_md_code_b64() { #@test
  # `echo | run` seems not to work!
  echo -n $''                                       >/tmp/c.bash.d/test.in && echo -n $''                                                                               >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64 </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'a'                                      >/tmp/c.bash.d/test.in && echo -n $'a'                                                                              >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64 </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'a\n'                                    >/tmp/c.bash.d/test.in && echo -n $'a\n'                                                                            >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64 </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'a\n\n'                                  >/tmp/c.bash.d/test.in && echo -n $'a\n\n'                                                                          >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64 </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'```sh\ncode\n```'                       >/tmp/c.bash.d/test.in && echo -n $'@__code_block__:YGBgc2gKY29kZQpgYGA='                                           >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64 </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'```sh\ncode\n```\n'                     >/tmp/c.bash.d/test.in && echo -n $'@__code_block__:YGBgc2gKY29kZQpgYGA=\n'                                         >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64 </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'```sh\ncode\n```\n\n```sh\ncode\n```'   >/tmp/c.bash.d/test.in && echo -n $'@__code_block__:YGBgc2gKY29kZQpgYGA=\n\n@__code_block__:YGBgc2gKY29kZQpgYGA='   >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64 </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'```sh\ncode\n```\n\n```sh\ncode\n```\n' >/tmp/c.bash.d/test.in && echo -n $'@__code_block__:YGBgc2gKY29kZQpgYGA=\n\n@__code_block__:YGBgc2gKY29kZQpgYGA=\n' >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64 </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
}

# ------------------------------------------------------------------------------
# command - md_code_b64d

# @depracated use c.js txtMarkdownCodeB64d
define_command md_code_b64d
cmd::md_code_b64d() {
  local -r usage="usage: $PROG md_code_b64d [-h | --help]"
  arg_parse "$usage" "" "$@"
  c.js txtMarkdownCodeB64d
}

test_md_code_b64d() { #@test
  echo -n $''                                                                               >/tmp/c.bash.d/test.in && echo -n $''                                       >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64d </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'a'                                                                              >/tmp/c.bash.d/test.in && echo -n $'a'                                      >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64d </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'a\n'                                                                            >/tmp/c.bash.d/test.in && echo -n $'a\n'                                    >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64d </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'a\n\n'                                                                          >/tmp/c.bash.d/test.in && echo -n $'a\n\n'                                  >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64d </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'@__code_block__:YGBgc2gKY29kZQpgYGA='                                           >/tmp/c.bash.d/test.in && echo -n $'```sh\ncode\n```'                       >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64d </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'@__code_block__:YGBgc2gKY29kZQpgYGA=\n'                                         >/tmp/c.bash.d/test.in && echo -n $'```sh\ncode\n```\n'                     >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64d </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'@__code_block__:YGBgc2gKY29kZQpgYGA=\n\n@__code_block__:YGBgc2gKY29kZQpgYGA='   >/tmp/c.bash.d/test.in && echo -n $'```sh\ncode\n```\n\n```sh\ncode\n```'   >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64d </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'@__code_block__:YGBgc2gKY29kZQpgYGA=\n\n@__code_block__:YGBgc2gKY29kZQpgYGA=\n' >/tmp/c.bash.d/test.in && echo -n $'```sh\ncode\n```\n\n```sh\ncode\n```\n' >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_code_b64d </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
}

# ------------------------------------------------------------------------------
# command - md_sec

define_command md_sec
cmd::md_sec() {
  local -r usage="usage: $PROG md_sec [-h | --help] SECTION"
  local SECTION="" && arg_parse "$usage" "SECTION" "$@"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  c.js txtMarkdownCodeB64 | node -e '
    const regExpEscape = ((string) => string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")); // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions ; $& means the whole matched string
    let txt = fs.readFileSync("/dev/stdin", "utf8") + "\0";
    const match = txt.match(new RegExp(`^(## ${regExpEscape(process.argv[1])}$[\\s\\S]*?)(?=(\r?\n## |\0))`, "m"));
    if (match !== null) process.stdout.write(match[1]);' "$SECTION" | c.js txtMarkdownCodeB64d
}

test_md_sec() { #@test
  # /\0/
  echo -n $'## foo\n\nbar'               >/tmp/c.bash.d/test.in && echo -n $'## foo\n\nbar'     >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo\n\nbar\n'             >/tmp/c.bash.d/test.in && echo -n $'## foo\n\nbar\n'   >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo\n\nbar\n\n'           >/tmp/c.bash.d/test.in && echo -n $'## foo\n\nbar\n\n' >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  # /\r?\n## /
  echo -n $'## foo\n\nbar\n## baz\n'     >/tmp/c.bash.d/test.in && echo -n $'## foo\n\nbar'     >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo\n\nbar\n\n## baz\n'   >/tmp/c.bash.d/test.in && echo -n $'## foo\n\nbar\n'   >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo\n\nbar\n\n\n## baz\n' >/tmp/c.bash.d/test.in && echo -n $'## foo\n\nbar\n\n' >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3

  echo -n $'## baz\n\n## foo\n\nbar\n' >/tmp/c.bash.d/test.in && echo -n $'## foo\n\nbar\n'   >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## not_foo\n\nbar\n'       >/tmp/c.bash.d/test.in && echo -n $''                  >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo_not\n\nbar\n'       >/tmp/c.bash.d/test.in && echo -n $''                  >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_sec foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
}

# ------------------------------------------------------------------------------
# command - md_secsp
# sections starting with the specified prefix

define_command md_secsp
cmd::md_secsp() {
  local -r usage="usage: $PROG md_secsp [-h | --help] SECTION_PREFIX"
  local SECTION_PREFIX="" && arg_parse "$usage" "SECTION_PREFIX" "$@"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  c.js txtMarkdownCodeB64 | node -e '
    const regExpEscape = ((string) => string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")); // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions ; $& means the whole matched string
    const txt = fs.readFileSync("/dev/stdin", "utf8") + "\0eof\0";
    let txt2 = "";
    let lastSectionIsMatch = false;
    for (const match of txt.matchAll(new RegExp(`(^## ${regExpEscape(process.argv[1])}[\\s\\S]*?)(?=(^## |eof\0))`, "gm"))) {
      if (match[1].at(-1) === "\0") {
        // ## SECTION_PREFIX section ... \0 (eof \0 EOF)
        txt2 += match[1].slice(0, -1); // remove \0
        lastSectionIsMatch = true;
      } else {
        txt2 += match[1];
      }
    }
    if (lastSectionIsMatch) process.stdout.write(txt2);
    else process.stdout.write(txt2.slice(0, -1));
  ' "$SECTION_PREFIX" | c.js txtMarkdownCodeB64d
}

test_md_secsp() { #@test
  # last match
  echo -n $'## foo\n## foo1\n## foo2'                                 >/tmp/c.bash.d/test.in && echo -n $'## foo\n## foo1\n## foo2'         >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo\n## foo1\n## foo2\n'                               >/tmp/c.bash.d/test.in && echo -n $'## foo\n## foo1\n## foo2\n'       >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo\n## foo1\n## foo2\n\n'                             >/tmp/c.bash.d/test.in && echo -n $'## foo\n## foo1\n## foo2\n\n'     >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  # last not match
  echo -n $'## foo\n## foo1\n## foo2\n## bar\n'                       >/tmp/c.bash.d/test.in && echo -n $'## foo\n## foo1\n## foo2'         >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo\n## foo1\n## foo2\n\n## bar\n'                     >/tmp/c.bash.d/test.in && echo -n $'## foo\n## foo1\n## foo2\n'       >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo\n## foo1\n## foo2\n\n\n## bar\n'                   >/tmp/c.bash.d/test.in && echo -n $'## foo\n## foo1\n## foo2\n\n'     >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3

  # intersection
  echo -n $'## foo1\n## foo2'                                 >/tmp/c.bash.d/test.in && echo -n $'## foo1\n## foo2'         >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo1\n\n## foo2\n'                             >/tmp/c.bash.d/test.in && echo -n $'## foo1\n\n## foo2\n'     >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo1\n\n\n## foo2\n\n'                         >/tmp/c.bash.d/test.in && echo -n $'## foo1\n\n\n## foo2\n\n' >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  # intersection (with excluded section)
  echo -n $'## foo1\n## bar1\n## foo2\n## bar2'               >/tmp/c.bash.d/test.in && echo -n $'## foo1\n## foo2'         >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo1\n\n## bar1\n\n## foo2\n\n## bar2\n'       >/tmp/c.bash.d/test.in && echo -n $'## foo1\n\n## foo2\n'     >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
  echo -n $'## foo1\n\n\n## bar1\n\n## foo2\n\n\n## bar2\n\n' >/tmp/c.bash.d/test.in && echo -n $'## foo1\n\n\n## foo2\n\n' >/tmp/c.bash.d/test.expect && run -0 bash -c "bash ~/sh/c.bash md_secsp foo </tmp/c.bash.d/test.in >/tmp/c.bash.d/test.out && cmp /tmp/c.bash.d/test.expect /tmp/c.bash.d/test.out" && [[ $output == '' ]] || bats_run_debug_fail >&3
}

# ------------------------------------------------------------------------------
# command - netbsd_makefile_expand_vars

define_command netbsd_makefile_expand_vars
cmd::netbsd_makefile_expand_vars() {
  local -r usage="usage: $PROG netbsd_makefile_expand_vars [-h | --help] MAKE_COMMAND <Makefile"
  local MAKE_COMMAND="" && arg_parse "$usage" "MAKE_COMMAND" "$@"

  local -A pairs_name_value
  local line
  while IFS= read -r line; do  # `IFS=`: prevent removing leading/preceding spaces
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

    if [[ "$line" == "$line2" ]]; then
      echo "$line2"
    else
      echo "$line2$(echo -e '\t')# $line"
    fi
  done
}

# ------------------------------------------------------------------------------
# command - net_if_rename

define_command net_if_rename
cmd::net_if_rename() {
  local -r usage="usage: $PROG net_if_rename [-h | --help] MAC_ADDRESS NEW_NAME"
  local MAC_ADDRESS="" NEW_NAME="" && arg_parse "$usage" "MAC_ADDRESS NEW_NAME" "$@"

  # 42: enx00005e005300: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
  #     link/ether 00:00:5e:00:53:00 brd ff:ff:ff:ff:ff:ff
  shopt -s lastpipe && set +m  # set +m for interactive shell  TODO: restore -m
  ip a | grep -B1 "$MAC_ADDRESS" | grep -P -o '(?<=\d: )\w+(?=: <)' | read -r old_name
  set -x
  sudo ip link set "$old_name" down
  sudo ip link set "$old_name" name "$NEW_NAME"
  sudo ip link set "$NEW_NAME" up
}

# ------------------------------------------------------------------------------
# command - pkill (pk)
# sudo -v && [ -e /usr/local/bin/pk ] && printf "\e[37m""exists\n\e[0m" || echo -e '#!/bin/sh \n exec /home/wsh/sh/c.bash pkill "$@"' | sudo tee /usr/local/bin/pk && sudo chmod +x /usr/local/bin/pk

define_command pkill pk
cmd::pkill() {
  local -r usage="usage: $PROG pkill [-h | --help] ARG..."
  local -a ARG=() && arg_parse "$usage" "ARG..." "$@"
  trap '' ERR
  pgrep -a "${ARG[@]}"
  pkill "${ARG[@]}"
  exit 0
}

# ------------------------------------------------------------------------------
# command - pstree

define_command pstree
cmd::pstree() {
  local -r usage="usage: $PROG pstree [-h | --help] PIDS..."
  local -a PIDS="" && arg_parse "$usage" "PIDS..." "$@"
  local pid
  local -a pids
  log_debug "PIDS: ${PIDS[*]}"
  for pid in "${PIDS[@]}"; do
    while true; do
      pids+=("$pid")
      local ppid
      ppid=$(ps -p $pid -o ppid:1=)
      [[ $pid = "1" ]] && { [[ $ppid == "0" ]] || unreachable; } && break;
      pid=$ppid
    done
  done
  ( ((LOG_LEVEL >= LOG_DEBUG)) && set -x; ps -p "$(IFS=,; echo "${pids[*]}")" -H u -ww)
}

# ------------------------------------------------------------------------------
# command - pty_qemu

# @ref:qemu-pty

define_command pty_qemu
cmd::pty_qemu() {
  local -r usage=$(cat <<EOS
usage:
  $PROG pty_qemu {-h | --help}
  $PROG pty_qemu QEMU_PID
  $PROG pty_qemu netbsd  # "\$(pgrep -f 'qemu-system-x86_64 .+/netbsd.qcow2')"
EOS
)
  local QEMU_PID="" && arg_parse "$usage" "QEMU_PID" "$@"
  local QEMU_PID_orig=$QEMU_PID
  [[ $QEMU_PID == "netbsd" ]] && QEMU_PID=$(pgrep -f 'qemu-system-x86_64 .+/netbsd.qcow2')

  [[ $QEMU_PID =~ ^[0-9]+$ ]] || die 2 "invalid QEMU_PID: $QEMU_PID"

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
    if [[ $QEMU_PID_orig != "$QEMU_PID" ]]; then
      ln -fsv "$IN_PTY"         "/tmp/c.bash.d/pty.qemu.$QEMU_PID_orig"            # /tmp/c.bash.d/pty.qemu.netbsd
      ln -fsv "$OUT_FILE"       "/tmp/c.bash.d/pty.qemu.$QEMU_PID_orig.out"        # /tmp/c.bash.d/pty.qemu.netbsd.out
      ln -fsv "$OUT_FILE_TS"    "/tmp/c.bash.d/pty.qemu.$QEMU_PID_orig.out.ts"     # /tmp/c.bash.d/pty.qemu.netbsd.out.ts
      ln -fsv "$OUT_FILE_RAWTS" "/tmp/c.bash.d/pty.qemu.$QEMU_PID_orig.out.rawts"  # /tmp/c.bash.d/pty.qemu.netbsd.out.rawts
    fi
  fi
  ssh -t localhost "tail -F $OUT_FILE & socat -d -u STDIN,rawer OPEN:$IN_PTY"
}

# ------------------------------------------------------------------------------
# command - pty_usb

define_command pty_usb
cmd::pty_usb() {
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
# command - qemu_net_setup

define_command qemu_net_setup
cmd::qemu_net_setup() {
  local -r usage="usage: $PROG qemu_net_setup [-h | --help]"
  arg_parse "$usage" "" "$@"

  set -x

  # 2023-04-24 Mon wsh79
  # cat /proc/sys/net/ipv4/ip_forward
  # ssh ログイン後は 1 だが、startup 時は 0 だった
  [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == "1" ]] || echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward

  # @ref:qemu-bridge @ref:iptables-bridge

  sudo ip link add br100 type bridge; sudo ip link set br100 up; sudo ip address add 172.31.100.100/24 dev br100
  sudo ip link add br101 type bridge; sudo ip link set br101 up; sudo ip address add 172.31.101.100/24 dev br101
  sudo ip link add br102 type bridge; sudo ip link set br102 up; sudo ip address add 172.31.102.100/24 dev br102
  sudo ip link add br103 type bridge; sudo ip link set br103 up; sudo ip address add 172.31.103.100/24 dev br103
  sudo ip link add br104 type bridge; sudo ip link set br104 up; sudo ip address add 172.31.104.100/24 dev br104
  sudo ip link add br105 type bridge; sudo ip link set br105 up; sudo ip address add 172.31.105.100/24 dev br105
  sudo ip link add br106 type bridge; sudo ip link set br106 up; sudo ip address add 172.31.106.100/24 dev br106
  sudo ip link add br107 type bridge; sudo ip link set br107 up; sudo ip address add 172.31.107.100/24 dev br107

  sudo nft add table ip nat0
  sudo nft 'add chain nat0 postrouting0 { type nat hook postrouting priority 100 ; }'
  sudo nft add rule ip nat0 postrouting0 ip saddr 172.31.100.0/24 ip daddr != 172.31.100.0/24 counter masquerade
  sudo nft add rule ip filter FORWARD ip saddr 172.31.100.0/24 counter accept  # 行き
  sudo nft add rule ip filter FORWARD ip daddr 172.31.100.0/24 counter accept  # 帰り

  # sudo iptables -t nat -A POSTROUTING -s 172.31.100.0/24 ! -d 172.31.100.0/24 -j MASQUERADE
  # @ref:iptables-bridge
  # ! -d 172.31.100.0/24 が無いとguest間通信に問題がある
  #   172.31.100.85->172.31.100.38:
  #     qemu-ubu 172.31.100.85->172.31.100.38 -> tap0 -> br0 MASQUERADE 172.31.100.100->172.31.100.38 -> tap1 -> qemu .38: .38 から見ると .100 から来たように見える

  sudo systemctl start isc-dhcp-server.service
}

# ------------------------------------------------------------------------------
# command - qemu_pty

# compat

define_command qemu_pty
cmd::qemu_pty() {
  cmd::pty_qemu "${@}"
}

# ------------------------------------------------------------------------------
# command - smux

# @ref:socat-pty-exec-mux

define_command smux
cmd::smux() {
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
  [[ $SEP == "" ]] || [[ $SEP == "--" ]] || { err 0 "error: \"--\" missing; you may wanted to: smux $NAME -- $SEP ${CMD[*]}" && echo "$usage" >&2 && exit 2; }

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
    [[ ${#CMD[@]} == "0" ]] && die 2 "smux-server not found; CMD needed"
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
# command - spotify_code_to_token

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
cmd::spotify_code_to_token() {
  local -r usage="usage: $PROG spotify_code_to_token [-h | --help] REDIRECT_URI CODE"
  local REDIRECT_URI="" CODE="" && arg_parse "$usage" "REDIRECT_URI CODE" "$@"
  [[ ${SPOTIFY_APP_AUTH+defined} == "defined" ]] || die 1 "environment variable SPOTIFY_APP_AUTH is not set"
  curl -fSs -X POST -H "Authorization: Basic $SPOTIFY_APP_AUTH" -d code="$CODE" -d redirect_uri="$REDIRECT_URI" -d grant_type=authorization_code "https://accounts.spotify.com/api/token" >/tmp/c.bash.d/spotify_code_to_token.json
  # jq < /tmp/c.bash.d/spotify_code_to_token.json
  log_debug "$(jq < /tmp/c.bash.d/spotify_code_to_token.json)"
  log_info "/tmp/c.bash.d/spotify_code_to_token.access_token.txt"
  log_info "/tmp/c.bash.d/spotify_code_to_token.refresh_token.txt"
  jq -er < /tmp/c.bash.d/spotify_code_to_token.json ".access_token" > /tmp/c.bash.d/spotify_code_to_token.access_token.txt
  jq -er < /tmp/c.bash.d/spotify_code_to_token.json ".refresh_token" > /tmp/c.bash.d/spotify_code_to_token.refresh_token.txt
}

# ------------------------------------------------------------------------------
# command - spotify_http_server

# google-chrome https://accounts.spotify.com/authorize?client_id=c78a65c5fb94462997b01eeeaf524324&response_type=code&redirect_uri=http://localhost:15350&scope=user-read-currently-playing
# -> http://localhost:15350/?code={CODE}

define_command spotify_http_server
cmd::spotify_http_server() {
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
# command - spotify_say_song

define_command spotify_say_song
cmd::spotify_say_song() {
  local -r usage="usage: $PROG spotify_say_song [-h | --help]"
  arg_parse "$usage" "" "$@"
  [[ ${SPOTIFY_TOKEN+defined} == "defined" ]] || die 1 "environment variable SPOTIFY_TOKEN is not set"

  local rest_secs
  local artist_prev="" album_prev="" name_prev=""
  while true; do
    curl -fSs -X "GET" "https://api.spotify.com/v1/me/player/currently-playing" -H "Accept: application/json" -H "Content-Type: application/json" -H "Authorization: Bearer $SPOTIFY_TOKEN" > /tmp/c.bash.d/spotify_say_song.json

    local artist name
    artist="$(jq -er < /tmp/c.bash.d/spotify_say_song.json ".item.artists[0].name")"
    album="$(jq -er < /tmp/c.bash.d/spotify_say_song.json ".item.album.name")"
    name="$(jq -er < /tmp/c.bash.d/spotify_say_song.json ".item.name")"
    [[ -z $artist ]] && [[ -z $album ]] && [[ -z $name ]] && log_debug "not playing" && sleep 10 && continue
    [[ $artist == "$artist_prev" ]] && [[ $album == "$album_prev" ]] && [[ $name == "$name_prev" ]] && log_debug "$artist - $album - $name; not changed; retry" && sleep 1 && continue
    log_debug "$artist - $album - $name"

    local say_name_begin say_name_secs
    cmd::spotify_say_song::say() {
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
      say_name_begin=$(date "+%s.%N")
      for _ in {1..2}; do
        if LANG=C grep '[^[:cntrl:][:print:]]' <<< "$name"; then
          echo "$name" | kakasi -i utf8 -JH | timeout 2 espeak -s120 -v ja+f3 || true
        else
          echo "$name"                      | timeout 2 espeak -s120 -v f1 || true
        fi
      done
      say_name_secs=$(echo "$(date "+%s.%N") - $say_name_begin" | bc)
    }

    cmd::spotify_say_song::say
    artist_prev=$artist && album_prev=$album && name_prev=$name

    curl -fSs -X "GET" "https://api.spotify.com/v1/me/player/currently-playing" -H "Accept: application/json" -H "Content-Type: application/json" -H "Authorization: Bearer $SPOTIFY_TOKEN" > /tmp/c.bash.d/spotify_say_song.json
    [[ $name != "$name_prev" ]] && continue  # song changed while speaking
    rest_secs=$(jq -e < /tmp/c.bash.d/spotify_say_song.json "(.item.duration_ms - .progress_ms) / 1000")

    # re-say just before the end of the song
    if (($(echo "$say_name_secs < $rest_secs - 1" | bc))); then
      local sleep_secs
      sleep_secs=$(echo "$rest_secs - 1 - $say_name_secs" | bc)
      log_debug "sleep $sleep_secs (then re-say)"
      sleep "$sleep_secs"
      cmd::spotify_say_song::say
      continue
    fi

    log_debug "sleep: $rest_secs (no re-say)"
    sleep "$rest_secs"
  done

  unreachable
}

# ------------------------------------------------------------------------------
# command - strace_prettify

: <<'DOC'
@beg:strace_prettify:tcase
710895 execve("/home/wsh/bin/bazel", ["bazel", "build", "-j", "1", "package", "--config", "oss_linux"], 0x7fff0476dda0 /* 50 vars */) = 0
710895 clone(child_stack=0xc000070000, flags=CLONE_VM|CLONE_FS|CLONE_FILES|CLONE_SIGHAND|CLONE_THREAD|CLONE_SYSVSEM|CLONE_SETTLS, tls=0xc000060090) = 710896
710896 gettid( <unfinished ...>
@end:strace_prettify:tcase
↓
[PID:1] execve("/home/wsh/bin/bazel", ["bazel", "build", "-j", "1", "package", "--config", "oss_linux"], 0x7fff0476dda0 /* 50 vars */) = 0
[PID:1] clone(child_stack=0xc000070000, flags=CLONE_VM|CLONE_FS|CLONE_FILES|CLONE_SIGHAND|CLONE_THREAD|CLONE_SYSVSEM|CLONE_SETTLS, tls=0xc000060090) = [PID:2]
[PID:2] gettid( <unfinished ...>

c.bash bef "strace_prettify:tcase" /home/wsh/sh/c.bash | c.bash strace_prettify
DOC

define_command strace_prettify
cmd::strace_prettify() {
  local -r usage="usage: $PROG strace_prettify [-h | --help] [FILE]"
  local FILE="" && arg_parse "$usage" "[FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  cat "$FILE" >/tmp/c.bash.d/strace_prettify.in.txt
  local -i i=0
  grep -P -o "^\d+(?= )" /tmp/c.bash.d/strace_prettify.in.txt | uniq | while IFS= read -r line; do  # `IFS=`: prevent removing leading/preceding spaces
    ((i++)) || true  # > If the value of the expression is non-zero, the return status is 0; otherwise the return status is 1.
    sed -i -E "s/\b$line\b/[PID:$i]/g" /tmp/c.bash.d/strace_prettify.in.txt
  done
  cat /tmp/c.bash.d/strace_prettify.in.txt
}

# ------------------------------------------------------------------------------
# command - time_sub

define_command time_sub
cmd::time_sub() {
  local -r usage="usage: $PROG time_sub [-h | --help] L R FMT"
  local L="" R="" FMT="" && arg_parse "$usage" "L R FMT" "$@"
  diff_epoch=$(("$(date -d"$L" "+%s")" - "$(date -d"$R" "+%s")"))
  # printf "%($FMT)T\n" "$diff_epoch"  # JP: JST: +9h
  date -u -d@"$diff_epoch" "+$FMT"
}

test_time_sub() { #@test
  run -0 bash ~/sh/c.bash time_sub " 1      " "0" "%s %F %T"            && [[ $output == "3600 1970-01-01 01:00:00" ]] || bats_run_debug_fail >&3
  run -0 bash ~/sh/c.bash time_sub "01:00   " "0" "%s %F %T"            && [[ $output == "3600 1970-01-01 01:00:00" ]] || bats_run_debug_fail >&3
  run -0 bash ~/sh/c.bash time_sub "01:00:00" "0" "%s %F %T"            && [[ $output == "3600 1970-01-01 01:00:00" ]] || bats_run_debug_fail >&3
  run -0 bash ~/sh/c.bash time_sub "01:01:01" "0" "%s %F %T"            && [[ $output == "3661 1970-01-01 01:01:01" ]] || bats_run_debug_fail >&3
  run -0 bash ~/sh/c.bash time_sub "23:59:59" "0" "%s %F %T"            && [[ $output == "86399 1970-01-01 23:59:59" ]] || bats_run_debug_fail >&3
  run -0 bash ~/sh/c.bash time_sub "23:59:59" "1h 1min 1sec" "%s %F %T" && [[ $output == "21538 1970-01-01 05:58:58" ]] || bats_run_debug_fail >&3
}

# ------------------------------------------------------------------------------
# command - txt_begin_end (be)
#
# prints:
# @beg:NAME
# HERE
# @end:NAME
#
# c.bash -v be NAME </home/wsh/sh/c.bash  # HERE
# c.bash -v be NONEXISTENT </home/wsh/sh/c.bash  # no output
# c.bash -v bef NAME </home/wsh/sh/c.bash  # HERE
# c.bash -v bef NONEXISTENT </home/wsh/sh/c.bash  # TypeError

define_command txt_begin_end be
cmd::txt_begin_end() {
  local -r usage="usage: [... |] $PROG txt_begin_end (be) [-h | --help] NAME [FILE]"
  local NAME="" FILE="" && arg_parse "$usage" "NAME [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"

  local in_section="false"
  cmd::txt_begin_end::process_line() {
    if [[ $in_section == "false" ]]; then
      log_debug "    $line"
      # shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true
      [[ $line =~ ^.*"@beg:$NAME"$         || $line =~ ^.*"@beg:$NAME "         ]] && in_section="true" && log_info "[->*] $line" || true
      [[ $line =~ ^.*"c.bash:begin:$NAME"$ || $line =~ ^.*"c.bash:begin:$NAME " ]] && in_section="true" && log_info "[->*] $line" || true
    else
      log_debug "[*] $line"
      [[ $line =~ ^.*"@end:$NAME"$         || $line =~ ^.*"@end:$NAME "         ]] && in_section="false" && log_info "[*->] $line" && return 1
      [[ $line =~ ^.*"c.bash:end:$NAME"$   || $line =~ ^.*"c.bash:end:$NAME "   ]] && in_section="false" && log_info "[*->] $line" && return 1
      echo "$line"
    fi
  }

  local line
  while IFS= read -r line; do  # `IFS=`: prevent removing leading/preceding spaces
    cmd::txt_begin_end::process_line || exit 0
  done <"$FILE"

  exit 0
}

# ------------------------------------------------------------------------------
# command - txt_begin_end_fast (bef)

define_command txt_begin_end_fast bef
cmd::txt_begin_end_fast() {
  local -r usage="usage: [... |] $PROG txt_begin_end_fast (bef) [-h | --help] NAME [FILE]"
  local NAME="" FILE="" && arg_parse "$usage" "NAME [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").match(new RegExp(`@beg:${process.argv[1]}\\b.*\r?\n([\\s\\S]*?\r?\n)^.*@end:${process.argv[1]}\\b`, "m"))[1]); // TODO: escape argv[1]' "$NAME" <"$FILE"
}

# ------------------------------------------------------------------------------
# command - txt_begin_end_v (bev)
#
# excludes (like grep -v):
# @beg:NAMEV  from here
# ...
# @end:NAMEV    to here
#
# c.bash -v bev NAMEV </home/wsh/sh/c.bash >/tmp/a
# diff -u /home/wsh/sh/c.bash /tmp/a
# c.bash -v bev NONEXISTENT </home/wsh/sh/c.bash >/tmp/a
# diff -u /home/wsh/sh/c.bash /tmp/a  # no diff

define_command txt_begin_end_v bev
cmd::txt_begin_end_v() {
  local -r usage="usage: [... |] $PROG txt_begin_end_v (bev) [-h | --help] NAME [FILE]"
  local NAME="" FILE="" && arg_parse "$usage" "NAME [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"

  local in_section="false"
  cmd::txt_begin_end_v::process_line() {
    if [[ $in_section == "true" ]]; then
      log_debug "[-v] $line"
      # shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true
      [[ $line =~ ^.*"@end:$NAME"$           || $line =~ ^.*"@end:$NAME "           ]] && in_section="false" && log_info "[-v ->] $line" || true
      [[ $line =~ ^.*"c.bash:end_v:$NAME"$   || $line =~ ^.*"c.bash:end_v:$NAME "   ]] && in_section="false" && log_info "[-v ->] $line" || true
    else
      log_debug "     $line"
      [[ $line =~ ^.*"@beg:$NAME"$           || $line =~ ^.*"@beg:$NAME "           ]] && in_section="true" && log_info "[-> -v] $line" && return
      [[ $line =~ ^.*"c.bash:begin_v:$NAME"$ || $line =~ ^.*"c.bash:begin_v:$NAME " ]] && in_section="true" && log_info "[-> -v] $line" && return
      echo "$line"
    fi
  }

  local line
  while IFS= read -r line; do cmd::txt_begin_end_v::process_line; done <"$FILE"  # `IFS=`: prevent removing leading/preceding spaces

  exit 0
}

# ------------------------------------------------------------------------------
# command - txt_begin_end_v_fast (bevf)
#
# excludes (like grep -v):
# @beg:NAMEV  from here
# ...
# @end:NAMEV    to here
#
# c.bash -v bevf NAMEV </home/wsh/sh/c.bash >/tmp/a
# diff -u /home/wsh/sh/c.bash /tmp/a
# c.bash -v bevf NONEXISTENT </home/wsh/sh/c.bash >/tmp/a
# diff -u /home/wsh/sh/c.bash /tmp/a  # no diff

define_command txt_begin_end_v_fast bevf
cmd::txt_begin_end_v_fast() {
  local -r usage="usage: [... |] $PROG txt_begin_end_v_fast (bevf) [-h | --help] NAME [FILE]"
  local NAME="" FILE="" && arg_parse "$usage" "NAME [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").replaceAll(new RegExp(`^.*@beg:${process.argv[1]}\\b.*\r?\n[\\s\\S]*?@end:${process.argv[1]}\\b.*(\r?\n|$)`, "gm"), ""))' "$NAME" <"$FILE"
}

# ------------------------------------------------------------------------------
# command - txt_bv_ev (bv)
#
# excludes (like grep -v):
# @ bv  from here
# ...
# @ ev    to here
#
# c.bash bv </home/wsh/sh/c.bash >/tmp/a
# diff -u /home/wsh/sh/c.bash /tmp/a

define_command txt_bv_ev bv
cmd::txt_bv_ev() {
  local -r usage="usage: [... |] $PROG txt_bv_ev (bv) [-h | --help] [FILE]"
  local FILE="" && arg_parse "$usage" "[FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  # from c.js txtPrivate
  node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").replaceAll(new RegExp(`^.*[@]bv\\b.*\r?\n[\\s\\S]*?[@]ev\\b.*(\r?\n|$)`, "gm"), ""))' <"$FILE"
}

# ------------------------------------------------------------------------------
# command - txt_eval

define_command txt_eval
cmd::txt_eval() {
  local -r usage="usage: [... |] $PROG txt_eval [-h | --help] [FILE]"
  local FILE="" && arg_parse "$usage" "[FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"

  local in_echo_eval="false"
  cmd::txt_eval::process_line() {
    [[ $line =~ ^"@echo_eval:end"$ ]] && in_echo_eval="false" && log_info "[in_echo_eval: true->false] $line" && return
    if [[ $in_echo_eval == "true" ]]; then
      log_info "[in_echo_eval] $line"
      echo "$line"
      eval "$line"
      return
    fi
    [[ $line =~ ^"@echo_eval:begin"$ ]] && in_echo_eval="true" && log_info "[in_echo_eval: false->true] $line" && return
    [[ $line =~ ^(.*)[[:space:]]*"# @echo_eval:this"$ ]]          && log_info "[@echo_eval:this]          $line" &&   echo "${BASH_REMATCH[1]}" && eval "${BASH_REMATCH[1]}"            && return
    [[ $line =~ ^(.*)[[:space:]]*"# @echo_eval_may_fail:this"$ ]] && log_info "[@echo_eval_may_fail:this] $line" && { echo "${BASH_REMATCH[1]}" && eval "${BASH_REMATCH[1]}" || true; } && return
    [[ $line =~ ^(.*)[[:space:]]*"# @eval:this"$ ]]               && log_info "[@eval:this]               $line" &&                                eval "${BASH_REMATCH[1]}"            && return
    [[ $line =~ ^(.*)[[:space:]]*"# @eval_may_fail:this"$ ]]      && log_info "[@eval_may_fail:this]      $line" &&                              { eval "${BASH_REMATCH[1]}" || true; } && return
    log_debug "[default] $line"
    echo "$line"
  }

  local line
  while IFS= read -r line; do cmd::txt_eval::process_line; done <"$FILE"  # `IFS=`: prevent removing leading/preceding spaces

  exit 0
}

# ------------------------------------------------------------------------------
# command - txt_replace (rep)

# c.bash rep "$(c.bash grep_multiline -P -m1 "^define_command grep_multiline" "cat" < /home/wsh/sh/c.bash)" "hi there" < /home/wsh/sh/c.bash > /tmp/c.bash.d/rep.test.bash
# delta /home/wsh/sh/c.bash /tmp/c.bash.d/rep.test.bash

define_command txt_replace rep DEPRECATED:replace
cmd::txt_replace() {
  local -r usage="usage: ... | $PROG txt_replace (rep) [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  # replaces only one
  # time node -e 'console.log(fs.readFileSync("/dev/stdin", "utf8").replace(process.argv[1], process.argv[2].replaceAll("$", "$$$$")))' foo bar
  # time python3 -c "import sys; print(sys.stdin.read().replace(sys.argv[1], sys.argv[2], 1), end='')" "$FROM" "$TO"
  python3 -c "import sys; print(sys.stdin.read().replace(sys.argv[1], sys.argv[2], 1), end='')" "$FROM" "$TO"
}

# ------------------------------------------------------------------------------
# command - txt_replace_all (repa)

define_command txt_replace_all repa DEPRECATED:replace_all
cmd::txt_replace_all() {
  local -r usage="usage: ... | $PROG txt_replace_all (repa) [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  # node -e 'console.log(fs.readFileSync("/dev/stdin", "utf8").replaceAll(process.argv[1], process.argv[2].replaceAll("$", "$$$$")))' foo bar
  python3 -c "import sys; print(sys.stdin.read().replace(sys.argv[1], sys.argv[2]), end='')" "$FROM" "$TO"
}

# ------------------------------------------------------------------------------
# command - txt_replace_line (repl)

define_command txt_replace_line repl DEPRECATED:replace_line
cmd::txt_replace_line() {
  local -r usage="usage: ... | $PROG txt_replace_line (repl) [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  python3 -c "import sys; [print(line.replace(sys.argv[1], sys.argv[2], 1), end='') for line in sys.stdin]" "$FROM" "$TO"  # not tested
}

# ------------------------------------------------------------------------------
# command - txt_replace_line_all (repla)

define_command txt_replace_line_all repla DEPRECATED:replace_line_all
cmd::txt_replace_line_all() {
  local -r usage="usage: ... | $PROG txt_replace_line_all (repla) [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  # node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").replaceAll(process.argv[1], process.argv[2].replaceAll("$", "$$$$")))' "$FROM" "$TO"  # not tested
  python3 -c "import sys; [print(line.replace(sys.argv[1], sys.argv[2]), end='') for line in sys.stdin]" "$FROM" "$TO"
}

# ------------------------------------------------------------------------------
# command - xargs_delay

define_command xargs_delay
cmd::xargs_delay() {
  local -r usage="usage: ... | $PROG xargs_delay [-h | --help] [-L1] [-I replace-str] COMMAND..."
  local -a COMMAND=() && arg_parse "$usage" "COMMAND..." "$@"
  local -a lines=()
  local -A line_latest_epochs=()
  while true; do
    local line
    IFS= read -r -t0.1 line || {  # `IFS=`: prevent removing leading/preceding spaces
      [[ $line != "" ]] && {
        # reaches here even with -t0.7; 0.1 でも 0.7 でも頻度は変わらない。↓ の -t1 以降は必ず完全なパスになった。スケジューラー依存かな
        # read "/" -> read "home/wsh/a.conf" of /home/wsh/a.conf
        # read "/home/wsh/a.c" -> read "onf" of /home/wsh/ample.conf
        log_warning "timeout with non-empty line: $line"
        echo -n "$line" | xxd >&2
        log_warning "trying to read the rest of the line..."
        IFS= read -r -t1 line2
        log_warning "line2: $line2"
        echo -n "$line2" | xxd >&2

        line="$line$line2"
        log_warning "line -> $line"
      }
    }
    if [[ $line != "" ]]; then
      [[ -e $line ]] || err 1 "not exist (git rebasing?): $line" || continue  # tmp for rsync
      [[ -f $line ]] || die 1 "BUG: not a file: $line"  # tmp for rsync
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
      if [[ $(echo "$now - ${line_latest_epochs[$line_]} > 0.5" | bc) == "1" ]]; then
        log_info "$line_: 0.5 seconds elapsed since the last seen; fire: ${COMMAND[*]} $line_"
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

cmd::repl() {
  touch ~/.c_bash_repl_history
  while true; do
    shopt -s lastpipe && set +m  # set +m for interactive shell  TODO: restore -m
    local line
    rlwrap -c -C c_bash_repl -f. -pgreen -S'$ ' -- head -1 | IFS= read -r line || {  # `IFS=`: prevent removing leading/preceding spaces
      local rc=$?
      # line=$'\n'
      log_info "EOF"
      [[ $rc == "1" ]] || log_warning "BUG: \$?: $rc"
      [[ $line == "" ]] || log_warning "BUG: \$line: $line (xxd: $(echo -n "$line" | xxd))"
      break
    }
    if false; then
      # xxd <<<"$line"  # "<<<" seems to append \n
      echo -n "$line" | xxd
    fi
    log_debug "\$line: $line (xxd: $(echo -n "$line" | xxd))"
    eval "$line"
  done
}

# ------------------------------------------------------------------------------
# command - z_meta_command_list

define_command z_meta_command_list
cmd::z_meta_command_list() {
  local -r usage="usage: $PROG z_meta_command_list [-h | --help]"
  arg_parse "$usage" "" "$@"
  # for cmd in "${!_commands[@]}"; do  # order is unstable
  for cmd in "${_command_list_stable_no_deprecated[@]}"; do
    echo "$cmd"
  done
}

# ------------------------------------------------------------------------------
# command - z_meta_command_list_no_alias

define_command z_meta_command_list_no_alias
cmd::z_meta_command_list_no_alias() {
  local -r usage="usage: $PROG z_meta_command_list_no_alias [-h | --help]"
  arg_parse "$usage" "" "$@"
  for cmd in "${_command_list_stable_no_deprecated_no_alias[@]}"; do
    echo "$cmd"
  done
}

# ------------------------------------------------------------------------------
# main tests

# shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
# shellcheck disable=SC2154  # * is referenced but not assigned.
test_main() { #@test
  run -0 --separate-stderr bash ~/sh/c.bash -h                 && [[ $output =~ "usage:" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -h --              && [[ $output =~ "usage:" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash                    && [[ $output == "" ]] && [[ $stderr =~ "command not specified".*"usage:" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash --                 && [[ $output == "" ]] && [[ $stderr =~ "command not specified".*"usage:" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -x                 && [[ $output == "" ]] && [[ $stderr =~ ": illegal option -- x".*"usage:" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -x --              && [[ $output == "" ]] && [[ $stderr =~ ": illegal option -- x".*"usage:" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash    no_such_command && [[ $output == "" ]] && [[ $stderr =~ "no such command: no_such_command".*"usage:" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -- no_such_command && [[ $output == "" ]] && [[ $stderr =~ "no such command: no_such_command".*"usage:" ]] || bats_run_debug_fail >&3

  run -2 --separate-stderr bash ~/sh/c.bash -v    0template                && [[ $output == "" ]] && [[ $stderr =~ "error: required argument: \"ARG\" missing".*"usage:" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -v -- 0template                && [[ $output == "" ]] && [[ $stderr =~ "error: required argument: \"ARG\" missing".*"usage:" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -v    0template arg1           && [[ $output == "ARG: arg1" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -v -- 0template arg1           && [[ $output == "ARG: arg1" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -v    0template arg1 arg2      && [[ $output == "" ]] && [[ $stderr =~ "error: excess argument(s): arg2" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -v -- 0template arg1 arg2      && [[ $output == "" ]] && [[ $stderr =~ "error: excess argument(s): arg2" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -v    0template arg1 arg2 arg3 && [[ $output == "" ]] && [[ $stderr =~ "error: excess argument(s): arg2 arg3" ]] || bats_run_debug_fail >&3
  run -2 --separate-stderr bash ~/sh/c.bash -v -- 0template arg1 arg2 arg3 && [[ $output == "" ]] && [[ $stderr =~ "error: excess argument(s): arg2 arg3" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -v    0template -h             && [[ $output == "usage: c.bash 0template [-h | --help] ARG" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -v -- 0template -h             && [[ $output == "usage: c.bash 0template [-h | --help] ARG" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -v    0template -z             && [[ $output == "ARG: -z" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -v -- 0template -z             && [[ $output == "ARG: -z" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3

  # runs main regardless of the name (even when not "c.bash")
  cp ~/sh/c.bash /tmp/c.bash.d/test_main.c.bash && chmod +x /tmp/c.bash.d/test_main.c.bash
  run -0 --separate-stderr bash /tmp/c.bash.d/test_main.c.bash -h                 && [[ $output =~ "usage:" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr      /tmp/c.bash.d/test_main.c.bash -h                 && [[ $output =~ "usage:" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  # in source: return 0, no main
  echo $'#!/bin/bash\nsource /tmp/c.bash.d/test_main.c.bash' > /tmp/c.bash.d/test_main.test.bash && chmod +x /tmp/c.bash.d/test_main.test.bash
  run -0 --separate-stderr bash /tmp/c.bash.d/test_main.test.bash                 && [[ $output == "" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr      /tmp/c.bash.d/test_main.test.bash                 && [[ $output == "" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash -c "source /tmp/c.bash.d/test_main.c.bash -h"     && [[ $output == "" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3

  run -0 --separate-stderr bash -c "bash <~/sh/c.bash -s -- -h            " && [[ $output =~ "usage:" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash -c "bash <~/sh/c.bash -s -- 0template arg1" && [[ $output == "ARG: arg1" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  # TODO: test all the styles listed in [todo_test_main]

  # $0 TODO
if false; then
  cd /tmp/c.bash.d/
  cp ~/sh/c.bash ./
  cp ~/sh/c.bash ./foo
  cp ~/sh/c.bash ./z_meta_command_list
  # TODO: -h
                run -2 --separate-stderr      ~/sh/c.bash                       && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr bash ~/sh/c.bash                       && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr      ./foo                             && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr bash ./foo                             && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr      /tmp/c.bash.d/foo                 && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr bash /tmp/c.bash.d/foo                 && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -0 --separate-stderr      ./z_meta_command_list             && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
                run -0 --separate-stderr bash ./z_meta_command_list             && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
                run -0 --separate-stderr      /tmp/c.bash.d/z_meta_command_list && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
                run -0 --separate-stderr bash /tmp/c.bash.d/z_meta_command_list && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -2 --separate-stderr      c.bash                            && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -2 --separate-stderr bash c.bash                            && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -2 --separate-stderr      foo                               && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -2 --separate-stderr bash foo                               && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -0 --separate-stderr      z_meta_command_list               && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -0 --separate-stderr bash z_meta_command_list               && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
fi
}

test_main_global_flags() { #@test
  export C_BASH_DEBUG_GLOBAL_FLAGS=1
  run -0 --separate-stderr bash ~/sh/c.bash -vv -v    CMD -a arg1 -- arg2 && [[ $output == "global_flags:-vv|-v @:CMD|-a|arg1|--|arg2" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  run -0 --separate-stderr bash ~/sh/c.bash -vv -v -- CMD -a arg1 -- arg2 && [[ $output == "global_flags:-vv|-v|-- @:CMD|-a|arg1|--|arg2" ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  #c.bash   # @ -vv -v    CMD -a arg1 -- arg2 | OPTIND 3 | [!OPTIND(3)] CMD | [..OPTIND-1(2)] -vv -v    |
  #c.bash   # @ -vv -v -- CMD -a arg1 -- arg2 | OPTIND 4 | [!OPTIND(4)] CMD | [..OPTIND-1(3)] -vv -v -- |
}

# ------------------------------------------------------------------------------
# main

[[ $C_BASH_DO_MAIN == "no" ]] && return 0

if [[ ${HAVE_UTIL_LINUX_GETOPT+defined} != defined ]]; then
  if getopt --version 2>/dev/null | grep -q util-linux; then
    HAVE_UTIL_LINUX_GETOPT="yes"
  else
    HAVE_UTIL_LINUX_GETOPT="no"
  fi
fi

OPT_q="false"
OPT_v=0
global_flags=()

if not_yet && [[ "$HAVE_UTIL_LINUX_GETOPT" == "yes" ]]; then
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
fi

[ $# != 0 ] && [[ $1 == "-h" || $1 == "-help" || $1 == "--help" ]] && top_usage && exit 0
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
global_flags=("${@:1:$OPTIND-1}")  # [1.. (len:$((OPTIND-1)))] (OPTIND:3, ${!OPTIND} == $3)
shift $((OPTIND - 1))
[[ -v C_BASH_DEBUG_GLOBAL_FLAGS ]] && (IFS="|" && echo "global_flags:${global_flags[*]} @:$*") && exit 0

[[ $OPT_q == "true" ]] && ((OPT_v > 0)) && die 1 "-q and -v are mutually exclusive"
[[ $OPT_q == "true" ]] && log_setlevel $LOG_ERR
((OPT_v == 1)) && log_setlevel $LOG_INFO
((OPT_v > 1)) && log_setlevel $LOG_DEBUG

_pre_main

# [[ $0 =~ ^.*/?"c.bash"$ ]] || TODO: COMMAND_=${0##*/}

(($# == 0)) && err 0 "command not specified" && top_usage >&2 && exit 2
COMMAND_=$1 && shift
[[ -v _commands[$COMMAND_] ]] || { err 0 "no such command: $COMMAND_" && top_usage >&2 && exit 2; }
"cmd::${_commands[$COMMAND_]}" "$@"
exit $?

# ------------------------------------------------------------------------------
# z Bash Reference Manual
# https://www.gnu.org/software/bash/manual/bash.html

# TODO:
# https://tiswww.case.edu/php/chet/bash/FAQ
# https://mywiki.wooledge.org/BashFAQ

# https://stackoverflow.com/a/16715681

if false; then
source /home/wsh/sh/c.bash
IN_BATS=no
log_setlevel "$LOG_DEBUG"
fi  # if false

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 1 Introduction

# 1.1 What is Bash?
# 1.2 What is a shell?

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 2 Definitions

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 3 Basic Shell Features

if false; then
# @beg:man_3

# 3.1 Shell Syntax
# 3.1.1 Shell Operation
# 3.1.2 Quoting
# 3.1.2.1 Escape Character
# 3.1.2.2 Single Quotes
# 3.1.2.3 Double Quotes
# 3.1.2.4 ANSI-C Quoting
# 3.1.2.5 Locale-Specific Translation
# 3.1.3 Comments
# 3.2 Shell Commands
# 3.2.1 Reserved Words
# 3.2.2 Simple Commands

# 3.2.3 Pipelines
# [time [-p]] [!] command1 [ | or |& command2 ] …

echo |& cat  # echo 2>&1 | cat

(
  set -e
  # false  # die
  ! false  # not die
  ! true   # not die (!)
)

# lastpipe
# when job control is not active
{
  bash
  echo "$$ $BASHPID"  # 100 100
  unset var

  shopt -u lastpipe
  true | eval 'echo this is subshell; echo "$$ $BASHPID"'  # 100 101
  echo val | read -r var  # read -r var: executed in subshell, which immediately exits
  declare -p var  # bash: declare: var: not found

  shopt -s lastpipe && set +m  # set +m for interactive shell
  true | eval 'echo this is parent shell; echo "$$ $BASHPID"'  # 100 100
  echo val | read -r var
  declare -p var  # declare -- var="val"
}

# pipefail
ret() { return "$1"; }
ret 1 | ret 2 | ret 3; echo $?; (set -o pipefail; ret 1 | ret 2 | ret 3; echo $?) # 3 3
ret 0 | ret 0 | ret 0; echo $?; (set -o pipefail; ret 0 | ret 0 | ret 0; echo $?) # 0 0  > zero if all commands exit successfully
ret 1 | ret 0 | ret 0; echo $?; (set -o pipefail; ret 1 | ret 0 | ret 0; echo $?) # 0 1
ret 0 | ret 2 | ret 0; echo $?; (set -o pipefail; ret 0 | ret 2 | ret 0; echo $?) # 0 2
ret 0 | ret 0 | ret 3; echo $?; (set -o pipefail; ret 0 | ret 0 | ret 3; echo $?) # 3 3
ret 1 | ret 2 | ret 0; echo $?; (set -o pipefail; ret 1 | ret 2 | ret 0; echo $?) # 0 2  > the value of the last (rightmost) command to exit with a non-zero status

(set -e            ; ret 42 | ret 0          ; echo "$? not die") ; echo "$?" # 0 not die  0
(set -e            ; ret 0 | ret 42          ; unreachable)       ; echo "$?" #            42
(set -e -o pipefail; ret 42 | ret 0          ; unreachable)       ; echo "$?" #            42
(set -e -o pipefail; ret 42 | ret 43 | ret 0 ; unreachable)       ; echo "$?" #            43

# 3.2.4 Lists of Commands
# > A list is a sequence of one or more pipelines separated by one of the operators ‘;’, ‘&’, ‘&&’, or ‘||’, and optionally terminated by one of ‘;’, ‘&’, or a newline.
command1 && command2
command1 || command2

# 3.2.5 Compound Commands
# > begins with a reserved word or control operator and is terminated by a corresponding reserved word or operator
# e.g. if ... fi
# > Any redirections (see Redirections) associated with a compound command apply to all commands within that compound command unless explicitly overridden
# e.g. if true; then cmd1; cmd2; cmd3 >b; fi >a  # cmd1/cmd2 >a

until test-commands; do consequent-commands; done

while test-commands; do consequent-commands; done

# for name [ [in [words …] ] ; ] do commands; done
for (( expr1 ; expr2 ; expr3 )) ; do commands ; done

# if test-commands; then
#   consequent-commands;
# [elif more-test-commands; then
#   more-consequents;]
# [else alternate-consequents;]
# fi

# case word in
#     [ [(] pattern [| pattern]…) command-list ;;]…
# esac
# ;;   break
# ;&   fallthrough
# ;;&  continues testing next case

# select name [in words …]; do commands; done

# shellcheck disable=SC2154  # expression is referenced but not assigned.
(( expression ))  # 0 -> returns 1, non-zero -> returns 0; see 6.5 Shell Arithmetic

# shellcheck disable=SC2078  # This expression is constant. Did you forget a $ somewhere?
[[ expression ]]  # < > == != =~
if false; then
  # POSIX extended regular expression pattern
  # using the POSIX regcomp and regexec interfaces usually described in regex(3)
  # returns:
  # - 0 (matches)
  # - 1 (does not)
  # - 2 (the regular expression is syntactically incorrect)
  # nocasematch shell option

: <<'COMMENT'
@ref:ERE-character-class
https://www.gnu.org/software/grep/manual/html_node/Character-Classes-and-Bracket-Expressions.html
in the ‘C’ locale and ASCII character encoding
[:alnum:]  [[:alnum:]]   [0-9A-Za-z]
[:alpha:]  [[:alpha:]]   [A-Za-z]
[:blank:]  [[:blank:]]   space and tab
[:cntrl:]  [[:cntrl:]]   octal codes 000 through 037, and 177 (DEL)
[:digit:]  [[:digit:]]   [0-9] (prefer[0-9])
[:graph:]  [[:graph:]]   [:alnum:] and [:punct:]
[:lower:]  [[:lower:]]   [a-z] (prefer [a-z])
[:print:]  [[:print:]]   [:alnum:], [:punct:], and space
[:punct:]  [[:punct:]]   ! " # $ % & ' ( ) * + , - . / : ; < = > ? @ [ \ ] ^ _ ` { | } ~
[:space:]  [[:space:]]   tab, newline, vertical tab, form feed, carriage return, and space
[:upper:]  [[:upper:]]   [A-Z] (prefer [A-Z])
[:xdigit:] [[:xdigit:]]  [0-9A-Fa-f]
COMMENT

  [[ "x"    =~ [[:space:]]*(a)?b ]] ; echo_array "${BASH_REMATCH[@]}"  #
  [[ "b"    =~ [[:space:]]*(a)?b ]] ; echo_array "${BASH_REMATCH[@]}"  # b       ""
  [[ "ab"   =~ [[:space:]]*(a)?b ]] ; echo_array "${BASH_REMATCH[@]}"  # ab      a
  [[ "  b"  =~ [[:space:]]*(a)?b ]] ; echo_array "${BASH_REMATCH[@]}"  # "  b"   ""
  [[ "  ab" =~ [[:space:]]*(a)?b ]] ; echo_array "${BASH_REMATCH[@]}"  # "  ab"  a

  # 'literal' "literal" は正規表現でなく文字列として扱われる
  # shellcheck disable=SC2076  # Remove quotes from right-hand side of =~ to match as a regex rather than literally
  {
    [[ ".?" =~  .?  ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=".")
    [[ ".?" =~ ".?" ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=".?")
    [[ ".?" =~ '.?' ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=".?")
  }
  # "$pattern" は正規表現でなく文字列として扱われる
  # shellcheck disable=SC2076  # Remove quotes from right-hand side of =~ to match as a regex rather than literally.
  {
    pattern='[[:space:]]*(a)?b'
    [[ "b"                 =~  [[:space:]]*(a)?b  ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="b" [1]="")
    [[ "b"                 =~  $pattern           ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="b" [1]="")
    [[ '[[:space:]]*(a)?b' =~ '[[:space:]]*(a)?b' ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="[[:space:]]*(a)?b")
    [[ '[[:space:]]*(a)?b' =~ "$pattern"          ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="[[:space:]]*(a)?b")
  }

  # character classes - $
  # [$chars] は展開される
  chars="a-z A-Z"
  [[ "foo fOO" =~ [$chars]+ ]]   ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo fOO") prefered
  [[ "foo fOO" =~ ["$chars"]+ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo fOO")

  # character classes - special character
  # space or >
  # 文字列にするかエスケープする必要がある
  [[ "A > Z" =~ [" >"]+ ]]   ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=" > ")
  [[ "A > Z" =~ [\ \>]+ ]]   ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=" > ")
  # $chars に入れても良い
  chars=" >"
  [[ "A > Z" =~ [$chars]+ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=" > ")
  # ^ $ は [] にできないっぽい
  [[ "foo" =~ ^foo$ ]]           ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo")
  [[ "foo" =~ [^]foo$ ]]         ; declare -p BASH_REMATCH  # bash: line 0: declare: BASH_REMATCH: not found  これはnegateになる
  [[ "foo" =~ [\^]foo$ ]]        ; declare -p BASH_REMATCH  # bash: line 0: declare: BASH_REMATCH: not found  これも？
  [[ "foo" =~ ["^"]foo$ ]]       ; declare -p BASH_REMATCH  # bash: line 0: declare: BASH_REMATCH: not found  これも？
  chars="^"
  [[ "foo" =~ [$chars]foo$ ]]    ; declare -p BASH_REMATCH  # bash: line 1: declare: BASH_REMATCH: not found  これも？
  [[ "foo" =~ ["$chars"]foo$ ]]  ; declare -p BASH_REMATCH  # bash: line 2: declare: BASH_REMATCH: not found  これも？
  [[ "foo" =~ [" $chars"]foo$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  [[ "foo" =~ [\\^]foo$ ]]       ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  [[ "foo" =~ [\\\^]foo$ ]]      ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  [[ "foo" =~ [a^]foo$ ]]        ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  # $
  [[ "foo" =~ ^foo[$] ]]      ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  [[ "foo" =~ ^foo[\$] ]]     ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  [[ "foo" =~ ^foo[\\$] ]]    ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  [[ "foo" =~ ^foo[\\\$] ]]   ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  [[ "foo" =~ ^foo[\\\$] ]]   ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  chars="$"; declare -p chars  # declare -- chars="\$"
  [[ "foo" =~ ^foo[$chars] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()

  # iterate / iteration / matchall / match all / all matches
  s="a_bb_ccc"
  while [[ $s =~ [a-z]+ ]]; do
    echo "match: ${BASH_REMATCH[0]}"  # a bb ccc
    s=${s/"${BASH_REMATCH[0]}"/}
  done
  echo "s: $s"  # __

  # non-greedy nongreedy un-greedy ungreedy .+? .*? はできないっぽい

  # word boundary \b
  s=$'foo'       ; [[ $s                    =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()  !!!!!
  s=$'foo '      ; [[ $s                    =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo " [1]="foo")
  s=$'foo\nbar'  ; [[ $s                    =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=$'foo\n' [1]="foo")
  s=$'foo \nbar' ; [[ $s                    =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo " [1]="foo")
  s=$'foox'      ; [[ $s                    =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox '     ; [[ $s                    =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox\nbar' ; [[ $s                    =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox \nbar'; [[ $s                    =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  # $ ||
  s=$'foo'       ; [[ $s =~ ^("foo")$ || $s =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo" [1]="foo")  OK
  s=$'foo '      ; [[ $s =~ ^("foo")$ || $s =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo " [1]="foo")
  s=$'foo\nbar'  ; [[ $s =~ ^("foo")$ || $s =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=$'foo\n' [1]="foo")
  s=$'foo \nbar' ; [[ $s =~ ^("foo")$ || $s =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo " [1]="foo")
  s=$'foox'      ; [[ $s =~ ^("foo")$ || $s =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox '     ; [[ $s =~ ^("foo")$ || $s =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox\nbar' ; [[ $s =~ ^("foo")$ || $s =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox \nbar'; [[ $s =~ ^("foo")$ || $s =~ ^("foo")[^0-9A-Za-z_] ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  # ([^\w].*)?$ でもできるが、何やってるか分からないので not recommended
  s=$'foo'       ; [[ $s =~ ^("foo")([^0-9A-Za-z_].*)?$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo" [1]="foo" [2]="")
  s=$'foo '      ; [[ $s =~ ^("foo")([^0-9A-Za-z_].*)?$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]="foo " [1]="foo" [2]=" ")
  s=$'foo\nbar'  ; [[ $s =~ ^("foo")([^0-9A-Za-z_].*)?$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=$'foo\nbar' [1]="foo" [2]=$'\nbar')
  s=$'foo \nbar' ; [[ $s =~ ^("foo")([^0-9A-Za-z_].*)?$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=([0]=$'foo \nbar' [1]="foo" [2]=$' \nbar')
  s=$'foox'      ; [[ $s =~ ^("foo")([^0-9A-Za-z_].*)?$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox '     ; [[ $s =~ ^("foo")([^0-9A-Za-z_].*)?$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox\nbar' ; [[ $s =~ ^("foo")([^0-9A-Za-z_].*)?$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
  s=$'foox \nbar'; [[ $s =~ ^("foo")([^0-9A-Za-z_].*)?$ ]] ; declare -p BASH_REMATCH  # declare -ar BASH_REMATCH=()
fi

( list )  # subshell
{ list; }

# coproc [NAME] command [redirections]
# coproc NAME { command; }
jobs
kill $(jobs -p)

coproc sleep_coproc { sleep 3; }
jobs  # coproc sleep_coproc { sleep 3; } &
declare -p sleep_coproc sleep_coproc_PID  # declare -a sleep_coproc=([0]="63" [1]="60")  declare -- sleep_coproc_PID="202953"
wait "$sleep_coproc_PID"
# 終了するとunsetされる
declare -p sleep_coproc sleep_coproc_PID  # sleep_coproc: not found  sleep_coproc_PID: not found

type args  # args is /home/wsh/bin/args
args "${sleep_coproc[@]}" "$sleep_coproc_PID"  # 63 60 202953

# write/read(cat)
coproc color_coproc { timeout 1 sed -Eu -e 's/^/\x1b[32m/' -e 's/$/\x1b[0m/'; }
echo "line1" >&"${color_coproc[1]}"
echo "line2" >&"${color_coproc[1]}"
cat <&"${color_coproc[0]}"  # line1 line2 (block; timeout 1 がないとデッドロック)

# read(cat &)/write できない
coproc color_coproc { sed -Eu -e 's/^/\x1b[32m/' -e 's/$/\x1b[0m/'; }
cat <&"${color_coproc[0]}" &  # bash: "${color_coproc[0]}": Bad file descriptor  https://stackoverflow.com/questions/10867153/background-process-redirect-to-coproc
echo "line1" >&"${color_coproc[1]}"
echo "line2" >&"${color_coproc[1]}"
cat <&"${color_coproc[0]}" &  # bash: "${color_coproc[0]}": Bad file descriptor
timeout 1 cat <&"${color_coproc[0]}"  # line1 line2  & なしなら行ける
exec {color_coproc[1]}>&-  # close write end

false && {
  # read fd: -u fd
  read -r -u "${color_coproc[0]}" line
}

# wait すると read/write 不可
coproc cp_echo { echo line1; echo line2; sleep 1; }
wait "${cp_echo_PID}"
# declare -p cp_echo cp_echo_PID  # bash: declare: cp_echo: not found  bash: declare: cp_echo_PID: not found
echo "line1" >&"${cp_echo[1]}"  # bash: "${cp_echo[1]}": Bad file descriptor
read -r -u "${cp_echo[0]}" line  # bash: read: : invalid file descriptor specification
cat <&"${cp_echo[0]}"  # bash: "${cp_echo[0]}": Bad file descriptor

# without NAME -> COPROC (これは使わない)
coproc sleep 3
jobs  # coproc COPROC sleep 3 &
declare -p COPROC COPROC_PID  # declare -a COPROC=([0]="63" [1]="60")  declare -- COPROC_PID="202953"

# 3.2.7 GNU Parallel

# 3.3 Shell Functions

# the DEBUG and RETURN traps
# trace attribute using the declare builtin (declare -t かな)
# -o functrace
# -errtrace
# TODO

# Consequently, a local variable at the current local scope is a variable declared using the local or declare builtins in the function that is currently executing.
# function 内の declare は local 扱いになる
if false; then
  fn () {
    declare var=1
    declare -g var_global=1  # [declare_g]
    echo "(fn) var: $var"
    echo "(fn) var_global: $var_global"
  }
  fn
  echo "(global) var: $var"  # (not set)
  echo "(global) var_global: $var_global"
fi

# localvar_unset TODO

# 3.4 Shell Parameters

if false; then
  # > If value is not given, the variable is assigned the null string.
  name=          # null string
  name2=""       # null string 多分
  declare name3  # ?
  declare -p name name2 name3
  #declare -- name=""
  #declare -- name2=""
  #declare -- name3
  unset name name2 name3
  # declare -p name name2 name3
  #/home/wsh/sh/bash_man.bash: line 195: declare: name: not found
  #/home/wsh/sh/bash_man.bash: line 195: declare: name2: not found
  #/home/wsh/sh/bash_man.bash: line 195: declare: name3: not found

  log_info "> integer attribute set, then value is evaluated as an arithmetic expression"
  declare s
  declare -i i
  s=1+1  # declare -- s="1+1"
  i=1+1  # declare -i i="2"     i=$((1+1)) の方が好み
  declare -p s i
  unset s i

  log_info "> Assignment statements may also appear as arguments to the alias, declare, typeset, export, readonly, and local builtin commands (declaration commands)."
  # shellcheck disable=SC2116  # Useless echo? Instead of 'cmd $(echo foo)', just use 'cmd foo'
  alias f="$(echo ls)"
  alias f  # alias f='ls'
  # TODO: unset f

  log_info "+="
  s="a"
  a=("a" "b")
  s+="b"     # s=([0]="ab" [1]="c")
  s+=("c")   # s="ab"
  a+="c"     # a=([0]="ac" [1]="b")
  a[1]+="d"  # [1]="bd"
  a+=("e")   # [2]="e"
  declare -p s a
  unset s a

  log_info "nameref"
  set -- foo
  # local -n nameref
  declare -n nameref_arg1="$1"  # declare -n nameref_arg1="foo"
  declare -n nameref_var="var"  # declare -n nameref_var="var"
  declare -p nameref_arg1 nameref_var
  foo=x
  var=x
  echo "$nameref_arg1 $nameref_var"  # x x
  unset nameref_arg1 nameref_var foo var

  log_info "> the control variable in a for loop has the nameref attribute"
  declare -n control_variable
  x="1"
  y="2"
  for control_variable in "x" "y"; do
    echo "$control_variable"  # 1, 2
  done
  unset x y
fi

# 3.4.1 Positional Parameters

if false; then
  set -- a b c d e f g h i j k l m n o p q r s t u v w x y z
  # shellcheck disable=SC1037  # Braces are required for positionals over 9, e.g. ${10}
  echo "bad: $10"    # a0
  echo "ok:  ${10}"  # j
fi

# 3.4.2 Special Parameters

if false; then
  false "$*"  # ($*) Expands to the positional parameters, starting from one. When the expansion is not within double quotes, each positional parameter expands to a separate word. In contexts where it is performed, those words are subject to further word splitting and filename expansion. When the expansion occurs within double quotes, it expands to a single word with the value of each parameter separated by the first character of the IFS special variable. That is, "$*" is equivalent to "$1c$2c…", where c is the first character of the value of the IFS variable. If IFS is unset, the parameters are separated by spaces. If IFS is null, the parameters are joined without intervening separators.
  false "$@"  # ($@) Expands to the positional parameters, starting from one. In contexts where word splitting is performed, this expands each positional parameter to a separate word; if not within double quotes, these words are subject to word splitting. In contexts where word splitting is not performed, this expands to a single word with each positional parameter separated by a space. When the expansion occurs within double quotes, and word splitting is performed, each parameter expands to a separate word. That is, "$@" is equivalent to "$1" "$2" …. If the double-quoted expansion occurs within a word, the expansion of the first parameter is joined with the beginning part of the original word, and the expansion of the last parameter is joined with the last part of the original word. When there are no positional parameters, "$@" and $@ expand to nothing (i.e., they are removed).
  false "$#"  # ($#) Expands to the number of positional parameters in decimal.
  false "$?"  # ($?) Expands to the exit status of the most recently executed foreground pipeline.
  false "$-"  # ($-, a hyphen.) Expands to the current option flags as specified upon invocation, by the set builtin command, or those set by the shell itself (such as the -i option).
  false "$$"  # ($$) Expands to the process ID of the shell. In a subshell, it expands to the process ID of the invoking shell, not the subshell.
  false "$!"  # ($!) Expands to the process ID of the job most recently placed into the background, whether executed as an asynchronous command or using the bg builtin (see Job Control Builtins).
  false "$0"  # ($0) Expands to the name of the shell or shell script. This is set at shell initialization. If Bash is invoked with a file of commands (see Shell Scripts), $0 is set to the name of that file. If Bash is started with the -c option (see Invoking Bash), then $0 is set to the first argument after the string to be executed, if one is present. Otherwise, it is set to the filename used to invoke Bash, as given by argument zero.

  echo "$-"  # hB
  set -x
  echo "$-"  # hxB

  echo "$0"
  # bash FILE -> FILE
  # bash -c "..." arg0 arg1 arg2 -> arg0
fi

# 3.5 Shell Expansions

# 3.5.1 Brace Expansion

# sequence expression {x..y[..incr]}
if false; then
  echo_array {1..3}  # 1 2 3
  echo_array {3..1}  # 3 2 1
  echo_array {0..10..2}  # 0 2 4 6 8 10
  echo_array {10..0..2}  # 10 8 6 4 2 0
  echo_array {10..0..-2}  # same
  echo_array {01..100}  # 001 002 ... 009 010 011 ... 100
  echo_array {001..100}  # same, prefer
  echo_array {a..c}  # a b c
  echo_array {a..c..2}  # a c
  echo_array {Z..a}  # Z [ SPACE ] ^ _ ` a
  echo_array {_..a}  # (not expanded) {_..a}
  echo_array {a..Z}  # (not expanded) {_..a}
  # 文字は [a-zA-Z] だけかな？
fi

# 3.5.2 Tilde Expansion

# 3.5.3 Shell Parameter Expansion

# [](file:///home/wsh/qc/bash/subst.c)
# /* ${[#][!]name[[:][^[^]][,[,]]#[#]%[%]-=?+[word][:e1[:e2]]]} */
# static WORD_DESC *
# parameter_brace_expand (string, indexp, quoted, pflags, quoted_dollar_atp, contains_dollar_at)
# この関数だけで700行くらいある…

if false; then
  # # parameter: a shell parameter as described above (see Shell Parameters) or an array reference (see Arrays)
  # 3.4 Shell Parameters
  # 6.7 Arrays
  false && ${parameter}

  log_info "\${!parameter} indirection"
  # parameter is not a nameref
  tmp="foo bar"
  parameter="tmp"
  echo "${!parameter}"  # -> "${tmp}" -> "foo bar"
  # exception (described below):
  # shellcheck disable=SC2145  # Argument mixes string and array. Use * or separate argument
  false "${!prefix*} ${!name[@]}"
  # nth argument
  set -- a b c && n=1             && echo "${!n}"        # [1]   a
  set -- a b c && n=1 && ((n++))  && echo "${!n}"        # [1+1] b  # n=1 && echo "${!n+1}"  # 1 (bad)
  set -- a b c && n=1 && ((n+=2)) && echo "${!n}"        # [1+2] c  # n=1 && echo "${!n+2}"  # 2 (bad)
  set -- a b c && n=1             && echo "${@:$n:1}"    # [1]   a
  set -- a b c && n=1             && echo "${@:$n+1:1}"  # [1+1] b
  set -- a b c && n=1             && echo "${@:$n+2:1}"  # [1+2] c
  #
  set -- a b c && n=3             && echo "${!n}"        # [3]   c
  set -- a b c && n=3 && ((n--))  && echo "${!n}"        # [3-1] b  # n=3 && echo "${!n-1}"  # c (bad)
  set -- a b c && n=3 && ((n-=2)) && echo "${!n}"        # [3-2] a  # n=3 && echo "${!n-2}"  # c (bad)
  set -- a b c && n=3             && echo "${@:$n:1}"    # [3]   c
  set -- a b c && n=3             && echo "${@:$n-1:1}"  # [3-1] b
  set -- a b c && n=3             && echo "${@:$n-2:1}"  # [3-2] a
fi

if false; then
  # ${parameter:-word}  # If parameter is unset or null, the expansion of word is substituted. Otherwise, the value of parameter is substituted.
  # ${parameter:=word}  # If parameter is unset or null, the expansion of word is assigned to parameter. The value of parameter is then substituted. Positional parameters and special parameters may not be assigned to in this way.
  # ${parameter:?word}  # If parameter is null or unset, the expansion of word (or a message to that effect if word is not present) is written to the standard error and the shell, if it is not interactive, exits. Otherwise, the value of parameter is substituted.
  # ${parameter:+word}  # If parameter is null or unset, nothing is substituted, otherwise the expansion of word is substituted.

  # ${parameter:-word}  # $parameter が空かunsetなら word
  # ${parameter:=word}  # $parameter が空かunsetなら parameter=word; word
  # ${parameter:?word}  # $parameter が空かunsetなら エラーメッセージ "word" を出して exit 1
  # ${parameter:+word}  # $parameter が空かunsetなら 空; set -u で有効

  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  log_info '"${parameter:-word}"'
  unset parameter      #        declare -p parameter -> /home/wsh/sh/bash_man.bash: line 42: declare: parameter: not found
  # declare parameter  # null?  declare -p parameter -> declare -- parameter
  # parameter=         # null   declare -p parameter -> declare -- parameter=""  > If value is not given, the variable is assigned the null string.
  # parameter=""       # null?  declare -p parameter -> declare -- parameter=""
  echo "${parameter:-word}"  # word
  parameter="x"              #  declare -p parameter -> declare -- parameter="x"
  echo "${parameter:-word}"  # x

  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  log_info '"${parameter:=word}"'
  unset parameter
  echo "${parameter:=word}"  # word
  declare -p parameter  # "word"
  # Positional parameters and special parameters may not be assigned to in this way.
  false && echo "${1:=word}"  # /home/wsh/sh/bash_man.bash: line 42: $1: cannot assign in this way

  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  log_info '"${parameter:?word}"'
  unset parameter
  false && echo "${parameter:?word}"  # /home/wsh/sh/bash_man.bash: line 42: parameter: word  exit 1

  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  log_info '"${parameter:+word}"'
  unset parameter
  set -u
  echo ">${parameter:+word}<"  # ><
  false && echo ">$parameter<"  # /home/wsh/sh/bash_man.bash: line 42: parameter: unbound variable  exit 1
  set +u

  # > the expansion of word
  log_info "the expansion of word"
  unset parameter
  echo "${parameter:-$(tr "[:lower:]" "[:upper:]" <<< "foo")}"  # FOO
  echo "${parameter:=$(tr "[:lower:]" "[:upper:]" <<< "foo")}"
  echo "${parameter:?$(tr "[:lower:]" "[:upper:]" <<< "foo")}"
  echo "${parameter:+$(tr "[:lower:]" "[:upper:]" <<< "foo")}"

  log_info "\${parameter:offset:length} Substring Expansion"
  # This is referred to as Substring Expansion. ...
  # ${parameter:offset}
  # ${parameter:offset:length}
  parameter="0123456789"
  log_debug "${parameter:1}"    # 123456789
  log_debug "${parameter:1:3}"  # 123
  log_debug "${parameter::3}"   # 012  "${parameter:0:3}" の方が好み
  # > length and offset are arithmetic expressions (see Shell Arithmetic)
  log_debug "${parameter:0+1:1+2}" # 123
  # shellcheck disable=SC2116  # Useless echo? Instead of 'cmd $(echo foo)', just use 'cmd foo'
  log_debug "${parameter:$(echo 1):1+2}" # 123

  # slice substring subarray
  string=01234567890abcdefgh
  echo "\${string:7}              __ ${string:7}"         # 7890abcdefgh
  echo "\${string:7:0}            __ ${string:7:0}"       # (empty) (length 0)
  echo "\${string:7:2}            __ ${string:7:2}"       # 78
  echo "\${string:7:-2}           __ ${string:7:-2}"      # 7890abcdef (<- "gh")
  echo "\${string: -7}            __ ${string: -7}"       # bcdefgh
  echo "\${string: -7:0}          __ ${string: -7:0}"     #
  echo "\${string: -7:2}          __ ${string: -7:2}"     # bc
  echo "\${string: -7:-2}         __ ${string: -7:-2}"    # bcdef
  echo "\${string: -7} (not work) __ ${string: -7}"       # > confused with the ‘:-’ expansion
  set -- 01234567890abcdefgh
  echo "\${1:7}                   __ ${1:7}"              # 7890abcdefgh
  echo "\${1:7:0}                 __ ${1:7:0}"            #
  echo "\${1:7:2}                 __ ${1:7:2}"            # 78
  echo "\${1:7:-2}                __ ${1:7:-2}"           # 7890abcdef
  echo "\${1: -7}                 __ ${1: -7}"            # bcdefgh
  echo "\${1: -7:0}               __ ${1: -7:0}"          #
  echo "\${1: -7:2}               __ ${1: -7:2}"          # bc
  echo "\${1: -7:-2}              __ ${1: -7:-2}"         # bcdef
  array[0]=01234567890abcdefgh
  echo "\${array[0]:7}            __ ${array[0]:7}"       # 7890abcdefgh
  echo "\${array[0]:7:0}          __ ${array[0]:7:0}"     #
  echo "\${array[0]:7:2}          __ ${array[0]:7:2}"     # 78
  echo "\${array[0]:7:-2}         __ ${array[0]:7:-2}"    # 7890abcdef
  echo "\${array[0]: -7}          __ ${array[0]: -7}"     # bcdefgh
  echo "\${array[0]: -7:0}        __ ${array[0]: -7:0}"   #
  echo "\${array[0]: -7:2}        __ ${array[0]: -7:2}"   # bc
  echo "\${array[0]: -7:-2}       __ ${array[0]: -7:-2}"  # bcdef

  log_info "> If parameter is ‘@’ or ‘*’,"
  set -- 1 2 3 4 5 6 7 8 9 0 a b c d e f g h
  echo "\${@:7}     ${*:7}    " # 7 8 9 0 a b c d e f g h
  echo "\${@:7:0}   ${*:7:0}  " #
  echo "\${@:7:2}   ${*:7:2}  " # 7 8
  false && echo "\${@:7:-2}  ${*:7:-2} " # bash: -2: substring expression < 0
  echo "\${@: -7:2} ${*: -7:2}" # b c
  echo "\${@:0}     ${*:0}    " # ./bash 1 2 3 4 5 6 7 8 9 0 a b c d e f g h
  echo "\${@:0:2}   ${*:0:2}  " # ./bash 1
  echo "\${@: -7:0} ${*: -7:0}" #

  log_info "indexed array"
  array=(0 1 2 3 4 5 6 7 8 9 0 a b c d e f g h)
  echo "\${array[@]:7}      ${array[*]:7}     " # 7 8 9 0 a b c d e f g h
  echo "\${array[@]:7:2}    ${array[*]:7:2}   " # 7 8
  echo "\${array[@]: -7:2}  ${array[*]: -7:2} " # b c
  false && echo "\${array[@]: -7:-2} ${array[*]: -7:-2}" # bash: -2: substring expression < 0
  echo "\${array[@]:0}      ${array[*]:0}     " # 0 1 2 3 4 5 6 7 8 9 0 a b c d e f g h
  echo "\${array[@]:0:2}    ${array[*]:0:2}   " # 0 1
  echo "\${array[@]: -7:0}  ${array[*]: -7:0} " #
  echo "\${array[@]: -7:99} ${array[*]: -7:99}" # b c d e f g h

  log_info "\${!prefix*} \${!prefix@}"
  # Expands to the names of variables whose names begin with prefix, separated by the first character of the IFS special variable. When ‘@’ is used and the expansion appears within double quotes, each variable name expands to a separate word.
  var1="a"
  var2="b"
  log_debug "${!var*}"  # var1 var2
  log_debug "${!var@}"  # var1 var2
  unest var1 var2

  log_info "\${!name[@]} \${!name[*]}"
  # If name is an array variable, expands to the list of array indices (keys) assigned in name. If name is not an array, expands to 0 if name is set and null otherwise. When ‘@’ is used and the expansion appears within double quotes, each key expands to a separate word.
  arr=("a" "b")
  log_debug "${!arr[@]}"  # 0 1
  log_debug "${!arr[*]}"  # 0 1
  unset arr

  log_info "\${#parameter}"
  # The length in characters of the expanded value of parameter is substituted. If parameter is ‘*’ or ‘@’, the value substituted is the number of positional parameters. If parameter is an array name subscripted by ‘*’ or ‘@’, the value substituted is the number of elements in the array. If parameter is an indexed array name subscripted by a negative number, that number is interpreted as relative to one greater than the maximum index of parameter, so negative indices count back from the end of the array, and an index of -1 references the last element.
  s="foo"
  set -- a b
  log_debug "${#s}"  # 3 ("foo".length)
  log_debug "${#*}"  # 2
  log_debug "${#@}"  # 2
  unset s
  arr=("xx" "yyyy")
  log_debug "${#arr[@]}"   # 2
  log_debug "${#arr[*]}"   # 2
  log_debug "${#arr}"      # 2 "xx".length
  log_debug "${#arr[0]}"   # 2 "xx".length
  log_debug "${#arr[1]}"   # 4 "yyyy".length
  log_debug "${#arr[-1]}"  # 4 "yyyy".length
  log_debug "${#arr[-2]}"  # 2 "xx".length

  log_info "\${parameter#word} \${parameter##word} \${parameter%word} \${parameter%%word}"
  # \{\w+#.+?\}
  # \{\w+%.+?\}
  parameter="a/b/c"
  echo "${parameter#a}"    #  /b/c  removes: ^a
  echo "${parameter#*/}"   #   b/c  removes: ^.*?/ (ungreedy)
  echo "${parameter##*/}"  #     c  removes: ^.*/ (greedy)
  echo "${parameter%/*}"   # a/b    removes: /.*?$ (ungreedy)
  echo "${parameter%%/*}"  # a      removes: /.*$ (greedy)
  echo "${parameter%c}"    # a/b/   removes: c$
  # parent directory: "${f%/*}"
  # 2025-01-01 Wed TODO: https://github.com/ko1nksm/readlinkf
  f=$(readlink -f "${BASH_SOURCE[0]}")  # ref: https://github.com/bats-core/bats-core/blob/v1.10.0/bin/bats#L52
  f="/tmp/foo.bar.baz/a.b.sh"
  echo "$f"              # /tmp/foo.bar.baz/a.b.sh
  echo "${f%/*}"         # /tmp/foo.bar.baz
  echo "${f%/*/*}"       # /tmp
  echo "${f%/*/*/*}"     #
  echo "${f%/*/*/*/*}"   # /tmp/foo.bar.baz/a.b.sh
  # remove extension
  f="/tmp/foo.bar.baz/a.b.sh"
  echo "$f"              # /tmp/foo.bar.baz/a.b.sh
  echo "${f%.*}"         # /tmp/foo.bar.baz/a.b
  # basename, remove extension
  f="/tmp/foo.bar.baz/a.b.sh"
  (tmp="${f##*/}"; echo "${tmp%.*}")  # a.b
  # both % and #
  {
    parameter="aaa.%#%.bbb.%#%.ccc"
    # 同時にはできない
    echo "${parameter#aaa.%#%.}"  # removes ^aaa.%#%.
    echo "${parameter%.%#%.ccc}"  # removes .%#%.ccc$
    # tmp する
    tmp="${parameter#aaa.%#%.}"  # removes ^aaa.%#%.
    echo "${tmp%.%#%.ccc}"       # removes .%#%.ccc$
  }
  # remove preceding spaces
  foo="  foo  " && while [[ $foo != "${foo# }" ]]; do foo="${foo# }"; done && echo "|$foo|"  # |foo  |
  # remove trailing spaces
  foo="  foo  " && while [[ $foo != "${foo% }" ]]; do foo="${foo% }"; done && echo "|$foo|"  # |  foo|
  # remove preceding/trailing spaces
  foo="  foo  " && while [[ $foo != "${foo# }" ]]; do foo="${foo# }"; done && while [[ $foo != "${foo% }" ]]; do foo="${foo% }"; done && echo "|$foo|"  # |foo|
  # remove trailing spaces (bad)
  foo="  foo  " && echo "|${foo% }|"            # |  foo | 1個しか消せない
  foo="  foo  " && echo "|${foo%[[:space:]]}|"  # |  foo | 1個しか消せない

  # remove trailing slashes
  false && {
    s=""             && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s=""
    s="/"            && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s=""  (!)
    s="//"           && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s=""  (!)
    s="/etc"         && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/etc"
    s="/etc/"        && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/etc"
    s="/etc//"       && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/etc"
    s="/usr/local"   && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/usr/local"
    s="/usr/local/"  && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/usr/local"
    s="/usr/local//" && while [[ $s != "${s%/}" ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/usr/local"
    # leave "/"
    s=""             && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s=""
    s="/"            && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/"  (!)
    s="//"           && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/"  (!)
    s="/etc"         && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/etc"
    s="/etc/"        && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/etc"
    s="/etc//"       && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/etc"
    s="/usr/local"   && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/usr/local"
    s="/usr/local/"  && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/usr/local"
    s="/usr/local//" && while [[ $s != "${s%/}" && $s != / ]]; do s="${s%/}"; done && declare -p s  # declare -- s="/usr/local"
  }

  # set
  set -- "a/b/c"
  echo "${1#a}"    #  /b/c  removes: ^a
  echo "${1#*/}"   #   b/c  removes: ^.*?/ (ungreedy)
  echo "${1##*/}"  #     c  removes: ^.*/ (greedy)
  echo "${1%/*}"   # a/b    removes: /.*?$ (ungreedy)
  echo "${1%%/*}"  # a      removes: /.*$ (greedy)
  echo "${1%c}"    # a/b/   removes: c$
  # split
  s="aaa   bbb"
  echo "|${s%% *}|"  # |aaa|
  echo "|${s##* }|"  #        |bbb|
  echo "|${s% *}|"   # |aaa  |
  echo "|${s#* }|"   #      |  bbb|

  log_info "\${parameter/pattern/string}"
  log_info "\${parameter//pattern/string}"
  log_info "\${parameter/#pattern/string}"
  log_info "\${parameter/%pattern/string}"
  # replace (sed s///)
  log_debug "${parameter/pattern/string}    "
  log_debug "${parameter//pattern/string}   "  # /g       | all matches of pattern are replaced with string
  log_debug "${parameter/#pattern/string}   "  # ^pattern | at the beginning of
  log_debug "${parameter/%pattern/string}   "  # pattern$ | at the end of
  log_debug "${parameter/pattern/"$(date)"} "
  log_debug "${parameter/pattern/__ & __}   "  # TODO: bash 5.2 patsub_replacement -> __ pattern __
  parameter=$' foo \n bar \n baz \n ' ; echo -n "${parameter//[^$'\r\n']/""}"  # emptify (preserves only \r and \n)
  parameter=$' foo bar \n baz \n ' ; echo -n "${parameter//[^[:space:]]/"x"}"  # xxx
  # nocasematch shell option ... TODO
  # If parameter is ‘@’ or ‘*’, ... TODO

  log_info "TODO below"

  false ${parameter^pattern}
  false ${parameter^^pattern}
  false ${parameter,pattern}
  false ${parameter,,pattern}

  false ${parameter@operator}  # The expansion is either a transformation of the value of parameter or information about parameter itself, depending on the value of operator. Each operator is a single letter:
  false ${parameter@U} # The expansion is a string that is the value of parameter with lowercase alphabetic characters converted to uppercase.
  false ${parameter@u} # The expansion is a string that is the value of parameter with the first character converted to uppercase, if it is alphabetic.
  false ${parameter@L} # The expansion is a string that is the value of parameter with uppercase alphabetic characters converted to lowercase.
  false ${parameter@Q} # The expansion is a string that is the value of parameter quoted in a format that can be reused as input.
    # find also: %q
  false ${parameter@E} # The expansion is a string that is the value of parameter with backslash escape sequences expanded as with the $'…' quoting mechanism.
  false ${parameter@P} # The expansion is a string that is the result of expanding the value of parameter as if it were a prompt string (see Controlling the Prompt).
  false ${parameter@A} # The expansion is a string in the form of an assignment statement or declare command that, if evaluated, will recreate parameter with its attributes and value.
  false ${parameter@K} # Produces a possibly-quoted version of the value of parameter, except that it prints the values of indexed and associative arrays as a sequence of quoted key-value pairs (see Arrays).
  false ${parameter@a} # The expansion is a string consisting of flag values representing parameter’s attributes.
  false ${parameter@k} # Like the ‘K’ transformation, but expands the keys and values of indexed and associative arrays to separate words after word splitting.
fi

# ${!name[@]}
if false; then
arr=(
'a b' # comment
# comment
'c d'
)
for i in "${!arr[@]}"; do
    echo "$i: ${arr[$i]}"
done
fi
# 0: a b
# 1: c d

# 3.5.4 Command Substitution

# 3.5.5 Arithmetic Expansion

# $(( expression ))

# 3.5.6 Process Substitution

# <(list)
# >(list)

# 3.5.7 Word Splitting
# 3.5.8 Filename Expansion
# 3.5.8.1 Pattern Matching
# 3.5.9 Quote Removal

# 3.6 Redirections

if false; then
  # > {varname} ... a file descriptor greater than 10

  touch /tmp/bash_varname0

  exec {varname0}</tmp/bash_varname0 {varname1}>/tmp/bash_varname1 {varname2}<>/tmp/bash_varname2
  echo "varname0:$varname0 varname1:$varname1 varname2:$varname2"  # 10 11 12
  lsof -nP -p "$BASHPID"
  #COMMAND    PID USER   FD   TYPE DEVICE SIZE/OFF     NODE NAME
  #bash    401318  wsh   10r   REG  253,1        0 31101440 /tmp/bash_varname0
  #bash    401318  wsh   11w   REG  253,1        0 31101443 /tmp/bash_varname1
  #bash    401318  wsh   12u   REG  253,1        0 31101444 /tmp/bash_varname2

  # varnable0 varnable1 varnable2: unset
  # fd 10 11 12: unchanged
  false && bash -c 'echo "varname0:$varname0 varname1:$varname1 varname2:$varname2"; lsof -nP -p "$BASHPID"'

  exec {varname0}<&- {varname1}<&- {varname2}<&-  # close fd 10 11 12; varname0 varname1 varname2 は 10 11 12 のまま
  false && lsof -nP -p "$BASHPID"

  # <&- と >&- はどっちでも良い
  # https://unix.stackexchange.com/questions/131801/closing-a-file-descriptor-vs
  exec {varname0}</tmp/bash_varname0 {varname1}>/tmp/bash_varname1 {varname2}<>/tmp/bash_varname2
  exec {varname0}>&- {varname1}>&- {varname2}>&-  # close fd 10 11 12; varname0 varname1 varname2 は 10 11 12 のまま

  # https://github.com/bminor/bash/blob/master/CHANGES
  # bash 5.2
  # varredir_close で {} を抜けた後に fd が close されるんだと思う
  if false; then
    # shopt -o varredir_close
    {
      echo "varname0:$varname0 varname1:$varname1 varname2:$varname2"  # 10 11 12
      lsof -nP -p "$BASHPID"
    } {varname0}</tmp/bash_varname0 {varname1}>/tmp/bash_varname1 {varname2}<>/tmp/bash_varname2
    # still exists
    echo "varname0:$varname0 varname1:$varname1 varname2:$varname2"  # 10 11 12
    lsof -nP -p "$BASHPID"
  fi

  # Bash handles several filenames specially
  # /dev/fd/fd
  # /dev/stdin
  # /dev/stdout
  # /dev/stderr
  # /dev/tcp/host/port  note: /dev/tcp は存在しない
  # /dev/udp/host/port  note: /dev/udp は存在しない
  exec 3<>/dev/tcp/example.com/80
  false && lsof -nP -p "$BASHPID"
  #bash    412651  wsh    3u  IPv6 3084994      0t0      TCP [2001:240:1bc:8005:b849:f0e6:cc87:245a]:55658->[2606:2800:220:1:248:1893:25c8:1946]:80 (ESTABLISHED)
  echo "GET /" >&3
  echo "" >&3
  cat <&3  # HTTP/1.0 404 Not Found ...
  false && lsof -nP -p "$BASHPID"
  #bash    412651  wsh    3u  IPv6 3097808      0t0      TCP [2001:240:1bc:8005:b849:f0e6:cc87:245a]:55660->[2606:2800:220:1:248:1893:25c8:1946]:80 (CLOSE_WAIT)
  exec 3>&-
fi

# 3.6.1 Redirecting Input

# 3.6.2 Redirecting Output

# bash extension (Appendix B Major Differences From The Bourne Shell)
# noclobber >|
# set -C

# 3.6.3 Appending Redirected Output

# 3.6.4 Redirecting Standard Output and Standard Error

# bash extension (Appendix B Major Differences From The Bourne Shell)
if false; then
  # all same:
  tail -F /tmp/bash.log &
  lsof -nP -p "$BASHPID" >/tmp/bash.log 2>&1
  lsof -nP -p "$BASHPID" >/tmp/bash.log 2>/tmp/bash.log
  lsof -nP -p "$BASHPID" &> /tmp/bash.log
  lsof -nP -p "$BASHPID" >& /tmp/bash.log
  # > Of the two forms, the first is preferred
  # なので &> を使う
fi

# 3.6.5 Appending Standard Output and Standard Error

if false; then
  tail -F /tmp/bash.log &
  # append なので tail: /tmp/bash.log: file truncated が出ない
  lsof -nP -p "$BASHPID" >>/tmp/bash.log 2>&1
  lsof -nP -p "$BASHPID" &>>/tmp/bash.log
fi

# 3.6.6 Here Documents

# [n]<<[-]word
#         here-document
# delimiter

# 3.6.7 Here Strings

# bash extension (Appendix B Major Differences From The Bourne Shell)
# [n]<<< word

# 3.6.8 Duplicating File Descriptors

# bash extension (Appendix B Major Differences From The Bourne Shell)
# [n]<&word
# [n]>&word

# 3.6.9 Moving File Descriptors

# [n]<&digit-
# [n]>&digit-

# 3.6.10 Opening File Descriptors for Reading and Writing

# bash extension (Appendix B Major Differences From The Bourne Shell)
# [n]<>word

# 3.7 Executing Commands
# 3.7.1 Simple Command Expansion
# 3.7.2 Command Search and Execution
# 3.7.3 Command Execution Environment
# 3.7.4 Environment
# 3.7.5 Exit Status
# 3.7.6 Signals
# 3.8 Shell Scripts

# @end:man_3
fi  # if false

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 4 Shell Builtin Commands

if false; then
# @beg:man_4

# 4.1 Bourne Shell Builtins

# exec
# If no command is specified, redirections may be used to affect the current shell environment.
if false; then
exec  # noop
exec 3>/tmp/foo
echo foo >&3
fi

# test
# [
# see 6.4 Bash Conditional Expressions

# 4.2 Bash Builtin Commands
# $x(`//div[@id="Bash-Builtins"]/dl/dt/span/code`).map(x => x.textContent)

# alias
# bind
# builtin

# caller
# see: BASH_LINENO BASH_SOURCE FUNCNAME LINENO

# command

# declare
if false; then
  # declare     # list
  # declare -p  # list
  # declare -p name

  # TODO: 違いが分からないのでdebug: [](file:///home/wsh/qc/bash/build/builtins/declare.c)
  # declare -f   # list functions
  # declare -fp  # list functions
  # declare -F   # list functions oneline
  # declare -Fp  # list functions oneline
  # If the extdebug shell option is enabled... TODO

  # declare -g  # global [declare_g]
  # declare -I  # inherit TODO

  declare -a indexed_array
  declare -A associative_array
  declare -i integer=foo  # -> 0
  integer=bar  # 0
  ((integer++))  # -> 1
  # declare -f  Use function names only.
  declare -l lower_case=FOO  # foo
  declare -n nameref=integer  # 1
  declare -r readonly_
  # declare -t  Give each name the trace attribute. Traced functions inherit the DEBUG and RETURN traps from the calling shell. The trace attribute has no special meaning for variables.
  declare -u upper_case=foo  # FOO
  declare -x export_

  # + でturns off the attribute
  declare +l lower_case

  indexed_array+=(a b c)
  # declare     # indexed_array=([0]="a" [1]="b" [2]="c")
  # declare -p  # declare -a indexed_array=([0]="a" [1]="b" [2]="c")

  # -g は見れない？
  fn() {
    local assign_local=1
    assign_global=1
    declare declare_local=1
    declare -g declare_global=1

    declare
    #assign_global=1
    #assign_local=1
    #declare_global=1
    #declare_local=1

    declare -p assign_local assign_global declare_local declare_global
    #declare -- assign_local="1"
    #declare -- assign_global="1"
    #declare -- declare_local="1"
    #declare -- declare_global="1"
  }
  # fn
fi

# echo
# enable
# help
# let
# local
# logout

# mapfile
if false; then
  shopt -s lastpipe && set +m  # set +m for interactive shell
  echo $'1\n2' | mapfile
  declare -p MAPFILE
  #declare -a MAPFILE=([0]=$'1\n' [1]=$'2\n')
  # without shopt -s lastpipe:
  #/home/wsh/sh/bash_man.bash: line 779: declare: MAPFILE: not found
  # interactive: without shopt -s lastpipe and/or set +m:
  #bash: declare: MAPFILE: not found
fi
# iterate over multi lines
mapfile -t lines < <(echo "$lines")
for line in "${lines[@]}"; do echo "$line"; done

# printf

# read
if false; then
  declare line  # local line
  echo -n $' \ foo \ \n bar \n ' | while IFS= read -r line; do  # `IFS=`: prevent removing leading/preceding spaces
    declare -p line
  done
  #declare -- line=" \\ foo \\ "
  #declare -- line=" bar "
  # experiment:
  echo -n $' \ foo \ \n bar \n ' | while IFS= read -r line; do declare -p line; done  # declare -- line=" \\ foo \\ "  declare -- line=" bar "  # `IFS=`: prevent removing leading/preceding spaces
  echo -n $' \ foo \ \n bar \n ' | while IFS= read    line; do declare -p line; done  # declare -- line="  foo  "      declare -- line=" bar "  # `IFS=`: prevent removing leading/preceding spaces
  echo -n $' \ foo \ \n bar \n ' | while      read -r line; do declare -p line; done  # declare -- line="\\ foo \\"    declare -- line="bar"
  echo -n $' \ foo \ \n bar \n ' | while      read    line; do declare -p line; done  # declare -- line=" foo"         declare -- line="bar"

  # multiline
  shopt -s lastpipe && set +m  # set +m for interactive shell
  declare txt  # local txt
  echo -n $' \ foo \ \n bar \n ' | IFS= read -d "" -r txt || true; declare -p txt  # 1 declare -- txt=" \\ foo \\ NL bar NL "  # `IFS=`: prevent removing leading/preceding spaces; `|| true`: -d "" always returns 1
  # experiment:
  echo -n $' \ foo \ \n bar \n ' | IFS= read -d "" -r txt; echo $? declare -p txt  # 1 declare -- txt=" \\ foo \\ NL bar NL "  # `IFS=`: prevent removing leading/preceding spaces
  echo -n $' \ foo \ \n bar \n ' | IFS= read -d ""    txt; echo $? declare -p txt  # 1 declare -- txt="  foo  NL bar NL "      # `IFS=`: prevent removing leading/preceding spaces
  echo -n $' \ foo \ \n bar \n ' |      read -d "" -r txt; echo $? declare -p txt  # 1 declare -- txt="\\ foo \\ NL bar"
  echo -n $' \ foo \ \n bar \n ' |      read -d ""    txt; echo $? declare -p txt  # 1 declare -- txt=" foo  NL bar"
  # -d が無いと最初の行だけ
  echo -n $' \ foo \ \n bar \n ' | IFS= read       -r txt; echo $? declare -p txt  # 0 declare -- txt=" \\ foo \\ "  #`IFS=`: prevent removing leading/preceding spaces
  echo -n $' \ foo \ \n bar \n ' | IFS= read          txt; echo $? declare -p txt  # 0 declare -- txt="  foo  "      #`IFS=`: prevent removing leading/preceding spaces
  echo -n $' \ foo \ \n bar \n ' |      read       -r txt; echo $? declare -p txt  # 0 declare -- txt="\\ foo \\"
  echo -n $' \ foo \ \n bar \n ' |      read          txt; echo $? declare -p txt  # 0 declare -- txt=" foo"
fi

# readarray
# source
# type

# 4.3 Modifying Shell Behavior

# 4.3.1 The Set Builtin

if false; then
  set

  set -o | grep on
  bash -c "set -o | grep on"
  #braceexpand    	on         -B
  #emacs          	on             only in interactive shell
  #hashall        	on         -h
  #histexpand     	on         -H  only in interactive shell
  #history        	on             only in interactive shell
  #interactive-comments	on         undocumented?
  #monitor        	on         -m  only in interactive shell

  echo $-            # himBHs | h hashall, i (bash option: interactive), m monitor, B braceexpand, H histexpand, s (bash option: standard input)
  bash -c 'echo $-'  # hBc    | h hashall,                                          B braceexpand, c (bash option: command),

  # -a allexport                      == Each variable or function that is created or modified is given the export attribute and marked for export to the environment of subsequent commands.
  # -b notify                         == Cause the status of terminated background jobs to be reported immediately, rather than before printing the next primary prompt.
  # -c (bash option: command)
  # -e errexit                        == Exit immediately if a pipeline (see Pipelines), which may consist of a single simple command (see Simple Commands), a list (see Lists of Commands), or a compound command (see Compound Commands) returns a non-zero status. The shell does not exit if the command that fails is part of the command list immediately following a while or until keyword, part of the test in an if statement, part of any command executed in a && or || list except the command following the final && or ||, any command in a pipeline but the last, or if the command’s return status is being inverted with !. If a compound command other than a subshell returns a non-zero status because a command failed while -e was being ignored, the shell does not exit. A trap on ERR, if set, is executed before the shell exits.  This option applies to the shell environment and each subshell environment separately (see Command Execution Environment), and may cause subshells to exit before executing all the commands in the subshell.  If a compound command or shell function executes in a context where -e is being ignored, none of the commands executed within the compound command or function body will be affected by the -e setting, even if -e is set and a command returns a failure status. If a compound command or shell function sets -e while executing in a context where -e is ignored, that setting will not have any effect until the compound command or the command containing the function call completes.
  # -f noglob                         == Disable filename expansion (globbing).
  # -h hashall                        == Locate and remember (hash) commands as they are looked up for execution. This option is enabled by default.
  # -i (bash option: interactive)
  # -k keyword                        == All arguments in the form of assignment statements are placed in the environment for a command, not just those that precede the command name.
  # -l (bash option: login)
  # -m monitor                        == Job control is enabled (see Job Control). All processes run in a separate process group. When a background job completes, the shell prints a line containing its exit status.
  # -n noexec                         == Read commands but do not execute them. This may be used to check a script for syntax errors. This option is ignored by interactive shells.
  # -p privileged                     == Turn on privileged mode. In this mode, the $BASH_ENV and $ENV files are not processed, shell functions are not inherited from the environment, and the SHELLOPTS, BASHOPTS, CDPATH and GLOBIGNORE variables, if they appear in the environment, are ignored. If the shell is started with the effective user (group) id not equal to the real user (group) id, and the -p option is not supplied, these actions are taken and the effective user id is set to the real user id. If the -p option is supplied at startup, the effective user id is not reset. Turning this option off causes the effective user and group ids to be set to the real user and group ids.
  # -r                                == Enable restricted shell mode. This option cannot be unset once it has been set.
  # -r (bash option: restricted)
  # -s (bash option: standard input)
  # -t onecmd                         == Exit after reading and executing one command.
  # -u nounset                        == Treat unset variables and parameters other than the special parameters ‘@’ or ‘*’, or array variables subscripted with ‘@’ or ‘*’, as an error when performing parameter expansion. An error message will be written to the standard error, and a non-interactive shell will exit.
  # -v (bash option: verbose)
  # -v verbose                        == Print shell input lines as they are read.
  # -x (bash option: xtrace)
  # -x xtrace                         == Print a trace of simple commands, for commands, case commands, select commands, and arithmetic for commands and their arguments or associated word lists after they are expanded and before they are executed. The value of the PS4 variable is expanded and the resultant value is printed before the command and its expanded arguments.
  # -B braceexpand                    == The shell will perform brace expansion (see Brace Expansion). This option is on by default.
  # -C noclobber                      == Prevent output redirection using ‘>’, ‘>&’, and ‘<>’ from overwriting existing files.
  # -D (bash option: debug?)
  # -E errtrace                       == If set, any trap on ERR is inherited by shell functions, command substitutions, and commands executed in a subshell environment. The ERR trap is normally not inherited in such cases.
  # -H histexpand                     == Enable ‘!’ style history substitution (see History Expansion). This option is on by default for interactive shells.
  # -P physical                       == If set, do not resolve symbolic links when performing commands such as cd which change the current directory. The physical directory is used instead. By default, Bash follows the logical chain of directories when performing commands which change the current directory.  For example, if /usr/sys is a symbolic link to /usr/local/sys then:  ...
  # -T functrace                      == If set, any trap on DEBUG and RETURN are inherited by shell functions, command substitutions, and commands executed in a subshell environment. The DEBUG and RETURN traps are normally not inherited in such cases.

  # (none)       Same as -r.  Enable restricted shell mode. This option cannot be unset once it has been set.
  # allexport    Same as -a.  Each variable or function that is created or modified is given the export attribute and marked for export to the environment of subsequent commands.
  # braceexpand  Same as -B.  The shell will perform brace expansion (see Brace Expansion). This option is on by default.
  # emacs                     Use an emacs-style line editing interface (see Command Line Editing). This also affects the editing interface used for read -e.
  # errexit      Same as -e.  Exit immediately if a pipeline (see Pipelines), which may consist of a single simple command (see Simple Commands), a list (see Lists of Commands), or a compound command (see Compound Commands) returns a non-zero status. The shell does not exit if the command that fails is part of the command list immediately following a while or until keyword, part of the test in an if statement, part of any command executed in a && or || list except the command following the final && or ||, any command in a pipeline but the last, or if the command’s return status is being inverted with !. If a compound command other than a subshell returns a non-zero status because a command failed while -e was being ignored, the shell does not exit. A trap on ERR, if set, is executed before the shell exits.  This option applies to the shell environment and each subshell environment separately (see Command Execution Environment), and may cause subshells to exit before executing all the commands in the subshell.  If a compound command or shell function executes in a context where -e is being ignored, none of the commands executed within the compound command or function body will be affected by the -e setting, even if -e is set and a command returns a failure status. If a compound command or shell function sets -e while executing in a context where -e is ignored, that setting will not have any effect until the compound command or the command containing the function call completes.
  # errtrace     Same as -E.  If set, any trap on ERR is inherited by shell functions, command substitutions, and commands executed in a subshell environment. The ERR trap is normally not inherited in such cases.
  # functrace    Same as -T.  If set, any trap on DEBUG and RETURN are inherited by shell functions, command substitutions, and commands executed in a subshell environment. The DEBUG and RETURN traps are normally not inherited in such cases.
  # hashall      Same as -h.  Locate and remember (hash) commands as they are looked up for execution. This option is enabled by default.
  # histexpand   Same as -H.  Enable ‘!’ style history substitution (see History Expansion). This option is on by default for interactive shells.
  # history                   Enable command history, as described in Bash History Facilities. This option is on by default in interactive shells.
  # ignoreeof                 An interactive shell will not exit upon reading EOF.
  # keyword      Same as -k.  All arguments in the form of assignment statements are placed in the environment for a command, not just those that precede the command name.
  # monitor      Same as -m.  Job control is enabled (see Job Control). All processes run in a separate process group. When a background job completes, the shell prints a line containing its exit status.
  # noclobber    Same as -C.  Prevent output redirection using ‘>’, ‘>&’, and ‘<>’ from overwriting existing files.
  # noexec       Same as -n.  Read commands but do not execute them. This may be used to check a script for syntax errors. This option is ignored by interactive shells.
  # noglob       Same as -f.  Disable filename expansion (globbing).
  # nolog                     Currently ignored.
  # notify       Same as -b.  Cause the status of terminated background jobs to be reported immediately, rather than before printing the next primary prompt.
  # nounset      Same as -u.  Treat unset variables and parameters other than the special parameters ‘@’ or ‘*’, or array variables subscripted with ‘@’ or ‘*’, as an error when performing parameter expansion. An error message will be written to the standard error, and a non-interactive shell will exit.
  # onecmd       Same as -t.  Exit after reading and executing one command.
  # physical     Same as -P.  If set, do not resolve symbolic links when performing commands such as cd which change the current directory. The physical directory is used instead. By default, Bash follows the logical chain of directories when performing commands which change the current directory.  For example, if /usr/sys is a symbolic link to /usr/local/sys then:  ...
  # pipefail                  If set, the return value of a pipeline is the value of the last (rightmost) command to exit with a non-zero status, or zero if all commands in the pipeline exit successfully. This option is disabled by default.
  # posix                     Change the behavior of Bash where the default operation differs from the POSIX standard to match the standard (see Bash POSIX Mode). This is intended to make Bash behave as a strict superset of that standard.
  # privileged   Same as -p.  Turn on privileged mode. In this mode, the $BASH_ENV and $ENV files are not processed, shell functions are not inherited from the environment, and the SHELLOPTS, BASHOPTS, CDPATH and GLOBIGNORE variables, if they appear in the environment, are ignored. If the shell is started with the effective user (group) id not equal to the real user (group) id, and the -p option is not supplied, these actions are taken and the effective user id is set to the real user id. If the -p option is supplied at startup, the effective user id is not reset. Turning this option off causes the effective user and group ids to be set to the real user and group ids.
  # verbose      Same as -v.  Print shell input lines as they are read.
  # vi                        Use a vi-style line editing interface. This also affects the editing interface used for read -e.
  # xtrace       Same as -x.  Print a trace of simple commands, for commands, case commands, select commands, and arithmetic for commands and their arguments or associated word lists after they are expanded and before they are executed. The value of the PS4 variable is expanded and the resultant value is printed before the command and its expanded arguments.

  # -a allexport                      == Each variable or function that is created or modified is given the export attribute and marked for export to the environment of subsequent commands.
  set -a
  set -o allexport
  env | sort > /tmp/env.1
  FOO=foo  # exported
  env | sort > /tmp/env.2
  diff -u /tmp/env.1 /tmp/env.2  # +FOO=foo

  # -b notify                         == Cause the status of terminated background jobs to be reported immediately, rather than before printing the next primary prompt.
  # -c (bash option: command)

  # -e errexit                        == Exit immediately if a pipeline (see Pipelines), which may consist of a single simple command (see Simple Commands), a list (see Lists of Commands), or a compound command (see Compound Commands) returns a non-zero status. The shell does not exit if the command that fails is part of the command list immediately following a while or until keyword, part of the test in an if statement, part of any command executed in a && or || list except the command following the final && or ||, any command in a pipeline but the last, or if the command’s return status is being inverted with !. If a compound command other than a subshell returns a non-zero status because a command failed while -e was being ignored, the shell does not exit. A trap on ERR, if set, is executed before the shell exits.  This option applies to the shell environment and each subshell environment separately (see Command Execution Environment), and may cause subshells to exit before executing all the commands in the subshell.  If a compound command or shell function executes in a context where -e is being ignored, none of the commands executed within the compound command or function body will be affected by the -e setting, even if -e is set and a command returns a failure status. If a compound command or shell function sets -e while executing in a context where -e is ignored, that setting will not have any effect until the compound command or the command containing the function call completes.
  # > or a compound command
  (
    set -e
    ret() { return "$1"; }
    case "$(echo x; ret 1; echo "alive 2" >&2)" in
      x) ret 3; unreachable;;
    esac
    unreachable
  ); echo $?  # alive 2  3
  # > The shell does not exit if the command that fails is part of the command list immediately following a while or until keyword, part of the test in an if statement, part of any command executed in a && or || list except the command following the final && or ||, any command in a pipeline but the last, or if the command’s return status is being inverted with !.
  # part of the command list immediately following a while or until keyword
  (set -e; while false; false; do unreachable; done ; echo "$? alive"); echo $?  # 0 alive  0
  # part of the test in an if statement
  (set -e; if false; false; then unreachable; fi    ; echo "$? alive"); echo $?  # 0 alive  0
  # part of any command executed in a && or || list except the command following the final && or ||
  (set -e; false && false                           ; echo "$? alive"); echo $?  # 1 alive  0  false (, last false skipped)
  (set -e; false || false                           ; echo "$? alive"); echo $?  #          1  false, false (die)
  # any command in a pipeline but the last
  see pipefail
  # if the command’s return status is being inverted with !.
  (set -e; ! false                                  ; echo "$? alive"); echo $?  # 0 alive  0
  (set -e; ! true                                   ; echo "$? alive"); echo $?  # 1 alive  0

  # case + jq -e
  (
    set -e
    # bad:
    case "$(echo '{}' | jq -er '.x')" in
      *) echo reached;;
    esac
    # ok:
    a=$(echo '{}' | jq -er '.x')
    unreachable
    case "$a" in
      *) echo unreachable;;
    esac
  )


  # -f noglob                         == Disable filename expansion (globbing).

  # -h hashall                        == Locate and remember (hash) commands as they are looked up for execution. This option is enabled by default.
  type cc  # cc is /usr/bin/cc
  cc
  type cc  # cc is hashed (/usr/bin/cc)
  set +h
  type cc  # cc is /usr/bin/cc

  # -i (bash option: interactive)
  # -k keyword                        == All arguments in the form of assignment statements are placed in the environment for a command, not just those that precede the command name.
  # -l (bash option: login)
  # -m monitor                        == Job control is enabled (see Job Control). All processes run in a separate process group. When a background job completes, the shell prints a line containing its exit status.
  # -n noexec                         == Read commands but do not execute them. This may be used to check a script for syntax errors. This option is ignored by interactive shells.
  # -p privileged                     == Turn on privileged mode. In this mode, the $BASH_ENV and $ENV files are not processed, shell functions are not inherited from the environment, and the SHELLOPTS, BASHOPTS, CDPATH and GLOBIGNORE variables, if they appear in the environment, are ignored. If the shell is started with the effective user (group) id not equal to the real user (group) id, and the -p option is not supplied, these actions are taken and the effective user id is set to the real user id. If the -p option is supplied at startup, the effective user id is not reset. Turning this option off causes the effective user and group ids to be set to the real user and group ids.
  # -r                                == Enable restricted shell mode. This option cannot be unset once it has been set.
  # -r (bash option: restricted)
  # -s (bash option: standard input)
  # -t onecmd                         == Exit after reading and executing one command.
  # -u nounset                        == Treat unset variables and parameters other than the special parameters ‘@’ or ‘*’, or array variables subscripted with ‘@’ or ‘*’, as an error when performing parameter expansion. An error message will be written to the standard error, and a non-interactive shell will exit.
  # -v (bash option: verbose)
  # -v verbose                        == Print shell input lines as they are read.
  # -x (bash option: xtrace)
  # -x xtrace                         == Print a trace of simple commands, for commands, case commands, select commands, and arithmetic for commands and their arguments or associated word lists after they are expanded and before they are executed. The value of the PS4 variable is expanded and the resultant value is printed before the command and its expanded arguments.
  # -B braceexpand                    == The shell will perform brace expansion (see Brace Expansion). This option is on by default.
  # -C noclobber                      == Prevent output redirection using ‘>’, ‘>&’, and ‘<>’ from overwriting existing files.
  # -D (bash option: debug?)
  # -E errtrace                       == If set, any trap on ERR is inherited by shell functions, command substitutions, and commands executed in a subshell environment. The ERR trap is normally not inherited in such cases.
  # -H histexpand                     == Enable ‘!’ style history substitution (see History Expansion). This option is on by default for interactive shells.
  # -P physical                       == If set, do not resolve symbolic links when performing commands such as cd which change the current directory. The physical directory is used instead. By default, Bash follows the logical chain of directories when performing commands which change the current directory.  For example, if /usr/sys is a symbolic link to /usr/local/sys then:  ...
  # -T functrace                      == If set, any trap on DEBUG and RETURN are inherited by shell functions, command substitutions, and commands executed in a subshell environment. The DEBUG and RETURN traps are normally not inherited in such cases.
fi

# 4.3.2 The Shopt Builtin

if false; then
  shopt
  shopt -p
  shopt -o  # set -o
  shopt -p -o

  echo "$BASHOPTS"            # checkwinsize:cmdhist:complete_fullquote:expand_aliases:extglob:extquote:force_fignore:globasciiranges:histappend:interactive_comments:progcomp:promptvars:sourcepath
  bash -c 'echo "$BASHOPTS"'  # checkwinsize:cmdhist:complete_fullquote:                       extquote:force_fignore:globasciiranges:hostcomplete:interactive_comments:progcomp:promptvars:sourcepath
  shopt -p | grep -- -s
  bash -c "shopt -p" | grep -- -s
  echo "shopt -p" | bash -s | grep -- -s
  #shopt -s checkwinsize            #                      [](file:///home/wsh/.bashrc)
  #shopt -s cmdhist                 #
  #shopt -s complete_fullquote      #
  #shopt -s expand_aliases          # only in interactive
  #shopt -s extglob                 # only in interactive
  #shopt -s extquote                #
  #shopt -s force_fignore           #
  #shopt -s globasciiranges         #
  #shopt -s histappend              # only in interactive  [](file:///home/wsh/.bashrc)
  #shopt -s hostcomplete            # only in -c, -s
  #shopt -s interactive_comments    #
  #shopt -s progcomp                #
  #shopt -s promptvars              #
  #shopt -s sourcepath              #

  shopt       autocd  && echo "autocd enabled"
  shopt -q    autocd  && echo "autocd enabled"
  shopt       cmdhist && echo "cmdhist enabled"
  shopt -q    cmdhist && echo "cmdhist enabled"
  shopt    -o xtrace       && echo "extrace enabled"
  shopt -q -o xtrace       && echo "extrace enabled"
  shopt    -o braceexpand  && echo "braceexpand enabled"
  shopt -q -o braceexpand  && echo "braceexpand enabled"

  # assoc_expand_once
  # autocd
  # cdable_vars
  # cdspell
  # checkhash
  # checkjobs
  # checkwinsize
  # cmdhist
  # compat31
  # compat32
  # compat40
  # compat41
  # compat42
  # compat43
  # compat44
  # complete_fullquote
  # direxpand
  # dirspell
  # dotglob
  # execfail
  # expand_aliases
  # extdebug
  # extglob
  # extquote
  # failglob
  # force_fignore
  # globasciiranges
  # globskipdots
  # globstar
  # gnu_errfmt
  # histappend
  # histreedit
  # histverify
  # hostcomplete
  # huponexit
  # inherit_errexit
  # interactive_comments

  # lastpipe
  # https://qiita.com/BlackCat_617/items/2b3003c4bb79b5d89bc8
  # > ・インタラクティブモード（対話的に入力する場合）ではsetコマンドでモニターオプションをオフにする（set +m）。
  shopt -s lastpipe && set +m  # set +m for interactive shell
  echo foo | read -r foo; echo "$foo"  # foo

  out="init"; shopt -u lastpipe; set +m; echo a | read -r out; declare -p out  # "init"
  out="init"; shopt -u lastpipe; set -m; echo a | read -r out; declare -p out  # "init"
  out="init"; shopt -s lastpipe; set +m; echo a | read -r out; declare -p out  # "a"
  out="init"; shopt -s lastpipe; set -m; echo a | read -r out; declare -p out  # "init"

  # 一時的に shopt -s lastpipe; set +m はやや面倒
  shopt -q lastpipe && orig_lastpipe="on" || orig_lastpipe="off"; [[ -o monitor ]] && orig_monitor="on" || orig_monitor="off"; shopt -s lastpipe && set +m
  out="init"; echo a | read -r out; declare -p out  # a
  [[ $orig_lastpipe == "off" ]] && shopt -u lastpipe; [[ $orig_monitor == "on" ]] && set -m
  # bad:
  out="init"; (shopt -s lastpipe; set +m; echo a | read -r out); declare -p out  # "init"
  # ok 1:
  shopt -u lastpipe && set +m  # orig
  shopt -q lastpipe && orig_lastpipe="on" || orig_lastpipe="off"; [[ -o monitor ]] && orig_monitor="on" || orig_monitor="off"; shopt -s lastpipe && set +m
  out="init"; echo a | read -r out; declare -p out  # a
  [[ $orig_lastpipe == "off" ]] && shopt -u lastpipe; [[ $orig_monitor == "on" ]] && set -m; shopt lastpipe; set -o | grep monitor  # off off
  # ok 2:
  shopt -s lastpipe && set -m  # orig
  shopt -q lastpipe && orig_lastpipe="on" || orig_lastpipe="off"; [[ -o monitor ]] && orig_monitor="on" || orig_monitor="off"; shopt -s lastpipe && set +m
  out="init"; echo a | read -r out; declare -p out  # a
  [[ $orig_lastpipe == "off" ]] && shopt -u lastpipe; [[ $orig_monitor == "on" ]] && set -m; shopt lastpipe; set -o | grep monitor  # on on
  # note:
  shopt -u lastpipe && shopt -q lastpipe && echo ok
  shopt -s lastpipe && shopt -q lastpipe && echo ok  # ok
  #
  shopt -u lastpipe
  shopt -q lastpipe && orig_lastpipe="on" || orig_lastpipe="off"
  declare -p orig_lastpipe  # "off"
  #
  shopt -s lastpipe
  shopt -q lastpipe && orig_lastpipe="on" || orig_lastpipe="off"
  declare -p orig_lastpipe  # "on"
  #
  set +m && [[ -o monitor ]] && echo ok
  set -m && [[ -o monitor ]] && echo ok  # ok
  #
  set +m
  [[ -o monitor ]] && orig_monitor="on" || orig_monitor="off"
  declare -p orig_monitor  # "off"
  #
  set -m
  [[ -o monitor ]] && orig_monitor="on" || orig_monitor="off"
  declare -p orig_monitor  # "on"

  # interactive bash:
  shopt lastpipe  # lastpipe       	off
  set -o          # monitor        	on
  # script:
  shopt lastpipe  # lastpipe       	off
  set -o          # monitor        	off
  #
  sleep 1 & sleep 2
  #[1] 2008725
  #[1]+  Done                    sleep 1 ← interactive && set -m のときのみ出る; script では set +m/-m どちらでも出ない

  shopt -u lastpipe; set +m; sleep 1000 | sleep 1001 | sleep 1002
  shopt -u lastpipe; set -m; sleep 1000 | sleep 1001 | sleep 1002
  shopt -s lastpipe; set +m; sleep 1000 | sleep 1001 | sleep 1002
  shopt -s lastpipe; set -m; sleep 1000 | sleep 1001 | sleep 1002
  # c.bash -vv pstree (pgrep sleep)
  # 全部変わらないな; subshell が関係すると思ったのだが
  #wsh      1995381  0.0  0.0 181056 21880 pts/14   Ss   12:44   0:00               fish
  #wsh      1995499  0.0  0.0  16092  6384 pts/14   S+   12:44   0:00                 bash
  #wsh      1997515  0.0  0.0  12332   520 pts/14   S+   12:51   0:00                   sleep 1000
  #wsh      1997516  0.0  0.0  12332   584 pts/14   S+   12:51   0:00                   sleep 1001
  #wsh      1997517  0.0  0.0  12332   588 pts/14   S+   12:51   0:00                   sleep 1002

  # lithist
  # localvar_inherit
  # localvar_unset
  # login_shell
  # mailwarn
  # no_empty_cmd_completion
  # nocaseglob
  # nocasematch
  # noexpand_translation
  # nullglob
  # patsub_replacement
  # progcomp
  # progcomp_alias
  # promptvars
  # restricted_shell
  # shift_verbose
  # sourcepath
  # varredir_close
  # xpg_echo
fi

# 4.4 Special Builtins

# @end:man_4
fi  # if false

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 5 Shell Variables

if false; then
# @beg:man_5

# 5.1 Bourne Shell Variables

# 5.2 Bash Variables

# BASH_LINENO BASH_SOURCE FUNCNAME LINENO
# shellcheck disable=SC2046  # Quote this to prevent word splitting.
if false; then
  #echo_array "${BASH_SOURCE[@]}"  # /home/wsh/sh/bash_man.bash
  #echo_array "self:$LINENO"  # 273
  #echo_array "${BASH_LINENO[@]}"  # 0
  #echo_array "${FUNCNAME[@]}"  # (empty; main すら出さない)
  func2() { echo -e '\n\e[32m---func2---\e[0m'; echo -e '\e[37m--BASH_SOURCE--\e[0m'; echo_array "${BASH_SOURCE[@]}"; echo -e "\e[37m--LINENO(self)--\e[0m $LINENO"; echo -e '\e[37m--BASH_LINENO--\e[0m'; echo_array "${BASH_LINENO[@]}"; echo -e '\e[37m--FUNCNAME--\e[0m'; echo_array "${FUNCNAME[@]}"; echo -e '\e[37m--caller--\e[0m'; echo_array $(caller); echo -e '\e[37m--caller 0--\e[0m'; echo_array $(caller 0); echo -e '\e[37m--caller 1--\e[0m'; echo_array $(caller 1); echo -e '\e[37m--caller 2--\e[0m'; echo_array $(caller 2); echo -e '\e[37m--caller 3--\e[0m'; echo_array $(caller 3); }         # ---func2--- --BASH_SOURCE-- /home/wsh/sh/bash_man.bash /home/wsh/sh/bash_man.bash /home/wsh/sh/bash_man.bash --LINENO(self)-- 275 --BASH_LINENO-- 276(func1) 277(main) 0(?) --FUNCNAME-- func2 func1 main --caller-- 276 ...bash --caller 0-- 276 func1 ...bash --caller 1-- 277 main ...bash --caller 2-- (empty) --caller 3-- (empty)
  func1() { echo -e '\n\e[32m---func1---\e[0m'; echo -e '\e[37m--BASH_SOURCE--\e[0m'; echo_array "${BASH_SOURCE[@]}"; echo -e "\e[37m--LINENO(self)--\e[0m $LINENO"; echo -e '\e[37m--BASH_LINENO--\e[0m'; echo_array "${BASH_LINENO[@]}"; echo -e '\e[37m--FUNCNAME--\e[0m'; echo_array "${FUNCNAME[@]}"; echo -e '\e[37m--caller--\e[0m'; echo_array $(caller); echo -e '\e[37m--caller 0--\e[0m'; echo_array $(caller 0); echo -e '\e[37m--caller 1--\e[0m'; echo_array $(caller 1); echo -e '\e[37m--caller 2--\e[0m'; echo_array $(caller 2); echo -e '\e[37m--caller 3--\e[0m'; echo_array $(caller 3); func2; }  # ---func1--- --BASH_SOURCE-- /home/wsh/sh/bash_man.bash /home/wsh/sh/bash_man.bash                            --LINENO(self)-- 276 --BASH_LINENO-- 277(main) 0(?)            --FUNCNAME-- func1 main       --caller-- 277 ...bash --caller 0-- 277 main  ...bash --caller 1-- (empty)          --caller 2-- (empty) --caller 3-- (empty)
            echo -e '\n\e[32m---main----\e[0m'; echo -e '\e[37m--BASH_SOURCE--\e[0m'; echo_array "${BASH_SOURCE[@]}"; echo -e "\e[37m--LINENO(self)--\e[0m $LINENO"; echo -e '\e[37m--BASH_LINENO--\e[0m'; echo_array "${BASH_LINENO[@]}"; echo -e '\e[37m--FUNCNAME--\e[0m'; echo_array "${FUNCNAME[@]}"; echo -e '\e[37m--caller--\e[0m'; echo_array $(caller); echo -e '\e[37m--caller 0--\e[0m'; echo_array $(caller 0); echo -e '\e[37m--caller 1--\e[0m'; echo_array $(caller 1); echo -e '\e[37m--caller 2--\e[0m'; echo_array $(caller 2); echo -e '\e[37m--caller 3--\e[0m'; echo_array $(caller 3);           # ---func1--- --BASH_SOURCE-- /home/wsh/sh/bash_man.bash /home/wsh/sh/bash_man.bash                            --LINENO(self)-- 276 --BASH_LINENO-- 277(main) 0(?)            --FUNCNAME-- func1 main       --caller-- 277 ...bash --caller 0-- 277 main  ...bash --caller 1-- (empty)          --caller 2-- (empty) --caller 3-- (empty)
  func1
fi
: <<'OUTPUT'
---main----
--BASH_SOURCE--
$1: /home/wsh/sh/sandbox.bash
--LINENO(self)-- 18
--BASH_LINENO--
$1: 0
--FUNCNAME--
--caller--
$1: 0
$2: NULL
--caller 0--
--caller 1--
--caller 2--
--caller 3--

---func1---
--BASH_SOURCE--
$1: /home/wsh/sh/sandbox.bash
$2: /home/wsh/sh/sandbox.bash
--LINENO(self)-- 17
--BASH_LINENO--
$1: 19
$2: 0
--FUNCNAME--
$1: func1
$2: main
--caller--
$1: 19
$2: /home/wsh/sh/sandbox.bash
--caller 0--
$1: 19
$2: main
$3: /home/wsh/sh/sandbox.bash
--caller 1--
--caller 2--
--caller 3--

---func2---
--BASH_SOURCE--
$1: /home/wsh/sh/sandbox.bash
$2: /home/wsh/sh/sandbox.bash
$3: /home/wsh/sh/sandbox.bash
--LINENO(self)-- 16
--BASH_LINENO--
$1: 17
$2: 19
$3: 0
--FUNCNAME--
$1: func2
$2: func1
$3: main
--caller--
$1: 17
$2: /home/wsh/sh/sandbox.bash
--caller 0--
$1: 17
$2: func1
$3: /home/wsh/sh/sandbox.bash
--caller 1--
$1: 19
$2: main
$3: /home/wsh/sh/sandbox.bash
--caller 2--
--caller 3--

interactive:

---main----
--BASH_SOURCE--
--LINENO(self)-- 14 ← コマンドを入力していくと増えていく
--BASH_LINENO--
--FUNCNAME--
--caller--
--caller 0--
--caller 1--
--caller 2--
--caller 3--

---func1---
--BASH_SOURCE--
$1: main
--LINENO(self)-- 1
--BASH_LINENO--
$1: 15 ← コマンドを入力していくと増えていく
--FUNCNAME--
$1: func1
--caller--
$1: 15 ← コマンドを入力していくと増えていく
$2: NULL
--caller 0--
--caller 1--
--caller 2--
--caller 3--

---func2---
--BASH_SOURCE--
$1: main
$2: main
--LINENO(self)-- 1
--BASH_LINENO--
$1: 1
$2: 15 ← コマンドを入力していくと増えていく
--FUNCNAME--
$1: func2
$2: func1
--caller--
$1: 1
$2: main
--caller 0--
$1: 1
$2: func1
$3: main
--caller 1--
--caller 2--
--caller 3--
OUTPUT

# BASHPID

# old
if false; then


echo $LINENO # 21
echo "${FUNCNAME}"
echo "${FUNCNAME[0]}"
echo "${FUNCNAME[@]}"

func1

echo $LINENO # 21
echo "${FUNCNAME}"
echo ${#FUNCNAME[@]}  # 0
echo "${FUNCNAME[0]}"
echo "${FUNCNAME[@]}"

fi

PIPESTATUS
# shellcheck disable=SC2216  # Piping to 'false', a command that doesn't read stdin. Wrong command or missing xargs?
true | false | sh -c 'exit 2' | sh -c 'return 3'
# $?: 3
echo "${PIPESTATUS[@]}"  # 0 1 2 3

# @end:man_5
fi  # if false

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 6 Bash Features

if false; then
# @beg:man_6

# 6.1 Invoking Bash
# 6.2 Bash Startup Files
# 6.3 Interactive Shells
# 6.3.1 What is an Interactive Shell?
# 6.3.2 Is this Shell Interactive?
# 6.3.3 Interactive Shell Behavior

# 6.4 Bash Conditional Expressions
if false; then
if test -e /tmp/; then
    echo /tmp/ exists
fi
fi
# -b block special file
# -c character special file
# -d directory
# -e any
# -f regular file
# -g symbolic link
# -p naped pipe (FIFO)
# -S socket

# 6.5 Shell Arithmetic
# > the (( compound command, the let builtin, or the -i option to the declare builtin
i=0
for ((i=0; i<3; i++)); do echo $i; done           # 3.2.5 Compound Commands          > for name [ [in [words …] ] ; ] do commands; done
((i++))                                           # 3.2.5 Compound Commands          > (( expression ))
string=01234567890abcdefgh; echo ${string:0:1+1}  # 3.5.3 Shell Parameter Expansion  > ${parameter:offset} ${parameter:offset:length}
echo $((1+1))                                     # 3.5.5 Arithmetic Expansion > $(( expression ))
declare -i i; i="1 + 1"                           # 4.2 Bash Builtin Commands        > declare [-aAfFgiIlnrtux] [-p] [name[=value] …]
let i++                                           # 4.2 Bash Builtin Commands        > let expression [expression …]
[[ "1 + 1" -eq "2" ]] && echo "true"              # 6.4 Bash Conditional Expressions > arg1 OP arg2
arr[1+1]="val"                                    # 6.7 Arrays

# 6.6 Aliases

# 6.7 Arrays

# arr[4] = "four" と初期化すると {null, null, null "four"} だが
# 長さ ${#arr[@]} は 1 だったり闇が深いが、あまり深追いしない

if false; then

print_argv() {
    echo len: ${#@}
    # echo len: ${#*}
    local i=0
    # for i in "${!@}"; do
    for item in "$@"; do
       echo argv[$i]: "$item"
       ((i++))
    done
}

var=foobar
arr=(zero one)
arr[2]=two

echo ${#var}     # 6 "foobar"
echo ${#arr[@]}  # 2 {two, four}
echo ${#arr[0]}  # 4 "zero"
echo ${#arr[1]}  # 3 "one"
echo ${#arr[2]}  # 3 "two"

print_argv ${arr[@]}    # {"zero", "one", "two"}
print_argv ${arr[*]}    # {"zero", "one", "two"}
print_argv "${arr[@]}"  # {"zero", "one", "two"}
print_argv "${arr[*]}"  #  "zero one two"
IFS=-
print_argv "${arr[*]}"  #  "zero-one-two"

# zero, one, two
for item in "${arr[@]}"; do
    echo $item
done

# 0: zero, 1: one, 2: two
for i in "${!arr[@]}"; do
    echo $i: ${arr[$i]}
done

unset arr
print_argv "${arr[@]}" # null
print_argv             # same (not "" !)

fi

# associative array
if false; then
  declare -A hash
  hash=([a]=1 [b]=2)
  declare -p hash  # declare -A hash=([b]="2" [a]="1" )
  #echo_array "${hash[@]}"  # 2 1
  echo "${hash[@]}"  # passes "2", "1"
  echo "${hash[*]}"  # passes "2 1"
  # echo_array "${!hash[@]}"  # b a
  # echo_array "${!hash[*]}"  # "b a"

  # TODO:
  # compat51 (set using BASH_COMPAT)
  # The unset builtin will unset the array a given an argument like ‘a[@]’. Bash-5.2 will unset an element with key ‘@’ (associative arrays) or remove all the elements without unsetting the array (indexed arrays)
  # test -v, when given an argument of ‘A[@]’, where A is an existing associative array, will return true if the array has any set elements. Bash-5.2 will look for and report on a key named ‘@’
  # assoc_expand_once
fi

# 6.8 The Directory Stack
# 6.8.1 Directory Stack Builtins
# 6.9 Controlling the Prompt
# 6.10 The Restricted Shell
# 6.11 Bash POSIX Mode

# @end:man_6
fi  # if false

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 7 Job Control

if false; then
# @beg:man_7

# 7.1 Job Control Basics

# delayed suspend character (typically ‘^Y’, Control-Y) 分からん

# The character ‘%’ introduces a job specification (jobspec).

false &
wait %1 || echo -e "\e[31m""false failed with $?\e[0m"

sleep 0.2 | sleep 0.3 | sh -c "exit 10" & # [1] 10010
jobs
#[1]+  Running                 sleep 0.2 | sleep 0.3 | sh -c "exit 10" &
# wait %1           ; echo $?  # 10
# wait %-           ; echo $?  # 10
# wait %%           ; echo $?  # 10
# wait %+           ; echo $?  # 10
# wait %"sleep 0.5" ; echo $?  # 10
# wait PID          ; echo $?  # 10

sleep 0.2 | sleep 0.3 | sh -c "exit 10" & # [1] 10010
sleep 0.3 | sleep 0.4 | sh -c "exit 11" & # [2] 10011
sleep 0.4 | sleep 0.5 | sh -c "exit 12" & # [3] 10012
sleep 0.5 | sleep 0.6 | sh -c "exit 13" & # [4] 10013
jobs
#[1]   Running                 sleep 0.2 | sleep 0.3 | sh -c "exit 10" &
#[2]   Running                 sleep 0.3 | sleep 0.4 | sh -c "exit 11" &
#[3]-  Running                 sleep 0.4 | sleep 0.5 | sh -c "exit 12" &
#[4]+  Running                 sleep 0.5 | sleep 0.6 | sh -c "exit 13" &
jobs -l
#[1]  438839 Running                 sleep 0.2
#     438840                       | sleep 0.3
#     438841 Running                 | sh -c "exit 10" &
#[2]  438842 Running                 sleep 0.3
#     438843                       | sleep 0.4
#     438844                       | sh -c "exit 11" &
#[3]- 438845 Running                 sleep 0.4
#     438846                       | sleep 0.5
#     438847                       | sh -c "exit 12" &
#[4]+ 438848 Running                 sleep 0.5
#     438849                       | sleep 0.6
#     438850                       | sh -c "exit 13" &
# jobs -n  # only cahnged
jobs -p  # process ID of the job’s process group leader
#10010
#10011
#10012
#10013
# jobs -r  # only Running
# jobs -s  # only stopped

# wait; echo $?  # 0; job 1 つでも 0 (wait 引数なしは returns 0)
# wait %1           ; echo $?  # 10
# wait %2           ; echo $?  # 11
# wait %3           ; echo $?  # 12
# wait %4           ; echo $?  # 13
# wait %-           ; echo $?  # 12
# wait %%           ; echo $?  # 13
# wait %+           ; echo $?  # 13
# wait "%sleep"     ; echo $?  # PROG: line 17: wait: sleep: ambiguous job spec
# wait "%sleep 0.2" ; echo $?  # 10 starts with "sleep 0.2"
# wait "%?exit 13"  ; echo $?    #    contains    "exit 13"; PROG: line 19: wait: exit 13: ambiguous job spec なぜだ？ group leader (pipe の一番最初のコマンド) のみマッチするっぽいな

fg %1
bg %1
%1 &  # bg %1

shopt -s checkjobs
sleep 9999 &
exit
#There are running jobs.
#[1]+  Running                 sleep 9999 &
exit
#exit

# 7.2 Job Control Builtins

# wait [-fn] [-p varname] [jobspec or pid …]
# https://github.com/bminor/bash/blob/master/builtins/wait.def

wait -f  # ?

# wait -n: any
sleep 0.2 | sh -c "exit 10" &
sleep 0.1 | sh -c "exit 11" &
wait -n; echo "?:$?"  # 11
wait -n; echo "?:$?"  # 10
wait -n; echo "?:$?"  # 127
# タイミングによっては回収できない…
sleep 0.2 | sh -c "exit 10" &
sleep 0.1 | sh -c "exit 11" &
sleep 0.3  # or terminal 待機
wait -n; echo "?:$?"  # 127
wait -n; echo "?:$?"  # 127

# wait -n {jobspec or pid…} と補足するjobspec指定もできる

# wait -p varname: bash 5.1? https://github.com/bminor/bash/blob/master/CHANGES
# This is useful only when the -n option is supplied.
# 20:04: GNU bash, version 5.0.17(1)-release (x86_64-pc-linux-gnu)
# 22.04: GNU bash, version 5.1.16(1)-release (x86_64-pc-linux-gnu)

kill $(jobs -p)

# 7.3 Job Control Variables

# @end:man_7
fi  # if false

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 8 Command Line Editing

# 8.1 Introduction to Line Editing
# 8.2 Readline Interaction
# 8.2.1 Readline Bare Essentials
# 8.2.2 Readline Movement Commands
# 8.2.3 Readline Killing Commands
# 8.2.4 Readline Arguments
# 8.2.5 Searching for Commands in the History
# 8.3 Readline Init File
# 8.3.1 Readline Init File Syntax
# 8.3.2 Conditional Init Constructs
# 8.3.3 Sample Init File
# 8.4 Bindable Readline Commands
# 8.4.1 Commands For Moving
# 8.4.2 Commands For Manipulating The History
# 8.4.3 Commands For Changing Text
# 8.4.4 Killing And Yanking
# 8.4.5 Specifying Numeric Arguments
# 8.4.6 Letting Readline Type For You
# 8.4.7 Keyboard Macros
# 8.4.8 Some Miscellaneous Commands
# 8.5 Readline vi Mode
# 8.6 Programmable Completion
# 8.7 Programmable Completion Builtins
# 8.8 A Programmable Completion Example

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 9 Using History Interactively

# 9.1 Bash History Facilities
# 9.2 Bash History Builtins
# 9.3 History Expansion
# 9.3.1 Event Designators
# 9.3.2 Word Designators
# 9.3.3 Modifiers

# ------------------------------------------------------------------------------
# z Bash Reference Manual - 10 Installing Bash

# 10.1 Basic Installation
# 10.2 Compilers and Options
# 10.3 Compiling For Multiple Architectures
# 10.4 Installation Names
# 10.5 Specifying the System Type
# 10.6 Sharing Defaults
# 10.7 Operation Controls
# 10.8 Optional Features

# ------------------------------------------------------------------------------
# z Bash Reference Manual - Appendix A Reporting Bugs

# ------------------------------------------------------------------------------
# z Bash Reference Manual - Appendix B Major Differences From The Bourne Shell

# B.1 Implementation Differences From The SVR4.2 Shell

# ------------------------------------------------------------------------------
# z Bash Reference Manual - Appendix C GNU Free Documentation License

# ------------------------------------------------------------------------------
# z Bash Reference Manual - Appendix D Indexes

# D.1 Index of Shell Builtin Commands
# D.2 Index of Shell Reserved Words
# D.3 Parameter and Variable Index
# D.4 Function Index
# D.5 Concept Index

# ------------------------------------------------------------------------------
# z scraps

if false; then

# ------------------------------------------------------------------------------
# z scraps - 0 draft

sudo systemd-run -- bash -c '{ TERM=xterm clear; lsof -nP -p "$$BASHPID"; echo -e "\e[32m""done\e[0m"; } >>/tmp/tmp.systemd.log 2> >(sed -e "s/^/\x1b[31m/" -e "s/\$/\x1b[0m/" >> /tmp/tmp.systemd.log)'

# ------------------------------------------------------------------------------
# z scraps - 0 references

# /usr/local/bin/bats               [](file:///usr/local/bin/bats)
# /usr/local/libexec/bats-core/bats [](file:///usr/local/libexec/bats-core/bats)

# ------------------------------------------------------------------------------
# z scraps - ansi escape sequences - colors

# @ref:shell_color

# colors
echo -e '\e[30m' black  '\e[0m'
echo -e '\e[31m' red    '\e[0m'
echo -e '\e[32m' green  '\e[0m'
echo -e '\e[33m' yellow '\e[0m'
echo -e '\e[34m' blue   '\e[0m'
echo -e '\e[35m' purple '\e[0m'
echo -e '\e[36m' cyan   '\e[0m'
echo -e '\e[37m' white  '\e[0m'

echo -e '\e[1;30m' bright black  '\e[0m'
echo -e '\e[1;31m' bright red    '\e[0m'
echo -e '\e[1;32m' bright green  '\e[0m'
echo -e '\e[1;33m' bright yellow '\e[0m'
echo -e '\e[1;34m' bright blue   '\e[0m'
echo -e '\e[1;35m' bright purple '\e[0m'
echo -e '\e[1;36m' bright cyan   '\e[0m'
echo -e '\e[1;37m' bright white  '\e[0m'

echo_black()  { tput setaf 0 ; echo "$@" ; tput sgr0 ; }
echo_red()    { tput setaf 1 ; echo "$@" ; tput sgr0 ; }
echo_green()  { tput setaf 2 ; echo "$@" ; tput sgr0 ; }
echo_yellow() { tput setaf 3 ; echo "$@" ; tput sgr0 ; }
echo_blue()   { tput setaf 4 ; echo "$@" ; tput sgr0 ; }
echo_purple() { tput setaf 5 ; echo "$@" ; tput sgr0 ; }
echo_cyan()   { tput setaf 6 ; echo "$@" ; tput sgr0 ; }
echo_white()  { tput setaf 7 ; echo "$@" ; tput sgr0 ; }

echo_black()  { echo -e "\e[30m$*\e[0m" ; }
echo_red()    { echo -e "\e[31m$*\e[0m" ; }
echo_green()  { echo -e "\e[32m$*\e[0m" ; }
echo_yellow() { echo -e "\e[33m$*\e[0m" ; }
echo_blue()   { echo -e "\e[34m$*\e[0m" ; }
echo_purple() { echo -e "\e[35m$*\e[0m" ; }
echo_cyan()   { echo -e "\e[36m$*\e[0m" ; }
echo_white()  { echo -e "\e[37m$*\e[0m" ; }

# ------------------------------------------------------------------------------
# z scraps - arguments - shell-arguments array to sh -c

# https://stackoverflow.com/questions/73722324/convert-bash-array-to-a-single-stringified-shell-argument-list-handable-by-sh
shell_arguments=(echo "foo bar" baz)
sh -c "${shell_arguments[*]@Q}"
sh -c "${*@Q}"  # not tested
sh -c "${@@Q}"  # not tested

echo "$(printf " %q" "$@")"  # '"' "foo bar" ->  \" foo\ bar

ssh localhost "$(printf " %q" /home/wsh/bin/args "arg 1" "" "'arg3'" ' !"#$%&'\''()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~')"
ssh localhost "$(printf " %q" printf " %q" "arg 1" "" "'arg3'" ' !"#$%&'\''()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~')"

# ------------------------------------------------------------------------------
# z scraps - arguments - shell-arguments array to sh -c - script re-exec

if [ -z "$C_BASH_IN_SCRIPT" ]; then
  echo -e "\e[32m$(date +"%F %T") $0$([ "$#" -gt 0 ] && printf " %q" "$@")\e[0m"  "[tty:$(tty)] script"
  export C_BASH_IN_SCRIPT=1
  mkdir -pv /tmp/$USER/c.bash.d/
  (set -x; script -efq -c "$0$(BASH_XTRACEFD=$fd_devnull set +x; [ "$#" -gt 0 ] && printf " %q" "$@")" /tmp/$USER/c.bash.d/script.out) {fd_devnull}>/dev/null
  exit $?
fi
echo -e "\e[32m$(date +"%F %T") $0$([ "$#" -gt 0 ] && printf " %q" "$@")\e[0m"  "[tty:$(tty)] in script, logging to /tmp/$USER/c.bash.d/script.out"

: <<'TESTS'
key.bash     # + script -efq -c /home/wsh/sh/key.bash /tmp/$USER/c.bash.d/script.out
key.bash ""  # + script -efq -c '/home/wsh/sh/key.bash '\'''\''' /tmp/$USER/c.bash.d/script.out
key.bash ' !"#$%&'\''()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~'
TESTS
# print_argv.bash "$@"

# ------------------------------------------------------------------------------
# z scraps - bash - argv - print argv (declare -p tmp=($@) "${@}")

declare -p @  # bash: declare: @: not found
tmp=("$@")
declare -p tmp

# ------------------------------------------------------------------------------
# z scraps - env

must_set() {
    if ! [[ -v $1 ]]; then
        err "fatal: $1 must be exported before"
        exit 1
    fi
}

must_set HOME  # /home/wsh

[[ -v HOME ]] || { echo "do export HOME=/path/to/home before." ; exit 1 ; }

# ------------------------------------------------------------------------------
# z scraps - grep environment variable

DBUS_SESSION_BUS_ADDRESS=$(strings /proc/"$(pgrep -u wsh pipewire | head -1)"/environ | grep -P -o '(?<=DBUS_SESSION_BUS_ADDRESS=).+$')

# ------------------------------------------------------------------------------
# z scraps - IFS - temporary IFS
# https://unix.stackexchange.com/a/92190/231543

# join by join_by

# summary
arr=(a b c)
(IFS=-; echo "{arr[*]}")                                # OK (subshell)
var=$(IFS=-; echo "${arr[*]}") && echo "$var"           # var=a-b-c
shopt -s lastpipe && set +m  # set +m for interactive shell
(IFS=-; echo "${arr[*]}") | read -r var && echo "$var"  # var=a-b-c

arr=(a b c)
echo -n "$IFS" | xxd  # default IFS: 20 09 0a (space \t \n)
echo "IFS: $(xxd -p <<<"$IFS") | ${arr[*]}"
IFS=- echo "IFS: $(xxd -p <<<"$IFS") | ${arr[*]}"       # not work (environment vaiable) | This assignment is only seen by the forked process. shellcheckSC2097
env IFS=- echo "IFS: $(xxd -p <<<"$IFS") | ${arr[*]}"   # not work (environment vaiable)
(IFS=-; echo "IFS: $(xxd -p <<<"$IFS") | ${arr[*]}")    # OK (subshell)
(IFS=-; echo "{arr[*]}")                                # OK (subshell)
echo "IFS: $(xxd -p <<<"$IFS") | ${arr[*]}"             # IFS restored
# IFS= read -r line は read command 自体？実行結果？に IFS が効くが、
# IFS=- echo "{arr[*]}" は IFS より先に "{arr[*]}" が評価されるのだと思われる

# assign to variable
arr=(a b c)
var=$(IFS=-; echo "${arr[*]}") && echo "$var"           # var=a-b-c
echo "IFS: $(xxd -p <<<"$IFS") | ${arr[*]}"             # IFS restored

arr=(a b c)
shopt -s lastpipe && set +m  # set +m for interactive shell
(IFS=-; echo "${arr[*]}") | read -r var && echo "$var"  # var=a-b-c
echo "IFS: $(xxd -p <<<"$IFS") | ${arr[*]}"             # IFS restored

# ------------------------------------------------------------------------------
# z scraps - jq - draft

echo '{"arr": [1, 2]}' >/tmp/a.json
echo '{"arr": [3, 4]}' >/tmp/b.json
jq -c    'inputs'       /tmp/a.json /tmp/b.json  # stdin?:a    inputs:b   {"arr":[3,4]}
jq -c -n 'inputs'       /tmp/a.json /tmp/b.json  # stdin?:null inputs:a,b {"arr":[1,2]} {"arr":[3,4]}
jq -c -n 'inputs.arr'   /tmp/a.json /tmp/b.json  # [1,2] [3,4]
jq -c -n 'inputs.arr[]' /tmp/a.json /tmp/b.json  # 1 2 3 4

# > {user: .user, title: .title}
# > Because that is so common, there's a shortcut syntax for it: {user, title}.
echo '{"key1": "val1"}'           | jq -c '{key1}'                     # {"key1":"val1"}
echo '{"key1": {"key2": "val1"}}' | jq -c '{key1}'                     # {"key1":{"key2":"val1"}}
echo '{"key1": {"key2": "val1"}}' | jq -c '{key1.key2}'                # syntax error
echo '{"key1": {"key2": "val1"}}' | jq -c '{key2: .key1.key2}'         # {"key2":"val1"}
echo '{"key1": {"key2": "val1"}}' | jq -c '{"key1.key2": .key1.key2}'  # {"key1.key2":"val1"}

# -e
echo invalid_json | jq    '.'   # 4 parse error: Invalid numeric literal at line 2, column 0
echo '{}'         | jq    '.'   # 0 {}
echo '{}'         | jq    '.x'  # 0 null
echo '{}'         | jq -e '.x'  # 1 null
# case + jq -e
(
  set -e
  # bad:
  case "$(echo '{}' | jq -er '.x')" in
    *) echo reached;;
  esac
  # ok:
  a=$(echo '{}' | jq -er '.x')
  unreachable
  case "$a" in
    *) unreachable;;
  esac
)

# ------------------------------------------------------------------------------
# z scraps - jq - 0 iterator

echo '[1, 2, 3]' | jq '  .           ' # [1, 2, 3] array
echo '[1, 2, 3]' | jq '  .[]         ' #  1  2  3  iterator
echo '[1, 2, 3]' | jq '[ .[] ]       ' # [1, 2, 3] iterator -> array
echo '[1, 2, 3]' | jq '  .[]' | jq -s  # [1, 2, 3] iterator -> array; --slurp / -s
echo ' 1  2  3 '              | jq -s  # [1, 2, 3] iterator -> array; --slurp / -s

echo '[{"directory": "/dir0", "file": "file0"}, {"directory": "/dir1", "file": "file1"}]' | jq '.[].directory'  # "/dir0"  "/dir1"
echo '[{"directory": "/dir0", "file": "file0"}, {"directory": "/dir1", "file": "file1"}]' | jq '.[].file'       # "file0"  "file1"
echo '[{"directory": "/dir0", "file": "file0"}, {"directory": "/dir1", "file": "file1"}]' | jq '.[].directory + "/" + .[].file'       # iterater + string("/") + iterator: 積 組み合わせ "/dir0/file0"  "/dir1/file0"  "/dir0/file1"  "/dir1/file1"

echo '[{"directory": "/dir0", "file": "file0"}, {"directory": "/dir1", "file": "file1"}]' | jq '.[] | .directory'  # "/dir0"  "/dir1"
echo '[{"directory": "/dir0", "file": "file0"}, {"directory": "/dir1", "file": "file1"}]' | jq '.[] | .file'       # "file0"  "file1"
echo '[{"directory": "/dir0", "file": "file0"}, {"directory": "/dir1", "file": "file1"}]' | jq '.[] | .directory + "/" + .file'       # string("/dir0") + string("/") + string("file0"): string  "/dir0/file0"  "/dir1/file1"

# ------------------------------------------------------------------------------
# z scraps - jq - 0 string

echo '"foo"' | jq '.'  # "foo"

# --raw-output / -r

echo '"foo"' | jq -r '.'          #  foo
echo '"foo"' | jq    '.' | jq -r  #  foo 1個目のjqの引数が長いならこっちで
# non-striong と string の区別が付かなくなるので注意
echo '"null"' | jq -r  # null
echo ' null ' | jq -r  # null ttyなら灰色

# --raw-input/-R
# --ascii-output / -a
# --slurp/-s

echo -e 'foo\n世界' | jq       # parse error: Invalid literal at line 2, column 0
echo -e 'foo\n世界' | jq -R    # "foo" "世界"
echo -e 'foo\n世界' | jq -aR   # "foo" "\u4e16\u754c"
echo -e 'foo\n世界' | jq -sR   # "foo\n世界\n"
echo -e 'foo\n世界' | jq -asR  # "foo\n\u4e16\u754c\n"
echo     null       | jq       #  null
echo     null       | jq -R    # "null"

# Builtin operators and functions

# Builtin operators and functions - Addition: +
echo '[]' | jq '"a" + "b"'  # "ab"

# Builtin operators and functions - ascii_downcase, ascii_upcase
echo '["foo", "bar"]' | jq '  .[]  '                 #  "foo" "bar"  iterator
echo '["foo", "bar"]' | jq '  .[] | ascii_upcase '   #  "FOO" "BAR"
echo '["foo", "bar"]' | jq '[ .[] | ascii_upcase ]'  # ["FOO", "BAR"]

# Builtin operators and functions - contains(element)
echo '["foo", "bar"]' | jq '[ .[] | contains("o") ]'  # [true, false]

# Builtin operators and functions - explode
echo '["foo", "bar"]' | jq '[ .[] | explode ]'  # [[102, 111, 111], [98, 97, 114]]

# Builtin operators and functions - join(str)
echo '["foo", "bar"]' | jq '. | join("-")'  # "foo-bar"
echo '["foo", "bar"]' | jq 'join("-")'  # "foo-bar"

# Builtin operators and functions - length utf8bytelength
echo '"あ"' | jq 'length'  # 1
echo '"あ"' | jq 'utf8bytelength'  # 3

# Builtin operators and functions - ltrimstr(str) rtrimstr(str)
echo '["foo", "bar"]' | jq '[ .[] | ltrimstr("f")  ]'  # ["oo", "bar"]
echo '["foo", "bar"]' | jq '[ .[] | rtrimstr("oo") ]'  # ["f", "bar"]

# Builtin operators and functions - Multiplication, division, modulo: *, /, and %
echo '"a"' | jq '. * 3'  # "aaa"

# Builtin operators and functions - sort
echo '["foo", "bar"]' | jq 'sort'  # ["bar", "foo"]

# Builtin operators and functions - split(str)
echo '["foo", "bar"]' | jq '[ .[] | split("a") ]'  # [["foo"], ["b", "r"]]

# Builtin operators and functions - endswith(str) startswith(str)
echo '["foo", "bar"]' | jq '[ .[] | endswith("o") ]'  # [true, false]
echo '["foo", "bar"]' | jq '[ .[] | startswith("f") ]'  # [true, false]

# Builtin operators and functions - tonumber
echo '["0", "1"]' | jq '[ .[] | tonumber ]'  # [0, 1]

# Builtin operators and functions - String interpolation - \(foo)

echo '["foo", "bar"]' | jq '"=== \(.[0]) ==="'  # "=== foo ==="
echo '{"path": "/"}' | jq '"=== \(.path) ==="'  # "=== / ==="

# ------------------------------------------------------------------------------
# z scraps - jq - 1 select (filter)

echo '[{"key": true}, {"key": false}]' | jq -c '.'                           # as-is
echo '[{"key": true}, {"key": false}]' | jq -c '.   | select(true)'          # same
echo '[{"key": true}, {"key": false}]' | jq -c '      select(true)'          # same
echo '[{"key": true}, {"key": false}]' | jq -c '      select(false)'         # (empty)
echo '[{"key": true}, {"key": false}]' | jq -c '.[] | select(.key == true)'  # {"key":true}

echo '[{"key": true}, {"key": false}]' | jq -c 'map(., .)'                  # [{"key":true},{"key":true},{"key":false},{"key":false}]
echo '[{"key": true}, {"key": false}]' | jq -c 'map([., .])'                # [{"key":true},{"key":true},{"key":false},{"key":false}]
echo '[{"key": true}, {"key": false}]' | jq -c 'select(.key == true)'       # jq: error (at <stdin>:1): Cannot index array with string "key"
echo '[{"key": true}, {"key": false}]' | jq -c 'map(select(.key == true))'  # [{"key": true}]

# select - string - contains()
echo '["foo", "bar"]' | jq -c '.[] | select(contains("o"))'  #  "foo"
echo '["foo", "bar"]' | jq -c 'map(select(contains("o")))'   # ["foo"]

# select - string - endswith(str) startswith(str)
echo '["foo", "bar"]' | jq -c '.[] | select(endswith("o"))'    # "foo"
echo '["foo", "bar"]' | jq -c 'map(select(endswith("o")))'     # ["foo"]
echo '["foo", "bar"]' | jq -c '.[] | select(startswith("f"))'  # "foo"
echo '["foo", "bar"]' | jq -c 'map(select(startswith("f")))'   # ["foo"]

# ------------------------------------------------------------------------------
# z scraps - jq - compile_commands.json

# TODO: old:
#   ~/qc/linux/
#   ~/qc/linux-build/

jq <~/qc/linux/focal-d/compile_commands.json '.'       # [ {}, {} ]
jq <~/qc/linux/focal-d/compile_commands.json '.[]'     #   {}, {}
jq <~/qc/linux/focal-d/compile_commands.json '.[0]'    #   {}
jq <~/qc/linux/focal-d/compile_commands.json '[ .[] ]' #  [ {}, {} ]
jq <~/qc/linux/focal-d/compile_commands.json '{ a: .[] }' #  { "a":{}, "a":{} } ("a" duplicate)
jq <~/qc/linux/focal-d/compile_commands.json '.[].file'
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | wc -l  # 6392
jq <~/qc/linux/focal-d/compile_commands.json '[ .[].file ]'
jq <~/qc/linux/focal-d/compile_commands.json '[ .[] | .file ]'
jq <~/qc/linux/focal-d/compile_commands.json '[ .[] | [.file] ]'
jq <~/qc/linux/focal-d/compile_commands.json '[ .[] | [.file, .directory] ]'
jq <~/qc/linux/focal-d/compile_commands.json '[ .[] | {f:.file, d:.directory} ]'

jq <~/qc/linux/focal-d/compile_commands.json '  .[] | select(  .file | startswith("/home/wsh/qc/linux/init/")  )'
jq <~/qc/linux/focal-d/compile_commands.json '  .[] | select( (.file | startswith("/home/wsh/qc/linux/init/")) )'  # same
jq <~/qc/linux/focal-d/compile_commands.json '  .[] | select( (.file | startswith("/home/wsh/qc/linux/init/")) or (.file | startswith("/home/wsh/qc/linux/arch/")) )'
jq <~/qc/linux/focal-d/compile_commands.json '[ .[] | select( (.file | startswith("/home/wsh/qc/linux/init/")) or (.file | startswith("/home/wsh/qc/linux/arch/")) ) ]'

jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | sort   # 眺めてどれがほしいか決める

jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/arch/'                  | wc -l  # 379 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/block/'                 | wc -l  # 64 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/certs/'                 | wc -l  # 3 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/crypto/'                | wc -l  # 144 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/Documentation/'         | wc -l  # 0
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/'               | wc -l  # 10533
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/acpi/'          | wc -l  # 252 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/base/'          | wc -l  # 61 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/block/'         | wc -l  # 64 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/bluetooth/'     | wc -l  # 45 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/char/'          | wc -l  # 85 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/firmware/'      | wc -l  # 32 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/firmware/efi/'  | wc -l  # 24
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/gpio/'          | wc -l  # 71 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/hid/'           | wc -l  # 144 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/input/'         | wc -l  # 283 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/tty/'           | wc -l  # 76 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/usb/'           | wc -l  # 344 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/drivers/virtio/'        | wc -l  # 10 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/fs/'                    | wc -l  # 1189 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/include/'               | wc -l  # 0
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/init/'                  | wc -l  # 8 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/ipc/'                   | wc -l  # 11 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/kernel/'                | wc -l  # 285 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/lib/'                   | wc -l  # 220 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/LICENSES/'              | wc -l  # 0
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/mm/'                    | wc -l  # 93 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/net/'                   | wc -l  # 1364 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/samples/'               | wc -l  # 1 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/scripts/'               | wc -l  # 0
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/security/'              | wc -l  # 119 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/sound/'                 | wc -l  # 757 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/tools/'                 | wc -l  # 0
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/usr/'                   | wc -l  # 0
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/virt/'                  | wc -l  # 8 *
jq <~/qc/linux/focal-d/compile_commands.json '.[].file' | ag '^"/home/wsh/qc/linux/zmisc/'                 | wc -l  # 0

jq <~/qc/linux/focal-d/compile_commands.json >~/qc/linux/compile_commands.json '[ .[] | select(
    (.file | startswith("/home/wsh/qc/linux/arch/")) or
    ...
    false
  ) ]'

# 1ファイル足す
jq <~/qc/linux/focal-d/compile_commands.json '[ .[] | select(.file | endswith("drivers/tty/vt/vt.c")) ]' > tmp.json
jq -s 'add' compile_commands.json tmp.json | sponge compile_commands.json

# backtraceのファイル一覧
echo '[]' > compile_commands.json
for f in \
arch/x86/entry/entry_64.S \
arch/x86/include/asm/idtentry.h \
arch/x86/include/asm/irq_stack.h \
arch/x86/kernel/irq.c \
drivers/input/input.c \
drivers/input/keyboard/atkbd.c \
drivers/input/serio/i8042.c \
drivers/input/serio/serio.c \
drivers/tty/vt/keyboard.c \
include/linux/input.h \
kernel/irq/handle.c \
;
  echo add $f
  jq <~/qc/linux/focal-d/compile_commands.json '[ .[] | select(.file | endswith("'$f'")) ]' > tmp.json
  jq -s 'add' compile_commands.json tmp.json | sponge compile_commands.json
end

Loading... で固まる
kernel/irq/chip.c    1597
drivers/tty/vt/vt.c  4865
なんか固まる原因になっている共通のマクロありそうだな

# insertion to array

jq --arg IPWD "-I$PWD" --arg IRUBY \
  "-I$HOME/src/ruby/include" '.[].arguments |= [ .[0], $IPWD, $IRUBY, .[1:][] ]' \
  compile_commands.json

# software - ruby

jq <~/qc/ruby/build/compile_commands.json >~/qc/ruby/compile_commands.json '[ .[] | select(
    (.file | endswith("/dln.c")) or  #
    (.file | endswith("/eval.c")) or  #
    (.file | endswith("/ext/pty/pty.c")) or  #
    (.file | endswith("/load.c")) or  #
    (.file | endswith("/main.c")) or  #
    (.file | endswith("/object.c")) or  #
    (.file | endswith("/vm_insnhelper.c")) or  #
    (.file | endswith("/vm.c")) or  #
    false
  ) ]'

# ------------------------------------------------------------------------------
# z scraps - jq - concatenate compile_commands.json

echo '[{"arguments": "cc", "directory": "/", "file": "a.c"}, {"arguments": "cc", "directory": "/", "file": "b.c"}]' > a.json
jq    '.'         a.json a.json  #  [{a}, {b}][{a}, {b}]
jq    '.[]'       a.json a.json  #   {a}  {b}  {a}  {b}
jq    '[ .[] ]'   a.json a.json  #  [{a}, {b}][{a}, {b}]  元通り; それぞれ独立に処理されてしまう
# # --slurp/-s Instead of running the filter for each JSON object in the input, read the entire input stream into a large array and run the filter just once.
jq -s '.'         a.json a.json  # [[{a}, {b}][{a}, {b}]]
jq -s '.[]'       a.json a.json  #  [{a}, {b}][{a}, {b}]
jq -s '.[][]'     a.json a.json  #   {a}  {b}  {a}  {b}
jq -s '[ .[][] ]' a.json a.json  #  [{a}, {b}, {a}, {b}]
jq -s '[ .[][] ]' a.json a.json a.json  #  [{a}, {b}, {a}, {b}, {a}, {b}]

jq    'add' a.json  #       {b}
jq -s 'add' a.json  # [{a}, {b}]
jq -s 'add' a.json a.json a.json  # [{a}, {b}, {a}, {b}, {a}, {b}]

# ------------------------------------------------------------------------------
# z scraps - jq - pandoc

'
@beg:pandoc_table
> |**col1** |col2
> |---      |---
> |val1     | **`val2`**
@end:pandoc_table
'
c.bash bef pandoc_table /home/wsh/sh/c.bash | pandoc -t json
# Recursive Descent: .. (recurse)
c.bash bef pandoc_table /home/wsh/sh/c.bash | pandoc -t json | jq -c '.. | iterables'
c.bash bef pandoc_table /home/wsh/sh/c.bash | pandoc -t json | jq -c '.. | scalars'
c.bash bef pandoc_table /home/wsh/sh/c.bash | pandoc -t json | jq -c '.. | arrays'
c.bash bef pandoc_table /home/wsh/sh/c.bash | pandoc -t json | jq -c '.. | objects'
c.bash bef pandoc_table /home/wsh/sh/c.bash | pandoc -t json | jq -c '.. | .t?'
c.bash bef pandoc_table /home/wsh/sh/c.bash | pandoc -t json | jq -c '.. | select(.t?=="Strong").c'  # [{"t":"Str","c":"col1"}]  [{"t":"Code","c":[["",[],[]],"val2"]}]

# ------------------------------------------------------------------------------
# z scraps - jq - scrapbox.json sort by title

# @ref:jq-scrapbox.json
jq <~/doc/scrapbox.json '.'              # {"name": "wataash", "displayName": "wataash", "exported": 1616609828, "pages": [...]}
jq <~/doc/scrapbox.json 'del(.pages)'    # {"name": "wataash", "displayName": "wataash", "exported": 1616609828}
jq <~/doc/scrapbox.json '.pages'
jq <~/doc/scrapbox.json '.pages | sort_by(.title)'
jq <~/doc/scrapbox.json '.pages = null'  # {"name": "wataash", "displayName": "wataash", "exported": 1616609828, "pages": null}
jq <~/doc/scrapbox.json '.pages = (.pages | sort_by(.title))'  # {"name": "wataash", "displayName": "wataash", "exported": 1616609828, "pages": [...]}
jq <~/doc/scrapbox.json '.pages = (.pages | sort_by(.title))' | sponge ~/doc/scrapbox.json

# ------------------------------------------------------------------------------
# z scraps - jq
# https://stedolan.github.io/jq/manual/

# ------------------------------------------------------------------------------
# z scraps - jq - Invoking jq

# ------------------------------------------------------------------------------
# z scraps - jq - Basic filters

# ------------------------------------------------------------------------------
# z scraps - jq - Types and Values

# ------------------------------------------------------------------------------
# z scraps - jq - Builtin operators and functions

# Addition: +
# > Strings are added by being joined into a larger string.
echo '["foo", "bar"]' | jq '.[0] + .[1]'  # "foobar"
echo '["foo", 42]'    | jq '.[0] + .[1]'  # jq: error (at <stdin>:1): string ("foo") and number (42) cannot be added
echo '["foo", 42]'    | jq '.[0] + (.[1] | tostring)'  # "foo42"
echo '["foo", 42]'    | jq '"\(.[0])\(.[1])"'          # "foo42"
echo '["foo", 42]'    | jq '"\(.[0]) \(.[1])"'         # "foo 42"

# select(boolean_expression)
# compdb
# https://stackoverflow.com/a/26701851/4085441
jq <compile_commands.json.linux '  .[] | select(.file | contains("gcov"))'
jq <compile_commands.json.linux '[ .[] | select(.file | contains("gcov")) ]'
jq <compile_commands.json.linux '[ .[] | select(.file | contains("gcov")) ]' > compile_commands.json
jq <compile_commands.json.linux '[ .[] | select(.file | contains("fortran") | not ) ]' > compile_commands.json

# ------------------------------------------------------------------------------
# z scraps - jq - Conditionals and Comparisons

# ------------------------------------------------------------------------------
# z scraps - jq - Regular expressions (PCRE)

# ------------------------------------------------------------------------------
# z scraps - jq - Advanced features

# ------------------------------------------------------------------------------
# z scraps - jq - Math

# ------------------------------------------------------------------------------
# z scraps - jq - I/O

# ------------------------------------------------------------------------------
# z scraps - jq - Streaming

# ------------------------------------------------------------------------------
# z scraps - jq - Assignment

# ------------------------------------------------------------------------------
# z scraps - jq - Modules

# ------------------------------------------------------------------------------
# z scraps - jq - Colors

# ------------------------------------------------------------------------------
# z scraps - node -e
# @ref:bash-node

# read file ?? stdin
node -e 'const txt = fs.readFileSync(process.argv[1] ?? "/dev/stdin", "utf8"); process.stdout.write(txt)' </etc/hostname
node -e 'const txt = fs.readFileSync(process.argv[1] ?? "/dev/stdin", "utf8"); process.stdout.write(txt)'  /etc/hostname _arg2

# read file ?? stdin - __filename
node -e "console.log(__filename)"                                                       # [eval]
node -e "console.log(__filename)"                     --input-type=commonjs             # [eval]
node -e "console.log(__filename)"                     --input-type=module               # ReferenceError: __filename is not defined in ES module scope
node -p "            __filename "                                                       # [eval]
node -p "            __filename "                     --input-type=commonjs             # [eval]
node -p "            __filename "                     --input-type=module               # ReferenceError: __filename is not defined in ES module scope
echo    "console.log(__filename)"              | node                                   # [stdin]
echo    "console.log(__filename)"              | node                                   # [stdin]
echo    "console.log(__filename)"              | node --input-type=commonjs             # [stdin]
echo    "console.log(__filename)"              | node --input-type=module               # ReferenceError: __filename is not defined in ES module scope
echo    "console.log(__filename)" >/tmp/a.js  && node                       /tmp/a.js   # /tmp/a.js
echo    "console.log(__filename)" >/tmp/a.js  && node --input-type=commonjs /tmp/a.js   # /tmp/a.js  --input-type は無視されてるっぽい
echo    "console.log(__filename)" >/tmp/a.js  && node --input-type=module   /tmp/a.js   # /tmp/a.js  --input-type は無視されてるっぽい
echo    "console.log(__filename)" >/tmp/a.mjs && node                       /tmp/a.mjs  # ReferenceError: __filename is not defined in ES module scope
echo    "console.log(__filename)" >/tmp/a.mjs && node --input-type=commonjs /tmp/a.mjs  # Error [ERR_INPUT_TYPE_NOT_ALLOWED]: --input-type can only be used with string input via --eval, --print, or STDIN
echo    "console.log(__filename)" >/tmp/a.mjs && node --input-type=module   /tmp/a.mjs  # Error [ERR_INPUT_TYPE_NOT_ALLOWED]: --input-type can only be used with string input via --eval, --print, or STDIN

# read file ?? stdin - process.argv
node -e "console.log(__filename, process.argv)"                                   arg1 arg2  # [eval]    [ '/usr/bin/node', 'arg1', 'arg2' ]
echo    "console.log(__filename, process.argv)"              | node                          # [stdin]   [ '/usr/bin/node' ]
echo    "console.log(__filename, process.argv)"              | node            -             # [stdin]   [ '/usr/bin/node', '-' ]
echo    "console.log(__filename, process.argv)"              | node               arg1 arg2  # Error: Cannot find module '/home/wsh/qjs/tesjs/arg1'
echo    "console.log(__filename, process.argv)"              | node            -  arg1 arg2  # [stdin]   [ '/usr/bin/node', '-', 'arg1', 'arg2' ]
echo    "console.log(__filename, process.argv)" >/tmp/a.js  && node /tmp/a.js     arg1 arg2  # /tmp/a.js [ '/usr/bin/node', '/tmp/a.js', 'arg1', 'arg2' ]
echo    "console.log(__filename, process.argv)" >/tmp/a.js  && node /tmp/a.js  -- arg1 arg2  # /tmp/a.js [ '/usr/bin/node', '/tmp/a.js', '--', 'arg1', 'arg2' ]
echo    "console.log(            process.argv)" >/tmp/a.mjs && node /tmp/a.mjs    arg1 arg2  #           [ '/usr/bin/node', '/tmp/a.mjs',       'arg1', 'arg2' ]
echo    "console.log(            process.argv)" >/tmp/a.mjs && node /tmp/a.mjs -- arg1 arg2  #           [ '/usr/bin/node', '/tmp/a.mjs', '--', 'arg1', 'arg2' ]

# variables
# https://stackoverflow.com/questions/31173473/list-all-global-variables-in-node-js

node -e "console.dir(Object.getOwnPropertyNames(globalThis), {maxArrayLength: null})"                              a b >/tmp/node.e   # [Object Function ... Response (assert async_hooks ... fs ... zlib) __filename module exports __dirname require]
echo    "console.dir(Object.getOwnPropertyNames(globalThis), {maxArrayLength: null})" >/tmp/a.js && node /tmp/a.js a b >/tmp/node.a   # [Object Function ... Response                                                                                 ]
echo    "console.dir(Object.getOwnPropertyNames(globalThis), {maxArrayLength: null})"             | node    -      a b >/tmp/node.s   # [Object Function ... Response                                      __filename module exports __dirname require]

# stdin

rm -f /tmp/node.stdin.empty           && echo -n $''           >/tmp/node.stdin.empty
rm -f /tmp/node.stdin.nl              && echo -n $'\n'         >/tmp/node.stdin.nl
rm -f /tmp/node.stdin.nl_nl           && echo -n $'\n\n'       >/tmp/node.stdin.nl_nl
rm -f /tmp/node.stdin.a               && echo -n $'a'          >/tmp/node.stdin.a
rm -f /tmp/node.stdin.a_nl            && echo -n $'a\n'        >/tmp/node.stdin.a_nl
rm -f /tmp/node.stdin.a_nl_nl         && echo -n $'a\n\n'      >/tmp/node.stdin.a_nl_nl
rm -f /tmp/node.stdin.a_nl_nl_z       && echo -n $'a\n\nz'     >/tmp/node.stdin.a_nl_nl_z
rm -f /tmp/node.stdin.a_nl_nl_z_nl    && echo -n $'a\n\nz\n'   >/tmp/node.stdin.a_nl_nl_z_nl
rm -f /tmp/node.stdin.a_nl_nl_z_nl_nl && echo -n $'a\n\nz\n\n' >/tmp/node.stdin.a_nl_nl_z_nl_nl
for f in $(ls -tr /tmp/node.stdin.*); do
  echo -en "\e[32m$f\e[0m "
  cat $f | xxd
  cat $f | xxd
  node -e 'process.stdin.on("data", (data) => process.stdout.write(data.toString()))' <"$f" | xxd
  node -e 'const txt = fs.readFileSync("/dev/stdin", "utf8");
    process.stdout.write(txt);' <"$f" | xxd
done
#/tmp/node.stdin.empty
#/tmp/node.stdin.nl              00000000: 0a                                       .
#/tmp/node.stdin.nl_nl           00000000: 0a0a                                     ..
#/tmp/node.stdin.a               00000000: 61                                       a
#/tmp/node.stdin.a_nl            00000000: 610a                                     a.
#/tmp/node.stdin.a_nl_nl_z       00000000: 610a 0a7a                                a..z
#/tmp/node.stdin.a_nl_nl         00000000: 610a 0a                                  a..
#/tmp/node.stdin.a_nl_nl_z_nl    00000000: 610a 0a7a 0a                             a..z.
#/tmp/node.stdin.a_nl_nl_z_nl_nl 00000000: 610a 0a7a 0a0a                           a..z..

# ------------------------------------------------------------------------------
# z scraps - os

if [ "$(uname -s)" = 'Darwin' ]; then
  :
fi

# ------------------------------------------------------------------------------
# z scraps - pipe stderr

# pipe stderr
# pipe to stderr
# stderr pipe
# stderr to pipe
# tee sed

echo 123 | tee /dev/stderr 2> >(sed -Eu -e "s/^/\x1b[31m[foo] /" -e "s/\$/\x1b[0m/" >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu -e "s/^/\x1b[32m[foo] /" -e "s/\$/\x1b[0m/" >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu -e "s/^/\x1b[33m[foo] /" -e "s/\$/\x1b[0m/" >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu -e "s/^/\x1b[34m[foo] /" -e "s/\$/\x1b[0m/" >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu -e "s/^/\x1b[35m[foo] /" -e "s/\$/\x1b[0m/" >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu -e "s/^/\x1b[36m[foo] /" -e "s/\$/\x1b[0m/" >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu -e "s/^/\x1b[37m[foo] /" -e "s/\$/\x1b[0m/" >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu 's/^(.*)$/\x1b[31m[foo] \1\x1b[m/' >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu 's/^(.*)$/\x1b[32m[foo] \1\x1b[m/' >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu 's/^(.*)$/\x1b[33m[foo] \1\x1b[m/' >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu 's/^(.*)$/\x1b[34m[foo] \1\x1b[m/' >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu 's/^(.*)$/\x1b[35m[foo] \1\x1b[m/' >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu 's/^(.*)$/\x1b[36m[foo] \1\x1b[m/' >&2) | sed -E 's/^/[stdout] /'
echo 123 | tee /dev/stderr 2> >(sed -Eu 's/^(.*)$/\x1b[37m[foo] \1\x1b[m/' >&2) | sed -E 's/^/[stdout] /'
echo $'123\n456' | tee /dev/stderr 2> >(sed -Ez 's/\n/ NL /'g >&2; echo >&2) | sed -E 's/^/[stdout] /'
echo $'123\n456' | tee /dev/stderr 2> >(sed -Ez 's/\n/\\n/g' >&2; echo >&2) | sed -E 's/^/[stdout] /'

# ------------------------------------------------------------------------------
# z scraps - self path

# https://stackoverflow.com/a/34208365/4085441
readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "$0"
DIR=$(dirname "$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "$0")")

# ------------------------------------------------------------------------------
# z scraps - set -x - mask credentials password

export PASSWORD=foo
set -x
(
  BASH_XTRACEFD=$fd_xtrace
  echo "$PASSWORD" | sha1sum
) {fd_xtrace}> >(node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").replaceAll(process.env.PASSWORD, "$PASSWORD".replaceAll("$", "$$$$")))' >&2)

# TODO: PASSWORD が環境変数でない場合; node に process.argv として渡せば良さそうだが、そのxtraceを消すのも面倒

# ------------------------------------------------------------------------------
# z scraps - set -x - コマンドを実行させる度にsleepさせて標準出力・エラーが出力されるのを待つ

exec {FD_DEVNULL}>/dev/null
BASH_XTRACEFD=$FD_DEVNULL
PS4='$(sleep 0.001)'
set -x

# ------------------------------------------------------------------------------
# z scraps - signal - for loop ^C

tail -F /tmp/strace.out
strace -f -o /tmp/strace.out -- sh
# set +m
for i in 1 2 3; do echo "$i";                                        sleep 10; done  # ^C -> 終了
for i in 1 2 3; do echo "$i"; ssh -T -oControlMaster=no localhost -- sleep 10; done  # ^C -> 次のループ (-T は無くても同じ; 明示的にした) set +m だと終了する

# wait4(2) の結果を見て、killed by signal ならforループ終了するようだ
# bash manual に記述は見つからなかった; POSIX定義か？

#951095 execve("/usr/bin/sh", ["sh"], 0x7ffe590bd290 /* 88 vars */) = 0
sleep:
#951171 execve("/usr/bin/sleep", ["sleep", "10"], 0x55895e1257d8 /* 88 vars */) = 0
#951171 clock_nanosleep(CLOCK_REALTIME, 0, {tv_sec=10, tv_nsec=0}, 
(ctrl-C)
#NULL) = ? ERESTART_RESTARTBLOCK (Interrupted by signal)
#951171 --- SIGINT {si_signo=SIGINT, si_code=SI_KERNEL} ---
#951171 +++ killed by SIGINT +++
#951095 <... wait4 resumed>[{WIFSIGNALED(s) && WTERMSIG(s) == SIGINT}], WSTOPPED, NULL) = 951171
#951095 --- SIGCHLD {si_signo=SIGCHLD, si_code=CLD_KILLED, si_pid=951171, si_uid=1000, si_status=SIGINT, si_utime=0, si_stime=0} ---
#951095 rt_sigreturn({mask=[]})          = 951171
#951095 ioctl(10, TIOCSPGRP, [951095])   = 0
#951095 rt_sigprocmask(SIG_BLOCK, ~[RTMIN RT_1], [], 8) = 0
ssh sleep:
#951314 execve("/usr/bin/ssh", ["ssh", "-T", "-oControlMaster=no", "localhost", "--", "sleep", "10"], 0x55895e125a38 /* 88 vars */) = 0
#951314 select(7, [3 4], [], NULL, {tv_sec=10, tv_usec=0}
(ctrl-C)
#) = ? ERESTARTNOHAND (To be restarted if no handler)
#951314 --- SIGINT {si_signo=SIGINT, si_code=SI_KERNEL} ---
#951314 rt_sigreturn({mask=[]})          = -1 EINTR (Interrupted system call)
#951314 rt_sigaction(SIGWINCH, {sa_handler=SIG_DFL, sa_mask=~[RTMIN RT_1], sa_flags=SA_RESTORER|SA_RESTART, sa_restorer=0x7f1ebddda090}, {sa_handler=0x555f3e282970, sa_mask=~[KILL STOP RTMIN RT_1], sa_flags=SA_RESTORER|SA_RESTART, sa_restorer=0x7f1ebddda090}, 8) = 0
...
#951314 exit_group(0)                    = ?
#951314 +++ exited with 0 +++
#951095 <... wait4 resumed>[{WIFEXITED(s) && WEXITSTATUS(s) == 0}], WSTOPPED, NULL) = 951314
#951095 --- SIGCHLD {si_signo=SIGCHLD, si_code=CLD_EXITED, si_pid=951314, si_uid=1000, si_status=0, si_utime=0, si_stime=0} ---
#951095 rt_sigreturn({mask=[]})          = 951314
#951095 ioctl(10, TIOCSPGRP, [951095])   = 0
#951095 write(1, "2\n", 2)               = 2

# @ref:sh-for-loop-SIGINT

# ssh sleep でもループ抜けたい場合
# ssh が ctrl-C で non-zero で終了することに依存
(
  set -e
  for i in 1 2 3; do echo "$i"; ssh -T -oControlMaster=no localhost -- sleep 10; done
)

TODO: trap 'echo " SIGINT $$"' SIGINT

# ------------------------------------------------------------------------------
# z scraps - source - include guard

if ! [[ -v _INCLUDE_GUARD_BASH ]]; then
    return
fi
_INCLUDE_GUARD_BASH=1

# ------------------------------------------------------------------------------
# z scraps - stop.sh

#!/bin/bash

echo kill -STOP $$
kill -STOP $$
# here, argv[0] (NOTE: this is not bash's $0) is "bash"
exec "$@"

# argv[0] を "stop-sh" にする
# $@ に " が含まれているとバグる
#
#cat <<EOF > /tmp/stop.sh.tmp
#echo "\$\$ (stop-sh \$0): kill -STOP \$\$"
#kill -STOP \$\$
#echo "\$\$ (stop-sh \$0): exec $@"
#exec $@
#EOF
#
## strace -f -- stop.sh
## [pid 3257274] execve("/usr/bin/bash", ["stop-sh", "/tmp/stop.sh.tmp"], 0x561ea88520f0 /* 0 vars */) = 0
#echo "$$ (bash $0): execve(\".../bash\", [\"stop-sh\", \"/tmp/stop.sh.tmp\"])"
#exec -a stop-sh -c bash /tmp/stop.sh.tmp

# ------------------------------------------------------------------------------
# z scraps - string - split

IFS=$'\t' read -ra tmp <<<$(echo -e "\tfoo\t\tbar\t")
declare -p tmp
#declare -a tmp=([0]="foo" [1]="bar")

# ------------------------------------------------------------------------------
# z scraps - string - starts with / ends with
# start with start_with starts with starts_with
# end with end_with ends with ends_with
# prefix suffix

[[ $var =~ ^*"Z"$ ]]
[[ $var =~ ^"A"*$ ]]

# ------------------------------------------------------------------------------
# z scraps - subshell

# > $
# > ($$) ... not the subshell
# > BASHPID
# > This differs from $$ under certain circumstances, such as subshells

echo $$ $BASHPID $BASH_SUBSHELL  # same, 0
( echo $$ $BASHPID $BASH_SUBSHELL )
( echo $$ $BASHPID $BASH_SUBSHELL ) | cat
{ echo $$ $BASHPID $BASH_SUBSHELL; }  # same, 0 (no subshell)
{ echo $$ $BASHPID $BASH_SUBSHELL; } | cat
{ echo $$ $BASHPID $BASH_SUBSHELL; } &
echo $$ $BASHPID $BASH_SUBSHELL &  # same(!), 1
echo $$ $BASHPID $BASH_SUBSHELL & echo $$ $BASHPID $BASH_SUBSHELL &

echo $BASH_SUBSHELL; ( echo $BASH_SUBSHELL; (echo $BASH_SUBSHELL; (echo $BASH_SUBSHELL)) )  # 0 1 2 3

# subshellで set -e を使うのはムズい
# https://mywiki.wooledge.org/BashFAQ/105
# https://github.com/koalaman/shellcheck/issues/1484

cat <<'EOS' | bash
set -e
(
  false  # exits at here
  echo 1
)
echo 2
EOS

cat <<'EOS' | bash
set -e
(
  false
  echo 1  # reach!
) || true
echo 2  # reach
EOS

# for のredirectionはsubshellにならないっぽい
for _once in _; do
  echo $$ $BASHPID $BASH_SUBSHELL $fd  # same, 0
done {fd}>/dev/null

# ------------------------------------------------------------------------------
# z scraps - variables - dynamic variable name assignment

nameref() {
  local -n nameref_local_scalar=local_scalar
  local -n nameref_local_indexed_array=local_indexed_array
  local -n nameref_local_associative_array=local_associative_array
  local -n nameref_global_scalar=global_scalar
  local -n nameref_global_indexed_array=global_indexed_array
  local -n nameref_global_associative_array=global_associative_array
  nameref_local_scalar="y"
  nameref_local_indexed_array+=("y")
  nameref_local_associative_array["z"]="w"
  nameref_global_scalar="y"
  nameref_global_indexed_array+=("y")
  nameref_global_associative_array["z"]="w"
}
others() {
  printf -v ...TODO
}
fn () {
  local local_scalar="x"
  local local_indexed_array=("x")
  local local_associative_array=(["x"]="y")
  global_scalar="x"
  global_indexed_array=("x")
  global_associative_array=(["x"]="y")
  $1
  echo "---------- $1"
  echo "local_scalar: $local_scalar"
  echo "local_indexed_array: ${local_indexed_array[*]}"
  echo "local_associative_array: ${local_associative_array[*]}"
  echo "global_scalar: $global_scalar"
  echo "global_indexed_array: ${global_indexed_array[*]}"
  echo "global_associative_array: ${global_associative_array[*]}"
}
fn "nameref"

# ------------------------------------------------------------------------------
# z scraps - z end

fi  # if false

# ------------------------------------------------------------------------------
# EOF
