- 下の /home/wsh/.config/blender/5.1/scripts/startup/pydevd_connect_crash.py を入れて Blender を起動
- F3 > "pydevd connect crash" を実行
  - `pydevd_pycharm.settrace('localhost', port=12345, stdout_to_server=True, stderr_to_server=True, suspend=False)` なし: Blender はクラッシュしない
  - `pydevd_pycharm.settrace('localhost', port=12345, stdout_to_server=True, stderr_to_server=True, suspend=False)` あり: Blender がクラッシュする
    - ただし `os.environ['USE_LOW_IMPACT_MONITORING'] = '1'` があればクラッシュしない

/home/wsh/.config/blender/5.1/scripts/startup/pydevd_connect_crash.py:

```py
import os
import site
import sys

import bpy

REPORT_LOG_PATH = "/tmp/blender_pydevd_connect_crash.log"


def report_info(operator, msg):
    operator.report({'INFO'}, msg)
    print(msg)
    os.makedirs(os.path.dirname(REPORT_LOG_PATH), exist_ok=True)
    with open(REPORT_LOG_PATH, "a", encoding="utf-8") as log_file:
        print(msg, file=log_file, flush=True)

class WM_OT_run_blender_home(bpy.types.Operator):
    bl_idname = "wm.wm_pydevd_connect_crash"
    bl_label = "pydevd connect crash"
    bl_description = f"pydevd connect crash description"

    def execute(self, context):
        sys.path.append(site.getusersitepackages())
        # os.environ['USE_LOW_IMPACT_MONITORING'] = '1'
        import pydevd_pycharm
        # pydevd_pycharm.settrace('localhost', port=12345, stdout_to_server=True, stderr_to_server=True, suspend=False)

        try:
            raise RuntimeError('raise test')
        except SystemExit as exc:
            report_info(self, f"~/.config/blender/5.1/scripts/startup/pydevd_connect_crash.py: execute(): {exc=}")

        report_info(self, "~/.config/blender/5.1/scripts/startup/pydevd_connect_crash.py: execute(): return")
        return {"FINISHED"}


def _draw_in_window_menu(self, context):
    self.layout.operator(WM_OT_run_blender_home.bl_idname)


def register():
    bpy.utils.register_class(WM_OT_run_blender_home)
    bpy.types.TOPBAR_MT_window.append(_draw_in_window_menu)


def unregister():
    bpy.types.TOPBAR_MT_window.remove(_draw_in_window_menu)
    bpy.utils.unregister_class(WM_OT_run_blender_home)


if __name__ == "__main__":
    register()
```
