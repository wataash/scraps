# dumpall / cdumpall: dump the full context at the current frame -- backtrace,
# current location, process context, then all args+locals with pointers
# dereferenced one level. Generic across functions.
#   dumpall  ... print to the gdb console
#   cdumpall ... same, and also copy to the (Wayland) clipboard via wl-copy

import gdb
import subprocess


def _run(cmd):
    "execute a gdb command, swallowing errors (feature may be unavailable)"
    try:
        return gdb.execute(cmd, to_string=True)
    except gdb.error as e:
        return "  <%s: %s>\n" % (cmd, e)


def _collect():
    "build the full context dump as a string"
    frame = gdb.selected_frame()
    out = []

    out.append("########## backtrace ##########\n")
    out.append(_run("bt"))
    out.append("########## location ##########\n")
    out.append(_run("frame"))
    out.append("########## process ##########\n")
    out.append(_process())
    out.append("########## args + locals ##########\n")

    block = frame.block()
    seen = set()
    while block:
        for sym in block:
            if sym.is_argument or sym.is_variable:
                if sym.name in seen:
                    continue
                seen.add(sym.name)
                out.append(_show(sym, frame))
        if block.function:   # 関数スコープより上(グローバル)は辿らない
            break
        block = block.superblock

    return "".join(out)


def _show(sym, frame):
    "format one symbol, dereferencing struct/union pointers one level"
    val = sym.value(frame)
    t = val.type.strip_typedefs()
    lines = ["=== %s ===\n" % sym.name, "%s\n" % val]
    # ポインタかつ NULL でなく、指す先が構造体/共用体なら一段展開
    if t.code == gdb.TYPE_CODE_PTR and int(val) != 0:
        tgt = t.target().strip_typedefs()
        if tgt.code in (gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION):
            try:
                lines.append("  *%s = %s\n" % (sym.name, val.dereference()))
            except gdb.MemoryError:
                lines.append("  *%s = <unreadable>\n" % sym.name)
    return "".join(lines)


def _process():
    "current process context via lx-symbols helpers, if loaded"
    try:
        cur = gdb.parse_and_eval("$lx_current()")
        return "pid=%s comm=%s\n" % (cur["pid"], cur["comm"].string())
    except gdb.error:
        return "  <lx_current unavailable: scripts/gdb not loaded?>\n"


class DumpAll(gdb.Command):
    "dump full context: backtrace, location, process, args+locals"

    def __init__(self):
        super().__init__("dumpall", gdb.COMMAND_USER)

    def invoke(self, arg, from_tty):
        print(_collect(), end="")


class CDumpAll(gdb.Command):
    "like dumpall, but also copy the output to the Wayland clipboard (wl-copy)"

    def __init__(self):
        super().__init__("cdumpall", gdb.COMMAND_USER)

    def invoke(self, arg, from_tty):
        text = _collect()
        print(text, end="")
        try:
            subprocess.run(["wl-copy"], input=text.encode(), check=True)
            print("[cdumpall] copied to clipboard")
        except (OSError, subprocess.CalledProcessError) as e:
            print("[cdumpall] wl-copy failed: %s" % e)


DumpAll()
CDumpAll()
