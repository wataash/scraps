#!/usr/bin/env bash

# shellcheck disable=SC2317  # Command appears to be unreachable. Check usage (or ignore if invoked indirectly).

: <<'DOC'
mini CLIs

test:
tail -F /tmp/c.bash.tests.log
bats ~/sh/c.bash

usage error -> exit 2
https://git.savannah.gnu.org/cgit/bash.git/tree/shell.h?h=bash-5.2#n71 EX_USAGE - EX_SHERRBASE == 2 bash -c 'help --foo' -> 2
https://salsa.debian.org/kernel-team/initramfs-tools/-/blob/v0.142/mkinitramfs#L36                  mkinitramfs --foo    -> 2
https://go.googlesource.com/go/+/refs/tags/go1.20.1/src/cmd/go/main.go#235                          go foo               -> 2
DOC

BATS_LOGFILE=/tmp/c.bash.tests.log

if false; then
  # bats ~/sh/c.bash
  # #$0                /usr/local/libexec/bats-core/bats-exec-file
  # #${BASH_SOURCE[@]} /tmp/bats-run-ajyNME/bats.657971.src /usr/local/libexec/bats-core/bats-exec-file /usr/local/libexec/bats-core/bats-exec-file
  # #$0                /usr/local/libexec/bats-core/bats-exec-test
  # #${BASH_SOURCE[@]} /tmp/bats-run-ajyNME/bats.657971.src /usr/local/lib/bats-core/preprocessing.bash /usr/local/libexec/bats-core/bats-exec-test
  # #$0                /home/wsh/sh/c.bash
  # #${BASH_SOURCE[@]} /home/wsh/sh/c.bash
  {
    echo "\$0                $0"
    echo "\${BASH_SOURCE[0]} ${BASH_SOURCE[0]}"
    echo "\${BASH_SOURCE[*]} ${BASH_SOURCE[*]}"
  } >>$BATS_LOGFILE

  # ln -s c.bash /tmp/c
  # /tmp/c
  # # $0          : /tmp/c
  # # realpath $0 : .../c.bash
fi
[ "$(basename "$(realpath "$0")")" = 'c.bash' ] && IN_BATS='no' || IN_BATS='yes'

if [[ $IN_BATS = 'no' ]]; then

set -Ceu

fi

# ------------------------------------------------------------------------------
# lib

PROG=$(basename "$0")

# shellcheck disable=SC2154  # * is referenced but not assigned.
bats_run_debug() {
  echo "BATS_RUN_COMMAND $BATS_RUN_COMMAND"
  echo "status: $status"
  echo -en '\e[37m'
  # echo "output: $output"
  local i
  # echo "lines of lines: ${#lines[@]}"
  for ((i=0; i <= "${#lines[@]}"; i++)); do echo "lines[$i]: ${lines[$i]}"; done
  # echo "stderr: $stderr"
  for ((i=0; i <= "${#stderr_lines[@]}"; i++)); do echo "stderr_lines[$i]: ${stderr_lines[$i]}"; done
  echo -en '\e[0m'
} >>$BATS_LOGFILE

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
  local varname=$1
  local -n nameref=$1
  echo -en "\$$varname:\n$(echo_array "${nameref[@]}")"
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
LOG_EMERG=0    # /* system is unusable */
LOG_ALERT=1    # /* action must be taken immediately */
LOG_CRIT=2     # /* critical conditions */
LOG_ERR=3      # /* error conditions */
LOG_WARNING=4  # /* warning conditions */
LOG_NOTICE=5   # /* normal but significant condition */
LOG_INFO=6     # /* informational */
LOG_DEBUG=7    # /* debug-level messages */

LOG_LEVEL=$LOG_WARNING

log_error() {
  [[ $LOG_LEVEL -ge $LOG_ERR ]] || return 0
  if [[ $IN_BATS = 'yes' ]]; then
    printf '\e[31m[E] %d %s: %s\e[0m\n' "${BASH_LINENO[0]}" "${FUNCNAME[1]}" "$*" >>$BATS_LOGFILE
  else
    printf '\e[31m[E] %d %s: %s\e[0m\n' "${BASH_LINENO[0]}" "${FUNCNAME[1]}" "$*" >&2
  fi
}

log_warning() {
  [[ $LOG_LEVEL -ge $LOG_WARNING ]] || return 0
  if [ "$IN_BATS" = 'yes' ]; then
    printf '\e[33m[W] %d %s: %s\e[0m\n' "${BASH_LINENO[0]}" "${FUNCNAME[1]}" "$*" >>$BATS_LOGFILE
  else
    printf '\e[33m[W] %d %s: %s\e[0m\n' "${BASH_LINENO[0]}" "${FUNCNAME[1]}" "$*" >&2
  fi
}

log_info() {
  [[ $LOG_LEVEL -ge $LOG_INFO ]] || return 0
  if [ "$IN_BATS" = 'yes' ]; then
    printf '\e[34m[I] %d %s: %s\e[0m\n' "${BASH_LINENO[0]}" "${FUNCNAME[1]}" "$*" >>$BATS_LOGFILE
  else
    printf '\e[34m[I] %d %s: %s\e[0m\n' "${BASH_LINENO[0]}" "${FUNCNAME[1]}" "$*" >&2
  fi
}

log_debug() {
  [[ $LOG_LEVEL -ge $LOG_DEBUG ]] || return 0
  if [ "$IN_BATS" = 'yes' ]; then
    printf '\e[37m[D] %d %s: %s\e[0m\n' "${BASH_LINENO[0]}" "${FUNCNAME[1]}" "$*" >>$BATS_LOGFILE
  else
    printf '\e[37m[D] %d %s: %s\e[0m\n' "${BASH_LINENO[0]}" "${FUNCNAME[1]}" "$*" >&2
  fi
}

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
    realpath "$0"  # /home/wsh/sh/c.bash
    readlink -f "$0"  # /home/wsh/sh/c.bash
    exit 42
  fi
  realpath "$0"
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

# ------------------------------------------------------------------------------
# bats setup

[ "$IN_BATS" = 'yes' ] && bats_require_minimum_version 1.8.0

[ "$IN_BATS" = 'yes' ] && [ -z "$BATS_TEST_NUMBER" ] && {
  clear
  [ -z "$BATS_SUITE_TEST_NUMBER" ] || echo -e "\e[31mBUG: BATS_SUITE_TEST_NUMBER defined: $BATS_SUITE_TEST_NUMBER\e[0m"
  [ -z "$BATS_TEST_NAME" ]         || echo -e "\e[31mBUG: BATS_TEST_NAME defined: $BATS_TEST_NAME\e[0m"
} >>$BATS_LOGFILE

setup() {
  [ -z "$BATS_TEST_NUMBER" ] && echo -e "\e[31mBUG: setup(): BATS_TEST_NUMBER not defined\e[0m"
  echo -e "\e[32m$BATS_TEST_NUMBER $BATS_TEST_NAME\e[0m"
  [ "$BATS_SUITE_TEST_NUMBER" = "$BATS_TEST_NUMBER" ] || echo -e "\e[31mBUG: BATS_SUITE_TEST_NUMBER: $BATS_SUITE_TEST_NUMBER BATS_TEST_NUMBER: $BATS_TEST_NUMBER\e[0m"
} >>$BATS_LOGFILE

# ------------------------------------------------------------------------------
# commands

declare -A _commands
define_command() {
  _commands[$1]+='defined'
}

arg_noarg() {
  local -r usage=$1 && shift
  [[ $# = 0 ]] && return 0
  [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && echo "$usage" && exit 0
  err 0 "expected no argument, but given: $1" && echo "$usage" >&2 && exit 2
}

# ------------------------------------------------------------------------------
# command - 0template @pub

define_command 0template
0template() {
  arg_noarg "usage: $PROG 0template [-h | --help]" "$@"
  echo 'code here'
  exit 0
}

# without arg_noarg:
if false; then
_() {
  # short usage
  local -r usage="usage: $PROG 0template [-h | --help]"
  [[ $# != 0 ]] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && echo "$usage" && exit 0
  [[ $# != 0 ]] && err 0 "expected no argument, but given: $1" && echo "$usage" >&2 && exit 2

  # long usage
  local -r usage=$(cat <<EOS
usage: $PROG 0template [-h | --help]
EOS
)
  # ...
}
fi

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
  arg_noarg "usage: $PROG discharging_checker [-h | --help]" "$@"
  local -r BASE_INTERVAL=240  # 4min, 8min, 16min, 32min, 64min, ...

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
    discharging='false'
    [ "$state_curr" != 'pending-charge' ] && [ "$(echo "$energy_curr < $energy_prev" | bc)" = 1 ] && discharging='true'  # energy slowly decreases in 'pending-charge' state; notify only in 'charging' state
    [ "$state_curr" = 'discharging' ]                                                             && discharging='true'
    if [ "$discharging" = 'true' ]; then
      percentage_=$(upower -i /org/freedesktop/UPower/devices/battery_BAT0 | grep -P -o '(?<=percentage:)\s+\S+' | tr -d ' ')
      echo "discharging: $energy_prev Wh -> $energy_curr Wh, $state_prev -> $state_curr ($percentage_)"
      bash /home/wsh/sh/debug_notify.bash "discharging: $energy_prev Wh -> $energy_curr Wh ($percentage_), $state_prev -> $state_curr"
      interval=$((interval * 2))
      echo "recheck in $interval seconds..."
    else
      # charging
      [ $interval -gt $BASE_INTERVAL ] && echo 'charging'
      interval=$BASE_INTERVAL
    fi
    energy_prev=$energy_curr
    state_prev=$state_curr
  done
  # NOTREACHED
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
# command - kill_clangd @pub

define_command kill_clangd
kill_clangd() {
  arg_noarg "usage: $PROG kill_clangd [-h | --help]" "$@"
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
    # read -ar -> fields: unbound variable
    IFS=' ' read -ra fields <<<"$line"
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
      IFS=' ' read -ra fields <<<"$line"
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
    IFS=' ' read -ra fields <<<"$line"
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
  arg_noarg "usage: dmesg | $PROG linux_dmesg_time0 [-h | --help]" "$@"
  sed -E s'/\[[0-9 ]{4}[0-9]\.[0-9]{6}\]/[    0.000000]/'
}

# ------------------------------------------------------------------------------
# command - net_if_rename @pub

define_command net_if_rename
net_if_rename() {
  local -r usage="usage: $PROG net_if_rename [-h | --help] MAC_ADDRESS NEW_NAME"
  [[ $# != 0 ]] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && echo "$usage" && exit 0
  # shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
  [ $# != 0 ] && local MAC_ADDRESS=$1 && shift || { err 0 'argument:MAC_ADDRESS not given' && echo "$usage" >&2 && exit 2; }
  # shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
  [ $# != 0 ] && local NEW_NAME=$1 && shift || { err 0 'argument:NEW_NAME not given' && echo "$usage" >&2 && exit 2; }
  [ $# != 0 ] && err 0 "excess argument(s): $*" && echo "$usage" >&2 && exit 2

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
  [[ $# != 0 ]] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && echo "$usage" && exit 0
  # shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
  [ $# != 0 ] && local MAKE_COMMAND=$1 && shift || { err 0 'argument:MAKE_COMMAND not given' && echo "$usage" >&2 && exit 2; }
  [ $# != 0 ] && err 0 "excess argument(s): $*" && echo "$usage" >&2 && exit 2

  local -A pairs_name_value
  local line
  # IFS= : prevent removeing preceding spaces
  while IFS= read -r line; do
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
  [[ $# != 0 ]] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && echo "$usage" && exit 0
  # shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
  [ $# != 0 ] && local QEMU_PID=$1 && shift || { err 0 'argument:QEMU_PID not given' && echo "$usage" >&2 && exit 2; }
  [ $# != 0 ] && err 0 "excess argument(s): $*" && echo "$usage" >&2 && exit 2

  [[ $QEMU_PID = 'netbsd' ]] && QEMU_PID=$(pgrep -f 'qemu-system-x86_64 .+/netbsd.qcow2')

  [[ $QEMU_PID =~ ^[0-9]+$ ]] || die 1 "invalid QEMU_PID: $QEMU_PID"
  realpath "/proc/$QEMU_PID/exe" | grep -q '/qemu-system-' || die 1 "QEMU_PID $QEMU_PID is not a qemu process; /proc/$QEMU_PID/exe: $(realpath /proc/$QEMU_PID/exe)"
  ln -fsv "/dev/pts/$(grep -r tty-index "/proc/$QEMU_PID/fdinfo" | cut -f2)" "/tmp/c_bash_pty_qemu.$QEMU_PID"
  set -x
  [ -f "/tmp/c_bash_pty_qemu.$QEMU_PID.out" ] || daemonize -o "/tmp/c_bash_pty_qemu.$QEMU_PID.out" "$(which cat)" "/tmp/c_bash_pty_qemu.$QEMU_PID"
  ssh -t localhost "tail -F /tmp/c_bash_pty_qemu.$QEMU_PID.out & socat -d -u STDIN,rawer OPEN:/tmp/c_bash_pty_qemu.$QEMU_PID"
}

# ------------------------------------------------------------------------------
# command - pty_usb @pub

define_command pty_usb
pty_usb() {
  local -r usage=$(cat <<EOS
usage:
  $PROG qemu_pty {-h | --help}
  $PROG qemu_pty DEVICE BAUD
  $PROG qemu_pty /dev/ttyUSB0 115200
EOS
)
  [[ $# != 0 ]] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && echo "$usage" && exit 0
  # shellcheck disable=SC2015  # Note that A && B || C is not if-then-else. C may run when A is true.
  [ $# != 0 ] && local DEVICE=$1 && shift || { err 0 'argument:DEVICE not given' && echo "$usage" >&2 && exit 2; }
  [ $# != 0 ] && local BAUD=$1 && shift || { err 0 'argument:BAUD not given' && echo "$usage" >&2 && exit 2; }
  [ $# != 0 ] && err 0 "excess argument(s): $*" && echo "$usage" >&2 && exit 2

  set -x
  lsof -nP "/tmp/c_bash_pty_usb.$(basename "$DEVICE").out" | grep '^cat' || rm -fv "/tmp/c_bash_pty_usb.$(basename "$DEVICE").out"
  if [ ! -f "/tmp/c_bash_pty_usb.$(basename "$DEVICE").out" ]; then
    # @ref:stty-tty-usb
    # stty: /dev/ttyUSB0: unable to perform all requested operations というエラーで失敗することがあるが、もう一回実行すれば通る; 謎
    sudo stty --file="$DEVICE" 1:0:80001cb2:0:3:1c:7f:15:4:5:1:0:11:13:1a:0:12:f:17:16:0:0:0:0:0:0:0:0:0:0:0:0:0:0:0:0 ||
      sudo stty --file="$DEVICE" 1:0:80001cb2:0:3:1c:7f:15:4:5:1:0:11:13:1a:0:12:f:17:16:0:0:0:0:0:0:0:0:0:0:0:0:0:0:0:0
    sudo stty --file="$DEVICE" "$BAUD"
    # sudo not needed:
    # ls -l /dev/ttyUSB0  # crw-rw---- 1 root dialout 188, 0  2月 27 13:56 /dev/ttyUSB0
    # groups              # dialout
    daemonize -o "/tmp/c_bash_pty_usb.$(basename "$DEVICE").out" "$(which cat)" "$DEVICE"
  fi
  ssh -t localhost "tail -F /tmp/c_bash_pty_usb.$(basename "$DEVICE").out & socat -d -u STDIN,rawer OPEN:$DEVICE"
}

# ------------------------------------------------------------------------------
# command - qemu_net_setup @pub

# TODO: 安定したらsystemd oneshot

define_command qemu_net_setup
qemu_net_setup() {
  arg_noarg "usage: $PROG qemu_net_setup [-h | --help]" "$@"
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
# command - z_meta_publish_self @pub

: <<'DOC'
c.bash -v z_meta_publish_self > ~/src/scraps/c.bash
cd ~/src/scraps/
git ...
DOC

define_command z_meta_publish_self
z_meta_publish_self() {
  arg_noarg "usage: $PROG z_meta_publish_self [-h | --help]" "$@"
  local public='true'
  # IFS= : prevent removeing preceding spaces
  while IFS= read -r line; do
    if [[ $line =~ ^'# command - '[[:alnum:]_]+' @pub'$ ]]; then
      log_info "[public: $public -> true] $line"
      public='true'
    elif [[ $line =~ ^'# command - '[[:alnum:]_]+$ ]]; then
      log_info "[public: $public -> false] $line"
      public='false'
    else
      log_debug "$line"
    fi
    [[ $public = 'false' ]] && continue
    [[ $line =~ [@]private ]] && continue
    echo "$line"
  done < "$(self_real_path)"

  return 0
}

# ------------------------------------------------------------------------------
# main tests

# shellcheck disable=SC2154  # * is referenced but not assigned.
test_help_usage() { #@test
  run -0 --separate-stderr bash ~/sh/c.bash -h     # ; bats_run_debug
  [[ ${lines[0]} = 'usage:' ]] ; [[ $stderr = '' ]]
  run -0 --separate-stderr bash ~/sh/c.bash -h --  # ; bats_run_debug
  [[ ${lines[0]} = 'usage:' ]] ; [[ $stderr = '' ]]

  run -2 --separate-stderr bash ~/sh/c.bash     # ; bats_run_debug
  [[ $output = '' ]] ; [[ ${stderr_lines[0]} = $'\e[31mcommand not specified\e[0m' ]] ; [[ ${stderr_lines[1]} = 'usage:' ]]
  run -2 --separate-stderr bash ~/sh/c.bash --  # ; bats_run_debug
  [[ $output = '' ]] ; [[ ${stderr_lines[0]} = $'\e[31mcommand not specified\e[0m' ]] ; [[ ${stderr_lines[1]} = 'usage:' ]]

  run -2 --separate-stderr bash ~/sh/c.bash -x     # ; bats_run_debug
  [[ $output = '' ]] ; [[ ${stderr_lines[0]} = *': illegal option -- x' ]] ; [[ ${stderr_lines[1]} = 'usage:' ]]
  run -2 --separate-stderr bash ~/sh/c.bash -x --  # ; bats_run_debug
  [[ $output = '' ]] ; [[ ${stderr_lines[0]} = *': illegal option -- x' ]] ; [[ ${stderr_lines[1]} = 'usage:' ]]

  run -2 --separate-stderr bash ~/sh/c.bash    no_such_command  # ; bats_run_debug
  [[ $output = '' ]] ; [[ ${stderr_lines[0]} = $'\e[31mno such command: no_such_command\e[0m' ]] ; [[ ${stderr_lines[1]} = 'usage:' ]]
  run -2 --separate-stderr bash ~/sh/c.bash -- no_such_command  # ; bats_run_debug
  [[ $output = '' ]] ; [[ ${stderr_lines[0]} = $'\e[31mno such command: no_such_command\e[0m' ]] ; [[ ${stderr_lines[1]} = 'usage:' ]]

  run -0 --separate-stderr bash ~/sh/c.bash -v    0template     # ; bats_run_debug
  [[ $output = 'code here' ]] ; [[ $stderr = '' ]]
  run -0 --separate-stderr bash ~/sh/c.bash -v -- 0template     # ; bats_run_debug
  [[ $output = 'code here' ]] ; [[ $stderr = '' ]]

  run -0 --separate-stderr bash ~/sh/c.bash -v    0template -h  # ; bats_run_debug
  [[ $output = 'usage: c.bash 0template [-h | --help]' ]] ; [[ $stderr = '' ]]
  run -0 --separate-stderr bash ~/sh/c.bash -v -- 0template -h  # ; bats_run_debug
  [[ $output = 'usage: c.bash 0template [-h | --help]' ]] ; [[ $stderr = '' ]]

  run -2 --separate-stderr bash ~/sh/c.bash -v    0template -z  # ; bats_run_debug
  [[ $output = '' ]] ; [[ ${stderr_lines[0]} = $'\e[31mexpected no argument, but given: -z\e[0m' ]] ; [[ ${stderr_lines[1]} = 'usage: c.bash 0template [-h | --help]' ]]
  run -2 --separate-stderr bash ~/sh/c.bash -v -- 0template -z  # ; bats_run_debug
  [[ $output = '' ]] ; [[ ${stderr_lines[0]} = $'\e[31mexpected no argument, but given: -z\e[0m' ]] ; [[ ${stderr_lines[1]} = 'usage: c.bash 0template [-h | --help]' ]]
}

# ------------------------------------------------------------------------------
# main

[ "$IN_BATS" = 'yes' ] && return 0

if [[ ${HAVE_UTIL_LINUX_GETOPT+defined} != defined ]]; then
  if getopt --version 2>/dev/null | grep -q util-linux; then
    HAVE_UTIL_LINUX_GETOPT='yes'
  else
    HAVE_UTIL_LINUX_GETOPT='no'
  fi
fi

OPT_q='false'
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
    -q) OPT_q='true'; shift;;
    -v) ((OPT_v+=1)); shift;;
    --) shift; break;;
    -*) NOTREACHED && top_usage >&2 && exit 2;;
    *) break;;  # COMMAND
    esac
  done
else
  [ $# != 0 ] && [[ $1 = '-h' || $1 = '-help' || $1 = '--help' ]] && top_usage && exit 0
  OPT_q='false'
  OPT_v=0
  while getopts hqv- OPT; do
    case $OPT in
    h) top_usage; exit 0;;
    q) OPT_q='true';;
    v) ((OPT_v+=1));;
    -) break;;  # COMMAND
    ?) top_usage >&2 && exit 2;;
    *) NOTREACHED && top_usage >&2 && exit 2;;
    esac
  done
  shift $((OPTIND - 1))
fi

[[ $OPT_q = 'true' ]] && [[ $OPT_v -gt 0 ]] && die 1 "-q and -v are mutually exclusive"
[[ $OPT_q = 'true' ]] && LOG_LEVEL=$LOG_ERR
[[ $OPT_v = 1 ]] && LOG_LEVEL=$LOG_INFO
[[ $OPT_v -gt 1 ]] && LOG_LEVEL=$LOG_DEBUG

if [[ $# = 0 ]]; then
  err 0 "command not specified"
  top_usage >&2
  exit 2
else
  COMMAND=$1 && shift
fi

if ! [[ -v _commands[$COMMAND] ]]; then
  err 0 "no such command: $COMMAND"
  top_usage >&2
  exit 2
fi

"$COMMAND" "$@"
exit $?
