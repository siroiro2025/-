"""反りのある屋根と瓦（丸瓦の列・軒先の巴瓦・熨斗瓦の棟）"""
import math
from mathutils import Vector


def hip_roof_fn(cx, cy, A, B, z0, H, p=1.6, corner_up=0.9, edge_up=0.25):
    """寄棟屋根の高さ関数。A,B は軒の半幅 (x, y)、z0 は軒の高さ、H は棟までの高さ。"""
    def f(x, y):
        dx, dy = A - abs(x - cx), B - abs(y - cy)
        d = max(0.0, min(dx, dy))
        t = min(1.0, d / B)
        z = z0 + H * t ** p
        corner = max(0.0, 1.0 - (max(dx, 0) + max(dy, 0)) / (0.55 * B))
        z += corner_up * corner ** 2 + edge_up * (1 - t) ** 4
        return z
    return f


def _row(b, m_tile, m_cap, pts, r, cap=True, seg=8):
    """丸瓦 1 列。pts は軒先→上の順。軒先に巴瓦の円盤。"""
    for p1, p2 in zip(pts, pts[1:]):
        b.cyl_between(m_tile, p1, p2, r, seg=seg)
    if cap and len(pts) >= 2:
        p0, p1 = Vector(pts[0]), Vector(pts[1])
        d = (p0 - p1).normalized()
        b.cyl_between(m_cap, p0 - d * 0.01, p0 + d * 0.06, r * 1.35, seg=seg + 4)


def hip_roof_tiles(b, f, cx, cy, A, B, m_tile, m_cap, pitch=0.34, r=0.085, step=0.55, lift=0.05):
    """寄棟屋根の 4 面に丸瓦の列を並べる。"""
    # 正面・背面（列は x 方向に並び、y 方向に流れる）
    nx = int(2 * A / pitch)
    for sy in (-1, 1):
        for i in range(nx):
            x = cx - A + pitch * (i + 0.5)
            dmax = min(B, A - abs(x - cx)) - 0.15
            if dmax < 0.3:
                continue
            n = max(1, int(dmax / step))
            pts = []
            for k in range(n + 1):
                d = dmax * k / n
                y = cy + sy * (B - d - 0.02)
                pts.append((x, y, f(x, y) + r * 0.55 + lift))
            _row(b, m_tile, m_cap, pts, r)
    # 妻側（列は y 方向に並び、x 方向に流れる）
    ny = int(2 * B / pitch)
    for sx in (-1, 1):
        for j in range(ny):
            y = cy - B + pitch * (j + 0.5)
            dmax = B - abs(y - cy) - 0.15
            if dmax < 0.3:
                continue
            n = max(1, int(dmax / step))
            pts = []
            for k in range(n + 1):
                d = dmax * k / n
                x = cx + sx * (A - d - 0.02)
                pts.append((x, y, f(x, y) + r * 0.55 + lift))
            _row(b, m_tile, m_cap, pts, r)


def surface_tiles_y(b, fn, x0, x1, y0, y1, m_tile, m_cap, pitch=0.34, r=0.08, step=0.5, lift=0.05):
    """z=fn(x,y) の面に、y 方向へ流れる丸瓦の列（唐破風など）。軒先は y0 側。"""
    n = int((x1 - x0) / pitch)
    for i in range(n):
        x = x0 + pitch * (i + 0.5)
        m = max(1, int((y1 - y0) / step))
        pts = [(x, y0 + (y1 - y0) * k / m, fn(x, y0 + (y1 - y0) * k / m) + r * 0.55 + lift) for k in range(m + 1)]
        _row(b, m_tile, m_cap, pts, r)


def slab_tiles(b, center, axis, normal, length, depth_dir, depth, m_tile, m_cap, pitch=0.34, r=0.08, eave_at_minus=True):
    """板状の屋根（千鳥破風の片側など）の上面に丸瓦の列。
    axis: 流れ方向の単位ベクトル（軒→棟が +）。depth_dir: 列が並ぶ方向。"""
    c, a, nrm, dd = Vector(center), Vector(axis), Vector(normal), Vector(depth_dir)
    n = int(depth / pitch)
    for i in range(n):
        off = dd * (-depth / 2 + pitch * (i + 0.5)) + nrm * (r * 0.55 + 0.17)
        p_eave = c - a * (length / 2) + off
        p_top = c + a * (length / 2 - 0.15) + off
        m = max(1, int(length / 0.55))
        pts = [tuple(p_eave.lerp(p_top, k / m)) for k in range(m + 1)]
        _row(b, m_tile, m_cap, pts, r)


def ridge(b, p1, p2, width, layers, m_dark, m_line, layer_h=0.14, base_z=0.0):
    """熨斗瓦を積んだ棟（暗い層と白い目地の互い違い）。p1,p2 は x-y 上の両端、base_z はその高さ。"""
    p1, p2 = Vector(p1), Vector(p2)
    mid = (p1 + p2) / 2
    d = p2 - p1
    ang = math.atan2(d.y, d.x)
    L = d.length
    z = base_z
    for k in range(layers):
        b.box((m_dark if k % 2 == 0 else m_line), (L, width - 0.04 * k, layer_h if k % 2 == 0 else 0.03),
              (mid.x, mid.y, z + (layer_h if k % 2 == 0 else 0.03) / 2), rot=(0, 0, ang))
        z += layer_h if k % 2 == 0 else 0.03
    b.cyl_between(m_dark, (p1.x, p1.y, z + 0.1), (p2.x, p2.y, z + 0.1), width * 0.32, seg=12)  # 冠瓦
    return z + 0.2
