# dumpall

break 地点の**コンテキストを一括ダンプ**する gdb コマンド。1 コマンドで以下を出す:

1. **backtrace** (`bt`) — どの経路でこの関数に来たか
2. **location** (`frame`) — 現在位置 (ファイル:行)
3. **process** (`$lx_current()`) — 現在のプロセス pid / comm
4. **args + locals** — 引数とローカル変数を総なめ、ポインタは**一段自動デリファレンス**

変数名を個別指定しないので、関数を問わず `dumpall` 一発で状況が揃う。

- 実体: [`dumpall.py`](dumpall.py)
- 提供コマンド:
  - `dumpall` — gdb コンソールに出力
  - `cdumpall` — 同じ出力を**クリップボードにもコピー**(Wayland / `wl-copy`)

## 動機

状況を伝えるには「どこで・誰に呼ばれ・どのプロセスで・変数は何か」が要る。
`info args` / `info locals` はポインタを `0xffff...` のアドレスでしか出さず、
構造体の中身を見るには毎回 `p *ops` のように変数名を手で指定する必要がある。
`dumpall` は `bt` / `frame` / `$lx_current()` / 変数ダンプを 1 コマンドにまとめ、
ポインタは自動で `*var` 相当まで展開する。関数に依存しないのでどの break 地点でも同じ。

## 使い方

### 都度 source

```gdb
source dumpall.py
set print pretty on
set print object on
(gdb) dumpall
```

### 常用する場合 (~/.gdbinit)

```gdb
source dumpall.py
set print pretty on
set print object on
```

`set print pretty on` を併用すると、展開された構造体が整形されて読みやすい。


## 出力例

`fg_ftrace_thunk(ip, parent_ip, ops, fregs)` で break 中:

```
(gdb) dumpall
########## backtrace ##########
#0  fg_ftrace_thunk (ip=..., parent_ip=..., ops=..., fregs=...) at src/file_guard.c:312
#1  0xffffffff81... in ftrace_ops_list_func (...)
#2  0xffffffff81... in do_dentry_open (...)
...
########## location ##########
#0  fg_ftrace_thunk (...) at src/file_guard.c:312
########## process ##########
pid=1234 comm=cat
########## args + locals ##########
=== ip ===
18446744072644943024
=== parent_ip ===
18446744071581523904
=== ops ===
0xffffffffc0740...
  *ops = {func = 0xffffffffc05ff060 <fg_ftrace_thunk>, next = ..., flags = 6231, ...}
=== hook ===
0xffffffffc07406c0 <fg_hook>
  *hook = {name = 0x... "security_file_open", function = ..., ...}
```

整数(`ip`, `parent_ip`)はそのまま、ポインタ(`ops`, `hook` 等)は中身まで出る。

## 仕様・制約

- **変数展開は一段のみ。** `*ops` の中の `ops->next` の先までは追わない
  (カーネル構造体は循環参照が多く、再帰展開すると爆発するため)。
  深掘りしたいものだけ `p ops->local_hash` のように個別に追う。
- デリファレンスするのは**指す先が struct / union のポインタ**のみ。
  `char *` は構造体ではないので展開せず、gdb が文字列として表示する。
- NULL ポインタ・読めないアドレス(`gdb.MemoryError`)は `<unreadable>` と表示してスキップ。
- 引数・ローカルの表示には**デバッグ情報 (`-g`)** が必要。無い関数では空になる。
- `cdumpall` のコピーは **Wayland 前提で `wl-copy`** を使う(`sudo apt install wl-clipboard`)。
  X11 なら `_collect()` を `xclip -selection clipboard` 等に差し替える。失敗時は注記を出すだけ。
- **process** 欄は `scripts/gdb` (lx-symbols) を読み込んでいないと出ない
  (dbgsym だけだと `$lx_current` 未提供。`linux_file_guard_kmod/debug.md` 参照)。
  その場合は注記だけ出して残りは続行する。
- スコープは関数ブロックまで。グローバルスコープは辿らない。
