# lkm_hello

最小の Loadable Kernel Module (LKM)。**gdb によるカーネルモジュールのソース行デバッグ (vng + lx-symbols) の練習台**として使う。

vng: file:///home/wsh/d/t/linux_kernel_vng.md
- /home/wsh/src/linux-src/
- /home/wsh/src/linux_build_for_guard/

https://docs.kernel.org/process/debugging/gdb-kernel-debugging.html Debugging kernel and modules via gdb
https://www.kernel.org/doc/html/latest/process/debugging/gdb-kernel-debugging.html Debugging kernel and modules via gdb

## build

```sh
# 動かしているカーネル向け（普通のビルド）
sudo apt install -y build-essential linux-headers-$(uname -r)
cd ~/d/s/lkm_hello/
make clean
bear -- make V=1 KCFLAGS="-O0"  # KCFLAGS="-O0": -g -gdwarf-5  -fsanitize=bounds-strict -> -g -gdwarf-5 -O0  -fsanitize=bounds-strict
modinfo build/lkm_hello.ko | grep vermagic   # vermagic:       7.0.0-27-generic SMP preempt mod_unload modversions 
# rebuild:
make -C ~/d/s/lkm_hello/ KCFLAGS="-O0"

# gdb デバッグ用カーネル向け（DWARF + CONFIG_GDB_SCRIPTS の O= ビルド）
cd ~/d/s/lkm_hello/
make KDIR=/home/wsh/src/linux_build_for_guard/ clean
bear -- make V=1 KCFLAGS="-O0" KDIR=/home/wsh/src/linux_build_for_guard/
# (!)modifies /home/wsh/src/linux_build_for_guard/Makefile:
#   +export KBUILD_EXTMOD = /home/wsh/d/s/lkm_hello
#   +export KBUILD_EXTMOD_OUTPUT = /home/wsh/d/s/lkm_hello/build
#   see file:///home/wsh/d/arc/kbuild_extmod_mo_rewrites_kdir_makefile.md
modinfo build/lkm_hello.ko | grep vermagic   # vermagic:       7.2.0-rc1-virtme SMP preempt mod_unload 
# rebuild:
make -C ~/d/s/lkm_hello/ KCFLAGS="-O0" KDIR=/home/wsh/src/linux_build_for_guard/

clion .
# Open as:
# [ ] Makefile project
# [x] Compilation Database project
```

/home/wsh/d/s/lkm_hello/README.md: q1:
/home/wsh/d/s/lkm_hello/Makefile で
MO ?= $(CURDIR)/build/ だと、上の (!) のように /home/wsh/src/linux_build_for_guard/Makefile を書き換えてしまう。
MO ?= $(CURDIR)/ なら書き換えない。
ビルド生成物は /home/wsh/d/s/lkm_hello/build/ にまとめたいので MO ?= $(CURDIR)/build/ が良いのだが、どうすれば /home/wsh/src/linux_build_for_guard/Makefile を書き換えずに済む？
-> file:///home/wsh/d/arc/kbuild_extmod_mo_rewrites_kdir_makefile.md

## debug with gdb (vng)

file:///home/wsh/src/linux-src/scripts/gdb/linux/symbols.py
                             ".text.hot", ".text.unlikely", ".init.text", ".exit.text"]:  # kvm だと insmod で __kvm_symbols_hack_insmod_segv__  orig: ".text.hot", ".text.unlikely"]:

```sh
# terminal 1
make -C ~/d/s/lkm_hello/ KCFLAGS="-O0" KDIR=/home/wsh/src/linux_build_for_guard/ && export KBUILD_OUTPUT=/home/wsh/src/linux_build_for_guard/ && vng --verbose --debug --disable-kvm
sudo insmod /home/wsh/d/s/lkm_hello/build/lkm_hello.ko count=2 who=gdb
echo 1 | sudo tee /sys/module/lkm_hello/parameters/trigger

# terminal 2
cd ~/d/s/lkm_hello/
gdb -q -ex 'set pagination off' -ex 'set confirm off' -ex 'add-auto-load-safe-path /home/wsh/src/linux_build_for_guard' -ex 'add-auto-load-safe-path /home/wsh/src/linux-src' -ex 'file /home/wsh/src/linux_build_for_guard/vmlinux' -ex 'target remote localhost:1234' -ex 'lx-symbols'
b lkm_hello_greet
c
# echo 1 | sudo tee /sys/module/lkm_hello/parameters/trigger
# Thread 5 hit Breakpoint 1, lkm_hello_greet (n=2) at ../lkm_hello.c:29

# for CLion
mkdir ~/.config/gdb/
echo > ~/.config/gdb/gdbinit '
echo gdbinit\n
add-auto-load-safe-path /home/wsh/src/linux_build_for_guard
add-auto-load-safe-path /home/wsh/src/linux-src
echo end of gdbinit\n
'
# CLion: Remote Debug:
#   tcp::1234
#   /home/wsh/src/linux_build_for_guard/vmlinux
# pause, lx-symbols -> lkm_hello.c のブレークポイントが有効になる
```

## debug init

(gdb) p lkm_hello_greet
$1 = {int (int)} 0xffffffffc0400010 <lkm_hello_greet>
(gdb) p trigger_set
$2 = {int (const char *, const struct kernel_param *)} 0xffffffffc0400040 <trigger_set>
(gdb) p lkm_hello_init
❌️ Cannot access memory at address 0x50
(gdb) p lkm_hello_exit
❌️ Cannot access memory at address 0xb0

file:///home/wsh/src/linux-src/scripts/gdb/linux/symbols.py
                             ".text.hot", ".text.unlikely", ".init.text", ".exit.text"]:  # kvm だと insmod で __kvm_symbols_hack_insmod_segv__  orig: ".text.hot", ".text.unlikely"]:

(gdb) p lkm_hello_init
$3 = {int (void)} 0xffffffffc0401010 <lkm_hello_init>
(gdb) p lkm_hello_exit
$4 = {void (void)} 0xffffffffc04000d0 <lkm_hello_exit>

/home/wsh/d/s/lkm_hello/README.md: q124:
lkm_hello_init() をgdbデバッグする。
lkm_hello_init() の先頭で実行を止めて、gdbを接続してブレークポイントを設置したら、実行を再開してbreakしたい。どのような方法がある？

debug with CLion:
make -C ~/d/s/lkm_hello/ KCFLAGS="-O0" KDIR=/home/wsh/src/linux_build_for_guard/ && export KBUILD_OUTPUT=/home/wsh/src/linux_build_for_guard/ && vng --verbose --debug --disable-kvm
CLion: pause, lx-symbols, continue
shell: sudo insmod /home/wsh/d/s/lkm_hello/build/lkm_hello.ko count=2 who=gdb

## lx-symbols

file:///home/wsh/src/linux-src/scripts/gdb/linux/symbols.py LxSymbols コマンド
add-symbol-file を組み立てるだけ

-ex 'lx-symbols' を以下にreplace:
-ex 'python _orig = gdb.execute; gdb.execute = lambda cmd, *a, **k: (gdb.write("[exec] " + str(cmd) + "\n"), _orig(cmd, *a, **k))[1]' -ex 'lx-symbols'

loading vmlinux
[exec] symbol-file                                                  file:///home/wsh/src/linux-src/scripts/gdb/linux/symbols.py drop all current symbols and reload vmlinux  gdb.execute("symbol-file", to_string=True)
[exec] symbol-file /home/wsh/src/linux_build_for_guard/vmlinux      file:///home/wsh/src/linux-src/scripts/gdb/vmlinux-gdb.py gdb.execute("", to_string=True)
[exec] 
scanning for modules in /home/wsh/d/s/lkm_hello
loading @0xffffffffc0400000: /home/wsh/d/s/lkm_hello/build/lkm_hello.ko
[exec] add-symbol-file /home/wsh/d/s/lkm_hello/build/lkm_hello.ko 0xffffffffc0400000  -s .data 0xffffffffc0201020 -s .rodata 0xffffffffc0203000

invoke():
kernel/module/main.c:do_init_module に internal breakpoint 設置
(gdb) info breakpoints 
No breakpoints, watchpoints, tracepoints, or catchpoints.
(gdb) maint info breakpoints 
Num     Type           Disp Enb Address            What
-1      breakpoint     keep y   0xffffffff8146dae0 in do_init_module at /home/wsh/src/linux-src/kernel/module/main.c:3078 inf 1
-1.1                        y   0xffffffff8146dae0 in do_init_module at /home/wsh/src/linux-src/kernel/module/main.c:3078 inf 1
  以降 insmod される度に自動で load_module_symbols() が走る (手動 lx-symbols 相当)

load_module_symbols():
  module->mem[MOD_TEXT].base = モジュール .text のロードアドレス (例 0xffffffffc0400000) を取得
  module_paths (lx-symbols の引数 + cwd) から .ko を再帰検索
  add-symbol-file <ko> <textaddr> -s <sect> <addr> ... を gdb.execute

_section_arguments():
module->sect_attrs から
「全セクション名 -> 実行時アドレス」の辞書を作る (.init.text .exit.text も辞書には入っている)
しかし実際に add-symbol-file へ渡すのは以下だけ:
  textaddr             : .text のアドレス (add-symbol-file の第1引数 = ベース)
  -s <name> <addr>     : .data .data..read_mostly .rodata .bss .text.hot .text.unlikely だけ (ハードコードのホワイトリスト)
.init.text (__init lkm_hello_init) と .exit.text (__exit lkm_hello_exit) はホワイトリスト外

sudo grep -H . /sys/module/lkm_hello/sections/{*,.*}
/sys/module/lkm_hello/sections/__mcount_loc:0xffffffffc020310a
/sys/module/lkm_hello/sections/__param:0xffffffffc0203128
/sys/module/lkm_hello/sections/__patchable_function_entries:0xffffffffc0201000
/sys/module/lkm_hello/sections/.call_sites:0xffffffffc02031d0
/sys/module/lkm_hello/sections/.data:0xffffffffc0201020
/sys/module/lkm_hello/sections/.exit.data:0xffffffffc0201030
/sys/module/lkm_hello/sections/.exit.text:0xffffffffc04000c0
/sys/module/lkm_hello/sections/.gnu.linkonce.this_module:0xffffffffc0201040
/sys/module/lkm_hello/sections/.init.data:0xffffffffc0205000
/sys/module/lkm_hello/sections/.init.text:0xffffffffc0401000
/sys/module/lkm_hello/sections/.note.gnu.build-id:0xffffffffc0203280
/sys/module/lkm_hello/sections/.note.gnu.property:0xffffffffc02031a0
/sys/module/lkm_hello/sections/.note.Linux:0xffffffffc02032a4
/sys/module/lkm_hello/sections/.orc_header:0xffffffffc02032d4
/sys/module/lkm_hello/sections/.orc_unwind:0xffffffffc02031f4
/sys/module/lkm_hello/sections/.orc_unwind_ip:0xffffffffc0203248
/sys/module/lkm_hello/sections/.return_sites:0xffffffffc02031c0
/sys/module/lkm_hello/sections/.rodata:0xffffffffc0203000
/sys/module/lkm_hello/sections/.strtab:0xffffffffc0205770
/sys/module/lkm_hello/sections/.symtab:0xffffffffc0205008
/sys/module/lkm_hello/sections/.text:0xffffffffc0400000

## __kvm_symbols_hack_insmod_segv__

wsh@virtme-ng ~/d/s/lkm_hello (main)> sudo insmod /home/wsh/d/s/lkm_hello/build/lkm_hello.ko count=2 who=gdb
[   13.106655] lkm_hello: loading out-of-tree module taints kernel.
[   13.121794] Oops: invalid opcode: 0000 [#1] SMP NOPTI
[   13.122582] CPU: 1 UID: 0 PID: 417 Comm: insmod Tainted: G           O        7.2.0-rc1-virtme #2 PREEMPT(lazy) 
[   13.122742] Tainted: [O]=OOT_MODULE
[   13.122798] Hardware name: QEMU Ubuntu 26.04 PC (i440FX + PIIX, 1996), BIOS 1.17.0-debian-1.17.0-1ubuntu1 04/01/2014
[   13.122932] RIP: 0010:do_init_module+0x1/0x250
[   13.123026] Code: 78 08 4c 89 e6 e8 bf d4 ff ff 65 48 ff 43 08 e9 68 fe ff ff 0f 1f 44 00 00 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 cc <1f> 44 00 00 55 ba 20 00 00 00 be c0 0c 00 00 53 48 89 fb 48 83 ec
[   13.123274] RSP: 0018:ffffc9000050bda0 EFLAGS: 00010282
[   13.123358] RAX: 0000000000000000 RBX: ffff88800492fcc0 RCX: ffff8880048a8480
[   13.123457] RDX: ffff88803ea6ebd8 RSI: ffff888003865c00 RDI: ffffffffc0201040
[   13.123570] RBP: 0000558f16f1b010 R08: 0000000000000000 R09: ffffffff8146fa2f
[   13.123740] R10: ffffea0000122a00 R11: ffff888003842200 R12: 0000000000000058
[   13.123880] R13: ffff88800492fcc0 R14: 0000558f16f1b010 R15: 0000000000000000
[   13.124013] FS:  00007f188f61c3c0(0000) GS:ffff8880bb5f1000(0000) knlGS:0000000000000000
[   13.124135] CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
[   13.124232] CR2: 00007f188f8023f0 CR3: 00000000095fb004 CR4: 0000000000772ef0
[   13.124354] PKRU: 55555554
[   13.124401] Call Trace:
[   13.124449]  <TASK>
[   13.124505]  init_module_from_file+0xd3/0xf0
[   13.124677]  idempotent_init_module+0x114/0x310
[   13.124768]  __x64_sys_finit_module+0x5f/0xb0
[   13.124862]  do_syscall_64+0x104/0x520
[   13.124943]  entry_SYSCALL_64_after_hwframe+0x77/0x7f
[   13.125039] RIP: 0033:0x7f188f832d0d
[   13.125115] Code: ff c3 66 2e 0f 1f 84 00 00 00 00 00 90 f3 0f 1e fa 48 89 f8 48 89 f7 48 89 d6 48 89 ca 4d 89 c2 4d 89 c8 4c 8b 4c 24 08 0f 05 <48> 3d 01 f0 ff ff 73 01 c3 48 8b 0d cb d0 0d 00 f7 d8 64 89 01 48
[   13.125406] RSP: 002b:00007ffec51617e8 EFLAGS: 00000246 ORIG_RAX: 0000000000000139
[   13.125568] RAX: ffffffffffffffda RBX: 0000558f16f1ca50 RCX: 00007f188f832d0d
[   13.125690] RDX: 0000000000000000 RSI: 0000558f16f1b010 RDI: 0000000000000003
[   13.125813] RBP: 00007ffec5161880 R08: 0000000000000000 R09: 00000000ffffffff
[   13.125931] R10: 0000000000000000 R11: 0000000000000246 R12: 0000558f16f1b010
[   13.126048] R13: 0000558f16f1ca10 R14: 0000000000000000 R15: 0000558f16f1ca50
[   13.126167]  </TASK>
[   13.126211] Modules linked in: lkm_hello(O+)
[   13.126349] ---[ end trace 0000000000000000 ]---
[   13.126439] RIP: 0010:do_init_module+0x1/0x250
[   13.126538] Code: 78 08 4c 89 e6 e8 bf d4 ff ff 65 48 ff 43 08 e9 68 fe ff ff 0f 1f 44 00 00 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 cc <1f> 44 00 00 55 ba 20 00 00 00 be c0 0c 00 00 53 48 89 fb 48 83 ec
[   13.126825] RSP: 0018:ffffc9000050bda0 EFLAGS: 00010282
[   13.126903] RAX: 0000000000000000 RBX: ffff88800492fcc0 RCX: ffff8880048a8480
[   13.127023] RDX: ffff88803ea6ebd8 RSI: ffff888003865c00 RDI: ffffffffc0201040
[   13.127140] RBP: 0000558f16f1b010 R08: 0000000000000000 R09: ffffffff8146fa2f
[   13.127268] R10: ffffea0000122a00 R11: ffff888003842200 R12: 0000000000000058
[   13.127392] R13: ffff88800492fcc0 R14: 0000558f16f1b010 R15: 0000000000000000
[   13.127520] FS:  00007f188f61c3c0(0000) GS:ffff8880bb5f1000(0000) knlGS:0000000000000000
[   13.127646] CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
[   13.127747] CR2: 00007f188f8023f0 CR3: 00000000095fb004 CR4: 0000000000772ef0
[   13.127879] PKRU: 55555554
fish: Job 1, 'sudo insmod /home/wsh/d/s/lkm_h…' terminated by signal SIGSEGV (Address boundary error)

## z notes

- ~/src/linux-src/ が in-tree でビルドされている（O= 無しで configure された＝出力先がソース自身 (KBUILD_OUTPUT なしでビルド)）
- lkm_hello/Makefile で MO= が設定されている
を満たすと、 make KDIR=$KBUILD_OUTPUT/ で無限再帰してビルドできない; linux kernel にパッチ投げたい
