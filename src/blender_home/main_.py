"""
このファイルは Blender Python Console で以下をコピペすることで実行できる:
exec(compile(open("/home/wsh/d/s/blender_home/blender_home_.py").read(), "/home/wsh/d/s/blender_home/blender_home_.py", "exec"))

あるいは ~/.config/blender/5.1/scripts/startup/wataash_run_blender_home.py wm.run_blender_home (Alt+F5) から呼び出される

See:
- ~/d/s/blender_home/AGENTS.md
- ~/.config/blender/5.1/scripts/startup/wataash_run_blender_home.py
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
WallOrigin: TypeAlias = Literal['NB', 'NT', 'SB', 'ST', 'EB', 'ET', 'WB', 'WT', 'NE', 'NW', 'SE', 'SW']  # 法線方向の軸 (N/S または E/W または T/B) は退化するので 2 文字。法線 X の YZ 平面 → N/S+T/B、法線 Y の XZ 平面 → E/W+T/B、法線 Z の XY 平面 → N/S+E/W
CylinderDirection: TypeAlias = Literal['+X', '-X', '+Y', '-Y', '+Z', '-Z']  # 円筒が origin から伸びる方向。例 '-Z' は origin が +Z 端面 (天井側) で -Z 方向に伸びる

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
    elif ez == 0:
        if 'T' in chars or 'B' in chars:
            raise ValueError(f"XY 平面 (法線 Z) では origin に T/B を指定できません (退化軸); use N/S+E/W (例 'NE'); got {origin!r}")
        x_lo, x_hi = rng(dx, ex)
        y_lo, y_hi = rng(dy, ey)
        verts = [(x_lo, y_lo, 0.0), (x_hi, y_lo, 0.0), (x_hi, y_hi, 0.0), (x_lo, y_hi, 0.0)]
    else:
        raise ValueError(f"scale_mm {scale_mm}: 法線方向の1軸を 0 にしてください (例: (plane_w, 0, plane_h) または (0, plane_d, plane_h) または (plane_w, plane_d, 0))")
    mesh = D.meshes.new(name)  # bpy.data.meshes.new で mesh datablock を直接作成 (Add > Mesh > Plane に相当)
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])  # 頂点と面を一括投入
    mesh.update()
    obj = D.objects.new(name, mesh)  # bpy.data.objects.new で object を作成
    collection.objects.link(obj)  # M > Room1 (object を collection に link)
    obj.location = mm(*location_mm)  # Sidebar(N) > Item > Location (壁の min(x), min(y), z=0 の隅、mm → m 変換)
    obj.parent = parent  # Plane を選択、最後に Empty を選択 > Ctrl+P > Object
    obj.data.materials.append(material)  # Properties > Material > Material Slot へ割り当て
    return obj


def create_cylinder(
    name: str,
    location_mm: Location3,   # mm 単位。origin の parent ローカル位置
    size_mm: Dimensions3,     # mm 単位。(dx, dy, dz) — 主軸方向は長さ、他 2 軸は楕円断面の径 (同じなら円)
    material: bpy.types.Material | None,
    parent: bpy.types.Object,
    collection: bpy.types.Collection,
    direction: CylinderDirection,  # origin から円筒が伸びる方向。例 '-Z' は origin が +Z 端面 (天井) で下方に伸びる
    vertices: int = 32,
) -> bpy.types.Object:
    sign, axis = direction[0], direction[1]
    d = +1 if sign == '+' else -1  # 伸びる向き。verts (主軸 ±0.5) を d 方向に +0.5 shift して origin を反対側端面に持っていく
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1, vertices=vertices)  # Add > Mesh > Cylinder (Z 軸沿い、verts は z=±0.5、xy 半径 0.5、origin は中心)
    obj = C.object  # 直前の Add で作成され、Active Object になった Cylinder
    move_to_collection(obj, collection)
    obj.name = name  # Properties > Object > Name
    if axis == 'X':
        obj.data.transform(Matrix.Rotation(pi / 2, 4, 'Y'))   # Z軸沿いの mesh を Y 軸回り +90° 回転して X 軸沿いに (Edit Mode で R Y 90 相当、mesh datablock を直接編集するので Object rotation は触らない)
    elif axis == 'Y':
        obj.data.transform(Matrix.Rotation(-pi / 2, 4, 'X'))  # X 軸回り -90° 回転で Z → Y (R X -90 相当)
    shift = {'X': (d * 0.5, 0, 0), 'Y': (0, d * 0.5, 0), 'Z': (0, 0, d * 0.5)}[axis]  # 主軸方向に半長 shift して反対側端面を origin に
    obj.data.transform(Matrix.Translation(shift))  # G で平行移動相当、mesh verts を shift
    obj.dimensions = mm(*size_mm)  # Sidebar(N) > Item > Dimensions (内部は m なので mm → m 変換)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)  # Ctrl+A > Scale
    obj.location = mm(*location_mm)  # Sidebar(N) > Item > Location
    obj.parent = parent  # Ctrl+P > Object
    if material is not None:
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
# common

mat_floor           = get_or_create_material('floor_light_gray' , (0.72, 0.72, 0.70, 1))
mat_wallpaper_white = get_or_create_material('wallpaper_white'  , (0.95, 0.94, 0.92, 1))
mat_wood_brown      = get_or_create_material('wood_brown'       , (0.45, 0.28, 0.15, 1))
mat_kitchen_yellow  = get_or_create_material('kitchen_yellow'   , (0.92, 0.80, 0.30, 1))
mat_door_cream      = get_or_create_material('door_cream'       , (0.96, 0.90, 0.75, 1))
mat_metal_silver    = get_or_create_material('metal_silver'     , (0.60, 0.60, 0.62, 1))

# ------------------------------------------------------------------------------
# Room2

collection_room2 = D.collections.new('Room2')  # M > New Collection
C.scene.collection.children.link(collection_room2)  # Outliner で Scene Collection 直下に配置

room2_empty = D.objects.new('EMPTY_Room2_Origin', None)  # Add > Empty > Plain Axes
collection_room2.objects.link(room2_empty)  # M > Room2
room2_empty.empty_display_type = 'ARROWS'  # Properties > Data > Empty > Display As: Arrows
room2_empty.empty_display_size = 0.5  # Properties > Data > Empty > Size: 500 mm
room2_empty.location = mm(0, 0, 0)  # Sidebar(N) > Item > Location

room2_empty_se = D.objects.new('EMPTY_Room2_SE', None)  # Add > Empty > Plain Axes
collection_room2.objects.link(room2_empty_se)  # M > Room2
room2_empty_se.empty_display_type = 'ARROWS'  # Properties > Data > Empty > Display As: Arrows
room2_empty_se.empty_display_size = 0.5  # Properties > Data > Empty > Size: 500 mm
room2_empty_se.parent = room2_empty  # Ctrl+P > Object
room2_empty_se.location = mm(3450, 0, 0)  # SEB コーナー: (max_x, min_y, min_z)

#   =                                             , ( 123456789012345678901234567890 , 123456789012345678901234567890 , 123456789012345678901234567890 ), ( 123456789012345678901234567890 , 123456789012345678901234567890 , 123456789012345678901234567890 ), material
#   =                                             , ( location x                     , y                              , z                              ), ( dimension x                    , y                              , z                              ), material
obj = create_wall_plane('Room2_Wall_W_Below'      , (0                               , 0                              , 0                              ), (0                               , 3690                           , 1100                           ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Wall_W_Above'      , (0                               , 0                              , 2004                           ), (0                               , 3690                           , 2400-2004                      ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Wall_W_Left'       , (0                               , 0                              , 1100                           ), (0                               , 1360                           , 2004-1100                      ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Wall_W_Right'      , (0                               , 1728                           , 1100                           ), (0                               , 3690-1728                      , 2004-1100                      ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Wall_S_Below'      , (0                               , 0                              , 0                              ), (3450                            , 0                              , 900                            ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Wall_S_Above'      , (0                               , 0                              , 2200                           ), (3450                            , 0                              , 2400-2200                      ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Wall_S_Left'       , (0                               , 0                              , 900                            ), (900                             , 0                              , 2200-900                       ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Wall_S_Right'      , (2550                            , 0                              , 900                            ), (3450-2550                       , 0                              , 2200-900                       ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Wall_E_Below'      , (0                               , 0                              , 0                              ), (0                               , 1180                           , 900                            ), mat_wallpaper_white, room2_empty_se, collection_room2)
obj = create_wall_plane('Room2_Wall_E_Right'      , (0                               , 870                            , 900                            ), (0                               , 1180-870                       , 2180-900                       ), mat_wallpaper_white, room2_empty_se, collection_room2)
obj = create_wall_plane('Room2_Wall_E_Above'      , (0                               , 0                              , 2180                           ), (0                               , 1180                           , 2400-2180                      ), mat_wallpaper_white, room2_empty_se, collection_room2)
obj = create_wall_plane('Room2_Wall_E_Beam'       , (0                               , 1180                           , 2010                           ), (0                               , 2808-1180                      , 390                            ), mat_wallpaper_white, room2_empty_se, collection_room2, origin='SB')
obj = create_box('Room2_BayWindow_E_Sill'         , (-8+170.123                      , 0                              , 901                            ), (170.123                         , 890                            , 22                             ), mat_door_cream     , room2_empty_se, collection_room2, origin='SET')  # 出窓の土台: Wall_E から -x 方向に 8mm せり出す
obj = create_wall_plane('Room2_BayWindow_E_Wall_S', (0                               , 0                              , 900                            ), (162.246                         , 0                              , 1280                           ), mat_wallpaper_white, room2_empty_se, collection_room2)  # 出窓 S 壁
obj = create_wall_plane('Room2_BayWindow_E_Wall_N', (0                               , 870                            , 900                            ), (162.246                         , 0                              , 1280                           ), mat_wallpaper_white, room2_empty_se, collection_room2)  # 出窓 N 壁
obj = create_wall_plane('Room2_BayWindow_E_Wall_T', (0                               , 0                              , 2180                           ), (162.246                         , 870                            , 0                              ), mat_wallpaper_white, room2_empty_se, collection_room2)  # 出窓 T 壁
obj = create_wall_plane('Room2_Wall_N'            , (0                               , 2808                           , 0                              ), (3450-1695                       , 0                              , 2400                           ), mat_wallpaper_white, room2_empty_se, collection_room2, origin='EB')

obj = create_wall_plane('Room2_Closet_Wall_N'     , (0                               , 3690                           , 0                              ), (1685                            , 0                              , 2400                           ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_wall_plane('Room2_Closet_Wall_E'     , (1685                            , 2808                           , 0                              ), (0                               , 3690-2808                      , 2400                           ), mat_wallpaper_white, room2_empty, collection_room2)
obj = create_box('Room2_Closet_Door'              , (0                               , 2808                           , 0                              ), (1695                            , 27                             , 2400                           ), mat_door_cream     , room2_empty, collection_room2, origin='SWB')

obj = create_wall_plane('Room2_Door_Wall_S'       , (0                               , 1180                           , 0                              ), (50.123                          , 0                              , 2010                           ), mat_wallpaper_white, room2_empty_se, collection_room2)
obj = create_wall_plane('Room2_Door_Wall_N'       , (0                               , 2808                           , 0                              ), (50.123                          , 0                              , 2010                           ), mat_wallpaper_white, room2_empty_se, collection_room2)
obj = create_wall_plane('Room2_Door_Wall_T'       , (0                               , 1180                           , 2020.123                       ), (50.123                          , 2808-1180                      , 0                              ), mat_wallpaper_white, room2_empty_se, collection_room2, origin='SW')
obj = create_box('Room2_DoorFrame_N'              , (54.123                          , 2808                           , 0                              ), (254                             , 24                             , 2020.123                       ), mat_door_cream     , room2_empty_se, collection_room2, origin='NWB')  # N ドア枠
obj = create_box('Room2_DoorFrame_S'              , (54.123                          , 1180                           , 0                              ), (254                             , 22                             , 2020.123                       ), mat_door_cream     , room2_empty_se, collection_room2, origin='SWB')  # S ドア枠
obj = create_box('Room2_DoorFrame_T'              , (54.123                          , 1180                           , 2020.123                       ), (254                             , 2808-1180                      , 24                             ), mat_door_cream     , room2_empty_se, collection_room2, origin='SWT')  # T ドア枠

obj = create_box('Room2_Baseboard_W'              , (0                               , 0                              , 0                              ), (7                               , 3690                           , 46                             ), mat_door_cream     , room2_empty, collection_room2, origin='SWB')  # 巾木
obj = create_box('Room2_Baseboard_S'              , (0                               , 0                              , 0                              ), (3450                            , 7                              , 46                             ), mat_door_cream     , room2_empty, collection_room2, origin='SWB')  # 巾木
obj = create_box('Room2_Baseboard_E'              , (0                               , 0                              , 0                              ), (7                               , 1180                           , 46                             ), mat_door_cream     , room2_empty_se, collection_room2, origin='SEB')  # 巾木
obj = create_box('Room2_Baseboard_N'              , (1685                            , 2808                           , 0                              ), (3450-1685+50                    , 7                              , 46                             ), mat_door_cream     , room2_empty, collection_room2, origin='NWB')  # 巾木

obj = create_box('Room2_CurtainRail_S'            , (-820.123                        , 0                              , 2230.123                       ), (2000.123                        , 110                            , 20.123                         ), mat_door_cream     , room2_empty_se, collection_room2, origin='SEB')  # カーテンレール
obj = create_box('Room2_CurtainRail_E'            , (0                               , 0                              , 2230.123                       ), (110                             , 955                            , 20.123                         ), mat_door_cream     , room2_empty_se, collection_room2, origin='SEB')  # カーテンレール
obj = create_box('Room2_Outlet_S_E'               , (-120                            , 0                              , 185                            ), (80                              , 10                             , 130                            ), mat_door_cream     , room2_empty_se, collection_room2, origin='SEB')  # コンセント
obj = create_box('Room2_Switch_N'                 , (54.123-61                       , 2808                           , 1140                           ), (70                              , 10                             , 120                            ), mat_door_cream     , room2_empty_se, collection_room2, origin='NEB')  # スイッチ (N 壁、DoorFrame_N の W 端から -30.123mm)
obj = create_box('Room2_Outlet_N'                 , (54.123-61                       , 2808                           , 195                            ), (70                              , 10                             , 120                            ), mat_door_cream     , room2_empty_se, collection_room2, origin='NEB')  # スイッチ (N 壁、DoorFrame_N の W 端から -30.123mm)
obj = create_cylinder('Room2_FireAlarm'           , (-600.123                        , 1400.123                       , 2400                           ), (100.123                         , 100.123                        , 50.123                         ), mat_wallpaper_white, room2_empty_se, collection_room2, direction='-Z')  # 火災報知器

obj = create_box('Room2_Shelf_Base_S'            , (0                                , 0                              , 0                              ), (910                             , 38                             , 89                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf_Post_SE'           , (0                                , 0                              , 89                             ), (89                              , 38                             , 1750                           ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf_Post_SW'           , (-(910-97.123)                    , 0                              , 89                             ), (89                              , 38                             , 1750                           ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SWB')
obj = create_box('Room2_Shelf_Top_S'             , (170                              , 0                              , 89+1750                        ), (910+170                         , 38                             , 89                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf_Base_N'            , (50.123                           , 2808                           , 0                              ), (910+50.123                      , 38                             , 89                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='NEB')
obj = create_box('Room2_Shelf_Post_NE'           , (-100.123                         , 2808                           , 89                             ), (89                              , 38                             , 1750                           ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='NEB')
obj = create_box('Room2_Shelf_Post_NW'           , (-(910)                           , 2808                           , 89                             ), (89                              , 38                             , 1750                           ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='NWB')
obj = create_box('Room2_Shelf_Top_N'             , (50.123                           , 2808                           , 89+1750                        ), (910+50.123                      , 38                             , 89                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='NEB')
obj = create_box('Room2_Shelf_TopRail_E1'        , (0                                , 0                              , 89+1750+89                     ), (89                              , 2808                           , 38                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf_TopRail_E2'        , (-(89+((910-89)/3-89))*1          , 0                              , 89+1750+89                     ), (89                              , 2808                           , 38                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf_TopRail_E3'        , (-(89+((910-89)/3-89))*2          , 0                              , 89+1750+89                     ), (89                              , 2808                           , 38                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf_TopRail_E4'        , (-(89+((910-89)/3-89))*3          , 0                              , 89+1750+89                     ), (89                              , 2808                           , 38                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf_Board_LowerS'      , (0                                , 0                              , 89+1750+89+38                  ), (910                             , 1820                           , 9                              ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_box('Room2_Shelf_Board_LowerN'      , (0                                , 1820                           , 89+1750+89+38                  ), (910                             , 2808-1820                      , 9                              ), mat_wallpaper_white     , room2_empty_se, collection_room2, origin='SEB')
obj = create_cylinder('Room2_Shelf_HangerPipeEE' , (-(89+((910-89)/3-89))*1          , 100                            , 1850.123                       ), (30                              , 2600.123                       , 30                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, direction='+Y')
obj = create_cylinder('Room2_Shelf_HangerPipeEW' , (-750                             , 100                            , 1850.123                       ), (30                              , 2600.123                       , 30                             ), mat_wallpaper_white     , room2_empty_se, collection_room2, direction='+Y')
obj = create_box('Room2_Shelf_Bracket_1'         , (-(89+((910-89)/3-89))*1          , 100                            , 89+1750+89+38                  ), (1                               , 16                             , 61                             ), mat_metal_silver        , room2_empty_se, collection_room2, origin='SWT')  # 金属の金具: W 面を TopRail_E2 の E 面に、T 面を Board_LowerN の B 面に接触; S から 100mm (Bracket_1-4 は等間隔: min_y を 100 〜 (2808-100)-16 で 3 等分)
obj = create_box('Room2_Shelf_Bracket_2'         , (-(89+((910-89)/3-89))*1          , 100+(2808-100*2-16)/3          , 89+1750+89+38                  ), (1                               , 16                             , 61                             ), mat_metal_silver        , room2_empty_se, collection_room2, origin='SWT')  # 金属の金具: 同上、min_y = 100+(2808-100*2-16)/3
obj = create_box('Room2_Shelf_Bracket_3'         , (-(89+((910-89)/3-89))*1          , 100+(2808-100*2-16)/3*2        , 89+1750+89+38                  ), (1                               , 16                             , 61                             ), mat_metal_silver        , room2_empty_se, collection_room2, origin='SWT')  # 金属の金具: 同上、min_y = 100+(2808-100*2-16)/3*2
obj = create_box('Room2_Shelf_Bracket_4'         , (-(89+((910-89)/3-89))*1          , 2808-100                       , 89+1750+89+38                  ), (1                               , 16                             , 61                             ), mat_metal_silver        , room2_empty_se, collection_room2, origin='NWT')  # 金属の金具: W 面を TopRail_E2 の E 面に、T 面を Board_LowerN の B 面に接触; N から 100mm

# # Room2_Shelf_Board_LowerS に火災報知器のためのくり抜き
# _board = D.objects['Room2_Shelf_Board_LowerS']
# _cutter = create_cylinder('_cutter_tmp', (-900, 1400, 0), (800, 800, 2400), None, room2_empty_se, collection_room2, direction='+Z')
# _mod = _board.modifiers.new('hole', 'BOOLEAN'); _mod.operation = 'DIFFERENCE'; _mod.object = _cutter  # Properties > Modifier > Boolean
# C.view_layer.objects.active = _board
# bpy.ops.object.modifier_apply(modifier=_mod.name)  # Modifier > Apply
# D.objects.remove(_cutter, do_unlink=True)

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

# temporary
del_ = lambda name: D.objects.remove(D.objects[name], do_unlink=True)
del_('Room2_Baseboard_W')
del_('Room2_Closet_Door')
del_('Room2_Closet_Wall_E')
del_('Room2_Closet_Wall_N')
del_('Room2_Wall_W_Above')
del_('Room2_Wall_W_Below')
del_('Room2_Wall_W_Left')
del_('Room2_Wall_W_Right')
_purge_collection_recursive(D.collections['Room2_Bed'])  # Outliner > Right Click > Delete Hierarchy

# ------------------------------------------------------------------------------

'''
(lambda: exit())()
exec(compile(open("/home/wsh/d/s/blender_home/blender_home_.py").read(), "/home/wsh/d/s/blender_home/blender_home_.py", "exec"))
'''
