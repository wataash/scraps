# ------------------------------------------------------------------------------
# Room1

collection_room1 = D.collections.new('Room1')  # M > New Collection / Outliner > Right Click > New Collection
C.scene.collection.children.link(collection_room1)  # Outliner で Scene Collection 直下に配置

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
obj = create_box('Room1_Column_N2'            , (0      , 1650.123      , 0), (250 , 1100, 2400), mat_wallpaper_white, room_empty               , collection_room1, origin='SEB')
obj = create_box('Room1_Door'                 , (-96.123, 1530.123      , 0), (65  , 840 , 1996.123), mat_door_cream     , room_empty               , collection_room1, origin='NEB')

# # room_empty.location = mm(123.123, 123.123, 0)  # Sidebar(N) > Item > Location (子は parent 追従で一緒に動く)
