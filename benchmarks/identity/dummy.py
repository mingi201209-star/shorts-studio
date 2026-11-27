"""The channel's character (identity, owner 2026-11-27, playbook section 11): "Bumper", an original crash-test dummy in safety
yellow with black joints and yellow-and-black target marks. He is the narrator's on-screen self (the channel voice is his) and is
shown fine at the end of each catch. Built from primitives with the Blender data API; posed by rotating joint pivots.

Units: metres, standing height about 1.78 m. Local frame: +y is where he faces, +z up, origin between the hips (seat point)."""
from __future__ import annotations

import math

YELLOW = (0.95, 0.70, 0.04)
BLACK = (0.02, 0.02, 0.02)


def _materials():
    import bpy

    def mat(name, colour, rough=0.45, metal=0.0):
        mt = bpy.data.materials.get(name)
        if mt is None:
            mt = bpy.data.materials.new(name)
            mt.use_nodes = True
            b = mt.node_tree.nodes.get("Principled BSDF")
            b.inputs["Base Color"].default_value = (*colour, 1.0)
            b.inputs["Roughness"].default_value = rough
            b.inputs["Metallic"].default_value = metal
        return mt

    target = bpy.data.materials.get("Bumper target")
    if target is None:                                  # a quartered circle: yellow and black quarters (object space, disc in x-z)
        target = bpy.data.materials.new("Bumper target")
        target.use_nodes = True
        nt = target.node_tree
        b = nt.nodes.get("Principled BSDF")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
        mx = nt.nodes.new("ShaderNodeMath")
        mx.operation = "MULTIPLY"
        nt.links.new(sep.outputs["X"], mx.inputs[0])
        nt.links.new(sep.outputs["Z"], mx.inputs[1])
        sign = nt.nodes.new("ShaderNodeMath")
        sign.operation = "GREATER_THAN"
        sign.inputs[1].default_value = 0.0
        nt.links.new(mx.outputs[0], sign.inputs[0])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        ramp.color_ramp.elements[0].color = (*BLACK, 1)
        ramp.color_ramp.elements[1].position = 0.5
        ramp.color_ramp.elements[1].color = (*YELLOW, 1)
        nt.links.new(sign.outputs[0], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 0.4
    return mat("Bumper yellow", YELLOW), mat("Bumper joints", BLACK, rough=0.6), target, mat("Bumper eyes", BLACK, rough=0.2)


def _cyl(name, r, depth, loc, mat, rot=(0.0, 0.0, 0.0), verts=16):
    import bpy
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def _sphere(name, r, loc, mat, scale=(1.0, 1.0, 1.0)):
    import bpy
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=r, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    return ob


def _pivot(name, parent, loc):
    import bpy
    p = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(p)
    p.parent = parent
    p.location = loc
    return p


def build(name: str = "Bumper") -> dict:
    """Returns {root, pivots..., parts}. Seated by default (thighs forward), arms down."""
    import bpy
    yellow, joints, target, eyes = _materials()
    root = bpy.data.objects.new(f"{name} root", None)
    bpy.context.collection.objects.link(root)
    parts = []
    pelvis = _pivot(f"{name} pelvis", root, (0, 0, 0))
    torso = _pivot(f"{name} torso", pelvis, (0, 0, 0.05))
    parts += [_cyl(f"{name} hips", 0.17, 0.22, (0, 0, 0.0), yellow, rot=(0, math.pi / 2, 0))]
    parts[-1].parent = pelvis
    chest = [_sphere(f"{name} chest", 0.20, (0, 0, 0.36), yellow, scale=(1.05, 0.72, 1.25)),
             _cyl(f"{name} spine", 0.09, 0.22, (0, 0, 0.14), joints),
             _cyl(f"{name} neck", 0.05, 0.12, (0, 0, 0.64), joints)]
    disc = _cyl(f"{name} chest target", 0.07, 0.01, (0, 0.145, 0.42), target, rot=(math.pi / 2, 0, 0), verts=24)
    chest.append(disc)
    for ob in chest:
        ob.parent = torso
    head = _pivot(f"{name} head", torso, (0, 0, 0.70))
    hp = [_sphere(f"{name} skull", 0.125, (0, 0.0, 0.11), yellow, scale=(0.95, 1.05, 1.15)),
          _sphere(f"{name} eye L", 0.018, (-0.045, 0.118, 0.13), eyes), _sphere(f"{name} eye R", 0.018, (0.045, 0.118, 0.13), eyes)]
    for sx in (-1, 1):
        hp.append(_cyl(f"{name} head target {sx}", 0.055, 0.008, (sx * 0.121, 0.0, 0.12), target, rot=(0, math.pi / 2, 0), verts=24))
    for ob in hp:
        ob.parent = head
    piv = {"root": root, "pelvis": pelvis, "torso": torso, "head": head}
    for sx, side in ((-1, "L"), (1, "R")):
        sh = _pivot(f"{name} shoulder {side}", torso, (sx * 0.24, 0, 0.52))
        upper = [_sphere(f"{name} shoulder ball {side}", 0.06, (0, 0, 0), joints), _cyl(f"{name} upper arm {side}", 0.05, 0.27, (0, 0, -0.15), yellow)]
        el = _pivot(f"{name} elbow {side}", sh, (0, 0, -0.30))
        lower = [_sphere(f"{name} elbow ball {side}", 0.048, (0, 0, 0), joints), _cyl(f"{name} forearm {side}", 0.043, 0.25, (0, 0, -0.14), yellow),
                 _sphere(f"{name} hand {side}", 0.05, (0, 0, -0.30), joints, scale=(0.8, 1.0, 1.2))]
        th = _sphere(f"{name} thumb {side}", 0.022, (0, 0.03, -0.27), joints, scale=(1.0, 1.0, 1.6))
        lower.append(th)
        for ob in upper:
            ob.parent = sh
        for ob in lower:
            ob.parent = el
        hip = _pivot(f"{name} hip {side}", pelvis, (sx * 0.10, 0, -0.02))
        thigh = [_sphere(f"{name} hip ball {side}", 0.07, (0, 0, 0), joints), _cyl(f"{name} thigh {side}", 0.075, 0.40, (0, 0, -0.22), yellow)]
        kn = _pivot(f"{name} knee {side}", hip, (0, 0, -0.44))
        shin = [_sphere(f"{name} knee ball {side}", 0.06, (0, 0, 0), joints), _cyl(f"{name} shin {side}", 0.06, 0.40, (0, 0, -0.22), yellow),
                _sphere(f"{name} foot {side}", 0.06, (0, 0.06, -0.45), joints, scale=(0.9, 1.9, 0.6))]
        for ob in thigh:
            ob.parent = hip
        for ob in shin:
            ob.parent = kn
        piv.update({f"shoulder_{side}": sh, f"elbow_{side}": el, f"hip_{side}": hip, f"knee_{side}": kn})
        parts += upper + lower + thigh + shin
    parts += chest + hp
    piv["parts"] = parts
    pose(piv)
    return piv


def pose(d: dict, lean: float = 0.0, thumbs_up: float = 0.0, seated: bool = True, head_nod: float = 0.0) -> None:
    """lean: radians the upper body is thrown forward (a hard stop pushes it into the straps); thumbs_up 0..1 raises the right arm."""
    # rotation about x: positive swings a limb that hangs down (-z) forward (+y); negative tips the upper body back
    d["torso"].rotation_euler = (-lean, 0.0, 0.0)
    d["head"].rotation_euler = (-head_nod - 0.4 * lean, 0.0, 0.0)
    for side in ("L", "R"):
        d[f"hip_{side}"].rotation_euler = (math.pi / 2 if seated else 0.0, 0.0, 0.0)
        d[f"knee_{side}"].rotation_euler = (-math.pi / 2 if seated else 0.0, 0.0, 0.0)
        d[f"shoulder_{side}"].rotation_euler = (0.7 + 0.5 * lean, 0.0, 0.0)
        d[f"elbow_{side}"].rotation_euler = (0.7, 0.0, 0.0)
    if thumbs_up > 0:
        u = min(1.0, thumbs_up)
        d["shoulder_R"].rotation_euler = (0.7 + 0.9 * u, 0.0, -0.5 * u)
        d["elbow_R"].rotation_euler = (0.7 + 0.9 * u, 0.0, 0.0)
