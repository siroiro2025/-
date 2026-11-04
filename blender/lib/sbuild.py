"""共通ヘルパー: マテリアルとメッシュ組み立て (bpy 5.x / glTF 書き出し前提)

- マテリアルは Principled BSDF の色・粗さ・発光だけを使う → .glb にそのまま出る
- MeshBuilder に箱・円柱・球などを足していき、最後に 1 オブジェクトにまとめる
"""
import math
import bmesh
import bpy
from mathutils import Matrix, Vector, Euler

# ---------------------------------------------------------------- materials
_MATS = {}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def mat(name, color="#808080", rough=0.7, metal=0.0, emit=None, emit_strength=0.0):
    """名前でキャッシュされるマテリアル。color は '#RRGGBB'(sRGB)。"""
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    rgb = hex_rgb(color) if isinstance(color, str) else tuple(color)
    m.diffuse_color = (*rgb, 1.0)
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        e = hex_rgb(emit) if isinstance(emit, str) else emit
        bsdf.inputs["Emission Color"].default_value = (*e, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    _MATS[name] = m
    return m


def color_mat(color, rough=0.75, prefix="col"):
    """色指定だけのマテリアル（人物の服など）。同じ色は共有。"""
    return mat(f"{prefix}_{color.lstrip('#')}", color, rough)


# ---------------------------------------------------------------- collections
def collection(name, parent=None):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


# ---------------------------------------------------------------- mesh builder
def M(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    if not isinstance(rot, Euler):
        rot = Euler(rot)
    return Matrix.LocRotScale(Vector(loc), rot, Vector(scale))


class MeshBuilder:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []
        self.smooth_faces = set()

    def _mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _tag(self, verts, m, smooth=False):
        mi = self._mi(m)
        faces = {f for v in verts for f in v.link_faces}
        for f in faces:
            f.material_index = mi
            if smooth:
                f.smooth = True
        return faces

    # 箱: size=(x,y,z) 中心 loc
    def box(self, m, size, loc=(0, 0, 0), rot=(0, 0, 0)):
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M(loc, rot, size))
        self._tag(r["verts"], m)
        return r["verts"]

    # 底面基準の箱 (z0 から高さ h)
    def box_z(self, m, sx, sy, z0, h, x=0, y=0, rot=(0, 0, 0)):
        return self.box(m, (sx, sy, h), (x, y, z0 + h / 2), rot)

    # 円柱/円錐: 中心 loc、z 軸方向 depth
    def cyl(self, m, r1, r2, depth, loc=(0, 0, 0), rot=(0, 0, 0), seg=16, scale=(1, 1, 1), smooth=True):
        mat_ = M(loc, rot, scale)
        r = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                                  radius1=r1, radius2=r2, depth=depth, matrix=mat_)
        self._tag(r["verts"], m, smooth)
        return r["verts"]

    # 2 点間の円柱
    def cyl_between(self, m, p1, p2, r1, r2=None, seg=8, smooth=True):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        ln = d.length
        if ln < 1e-6:
            return []
        q = Vector((0, 0, 1)).rotation_difference(d.normalized())
        mat_ = Matrix.Translation((p1 + p2) / 2) @ q.to_matrix().to_4x4()
        r = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                                  radius1=r1, radius2=r2 if r2 is not None else r1,
                                  depth=ln, matrix=mat_)
        self._tag(r["verts"], m, smooth)
        return r["verts"]

    def sphere(self, m, radius, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), seg=16, rings=10):
        r = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=rings, radius=radius,
                                      matrix=M(loc, rot, scale))
        self._tag(r["verts"], m, True)
        return r["verts"]

    def ico(self, m, radius, loc=(0, 0, 0), scale=(1, 1, 1), subdiv=1, smooth=False):
        r = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=radius,
                                       matrix=M(loc, (0, 0, 0), scale))
        self._tag(r["verts"], m, smooth)
        return r["verts"]

    def torus(self, m, R, r, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), seg=20, cseg=8):
        mat_ = M(loc, rot, scale)
        verts = []
        rings = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring = []
            for j in range(cseg):
                b = 2 * math.pi * j / cseg
                p = Vector(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
                v = self.bm.verts.new(mat_ @ p)
                ring.append(v)
            rings.append(ring)
            verts += ring
        for i in range(seg):
            for j in range(cseg):
                a, b = rings[i], rings[(i + 1) % seg]
                self.bm.faces.new((a[j], b[j], b[(j + 1) % cseg], a[(j + 1) % cseg]))
        self._tag(verts, m, True)
        return verts

    def quad(self, m, pts):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self._mi(m)
        return f

    def poly(self, m, pts):
        return self.quad(m, pts)

    # 断面矩形を経路に沿って押し出し (梁・縁取りなど)。経路は x-z 平面想定、断面は (幅y, 高さz)
    def loft_beam(self, m, path, width, height, y=0.0):
        rings = []
        for p in path:
            x, z = p
            hw, hh = width / 2, height / 2
            rings.append([self.bm.verts.new((x, y - hw, z - hh)), self.bm.verts.new((x, y + hw, z - hh)),
                          self.bm.verts.new((x, y + hw, z + hh)), self.bm.verts.new((x, y - hw, z + hh))])
        mi = self._mi(m)
        for a, b in zip(rings, rings[1:]):
            for j in range(4):
                f = self.bm.faces.new((a[j], b[j], b[(j + 1) % 4], a[(j + 1) % 4]))
                f.material_index = mi
        for cap in (rings[0][::-1], rings[-1]):
            f = self.bm.faces.new(cap)
            f.material_index = mi

    # 高さ関数 z=f(x,y) の格子面 (屋根など)。厚みは solidify で付ける
    def heightfield(self, m, fn, x0, x1, y0, y1, nx, ny):
        grid = []
        for j in range(ny + 1):
            row = []
            y = y0 + (y1 - y0) * j / ny
            for i in range(nx + 1):
                x = x0 + (x1 - x0) * i / nx
                row.append(self.bm.verts.new((x, y, fn(x, y))))
            grid.append(row)
        mi = self._mi(m)
        for j in range(ny):
            for i in range(nx):
                f = self.bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
                f.material_index = mi
                f.smooth = True

    def build(self, coll, loc=(0, 0, 0), rot=(0, 0, 0), sharp_angle=40):
        me = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        try:
            me.set_sharp_from_angle(angle=math.radians(sharp_angle))
        except Exception:
            pass
        ob = bpy.data.objects.new(self.name, me)
        ob.location = loc
        ob.rotation_euler = rot
        coll.objects.link(ob)
        return ob


def solidify(ob, thickness, offset=-1.0, mat_offset=0):
    mod = ob.modifiers.new("Solidify", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.material_offset = mat_offset
    mod.use_even_offset = True
    return mod
