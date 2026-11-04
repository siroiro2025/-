"""マネキンの見本を横一列に並べて撮影 + 1 体ずつ .glb にも書き出す

    blender-py blender/scenes/mannequin_lineup.py
出力: blender/output/mannequin_lineup.png, blender/output/mannequins.glb
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import bpy  # noqa: E402
from sbuild import MeshBuilder, mat, collection  # noqa: E402
from mannequin import Person, build_person  # noqa: E402

OUT = os.path.join(HERE, "..", "output")
SAMPLES = [
    Person(name="M_down_black", gender="male", outfit="down", outfit_color="black", bottom_color="denim"),
    Person(name="M_coat_camel", gender="male", outfit="short_coat", outfit_color="camel", bottom_color="black",
           scarf="navy", hat="gray"),
    Person(name="M_longcoat_char", gender="male", outfit="long_coat", outfit_color="charcoal", bag="backpack",
           hair="short", hair_color="gray"),
    Person(name="M_kimono", gender="male", outfit="kimono", outfit_color="#2b2d3a", obi_color="#6b6f7a"),
    Person(name="F_kimono_red", gender="female", outfit="kimono", outfit_color="kimono_red", hair="bun",
           scarf="white"),
    Person(name="F_long_beige", gender="female", outfit="long_coat", outfit_color="beige", bottom="skirt",
           bottom_color="black", hair="long", hair_color="darkbrown", scarf="red", mask=True, bag="shoulder",
           bag_color="camel"),
    Person(name="F_down_pink", gender="female", outfit="down", outfit_color="pink", hair="bob", bag="backpack"),
    Person(name="F_short_cream", gender="female", outfit="short_coat", outfit_color="cream", bottom="skirt",
           bottom_color="wine", hair="long", hat="cream", pose="walk"),
]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(1)
    c = collection("Mannequins")
    rig = collection("Rig")
    n = len(SAMPLES)
    for i, p in enumerate(SAMPLES):
        p.height = 1.72 if p.gender == "male" else 1.6
        build_person(p, c, ((i - (n - 1) / 2) * 0.8, 0, 0), 0, rng)
    fl = MeshBuilder("Floor")
    fl.quad(mat("floor", "#c9c6c0", 0.9), [(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)])
    fl.build(rig)

    sc = bpy.context.scene
    w = bpy.data.worlds.new("W"); sc.world = w
    bgn = next(x for x in w.node_tree.nodes if x.type == "BACKGROUND")
    bgn.inputs["Color"].default_value = (0.8, 0.8, 0.82, 1); bgn.inputs["Strength"].default_value = 1.0
    sd = bpy.data.lights.new("Key", "SUN"); sd.energy = 2.5; sd.angle = math.radians(20)
    so = bpy.data.objects.new("Key", sd); so.rotation_euler = (math.radians(50), 0, math.radians(-30)); rig.objects.link(so)
    cd = bpy.data.cameras.new("Cam"); cd.lens = 50
    cam = bpy.data.objects.new("Cam", cd); cam.location = (0, -9.0, 1.3)
    cam.rotation_euler = (math.radians(87), 0, 0); rig.objects.link(cam); sc.camera = cam
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 48; sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1280, 480
    sc.view_settings.view_transform = "AgX"

    os.makedirs(OUT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in c.objects:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "mannequins.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    sc.render.filepath = os.path.join(OUT, "mannequin_lineup.png")
    bpy.ops.render.render(write_still=True)


main()
