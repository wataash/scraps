"""
MUJI 木製ベッドフレーム オーク材突板 セミダブル (商品番号 12892151) + 木製脚 12cm
https://www.muji.com/jp/ja/store/cmdty/detail/4550512892151

仕様シートより:
  外寸 1230(W) × 2020(D) × 55(H) mm (フレーム単体)
  長手フレーム 2020×70×55 × 2
  短手フレーム 1090×70×55 × 2
  ウッドスプリング 5本 552×1087 ×2枚 + 6本 704×1087 ×1枚 (計16本のスラット)
  センターバー: 鋼製 (2本でスラット領域を3分割)
  脚 12cm (別売)
"""
from __future__ import annotations

import bpy
from mathutils import Matrix

C = bpy.context
D = bpy.data


def build(*, parent: bpy.types.Object, collection: bpy.types.Collection,
          name_prefix: str,
          create_box, mm, get_or_create_material, move_to_collection):
    """name_prefix の下にベッド一式を生成。helpers は main から注入する。
    パーツは `{name_prefix}` という子 Collection にまとめる (Outliner で一括選択しやすく)。"""
    bed_collection = D.collections.new(name_prefix)  # M > New Collection
    collection.children.link(bed_collection)         # Outliner で親 Collection 直下に配置
    collection = bed_collection                       # 以降の create_box / cylinder はこの子 Collection へ
    mat_oak       = get_or_create_material('oak'      , (0.78, 0.62, 0.42, 1))
    mat_steel_blk = get_or_create_material('steel_blk', (0.10, 0.10, 0.10, 1))
    mat_slat      = get_or_create_material('slat_ply' , (0.85, 0.70, 0.50, 1))

    bed_leg_h   = 120
    bed_frame_h = 55
    bed_rail_w  = 70
    bed_w       = 1230
    bed_d       = 2020

    # 長手レール
    create_box(f'{name_prefix}_Rail_L_W', (0               , 0               , bed_leg_h), (bed_rail_w        , bed_d     , bed_frame_h), mat_oak, parent, collection, origin='SWB')
    create_box(f'{name_prefix}_Rail_L_E', (bed_w-bed_rail_w, 0               , bed_leg_h), (bed_rail_w        , bed_d     , bed_frame_h), mat_oak, parent, collection, origin='SWB')
    # 短手レール
    create_box(f'{name_prefix}_Rail_S_S', (bed_rail_w      , 0               , bed_leg_h), (bed_w-2*bed_rail_w, bed_rail_w, bed_frame_h), mat_oak, parent, collection, origin='SWB')
    create_box(f'{name_prefix}_Rail_S_N', (bed_rail_w      , bed_d-bed_rail_w, bed_leg_h), (bed_w-2*bed_rail_w, bed_rail_w, bed_frame_h), mat_oak, parent, collection, origin='SWB')

    # センターバー: スラット領域 (y 70→1950) を 552 + 36 + 704 + 36 + 552 に分割
    bar_w   = 36
    bar_h   = 25
    bar_z   = bed_leg_h + bed_frame_h - bar_h
    inner_x = bed_rail_w
    inner_w = bed_w - 2*bed_rail_w
    y0 = bed_rail_w
    y_panel1, y_panel2, y_panel3 = 552, 704, 552
    y_bar1 = y0 + y_panel1
    y_bar2 = y_bar1 + bar_w + y_panel2
    create_box(f'{name_prefix}_CenterBar_1', (inner_x, y_bar1, bar_z), (inner_w, bar_w, bar_h), mat_steel_blk, parent, collection, origin='SWB')
    create_box(f'{name_prefix}_CenterBar_2', (inner_x, y_bar2, bar_z), (inner_w, bar_w, bar_h), mat_steel_blk, parent, collection, origin='SWB')

    # ウッドスプリング (スラット)
    slat_x_lo = bed_rail_w + 3
    slat_len  = inner_w - 6
    slat_w_mm = 68
    slat_h    = 9
    slat_z    = bed_leg_h + bed_frame_h - slat_h
    def _slat_centers(y_start: float, panel_len: float, n: int) -> list[float]:
        step = panel_len / n
        return [y_start + step * (i + 0.5) for i in range(n)]
    panels = [
        ('A', y0,                            y_panel1, 5),
        ('B', y0 + y_panel1 + bar_w,         y_panel2, 6),
        ('C', y_bar2 + bar_w,                y_panel3, 5),
    ]
    for panel_id, y_start, panel_len, n_slats in panels:
        for i, yc in enumerate(_slat_centers(y_start, panel_len, n_slats)):
            create_box(f'{name_prefix}_Slat_{panel_id}{i+1}',
                       (slat_x_lo, yc - slat_w_mm/2, slat_z),
                       (slat_len, slat_w_mm, slat_h),
                       mat_slat, parent, collection, origin='SWB')

    # 木製脚 12cm (丸脚 Φ50)
    def create_cylinder(name: str, location_mm: tuple[float, float, float], radius_mm: float, height_mm: float,
                        material: bpy.types.Material) -> bpy.types.Object:
        bpy.ops.mesh.primitive_cylinder_add(radius=radius_mm/1000, depth=height_mm/1000, vertices=24)  # Add > Mesh > Cylinder
        obj = C.object
        move_to_collection(obj, collection)
        obj.name = name
        obj.data.transform(Matrix.Translation((0, 0, height_mm/2000)))  # 底面を原点に
        obj.location = mm(location_mm[0], location_mm[1], location_mm[2])
        obj.parent = parent
        obj.data.materials.append(material)
        return obj

    leg_r = 25
    leg_inset_x = bed_rail_w / 2
    leg_inset_y_foot = bed_rail_w + 10
    leg_inset_y_head = bed_d - bed_rail_w - 10
    for _ln, (_x, _y) in [
        ('SW', (leg_inset_x        , leg_inset_y_foot)),
        ('SE', (bed_w - leg_inset_x, leg_inset_y_foot)),
        ('NW', (leg_inset_x        , leg_inset_y_head)),
        ('NE', (bed_w - leg_inset_x, leg_inset_y_head)),
    ]:
        create_cylinder(f'{name_prefix}_Leg_{_ln}', (_x, _y, 0), leg_r, bed_leg_h, mat_oak)
