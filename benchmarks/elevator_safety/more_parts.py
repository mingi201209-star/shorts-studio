"""EP.37 parts for the shots after the frozen opening (Blender only). Kept apart from car_parts so the opening's code path is
unchanged:
- the hoist ropes running up from the car's hitch to the top of the shaft (before they break);
- the machine room at the top of the hoistway: the traction machine, the governor on its stand with the governor rope loop going
  down through the floor, its two flyweights on the sheave and the pawl that locks it;
- the drop marker: the car's fall from the break to the stop laid out in safety yellow beside the car;
- 1854: an open wooden hoist tower with toothed guide posts, the platform with crates and barrels, a wagon spring with pawls under
  the top beam, the hoist rope, a man on the platform and a crowd below. No text, no likeness of anyone."""
from __future__ import annotations

import math
import random

import bpy

from benchmarks.buffer_stop import stop_parts as sp
from benchmarks.elevator_safety import car_parts as cp
from benchmarks.identity import dummy

cube, _cyl, _rbox, material, emissive = cp.cube, cp._cyl, cp._rbox, cp.material, cp.emissive

N_ROPES = 5                        # matches the five broken rope ends of the opening
HITCH_Z = cp.CAB_H + 0.78          # where the ropes leave the car (car frame)
TOP_Z = cp.SHAFT_Z[1]
GOV = (60.0, 0.0, 0.0)             # the machine room, built away from the shaft
GOV_R = 0.30                       # governor sheave radius (m)
OTIS = (-60.0, 0.0, 0.0)           # the 1854 tower


def hoist_ropes(m):
    """Five unit-length ropes along +z from the hitch; the renderer stretches them to the top of the shaft."""
    out = []
    for k in range(N_ROPES):
        ob = _cyl(f"Hoist rope {k}", 0.013, 1.0, (0.0, 0.0, 0.5), m["rope"], verts=10)
        bpy.context.view_layer.update()
        ob["x"] = -0.16 + 0.08 * k
        out.append(ob)
    return out


def set_ropes(ropes, car_z, on):
    for ob in ropes:
        if not on:
            ob.location = (0, 0, -80)
            continue
        z0 = car_z + HITCH_Z
        ob.location = (ob["x"], 0.0, (z0 + TOP_Z) / 2)
        ob.scale = (1.0, 1.0, max(0.01, TOP_Z - z0))


def glow(name, colour, strength):
    return emissive(name, colour, strength)


def machine_room(m):
    """Returns the room's parts, the sheave root (it spins about x), the two flyweight pivots and the pawl."""
    ox, oy, oz = GOV
    floor = material("MR floor paint", (0.20, 0.22, 0.21), rough=0.6)
    dark = material("MR wall", (0.30, 0.30, 0.29), rough=0.8)
    room = [cube("MR floor", (ox, oy, oz - 0.1), (8.0, 8.0, 0.2), floor),
            cube("MR ceiling", (ox, oy, oz + 3.3), (8.0, 8.0, 0.2), dark),
            cube("MR wall right", (ox + 3.0, oy, oz + 1.6), (0.2, 8.0, 3.2), dark),
            cube("MR hoist beam", (ox, oy, oz + 3.05), (0.2, 6.0, 0.3), m["steel"]),
            _rbox("MR controller", (ox + 1.6, oy + 2.6, oz + 1.0), (1.2, 0.5, 2.0), material("Controller grey", (0.55, 0.56, 0.55), metal=0.3, rough=0.5), 0.02),
            cube("MR controller light", (ox + 1.3, oy + 2.34, oz + 1.6), (0.06, 0.01, 0.06), emissive("Status green", (0.1, 1.0, 0.3), 6.0)),
            cube("MR wall back", (ox, oy + 3.0, oz + 1.6), (8.0, 0.2, 3.2), dark),
            cube("MR wall left", (ox - 3.0, oy, oz + 1.6), (0.2, 8.0, 3.2), dark),
            _rbox("Traction machine", (ox - 1.4, oy + 1.6, oz + 0.55), (1.6, 0.9, 1.1), sp_mat(m, "machine"), 0.05),
            _cyl("Machine sheave", 0.38, 0.35, (ox - 1.4, oy + 0.9, oz + 0.75), m["steel"], rot=(0, math.pi / 2, 0), verts=40),
            _rbox("Governor stand", (ox, oy, oz + 0.35), (0.42, 0.5, 0.7), sp_mat(m, "machine"), 0.02),
            cube("Floor hole", (ox, oy, oz + 0.005), (0.5, 0.18, 0.01), m["steel"])]
    for sx in (-1, 1):
        room.append(_rbox(f"Gov bearing {sx}", (ox + sx * 0.13, oy, oz + 0.95), (0.05, 0.14, 0.5), sp_mat(m, "machine"), 0.01))
    root = bpy.data.objects.new("Gov sheave", None)
    bpy.context.collection.objects.link(root)
    root.location = (ox, oy, oz + 1.15)
    parts = [_cyl("Gov rim", GOV_R, 0.06, (0, 0, 0), m["steel"], rot=(0, math.pi / 2, 0), verts=48),
             _cyl("Gov groove", GOV_R + 0.005, 0.02, (0, 0, 0), m["rope"], rot=(0, math.pi / 2, 0), verts=48),
             _cyl("Gov hub", 0.06, 0.12, (0, 0, 0), m["handrail"], rot=(0, math.pi / 2, 0), verts=24)]
    for k in range(6):
        a = k * math.pi / 3
        sp_ = cube(f"Gov spoke {k}", (0, 0.5 * GOV_R * math.cos(a), 0.5 * GOV_R * math.sin(a)), (0.03, GOV_R, 0.03), m["steel"])
        sp_.rotation_euler = (a - math.pi / 2, 0, 0)
        parts.append(sp_)
    for k in range(10):                                      # the ratchet teeth on the sheave's face
        a = k * 2 * math.pi / 10
        t = cube(f"Gov tooth {k}", (0.05, (GOV_R - 0.03) * math.cos(a), (GOV_R - 0.03) * math.sin(a)), (0.03, 0.05, 0.035), m["gear"])
        t.rotation_euler = (a, 0, 0)
        parts.append(t)
    flyweights = []
    for k, a in enumerate((0.0, math.pi)):
        piv = bpy.data.objects.new(f"Flyweight pivot {k}", None)
        bpy.context.collection.objects.link(piv)
        piv.parent = root
        piv.location = (0.07, 0.12 * math.cos(a), 0.12 * math.sin(a))
        piv.rotation_euler = (a, 0, 0)
        w = _rbox(f"Flyweight {k}", (0.0, 0.0, 0.08), (0.04, 0.07, 0.17), m["gear"], 0.01)
        w.parent = piv
        flyweights.append(piv)
    for ob in parts:
        ob.parent = root
    pawl = cube("Gov pawl", (ox + 0.12, oy - 0.0, oz + 1.15 + GOV_R + 0.12), (0.05, 0.05, 0.22), m["gear"])
    rope = [cube(f"Gov rope run {k}", (ox + 0.03, oy + sy * GOV_R, oz + 0.5), (0.02, 0.02, 1.3), m["rope"]) for k, sy in enumerate((-1, 1))]
    return {"room": room, "sheave": root, "parts": parts, "flyweights": flyweights, "pawl": pawl, "rope": rope}


def sp_mat(m, key):
    if key not in m:
        m[key] = material("Machine green", (0.10, 0.22, 0.16), metal=0.5, rough=0.45)
    return m[key]


def drop_marker():
    ob = cube("Drop marker", (0, 0, -80), (0.02, 1.3, 1.0), sp._marker_material())
    return ob


def otis_tower(m, seed=1854):
    """The 1854 demonstration: two toothed wooden guide posts, a top beam with the hoist sheave, the open platform with crates and
    barrels, the wagon spring under the platform's top frame with a pawl at each end, the man on the platform, a crowd below."""
    rng = random.Random(seed)
    ox, oy, oz = OTIS
    wood = material("Old timber", (0.33, 0.21, 0.11), rough=0.85)
    iron = material("Black iron", (0.06, 0.06, 0.06), metal=0.7, rough=0.5)
    obs = [cube("Exhibition floor", (ox, oy, oz - 0.05), (30.0, 30.0, 0.1), material("Hall floor", (0.42, 0.36, 0.28), rough=0.7)),
           cube("Hall wall", (ox, oy + 9.0, oz + 6.0), (30.0, 0.3, 12.0), material("Hall wall", (0.55, 0.5, 0.42), rough=0.8))]
    for sx in (-1, 1):
        x = ox + sx * 1.3
        obs.append(cube(f"Guide post {sx}", (x, oy, oz + 6.0), (0.25, 0.25, 12.0), wood))
        z = 0.4
        while z < 11.5:
            t = cube(f"Post tooth {sx} {z:.1f}", (x - sx * 0.16, oy, oz + z), (0.07, 0.2, 0.12), iron)
            t.rotation_euler = (0, sx * 0.5, 0)
            obs.append(t)
            z += 0.3
    obs.append(cube("Top beam", (ox, oy, oz + 12.1), (3.0, 0.3, 0.3), wood))
    obs.append(_cyl("Top sheave", 0.35, 0.1, (ox, oy, oz + 12.6), iron, rot=(0, math.pi / 2, 0), verts=32))
    root = bpy.data.objects.new("Otis platform", None)
    bpy.context.collection.objects.link(root)
    plat = [cube("Platform deck", (0, 0, 0.0), (2.3, 2.0, 0.12), wood),
            cube("Platform frame top", (0, 0, 2.6), (2.5, 0.2, 0.2), wood)]
    for sx in (-1, 1):
        plat.append(cube(f"Platform upright {sx}", (sx * 1.12, 0, 1.3), (0.15, 0.15, 2.6), wood))
        pawl = cube(f"Spring pawl {sx}", (sx * 1.2, 0, 2.5), (0.25, 0.12, 0.06), iron)
        plat.append(pawl)
    spring = []
    for k in range(4):
        leaf = cube(f"Wagon spring leaf {k}", (0, 0, 2.75 + 0.03 * k), (2.2 - 0.35 * k, 0.12, 0.025), iron)
        spring.append(leaf)
    plat += spring
    plat.append(cube("Hitch", (0, 0, 2.9), (0.15, 0.15, 0.12), iron))
    for k, (x, y, s) in enumerate(((-0.6, 0.5, 0.5), (0.65, 0.45, 0.45), (0.7, -0.3, 0.4))):
        plat.append(_rbox(f"Crate {k}", (x, y, 0.06 + s / 2), (s, s, s), wood, 0.02))
    plat.append(_cyl("Barrel", 0.25, 0.6, (-0.7, -0.45, 0.36), material("Barrel", (0.4, 0.25, 0.12), rough=0.7), verts=20))
    for ob in plat:
        ob.parent = root
    man = sp.passenger(54, (0.08, 0.08, 0.1), rng)                 # dark coat
    man.parent = root
    man.location = (0.1, -0.2, 0.06)
    man.rotation_euler = (0, 0, -math.pi / 2)
    rope = cube("Otis rope", (0, 0, 0), (0.03, 0.03, 1.0), material("Hemp", (0.6, 0.5, 0.32), rough=0.9))
    crowd = []
    for k in range(14):
        p = sp.passenger(70 + k, ((0.1, 0.08, 0.07), (0.25, 0.2, 0.15), (0.15, 0.17, 0.25), (0.35, 0.1, 0.1))[k % 4], rng)
        p.location = (ox + rng.uniform(-5, 5), oy - rng.uniform(3.0, 7.0), oz)
        p.rotation_euler = (0, 0, math.pi / 2 + rng.uniform(-0.4, 0.4))
        crowd.append(p)
    return {"static": obs, "root": root, "plat": plat, "spring": spring, "rope": rope, "man": man, "crowd": crowd}


def set_otis(o, z, cut, t):
    """Platform at height z (m above the floor). The rope runs from the hitch to the top sheave until it is cut; then its upper end
    whips up and its lower end falls slack."""
    ox, oy, oz = OTIS
    o["root"].location = (ox, oy, oz + z)
    top, hitch = oz + 12.6, oz + z + 2.96
    r = o["rope"]
    if not cut:
        r.location = (ox, oy, (top + hitch) / 2)
        r.scale = (1, 1, max(0.01, top - hitch))
        r.rotation_euler = (0, 0, 0)
    else:
        L = 1.2
        r.location = (ox + 0.15 * math.sin(9 * t), oy, top - L / 2 + 0.3 * min(1.0, t * 4))
        r.scale = (1, 1, L)
        r.rotation_euler = (0, 0.25 * math.sin(11 * t), 0)
