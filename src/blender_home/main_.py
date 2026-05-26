"""
このファイルは Blender Python Console で以下をコピペすることで実行できる:
exec(compile(open("/home/wsh/d/s/blender_home/blender_home_.py").read(), "/home/wsh/d/s/blender_home/blender_home_.py", "exec"))

あるいは ~/.config/blender/5.1/scripts/startup/wataash_run_blender_home.py wm.run_blender_home (Alt+F5) から呼び出される

See:
- ~/d/s/blender_home/AGENTS.md
- ~/.config/blender/5.1/scripts/startup/wataash_run_blender_home.py

## agent prompts

今作ったオブジェクトを作成するpythonコードを
~/d/s/blender_home/blender_home_.py __here__
に書いて。
"""
from __future__ import annotations

import os
import site
import sys
import warnings
import types
from typing import Literal, TypeAlias

# These imports are already done by blender Python Console.
# Just for the PyCharm's static analysis.
#
# Builtin Modules:       bpy, bpy.data, bpy.ops, bpy.props, bpy.types, bpy.context, bpy.utils, gpu, blf, mathutils
# Convenience Imports:   from mathutils import *; from math import *
# Convenience Variables: C = bpy.context, D = bpy.data
import bpy
from mathutils import *
from math import *
C = bpy.context
D = bpy.data

Location3: TypeAlias = tuple[float, float, float]
Dimensions3: TypeAlias = tuple[float, float, float]
Rotation3: TypeAlias = tuple[float, float, float]
Scale3: TypeAlias = tuple[float, float, float]
Rgba: TypeAlias = tuple[float, float, float, float]
BoxOrigin: TypeAlias = Literal['NEB', 'NWB', 'SEB', 'SWB', 'NET', 'NWT', 'SET', 'SWT']  # コンパス + 上下: N=+Y, S=-Y, E=+X, W=-X, T=+Z, B=-Z。origin に来る mesh コーナーを表す
WallOrigin: TypeAlias = Literal['NB', 'NT', 'SB', 'ST', 'EB', 'ET', 'WB', 'WT']  # 法線方向の軸 (N/S または E/W) は退化するので 2 文字。法線 X の YZ 平面 → N/S+T/B、法線 Y の XZ 平面 → E/W+T/B

REPORT_LOG_PATH = "/tmp/wataash/blender_home_.log"


def log(msg):
    print(msg)
    os.makedirs(os.path.dirname(REPORT_LOG_PATH), exist_ok=True)
    with open(REPORT_LOG_PATH, "a", encoding="utf-8") as log_file:
        print(msg, file=log_file, flush=True)


def report_info(msg):
    def _draw(self, context):
        self.layout.label(text=msg)
    bpy.context.window_manager.popup_menu(_draw, title="Info", icon='INFO')
    log(msg)


def _redraw():
    # pydevd が breakpoint でメインスレッドを止めるとイベントループも止まり GUI が更新されない。
    # この operator は suspended frame からの評価でも同期的に 1 描画サイクル走らせる。
    # PyCharm Watches / Evaluate Expression からも呼べる。
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


# Blender プロセス全体で共有される名前空間。新しい .blend ファイルを開いても残り続ける。
_ns = sys.modules.setdefault('_wataash_blender_home_ns', types.ModuleType('_wataash_blender_home_ns'))
log(f'{getattr(_ns, "pydevd_connected", False)=}')
if getattr(_ns, 'pydevd_connected', False):
    log(f'PyCharm debugger already connected')
else:
    # import pydevd_pycharm  # ModuleNotFoundError: No module named 'pydevd_pycharm'
    site.getusersitepackages()  # '/home/wsh/.local/lib/python3.13/site-packages'
    if site.getusersitepackages() not in sys.path:
        log(f"Adding {site.getusersitepackages()=} to sys.path")
        sys.path.append(site.getusersitepackages())
        log(sys.path)  # ['/snap/blender/7360/5.1/scripts/startup', '/snap/blender/7360/5.1/scripts/modules', '/snap/blender/7360/5.1/python/lib/python313.zip', '/snap/blender/7360/5.1/python/lib/python3.13', '/snap/blender/7360/5.1/python/lib/python3.13/lib-dynload', '/snap/blender/7360/5.1/python/lib/python3.13/site-packages', '/snap/blender/7360/5.1/scripts/freestyle/modules', '/home/wsh/.config/blender/5.1/scripts/addons/modules', '/snap/blender/7360/5.1/scripts/addons_core', '/home/wsh/.local/lib/python3.13/site-packages']
    # import pydevd_pycharm  # ok

    # pydevd_pycharm.settrace は接続失敗時に内部で traceback を stderr に直書きするので、
    # 先にポートを軽く叩いて listen 確認してから呼ぶ
    import socket
    try:
        with socket.create_connection(('localhost', 12345), timeout=0.2):
            pass
    except OSError as exc:
        log(f'PyCharm debugger not listening on localhost:12345 ({exc}); continuing without debugger')
    else:
        os.environ['USE_LOW_IMPACT_MONITORING'] = '1'  # See /home/wsh/d/s/blender_home/pycharm_USE_LOW_IMPACT_MONITORING.md; TODO: remove me
        # copy-pasted from the PyCharm's debug configuration
        import pydevd_pycharm
        pydevd_pycharm.settrace('localhost', port=12345, stdout_to_server=True, stderr_to_server=True, suspend=False)
        _ns.pydevd_connected = True
        log('PyCharm debugger connected')


# ------------------------------------------------------------------------------

def mm(*args: float):
    """mm → m 変換。Blender 内部は m なので、コードに mm 単位で数値を書きたいときに使う。
    例: mm(857) → 0.857、mm(0, 2113.789, 0) → (0.0, 2.113789, 0.0)
    """
    return args[0] / 1000 if len(args) == 1 else tuple(a / 1000 for a in args)


def get_or_create_material(name: str, color: Rgba) -> bpy.types.Material:
    material = D.materials.get(name) or D.materials.new(name)  # Properties > Material > New
    material.diffuse_color = color  # Properties > Material > Viewport Display > Color
    return material


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for user_collection in list(obj.users_collection):
        user_collection.objects.unlink(obj)  # M > 移動先 Collection へ移す前に元 Collection から外す
    collection.objects.link(obj)  # M > Collection を選択


def create_box(
    name: str,
    location_mm: Location3,   # mm 単位。origin の parent ローカル位置
    size_mm: Dimensions3,     # mm 単位。(w, d, h)。Cube は origin から `origin` で指定したコーナーの反対側に伸びる
    material: bpy.types.Material | None,
    parent: bpy.types.Object,
    collection: bpy.types.Collection,
    origin: BoxOrigin = 'SEB',  # origin に来る mesh コーナー。例: 'NEB' = (max_x, max_y, min_z) = North-East-Bottom
) -> bpy.types.Object:
    sx = +1 if origin[1] == 'E' else -1  # E → +X, W → -X
    sy = +1 if origin[0] == 'N' else -1  # N → +Y, S → -Y
    sz = +1 if origin[2] == 'T' else -1  # T → +Z, B → -Z
    bpy.ops.mesh.primitive_cube_add(size=1)  # Add > Mesh > Cube (verts は ±0.5, origin は中心)
    obj = C.object  # 直前の Add で作成され、Active Object になった Cube
    move_to_collection(obj, collection)
    obj.name = name  # Properties > Object > Name
    obj.data.transform(Matrix.Translation((-sx * 0.5, -sy * 0.5, -sz * 0.5)))  # mesh verts を shift して指定コーナー (sx,sy,sz)*0.5 を origin に持っていく; Edit Mode で頂点を全選択 > G で平行移動するのと同等 (mesh datablock 自体を編集するので Object の location は動かない)
    obj.dimensions = mm(*size_mm)  # Sidebar(N) > Item > Dimensions (内部は m なので mm → m 変換)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)  # Ctrl+A > Scale
    obj.location = mm(*location_mm)  # Sidebar(N) > Item > Location (内部は m なので mm → m 変換)
    obj.parent = parent  # Object を選択、最後に parent を選択 > Ctrl+P > Object
    if material is not None:
        obj.data.materials.append(material)  # Properties > Material > Material Slot へ割り当て
    return obj


def create_wall_plane(
    name: str,
    location_mm: Location3,   # mm 単位。origin の parent ローカル位置
    scale_mm: Scale3,         # mm 単位。法線方向の軸を 0 に。例: (plane_w, 0, plane_h) → 法線 Y / XZ 平面 / 幅 plane_w × 高さ plane_h、(0, plane_d, plane_h) → 法線 X / YZ 平面
    material: bpy.types.Material,
    parent: bpy.types.Object,
    collection: bpy.types.Collection,
    origin: WallOrigin | None = None,  # origin に来る壁コーナー。デフォルト None は min コーナー (法線 X→'SB'、法線 Y→'WB' と等価)。法線 X (YZ 平面) は N/S+T/B (例 'NB')、法線 Y (XZ 平面) は E/W+T/B (例 'ET')
) -> bpy.types.Object:
    ex, ey, ez = mm(*scale_mm)  # mm → m (extents、法線方向の1軸は 0)
    chars = set(origin) if origin is not None else set()
    dx = +1 if 'E' in chars else -1  # 未指定なら -1 (W = min_x 側)
    dy = +1 if 'N' in chars else -1  # 未指定なら -1 (S = min_y 側)
    dz = +1 if 'T' in chars else -1  # 未指定なら -1 (B = min_z 側)
    def rng(d: int, e: float) -> tuple[float, float]:
        return (-e, 0.0) if d == +1 else (0.0, e)  # origin が + 側なら verts は [-extent, 0]、- 側なら [0, +extent]
    if ex == 0:
        if 'E' in chars or 'W' in chars:
            raise ValueError(f"YZ 平面 (法線 X) では origin に E/W を指定できません (退化軸); use N/S+T/B (例 'NB'); got {origin!r}")
        y_lo, y_hi = rng(dy, ey)
        z_lo, z_hi = rng(dz, ez)
        verts = [(0.0, y_lo, z_lo), (0.0, y_hi, z_lo), (0.0, y_hi, z_hi), (0.0, y_lo, z_hi)]
    elif ey == 0:
        if 'N' in chars or 'S' in chars:
            raise ValueError(f"XZ 平面 (法線 Y) では origin に N/S を指定できません (退化軸); use E/W+T/B (例 'ET'); got {origin!r}")
        x_lo, x_hi = rng(dx, ex)
        z_lo, z_hi = rng(dz, ez)
        verts = [(x_lo, 0.0, z_lo), (x_hi, 0.0, z_lo), (x_hi, 0.0, z_hi), (x_lo, 0.0, z_hi)]
    else:
        raise ValueError(f"scale_mm {scale_mm}: 法線方向の1軸を 0 にしてください (例: (plane_w, 0, plane_h) または (0, plane_d, plane_h))")
    mesh = D.meshes.new(name)  # bpy.data.meshes.new で mesh datablock を直接作成 (Add > Mesh > Plane に相当)
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])  # 頂点と面を一括投入
    mesh.update()
    obj = D.objects.new(name, mesh)  # bpy.data.objects.new で object を作成
    collection.objects.link(obj)  # M > Room1 (object を collection に link)
    obj.location = mm(*location_mm)  # Sidebar(N) > Item > Location (壁の min(x), min(y), z=0 の隅、mm → m 変換)
    obj.parent = parent  # Plane を選択、最後に Empty を選択 > Ctrl+P > Object
    obj.data.materials.append(material)  # Properties > Material > Material Slot へ割り当て
    return obj


# (lambda: exit())()  # ここで exit() すれば以降の行は blender Python Console でコピペ実行できる; 普通に exit() だと、以降の行が PyCharm で灰色になってしまうので lambda にしてある

# ------------------------------------------------------------------------------
# Initialize

# assert C.screen.areas[0].ui_type == 'PROPERTIES', f"C.screen.areas[0].ui_type={C.screen.areas[0].ui_type}"
# assert C.screen.areas[1].ui_type == 'OUTLINER', f"C.screen.areas[1].ui_type={C.screen.areas[1].ui_type}"
# assert C.screen.areas[2].ui_type == 'TIMELINE', f"C.screen.areas[2].ui_type={C.screen.areas[2].ui_type}"
# assert C.screen.areas[3].ui_type == 'VIEW_3D', f"C.screen.areas[3].ui_type={C.screen.areas[3].ui_type}"

# CONSOLE エリアを探す。なければ areas[2] (このユーザーのレイアウトでは下端) を CONSOLE に切り替える
console_area = next((a for a in C.screen.areas if a.ui_type == 'CONSOLE'), None)
if console_area is None:
    C.screen.areas[2].ui_type = 'CONSOLE'  # Editor Type > Python Console
    console_area = C.screen.areas[2]

C.screen.areas[3].spaces.active.show_region_ui = True  # N
# C.screen.areas[3].spaces.active.shading.type = 'MATERIAL'  # Z > Material Preview; 'WIREFRAME' | 'SOLID' | 'MATERIAL' | 'RENDERED'

C.scene.unit_settings.length_unit = 'MILLIMETERS'  # Properties > Scene > Length: Millimeters

# 最初まで undo 相当: 前回 run で script が作った collection と中身を削除
# 注: bpy.ops.ed.undo はスクリプト context では効かず、read_homefile は context を壊すため、明示削除で代用
# Outliner > Right Click > Delete Hierarchy 相当
def _purge_collection_recursive(_col: bpy.types.Collection) -> None:
    for _child in list(_col.children):
        _purge_collection_recursive(_child)  # 子 Collection を先に
    for _o in list(_col.objects):
        D.objects.remove(_o, do_unlink=True)  # X > Delete
    D.collections.remove(_col)  # Outliner > Delete Collection
for _col_name in ('Room1', 'Room2'):
    _col = D.collections.get(_col_name)
    if _col is not None:
        _purge_collection_recursive(_col)
for _mesh in list(D.meshes):
    if _mesh.users == 0:
        D.meshes.remove(_mesh)  # orphan mesh datablock を掃除

# Default Cube を削除 (新規 .blend 起動直後の Cube を消す); Object Mode で 'Cube' を選択 > X > Delete
cube = D.objects.get('Cube')
if cube is not None:
    D.objects.remove(cube, do_unlink=True)  # X > Delete

# ------------------------------------------------------------------------------
# Room1

collection_room1 = D.collections.new('Room1')  # M > New Collection / Outliner > Right Click > New Collection
C.scene.collection.children.link(collection_room1)  # Outliner で Scene Collection 直下に配置

mat_floor           = get_or_create_material('floor_light_gray' , (0.72, 0.72, 0.70, 1))
mat_wallpaper_white = get_or_create_material('wallpaper_white'  , (0.95, 0.94, 0.92, 1))
mat_wood_brown      = get_or_create_material('wood_brown'       , (0.45, 0.28, 0.15, 1))
mat_kitchen_yellow  = get_or_create_material('kitchen_yellow'   , (0.92, 0.80, 0.30, 1))
mat_door_cream      = get_or_create_material('door_cream'       , (0.96, 0.90, 0.75, 1))

room_empty = D.objects.new('EMPTY_Room_Origin_location_0_0_0', None)  # Add > Empty > Plain Axes
collection_room1.objects.link(room_empty)  # M > Room1
room_empty.empty_display_type = 'ARROWS'  # Properties > Data > Empty > Display As: Arrows
room_empty.empty_display_size = 0.8  # Properties > Data > Empty > Size: 800 mm

r'''
  y
  ↑
 ↙ → x
z
z Height: 2400
'''

plane_w = 3420  # mm; width of Wall_S
plane_d = 4346  # mm; width of Wall_E
plane_h = 2400  # mm

# Room1_Wall_S: 窓 (x 824.123→2474.123, z 700→2200) を抜いた 4 枚の plane で構成
create_wall_plane('Room1_Wall_S_Below' , (0       , 0       , 0    ), (plane_w          , 0       , 700          ) , mat_wallpaper_white, room_empty, collection_room1)  # 窓下: x 0→plane_w, z 0→700
create_wall_plane('Room1_Wall_S_Above' , (0       , 0       , 2200 ), (plane_w          , 0       , plane_h-2200 ) , mat_wallpaper_white, room_empty, collection_room1)  # 窓上: x 0→plane_w, z 2200→2400
create_wall_plane('Room1_Wall_S_Left'  , (0       , 0       , 700  ), (824.123          , 0       , 2200-700     ) , mat_wallpaper_white, room_empty, collection_room1)  # 窓左: x 0→824.123, z 700→2200
create_wall_plane('Room1_Wall_S_Right' , (2474.123, 0       , 700  ), (plane_w-2474.123 , 0       , 2200-700     ) , mat_wallpaper_white, room_empty, collection_room1)  # 窓右: x 2474.123→plane_w, z 700→2200
create_wall_plane('Room1_Wall_S_Ext_W' , (0       , 0       , 0    ), (245              , 0       , plane_h      ) , mat_wallpaper_white, room_empty, collection_room1, origin='EB')
create_wall_plane('Room1_Wall_N'       , (0       , plane_d , 0    ), (plane_w          , 0       , plane_h      ) , mat_wallpaper_white, room_empty, collection_room1)
create_wall_plane('Room1_Wall_E'       , (plane_w , 0       , 0    ), (0                , plane_d , plane_h      ) , mat_wallpaper_white, room_empty, collection_room1)

# 0.123 mm は、正確に実測できていない値。2113.123 = 2113 mm **くらい**
obj = create_box('Room1_Wall_E_Partition'     , (0      , 2113.123       , 0), (857 , 136 , 2400), mat_wallpaper_white, D.objects['Room1_Wall_E'], collection_room1)
obj = create_box('Room1_Shoe_Cabinet'         , (0      , 2113.123 + 136 , 0), (804 , 363 ,  888), mat_wood_brown     , D.objects['Room1_Wall_E'], collection_room1)
obj = create_box('Room1_Wall_N_Partition'     , (0      , 0              , 0), (134 , 672 , 2400), mat_wallpaper_white, D.objects['Room1_Wall_N'], collection_room1, origin='NEB') ; obj.matrix_parent_inverse = Matrix.Translation(mm(plane_w - 854.123, 0, 0))  # location=(0,0,0) で見た目を保つため X オフセットを parent inverse に焼く
obj = create_box('Room1_Kitchen_Upper_Cabinet', (0      , 0              , 0), (1650, 360 ,  725), mat_kitchen_yellow , room_empty               , collection_room1, origin='NWT') ; obj.matrix_parent_inverse = Matrix.Translation(mm(0, plane_d, plane_h))  # location=(0,0,0) で見た目を保つためオフセットを parent inverse に焼く (Ctrl+P 相当)
obj = create_box('Room1_Kitchen'              , (0      , 0              , 0), (1650, 595 ,  850), mat_kitchen_yellow , room_empty               , collection_room1, origin='NWB') ; obj.matrix_parent_inverse = Matrix.Translation(mm(0, plane_d, 0))  # location=(0,0,0) で見た目を保つためオフセットを parent inverse に焼く (Ctrl+P 相当)

obj = create_box('Room1_Beam_W'               , (0      , 0             , 0), (245 , 4340,  390), mat_wallpaper_white, room_empty               , collection_room1, origin='SET') ; obj.matrix_parent_inverse = Matrix.Translation(mm(0, 0, plane_h))
obj = create_box('Room1_Column_NW'            , (0      , 4340          , 0), (250 , 880 , 2400), mat_wallpaper_white, room_empty               , collection_room1, origin='NEB')
obj = create_box('Room1_Column_N2'            , (0      , 1514.123      , 0), (250 , 1100, 2400), mat_wallpaper_white, room_empty               , collection_room1, origin='SEB')
obj = create_box('Room1_Door'                 , (-96.123, 1671.123      , 0), (65  , 840 , 1950), mat_door_cream     , room_empty               , collection_room1, origin='NEB')

# room_empty.location = mm(123.123, 123.123, 0)  # Sidebar(N) > Item > Location (子は parent 追従で一緒に動く)

# ------------------------------------------------------------------------------
# Room2

collection_room2 = D.collections.new('Room2')  # M > New Collection
C.scene.collection.children.link(collection_room2)  # Outliner で Scene Collection 直下に配置

room2_empty = D.objects.new('EMPTY_Room2_Origin', None)  # Add > Empty > Plain Axes
collection_room2.objects.link(room2_empty)  # M > Room2
room2_empty.empty_display_type = 'ARROWS'  # Properties > Data > Empty > Display As: Arrows
room2_empty.empty_display_size = 0.8  # Properties > Data > Empty > Size: 800 mm
room2_empty.location = mm(-3815, -1180, 0)  # Sidebar(N) > Item > Location

# Room2_Wall_W: 窓 (y 1360→1728, z 1100→2004) を抜いた 4 枚の plane で構成
create_wall_plane('Room2_Wall_W_Below'  , (0   , 0   , 0   ), (0   , 3690     , 1100     ), mat_wallpaper_white, room2_empty, collection_room2)  # 窓下: y 0→3690, z 0→1100
create_wall_plane('Room2_Wall_W_Above'  , (0   , 0   , 2004), (0   , 3690     , 2400-2004), mat_wallpaper_white, room2_empty, collection_room2)  # 窓上: y 0→3690, z 2004→2400
create_wall_plane('Room2_Wall_W_Left'   , (0   , 0   , 1100), (0   , 1360     , 2004-1100), mat_wallpaper_white, room2_empty, collection_room2)  # 窓左: y 0→1360, z 1100→2004
create_wall_plane('Room2_Wall_W_Right'  , (0   , 1728, 1100), (0   , 3690-1728, 2004-1100), mat_wallpaper_white, room2_empty, collection_room2)  # 窓右: y 1728→3690, z 1100→2004
# Room2_Wall_S: 窓 (x 900→2550, z 900→2200) を抜いた 4 枚の plane で構成
create_wall_plane('Room2_Wall_S_Below'  , (0   , 0   , 0   ), (3570     , 0   , 900      ), mat_wallpaper_white, room2_empty, collection_room2)  # 窓下: x 0→3570, z 0→900
create_wall_plane('Room2_Wall_S_Above'  , (0   , 0   , 2200), (3570     , 0   , 2400-2200), mat_wallpaper_white, room2_empty, collection_room2)  # 窓上: x 0→3570, z 2200→2400
create_wall_plane('Room2_Wall_S_Left'   , (0   , 0   , 900 ), (900      , 0   , 2200-900 ), mat_wallpaper_white, room2_empty, collection_room2)  # 窓左: x 0→900, z 900→2200
create_wall_plane('Room2_Wall_S_Right'  , (2550, 0   , 900 ), (3570-2550, 0   , 2200-900 ), mat_wallpaper_white, room2_empty, collection_room2)  # 窓右: x 2550→3570, z 900→2200
# Room2_Wall_E: 窓穴 (y, z) ∈ [(0, 900)-(870, 2180)] を抜いた C 字型を 3 枚の plane で構成
# 窓が y=0 (Wall_S との隅) に接しているので左側ストリップは不要
create_wall_plane('Room2_Wall_E_Below'  , (3570, 0   , 0   ), (0         , 1180      , 900       ), mat_wallpaper_white, room2_empty, collection_room2)  # 窓下: y 0→1180, z 0→900
create_wall_plane('Room2_Wall_E_Right'  , (3570, 870 , 900 ), (0         , 1180-870  , 2180-900  ), mat_wallpaper_white, room2_empty, collection_room2)  # 窓右: y 870→1180, z 900→2180
create_wall_plane('Room2_Wall_E_Above'  , (3570, 0   , 2180), (0         , 1180      , 2400-2180 ), mat_wallpaper_white, room2_empty, collection_room2)  # 窓上: y 0→1180, z 2180→2400
create_wall_plane('Room2_Wall_N'        , (1685, 2808, 0   ), (3570-1685 , 0         , 2400      ), mat_wallpaper_white, room2_empty, collection_room2)                   # closet door (x=0→1685) の右、x=1685→3570
create_wall_plane('Room2_Wall_E_Beam'   , (3570, 1180, 2010), (0         , 2808-1180 , 390       ), mat_wallpaper_white, room2_empty, collection_room2, origin='SB')     # Wall_E (y 0→1180) と closet door (y 2808〜) の隙間 y 1180→2808 を埋める梁; z 2010→2400 (天井下 390mm)

create_wall_plane('Room2_Closet_Wall_N' , (0   , 3690, 0   ), (1685, 0        , 2400), mat_wallpaper_white, room2_empty, collection_room2)
create_wall_plane('Room2_Closet_Wall_E' , (1685, 2808, 0   ), (0   , 3690-2808, 2400), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_box('Room2_Closet_Door'    , (0   , 2808, 0   ), (1685, 27       , 2400), mat_door_cream     , room2_empty, collection_room2, origin='SWB')

obj = create_box('Room2_Shelf'          , (3570, 0   , 2010    ), (397 , 2767, 33  ), mat_door_cream     , room2_empty, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf'          , (3570, 0   , 2010+33 ), (700 , 2808, 9   ), mat_door_cream     , room2_empty, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf'          , (3570, 0   , 1910    ), (910 , 2808, 9   ), mat_door_cream     , room2_empty, collection_room2, origin='SEB')

# MUJI 木製ベッドフレーム シングル + 12cm 脚。詳細は blender_home_bed.py 参照
import importlib
_bed_dir = "/home/wsh/d/s/blender_home"
if _bed_dir not in sys.path:
    sys.path.append(_bed_dir)
import blender_home_bed
importlib.reload(blender_home_bed)  # 編集を毎回反映
blender_home_bed.build(
    parent=room2_empty, collection=collection_room2, name_prefix='Room2_Bed',
    create_box=create_box, mm=mm,
    get_or_create_material=get_or_create_material,
    move_to_collection=move_to_collection,
)

# ------------------------------------------------------------------------------

'''
(lambda: exit())()
exec(compile(open("/home/wsh/d/s/blender_home/blender_home_.py").read(), "/home/wsh/d/s/blender_home/blender_home_.py", "exec"))
'''
