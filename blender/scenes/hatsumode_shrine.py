"""初詣の神社シーン（参考画像: 朱の鳥居ごしに石畳の参道・紅白の屋台・拝殿）

実行:
    blender-py blender/scenes/hatsumode_shrine.py               # 本番 (1280x720)
    blender-py blender/scenes/hatsumode_shrine.py --preview     # 軽いプレビュー
    blender-py blender/scenes/hatsumode_shrine.py --crowd blender/scenes/hatsumode_crowd.json

出力 (blender/output/):
    hatsumode_shrine_bg.glb    背景のみ（人物なし）
    hatsumode_shrine_full.glb  背景＋人物
    hatsumode_shrine.blend     Blender で開いて調整する用
    hatsumode_shrine.png       レンダリング画像

座標: Z が上、参道は +Y 方向（奥が拝殿）。1 単位 = 1m。
"""
import argparse
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import bpy  # noqa: E402
from sbuild import MeshBuilder, mat, collection, solidify  # noqa: E402
from mannequin import Person, build_person, random_person  # noqa: E402
from roofs import hip_roof_fn, hip_roof_tiles, surface_tiles_y, slab_tiles, ridge  # noqa: E402
from trees import bare_tree, broadleaf_tree, sugi_tree, shrubs  # noqa: E402
from yatai import build_stall, THEMES  # noqa: E402

# ------------------------------------------------------------------ 配置の基準値
PATH_HALF = 3.0          # 参道の半幅
PATH_Y0, PATH_Y1 = -16.0, 17.7
TORII_Y, TORII_SPAN = 0.0, 3.6
STAIR_Y0, STAIR_Y1, BASE_H = 17.7, 21.7, 1.2
STALL_INNER = 4.4        # 屋台の前面 (参道側) の |x|

# ------------------------------------------------------------------ マテリアル
def M_():
    return dict(
        verm=mat("vermilion", "#c9381f", 0.5),
        verm_dark=mat("vermilion_dark", "#4a1a12", 0.5),
        black=mat("lacquer_black", "#181616", 0.45),
        stone=mat("stone", "#9b968d", 0.85),
        stone_dark=mat("stone_dark", "#74706a", 0.9),
        tile=[mat("path_tile_a", "#a7a49e", 0.8), mat("path_tile_b", "#97948f", 0.8),
              mat("path_tile_c", "#b3b0aa", 0.8)],
        grout=mat("grout", "#57544f", 0.95),
        gravel=mat("gravel", "#857e74", 1.0),
        hred=mat("haiden_red", "#9a3622", 0.55),
        wood=mat("wood", "#6e432a", 0.7),
        wood_dark=mat("wood_dark", "#2c1b13", 0.7),
        lattice=mat("lattice", "#8a5a36", 0.6),
        door=mat("doorway", "#0c0907", 0.9),
        gold=mat("gold", "#c9a14a", 0.35, metal=0.7),
        roof=mat("roof_base", "#3b3e43", 0.6),
        kawara=mat("kawara", "#6c7077", 0.4, metal=0.1),
        kawara_cap=mat("kawara_cap", "#585c62", 0.4, metal=0.1),
        noshi_line=mat("noshi_line", "#d9d6cf", 0.7),
        copper_tile=mat("copper_tile", "#6a9682", 0.5, metal=0.2),
        roof_ridge=mat("roof_ridge", "#3f4247", 0.5),
        soffit=mat("eave_soffit", "#3a2418", 0.8),
        plaster=mat("plaster", "#e7e0cf", 0.85),
        straw=mat("straw", "#c9b277", 0.9),
        paper=mat("paper", "#f7f6f2", 0.7),
        copper=mat("copper_green", "#5f8a76", 0.6),
        stall_wood=mat("stall_wood", "#7b5636", 0.75),
        stall_top=mat("stall_top", "#a07a52", 0.7),
        tent_red=mat("tent_red", "#c3262c", 0.65),
        tent_white=mat("tent_white", "#efe9de", 0.7),
        canvas=mat("canvas", "#cfc8b9", 0.9),
        metal=mat("metal", "#444444", 0.4, metal=0.6),
        bulb=mat("bulb", "#ffe2a8", 0.3, emit="#ffd08a", emit_strength=25.0),
        water=mat("water", "#2a3a3e", 0.05),
        bark=mat("bark", "#4d443c", 0.95),
        leaf=[mat("evergreen", "#2f4434", 0.85), mat("evergreen2", "#3a5240", 0.85),
              mat("evergreen3", "#27392c", 0.85)],
        sugi=[mat("sugi", "#2b3d2c", 0.85), mat("sugi2", "#34482f", 0.85)],
        shrub=mat("shrub", "#3b5537", 0.9),
    )


def ground_z(x, y):
    if abs(x) <= 4.0 and STAIR_Y0 <= y < STAIR_Y1:
        k = int((y - STAIR_Y0) / ((STAIR_Y1 - STAIR_Y0) / 6))
        return (k + 1) * (BASE_H / 6)
    if y >= STAIR_Y1 and abs(x) <= 11.7:
        return BASE_H
    return 0.0


# ------------------------------------------------------------------ 地面・参道
def build_ground(c, m, rng):
    b = MeshBuilder("Ground")
    b.quad(m["gravel"], [(-80, -60, 0), (80, -60, 0), (80, 90, 0), (-80, 90, 0)])
    b.build(c)

    b = MeshBuilder("SandoPath")
    b.quad(m["grout"], [(-PATH_HALF, PATH_Y0, 0.006), (PATH_HALF, PATH_Y0, 0.006),
                        (PATH_HALF, PATH_Y1, 0.006), (-PATH_HALF, PATH_Y1, 0.006)])
    tw, td, gap = 0.6, 0.45, 0.025
    y = PATH_Y0
    row = 0
    while y < PATH_Y1 - 0.01:
        y2 = min(y + td, PATH_Y1)
        off = (tw / 2) if row % 2 else 0
        x = -PATH_HALF - off
        while x < PATH_HALF - 0.01:
            xa, xb = max(x, -PATH_HALF), min(x + tw, PATH_HALF)
            if xb - xa > 0.08:
                z = 0.018 + rng.uniform(-0.004, 0.004)
                b.quad(rng.choice(m["tile"]), [(xa + gap / 2, y + gap / 2, z), (xb - gap / 2, y + gap / 2, z),
                                               (xb - gap / 2, y2 - gap / 2, z), (xa + gap / 2, y2 - gap / 2, z)])
            x += tw
        y += td
        row += 1
    # 縁石
    for s in (-1, 1):
        b.box_z(m["stone_dark"], 0.22, PATH_Y1 - PATH_Y0, 0, 0.07, s * (PATH_HALF + 0.11), (PATH_Y0 + PATH_Y1) / 2)
    b.build(c)


# ------------------------------------------------------------------ 鳥居（明神鳥居）
def build_torii(c, m, y=TORII_Y, span=TORII_SPAN):
    b = MeshBuilder("Torii")
    for s in (-1, 1):
        x = s * span
        b.box_z(m["stone"], 1.35, 1.35, 0, 0.16, x, y)
        b.cyl(m["black"], 0.53, 0.5, 0.95, (x, y, 0.16 + 0.475), seg=28)        # 根巻
        b.cyl(m["verm"], 0.45, 0.39, 6.5, (x, y, 1.1 + 3.25), seg=28)            # 柱
    L_nuki = 2 * span + 2.8
    b.box(m["verm"], (L_nuki, 0.34, 0.5), (0, y, 6.05))                         # 貫
    b.box(m["verm"], (0.55, 0.32, 1.05), (0, y, 6.8))                           # 額束

    def beam(L, z, w, h, rise, mat_):
        n = 28
        path = []
        for i in range(n + 1):
            x = -L / 2 + L * i / n
            t = abs(x) / (L / 2)
            path.append((x, z + rise * t ** 3.2))
        b.loft_beam(mat_, path, w, h, y)
    beam(2 * span + 3.6, 7.53, 0.56, 0.42, 0.28, m["verm"])                      # 島木
    beam(2 * span + 4.8, 8.0, 0.72, 0.55, 0.62, m["verm"])                       # 笠木
    beam(2 * span + 4.9, 8.3, 0.76, 0.07, 0.64, m["verm_dark"])
    b.build(c, sharp_angle=35)


# ------------------------------------------------------------------ 石灯籠
def build_lantern(c, m, x, y, scale=1.0, name="Toro"):
    s = scale
    b = MeshBuilder(name)
    st, sd = m["stone"], m["stone_dark"]
    b.box_z(sd, 1.1 * s, 1.1 * s, 0, 0.18 * s)
    b.cyl(st, 0.46 * s, 0.4 * s, 0.24 * s, (0, 0, 0.18 * s + 0.12 * s), seg=6, smooth=False)
    b.cyl(st, 0.34 * s, 0.28 * s, 0.16 * s, (0, 0, 0.42 * s + 0.08 * s), seg=6, smooth=False)
    b.cyl(st, 0.16 * s, 0.15 * s, 0.95 * s, (0, 0, 0.58 * s + 0.475 * s), seg=12)
    b.cyl(st, 0.26 * s, 0.42 * s, 0.2 * s, (0, 0, 1.53 * s + 0.1 * s), seg=6, smooth=False)
    b.cyl(st, 0.29 * s, 0.29 * s, 0.42 * s, (0, 0, 1.73 * s + 0.21 * s), seg=6, smooth=False)  # 火袋
    for a in range(0, 360, 120):
        r = math.radians(a + 30)
        b.box(m["door"], (0.16 * s, 0.02 * s, 0.24 * s),
              (math.cos(r) * 0.255 * s, math.sin(r) * 0.255 * s, 1.95 * s), rot=(0, 0, r + math.pi / 2))
    b.cyl(st, 0.6 * s, 0.12 * s, 0.36 * s, (0, 0, 2.15 * s + 0.18 * s), seg=6, smooth=False)  # 笠
    for a in range(0, 360, 60):                                                     # 蕨手
        r = math.radians(a)
        b.ico(st, 0.07 * s, (math.cos(r) * 0.6 * s, math.sin(r) * 0.6 * s, 2.2 * s), subdiv=1)
    b.cyl(st, 0.1 * s, 0.1 * s, 0.1 * s, (0, 0, 2.56 * s), seg=10)
    b.sphere(st, 0.12 * s, (0, 0, 2.7 * s), scale=(1, 1, 1.2), seg=12, rings=8)     # 宝珠
    b.build(c, loc=(x, y, 0), sharp_angle=30)


# ------------------------------------------------------------------ 手水舎
def build_chozuya(c, m, x, y):
    b = MeshBuilder("Chozuya")
    b.box_z(m["stone_dark"], 3.4, 2.8, 0, 0.15)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box_z(m["stone"], 0.36, 0.36, 0.15, 0.25, sx * 1.25, sy * 0.95)
            b.cyl(m["wood"], 0.11, 0.1, 2.35, (sx * 1.25, sy * 0.95, 0.4 + 1.175), seg=10)
    b.box(m["wood"], (2.8, 0.18, 0.22), (0, -0.95, 2.62))
    b.box(m["wood"], (2.8, 0.18, 0.22), (0, 0.95, 2.62))
    b.box(m["wood"], (0.18, 2.1, 0.22), (-1.25, 0, 2.62))
    b.box(m["wood"], (0.18, 2.1, 0.22), (1.25, 0, 2.62))
    # 水盤
    st = m["stone"]
    b.box_z(st, 1.9, 0.9, 0.15, 0.6)
    b.quad(m["water"], [(-0.85, -0.35, 0.76), (0.85, -0.35, 0.76), (0.85, 0.35, 0.76), (-0.85, 0.35, 0.76)])
    for sx in (-1, 1):
        b.box_z(st, 0.1, 0.9, 0.75, 0.12, sx * 0.9)
    for sy in (-1, 1):
        b.box_z(st, 1.9, 0.1, 0.75, 0.12, 0, sy * 0.4)
    b.cyl_between(m["wood"], (0, 0.42, 0.95), (0, 0.05, 1.05), 0.03, seg=6)  # 竹の注ぎ口
    roof_f = hip_roof_fn(0, 0, 2.15, 1.75, 2.75, 1.35, p=1.5, corner_up=0.35, edge_up=0.12)
    rb = MeshBuilder("Chozuya_Roof")
    rb.heightfield(m["copper"], roof_f, -2.15, 2.15, -1.75, 1.75, 30, 24)
    rb._mi(m["soffit"])
    hip_roof_tiles(rb, roof_f, 0, 0, 2.15, 1.75, m["copper_tile"], m["copper_tile"], pitch=0.22, r=0.05, step=0.35, lift=0.02)
    rb.box(m["copper"], (0.9, 0.3, 0.25), (0, 0, 2.75 + 1.35 + 0.05))
    rb.sphere(m["copper"], 0.16, (0, 0, 4.35), scale=(1, 1, 1.25), seg=12, rings=8)
    ro = rb.build(c, loc=(x, y, 0))
    solidify(ro, 0.16, -1, 1)
    b.build(c, loc=(x, y, 0))


# ------------------------------------------------------------------ 拝殿
def build_haiden(c, m):
    F = 22.4                 # 正面の柱列 y
    WALL_Y = 23.0
    BACK = 34.6
    zf = BASE_H + 0.12       # 床上面
    b = MeshBuilder("Haiden")
    # 基壇と石段
    b.box_z(m["stone"], 23.4, 35.6 - STAIR_Y1, 0, BASE_H, 0, (STAIR_Y1 + 35.6) / 2)
    steps = 6
    for i in range(steps):
        ys = STAIR_Y0 + i * (STAIR_Y1 - STAIR_Y0) / steps
        b.box_z(m["stone"], 8.0, STAIR_Y1 - ys + 0.01, 0, (i + 1) * BASE_H / steps, 0, (ys + STAIR_Y1) / 2)
    for s in (-1, 1):
        b.box_z(m["stone_dark"], 0.35, STAIR_Y1 - STAIR_Y0, 0, BASE_H + 0.15, s * 4.15, (STAIR_Y0 + STAIR_Y1) / 2)
    # 床
    b.box_z(m["wood"], 21.4, BACK - F + 1.2, BASE_H, 0.12, 0, (F - 0.6 + BACK + 0.6) / 2)
    # 本体の壁
    b.box_z(m["hred"], 19.4, BACK - WALL_Y, zf, 5.0, 0, (WALL_Y + BACK) / 2)
    # 正面の柱
    xs = [-9.6 + 3.2 * i for i in range(7)]
    for x in xs:
        b.cyl(m["hred"], 0.25, 0.24, 5.4, (x, F, zf + 2.7), seg=16)
        b.cyl(m["black"], 0.3, 0.3, 0.2, (x, F, zf + 0.1), seg=16)
    # 格子戸
    for i in range(6):
        xa, xb = xs[i], xs[i + 1]
        cx_ = (xa + xb) / 2
        bw = xb - xa - 0.45
        if i in (2, 3):
            # 中央 2 間は開いた入口
            b.box(m["door"], (bw + 0.1, 0.06, 3.6), (cx_, WALL_Y - 0.03, zf + 1.8))
            continue
        b.box(m["wood_dark"], (bw, 0.06, 3.4), (cx_, WALL_Y - 0.03, zf + 0.3 + 1.7))
        nv = int(bw / 0.2)
        for k in range(nv + 1):
            b.box(m["lattice"], (0.035, 0.05, 3.4), (cx_ - bw / 2 + bw * k / nv, WALL_Y - 0.08, zf + 2.0))
        for k in range(9):
            b.box(m["lattice"], (bw, 0.05, 0.035), (cx_, WALL_Y - 0.08, zf + 0.3 + 3.4 * k / 8))
        b.box(m["hred"], (bw, 0.08, 0.3), (cx_, WALL_Y - 0.05, zf + 0.15))
    # 長押・頭貫・組物
    b.box(m["hred"], (20.4, 0.32, 0.32), (0, F, zf + 3.9))
    b.box(m["hred"], (20.4, 0.32, 0.36), (0, F, zf + 5.2))
    b.box(m["plaster"], (20.0, 0.12, 0.5), (0, F + 0.1, zf + 4.55))
    for k in range(34):
        gx = -9.9 + 19.8 * k / 33
        b.box(m["gold"], (0.22, 0.4, 0.26), (gx, F - 0.02, zf + 5.55))
        b.box(m["hred"], (0.14, 0.5, 0.18), (gx, F - 0.08, zf + 5.78))
    b.box(m["gold"], (20.6, 0.1, 0.12), (0, F - 0.2, zf + 5.38))
    # 高欄
    for x0, x1 in ((-10.5, -4.3), (4.3, 10.5)):
        L = x1 - x0
        cx_ = (x0 + x1) / 2
        b.box(m["hred"], (L, 0.12, 0.1), (cx_, F - 0.25, zf + 0.75))
        b.box(m["hred"], (L, 0.08, 0.08), (cx_, F - 0.25, zf + 0.4))
        for k in range(int(L / 1.0) + 1):
            b.box_z(m["hred"], 0.1, 0.1, zf, 0.8, x0 + L * k / int(L / 1.0), F - 0.25)
        b.box(m["gold"], (0.14, 0.14, 0.12), (x0 if x0 < 0 else x1, F - 0.25, zf + 0.86))
    # 賽銭箱
    b.box_z(m["wood"], 2.4, 0.8, zf, 0.75, 0, F + 0.4)
    b.box_z(m["wood_dark"], 2.5, 0.9, zf + 0.75, 0.06, 0, F + 0.4)
    b.box(m["gold"], (2.42, 0.02, 0.06), (0, F - 0.01, zf + 0.6))
    # 鈴緒
    b.cyl_between(m["straw"], (0, F + 0.25, zf + 1.1), (0, F + 0.25, zf + 4.8), 0.05, seg=8)
    b.sphere(m["gold"], 0.22, (0, F + 0.25, zf + 4.85), seg=14, rings=8)
    b.build(c, sharp_angle=35)

    # ---- 主屋根
    cy, A, B, z0, H = 28.8, 13.4, 8.0, 7.0, 5.9
    f = hip_roof_fn(0, cy, A, B, z0, H)
    rb = MeshBuilder("Haiden_Roof")
    rb.heightfield(m["roof"], f, -A, A, cy - B, cy + B, 90, 54)
    rb._mi(m["soffit"])
    hip_roof_tiles(rb, f, 0, cy, A, B, m["kawara"], m["kawara_cap"], pitch=0.36, r=0.09, step=0.6)
    # 大棟（熨斗瓦を積む）と鬼瓦
    zr = z0 + H
    ztop = ridge(rb, (-(A - B) - 0.3, cy), ((A - B) + 0.3, cy), 0.9, 9, m["roof_ridge"], m["noshi_line"],
                 layer_h=0.13, base_z=zr - 0.1)
    for s in (-1, 1):
        rb.box(m["roof_ridge"], (0.5, 1.1, ztop - zr + 0.9), (s * (A - B + 0.55), cy, (zr + ztop) / 2 + 0.35))
        rb.box(m["roof_ridge"], (0.3, 1.3, 0.25), (s * (A - B + 0.6), cy, ztop + 0.75), rot=(0, s * 0.5, 0))
        rb.box(m["gold"], (0.52, 0.5, 0.12), (s * (A - B + 0.55), cy - 0.3, (zr + ztop) / 2 + 0.3))
    # 隅棟
    for sx in (-1, 1):
        for sy in (-1, 1):
            pts = []
            for k in range(13):
                t = k / 12
                px = sx * ((A - B) + B * t * 0.985)
                py = cy + sy * B * t * 0.985
                pts.append((px, py, f(px, py) + 0.2))
            for p1, p2 in zip(pts, pts[1:]):
                rb.cyl_between(m["roof_ridge"], p1, p2, 0.24, seg=10)
                rb.cyl_between(m["noshi_line"], (p1[0], p1[1], p1[2] + 0.2), (p2[0], p2[1], p2[2] + 0.2), 0.12, seg=8)
    ro = rb.build(c)
    solidify(ro, 0.4, -1, 1)
    ro.modifiers["Solidify"].material_offset_rim = 1

    # ---- 千鳥破風（正面の三角屋根）
    g = MeshBuilder("Haiden_Chidori")
    yg = cy - 4.3
    ze = f(0, yg) - 0.05
    w, hh = 4.6, 3.0
    ang = math.atan2(hh, w)
    L = math.hypot(w, hh) + 0.7
    D = 4.8
    L = math.hypot(w, hh) + 0.6
    for s in (-1, 1):
        # 中心を軒側へ 0.3 ずらして、頂点で止め軒先だけ出す
        cxs = s * (w / 2 + 0.3 * math.cos(ang))
        czs = ze + hh / 2 - 0.3 * math.sin(ang)
        g.box(m["roof"], (L, D, 0.3), (cxs, yg - 0.7 + D / 2, czs + 0.12), rot=(0, s * ang, 0))
        th = s * ang
        axis = (-s * math.cos(th), 0, s * math.sin(th))   # 軒→頂点
        normal = (math.sin(th), 0, math.cos(th))
        slab_tiles(g, (cxs, yg - 0.7 + D / 2, czs + 0.12), axis, normal, L, (0, 1, 0), D,
                   m["kawara"], m["kawara_cap"], pitch=0.34, r=0.08)
        g.box(m["gold"], (L, 0.16, 0.34), (cxs, yg - 0.72, czs - 0.08), rot=(0, s * ang, 0))
    g.poly(m["plaster"], [(-w + 0.3, yg - 0.3, ze + 0.05), (w - 0.3, yg - 0.3, ze + 0.05), (0, yg - 0.3, ze + hh - 0.25)])
    for k in range(5):
        xk = -w * 0.55 + w * 1.1 * k / 4
        g.box(m["gold"], (0.08, 0.06, 1.3 * (1 - abs(xk) / w)), (xk, yg - 0.33, ze + 0.7 * (1 - abs(xk) / w) + 0.1))
    g.ico(m["gold"], 0.3, (0, yg - 0.78, ze + hh - 0.35), scale=(1.4, 0.5, 1.1), subdiv=2, smooth=True)  # 懸魚
    g.box(m["roof_ridge"], (0.5, D, 0.4), (0, yg - 0.7 + D / 2, ze + hh + 0.38))
    g.box(m["gold"], (0.7, 0.5, 0.9), (0, yg - 0.75, ze + hh + 0.6))                                  # 鬼板
    g.build(c, sharp_angle=35)

    # ---- 唐破風（正面中央の曲線屋根）
    kw, ky0, ky1, kz = 4.3, 20.3, 24.9, 6.95

    def kf(x, y):
        t = min(1.0, abs(x) / kw)
        arch = 1.35 * math.cos(t * math.pi / 2) ** 1.4 - 0.25 * t ** 6
        return kz + arch + 0.6 * (y - ky0) / (ky1 - ky0)
    kb = MeshBuilder("Haiden_Karahafu")
    kb.heightfield(m["roof"], kf, -kw, kw, ky0, ky1, 40, 12)
    kb._mi(m["soffit"])
    surface_tiles_y(kb, kf, -kw, kw, ky0, ky1, m["kawara"], m["kawara_cap"], pitch=0.32, r=0.08, step=0.45)
    ko = kb.build(c)
    solidify(ko, 0.38, -1, 1)
    kg = MeshBuilder("Haiden_Karahafu_Trim")
    path = [(-kw + 2 * kw * i / 40, kf(-kw + 2 * kw * i / 40, ky0) - 0.22) for i in range(41)]
    kg.loft_beam(m["gold"], path, 0.18, 0.34, ky0 - 0.05)
    face = [(x, ky0 + 0.6, z - 0.35) for x, z in path[4:-4]]
    face += [(path[-5][0], ky0 + 0.6, zf + 5.6), (path[4][0], ky0 + 0.6, zf + 5.6)]
    kg.poly(m["wood_dark"], face)
    kg.box(m["gold"], (1.4, 0.15, 0.5), (0, ky0 + 0.5, kz + 0.45))               # 兎の毛通し
    kg.ico(m["gold"], 0.25, (0, ky0 - 0.12, kz + 1.0), scale=(1.5, 0.4, 0.8), subdiv=2, smooth=True)
    kg.build(c)

    # ---- 注連縄と紙垂
    s_ = MeshBuilder("Shimenawa")
    zs, sag, half = zf + 4.1, 0.55, 3.0
    pts = []
    for k in range(25):
        t = -1 + 2 * k / 24
        pts.append((t * half, F - 0.32, zs - sag * (1 - t * t)))
    for k, (p1, p2) in enumerate(zip(pts, pts[1:])):
        t = abs(-1 + 2 * (k + 0.5) / 24)
        s_.cyl_between(m["straw"], p1, p2, 0.24 - 0.13 * t ** 2, seg=10)
    for k in range(7):
        t = -0.75 + 1.5 * k / 6
        x = t * half
        z = zs - sag * (1 - t * t) - 0.2
        if k % 2 == 0:
            for j in range(4):  # 紙垂（ジグザグ）
                s_.box(m["paper"], (0.1, 0.012, 0.15), (x + (0.05 if j % 2 else -0.05), F - 0.34, z - 0.08 - j * 0.15))
        else:
            s_.cyl(m["straw"], 0.05, 0.08, 0.45, (x, F - 0.32, z - 0.2), seg=8)  # 〆の子
    s_.build(c)


# ------------------------------------------------------------------ 人物配置
def place_crowd(c, rng, count, featured):
    placed = []

    def ok(x, y, d):
        return all((x - px) ** 2 + (y - py) ** 2 > d * d for px, py in placed)

    n = 0
    for spec in featured:
        pos = spec.pop("pos", None)
        facing = spec.pop("facing", 180)
        p = Person(**spec)
        x, y = pos if pos else (rng.uniform(-2.5, 2.5), rng.uniform(-2, 16))
        build_person(p, c, (x, y, ground_z(x, y) + 0.018), facing, rng)
        placed.append((x, y))
        n += 1

    tries = 0
    while n < count and tries < count * 200:
        tries += 1
        zone = rng.random()
        if zone < 0.58:          # 参道（奥ほど密）
            y = -3.5 + 21.0 * rng.random() ** 0.55
            x = rng.uniform(-2.7, 2.7)
            facing = rng.gauss(180, 18) if rng.random() < 0.8 else rng.gauss(0, 22)
            d = 0.62
        elif zone < 0.76:        # 屋台の前
            s = rng.choice((-1, 1))
            y = rng.uniform(3.0 if s < 0 else -3.5, 16.0)
            x = s * rng.uniform(3.2, 4.0)
            facing = s * 90 + rng.gauss(0, 20)
            d = 0.6
        elif zone < 0.93:        # 石段
            y = rng.uniform(STAIR_Y0 + 0.2, STAIR_Y1 - 0.2)
            x = rng.uniform(-3.6, 3.6)
            facing = rng.gauss(180, 10)
            d = 0.52
        else:                    # 拝殿前
            y = rng.uniform(STAIR_Y1 + 0.05, 22.0)
            x = rng.uniform(-3.8, 3.8)
            facing = rng.gauss(180, 8)
            d = 0.5
        if abs(x - TORII_SPAN) < 0.8 and abs(y - TORII_Y) < 0.8 or abs(x + TORII_SPAN) < 0.8 and abs(y - TORII_Y) < 0.8:
            continue
        if not ok(x, y, d):
            continue
        p = random_person(rng)
        if zone >= 0.76:
            p.pose = "stand"
        build_person(p, c, (x, y, ground_z(x, y) + 0.018), facing, rng)
        placed.append((x, y))
        n += 1
    return n


# ------------------------------------------------------------------ ライト・カメラ
def setup_world_camera(lights_c, stall_lights, args):
    sc = bpy.context.scene
    world = bpy.data.worlds.new("Overcast")
    sc.world = world
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    if args.night:
        bg.inputs["Color"].default_value = (0.02, 0.03, 0.06, 1)
        bg.inputs["Strength"].default_value = 0.6
    else:
        bg.inputs["Color"].default_value = (0.62, 0.65, 0.7, 1)
        bg.inputs["Strength"].default_value = 1.1

    sun_d = bpy.data.lights.new("Sun", "SUN")
    sun_d.energy = 0.02 if args.night else 1.2
    sun_d.angle = math.radians(35)
    sun_d.color = (0.95, 0.96, 1.0)
    sun = bpy.data.objects.new("Sun", sun_d)
    sun.rotation_euler = (math.radians(45), 0, math.radians(200))
    lights_c.objects.link(sun)

    for i, (x, y, z) in enumerate(stall_lights):
        ld = bpy.data.lights.new(f"StallLight{i}", "POINT")
        ld.energy = args.stall_light
        ld.color = (1.0, 0.78, 0.5)
        ld.shadow_soft_size = 0.4
        lo = bpy.data.objects.new(f"StallLight{i}", ld)
        lo.location = (x, y, z)
        lights_c.objects.link(lo)

    cd = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cd)
    presets = {
        # 名前: (位置, 回転(度), レンズmm)
        "main": ((-0.4, -10.0, 1.6), (98.5, 0, 0), 24),        # 鳥居ごしに拝殿
        "stalls": ((1.0, 0.6, 1.6), (90, 0, -33), 24),       # 参道から右の屋台の列
        "haiden": ((0.6, 9.0, 1.7), (99, 0, 0), 30),          # 拝殿に近づいて
    }
    loc, rot, lens = presets[args.cam]
    cd.lens = lens
    cam.location = loc
    cam.rotation_euler = tuple(math.radians(a) for a in rot)
    lights_c.objects.link(cam)
    sc.camera = cam

    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = args.samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = args.res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.render.film_transparent = False


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "output"))
    ap.add_argument("--preview", action="store_true", help="低解像度・低サンプルで確認用")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--crowd", help="指定人物の JSON (Person の項目 + pos/facing)")
    ap.add_argument("--count", type=int, default=120, help="人物の総数")
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--res", type=int, nargs=2, default=[1280, 720])
    ap.add_argument("--night", action="store_true", help="夜（屋台の明かりが主役）")
    ap.add_argument("--cam", default="main", choices=["main", "stalls", "haiden"], help="カメラ位置")
    ap.add_argument("--stall-light", type=float, default=None, help="屋台の照明の強さ (W)")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]  # blender -b -P ... -- の形にも対応
    args = ap.parse_args(argv)
    if args.preview:
        args.samples, args.res = 16, [640, 360]
    if args.stall_light is None:
        args.stall_light = 70.0 if args.night else 18.0
    os.makedirs(args.out, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(args.seed)
    m = M_()

    env = collection("Environment")
    shrine = collection("Shrine")
    stalls = collection("Stalls")
    trees = collection("Trees")
    crowd = collection("Crowd")
    rig = collection("CameraLights")

    build_ground(env, m, rng)
    build_torii(shrine, m)
    build_haiden(shrine, m)
    build_chozuya(shrine, m, -7.0, 1.6)
    build_lantern(shrine, m, -4.75, -2.2, 1.0, "Toro_Front")
    for s in (-1, 1):
        build_lantern(shrine, m, s * 6.2, 16.3, 1.05, f"Toro_Stair{'R' if s > 0 else 'L'}")
        build_lantern(shrine, m, s * 10.8, 19.0, 0.95, f"Toro_Side{'R' if s > 0 else 'L'}")

    stall_lights = []
    themes = list(THEMES)
    k = 0
    for y0 in (-4.4, -0.8, 2.8, 6.4, 10.0, 13.6):
        stall_lights += build_stall(stalls, 1, y0, themes[k % len(themes)], w=3.4, inner=STALL_INNER, rng=rng, idx=k); k += 1
    for y0 in (2.8, 6.4, 10.0, 13.6):
        stall_lights += build_stall(stalls, -1, y0, themes[k % len(themes)], w=3.4, inner=STALL_INNER, rng=rng, idx=k); k += 1
    stall_lights += build_stall(stalls, -1, -7.6, themes[k % len(themes)], w=3.4, inner=5.4, rng=rng, idx=k)

    bare = [(-10.5, 4.5, 15), (-13.5, -3.5, 13), (-15.5, 13, 16), (-9.5, 19, 12),
            (11.5, 1.0, 14), (14, 11, 15), (10.5, 20, 11), (9.5, -9, 13)]
    for i, (x, y, h) in enumerate(bare):
        bare_tree(trees, m["bark"], x, y, h, rng, f"BareTree{i}")
    i = 0
    for s in (-1, 1):
        for _ in range(4):  # 奥の裸木
            bare_tree(trees, m["bark"], s * rng.uniform(12, 24), rng.uniform(24, 40), rng.uniform(11, 15), rng,
                      f"BareTreeBack{i}", max_depth=5); i += 1
    # 拝殿の裏の森（杉と常緑広葉樹）
    for _ in range(26):
        x, y = rng.uniform(-36, 36), rng.uniform(42, 68)
        if rng.random() < 0.55:
            sugi_tree(trees, m["bark"], m["sugi"], x, y, rng.uniform(13, 20), rng, f"Sugi{i}")
        else:
            broadleaf_tree(trees, m["bark"], m["leaf"], x, y, rng.uniform(10, 15), rng, f"Broadleaf{i}", detail=2)
        i += 1
    for s in (-1, 1):
        for _ in range(4):
            sugi_tree(trees, m["bark"], m["sugi"], s * rng.uniform(19, 32), rng.uniform(10, 38),
                      rng.uniform(10, 15), rng, f"Sugi{i}"); i += 1
    # 手前を囲む常緑樹（参考画像の右奥・左奥）
    broadleaf_tree(trees, m["bark"], m["leaf"], 15.5, 5.0, 11, rng, "Broadleaf_R", detail=3)
    broadleaf_tree(trees, m["bark"], m["leaf"], -14.5, 22.0, 10, rng, "Broadleaf_L", detail=3)
    shrubs(trees, m["shrub"], [(-9.5, -1.5, 0.9), (-10, 1.5, 1.0), (-8.8, 5.5, 0.8), (-12, 8, 1.1),
                               (8.5, 18.5, 0.8), (-8.5, 18.5, 0.8), (13, 17, 1.0), (-13, 17, 1.0),
                               (8.2, -6, 0.7), (8.4, 5, 0.8), (8.4, 12, 0.8), (-8.4, 11, 0.8)], rng)

    featured = []
    if args.crowd:
        with open(args.crowd, encoding="utf-8") as fh:
            featured = json.load(fh)
    n = place_crowd(crowd, rng, args.count, featured)
    print(f"[hatsumode] people placed: {n}")

    setup_world_camera(rig, stall_lights, args)

    base = os.path.join(args.out, "hatsumode_shrine" + ("_night" if args.night else ""))
    if not args.no_export:
        def export(path, include_crowd):
            bpy.ops.object.select_all(action="DESELECT")
            for ob in bpy.context.scene.objects:
                cols = {c.name for c in ob.users_collection}
                if "CameraLights" in cols:
                    continue
                if "Crowd" in cols and not include_crowd:
                    continue
                ob.select_set(True)
            bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                                      export_apply=True, export_cameras=False, export_lights=False)
        export(base + "_bg.glb", False)
        export(base + "_full.glb", True)
        bpy.ops.wm.save_as_mainfile(filepath=base + ".blend", compress=True)

    if not args.no_render:
        suffix = ("" if args.cam == "main" else "_" + args.cam) + ("_preview" if args.preview else "")
        bpy.context.scene.render.filepath = base + suffix + ".png"
        bpy.ops.render.render(write_still=True)
    print("[hatsumode] done")


main()
