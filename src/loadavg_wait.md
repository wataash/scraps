# loadavg_wait.py

[loadavg_wait.py](loadavg_wait.py)

`/proc/loadavg` を一定間隔でポーリングし、1/5/15 分平均をタイムスタンプ付きで
表示する。監視対象の load average が閾値を下回った時点で終了する。重い処理を
始める前に、混んでいるマシンが落ち着くのを待つ用途に便利。

## Usage

```sh
python loadavg_wait.py
python loadavg_wait.py --threshold 0.5 --interval 30
python loadavg_wait.py --field 5
```

各行は `<date> <time> <load1> <load5> <load15>` の形式。例:

```
loadavg 1/5/15:
2026-06-19 14:32:01 1.82 1.57 1.84
2026-06-19 14:33:01 0.74 1.20 1.70
```

閾値チェックの前に必ず 1 回サンプルを出力するため、ループは最低 1 回は実行され、
条件を満たした場合は末尾の sleep なしで即座に終了する。`/proc/loadavg` を読むため
Linux 専用。

## Options

| Option        | 説明                                                          |
| ------------- | ------------------------------------------------------------- |
| `--threshold` | 監視対象の load average がこの値を下回ったら終了(デフォルト `1.0`)。 |
| `--interval`  | サンプル間隔の秒数(デフォルト `60`)。                        |
| `--field`     | 比較対象の平均値。`1` / `5` / `15` 分(デフォルト `1`)。      |
| `-h, --help`  | ヘルプを表示して終了。                                        |
