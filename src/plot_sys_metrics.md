# plot_sys_metrics

[plot_sys_metrics.py](plot_sys_metrics.py)

`/proc/loadavg`、`/proc/pressure/cpu`、`/proc/stat`、および `iostat` /
`vmstat` の出力を定期的にログに採取し（`collect`）、その生ログをパースして
任意のメトリックを時系列プロットする（`plot`）。

## サブコマンド

- `collect` — 60秒（既定）ごとに `/proc` と `iostat 1 2` / `mpstat 1 2` /
  `vmstat 1 2` のスナップショットをログへ追記し続ける。外部コマンドは初回の
  since-boot 行ではなく、最後の1秒区間行を `plot` 側で使用する。
- `plot` — `collect` が作ったログを読み、傾向を可視化したPNGを出力する。
  既定の4パネル（CPU%/load/PSI/procs）に加え、`--panel ID,ID,...`
  （繰り返し可）でユーザー指定のID群を独自パネルとして描画できる。

## 使い方

```sh
# 採取（フォアグラウンドで延々と回るのでCtrl+C/別端末でkill）
python plot_sys_metrics.py collect sys_metrics.log
python plot_sys_metrics.py collect sys_metrics.log --interval 30
python plot_sys_metrics.py collect sys_metrics.log -n   # dry-run

# 既定（4パネル）
python plot_sys_metrics.py plot sys_metrics.log sys_metrics.png

# 利用可能IDを列挙して終了
python plot_sys_metrics.py plot sys_metrics.log sys_metrics.png --list-ids

# カスタム1パネル
python plot_sys_metrics.py plot sys_metrics.log sys_metrics.png \
    --panel loadavg_load1,loadavg_load5,loadavg_load15

# カスタム複数パネル
python plot_sys_metrics.py plot sys_metrics.log sys_metrics.png \
    --panel stat_cpu_user,stat_cpu_system,stat_cpu_iowait \
    --panel stat_ctxt_rate,stat_intr_total_rate \
    --panel vmstat_free,vmstat_cache,vmstat_buff \
    --panel iostat_kb_read_rate_nvme0n1,iostat_kb_wrtn_rate_nvme0n1
```

## 引数とオプション (`collect`)

| Name                | Kind       | Default | Description                                              |
| ------------------- | ---------- | ------- | -------------------------------------------------------- |
| `log`               | positional | —       | 追記先ログファイル（`plot` の `log` と同じファイルを指す） |
| `--interval`        | option     | `60`    | サンプリング間隔（秒）                                   |
| `-n` / `--dry_run`  | option     | `False` | 1イテレーション分のshell相当コマンドを表示して終了。書き込みなし |

## 引数とオプション (`plot`)

| Name         | Kind         | Default | Description                                                                 |
| ------------ | ------------ | ------- | --------------------------------------------------------------------------- |
| `log`        | positional   | —       | 入力ログのパス                                                              |
| `out`        | positional   | —       | 出力PNGのパス（`--list-ids` 時は使われない）                                |
| `--ncpu`     | option       | `14`    | load参考線・`derived_cpu_saturation` 用CPU数                                |
| `--panel`    | option (反復)| —       | カンマ区切りID群を1パネルとして線描画。繰り返しで複数パネル                  |
| `--list-ids` | flag         | `False` | ログをパースして利用可能なID一覧を `stdout` に出して終了                    |

`--panel` 未指定時は既定の4パネル（後述）を出力。
未知IDを `--panel` に渡すと exit 2 で「`--list-ids` を見ろ」とエラーを出す。

## 既定の4パネル

1. **CPU%** — `/proc/stat` 累積jiffiesの差分から算出した `stat_cpu_user / stat_cpu_system /
   stat_cpu_iowait / stat_cpu_irq / stat_cpu_softirq / stat_cpu_steal / stat_cpu_idle` の積み上げ面グラフ。
2. **Load average** — `/proc/loadavg` の `loadavg_load1/5/15` + `--ncpu` の参考線。
3. **PSI** — `/proc/pressure/cpu` の `some` と `full` それぞれの
   `avg10 / avg60 / avg300`（`full` は破線）。
4. **procs** — `/proc/stat` の `stat_procs_running` と `stat_procs_blocked`。

---

## ID 体系

`--list-ids` で実際に得られるIDは、ソース毎に以下の通り。Python変数名として
そのまま使えるよう設計してある（一部、デバイス名にハイフンを含むもの
（`dm-0` 等）は文字列キーとしては有効だが識別子としては使えない例外あり）。

### 命名規則

- 接頭辞でソースを示す: `loadavg_` / `psi_cpu_` / `stat_` / `iostat_` / `vmstat_` / `derived_`
- 集計CPU%（`/proc/stat` 集計行から計算）は `stat_cpu_`、per-CPU CPU% は `stat_cpu<N>_` 始まり
- 区間差分から算出する量は `_rate`（/sec）として出す
- 累積カウンタは内部的に `_cum` で保持し、`--list-ids` には出さない（公開IDのみ）
- 瞬時値は接尾辞なし

### /proc/loadavg

| ID                       | 説明                                              | プロット案                       |
| ------------------------ | ------------------------------------------------- | -------------------------------- |
| `loadavg_load1`          | load average 1min                                 | 線                               |
| `loadavg_load5`          | load average 5min                                 | 線                               |
| `loadavg_load15`         | load average 15min                                | 線                               |
| `loadavg_nr_runnable`    | 4列目 `R/T` の `R`。実行可能タスク数(現在値)      | 線（procsパネルに重ね描き可）    |
| `loadavg_nr_threads`     | 4列目 `R/T` の `T`。総スレッド/タスク数            | 線（右軸別スケール）             |
| `loadavg_last_pid_rate`  | 5列目の前スナップショット差 /sec = 新規プロセス数/sec | 線。プロセス生成レート            |

### /proc/pressure/cpu

| ID                       | 説明                                                              | プロット案                                  |
| ------------------------ | ----------------------------------------------------------------- | ------------------------------------------- |
| `psi_cpu_some_10/60/300` | `some` の avg10/60/300                                            | 線                                          |
| `psi_cpu_full_10/60/300` | `full` の avg10/60/300                                            | 線（`full` は破線、`some` と同パネル）       |
| `psi_cpu_some_total_rate` | `some` の `total=`(μs) の差分 /sec。stall時間レート               | 線。avg10より粒度が細かい                   |
| `psi_cpu_full_total_rate` | `full` の `total=`(μs) の差分 /sec                                | 線。重なるなら `some` と同パネル            |

### /proc/stat 集計CPU%（`cpu ` 行から計算）

| ID            | 説明                                                  | プロット案                                |
| ------------- | ----------------------------------------------------- | ----------------------------------------- |
| `stat_cpu_user`        | CPU% user                                              | 既定の積み上げパネルに含む                |
| `stat_cpu_system`      | CPU% system                                            | 同上                                      |
| `stat_cpu_iowait`      | CPU% iowait                                            | 同上                                      |
| `stat_cpu_irq`         | CPU% irq                                               | 同上                                      |
| `stat_cpu_softirq`     | CPU% softirq                                           | 同上                                      |
| `stat_cpu_steal`       | CPU% steal                                             | 同上                                      |
| `stat_cpu_idle`        | CPU% idle                                              | 同上                                      |
| `stat_cpu_nice`        | nice値を上げたユーザータスクのCPU%                     | CPU%積み上げに追加可                      |
| `stat_cpu_guest`       | KVM等のゲストVMが消費したCPU%                          | CPU%積み上げに追加可（ホスト/VM混在時）   |
| `stat_cpu_guest_nice`  | niced guest                                            | 同上                                      |

### /proc/stat per-CPU CPU%（`cpu0`〜`cpu<N-1>` 行から計算）

| ID テンプレート           | 説明                                                | プロット案                                            |
| ------------------------ | --------------------------------------------------- | ----------------------------------------------------- |
| `stat_cpu<N>_user`       | コア `<N>` の user 比率                              | ヒートマップ（X=時刻, Y=コア, 色=使用率）が見やすい   |
| `stat_cpu<N>_system`     | コア `<N>` の system                                 | 同上                                                  |
| `stat_cpu<N>_iowait`     | コア `<N>` の iowait（偏りの検出に有用）              | 線複数（少コア時）/ ヒートマップ                       |
| `stat_cpu<N>_idle`       | コア `<N>` の idle                                   | 同上                                                  |
| `stat_cpu<N>_{irq,softirq,steal,nice,guest,guest_nice}` | 同様                           | 必要時のみ                                            |

### /proc/stat スカラ系（レート/瞬間値）

| ID                          | 説明                                                | プロット案                                            |
| --------------------------- | --------------------------------------------------- | ----------------------------------------------------- |
| `stat_procs_running`        | 実行可能プロセス数（瞬間値）                         | 線。既定パネルに含む                                  |
| `stat_procs_blocked`        | ブロック中プロセス数（瞬間値）                       | 同上                                                  |
| `stat_ctxt_rate`            | `ctxt` 累積の差分 /sec。context switch /sec          | 線（log scale 推奨）                                  |
| `stat_processes_rate`       | `processes` 累積の差分 /sec。fork /sec               | 線。`loadavg_last_pid_rate` とほぼ同じ                 |
| `stat_intr_total_rate`      | `intr` 先頭フィールド差分 /sec。IRQ /sec             | 線（log scale 推奨）                                  |
| `stat_intr_<i>_rate`        | IRQ番号 `<i>` の発生回数差分 /sec（変化のあるIRQのみ） | 上位N IRQ を選んで線。ノイジーIRQ特定                |
| `stat_softirq_total_rate`   | `softirq` 先頭フィールド差分 /sec                    | 線                                                    |
| `stat_softirq_hi_rate`      | softirq HI 差分 /sec                                 | stacked area の1系列                                  |
| `stat_softirq_timer_rate`   | softirq TIMER 差分 /sec                              | 同上                                                  |
| `stat_softirq_net_tx_rate`  | softirq NET_TX 差分 /sec                             | 同上                                                  |
| `stat_softirq_net_rx_rate`  | softirq NET_RX 差分 /sec                             | 同上                                                  |
| `stat_softirq_block_rate`   | softirq BLOCK 差分 /sec                              | 同上                                                  |
| `stat_softirq_irq_poll_rate`| softirq IRQ_POLL 差分 /sec                           | 同上                                                  |
| `stat_softirq_tasklet_rate` | softirq TASKLET 差分 /sec                            | 同上                                                  |
| `stat_softirq_sched_rate`   | softirq SCHED 差分 /sec                              | 同上                                                  |
| `stat_softirq_hrtimer_rate` | softirq HRTIMER 差分 /sec                            | 同上                                                  |
| `stat_softirq_rcu_rate`     | softirq RCU 差分 /sec                                | 同上                                                  |

### iostat（per-device 1秒レート）

`collect` は `iostat 1 2` を実行し、最後の1秒区間レポートをパースする。
`tps` / `kB_*/s` 列をそのまま per-second 値として取り込む。
`loop*` / `zd*` デバイスは除外。

| ID テンプレート                  | 説明                                                       | プロット案                                                       |
| -------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------- |
| `iostat_tps_rate_<dev>`          | デバイス別 transfer/sec                                    | 線複数（デバイス別）                                             |
| `iostat_kb_read_rate_<dev>`      | デバイス別 read KB/sec                                     | 線複数（デバイス別）                                             |
| `iostat_kb_wrtn_rate_<dev>`      | デバイス別 write KB/sec                                    | 線複数。read/write を別パネルか色分け                            |
| `iostat_kb_dscd_rate_<dev>`      | デバイス別 discard KB/sec                                  | 必要時のみ                                                       |
| `iostat_kb_read_rate_total`      | `loop*`/`zd*` を除く主デバイスの read KB/sec 合計           | 1本でストレージ全体傾向                                          |
| `iostat_kb_wrtn_rate_total`      | 同上 write KB/sec 合計                                     | 同上                                                             |

### vmstat（瞬間値のみ）

`collect` は `vmstat 1 2` を実行し、最後の1秒区間行をパースする。
メモリ列と procs 列は瞬間値、swap/io/system 列は per-second 値、cpu 列は
その1秒区間のCPU%として取り込む。

| ID              | 説明                                              | プロット案                       |
| --------------- | ------------------------------------------------- | -------------------------------- |
| `vmstat_swpd`   | 仮想メモリ使用量 (KB)                             | 線。MB/GB表示                    |
| `vmstat_free`   | 空きメモリ (KB)                                   | 線                               |
| `vmstat_buff`   | バッファ (KB)                                     | 積み上げの1系列                  |
| `vmstat_cache`  | ページキャッシュ (KB)                             | 積み上げの1系列                  |
| `vmstat_r`      | 実行可能タスク数（procs列、瞬間値）                | `loadavg_nr_runnable` と同等     |
| `vmstat_b`      | uninterruptible sleep 中プロセス数                  | `stat_procs_blocked` と同等      |
| `vmstat_si_rate`| swap in KB/sec                                      | 線                               |
| `vmstat_so_rate`| swap out KB/sec                                     | 線                               |
| `vmstat_bi_rate`| block in blocks/sec                                 | 線                               |
| `vmstat_bo_rate`| block out blocks/sec                                | 線                               |
| `vmstat_in_rate`| interrupts/sec                                      | 線                               |
| `vmstat_cs_rate`| context switches/sec                                | 線                               |
| `vmstat_cpu_user/system/idle/iowait/steal/guest` | 1秒区間のCPU% | CPU%比較用 |

> `vmstat_mem_used` / `vmstat_mem_stacked` は `MemTotal` が必要なため未対応
> （`/proc/meminfo` を `collect` に追加する将来作業）。

### mpstat

`collect` は `mpstat 1 2` を実行し、最後の1秒区間行を `mpstat_cpu_*` として
取り込む。`/proc/stat` 由来の `stat_cpu_*` はスナップショット間隔全体の差分から
算出されるのに対し、`mpstat_cpu_*` は採取時点直前1秒の値。

| ID                    | 説明                   | プロット案             |
| --------------------- | ---------------------- | ---------------------- |
| `mpstat_cpu_user`     | 1秒区間の user CPU%    | `stat_cpu_user` と比較 |
| `mpstat_cpu_system`   | 1秒区間の system CPU%  | 同上                   |
| `mpstat_cpu_iowait`   | 1秒区間の iowait CPU%  | 同上                   |
| `mpstat_cpu_irq`      | 1秒区間の irq CPU%     | 同上                   |
| `mpstat_cpu_softirq`  | 1秒区間の softirq CPU% | 同上                   |
| `mpstat_cpu_steal`    | 1秒区間の steal CPU%   | 同上                   |
| `mpstat_cpu_idle`     | 1秒区間の idle CPU%    | 同上                   |

### 派生指標（複数ソース横断）

| ID                              | 計算式                                                                       | 用途                                       |
| ------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------ |
| `derived_cpu_saturation`        | `loadavg_load1 / ncpu`                                                       | 1超えで飽和判定                            |
| `derived_iowait_per_iobyte`     | `stat_cpu_iowait / (iostat_kb_read_rate_total + iostat_kb_wrtn_rate_total)` | I/Oが効率良いか                           |
| `derived_ctxt_per_task`         | `stat_ctxt_rate / stat_procs_running`                                        | スイッチ過多の検出                         |
| `derived_mem_pressure_warning`  | `(vmstat_swpd > 0).astype(int)`（簡略版、`vmstat_cache` 急減判定は未実装）   | スワップ発生の予兆フラグ（0/1）            |

---

## 採取側の改善余地（参考、未採取データ）

以下を `collect` に追加すると、対応するIDで描けるものが増える:

| 採取追加候補                                  | 取れる項目（IDは例）                                                              |
| --------------------------------------------- | --------------------------------------------------------------------------------- |
| `/proc/meminfo`                               | `meminfo_mem_available`, `meminfo_slab`, `meminfo_swap_free`, `meminfo_dirty`, `meminfo_writeback`（および `vmstat_mem_used`/`_stacked` の計算に必要な `MemTotal`） |
| `/proc/pressure/memory`、`/proc/pressure/io`  | `psi_mem_some_10` … / `psi_io_some_10` …（cpuと同パターン）                       |
| `/proc/diskstats`                             | `iostat -x` 相当（`diskstats_util_<dev>`, `diskstats_await_<dev>`, ...）          |
| `/proc/net/dev`                               | `net_rx_bytes_delta_<iface>`, `net_tx_bytes_delta_<iface>`                        |
| `/sys/class/thermal/thermal_zone*/temp`       | `thermal_zone<i>_temp`                                                            |
| `/proc/<pid>/stat`、`/proc/<pid>/io`          | プロセス追跡（`proc_<pid>_rss`, `proc_<pid>_io_read_bytes`）                       |

---

## ログフォーマット

`collect` は以下の形でセクションを追記する（`plot` はこれを期待する）:

```
===== 2006-01-02T15:04:05+09:00 /proc/loadavg =====
<本文>
===== 2006-01-02T15:04:05+09:00 /proc/pressure/cpu =====
<本文>
===== 2006-01-02T15:04:05+09:00 /proc/stat =====
<本文>
===== 2006-01-02T15:04:05+09:00 iostat =====
<本文>
...
```

タイムスタンプは ISO 8601（ローカルTZオフセット付き、秒精度）。
`iostat` / `mpstat` / `vmstat` セクションは `1 2` の出力を保存し、`plot` 側では
最後の1秒区間レポートを使用する。
