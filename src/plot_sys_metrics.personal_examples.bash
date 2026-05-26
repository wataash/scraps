#!/usr/bin/env bash
# [](file:///home/wsh/d/s/plot_sys_metrics.py)
# [](file:///home/wsh/d/s/plot_sys_metrics.md)

python ~/d/s/plot_sys_metrics.py collect ~/sys_metrics.log
python ~/d/s/plot_sys_metrics.py plot ~/sys_metrics.log ~/sys_metrics.png
python ~/d/s/plot_sys_metrics.py plot ~/sys_metrics.log ~/sys_metrics2.png --list-ids

python ~/d/s/plot_sys_metrics.py plot ~/sys_metrics.log ~/sys_metrics2.png \
  --panel stat_cpu_guest,stat_cpu0_guest,stat_cpu1_guest,stat_cpu2_guest,stat_cpu3_guest,stat_cpu4_guest,stat_cpu5_guest,stat_cpu6_guest,stat_cpu7_guest,stat_cpu8_guest,stat_cpu9_guest,stat_cpu10_guest,stat_cpu11_guest,stat_cpu12_guest,stat_cpu13_guest \
  --panel stat_cpu_guest_nice,stat_cpu0_guest_nice,stat_cpu1_guest_nice,stat_cpu2_guest_nice,stat_cpu3_guest_nice,stat_cpu4_guest_nice,stat_cpu5_guest_nice,stat_cpu6_guest_nice,stat_cpu7_guest_nice,stat_cpu8_guest_nice,stat_cpu9_guest_nice,stat_cpu10_guest_nice,stat_cpu11_guest_nice,stat_cpu12_guest_nice,stat_cpu13_guest_nice \
  --panel stat_cpu_idle,stat_cpu0_idle,stat_cpu1_idle,stat_cpu2_idle,stat_cpu3_idle,stat_cpu4_idle,stat_cpu5_idle,stat_cpu6_idle,stat_cpu7_idle,stat_cpu8_idle,stat_cpu9_idle,stat_cpu10_idle,stat_cpu11_idle,stat_cpu12_idle,stat_cpu13_idle \
  --panel stat_cpu_iowait,stat_cpu0_iowait,stat_cpu1_iowait,stat_cpu2_iowait,stat_cpu3_iowait,stat_cpu4_iowait,stat_cpu5_iowait,stat_cpu6_iowait,stat_cpu7_iowait,stat_cpu8_iowait,stat_cpu9_iowait,stat_cpu10_iowait,stat_cpu11_iowait,stat_cpu12_iowait,stat_cpu13_iowait \
  --panel stat_cpu_irq,stat_cpu0_irq,stat_cpu1_irq,stat_cpu2_irq,stat_cpu3_irq,stat_cpu4_irq,stat_cpu5_irq,stat_cpu6_irq,stat_cpu7_irq,stat_cpu8_irq,stat_cpu9_irq,stat_cpu10_irq,stat_cpu11_irq,stat_cpu12_irq,stat_cpu13_irq \
  --panel stat_cpu_nice,stat_cpu0_nice,stat_cpu1_nice,stat_cpu2_nice,stat_cpu3_nice,stat_cpu4_nice,stat_cpu5_nice,stat_cpu6_nice,stat_cpu7_nice,stat_cpu8_nice,stat_cpu9_nice,stat_cpu10_nice,stat_cpu11_nice,stat_cpu12_nice,stat_cpu13_nice \
  --panel stat_cpu_softirq,stat_cpu0_softirq,stat_cpu1_softirq,stat_cpu2_softirq,stat_cpu3_softirq,stat_cpu4_softirq,stat_cpu5_softirq,stat_cpu6_softirq,stat_cpu7_softirq,stat_cpu8_softirq,stat_cpu9_softirq,stat_cpu10_softirq,stat_cpu11_softirq,stat_cpu12_softirq,stat_cpu13_softirq \
  --panel stat_cpu_steal,stat_cpu0_steal,stat_cpu1_steal,stat_cpu2_steal,stat_cpu3_steal,stat_cpu4_steal,stat_cpu5_steal,stat_cpu6_steal,stat_cpu7_steal,stat_cpu8_steal,stat_cpu9_steal,stat_cpu10_steal,stat_cpu11_steal,stat_cpu12_steal,stat_cpu13_steal \
  --panel stat_cpu_system,stat_cpu0_system,stat_cpu1_system,stat_cpu2_system,stat_cpu3_system,stat_cpu4_system,stat_cpu5_system,stat_cpu6_system,stat_cpu7_system,stat_cpu8_system,stat_cpu9_system,stat_cpu10_system,stat_cpu11_system,stat_cpu12_system,stat_cpu13_system \
  --panel stat_cpu_user,stat_cpu0_user,stat_cpu1_user,stat_cpu2_user,stat_cpu3_user,stat_cpu4_user,stat_cpu5_user,stat_cpu6_user,stat_cpu7_user,stat_cpu8_user,stat_cpu9_user,stat_cpu10_user,stat_cpu11_user,stat_cpu12_user,stat_cpu13_user \
  --panel stat_cpu_user,stat_cpu0_user,stat_cpu1_user,stat_cpu2_user,stat_cpu3_user,stat_cpu4_user,stat_cpu5_user,stat_cpu6_user,stat_cpu7_user,stat_cpu8_user,stat_cpu9_user,stat_cpu10_user,stat_cpu11_user,stat_cpu12_user,stat_cpu13_user \
  ;

xdg-open ~/sys_metrics.png
xdg-open ~/sys_metrics2.png
