"""
地下座敷牢 セットアップスクリプト (Blender 3.6+ / 4.x / 5.x)

やること
  1. GLB を読み込む(すでにシーンにあれば読み込まない)
  2. 壁・柱・鎖・格子などを「壁ごと」のコレクションに分類
       壁_北(奥) / 壁_南(手前) / 壁_東(階段側) / 壁_西
       床 / 天井 / 階段 / 格子(牢の枠) / 家具・小物
  3. 牢の扉を格子から切り出して「扉」オブジェクトにし、
     ヒンジ位置に原点を置いて開閉できるようにする
       「扉コントロール」エンプティのカスタムプロパティ  扉の開き(0〜1) で開閉
  4. .blend と、扉・グループが分かれた .glb を書き出す

使い方 (GUI)
  Scripting タブ → このファイルを開く → 下の GLB_PATH を直す → Run Script
使い方 (コマンドライン)
  blender -b -P setup_zashikiro.py -- 入力.glb 出力フォルダ

非表示にするとき
  アウトライナーでコレクション横の「目」アイコンをクリック
  (ビューポートのみなら画面アイコン、レンダーにも効かせるなら カメラアイコン)
"""
import bpy
import bmesh
import glob
import math
import os
import sys
from mathutils import Vector

# ---------------------------------------------------------------- 設定
GLB_PATH = r"F:\@manga-hermes\サキュバス嫌い\白狐甲号\甲号　３D\座敷牢\地下座敷牢\out"  # フォルダでも .glb 直指定でも可
OUT_DIR = ""            # 空なら GLB と同じフォルダ
DOOR_OPEN_DEG = 105.0   # 全開の角度

# 扉の範囲 (Blender座標: X右 / Y奥 / Z上)。正面格子の「扉部分」
DOOR_X0, DOOR_X1 = -0.15, 0.72
DOOR_Y0, DOOR_Y1 = -0.25, 0.10
HINGE_X, HINGE_Y = DOOR_X1, 0.0   # ヒンジは右端(ラッチの反対側)。手前(-Y)へ開く

# ---------------------------------------------------------------- 引数
argv = sys.argv
if "--" in argv:
    a = argv[argv.index("--") + 1:]
    if len(a) >= 1:
        GLB_PATH = a[0]
    if len(a) >= 2:
        OUT_DIR = a[1]

# ---------------------------------------------------------------- ユーティリティ
def find_glb(p):
    if os.path.isdir(p):
        c = sorted(glob.glob(os.path.join(p, "*.glb")) + glob.glob(os.path.join(p, "*.gltf")))
        if not c:
            raise FileNotFoundError("GLB が見つかりません: " + p)
        return c[0]
    return p


def get_or_create_collection(name, parent):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        parent.children.link(c)
    return c


def move_to(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def islands(bm):
    """頂点溶接済み bmesh の連結島 -> [set(faces)]"""
    seen, out = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        st, cur = [f], set([f])
        seen.add(f)
        while st:
            a = st.pop()
            for e in a.edges:
                for b in e.link_faces:
                    if b not in seen:
                        seen.add(b)
                        cur.add(b)
                        st.append(b)
        out.append(cur)
    return out


def split_object(src, label_of_face, name_fmt="{src}_{label}", weld=0.0):
    """
    src の面を label_of_face(bmesh_face) の値ごとに別オブジェクトへ分ける。
    戻り値 {label: object}。元の src は削除される。
    """
    bm = bmesh.new()
    bm.from_mesh(src.data)
    if weld > 0:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bm.faces.ensure_lookup_table()
    labels = {}
    for f in bm.faces:
        labels.setdefault(label_of_face(f), []).append(f.index)
    bm.free()

    result = {}
    for lab, idx in labels.items():
        if lab is None:
            continue
        bm = bmesh.new()
        bm.from_mesh(src.data)
        if weld > 0:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
        bm.faces.ensure_lookup_table()
        keep = set(idx)
        kill = [f for f in bm.faces if f.index not in keep]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        me = bpy.data.meshes.new(name_fmt.format(src=src.name, label=lab))
        bm.to_mesh(me)
        bm.free()
        for m in src.data.materials:
            me.materials.append(m)
        ob = bpy.data.objects.new(me.name, me)
        ob.matrix_world = src.matrix_world.copy()
        bpy.context.scene.collection.objects.link(ob)
        for p in me.polygons:
            p.use_smooth = src.data.polygons[0].use_smooth if len(src.data.polygons) else False
        result[lab] = ob
    return result


def world_bbox_center(face, mw):
    c = face.calc_center_median()
    return mw @ c


# ---------------------------------------------------------------- 読み込み
if "earth_walls" not in bpy.data.objects:
    path = find_glb(GLB_PATH)
    print("読み込み:", path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    if not OUT_DIR:
        OUT_DIR = os.path.dirname(os.path.abspath(path))
elif not OUT_DIR:
    OUT_DIR = bpy.path.abspath("//") or os.getcwd()

scene = bpy.context.scene
root_col = scene.collection
O = bpy.data.objects

# インポートで付くルート Empty の変換は単位のはずだが、念のため確認
root_empty = O.get("zashikiro_chika")
if root_empty is not None:
    # ルートを外して子を直接シーン直下へ(ワールド変換は保持)
    for ch in list(root_empty.children):
        mw = ch.matrix_world.copy()
        ch.parent = None
        ch.matrix_world = mw
    bpy.data.objects.remove(root_empty)

# ---------------------------------------------------------------- コレクション
top = get_or_create_collection("座敷牢", root_col)
C = {
    "N": get_or_create_collection("壁_北(奥)", top),
    "S": get_or_create_collection("壁_南(手前)", top),
    "E": get_or_create_collection("壁_東(階段側)", top),
    "W": get_or_create_collection("壁_西", top),
    "floor": get_or_create_collection("床", top),
    "ceil": get_or_create_collection("天井", top),
    "stairs": get_or_create_collection("階段", top),
    "lattice": get_or_create_collection("格子(牢の枠)", top),
    "props": get_or_create_collection("家具・小物", top),
    "door": get_or_create_collection("扉", top),
}

# ---------------------------------------------------------------- 壁の位置を求める
ew = O["earth_walls"]
mw = ew.matrix_world
xs = [(mw @ v.co).x for v in ew.data.vertices]
ys = [(mw @ v.co).y for v in ew.data.vertices]


def median(a):
    a = sorted(a)
    return a[len(a) // 2]


xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
LINE = {
    "W": median([x for x in xs if x < xmin + 0.4]),
    "E": median([x for x in xs if x > xmax - 0.4]),
    "S": median([y for y in ys if y < ymin + 0.4]),
    "N": median([y for y in ys if y > ymax - 0.4]),
}
print("壁の位置:", {k: round(v, 2) for k, v in LINE.items()})


def nearest_wall(p, max_dist=None):
    d = {
        "W": abs(p.x - LINE["W"]),
        "E": abs(p.x - LINE["E"]),
        "S": abs(p.y - LINE["S"]),
        "N": abs(p.y - LINE["N"]),
    }
    k = min(d, key=d.get)
    if max_dist is not None and d[k] > max_dist:
        return None
    return k


# ---------------------------------------------------------------- 壁を4枚に分割
parts = split_object(ew, lambda f: nearest_wall(world_bbox_center(f, ew.matrix_world)),
                     name_fmt="壁_{label}")
NAME = {"N": "北", "S": "南", "E": "東", "W": "西"}
for k, ob in parts.items():
    ob.name = ob.data.name = "壁_" + NAME[k]
    move_to(ob, C[k])
bpy.data.objects.remove(ew)

# ---------------------------------------------------------------- 床 / 天井 / 階段
for n, key in (("rock_floor", "floor"), ("ceiling", "ceil"), ("stairs", "stairs")):
    if n in O:
        ob = O[n]
        ob.name = {"floor": "床", "ceil": "天井", "stairs": "階段"}[key]
        move_to(ob, C[key])

# ---------------------------------------------------------------- 梁・柱 (timbers)
if "timbers" in O:
    t = O["timbers"]

    def timber_label(f):
        c = world_bbox_center(f, t.matrix_world)
        if c.z > 2.5:                       # 水平材 = 天井の梁
            return "ceil"
        return nearest_wall(c, 0.6) or "post"   # 縦の柱 → 一番近い壁 / 壁から離れた柱

    sp = split_object(t, timber_label, name_fmt="柱梁_{label}")
    for k, ob in sp.items():
        if k == "ceil":
            ob.name = ob.data.name = "梁(天井)"
            move_to(ob, C["ceil"])
        elif k == "post":
            ob.name = ob.data.name = "柱(室内)"
            move_to(ob, C["props"])
        else:
            ob.name = ob.data.name = "柱_" + NAME[k]
            move_to(ob, C[k])
    bpy.data.objects.remove(t)

# ---------------------------------------------------------------- 鎖 (chains): 壁際のものは壁グループへ
if "chains" in O:
    ch = O["chains"]
    bm = bmesh.new()
    bm.from_mesh(ch.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    isl = islands(bm)
    key_of = {}
    for fs in isl:
        vs = {v for f in fs for v in f.verts}
        c = sum((v.co for v in vs), Vector()) / len(vs)
        lab = nearest_wall(ch.matrix_world @ c, 0.35) or "chain"
        for f in fs:
            key_of[tuple(sorted(v.index for v in f.verts))] = lab
    bm.free()
    sp = split_object(ch, lambda f: key_of.get(tuple(sorted(v.index for v in f.verts)), "chain"),
                      name_fmt="鎖_{label}", weld=1e-5)
    for k, ob in sp.items():
        if k == "chain":
            ob.name = ob.data.name = "鎖"
            move_to(ob, C["props"])
        else:
            ob.name = ob.data.name = "鎖_" + NAME[k]
            move_to(ob, C[k])
    bpy.data.objects.remove(ch)

# ---------------------------------------------------------------- 机・新聞紙
for n, nm in (("desk", "机とランプ"), ("newspaper", "新聞紙")):
    if n in O:
        O[n].name = nm
        move_to(O[nm], C["props"])

# ---------------------------------------------------------------- 格子 → 枠(正面/東側/西側/上の桟/奥) + 扉
lat = O["lattice"]
mw = lat.matrix_world
bm = bmesh.new()
bm.from_mesh(lat.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)


def is_nameplate(f):
    c = f.calc_center_median()
    return c.y < -0.085 and c.z > 1.9      # 扉の上に付いている札。枠側に残す


# 扉の左右端で、牢全幅の横桟を切断する(扉が開いても桟が邪魔しないように)
for px in (DOOR_X0, DOOR_X1):
    geom = [e for e in bm.edges if not any(is_nameplate(f) for f in e.link_faces)]
    geom += [f for f in bm.faces if not is_nameplate(f)]
    geom += [v for v in bm.verts if any(not is_nameplate(f) for f in v.link_faces)]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(px, 0, 0), plane_no=(1, 0, 0))
# 切り口を閉じる
bm.edges.ensure_lookup_table()
bnd = [e for e in bm.edges if e.is_boundary]
if bnd:
    bmesh.ops.holes_fill(bm, edges=bnd, sides=4)
bm.faces.ensure_lookup_table()


def lattice_label(f):
    c = f.calc_center_median()
    if is_nameplate(f):
        return "front"
    if DOOR_X0 - 1e-4 <= c.x <= DOOR_X1 + 1e-4 and DOOR_Y0 <= c.y <= DOOR_Y1:
        return "door"
    if c.y < 0.2:
        return "front"
    if c.x > 0.7:
        return "east"
    if c.x < -2.5:
        return "west"
    if c.y > 3.2:
        return "back"
    return "top"


# bm を一旦メッシュへ戻し、分割
bm.to_mesh(lat.data)
bm.free()
LAT_NAME = {"front": "格子_正面", "east": "格子_東側", "west": "格子_西側",
            "back": "格子_奥", "top": "格子_上の桟", "door": "扉"}
sp = split_object(lat, lattice_label, name_fmt="{label}")
for k, ob in sp.items():
    ob.name = ob.data.name = LAT_NAME[k]
    move_to(ob, C["door"] if k == "door" else C["lattice"])
bpy.data.objects.remove(lat)

# ---------------------------------------------------------------- 扉: ヒンジ設定 + 開閉ドライバ
door = O["扉"]
hinge = Vector((HINGE_X, HINGE_Y, 0.0))
door.data.transform(__import__("mathutils").Matrix.Translation(-hinge))   # 原点=ヒンジ(Z軸まわり)
door.location = hinge
door.rotation_mode = "XYZ"
door.lock_location = (True, True, True)
door.lock_rotation = (True, True, True)   # 角度は下のスライダー(ドライバ)で操作
door.lock_scale = (True, True, True)

ctrl = bpy.data.objects.new("扉コントロール", None)
ctrl.empty_display_type = "ARROWS"
ctrl.empty_display_size = 0.25
ctrl.location = (HINGE_X - 0.5, -0.45, 1.1)
C["door"].objects.link(ctrl)
ctrl["扉の開き"] = 0.0
ctrl.id_properties_ui("扉の開き").update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                                       description="0=閉 1=全開")
ctrl["開き角度(度)"] = DOOR_OPEN_DEG
ctrl.id_properties_ui("開き角度(度)").update(min=0.0, max=170.0, description="全開時の角度")

fc = door.driver_add("rotation_euler", 2)
d = fc.driver
d.type = "SCRIPTED"
v1 = d.variables.new(); v1.name = "t"; v1.type = "SINGLE_PROP"
v1.targets[0].id = ctrl; v1.targets[0].data_path = '["扉の開き"]'
v2 = d.variables.new(); v2.name = "a"; v2.type = "SINGLE_PROP"
v2.targets[0].id = ctrl; v2.targets[0].data_path = '["開き角度(度)"]'
d.expression = "t * radians(a)"     # +Z回転 = 手前(-Y)へ開く

# アニメーション確認用: フレーム1=閉, 24=全開 のキーを制御プロパティに打つ(不要なら削除可)
scene.frame_start, scene.frame_end = 1, 48
ctrl["扉の開き"] = 0.0
ctrl.keyframe_insert('["扉の開き"]', frame=1)
ctrl["扉の開き"] = 1.0
ctrl.keyframe_insert('["扉の開き"]', frame=24)
ctrl["扉の開き"] = 0.0
ctrl.keyframe_insert('["扉の開き"]', frame=48)
scene.frame_set(1)

# ---------------------------------------------------------------- 空のコレクションは消す / 並び順
for c in list(top.children):
    if not c.objects and not c.children:
        bpy.data.collections.remove(c)

# ---------------------------------------------------------------- 保存・書き出し
os.makedirs(OUT_DIR, exist_ok=True)
blend = os.path.join(OUT_DIR, "座敷牢_整理済み.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
print("保存:", blend)

# glTF: コレクションをノード階層として出す。扉は原点=ヒンジなのでそのまま回せる。
glb = os.path.join(OUT_DIR, "座敷牢_整理済み.glb")
kw = dict(filepath=glb, export_format="GLB", export_apply=False)
try:
    bpy.ops.export_scene.gltf(export_hierarchy_full_collections=True, **kw)
except TypeError:
    bpy.ops.export_scene.gltf(**kw)
print("書き出し:", glb)

print("\n=== コレクション内訳 ===")
def dump(c, depth=0):
    print("  " * depth + c.name, "(%d)" % len(c.objects))
    for o in c.objects:
        print("  " * (depth + 1) + "-", o.name)
    for ch in c.children:
        dump(ch, depth + 1)
dump(top)
