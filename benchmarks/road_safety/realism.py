"""Photorealism upgrades for the runaway-ramp renderer (Blender Cycles, no external assets).

Three levels, so each improvement can be judged on the same frames:
  A  the existing look (nothing here is called)
  B  beveled edges, a tyre with tread and dust, clear-coated dirty paint, mixed grey/tan stones with real bump
  C  B plus a sprung body: the cab and chassis pitch and bounce after the tyres bite (damped second-order response)

Everything is procedural (no textures downloaded). It is a change of materials, edges, light and body motion; it is not
a scan of a real truck, and the stones are still point-cloud spheres. `suspension` is pure Python and unit-tested;
the `bpy` functions import bpy lazily so the module can be imported without Blender.
"""
from __future__ import annotations

import math

LEVELS = ("A", "B", "C")

#: assumed body suspension (a heavy truck's cab/chassis on its springs); picture-only, not calibrated
SUSPENSION_HZ = 1.6
SUSPENSION_DAMPING = 0.28
HEAVE_M = 0.035


def step_response(t: float, hz: float = SUSPENSION_HZ, zeta: float = SUSPENSION_DAMPING) -> float:
    """Unit-step response of a damped second-order system at time t (s) after the step. 0 before, -> 1 later."""
    if t <= 0.0:
        return 0.0
    w = 2.0 * math.pi * hz
    wd = w * math.sqrt(1.0 - zeta * zeta)
    return 1.0 - math.exp(-zeta * w * t) * (math.cos(wd * t) + zeta * w / wd * math.sin(wd * t))


def suspension(sim_t: float, steady_pitch: float, level: str) -> tuple[float, float]:
    """(pitch in rad, heave in m) of the body. A and B return the steady pitch; C adds the sprung overshoot.

    `steady_pitch` is what the existing renderer applies (nose dips as the truck decelerates). With level C the
    pitch approaches it through a damped oscillation that starts when the tyres touch the gravel (sim_t = 0)."""
    if level != "C" or sim_t <= 0.0:
        return steady_pitch, 0.0
    s = step_response(sim_t)
    pitch = steady_pitch * s
    # the body rises slightly as the nose dives and settles with the same oscillation (derivative-like term)
    heave = -HEAVE_M * (s - 1.0) * math.exp(-0.6 * sim_t)
    return pitch, heave


# ----------------------------------------------------------------------------- Blender (lazy)

def _socket(node, *names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    raise KeyError(names)


def bevel_edges(objects, width: float = 0.035, segments: int = 2) -> None:
    """Round the razor-sharp box edges: a bevel modifier on each box-like object."""
    for ob in objects:
        if ob.type != "MESH" or ob.name.startswith(("Wheel", "Hub", "Lug")):
            continue
        mod = ob.modifiers.new("Bevel", "BEVEL")
        mod.width = min(width, 0.25 * min(ob.dimensions))
        mod.segments = segments
        mod.limit_method = "ANGLE"


def upgrade_materials(mats: dict, gravel_slab, stone_mat) -> None:  # gravel_slab: kept as it was (its colour is part of the look)
    """Paint with clear coat and road dirt, a tyre with tread bump, mixed stones. Edits the existing materials."""
    cab = mats["cab"].node_tree
    bsdf = cab.nodes.get("Principled BSDF")
    for name, value in (("Coat Weight", 1.0), ("Coat Roughness", 0.08)):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = value
    pos = cab.nodes.new("ShaderNodeNewGeometry")
    sep = cab.nodes.new("ShaderNodeSeparateXYZ")
    cab.links.new(pos.outputs["Position"], sep.inputs["Vector"])
    noise = cab.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    noise.inputs["Detail"].default_value = 8.0
    cab.links.new(pos.outputs["Position"], noise.inputs["Vector"])
    low = cab.nodes.new("ShaderNodeMapRange")           # more road dust on the lower body
    low.inputs["From Min"].default_value = 0.9
    low.inputs["From Max"].default_value = 2.4
    low.inputs["To Min"].default_value = 0.55
    low.inputs["To Max"].default_value = 0.0
    cab.links.new(sep.outputs["Z"], low.inputs["Value"])
    mulr = cab.nodes.new("ShaderNodeMath")
    mulr.operation = "MULTIPLY"
    cab.links.new(noise.outputs["Fac"], mulr.inputs[0])
    cab.links.new(low.outputs["Result"], mulr.inputs[1])
    mix = cab.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["B"].default_value = (0.36, 0.30, 0.22, 1.0)
    base_color = bsdf.inputs["Base Color"].default_value[:]
    mix.inputs["A"].default_value = base_color
    cab.links.new(mulr.outputs[0], mix.inputs["Factor"])
    cab.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    rough = cab.nodes.new("ShaderNodeMath")
    rough.operation = "MULTIPLY_ADD"
    rough.inputs[1].default_value = 0.5
    rough.inputs[2].default_value = 0.30
    cab.links.new(mulr.outputs[0], rough.inputs[0])
    cab.links.new(rough.outputs[0], bsdf.inputs["Roughness"])

    # the trailer: dusty white with streaks
    tr = mats["trailer"].node_tree
    tb = tr.nodes.get("Principled BSDF")
    tnoise = tr.nodes.new("ShaderNodeTexNoise")
    tnoise.inputs["Scale"].default_value = 14.0
    tnoise.inputs["Detail"].default_value = 6.0
    tgeo = tr.nodes.new("ShaderNodeNewGeometry")
    tr.links.new(tgeo.outputs["Position"], tnoise.inputs["Vector"])
    tmix = tr.nodes.new("ShaderNodeMix")
    tmix.data_type = "RGBA"
    tmix.inputs["A"].default_value = (0.80, 0.80, 0.78, 1.0)
    tmix.inputs["B"].default_value = (0.42, 0.38, 0.31, 1.0)
    tr.links.new(tnoise.outputs["Fac"], tmix.inputs["Factor"])
    tr.links.new(tmix.outputs["Result"], tb.inputs["Base Color"])

    # tyre: tread lugs around the circumference, grooves across, sidewall noise (object space; the cylinder axis is Z)
    ty = mats["rubber"].node_tree
    tyb = ty.nodes.get("Principled BSDF")
    tc = ty.nodes.new("ShaderNodeTexCoord")
    sp = ty.nodes.new("ShaderNodeSeparateXYZ")
    ty.links.new(tc.outputs["Object"], sp.inputs["Vector"])
    ang = ty.nodes.new("ShaderNodeMath")
    ang.operation = "ARCTAN2"
    ty.links.new(sp.outputs["Y"], ang.inputs[0])
    ty.links.new(sp.outputs["X"], ang.inputs[1])
    lugs = ty.nodes.new("ShaderNodeMath")
    lugs.operation = "MULTIPLY"
    lugs.inputs[1].default_value = 30.0
    ty.links.new(ang.outputs[0], lugs.inputs[0])
    lug_wave = ty.nodes.new("ShaderNodeMath")
    lug_wave.operation = "SINE"
    ty.links.new(lugs.outputs[0], lug_wave.inputs[0])
    zg = ty.nodes.new("ShaderNodeMath")
    zg.operation = "MULTIPLY"
    zg.inputs[1].default_value = 38.0
    ty.links.new(sp.outputs["Z"], zg.inputs[0])
    zwave = ty.nodes.new("ShaderNodeMath")
    zwave.operation = "SINE"
    ty.links.new(zg.outputs[0], zwave.inputs[0])
    both = ty.nodes.new("ShaderNodeMath")
    both.operation = "MULTIPLY"
    ty.links.new(lug_wave.outputs[0], both.inputs[0])
    ty.links.new(zwave.outputs[0], both.inputs[1])
    tbump = ty.nodes.new("ShaderNodeBump")
    tbump.inputs["Strength"].default_value = 1.0
    tbump.inputs["Distance"].default_value = 0.012
    ty.links.new(both.outputs[0], tbump.inputs["Height"])
    ty.links.new(tbump.outputs["Normal"], tyb.inputs["Normal"])
    tyb.inputs["Base Color"].default_value = (0.03, 0.03, 0.03, 1.0)
    tdust = ty.nodes.new("ShaderNodeTexNoise")
    tdust.inputs["Scale"].default_value = 6.0
    ty.links.new(tc.outputs["Object"], tdust.inputs["Vector"])
    dmix = ty.nodes.new("ShaderNodeMix")
    dmix.data_type = "RGBA"
    dmix.inputs["A"].default_value = (0.03, 0.03, 0.03, 1.0)
    dmix.inputs["B"].default_value = (0.30, 0.25, 0.18, 1.0)
    thr = ty.nodes.new("ShaderNodeMath")
    thr.operation = "SUBTRACT"
    thr.inputs[1].default_value = 0.45
    ty.links.new(tdust.outputs["Fac"], thr.inputs[0])
    thr2 = ty.nodes.new("ShaderNodeMath")
    thr2.operation = "MULTIPLY"
    thr2.inputs[1].default_value = 1.4
    ty.links.new(thr.outputs[0], thr2.inputs[0])
    ty.links.new(thr2.outputs[0], dmix.inputs["Factor"])
    ty.links.new(dmix.outputs["Result"], tyb.inputs["Base Color"])

    # stones: grey and tan mixed, rough, with a fine bump
    sn = stone_mat.node_tree
    sb = sn.nodes.get("Principled BSDF")
    pinfo = sn.nodes.get("Point Info") or next(n for n in sn.nodes if n.bl_idname == "ShaderNodePointInfo")
    grey = sn.nodes.new("ShaderNodeValToRGB")
    grey.color_ramp.elements[0].color = (0.30, 0.23, 0.15, 1)
    grey.color_ramp.elements[0].position = 0.0
    grey.color_ramp.elements[1].color = (1.0, 0.80, 0.50, 1)
    mid = grey.color_ramp.elements.new(0.45)
    mid.color = (0.58, 0.46, 0.32, 1)
    sn.links.new(pinfo.outputs["Random"], grey.inputs["Fac"])
    sn.links.new(grey.outputs["Color"], sb.inputs["Base Color"])
    snoise = sn.nodes.new("ShaderNodeTexNoise")
    snoise.inputs["Scale"].default_value = 90.0
    snoise.inputs["Detail"].default_value = 10.0
    sgeo = sn.nodes.new("ShaderNodeNewGeometry")
    sn.links.new(sgeo.outputs["Position"], snoise.inputs["Vector"])
    sbump = sn.nodes.new("ShaderNodeBump")
    sbump.inputs["Strength"].default_value = 0.8
    sbump.inputs["Distance"].default_value = 0.01
    sn.links.new(snoise.outputs["Fac"], sbump.inputs["Height"])
    sn.links.new(sbump.outputs["Normal"], sb.inputs["Normal"])
    sn.links.new(snoise.outputs["Fac"], sb.inputs["Roughness"])
