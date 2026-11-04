"""お祭り・初詣の屋台（テキ屋）

build_stall(coll, side, y0, theme) で参道の片側に 1 軒建てる。
ローカル座標: 正面（客側）が y=0、奥が +y、間口は x=0..w。参道に向くよう回転して置く。
"""
import math
import random

from sbuild import MeshBuilder, mat

# ------------------------------------------------------------------ 店の種類
THEMES = [
    dict(label="やきそば", kind="yakisoba", tent=("#c3262c", "#f1ece2"), band="#c3262c", band_text="#ffffff",
         sign=("#f2cf2a", "#c01b1b", "やきそば"), nobori=("#f2cf2a", "#c01b1b", "やきそば")),
    dict(label="たこ焼", kind="takoyaki", tent=("#c3262c", "#f1ece2"), band="#ffffff", band_text="#c3262c",
         sign=("#c3262c", "#ffffff", "たこ焼"), nobori=("#ffffff", "#c3262c", "たこ焼")),
    dict(label="りんご飴", kind="ringo", tent=("#d1402c", "#f6d34a"), band="#f6d34a", band_text="#c01b1b",
         sign=None, nobori=("#c3262c", "#ffffff", "りんご飴")),
    dict(label="ベビーカステラ", kind="castella", tent=("#e77a1f", "#f1ece2"), band="#f2cf2a", band_text="#c01b1b",
         sign=("#f2cf2a", "#c01b1b", "ベビーカステラ"), nobori=None),
    dict(label="甘酒", kind="amazake", tent=("#c3262c", "#f1ece2"), band="#ffffff", band_text="#222222",
         sign=("#1f3e7a", "#ffffff", "甘酒"), nobori=("#ffffff", "#c3262c", "あま酒")),
    dict(label="焼きとり", kind="yakitori", tent=("#c3262c", "#f1ece2"), band="#c3262c", band_text="#ffffff",
         sign=None, nobori=("#f2cf2a", "#c01b1b", "焼きとり")),
    dict(label="お面", kind="omen", tent=("#2f6fb3", "#f1ece2"), band="#2f6fb3", band_text="#ffffff",
         sign=None, nobori=None),
    dict(label="チョコバナナ", kind="banana", tent=("#d45c9a", "#f1ece2"), band="#5a3420", band_text="#f6d34a",
         sign=("#5a3420", "#f6d34a", "チョコバナナ"), nobori=None),
    dict(label="東京ケーキ", kind="castella", tent=("#e77a1f", "#f6d34a"), band="#f2cf2a", band_text="#c01b1b",
         sign=("#f2cf2a", "#c01b1b", "東京ケーキ"), nobori=("#f2cf2a", "#c01b1b", "東京ケーキ")),
    dict(label="わたあめ", kind="wataame", tent=("#c3262c", "#f1ece2"), band="#ffffff", band_text="#d23a7a",
         sign=None, nobori=("#ffffff", "#d23a7a", "わたあめ")),
    dict(label="じゃがバター", kind="jaga", tent=("#c3262c", "#f1ece2"), band="#f2cf2a", band_text="#3a2a10",
         sign=None, nobori=("#f2cf2a", "#c01b1b", "じゃがバター")),
    dict(label="いか焼", kind="yakitori", tent=("#c3262c", "#f1ece2"), band="#ffffff", band_text="#c3262c",
         sign=("#ffffff", "#c3262c", "いか焼"), nobori=None),
]


def _m():
    return dict(
        pipe=mat("pipe", "#8d9095", 0.35, metal=0.8),
        red_paint=mat("stall_red_paint", "#c4262a", 0.45),
        white_trim=mat("stall_white", "#f3f1ec", 0.5),
        steel=mat("stainless", "#c8cacc", 0.25, metal=0.9),
        black=mat("stall_black", "#1d1d1d", 0.4, metal=0.4),
        wood=mat("stall_wood", "#8a6440", 0.75),
        canvas=mat("canvas", "#d8d2c4", 0.9),
        vinyl=mat("vinyl", "#e9ecee", 0.25),
        tarp=mat("blue_tarp", "#2a62b5", 0.6),
        tank_blue=mat("poly_tank", "#2f6fc0", 0.4),
        gas=mat("gas_cylinder", "#b9bcc0", 0.35, metal=0.6),
        bulb=mat("bulb", "#ffe2a8", 0.3, emit="#ffcf86", emit_strength=30.0),
        tube=mat("fluor_tube", "#ffffff", 0.3, emit="#f4f7ff", emit_strength=12.0),
        cord=mat("cord", "#111111", 0.6),
        coal=mat("coal_glow", "#3a1a10", 0.8, emit="#ff5a1a", emit_strength=6.0),
        cardboard=mat("cardboard", "#b58c5a", 0.9),
        cooler=mat("cooler", "#e8eef3", 0.4),
        price=mat("price_board", "#fbfaf4", 0.6),
        price_text=mat("price_text", "#1a1a1a", 0.6),
        red_text=mat("red_text", "#c01b1b", 0.5),
    )


def _c(col, rough=0.6):
    return mat(f"yatai_{col.lstrip('#')}", col, rough)


# ------------------------------------------------------------------ 商品
def _goods(b, m, kind, w, rng, z_top, y_front=0.25, y_back=0.6):
    if kind == "yakisoba":
        b.box_z(m["black"], 1.3, 0.6, z_top, 0.05, w * 0.35, 0.45)                   # 鉄板
        b.ico(_c("#b8854a", 0.7), 0.28, (w * 0.35, 0.45, z_top + 0.05), scale=(1.6, 0.8, 0.25), subdiv=2, smooth=True)
        for k in range(3):
            b.ico(_c("#3d7a32"), 0.05, (w * 0.3 + k * 0.12, 0.4, z_top + 0.11), subdiv=1)
        for i in range(6):                                                              # パック
            for j in range(2):
                x = w * 0.62 + i * 0.16
                b.box_z(_c("#e9e2c8", 0.3), 0.14, 0.2, z_top + j * 0.045, 0.04, x, 0.22)
                b.box_z(_c("#b8854a"), 0.12, 0.17, z_top + j * 0.045 + 0.035, 0.012, x, 0.22)
    elif kind == "takoyaki":
        b.box_z(m["black"], 1.0, 0.5, z_top, 0.08, w * 0.3, 0.45)
        for i in range(8):
            for j in range(4):
                b.sphere(_c("#b5772f", 0.7), 0.025, (w * 0.3 - 0.4 + i * 0.11, 0.3 + j * 0.1, z_top + 0.09),
                         seg=8, rings=5)
        for i in range(5):                                                              # 舟皿
            x = w * 0.62 + i * 0.17
            b.box_z(_c("#e9dfc2", 0.6), 0.14, 0.2, z_top, 0.03, x, 0.22)
            for k in range(6):
                b.sphere(_c("#a8692a", 0.7), 0.022, (x - 0.035 + (k % 2) * 0.07, 0.15 + (k // 2) * 0.06, z_top + 0.05),
                         seg=8, rings=5)
    elif kind in ("ringo", "banana"):
        b.box_z(_c("#f4f4f0", 0.8), w - 0.6, 0.35, z_top, 0.12, w / 2, 0.3)          # 発泡スチロール台
        n = int((w - 0.7) / 0.1)
        for i in range(n):
            for j in range(3):
                x = 0.35 + i * 0.1 + (0.05 if j % 2 else 0)
                y = 0.18 + j * 0.11
                stick_top = z_top + 0.12 + 0.12
                b.cyl(_c("#e9dcb6"), 0.004, 0.004, 0.12, (x, y, z_top + 0.18), seg=4, smooth=False)
                if kind == "ringo":
                    col = rng.choice(["#b3121b", "#b3121b", "#c21a22", "#2f8a2f"])
                    b.sphere(mat(f"candy_{col.lstrip('#')}", col, 0.08), 0.034, (x, y, stick_top + 0.03), seg=10, rings=6)
                else:
                    b.cyl(_c("#3a2114", 0.35), 0.018, 0.015, 0.16, (x, y, stick_top + 0.08), seg=8)
                    col = rng.choice(["#f2c8d8", "#f6f1e4", "#ffd34a", "#7fc6e8"])
                    b.sphere(_c(col, 0.5), 0.019, (x, y, stick_top + 0.16), seg=8, rings=5)
    elif kind == "castella":
        b.box_z(m["steel"], 0.9, 0.5, z_top, 0.32, w * 0.3, 0.45)                    # 焼き機
        b.box_z(_c("#b88a3a", 0.3), 0.85, 0.45, z_top + 0.32, 0.03, w * 0.3, 0.45)
        b.box_z(m["steel"], 0.4, 0.4, z_top, 0.08, w * 0.62, 0.3)
        for i in range(25):
            b.sphere(_c("#d29a4a", 0.6), 0.025, (w * 0.62 - 0.15 + (i % 5) * 0.075, 0.15 + (i // 5) * 0.075,
                                                   z_top + 0.11), seg=8, rings=5)
        for i in range(6):                                                              # 紙袋
            b.box_z(_c(rng.choice(["#f3efe2", "#e9d4a8"]), 0.8), 0.14, 0.08, z_top, 0.24, w * 0.8 + (i % 3) * 0.16,
                    0.2 + (i // 3) * 0.12)
    elif kind == "amazake":
        for i in range(2):
            b.cyl(m["steel"], 0.2, 0.2, 0.36, (w * 0.3 + i * 0.5, 0.45, z_top + 0.18), seg=16)
            b.cyl(_c("#f2eee2", 0.3), 0.19, 0.19, 0.01, (w * 0.3 + i * 0.5, 0.45, z_top + 0.36), seg=16)
        for i in range(10):
            b.cyl(_c("#f7f4ec", 0.5), 0.035, 0.03, 0.08, (w * 0.65 + (i % 5) * 0.09, 0.18 + (i // 5) * 0.09,
                                                          z_top + 0.04), seg=10)
    elif kind == "yakitori":
        b.box_z(m["black"], 1.5, 0.35, z_top, 0.2, w * 0.4, 0.3)                      # 焼き台
        b.box_z(m["coal"], 1.4, 0.28, z_top + 0.2, 0.02, w * 0.4, 0.3)
        for i in range(14):
            x = w * 0.4 - 0.65 + i * 0.1
            b.cyl_between(_c("#e2cfa0"), (x, 0.13, z_top + 0.24), (x, 0.47, z_top + 0.24), 0.004, seg=4)
            for k in range(4):
                b.box(_c("#8a4a22", 0.5), (0.035, 0.04, 0.035), (x, 0.2 + k * 0.06, z_top + 0.24))
    elif kind == "jaga":
        for i in range(3):
            b.cyl(m["steel"], 0.17, 0.17, 0.4, (w * 0.25 + i * 0.42, 0.45, z_top + 0.2), seg=14)
            b.cyl(m["steel"], 0.12, 0.16, 0.08, (w * 0.25 + i * 0.42, 0.45, z_top + 0.44), seg=14)
        for i in range(8):
            b.ico(_c("#c8a060", 0.7), 0.045, (w * 0.75 + (i % 4) * 0.1, 0.2 + (i // 4) * 0.12, z_top + 0.04),
                  scale=(1.2, 1, 0.9), subdiv=1)
    elif kind == "wataame":
        b.cyl(m["steel"], 0.3, 0.3, 0.3, (w * 0.3, 0.4, z_top + 0.15), seg=18)        # わたあめ機
        b.ico(_c("#f6eef2", 0.9), 0.24, (w * 0.3, 0.4, z_top + 0.32), scale=(1, 1, 0.6), subdiv=2, smooth=True)
    elif kind == "omen":
        b.box_z(_c("#f2efe6"), w - 0.3, 0.4, z_top, 0.05, w / 2, 0.3)
        for i in range(8):
            b.box_z(_c(rng.choice(["#e94a4a", "#3d8be0", "#f5c53a", "#55b35b", "#f08ac0"]), 0.4),
                    0.18, 0.18, z_top + 0.05, 0.12, 0.35 + i * (w - 0.7) / 7, 0.3)


def _hanging(b, m, kind, w, hf, rng):
    """屋根の下に吊るす商品（わたあめ袋・お面・風船）"""
    if kind == "wataame":
        for i in range(9):
            x = 0.25 + i * (w - 0.5) / 8
            col = rng.choice(["#f7b8d0", "#9fd3f0", "#ffe27a", "#b8e3a2", "#f2f2f2"])
            b.cyl(m["cord"], 0.003, 0.003, 0.15, (x, 0.12, hf - 0.6), seg=3, smooth=False)
            b.box(_c(col, 0.15), (0.2, 0.06, 0.38), (x, 0.12, hf - 0.88))
            b.box(_c(rng.choice(["#e9374a", "#2a6ad1", "#1f1f1f"]), 0.5), (0.12, 0.062, 0.12), (x, 0.12, hf - 0.86))
    elif kind == "omen":
        # 奥の壁にお面の格子
        D = 2.4
        for i in range(8):
            for j in range(3):
                x = 0.3 + i * (w - 0.6) / 7
                z = 1.15 + j * 0.38
                col = rng.choice(["#f4f1ea", "#f7c9b0", "#f5d34a", "#7ec0ea", "#f08ac0", "#e94a4a"])
                b.sphere(_c(col, 0.3), 0.13, (x, D - 0.04, z), scale=(0.9, 0.35, 1.1), seg=12, rings=8)
                for ex in (-0.04, 0.04):
                    b.sphere(m["cord"], 0.016, (x + ex, D - 0.09, z + 0.03), seg=6, rings=4)
                b.box(_c("#c01b1b"), (0.04, 0.01, 0.012), (x, D - 0.09, z - 0.05))
        for i in range(6):  # 風船
            x = 0.3 + i * (w - 0.6) / 5
            col = rng.choice(["#e9374a", "#2a6ad1", "#f6c62a", "#3fae52", "#f07ab8"])
            b.cyl(m["cord"], 0.002, 0.002, 0.35, (x, 0.1, hf - 0.55), seg=3, smooth=False)
            b.sphere(_c(col, 0.15), 0.11, (x, 0.1, hf - 0.82), scale=(1, 1, 1.15), seg=12, rings=8)


# ------------------------------------------------------------------ 屋台本体
def build_stall(coll, side, y0, theme, w=3.4, D=2.4, inner=4.4, rng=None, idx=0):
    """side=+1 なら参道の右（x>0）、-1 なら左。y0..y0+w に建つ。
    戻り値: 照明を置く位置（ワールド座標）のリスト"""
    rng = rng or random.Random()
    m = _m()
    b = MeshBuilder(f"Yatai_{'R' if side > 0 else 'L'}{idx}_{theme['kind']}")
    hf, hb = 2.35, 2.8           # 前・奥の軒高
    yf = -0.4                     # 屋根の前の出

    # --- 地面: ブルーシート・ポリタンク・ガスボンベ・クーラー
    b.quad(m["tarp"], [(-0.1, D * 0.45, 0.012), (w + 0.1, D * 0.45, 0.012), (w + 0.1, D + 0.3, 0.012),
                       (-0.1, D + 0.3, 0.012)])
    gx = rng.choice([0.25, w - 0.25])
    b.cyl(m["gas"], 0.17, 0.17, 0.85, (gx, D + 0.15, 0.45), seg=16)
    b.sphere(m["gas"], 0.17, (gx, D + 0.15, 0.87), scale=(1, 1, 0.45), seg=16, rings=6)
    b.cyl(_c("#2a5b3a"), 0.05, 0.05, 0.1, (gx, D + 0.15, 0.98), seg=8)
    b.cyl_between(m["cord"], (gx, D + 0.15, 0.95), (w * 0.4, D - 0.4, 0.9), 0.01, seg=4)
    tx = w - 0.35 if gx < w / 2 else 0.35
    b.box_z(m["tank_blue"], 0.3, 0.24, 0.012, 0.44, tx, D * 0.62)
    b.cyl(_c("#f2c12e"), 0.04, 0.04, 0.05, (tx + 0.08, D * 0.62, 0.48), seg=8)
    b.box_z(m["cooler"], 0.55, 0.36, 0.012, 0.36, w * 0.5, D + 0.05)
    b.box_z(_c("#2f6fc0"), 0.57, 0.38, 0.37, 0.05, w * 0.5, D + 0.05)
    if rng.random() < 0.6:
        b.box_z(m["cardboard"], 0.45, 0.35, 0.012, 0.3, w * 0.75, D * 0.6)
        b.box_z(m["cardboard"], 0.4, 0.32, 0.31, 0.28, w * 0.75, D * 0.6)

    # --- パイプの骨組み
    for x in (0.04, w - 0.04):
        b.cyl(m["pipe"], 0.024, 0.024, hf, (x, 0.04, hf / 2), seg=8)
        b.cyl(m["pipe"], 0.024, 0.024, hb, (x, D - 0.04, hb / 2), seg=8)
        b.cyl_between(m["pipe"], (x, 0.04, hf), (x, D - 0.04, hb), 0.022, seg=8)
        b.cyl_between(m["pipe"], (x, 0.04, 1.0), (x, D - 0.04, 1.0), 0.02, seg=8)
    b.cyl_between(m["pipe"], (0.04, 0.04, hf), (w - 0.04, 0.04, hf), 0.022, seg=8)
    b.cyl_between(m["pipe"], (0.04, D - 0.04, hb), (w - 0.04, D - 0.04, hb), 0.022, seg=8)
    b.cyl_between(m["pipe"], (0.04, yf, hf - 0.04), (0.04, 0.04, hf), 0.02, seg=6)
    b.cyl_between(m["pipe"], (w - 0.04, yf, hf - 0.04), (w - 0.04, 0.04, hf), 0.02, seg=6)

    # --- カウンター（赤い台＋白い縁＋ステンレス天板）
    zc = 0.82
    b.box_z(m["red_paint"], w - 0.12, 0.7, 0, zc, w / 2, 0.38)
    b.box_z(m["white_trim"], w - 0.1, 0.02, zc - 0.12, 0.08, w / 2, 0.025)
    b.box_z(m["white_trim"], w - 0.1, 0.02, 0.05, 0.05, w / 2, 0.025)
    for x in (0.06, w - 0.06):
        b.box_z(m["white_trim"], 0.04, 0.72, 0, zc, x, 0.38)
    b.box_z(m["steel"], w - 0.06, 0.76, zc, 0.03, w / 2, 0.38)
    z_top = zc + 0.03
    # 値札
    for k in range(2):
        px = w * (0.3 + 0.4 * k)
        b.box(m["price"], (0.5, 0.012, 0.26), (px, 0.018, zc - 0.33))
        b.text(m["price_text"], "500円" if k == 0 else rng.choice(["600円", "400円", "800円"]),
               (px, 0.008, zc - 0.33), size=0.13, bold=0.004)
    _goods(b, m, theme["kind"], w, rng, z_top)

    # --- 奥の作業台
    b.box_z(m["wood"], w - 0.4, 0.55, 0, 0.85, w / 2, D - 0.4)
    b.box_z(m["steel"], w - 0.4, 0.55, 0.85, 0.03, w / 2, D - 0.4)
    for i in range(rng.randint(2, 4)):
        col = rng.choice(["#f4f1e6", "#d9d2bf", "#c9a86a", "#ffffff"])
        b.box_z(_c(col), rng.uniform(0.25, 0.4), 0.3, 0.88, rng.uniform(0.1, 0.35), 0.4 + i * (w - 0.8) / 3, D - 0.4)

    # --- 奥の幕と側面のビニール
    b.quad(m["canvas"], [(0, D, 0.0), (w, D, 0.0), (w, D, hb), (0, D, hb)])
    for x in (0.0, w):
        b.quad(m["vinyl"], [(x, 0.08, 1.0), (x, D, 1.0), (x, D, hb - 0.02), (x, 0.08, hf - 0.02)])

    # --- テント屋根（縞・少したわむ）
    tent_a, tent_b = _c(theme["tent"][0], 0.65), _c(theme["tent"][1], 0.7)
    ns = max(6, int(round(w / 0.42)))
    nseg = 5
    for i in range(ns):
        xa, xb = -0.08 + (w + 0.16) * i / ns, -0.08 + (w + 0.16) * (i + 1) / ns
        tm = tent_a if i % 2 == 0 else tent_b
        for k in range(nseg):
            t0, t1 = k / nseg, (k + 1) / nseg
            def P(x, t):
                y = yf + (D + 0.12 - yf) * t
                z = hf + (hb + 0.05 - hf) * t - 0.06 * math.sin(math.pi * t)
                return (x, y, z + 0.03)
            b.quad(tm, [P(xa, t0), P(xb, t0), P(xb, t1), P(xa, t1)])
    # 側面の三角
    for x in (-0.08, w + 0.08):
        b.poly(tent_a, [(x, yf, hf + 0.03), (x, D + 0.12, hb + 0.08), (x, D + 0.12, hf + 0.03)])

    # --- 正面の幕（店名入り）＋波形の裾
    band = _c(theme["band"], 0.6)
    bh = 0.42
    b.quad(band, [(-0.08, yf, hf + 0.03), (w + 0.08, yf, hf + 0.03), (w + 0.08, yf, hf - bh), (-0.08, yf, hf - bh)])
    b.text(_c(theme["band_text"], 0.5), theme["label"], (w / 2, yf - 0.006, hf - bh / 2 + 0.01),
           size=min(0.34, (w - 0.3) / max(3, len(theme["label"])) * 1.05), bold=0.012)
    nsc = int(w / 0.34)
    sw = (w + 0.16) / nsc
    for i in range(nsc):
        x0 = -0.08 + i * sw
        pts = [(x0 + sw * k / 6, yf, hf - bh - 0.1 * math.sin(math.pi * k / 6)) for k in range(7)]
        b.poly(tent_b if theme["band"].lower() != theme["tent"][1].lower() else tent_a, pts)

    # --- 屋根上の看板
    if theme.get("sign"):
        bg, fg, txt = theme["sign"]
        sh = 0.62
        tilt = math.radians(10)
        cy_, cz_ = yf + 0.1, hf + 0.12 + sh / 2
        b.box(_c(bg, 0.5), (w - 0.1, 0.05, sh), (w / 2, cy_, cz_), rot=(tilt, 0, 0))
        b.box(_c("#c01b1b" if bg != "#c3262c" else "#ffffff", 0.5), (w - 0.02, 0.055, 0.05),
              (w / 2, cy_, cz_ - sh / 2), rot=(tilt, 0, 0))
        tsize = min(0.48, (w - 0.35) / max(3, len(txt)) * 1.08)
        b.text(_c(fg, 0.5), txt, (w / 2, cy_ - 0.03 + math.sin(tilt) * 0.0, cz_ + 0.02), rot=(tilt, 0, 0),
               size=tsize, bold=0.015)
        for x in (0.3, w - 0.3):
            b.cyl_between(m["pipe"], (x, yf + 0.15, hf), (x, cy_ + 0.12, cz_ + 0.15), 0.015, seg=6)

    # --- のぼり旗
    if theme.get("nobori"):
        bg, fg, txt = theme["nobori"]
        nx = rng.choice([-0.25, w + 0.25])
        ny = yf - 0.15
        b.cyl(_c("#e8e8e8", 0.4), 0.02, 0.02, 4.4, (nx, ny, 2.2), seg=8)
        b.cyl_between(_c("#e8e8e8", 0.4), (nx, ny, 4.1), (nx + (0.5 if nx > 0 else -0.5), ny, 4.1), 0.012, seg=6)
        fx = nx + (0.27 if nx > 0 else -0.27)
        b.box(_c(bg, 0.8), (0.5, 0.01, 1.75), (fx, ny, 3.2))
        b.box(_c("#c01b1b" if bg != "#c3262c" else "#ffffff", 0.7), (0.5, 0.012, 0.12), (fx, ny, 4.05))
        n = len(txt)
        size = min(0.36, 1.45 / max(n, 3))
        b.text(_c(fg, 0.5), txt, (fx, ny - 0.008, 3.15), size=size, bold=0.012, vertical=True)
        b.text(_c(fg, 0.5), txt, (fx, ny + 0.008, 3.15), rot=(0, 0, math.pi), size=size, bold=0.012, vertical=True)

    # --- 照明（裸電球・蛍光灯）と吊り物
    lights = []
    nb = 4 if w > 3 else 3
    for i in range(nb):
        bx = 0.35 + (w - 0.7) * i / (nb - 1)
        by = 0.15
        bz = hf - 0.62
        b.cyl(m["cord"], 0.006, 0.006, 0.6, (bx, by, hf - 0.3), seg=4, smooth=False)
        b.cyl(m["black"], 0.022, 0.018, 0.05, (bx, by, bz + 0.07), seg=8)
        b.sphere(m["bulb"], 0.05, (bx, by, bz), scale=(1, 1, 1.25), seg=10, rings=6)
        if i in (1, nb - 2):
            lights.append((bx, by, bz - 0.05))
    b.cyl_between(m["tube"], (0.3, D * 0.55, (hf + hb) / 2 - 0.06), (w - 0.3, D * 0.55, (hf + hb) / 2 - 0.06), 0.018, seg=8)
    lights.append((w / 2, D * 0.55, (hf + hb) / 2 - 0.15))
    _hanging(b, m, theme["kind"], w, hf, rng)

    # --- 配置（正面を参道へ）
    if side > 0:
        loc, rot = (inner, y0 + w, 0), (0, 0, -math.pi / 2)
    else:
        loc, rot = (-inner, y0, 0), (0, 0, math.pi / 2)
    b.build(coll, loc=loc, rot=rot)
    from mathutils import Euler, Matrix, Vector
    mw = Matrix.LocRotScale(Vector(loc), Euler(rot), Vector((1, 1, 1)))
    return [tuple(mw @ Vector(p)) for p in lights]
