"""木: 冬の裸木（枝分かれ＋細い小枝）、常緑広葉樹（もこもこの葉の塊）、杉"""
import math
import random

import bpy
from mathutils import Vector

from sbuild import MeshBuilder


def _jitter(rng, v, s):
    return (v + Vector((rng.uniform(-s, s), rng.uniform(-s, s), rng.uniform(-s, s) * 0.5))).normalized()


def _lumpy(ob, strength=0.45, size=0.9, seed=0):
    """葉の塊をでこぼこにする（Displace。glb 書き出し時に適用される）"""
    tex = bpy.data.textures.new(f"{ob.name}_noise", "CLOUDS")
    tex.noise_scale = size
    tex.noise_depth = 2
    mod = ob.modifiers.new("Lumpy", "DISPLACE")
    mod.texture = tex
    mod.strength = strength
    mod.mid_level = 0.5
    mod.texture_coords = "GLOBAL"
    return mod


def bare_tree(coll, m_bark, x, y, height, rng, name, spread=1.0, max_depth=6):
    """冬の落葉樹。幹が 2〜4 本の大枝に分かれ、先は細い小枝が密に出る。"""
    b = MeshBuilder(name)
    trunk_r = height * 0.032
    # 根張り
    b.cyl(m_bark, trunk_r * 1.9, trunk_r * 1.05, height * 0.06, (0, 0, height * 0.03), seg=10, smooth=True)
    for a in range(5):
        ang = a * 2 * math.pi / 5 + rng.uniform(-0.3, 0.3)
        b.cyl_between(m_bark, (0, 0, height * 0.05),
                      (math.cos(ang) * trunk_r * 3.2, math.sin(ang) * trunk_r * 3.2, -0.05), trunk_r * 0.55, trunk_r * 0.2, seg=6)

    def grow(p, d, length, r, depth):
        segs = 4 if depth < 2 else (3 if depth < 4 else 1)
        cur = Vector(p)
        for s in range(segs):
            d = _jitter(rng, d, 0.28 if depth > 0 else 0.12)
            if depth >= 2:  # 外側の枝はやや上向きに
                d = (d + Vector((0, 0, 0.08))).normalized()
            nxt = cur + d * (length / segs)
            r_end = r * (1 - 0.3 * (s + 1) / segs)
            b.cyl_between(m_bark, cur, nxt, r * (1 - 0.3 * s / segs), r_end,
                          seg=(8 if depth == 0 else 6 if depth < 3 else 3))
            cur = nxt
            # 途中からも脇枝
            if depth < max_depth - 1 and s < segs - 1 and rng.random() < (0.45 if depth > 0 else 0.0):
                side = _jitter(rng, Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.1, 0.7))), 0.3)
                grow(cur, side, length * 0.45, r_end * 0.55, depth + 2)
        if depth >= max_depth:
            return
        if depth == 0:
            nchild = rng.randint(2, 4)
        elif depth < 3:
            nchild = 3
        else:
            nchild = rng.randint(2, 4)
        base_ang = rng.uniform(0, 2 * math.pi)
        for k in range(nchild):
            ang = base_ang + 2 * math.pi * k / nchild + rng.uniform(-0.5, 0.5)
            tilt = rng.uniform(0.35, 0.8) * spread if depth == 0 else rng.uniform(0.4, 1.0)
            nd = (d * (1.2 - tilt) + Vector((math.cos(ang), math.sin(ang), 0)) * tilt).normalized()
            k_len = rng.uniform(0.6, 0.78) if depth > 0 else rng.uniform(0.75, 0.95)
            grow(cur, nd, length * k_len, r_end * (0.62 if depth > 0 else 0.7), depth + 1)

    grow((0, 0, 0.0), Vector((0, 0, 1)), height * 0.34, trunk_r, 0)
    return b.build(coll, loc=(x, y, 0), sharp_angle=85)


def broadleaf_tree(coll, m_bark, m_leaves, x, y, height, rng, name, detail=3):
    """常緑広葉樹（クスノキ・シイなど）。幹＋大枝＋葉の塊。"""
    b = MeshBuilder(name)
    tr = height * 0.035
    top = Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), height * 0.42))
    b.cyl_between(m_bark, (0, 0, 0), top, tr * 1.3, tr * 0.8, seg=10)
    ends = []
    for k in range(rng.randint(4, 6)):
        ang = 2 * math.pi * k / 5 + rng.uniform(-0.4, 0.4)
        e = top + Vector((math.cos(ang) * height * 0.22, math.sin(ang) * height * 0.22, height * rng.uniform(0.12, 0.3)))
        b.cyl_between(m_bark, top, e, tr * 0.6, tr * 0.25, seg=6)
        ends.append(e)
    ends.append(top + Vector((0, 0, height * 0.35)))
    trunk = b.build(coll, loc=(x, y, 0))

    leaves = MeshBuilder(name + "_Leaves")
    mats = m_leaves if isinstance(m_leaves, (list, tuple)) else [m_leaves]
    for e in ends:
        for _ in range(3):
            rr = height * rng.uniform(0.13, 0.2)
            c = e + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.6))) * height * 0.08
            leaves.ico(rng.choice(mats), rr, tuple(c), scale=(1, 1, 0.8), subdiv=detail, smooth=True)
    lo = leaves.build(coll, loc=(x, y, 0))
    _lumpy(lo, strength=height * 0.05, size=height * 0.06)
    return trunk, lo


def sugi_tree(coll, m_bark, m_leaves, x, y, height, rng, name, detail=2):
    """杉。まっすぐな幹に、段々の葉の層。"""
    b = MeshBuilder(name)
    b.cyl(m_bark, height * 0.022, height * 0.008, height * 0.95, (0, 0, height * 0.475), seg=8)
    trunk = b.build(coll, loc=(x, y, 0))
    leaves = MeshBuilder(name + "_Leaves")
    mats = m_leaves if isinstance(m_leaves, (list, tuple)) else [m_leaves]
    tiers = 7
    for k in range(tiers):
        t = k / (tiers - 1)
        z = height * (0.32 + 0.6 * t)
        r = height * (0.16 * (1 - t) + 0.035)
        for _ in range(3 if t < 0.8 else 1):
            off = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * r * 0.35
            leaves.ico(rng.choice(mats), r, (off.x, off.y, z), scale=(1, 1, 0.55 + 0.3 * t), subdiv=detail, smooth=True)
    lo = leaves.build(coll, loc=(x, y, 0))
    _lumpy(lo, strength=height * 0.035, size=height * 0.04)
    return trunk, lo


def shrubs(coll, m, pts, rng, name="Shrubs"):
    b = MeshBuilder(name)
    for (x, y, r) in pts:
        for _ in range(4):
            b.ico(m, r * rng.uniform(0.55, 0.95),
                  (x + rng.uniform(-r, r), y + rng.uniform(-r, r) * 0.6, r * 0.55), scale=(1, 1, 0.7), subdiv=3, smooth=True)
    ob = b.build(coll)
    _lumpy(ob, strength=0.18, size=0.25)
    return ob
