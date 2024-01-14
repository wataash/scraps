#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2022-2023 Wataru Ashihara <wataash0607@gmail.com>
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
if [[ "${#BASH_SOURCE[@]}" == 0 ]]; then
  # bash <c.bash
  C_BASH_DO_MAIN="yes"
elif [[ "${#BASH_SOURCE[@]}" == 1 ]]; then
  C_BASH_DO_MAIN="yes"  # c.bash / bash c.bash
  [[ -v BASH_EXECUTION_STRING ]] && C_BASH_DO_MAIN="no"  # bash -c "source /home/wsh/sh/c.bash"
  # likely [[ $(realpath "${BASH_SOURCE[-1]}") == "/home/wsh/sh/c.bash" ]]
elif [[ "${#BASH_SOURCE[@]}" == 2 ]]; then
  # source c.bash
  C_BASH_DO_MAIN="no"
elif [[ "${#BASH_SOURCE[@]}" == 3 ]]; then
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
set -eu
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

unreachable() {
  die 1 "unreachable: $(caller1): $(sed -n "${BASH_LINENO[0]}"p "$(self_real_path)")"
}

# ------------------------------------------------------------------------------
# bats setup

[[ $C_BASH_IN_BATS == "yes" ]] && bats_require_minimum_version 1.8.0

[[ $C_BASH_IN_BATS == "yes" ]] && [ -z "$BATS_TEST_NUMBER" ] && {
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

  [[ $# != 0 ]] && [[ $1 = "-h" || $1 = "-help" || $1 = "--help" ]] && echo "$usage" && exit 0

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
      (($# == 0)) && return 0
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
      (($# == 0)) && return 0
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
  set -- "arg1" "arg2" "argv1" "argv2" && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]] && [[ ${#ARGV[@]} == 2 ]] && [[ ${ARGV[*]} == "argv1 argv2" ]]                              || bats_run_debug_fail >&3
  set -- "arg1" "arg2" "argv1"         && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == "arg2" ]] && [[ ${#ARGV[@]} == 1 ]] && [[ ${ARGV[*]} == "argv1"       ]]                              || bats_run_debug_fail >&3
  set -- "arg1" "arg2"                 && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARGV..." missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set -- "arg1"                        && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARG2" missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]]    || bats_run_debug_fail >&3
  set -- "arg1" ""                     && run -2 --separate-stderr                     arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@"          && [[ $output == "" ]] && [[ ${stderr_lines[0]} =~ 'error: required argument: "ARGV..." missing' ]] && [[ ${stderr_lines[1]} =~ ^"usage: " ]] || bats_run_debug_fail >&3
  set -- "arg1" "" ""                  && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]] && [[ ${#ARGV[@]} == 1 ]] && [[ ${ARGV[*]} == ""            ]]                              || bats_run_debug_fail >&3
  set -- "arg1" "" "" ""               && local ARG1="" ARG2="" && local -a ARGV=() && arg_parse "$usage" "ARG1 ARG2 ARGV..." "$@" >&3 2>&3 && [[ $ARG1 == "arg1" ]] && [[ $ARG2 == ""     ]] && [[ ${#ARGV[@]} == 2 ]] && [[ ${ARGV[*]} == " "           ]]                              || bats_run_debug_fail >&3

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
  [[ $# != 0 ]] && [[ $1 = "-h" || $1 = "-help" || $1 = "--help" ]] && echo "$usage" && exit 0
  [[ $# != 0 ]] && err 0 "error: excess argument(s): $*" && echo "$usage" >&2 && exit 2

  # long usage
  local -r usage=$(cat <<EOS
usage: $PROG 0template [-h | --help]
EOS
)
  # ...
}

# ------------------------------------------------------------------------------
# command - apt_changelog @pub

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
# command - cfl - lib @pub

cfl_env_check() {
  local ok="true"
  [[ ${CONFLUENCE_URL+defined} = defined ]] || err 1 'environment variable CONFLUENCE_URL is not set' || ok="false"
  [[ ${CONFLUENCE_USER+defined} = defined ]] || err 1 'environment variable CONFLUENCE_USER is not set' || ok="false"
  [[ ${CONFLUENCE_PASS+defined} = defined ]] || err 1 'environment variable CONFLUENCE_PASS is not set' || ok="false"
  [[ $ok == "true" ]] || exit 1
  [[ $CONFLUENCE_URL != "${CONFLUENCE_URL%/}" ]] && {
    log_debug "remove trailing slash in CONFLUENCE_URL: $CONFLUENCE_URL -> ${CONFLUENCE_URL%/}"
    CONFLUENCE_URL=${CONFLUENCE_URL%/}
  }
  return 0
}

# ------------------------------------------------------------------------------
# command - cfl_curl @pub

define_command cfl_curl
cmd::cfl_curl() {
  cfl_env_check
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  (
    BASH_XTRACEFD=$fd_xtrace
    ((LOG_LEVEL >= LOG_DEBUG)) && set -x
    env LD_LIBRARY_PATH="$HOME/opt/curl8/lib/" /home/wsh/opt/curl8/bin/curl --fail-with-body -Ss -u "$CONFLUENCE_USER:$CONFLUENCE_PASS" "$@" >/tmp/c.bash.d/cfl_curl.out || die 1 "cfl_curl failed; body: $(cat /tmp/c.bash.d/cfl_curl.out)"
  ) {fd_xtrace}> >(node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").replaceAll(process.env.CONFLUENCE_PASS, "$CONFLUENCE_PASS".replaceAll("$", "$$$$")))' | sed -E 's/^(.{160}).*$/\1.../' >&2)
  jq -c "." /tmp/c.bash.d/cfl_curl.out
}
false && pre_main() {
  cmd::cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content/1"
}

# ------------------------------------------------------------------------------
# command - cfl_page_get_content @pub

# echo:
# title
# storage
define_command cfl_page_get_content
cmd::cfl_page_get_content() {
  local -r usage="usage: $PROG cfl_page_get_content [-h | --help] ID"
  local ID="" && arg_parse "$usage" "ID" "$@"
  [[ $ID =~ ^[0-9]+$ ]] || err 1 "ID must be a number: $ID"
  cfl_env_check
  (set -o pipefail; ((LOG_LEVEL >= LOG_INFO)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content/$ID?expand=body.storage" | jq -e >/tmp/c.bash.d/cfl_page_get_content.json)
  jq -er </tmp/c.bash.d/cfl_page_get_content.json ".title"
  jq -er </tmp/c.bash.d/cfl_page_get_content.json ".body.storage.value"
}

# ------------------------------------------------------------------------------
# command - cfl_page_get_id @pub

define_command cfl_page_get_id
cmd::cfl_page_get_id() {
  local -r usage="usage: $PROG cfl_page_get_id [-h | --help] SPACE_KEY TITLE"
  local SPACE_KEY="" TITLE="" && arg_parse "$usage" "SPACE_KEY TITLE" "$@"
  cfl_env_check
  (set -o pipefail; (((LOG_LEVEL >= LOG_INFO)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content?spaceKey=$SPACE_KEY&title=$TITLE") | jq -er ".results[0].id")
}

# ------------------------------------------------------------------------------
# command - cfl_page_rm @pub

define_command cfl_page_rm
cmd::cfl_page_rm() {
  local -r usage="usage: $PROG cfl_page_rm [-h | --help] ID"
  local ID="" && arg_parse "$usage" "ID" "$@"
  cfl_env_check
  ( ((LOG_LEVEL >= LOG_INFO)) && set -x; cmd cfl_curl -X DELETE "$CONFLUENCE_URL/rest/api/content/$ID")
}

# ------------------------------------------------------------------------------
# command - cfl_page_update @pub

define_command cfl_page_update
cmd::cfl_page_update() {
  local -r usage="usage: $PROG cfl_page_update [-h | --help] ID TITLE [FILE]"
  local ID="" TITLE="" FILE="" && arg_parse "$usage" "ID TITLE [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  [[ $ID =~ ^[0-9]+$ ]] || err 1 "ID must be a number: $ID"
  cfl_env_check
  ( ((LOG_LEVEL >= LOG_INFO)) && set -x; cmd cfl_curl -X GET "$CONFLUENCE_URL/rest/api/content/$ID") | jq -e >/tmp/c.bash.d/cfl_page_update.1.json
  local -i ver
  ver=$(jq -er ".version.number" /tmp/c.bash.d/cfl_page_update.1.json)
  ((ver++))
  jo -p -d. -- version.number="$ver" title="$TITLE" type=page body.storage.value=@"$FILE" body.storage.representation=storage >/tmp/c.bash.d/cfl_page_update.put.json
  ( ((LOG_LEVEL >= LOG_INFO)) && set -x; cmd cfl_curl -X PUT -H "Content-Type: application/json" -d @/tmp/c.bash.d/cfl_page_update.put.json "$CONFLUENCE_URL/rest/api/content/$ID") | jq -e >/tmp/c.bash.d/cfl_page_update.2.json
}

# ------------------------------------------------------------------------------
# command - cmd_intercept @pub

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
cmd::discharging_checker() {
  local -r usage="usage: $PROG discharging_checker [-h | --help]"
  arg_parse "$usage" "" "$@"
  local -ir BASE_INTERVAL=240  # 4min, 8min, 16min, 32min, 64min, ...

  # without this: notify-send: Cannot autolaunch D-Bus without X11 $DISPLAY
  # @ref:no-X11-DBUS_SESSION_BUS_ADDRESS
  DBUS_SESSION_BUS_ADDRESS=$(strings /proc/"$(pgrep -u wsh gnome-session | head -1)"/environ | grep -P -o "(?<=DBUS_SESSION_BUS_ADDRESS=).+")  # unix:path=/run/user/1000/bus
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
# command - file_sync_watch @pub

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
# command - file_timestamp @pub

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
# command - git_status_repos @pub

define_command git_status_repos
cmd::git_status_repos() {
  local -r usage="usage: $PROG git_status_repos [-h | --help]"
  arg_parse "$usage" "" "$@"
  for d in \
      ~/qc/tesc/ \
      ~/qjs/tesjs/ \
      ~/qjs/tesjs/proj/kousu/ \
      ~/qpy/tespy/ \
      ~/qrb/tesrb/ \
      ~/qrs/tesrs/ \
  ; do
    echo "---------- $d ----------"
    cd "$d"
    # https://unix.stackexchange.com/questions/155046/determine-if-git-working-directory-is-clean-from-a-script
    git update-index -q --really-refresh
    git diff-index --quiet HEAD && continue
    git status -sb
  done
}

# ------------------------------------------------------------------------------
# command - grep_multiline (gm) @pub

# c.bash gm -P -m1 "^define_command grep_multiline" "cat" < /home/wsh/sh/c.bash
# c.bash gm -P -m1 "^define_command grep_multiline" "cat" < /home/wsh/sh/c.bash | sed '1d;$d'
# command - grep_multiline_greedy (gm_greedy) @pub

# c.bash gm_greedy -P "^define_command grep_multiline_greedy" "cat" < /home/wsh/sh/c.bash

define_command grep_multiline_greedy
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

define_command gm_greedy
cmd::gm_greedy() { cmd::grep_multiline_greedy "$@"; }

# ------------------------------------------------------------------------------
# command - journalctl @pub

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
# command - kill_clangd @pub

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
      [[ ${#alive_pids[@]} = 0 ]] && return 0
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
# command - kill_code_md_ext @pub

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
# command - linux_dmesg_time0 @pub

define_command linux_dmesg_time0
cmd::linux_dmesg_time0() {
  local -r usage="usage: dmesg | $PROG linux_dmesg_time0 [-h | --help]"
  arg_parse "$usage" "" "$@"
  sed -E s'/\[[0-9 ]{4}[0-9]\.[0-9]{6}\]/[    0.000000]/'
}

# ------------------------------------------------------------------------------
# command - linux_kern_config @pub

define_command linux_kern_config
cmd::linux_kern_config() {
  local -r usage="usage: $PROG linux_kern_config [-h | --help] [TARGET...]"
  local -a TARGET=() && arg_parse "$usage" "[TARGET...]" "$@"
  [[ ${#TARGET[@]} = 0 ]] && TARGET=(vmlinux modules compile_commands.json bindeb-pkg)
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
  [[ ${KBUILD_OUTPUT+defined} = defined ]] || case $PWD in
    "/home/wsh/qc/linux/focal-d"*)       export KBUILD_OUTPUT=/home/wsh/qc/linux/focal-build-d;;
    "/home/wsh/qc/linux/focal-build-d"*) export KBUILD_OUTPUT=/home/wsh/qc/linux/focal-build-d;;
    "/home/wsh/qc/linux/focal-r"*)       export KBUILD_OUTPUT=/home/wsh/qc/linux/focal-build-r;;
    "/home/wsh/qc/linux/focal-build-r"*) export KBUILD_OUTPUT=/home/wsh/qc/linux/focal-build-r;;
    *) die 1 "environment variable KBUILD_OUTPUT is not set / unknown PWD";;
  esac
  [[ ${KBUILD_OUTPUT+defined} = defined ]] || die 1 "environment variable KBUILD_OUTPUT is not set"
  case $KBUILD_OUTPUT in
    "/home/wsh/qc/linux/focal-build-d") log_info "debug";;
    "/home/wsh/qc/linux/focal-build-r") log_warning "release";;
    *) die 1 "unknown KBUILD_OUTPUT: $KBUILD_OUTPUT";;
  esac
  echo "$KBUILD_OUTPUT"
}

# ------------------------------------------------------------------------------
# command - linux_kern_initramfs @pub

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
# command - linux_kern_make @pub

# TODO: -d CONFIG_DEBUG_INFO_BTF でビルド時間短くなるかやってみる

define_command linux_kern_make
cmd::linux_kern_make() {
  local -r usage="usage: $PROG linux_kern_make [-h | --help] [TARGET...]"
  local -a TARGET=() && arg_parse "$usage" "[TARGET...]" "$@"
  [[ ${#TARGET[@]} = 0 ]] && TARGET=(vmlinux modules compile_commands.json bindeb-pkg)
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
# command - linux_kern_make_summary @pub

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
# command - net_if_rename @pub

# variable_diff: usage:
# variable_diff_1
# some commands...
# variable_diff_2

cmd::variable_diff_1() {
  declare -p > /tmp/c.bash.d/variable_diff.1
}

cmd::variable_diff_2() {
  declare -p > /tmp/c.bash.d/variable_diff.2
  delta /tmp/c.bash.d/variable_diff.1 /tmp/c.bash.d/variable_diff.2
}

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
# command - md_code_b64 @pub

: <<'DOC'
```sh
code
``` -> @__code_block__:YGBgc2gKY29kZQpgYGA=
DOC

define_command md_code_b64
cmd::md_code_b64() {
  local -r usage="usage: $PROG md_code_b64 [-h | --help]"
  arg_parse "$usage" "" "$@"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  node -e '
    let txt = fs.readFileSync("/dev/stdin", "utf8");
    for (const match of txt.matchAll(/^```(\w+)?[\s\S]+?^```$/gm)) {
      txt = txt.replace(match[0], `@__code_block__:${Buffer.from(match[0]).toString("base64")}`);
    }
    process.stdout.write(txt);'
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
# command - md_code_b64d @pub

define_command md_code_b64d
cmd::md_code_b64d() {
  local -r usage="usage: $PROG md_code_b64d [-h | --help]"
  arg_parse "$usage" "" "$@"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  node -e '
    let txt = fs.readFileSync("/dev/stdin", "utf8");
    for (const match of txt.matchAll(/^@__code_block__:(.+)$/gm)) {
      txt = txt.replace(match[0], Buffer.from(match[1], "base64").toString("utf8").replaceAll("$", "$$$$"));
    }
    process.stdout.write(txt);'
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
# command - md_sec @pub

define_command md_sec
cmd::md_sec() {
  local -r usage="usage: $PROG md_sec [-h | --help] SECTION"
  local SECTION="" && arg_parse "$usage" "SECTION" "$@"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  cmd md_code_b64 | node -e '
    const regExpEscape = ((string) => string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")); // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions ; $& means the whole matched string
    let txt = fs.readFileSync("/dev/stdin", "utf8") + "\0";
    const match = txt.match(new RegExp(`^(## ${regExpEscape(process.argv[1])}$[\\s\\S]*?)(?=(\r?\n## |\0))`, "m"));
    if (match !== null) process.stdout.write(match[1]);' "$SECTION" | cmd md_code_b64d
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
# command - md_secsp @pub
# sections starting with the specified prefix

define_command md_secsp
cmd::md_secsp() {
  local -r usage="usage: $PROG md_secsp [-h | --help] SECTION_PREFIX"
  local SECTION_PREFIX="" && arg_parse "$usage" "SECTION_PREFIX" "$@"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  cmd md_code_b64 | node -e '
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
  ' "$SECTION_PREFIX" | cmd md_code_b64d
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
# command - netbsd_makefile_expand_vars @pub

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

    if [ "$line" = "$line2" ]; then
      echo "$line2"
    else
      echo "$line2$(echo -e '\t')# $line"
    fi
  done
}

# ------------------------------------------------------------------------------
# command - smux @pub

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
cmd::spotify_code_to_token() {
  local -r usage="usage: $PROG spotify_code_to_token [-h | --help] REDIRECT_URI CODE"
  local REDIRECT_URI="" CODE="" && arg_parse "$usage" "REDIRECT_URI CODE" "$@"
  [[ ${SPOTIFY_APP_AUTH+defined} = defined ]] || die 1 "environment variable SPOTIFY_APP_AUTH is not set"
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
# command - spotify_say_song @pub

define_command spotify_say_song
cmd::spotify_say_song() {
  local -r usage="usage: $PROG spotify_say_song [-h | --help]"
  arg_parse "$usage" "" "$@"
  [[ ${SPOTIFY_TOKEN+defined} = defined ]] || die 1 "environment variable SPOTIFY_TOKEN is not set"

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
# command - strace_prettify @pub

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
# command - time_sub @pub

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
# command - txt_begin_end (be) @pub
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

define_command txt_begin_end
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

# alias
define_command be
cmd::be() { cmd::txt_begin_end "$@"; }

# ------------------------------------------------------------------------------
# command - txt_begin_end_fast (bef) @pub

define_command txt_begin_end_fast
cmd::txt_begin_end_fast() {
  local -r usage="usage: [... |] $PROG txt_begin_end_fast (bef) [-h | --help] NAME [FILE]"
  local NAME="" FILE="" && arg_parse "$usage" "NAME [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").match(new RegExp(`@beg:${process.argv[1]}\\b.*\r?\n([\\s\\S]*?\r?\n)^.*@end:${process.argv[1]}\\b`, "m"))[1]); // TODO: escape argv[1]' "$NAME" <"$FILE"
}

# alias
define_command bef
cmd::bef() { cmd::txt_begin_end_fast "$@"; }

# ------------------------------------------------------------------------------
# command - txt_begin_end_v (bev) @pub
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

define_command txt_begin_end_v
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

# alias
define_command bev
cmd::bev() { cmd::txt_begin_end_v "$@"; }

# ------------------------------------------------------------------------------
# command - txt_begin_end_v_fast (bevf) @pub
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

define_command txt_begin_end_v_fast
cmd::txt_begin_end_v_fast() {
  local -r usage="usage: [... |] $PROG txt_begin_end_v_fast (bevf) [-h | --help] NAME [FILE]"
  local NAME="" FILE="" && arg_parse "$usage" "NAME [FILE]" "$@"
  [[ $FILE == "" ]] && FILE="/dev/stdin"
  # shellcheck disable=SC2016  # Expressions don't expand in single quotes, use double quotes for that
  node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").replaceAll(new RegExp(`^.*@beg:${process.argv[1]}\\b.*\r?\n[\\s\\S]*?@end:${process.argv[1]}\\b.*(\r?\n|$)`, "gm"), ""))' "$NAME" <"$FILE"
}

# alias
define_command bevf
cmd::bevf() { cmd::txt_begin_end_v_fast "$@"; }

# ------------------------------------------------------------------------------
# command - txt_eval @pub

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
# command - txt_replace (rep) @pub

# c.bash rep "$(c.bash grep_multiline -P -m1 "^define_command grep_multiline" "cat" < /home/wsh/sh/c.bash)" "hi there" < /home/wsh/sh/c.bash > /tmp/c.bash.d/rep.test.bash
# delta /home/wsh/sh/c.bash /tmp/c.bash.d/rep.test.bash

define_command txt_replace
cmd::txt_replace() {
  local -r usage="usage: ... | $PROG txt_replace (rep) [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  # replaces only one
  # time node -e 'console.log(fs.readFileSync("/dev/stdin", "utf8").replace(process.argv[1], process.argv[2].replaceAll("$", "$$$$")))' foo bar
  # time python3 -c "import sys; print(sys.stdin.read().replace(sys.argv[1], sys.argv[2], 1), end='')" "$FROM" "$TO"
  python3 -c "import sys; print(sys.stdin.read().replace(sys.argv[1], sys.argv[2], 1), end='')" "$FROM" "$TO"
}

# alias
define_command rep
cmd::rep() { cmd::txt_replace "$@"; }

# compatibility
define_command replace
cmd::replace() { cmd::txt_replace "$@"; }

# ------------------------------------------------------------------------------
# command - txt_replace_all (repa) @pub

define_command txt_replace_all
cmd::txt_replace_all() {
  local -r usage="usage: ... | $PROG txt_replace_all (repa) [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  # node -e 'console.log(fs.readFileSync("/dev/stdin", "utf8").replaceAll(process.argv[1], process.argv[2].replaceAll("$", "$$$$")))' foo bar
  python3 -c "import sys; print(sys.stdin.read().replace(sys.argv[1], sys.argv[2]), end='')" "$FROM" "$TO"
}

# alias
define_command repa
cmd::repa() { cmd::txt_replace_all "$@"; }

# compatibility
define_command replace_all
cmd::replace_all() { cmd::txt_replace_all "$@"; }

# ------------------------------------------------------------------------------
# command - txt_replace_line (repl) @pub

define_command txt_replace_line
cmd::txt_replace_line() {
  local -r usage="usage: ... | $PROG txt_replace_line (repl) [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  python3 -c "import sys; [print(line.replace(sys.argv[1], sys.argv[2], 1), end='') for line in sys.stdin]" "$FROM" "$TO"  # not tested
}

# alias
define_command repl
cmd::repl() { cmd::txt_replace_line "$@"; }

# compatibility
define_command replace_line
cmd::replace_line() { cmd::txt_replace_line "$@"; }

# ------------------------------------------------------------------------------
# command - txt_replace_line_all (repla) @pub

define_command txt_replace_line_all
cmd::txt_replace_line_all() {
  local -r usage="usage: ... | $PROG txt_replace_line_all (repla) [-h | --help] FROM TO"
  local FROM="" TO="" && arg_parse "$usage" "FROM TO" "$@"
  local txt
  # node -e 'process.stdout.write(fs.readFileSync("/dev/stdin", "utf8").replaceAll(process.argv[1], process.argv[2].replaceAll("$", "$$$$")))' "$FROM" "$TO"  # not tested
  python3 -c "import sys; [print(line.replace(sys.argv[1], sys.argv[2]), end='') for line in sys.stdin]" "$FROM" "$TO"
}

# alias
define_command repla
cmd::repla() { cmd::txt_replace_line_all "$@"; }

# compatibility
define_command replace_line_all
cmd::replace_line_all() { cmd::txt_replace_line_all "$@"; }

# ------------------------------------------------------------------------------
# command - pty_qemu @pub

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
# command - pty_usb @pub

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
# command - qemu_net_setup @pub

define_command qemu_net_setup
cmd::qemu_net_setup() {
  local -r usage="usage: $PROG qemu_net_setup [-h | --help]"
  arg_parse "$usage" "" "$@"

  set -x

  # 2023-04-24 Mon wsh79
  # cat /proc/sys/net/ipv4/ip_forward
  # ssh ログイン後は 1 だが、startup 時は 0 だった
  [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == 1 ]] || echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward

  # @ref:qemu-bridge @ref:iptables-bridge

  sudo ip link add br100 type bridge; sudo ip link set br100 up; sudo ip address add 172.31.100.100/24 dev br100
  sudo ip link add br101 type bridge; sudo ip link set br101 up; sudo ip address add 172.31.101.100/24 dev br101
  sudo ip link add br102 type bridge; sudo ip link set br102 up; sudo ip address add 172.31.102.100/24 dev br102

  sudo nft add table ip nat0
  sudo nft 'add chain nat0 postrouting0 { type nat hook postrouting priority 100 ; }'
  sudo nft add rule ip nat0 postrouting0 ip saddr 172.31.100.0/24 ip daddr != 172.31.100.0/24 counter masquerade

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
cmd::qemu_pty() {
  cmd::pty_qemu "${@}"
}

# ------------------------------------------------------------------------------
# command - xargs_delay @pub

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
      if [[ $(echo "$now - ${line_latest_epochs[$line_]} > 0.5" | bc) = 1 ]]; then
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
# command - z_meta_commands_list @pub

define_command z_meta_commands_list
cmd::z_meta_commands_list() {
  local -r usage="usage: $PROG z_meta_commands_list [-h | --help]"
  arg_parse "$usage" "" "$@"
  for k in "${!_commands[@]}"; do
    echo "$k"
  done | sort
}

# ------------------------------------------------------------------------------
# command - z_meta_publish_self @pub

: <<'DOC'
c.bash -v z_meta_publish_self > ~/src/scraps/c.bash
cd ~/src/scraps/
git ...
DOC

define_command z_meta_publish_self
cmd::z_meta_publish_self() {
  local -r usage="usage: $PROG z_meta_publish_self [-h | --help]"
  arg_parse "$usage" "" "$@"
  local public_cmd="true"
  cmd bev "private_v" <"$(self_real_path)" | while IFS= read -r line; do  # `IFS=`: prevent removing leading/preceding spaces
    # # section @pub
    if [[ $line =~ ^#.+@pub$ ]]; then
      log_info "[public_cmd: $public_cmd -> true] $line"
      public_cmd="true"
    # # command - COMMAND  (private unless explicitly marked as @pub)
    # # section @private
    elif [[ $line =~ ^"# command - " ]] || [[ $line =~ ^#.+[@]private$ ]]; then
      log_info "[public_cmd: $public_cmd -> false] $line"
      public_cmd="false"
    else
      log_debug "$line"
    fi
    [[ $public_cmd = "false" ]] && continue
    [[ $line =~ [@]private_line ]] && continue
    echo "$line"
  done

  return 0
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
  cp ~/sh/c.bash ./z_meta_commands_list
  # TODO: -h
                run -2 --separate-stderr      ~/sh/c.bash                        && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr bash ~/sh/c.bash                        && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr      ./foo                              && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr bash ./foo                              && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr      /tmp/c.bash.d/foo                  && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -2 --separate-stderr bash /tmp/c.bash.d/foo                  && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
                run -0 --separate-stderr      ./z_meta_commands_list             && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
                run -0 --separate-stderr bash ./z_meta_commands_list             && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
                run -0 --separate-stderr      /tmp/c.bash.d/z_meta_commands_list && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
                run -0 --separate-stderr bash /tmp/c.bash.d/z_meta_commands_list && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -2 --separate-stderr      c.bash                             && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -2 --separate-stderr bash c.bash                             && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -2 --separate-stderr      foo                                && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -2 --separate-stderr bash foo                                && [[ $output == "" ]]                    && [[ $stderr =~ $'command not specified / no such command: foo\e[0m'.*"usage:" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -0 --separate-stderr      z_meta_commands_list               && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
  PATH=$PATH:./ run -0 --separate-stderr bash z_meta_commands_list               && [[ $output =~ ^$'0template\nagsafe' ]] && [[ $stderr == "" ]] || bats_run_debug_fail >&3
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

if not_yet && [ "$HAVE_UTIL_LINUX_GETOPT" = "yes" ]; then
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

[ $# != 0 ] && [[ $1 = "-h" || $1 = "-help" || $1 = "--help" ]] && top_usage && exit 0
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
"cmd::$COMMAND_" "$@"
exit $?
