"""EP.18 wedge (anti-ram) barrier: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.17 (golden hour, red car, depth of
field). A secure gate: two inbound lanes, a guard booth, a fence and bollards, a building beyond. In each lane a striped steel plate
hinged over a concrete pit swings up on two hydraulic cylinders. The red CC0 sedan hits the raised face: its nose crushes
(crumple_zone's crush map with this film's stroke), glass, plastic and sparks fly, the rear lifts and drops back. A 15,000 lb box truck
hits the other lane in the truck shot. Cut-away shots open a trench beside lane A to show the pit, the hinge, the cylinders and the
foundation; in the force shot the load path glows. Everything that moves comes from wedge_motion. No text."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks import hook_gate  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.wedge_barrier import wedge_motion as wm  # noqa: E402
from benchmarks.wedge_barrier import wedge_timeline as tl  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
Y_RANGE = (-220.0, 70.0)
ROAD_HALF = 3.65
BOOTH_ISLAND = ((-5.6, 7.0, 0.08), (2.6, 6.0, 0.16))      # centre, size: starts at y = 4, clear of the cut-away cameras
BOLLARD_XS = [float(x) for x in list(np.arange(-12.5, -7.4, 1.4)) + list(np.arange(7.5, 12.6, 1.4))]


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--list", default="")
    p.add_argument("--film", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


class Deformable:
    """A mesh whose vertices follow crumple_motion's crush map (same technique as EP.03's renderer; copied because that module parses
    its own arguments on import)."""

    def __init__(self, ob, nose):
        mesh = ob.data
        if mesh.users > 1:
            ob.data = mesh = mesh.copy()
        self.ob, self.mesh = ob, mesh
        n = len(mesh.vertices)
        co = np.zeros(n * 3)
        mesh.vertices.foreach_get("co", co)
        self.local0 = co.reshape(n, 3)
        m = np.array(ob.matrix_world)
        self.m3, self.t = m[:3, :3], m[:3, 3]
        self.p0 = self.local0 @ self.m3.T + self.t
        self.minv = np.linalg.inv(self.m3)
        self.idx = np.where(self.p0[:, 1] > nose - cm.CRUSH_LENGTH - 1e-6)[0]

    def apply(self, s, nose):
        if len(self.idx) == 0:
            return
        out = self.local0.copy()
        out[self.idx] = (cm.crush_map(self.p0[self.idx], s, nose) - self.t) @ self.minv.T
        self.mesh.vertices.foreach_set("co", out.ravel())
        self.mesh.update()


def glowable(name, colour, metal=0.0, rough=0.5, glow=(1.0, 0.35, 0.05)):
    m = material(name, colour, metal=metal, rough=rough)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Emission Color"].default_value = (*glow, 1.0)
    b.inputs["Emission Strength"].default_value = 0.0
    return m


def set_glow(m, s):
    m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = s


def stripes(name):
    """Yellow and black diagonal hazard stripes in object space (no text)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.45
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0.0, math.radians(45), 0.0)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type, wave.bands_direction = "BANDS", "X"
    wave.inputs["Scale"].default_value = 1.6
    wave.inputs["Distortion"].default_value = 0.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.95, 0.65, 0.03, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return m


class Site:
    def __init__(self):
        road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
        base.asphalt_grain(road)
        paint = material("Line paint", (0.85, 0.85, 0.80), rough=0.6)
        grass = material("Grass", (0.11, 0.21, 0.045), rough=0.95)
        self.soil_m = material("Soil", (0.20, 0.13, 0.08), rough=0.95)
        self.concrete = glowable("Foundation concrete", (0.42, 0.41, 0.39), rough=0.85)
        curb = material("Curb", (0.55, 0.54, 0.50), rough=0.8)
        y0, y1 = Y_RANGE
        x0 = wm.PLATE_L + 0.12
        self.cut_hide, self.cut_show = [], []
        # road with two holes for the pits (y -0.12 .. PLATE_L + 0.12 in each lane)
        cube("Road approach", (0.0, (y0 - 0.12) / 2, -0.05), (2 * ROAD_HALF, -0.12 - y0, 0.1), road)
        cube("Road inside", (0.0, (x0 + y1) / 2, -0.05), (2 * ROAD_HALF, y1 - x0, 0.1), road)
        cube("Median curb", (0.0, (y0 + y1) / 2, 0.06), (0.3, y1 - y0, 0.14), curb)
        for xe in (-ROAD_HALF + 0.1, ROAD_HALF - 0.1):
            cube(f"Edge line {xe}", (xe, (y0 - 0.12) / 2, 0.002), (0.13, -0.12 - y0, 0.004), paint)
        for sx in (-1, 1):
            cube(f"Stop bar {sx}", (sx * 1.9, -6.0, 0.002), (3.2, 0.35, 0.004), paint)
        # ground beside the road: on the left a trench can open for the cut-away shots
        win = (-1.4, 3.2)
        whole = cube("Ground left", (-(ROAD_HALF + 20) / 2 - ROAD_HALF / 2 - 0.1, (y0 + y1) / 2, -1.25), (20.0, y1 - y0, 2.5), grass)
        self.cut_hide.append(whole)
        for name, ya, yb in (("Ground left a", y0, win[0]), ("Ground left b", win[1], y1)):
            ob = cube(name, (-ROAD_HALF - 10.1, (ya + yb) / 2, -1.25), (20.0, yb - ya, 2.5), grass)
            self.cut_show.append(ob)
        ob = cube("Ground left under", (-ROAD_HALF - 10.1, sum(win) / 2, -1.9), (20.0, win[1] - win[0], 1.2), self.soil_m)
        self.cut_show.append(ob)
        cube("Ground right", (ROAD_HALF + 10.1, (y0 + y1) / 2, -1.25), (20.0, y1 - y0, 2.5), grass)
        cube("Soil under road", (0.0, (y0 + y1) / 2, -1.85), (2 * ROAD_HALF + 0.2, y1 - y0, 1.3), self.soil_m)
        # pits and footings
        self.pit_left_wall = None
        for lane in (wm.LANE_A, wm.LANE_B):
            ya, yb = -0.12, x0
            cube(f"Pit floor {lane}", (lane, (ya + yb) / 2, -wm.PIT_DEPTH - 0.15), (wm.PLATE_W + 0.5, yb - ya + 0.3, 0.3), self.concrete)
            cube(f"Footing {lane}", (lane, (ya + yb) / 2, -wm.PIT_DEPTH - 0.6), (wm.PLATE_W + 1.4, yb - ya + 1.6, 0.6), self.concrete)
            for sy, yw in (("front", ya - 0.1), ("back", yb + 0.1)):
                cube(f"Pit wall {sy} {lane}", (lane, yw, -wm.PIT_DEPTH / 2), (wm.PLATE_W + 0.5, 0.2, wm.PIT_DEPTH), self.concrete)
            for sx in (-1, 1):
                ob = cube(f"Pit wall side {sx} {lane}", (lane + sx * (wm.PLATE_W / 2 + 0.15), (ya + yb) / 2, -wm.PIT_DEPTH / 2), (0.2, yb - ya, wm.PIT_DEPTH), self.concrete)
                if lane == wm.LANE_A and sx < 0:
                    self.pit_left_wall = ob
        self.cut_hide.append(self.pit_left_wall)
        # guard booth, bollards, fence, building, trees
        booth = material("Booth", (0.75, 0.74, 0.70), rough=0.6)
        glass = material("Booth glass", (0.10, 0.14, 0.16), metal=0.5, rough=0.1)
        cube("Booth island", BOOTH_ISLAND[0], BOOTH_ISLAND[1], curb)
        cube("Booth", (-5.6, 7.0, 1.4), (2.0, 2.6, 2.5), booth)
        cube("Booth window", (-4.58, 7.0, 1.75), (0.04, 2.0, 0.9), glass)
        cube("Booth roof", (-5.6, 7.0, 2.75), (2.6, 3.2, 0.2), booth)
        dark = material("Bollard", (0.12, 0.12, 0.13), metal=0.6, rough=0.4)
        for x in BOLLARD_XS:
            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.14, depth=1.0, location=(x, -0.7, 0.5))
            bpy.context.object.data.materials.append(dark)
        steel = material("Fence", (0.25, 0.26, 0.27), metal=0.7, rough=0.4)
        for sx in (-1, 1):
            for y in np.arange(1.5, 60.0, 2.5):
                cube(f"Fence post {sx} {y}", (sx * 12.5, float(y), 1.1), (0.08, 0.08, 2.2), steel)
            for z in (0.4, 1.2, 2.0):
                cube(f"Fence rail {sx} {z}", (sx * 12.5, 30.75, z), (0.05, 58.5, 0.05), steel)
        bld = material("Building", (0.62, 0.60, 0.56), rough=0.7)
        win_m = material("Windows", (0.08, 0.11, 0.14), metal=0.6, rough=0.15)
        cube("Building", (0.0, 52.0, 6.0), (44.0, 14.0, 12.0), bld)
        for z in (3.0, 6.5, 10.0):
            cube(f"Window band {z}", (0.0, 44.95, z), (40.0, 0.1, 1.4), win_m)
        bark = material("Bark", (0.10, 0.07, 0.05), rough=0.9)
        leaves = [material("Leaves a", (0.10, 0.17, 0.05), rough=0.85), material("Leaves b", (0.16, 0.19, 0.05), rough=0.85)]
        rng = random.Random(18)
        for k in range(50):
            x = rng.choice((-1, 1)) * rng.uniform(15, 60)
            y = rng.uniform(-200, 40)
            h = rng.uniform(5, 11)
            bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18, depth=h * 0.5, location=(x, y, h * 0.25))
            bpy.context.object.data.materials.append(bark)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=h * 0.32, location=(x, y, h * 0.62))
            ob = bpy.context.object
            ob.scale = (1.0, 1.0, 1.25)
            ob.data.materials.append(leaves[k % 2])
        hill = material("Hills", (0.10, 0.14, 0.10), rough=1.0)
        for x, y, sx in ((260, 120, 180), (230, -160, 140), (-280, 60, 200), (-240, 260, 180)):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(x, y, -10))
            ob = bpy.context.object
            ob.scale = (sx, sx * 0.8, 45)
            ob.data.materials.append(hill)

    def set_cut(self, cut):
        if not hasattr(self, "lamp"):
            bpy.ops.object.light_add(type="AREA", location=(-3.0, 0.9, 0.5))
            self.lamp = bpy.context.object
            self.lamp.data.size, self.lamp.data.color = 1.5, (1.0, 0.85, 0.7)
            self.lamp.rotation_euler = (0.0, math.radians(-70), 0.0)
            self.lamp.visible_camera = False
        self.lamp.data.energy = 220.0 if cut else 0.0
        for ob in self.cut_hide:
            ob.hide_render = cut
        for ob in self.cut_show:
            ob.hide_render = not cut


def _cyl(name, r, mat, verts=20):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=1.0, location=(0, 0, -20))
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def place_between(ob, a: Vector, b: Vector):
    d = b - a
    ob.location = (a + b) / 2
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    ob.scale = (1.0, 1.0, max(d.length, 1e-4))


class Barrier:
    def __init__(self, lane, plate_m, stripe_m, cyl_m, rod_m, hinge_m):
        self.lane = lane
        self.pivot = bpy.data.objects.new(f"Hinge {lane}", None)
        bpy.context.collection.objects.link(self.pivot)
        self.pivot.location = (lane, wm.PLATE_L, 0.0)
        plate = cube(f"Plate {lane}", (lane, wm.PLATE_L / 2, -0.04), (wm.PLATE_W, wm.PLATE_L, 0.08), plate_m)
        rib_objs = [plate]
        for k in range(4):                                     # stiffening ribs under the plate
            rib_objs.append(cube(f"Rib {lane} {k}", (lane - 1.2 + 0.8 * k, wm.PLATE_L / 2, -0.16), (0.06, wm.PLATE_L - 0.1, 0.18), plate_m))
        for ob in rib_objs:
            mw = ob.matrix_world.copy()
            ob.parent = self.pivot
            ob.matrix_world = mw
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.09, depth=wm.PLATE_W, location=(lane, wm.PLATE_L, -0.06), rotation=(0, math.pi / 2, 0))
        bpy.context.object.data.materials.append(hinge_m)
        self.skirt = cube(f"Skirt {lane}", (lane, 0.0, -0.5), (wm.PLATE_W, 0.05, 0.92), stripe_m)
        self.cyls = []
        for dx in (-1.05, 1.05):
            self.cyls.append((dx, _cyl(f"Cylinder {lane} {dx}", 0.085, cyl_m), _cyl(f"Rod {lane} {dx}", 0.045, rod_m)))
        self.anchor_y, self.anchor_z = 1.25, -wm.PIT_DEPTH + 0.05

    def set(self, t):
        phi = wm.plate_angle(t)
        self.pivot.rotation_euler = (-phi, 0.0, 0.0)
        yf, zf = wm.plate_front(t)
        self.skirt.location = (self.lane, yf + 0.03, zf - 0.46 - 0.03)
        for dx, barrel, rod in self.cyls:
            a = Vector((self.lane + dx, self.anchor_y, self.anchor_z))
            d = wm.PLATE_L - 0.45                              # attach point under the plate, 0.45 m from the front edge
            p = Vector((self.lane + dx, wm.PLATE_L - d * math.cos(phi), d * math.sin(phi) - 0.14 * math.cos(phi)))
            direction = (p - a).normalized()
            mid = a + direction * 0.6
            place_between(barrel, a, mid)
            place_between(rod, mid - direction * 0.05, p)
        return phi, zf


def box_truck():
    root = bpy.data.objects.new("Truck root", None)
    bpy.context.collection.objects.link(root)
    white = material("Truck white", (0.86, 0.86, 0.84), rough=0.4)
    grey = material("Truck box", (0.78, 0.79, 0.80), rough=0.55)
    dark = material("Truck dark", (0.06, 0.06, 0.07), rough=0.6)
    glass = material("Truck glass", (0.08, 0.10, 0.12), metal=0.5, rough=0.1)
    tyre = material("Truck tyre", (0.03, 0.03, 0.035), rough=0.8)
    cab = [cube("Truck cab", (0.0, -0.55, 1.55), (2.3, 2.1, 1.9), white), cube("Truck hood", (0.0, 0.25, 0.95), (2.2, 0.6, 0.8), white),
           cube("Truck windshield", (0.0, 0.52, 1.95), (2.0, 0.04, 0.8), glass), cube("Truck bumper", (0.0, 0.57, 0.55), (2.35, 0.12, 0.3), dark)]
    rest = [cube("Truck box", (0.0, -4.1, 2.25), (2.45, 4.6, 2.7), grey), cube("Truck chassis", (0.0, -3.0, 0.65), (1.0, 6.6, 0.25), dark)]
    wheels = []
    for wy in (0.0, -4.5, -5.6):
        for sx in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.48, depth=0.35, location=(sx * 0.98, wy, 0.48), rotation=(0, math.pi / 2, 0))
            ob = bpy.context.object
            ob.data.materials.append(tyre)
            wheels.append(ob)
    for ob in cab + rest + wheels:
        ob.parent = root
    return root, cab, wheels


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.2
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 7600.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.6, 0.7), 15.0)                    # low sun from the left behind the car: the impact side is lit
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.5, 0.02
    sun.data.color = (1.0, 0.74, 0.48)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    site = Site()
    plate_m = glowable("Plate steel", (0.30, 0.31, 0.32), metal=0.8, rough=0.45)
    cyl_m = glowable("Cylinder", (0.85, 0.60, 0.05), metal=0.4, rough=0.35)
    rod_m = glowable("Rod chrome", (0.85, 0.86, 0.88), metal=1.0, rough=0.12)
    hinge_m = glowable("Hinge", (0.20, 0.20, 0.22), metal=0.8, rough=0.4)
    barriers = [Barrier(lane, plate_m, stripes("Hazard stripes"), cyl_m, rod_m, hinge_m) for lane in (wm.LANE_A, wm.LANE_B)]
    # car: tinted red, its nose crushable
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    bpy.context.view_layer.update()
    nose = geom["nose"]
    deform = [Deformable(o, nose) for o in parts]
    truck, truck_cab, truck_wheels = box_truck()
    cab_rest = [(ob, ob.location.copy(), ob.scale.copy()) for ob in truck_cab]
    # debris
    mats = {"spark": glowable("Spark", (1.0, 0.7, 0.2), glow=(1.0, 0.55, 0.1)), "glass": material("Lamp glass", (0.85, 0.92, 0.95), rough=0.15),
            "plastic": material("Bumper plastic", (0.06, 0.06, 0.07), rough=0.6)}
    set_glow(mats["spark"], 25.0)
    pieces = [cube(f"Debris {k} {kind}", (0, 0, -30), size, mats[kind]) for k, (_, _, _, size, _, kind) in enumerate(wm.debris())]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    r_t = geom["tyre_radius"]

    def pose(obj, x, st):
        """Place a vehicle root: reference at (x, y), pitched (rear up) about its front contact pivot."""
        py, pz = st["pivot"]
        piv = Vector((x, py, pz))
        rot = Matrix.Rotation(-st["pitch"], 4, "X")
        obj.matrix_world = Matrix.Translation(piv) @ rot @ Matrix.Translation(Vector((x, st["y"], 0.0)) - piv)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, variant = sh["t"], sh["variant"]
        cut, force = bool(sh.get("cut")), bool(sh.get("force"))
        site.set_cut(cut)
        phis = [b.set(t) for b in barriers]
        car_st = wm.car_state(t)
        truck_st = wm.truck_state(t)
        info = {"variant": variant, "t": round(t, 6), "plate_deg": round(math.degrees(phis[0][0]), 3), "plate_front_z": round(phis[0][1], 4), "cut": cut}
        if variant == "car":
            root.hide_render = False
            for ob in parts:
                ob.hide_render = False
            pose(root, wm.LANE_A, car_st)
            for dm in deform:
                dm.apply(car_st["crush"], nose)
            spin = (car_st["y"] + 300.0) / r_t
            for wh in wheels.values():
                wh["node"].rotation_mode = "ZXY"
                wh["node"].rotation_euler = (-spin, 0, 0)
            truck.location = (0, 0, -60)
            info.update({"car_y": round(car_st["y"], 4), "crush": round(car_st["crush"], 4), "pitch_deg": round(math.degrees(car_st["pitch"]), 3)})
        else:
            root.location = (0, 0, -60)
            for dm in deform:
                dm.apply(0.0, nose)
            pose(truck, wm.LANE_B, truck_st)
            s = truck_st["crush"]
            for ob, loc, sc in cab_rest:                    # the cab front squashes back by the crush stroke
                if ob.name in ("Truck bumper", "Truck hood", "Truck windshield"):
                    ob.location = (loc.x, loc.y - s, loc.z)
                else:
                    k = max(0.55, 1 - s / 2.1)
                    ob.scale = (sc.x, sc.y * k, sc.z)
                    ob.location = (loc.x, loc.y - (1 - k) * 2.1 / 2 * 0.0 - s / 2, loc.z)
            for w in truck_wheels:
                w.rotation_euler = ((truck_st["y"] + 300.0) / 0.48, math.pi / 2, 0)
            info.update({"truck_y": round(truck_st["y"], 4), "crush": round(s, 4), "pitch_deg": round(math.degrees(truck_st["pitch"]), 3)})
        air = 0
        for k, ob in enumerate(pieces):
            p = wm.debris_pose(k, t) if variant == "car" else None
            if p is None:
                ob.hide_render = True
                continue
            ob.hide_render = False
            ob.location = tuple(p[0])
            ob.rotation_euler = tuple(p[1])
            air += p[2]
        info["airborne"] = air
        f = wm.impact_force(t, variant == "truck")
        glow = 6.0 if (force and f > 0) else (2.0 * math.exp(-(t - 0.064) / 0.05) if (force and t > 0.064) else 0.0)
        for m in (plate_m, cyl_m, rod_m, hinge_m):
            set_glow(m, glow)
        set_glow(site.concrete, 0.35 * glow)
        info["force_kN"] = round(f / 1000, 1)
        info["glow"] = round(glow, 3)
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        if variant == "car":
            info["subject_box"] = hook_gate.project_box(scene, cam, root.matrix_world, (-0.85, -wm.TAIL, 0.0), (0.85, wm.NOSE, 1.45))
        else:
            info["subject_box"] = hook_gate.project_box(scene, cam, truck.matrix_world, (-1.25, -wm.TRUCK_TAIL, 0.0), (1.25, wm.TRUCK_NOSE, 3.6))
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return info

    segs = tl.segments()
    a0, b0 = (int(v) for v in args.frames.split("-"))
    frames = [int(v) for v in args.list.split(",")] if args.list else list(range(a0, b0 + 1))
    out = []
    for f in frames:
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        part = render(sh, args.out / f"frame_{f:05d}.png")
        info = {"frame": f, "segment": sh["segment"], "split": False, "parts": [part], "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("WEDGE_FRAME " + json.dumps(info), flush=True)
    (args.out / f"wedge-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                            "frames": out}, indent=1))


if __name__ == "__main__":
    main()
