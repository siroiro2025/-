"""指定できるマネキン（人物）生成

使い方:
    from mannequin import Person, build_person
    p = Person(gender="female", outfit="long_coat", outfit_color="beige",
               bottom="skirt", hair="long", scarf="red", mask=True)
    build_person(p, coll, loc=(0, 3, 0), facing=180)

- 正面はローカル -Y 向き。facing は度数（0=カメラ(-Y)向き, 180=奥(+Y)向き, 90=+X向き）
- 足元が原点。1 人 = 1 オブジェクト。色は共有マテリアルなので .glb が軽い
"""
import math
import random
from dataclasses import dataclass, field, asdict
from typing import Optional

from sbuild import MeshBuilder, color_mat, mat

# 名前で指定できる色 (sRGB)
PALETTE = {
    "black": "#1b1b1e", "charcoal": "#33343a", "gray": "#6d6e73", "lightgray": "#a9aaae",
    "navy": "#1f2840", "blue": "#33507e", "beige": "#c9b393", "cream": "#e4dccb",
    "white": "#ecebe7", "camel": "#a8804f", "brown": "#5a3f2c", "darkbrown": "#3a2a20",
    "olive": "#545a3a", "khaki": "#8c835f", "pink": "#d9a7b0", "dustypink": "#b98b8f",
    "red": "#a5262b", "wine": "#5e1f2a", "green": "#2f4a37", "mustard": "#b48a2c",
    "denim": "#3d4f6b",
    # 晴れ着用
    "kimono_red": "#b3202c", "kimono_pink": "#d98ca0", "kimono_blue": "#3a5f9a",
    "kimono_purple": "#6b3f7a", "kimono_green": "#3c6e57", "gold": "#c9a33b",
}
SKIN = {"light": "#e8c4a6", "medium": "#d4a685", "tan": "#b98a66"}
HAIR = {"black": "#141212", "darkbrown": "#2e2019", "brown": "#5b3d2a", "gray": "#8a8783", "blonde": "#b89a64"}

OUTFITS = ("down", "long_coat", "short_coat", "kimono")
BOTTOMS = ("pants", "skirt")
HAIRSTYLES = ("short", "long", "bob", "bun", "bald")


def _c(name_or_hex, table=PALETTE):
    if name_or_hex is None:
        return None
    if name_or_hex.startswith("#"):
        return name_or_hex
    return table.get(name_or_hex, PALETTE.get(name_or_hex, "#808080"))


@dataclass
class Person:
    gender: str = "female"              # "male" / "female"
    height: Optional[float] = None      # m。None なら性別の標準±ばらつき
    outfit: str = "down"                # down(ダウン) / long_coat / short_coat / kimono(晴れ着)
    outfit_color: str = "black"
    bottom: str = "pants"               # pants / skirt (kimono のときは無視)
    bottom_color: str = "charcoal"
    shoes_color: str = "black"
    skin: str = "light"
    hair: str = "short"                 # short / long / bob / bun / bald
    hair_color: str = "black"
    scarf: Optional[str] = None         # 色名 or None
    hat: Optional[str] = None           # ニット帽の色 or None
    mask: bool = False                  # 白マスク
    bag: Optional[str] = None           # "shoulder" / "backpack" / None
    bag_color: str = "brown"
    obi_color: str = "gold"             # kimono の帯
    pose: str = "stand"                 # stand / walk
    name: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def build_person(p: Person, coll, loc=(0, 0, 0), facing=0.0, rng=None):
    rng = rng or random.Random()
    male = p.gender == "male"
    H = p.height or (rng.gauss(1.72, 0.05) if male else rng.gauss(1.59, 0.05))

    skin = color_mat(_c(p.skin, SKIN), 0.6, "skin")
    top = color_mat(_c(p.outfit_color), 0.85 if p.outfit != "down" else 0.45, "cloth")
    bot = color_mat(_c(p.bottom_color), 0.85, "cloth")
    shoe = color_mat(_c(p.shoes_color), 0.5, "shoe")
    hair = color_mat(_c(p.hair_color, HAIR), 0.55, "hair")

    b = MeshBuilder(p.name or f"Person_{p.gender}")

    # ---- 寸法
    sh_w = 0.215 if male else 0.185          # 肩の半幅
    hip_w = 0.17 if male else 0.18
    leg_x = 0.095 if male else 0.085
    z_hip = 0.50 * H
    z_sh = 0.815 * H
    z_head = H - 0.115 * (H / 1.7)
    head_r = 0.112 * (H / 1.7)
    depth = 0.62                              # 体の前後方向のつぶれ
    stride = 0.18 if p.pose == "walk" else 0.0
    swing = math.radians(rng.uniform(12, 20)) if p.pose == "walk" else 0.0

    # ---- 足・脚
    leg_len = z_hip - 0.07
    for side, ph in ((-1, 1), (1, -1)):
        x = side * leg_x
        a = ph * swing
        foot_y = -math.sin(a) * leg_len
        b.box(shoe, (0.11, 0.27, 0.085), (x, foot_y - 0.04, 0.045))
        top_p = (x, 0, z_hip)
        bot_p = (x, foot_y, 0.08)
        leg_m = bot if (p.bottom == "pants" and p.outfit != "kimono") else (
            color_mat("#2a2626", 0.6, "tights") if p.outfit != "kimono" else color_mat("#ecebe7", 0.7, "tabi"))
        if p.outfit == "kimono":
            # 着物は裾から足袋だけ見せる
            b.cyl_between(leg_m, bot_p, (x * 0.8, foot_y * 0.5, 0.4), 0.045, 0.05, seg=10)
        else:
            b.cyl_between(leg_m, bot_p, top_p, 0.058 if not male else 0.065, 0.085 if not male else 0.09, seg=10)

    # ---- 胴体 / 服
    hem = {"down": z_hip - 0.04 if male else z_hip - 0.10, "short_coat": z_hip - 0.08,
           "long_coat": 0.30 * H, "kimono": 0.06}[p.outfit]
    body_top = z_sh - 0.02
    r_top = sh_w - 0.02
    r_bot = {"down": hip_w + 0.035, "short_coat": hip_w + 0.02, "long_coat": hip_w + 0.06,
             "kimono": hip_w + 0.03}[p.outfit]
    if p.outfit == "kimono":
        r_top = sh_w - 0.03
    h = body_top - hem
    b.cyl(top, r_bot, r_top, h, (0, 0, hem + h / 2), seg=18, scale=(1, depth, 1))
    # 肩の丸み
    b.sphere(top, sh_w, (0, 0, z_sh - 0.04), scale=(1, depth * 0.95, 0.38), seg=18, rings=8)

    if p.outfit == "down":
        # ダウンのふくらみ（横縞）
        n = 4
        for i in range(n):
            t = (i + 0.5) / n
            z = hem + h * t * 0.92
            r = r_bot + (r_top - r_bot) * t
            b.torus(top, r * 0.98, 0.028, (0, 0, z), scale=(1, depth * 1.02, 1), seg=20, cseg=6)
        b.torus(top, 0.085, 0.04, (0, 0, z_sh + 0.01), seg=16, cseg=6)  # 襟
    elif p.outfit == "kimono":
        obi = color_mat(_c(p.obi_color), 0.5, "obi")
        b.cyl(obi, hip_w + 0.05, hip_w + 0.045, 0.2, (0, 0, z_hip + 0.17), seg=18, scale=(1, depth + 0.02, 1))
        b.box(obi, (0.2, 0.09, 0.14), (0, (hip_w + 0.03) * depth + 0.03, z_hip + 0.2))   # 背中の結び
        b.cyl(color_mat("#f2efe6", 0.6, "collar"), 0.075, 0.07, 0.06, (0, 0, z_sh + 0.01), seg=12)
        b.cyl(top, r_bot + 0.015, r_bot + 0.02, 0.06, (0, 0, 0.09), seg=18, scale=(1, depth, 1))  # 裾
    else:
        if p.outfit == "long_coat":
            b.box(top, (0.03, 0.02, h * 0.9), (0, -(r_bot * depth) + 0.01, hem + h * 0.45))  # 前合わせ
        if p.bottom == "skirt":
            sk = 0.30 * H
            b.cyl(bot, hip_w + 0.05, hip_w - 0.01, max(0.05, hem - sk + 0.04),
                  (0, 0, sk + (hem - sk + 0.04) / 2), seg=18, scale=(1, depth, 1))

    # ---- 腕
    arm_len = 0.33 * H
    for side, ph in ((-1, -1), (1, 1)):
        a = ph * swing * 0.8
        sp = (side * (sh_w + 0.005), 0, z_sh - 0.05)
        out = 0.06
        ep = (side * (sh_w + out), -math.sin(a) * arm_len, z_sh - 0.05 - math.cos(a) * arm_len)
        if p.outfit == "kimono":
            b.cyl_between(top, sp, ep, 0.07, 0.075, seg=10)
            # 振袖のたもと
            b.box(top, (0.06, 0.16, 0.42 if not male else 0.22),
                  (side * (sh_w + out + 0.01), ep[1] + 0.04, ep[2] + (0.05 if not male else 0.12)))
        else:
            thick = 0.068 if p.outfit == "down" else 0.058
            b.cyl_between(top, sp, ep, thick, thick * 0.85, seg=10)
        b.sphere(skin, 0.042, (ep[0], ep[1], ep[2] - 0.05), scale=(0.8, 0.9, 1.15), seg=10, rings=6)

    # ---- 首・頭
    b.cyl(skin, 0.048, 0.048, 0.12, (0, 0, z_sh + 0.04), seg=10)
    b.sphere(skin, head_r, (0, 0, z_head), scale=(0.88, 0.95, 1.12), seg=18, rings=12)
    hs = p.hair
    if hs != "bald":
        b.sphere(hair, head_r * 1.06, (0, 0.018, z_head + 0.02), scale=(0.9, 0.95, 1.06), seg=18, rings=10)
        if hs == "long":
            b.sphere(hair, 0.11, (0, 0.06, z_head - 0.15), scale=(1.25, 0.6, 1.9), seg=14, rings=8)
        elif hs == "bob":
            b.sphere(hair, head_r * 1.12, (0, 0.05, z_head - 0.035), scale=(1.0, 0.8, 0.85), seg=16, rings=8)
        elif hs == "bun":
            b.sphere(hair, 0.05, (0, 0.08, z_head + 0.09), seg=12, rings=8)
    if p.hat:
        knit = color_mat(_c(p.hat), 0.9, "knit")
        b.sphere(knit, head_r * 1.08, (0, 0.012, z_head + 0.055), scale=(0.92, 0.98, 0.62), seg=16, rings=8)
        b.torus(knit, head_r * 0.9, 0.018, (0, 0.012, z_head + 0.03), scale=(1.0, 1.06, 1), seg=18, cseg=6)
    if p.mask:
        b.box(color_mat("#f4f4f2", 0.8, "mask"), (0.13, 0.03, 0.08),
              (0, -head_r * 0.93, z_head - 0.045))
    if p.scarf:
        b.torus(color_mat(_c(p.scarf), 0.9, "scarf"), 0.085, 0.045, (0, 0, z_sh + 0.03),
                scale=(1, 0.9, 1), seg=16, cseg=8)

    # ---- かばん
    bm_ = color_mat(_c(p.bag_color), 0.6, "bag")
    if p.bag == "backpack":
        b.box(bm_, (0.28, 0.14, 0.38), (0, (r_top * depth) + 0.08, z_sh - 0.25))
    elif p.bag == "shoulder":
        b.box(bm_, (0.06, 0.2, 0.18), (-(hip_w + 0.06), 0, z_hip + 0.03))
        b.cyl_between(bm_, (-(hip_w + 0.06), 0, z_hip + 0.1), (sh_w * 0.5, -r_top * depth, z_sh - 0.02), 0.012, seg=6)

    return b.build(coll, loc=loc, rot=(0, 0, math.radians(facing)), sharp_angle=50)


# ---------------------------------------------------------------- ランダム生成
WINTER_COATS = ["black", "black", "black", "navy", "charcoal", "charcoal", "gray", "beige", "cream",
                "camel", "brown", "olive", "khaki", "pink", "dustypink", "white", "wine", "green", "denim"]
BOTTOM_COLORS = ["black", "black", "charcoal", "navy", "denim", "denim", "gray", "beige", "brown"]
KIMONO_COLORS = ["kimono_red", "kimono_pink", "kimono_blue", "kimono_purple", "kimono_green"]


def random_person(rng, female_ratio=0.55, kimono_ratio=0.05, **override):
    female = rng.random() < female_ratio
    g = "female" if female else "male"
    if female and rng.random() < kimono_ratio * 2:
        p = Person(gender=g, outfit="kimono", outfit_color=rng.choice(KIMONO_COLORS),
                   obi_color=rng.choice(["gold", "cream", "red"]), hair="bun",
                   hair_color=rng.choice(["black", "darkbrown"]),
                   scarf=rng.choice([None, "white", "cream"]), shoes_color="#3a2a20")
    else:
        outfit = rng.choices(["down", "long_coat", "short_coat"], [0.5, 0.3, 0.2] if female else [0.55, 0.2, 0.25])[0]
        p = Person(
            gender=g, outfit=outfit, outfit_color=rng.choice(WINTER_COATS),
            bottom=("skirt" if female and outfit != "down" and rng.random() < 0.3 else "pants"),
            bottom_color=rng.choice(BOTTOM_COLORS),
            shoes_color=rng.choice(["black", "black", "brown", "white", "gray"]),
            hair=(rng.choice(["long", "long", "bob", "bun", "short"]) if female else
                  rng.choice(["short", "short", "short", "bald"])),
            hair_color=rng.choice(["black", "black", "darkbrown", "brown"] + ([] if female else ["gray"])),
            scarf=rng.choice([None, None, "red", "gray", "beige", "wine", "navy", "cream"]),
            hat=rng.choice([None] * 6 + ["black", "gray", "cream", "navy"]),
            mask=rng.random() < 0.25,
            bag=rng.choices([None, "shoulder", "backpack"], [0.5, 0.3 if female else 0.15, 0.2])[0],
            bag_color=rng.choice(["black", "brown", "camel", "gray"]),
        )
    p.pose = rng.choice(["stand", "walk", "walk"])
    for k, v in override.items():
        setattr(p, k, v)
    return p
