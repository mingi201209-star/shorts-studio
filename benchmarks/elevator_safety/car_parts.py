"""EP.37 scene parts (Blender only), detailed from the start: a concrete hoistway (formwork-marked walls, landing door openings with
closed doors and light at their seams, rail brackets), T-section guide rails for the car and the counterweight, the counterweight
frame with its filler weights, the car (a cab with brushed-steel and glass panels, handrail, ceiling light; the sling around it:
stiles, crosshead, plank, roller guide shoes), the progressive safety gear on each rail (block, wedge, springs, the linkage under
the car and the lever the governor rope pulls), the governor rope, the broken hoist rope ends, passengers and Bumper. No text."""
from __future__ import annotations

import math
import random

import bpy

from benchmarks.buffer_stop import stop_parts as sp
from benchmarks.carrier_wire import detail as cw
from benchmarks.identity import dummy
from benchmarks.road_safety import render_jersey_barrier as base

material, cube = base.material, base.cube
_mesh, _cyl, _sphere, _rbox, emissive = cw._mesh, cw._cyl, cw._sphere, cw._rbox, cw.emissive

SHAFT_X, SHAFT_Y = 1.55, 1.45      # inner half sizes
WALL = 0.25
FLOOR_H = 3.6
RAIL_X = 1.25                      # the car rails' blade tips face the car at x = +-(RAIL_X - 0.0325)
CAB_X, CAB_Y, CAB_H = 0.8, 0.7, 2.3
SHAFT_Z = (-12.0, 16.0)


def mats():
    return {
        "concrete": sp.concrete("Shaft concrete", (0.26, 0.255, 0.245), 1.2, 0.35),
        "rail": material("Guide rail", (0.30, 0.30, 0.31), metal=0.9, rough=0.35),
        "blade": material("Rail blade", (0.62, 0.62, 0.64), metal=1.0, rough=0.2),
        "bracket": material("Bracket", (0.18, 0.19, 0.2), metal=0.6, rough=0.5),
        "steel": material("Sling steel", (0.08, 0.09, 0.10), metal=0.6, rough=0.45),
        "cab": material("Brushed steel", (0.62, 0.63, 0.64), metal=1.0, rough=0.28),
        "glass": cw.canopy_glass("Cab glass"),
        "floor": material("Cab floor", (0.10, 0.10, 0.11), rough=0.7),
        "light": emissive("Cab light", (1.0, 0.93, 0.80), 8.0),
        "door": material("Landing door", (0.40, 0.42, 0.44), metal=0.8, rough=0.35),
        "seam": emissive("Door seam light", (1.0, 0.86, 0.6), 10.0),
        "gear": material("Safety gear", (0.85, 0.55, 0.05), metal=0.4, rough=0.4),
        "wedge": material("Wedge", (0.55, 0.56, 0.58), metal=1.0, rough=0.25),
        "spring": material("Spring", (0.6, 0.1, 0.08), metal=0.5, rough=0.4),
        "rope": material("Wire rope", (0.42, 0.42, 0.43), metal=0.9, rough=0.4),
        "cw": material("Counterweight", (0.16, 0.17, 0.18), metal=0.5, rough=0.6),
        "rubber": material("Roller rubber", (0.04, 0.04, 0.04), rough=0.6),
        "spark": material("Spark", (1.0, 0.72, 0.3), emission=14.0),
        "handrail": material("Handrail", (0.85, 0.85, 0.87), metal=1.0, rough=0.15),
    }


T_SECTION = [(-0.0635, 0.0), (0.0635, 0.0), (0.0635, 0.012), (0.008, 0.012), (0.008, 0.077), (-0.008, 0.077), (-0.008, 0.012), (-0.0635, 0.012)]


def _rail(m, name, x, y, z0, z1, facing):
    """A T-rail along z: its base on the wall side, the blade toward the car (facing = +1: blade toward +x)."""
    n = len(T_SECTION)
    verts = []
    for z in (z0, z1):
        for u, d in T_SECTION:                         # u across (along y), d out from the base (along x toward the car)
            verts.append((x + facing * d, y + u, z))
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    ob = _mesh(name, verts, faces, m["rail"])
    tip = cube(f"{name} blade face", (x + facing * 0.0775, y, (z0 + z1) / 2), (0.003, 0.016, z1 - z0), m["blade"])
    return [ob, tip]


def hoistway(m):
    obs = []
    z0, z1 = SHAFT_Z
    zc, h = (z0 + z1) / 2, z1 - z0
    # back (+y) and left (-x) walls; the right (+x) wall is the cutaway side, the front (-y) wall carries the landing doors
    obs.append(cube("Wall back", (0.0, SHAFT_Y + WALL / 2, zc), (2 * SHAFT_X + 2 * WALL, WALL, h), m["concrete"]))
    obs.append(cube("Wall left", (-SHAFT_X - WALL / 2, 0.0, zc), (WALL, 2 * SHAFT_Y, h), m["concrete"]))
    front = []
    z = z0
    while z < z1:
        # a storey of front wall with a door opening 1.0 x 2.2 m at the floor
        front.append(cube(f"Wall front low {z:.1f}", (-(SHAFT_X + 0.5) / 2 - 0.25, -SHAFT_Y - WALL / 2, z + 1.1), (SHAFT_X - 0.5 + WALL, WALL, 2.2), m["concrete"]))
        front.append(cube(f"Wall front low r {z:.1f}", ((SHAFT_X + 0.5) / 2 + 0.25, -SHAFT_Y - WALL / 2, z + 1.1), (SHAFT_X - 0.5 + WALL, WALL, 2.2), m["concrete"]))
        front.append(cube(f"Wall front high {z:.1f}", (0.0, -SHAFT_Y - WALL / 2, z + 2.2 + (FLOOR_H - 2.2) / 2), (2 * SHAFT_X + 2 * WALL, WALL, FLOOR_H - 2.2), m["concrete"]))
        for sx in (-1, 1):
            front.append(cube(f"Landing door {z:.1f} {sx}", (sx * 0.25, -SHAFT_Y + 0.02, z + 1.1), (0.495, 0.04, 2.18), m["door"]))
        front.append(cube(f"Door seam {z:.1f}", (0.0, -SHAFT_Y + 0.045, z + 1.1), (0.012, 0.01, 2.1), m["seam"]))
        front.append(cube(f"Sill {z:.1f}", (0.0, -SHAFT_Y + 0.06, z - 0.02), (1.2, 0.12, 0.04), m["bracket"]))
        front.append(cube(f"Header {z:.1f}", (0.0, -SHAFT_Y + 0.08, z + 2.32), (1.4, 0.16, 0.2), m["bracket"]))
        z += FLOOR_H
    obs += front
    # car rails on both side walls (blades toward the car), counterweight rails on the back wall
    for sx in (-1, 1):
        obs += _rail(m, f"Car rail {sx}", sx * (SHAFT_X - 0.02), 0.0, z0, z1, -sx)
        zz = z0 + 1.0
        while zz < z1:
            obs.append(cube(f"Rail bracket {sx} {zz:.1f}", (sx * (SHAFT_X - 0.01), 0.0, zz), (0.04, 0.3, 0.2), m["bracket"]))
            zz += 2.5
    for sx in (-1, 1):                                                   # counterweight rails: base on the back wall, blade toward -y
        n = len(T_SECTION)
        x, y = sx * 0.48, SHAFT_Y - 0.02
        verts = [(x + u, y - d, z) for z in (z0, z1) for u, d in T_SECTION]
        faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        obs.append(_mesh(f"Weight rail {sx}", verts, faces, m["rail"]))
    obs.append(cube("Pit floor", (0.0, 0.0, z0), (2 * SHAFT_X, 2 * SHAFT_Y, 0.1), m["concrete"]))
    return obs


def counterweight(m, z):
    root = bpy.data.objects.new("Counterweight root", None)
    bpy.context.collection.objects.link(root)
    parts = [cube("CW stile L", (-0.4, SHAFT_Y - 0.25, 1.6), (0.08, 0.16, 3.2), m["steel"]), cube("CW stile R", (0.4, SHAFT_Y - 0.25, 1.6), (0.08, 0.16, 3.2), m["steel"]),
             cube("CW top", (0.0, SHAFT_Y - 0.25, 3.22), (0.9, 0.18, 0.12), m["steel"]), cube("CW bottom", (0.0, SHAFT_Y - 0.25, 0.0), (0.9, 0.18, 0.12), m["steel"])]
    for k in range(14):
        parts.append(_rbox(f"CW filler {k}", (0.0, SHAFT_Y - 0.25, 0.15 + k * 0.21), (0.72, 0.14, 0.18), m["cw"], 0.01))
    for ob in parts:
        ob.parent = root
    root.location = (0.0, 0.0, z)
    return root


def car(m, seed=37):
    """The car, root at its platform's floor level on the shaft's centre line; returns what the renderer moves."""
    rng = random.Random(seed)
    root = bpy.data.objects.new("Car root", None)
    bpy.context.collection.objects.link(root)
    P = []
    # the cab: floor, ceiling, back and left steel panels, the right (+x) side and front glass with steel frames, doors on -y
    P.append(cube("Cab floor", (0.0, 0.0, -0.08), (2 * CAB_X, 2 * CAB_Y, 0.16), m["floor"]))
    P.append(cube("Cab ceiling", (0.0, 0.0, CAB_H + 0.05), (2 * CAB_X, 2 * CAB_Y, 0.1), m["cab"]))
    P.append(cube("Cab ceiling light", (0.0, 0.0, CAB_H - 0.005), (1.0, 0.9, 0.01), m["light"]))
    P.append(cube("Cab back", (0.0, CAB_Y - 0.02, CAB_H / 2), (2 * CAB_X, 0.04, CAB_H), m["cab"]))
    P.append(cube("Cab left", (-CAB_X + 0.02, 0.0, CAB_H / 2), (0.04, 2 * CAB_Y, CAB_H), m["cab"]))
    P.append(cube("Cab right glass", (CAB_X - 0.02, 0.0, CAB_H / 2 + 0.2), (0.02, 2 * CAB_Y - 0.1, CAB_H - 0.5), m["glass"]))
    P.append(cube("Cab right kick", (CAB_X - 0.02, 0.0, 0.15), (0.04, 2 * CAB_Y, 0.3), m["cab"]))
    for y in (-CAB_Y + 0.03, CAB_Y - 0.03):
        P.append(cube(f"Cab post {y:.2f}", (CAB_X - 0.02, y, CAB_H / 2), (0.06, 0.06, CAB_H), m["cab"]))
    P.append(cube("Cab top rail", (CAB_X - 0.02, 0.0, CAB_H - 0.03), (0.06, 2 * CAB_Y, 0.06), m["cab"]))
    for sx in (-1, 1):
        P.append(cube(f"Car door {sx}", (sx * 0.27, -CAB_Y + 0.02, 1.1), (0.52, 0.04, 2.2), m["cab"]))
    P.append(cube("Handrail", (CAB_X - 0.08, 0.0, 0.95), (0.04, 2 * CAB_Y - 0.25, 0.04), m["handrail"]))
    P.append(cube("Handrail back", (0.0, CAB_Y - 0.08, 0.95), (2 * CAB_X - 0.25, 0.04, 0.04), m["handrail"]))
    # the sling: stiles beside the rails, crosshead over the cab, plank under it, roller guide shoes top and bottom
    for sx in (-1, 1):
        x = sx * (RAIL_X - 0.15)
        P.append(cube(f"Stile {sx}", (x, 0.0, CAB_H / 2 + 0.1), (0.1, 0.2, CAB_H + 0.9), m["steel"]))
        for z in (-0.5, CAB_H + 0.45):
            P.append(_rbox(f"Guide shoe {sx} {z:.1f}", (sx * (RAIL_X - 0.04), 0.0, z), (0.1, 0.26, 0.2), m["steel"], 0.01))
            for dy in (-0.09, 0.0, 0.09):
                P.append(_cyl(f"Roller {sx} {z:.1f} {dy}", 0.055, 0.03, (sx * (SHAFT_X - 0.115) - sx * 0.0, dy, z), m["rubber"],
                              rot=(0, math.pi / 2, 0) if dy == 0 else (math.pi / 2, 0, 0), verts=16))
    P.append(cube("Crosshead", (0.0, 0.0, CAB_H + 0.5), (2 * RAIL_X - 0.2, 0.22, 0.24), m["steel"]))
    P.append(cube("Plank", (0.0, 0.0, -0.32), (2 * RAIL_X - 0.2, 0.26, 0.28), m["steel"]))
    P.append(cube("Rope hitch", (0.0, 0.0, CAB_H + 0.7), (0.5, 0.18, 0.16), m["steel"]))
    # the progressive safety gear on each rail: a block under the plank's end, the wedge in it, springs, the linkage bar, the lever
    gear, wedges = [], []
    for sx in (-1, 1):
        bx = sx * (SHAFT_X - 0.02 - 0.06)
        g = [_rbox(f"Gear block {sx}", (bx, 0.0, -0.42), (0.16, 0.24, 0.34), m["gear"], 0.012)]
        for dy in (-0.085, 0.085):
            g.append(_cyl(f"Gear spring {sx} {dy}", 0.035, 0.24, (bx - sx * 0.05, dy, -0.42), m["spring"], verts=12))
        w = _rbox(f"Wedge {sx}", (sx * (SHAFT_X - 0.02 - 0.0775 - 0.016), 0.0, -0.5), (0.03, 0.08, 0.2), m["wedge"], 0.005)
        wedges.append(w)
        gear += g + [w]
    gear.append(cube("Safety linkage", (0.0, 0.12, -0.5), (2 * RAIL_X - 0.15, 0.04, 0.04), m["steel"]))
    lever = cube("Safety lever", (-RAIL_X + 0.35, 0.22, -0.32), (0.04, 0.04, 0.45), m["gear"])
    gear.append(lever)
    P += gear
    for ob in P:
        ob.parent = root
    # people: Bumper and two passengers standing
    people = []
    d = dummy.build("Bumper")
    d["root"].parent = root
    d["root"].location = (0.35, 0.25, 0.86)
    d["root"].rotation_euler = (0.0, 0.0, math.pi / 2)              # facing the glass (+x)
    dummy.pose(d, seated=False)
    for k, (x, y, col, yaw) in enumerate(((-0.25, -0.25, (0.55, 0.08, 0.10), 1.4), (-0.35, 0.35, (0.12, 0.14, 0.18), 1.9))):
        p = sp.passenger(k + 20, col, rng)
        p.parent = root
        p.location = (x, y, 0.0)
        p.rotation_euler = (0.0, 0.0, yaw)
        people.append(p)
    # broken hoist rope ends on the hitch (five ropes), each a short frayed curve the renderer whips
    stubs = []
    for k in range(5):
        cu = bpy.data.curves.new(f"Rope stub {k}", "CURVE")
        cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.013, 2
        ob = bpy.data.objects.new(f"Rope stub {k}", cu)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(m["rope"])
        ob.parent = root
        ob["x"] = -0.16 + 0.08 * k
        ob["len"] = rng.uniform(0.9, 1.6)
        ob["phase"] = rng.uniform(0, 6.28)
        stubs.append(ob)
    return {"root": root, "parts": P, "gear": gear, "wedges": wedges, "bumper": d, "people": people, "stubs": stubs}


def governor_rope(m):
    """The governor rope: a loop running the full height beside the left rail; the car's lever is hitched to one run of it."""
    obs = []
    z0, z1 = SHAFT_Z
    for k, y in enumerate((0.22, 0.42)):
        obs.append(cube(f"Governor rope {k}", (-RAIL_X + 0.35, y, (z0 + z1) / 2), (0.01, 0.01, z1 - z0), m["rope"]))
    return obs


def set_stub(ob, t, slack):
    """A broken rope end: from the hitch up, then flopping over (more as it goes slack), whipping with time."""
    x0 = ob["x"]
    L = ob["len"]
    pts = []
    for i in range(8):
        s = i / 7
        sway = (0.25 + 0.6 * slack) * s * s * math.sin(ob["phase"] + 9.0 * t + 2.2 * s)
        bend = slack * 0.6 * s * s
        pts.append((x0 + sway, 0.05 * math.sin(ob["phase"] + 5 * t) * s + bend * 0.5, CAB_H + 0.78 + L * s * (1 - 0.35 * slack * s)))
    cu = ob.data
    cu.splines.clear()
    spl = cu.splines.new("POLY")
    spl.points.add(len(pts) - 1)
    for p, q in zip(spl.points, pts):
        p.co = (*q, 1.0)


def sparks(m, n=120, seed=37):
    rng = random.Random(seed)
    obs = []
    for k in range(n):
        s = rng.uniform(0.016, 0.034)
        ob = cube(f"Spark {k}", (0, 0, -50), (s, s, s * 4.0), m["spark"])
        ob["phase"] = rng.random()
        ob["v"] = (rng.uniform(0.2, 1.4), rng.uniform(-1.6, 1.6), rng.uniform(0.5, 3.5))
        ob["side"] = 1 if k % 2 else -1
        obs.append(ob)
    return obs
