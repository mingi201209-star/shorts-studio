"""The channel's reveal look (identity, owner 2026-11-27, playbook section 11). When a film opens a machine up, everything but the
mechanism turns into see-through blueprint blue and the mechanism glows safety orange; the channel's sting plays on that cut
(benchmarks/signature_sting.py). Blender only (imports bpy when used)."""
from __future__ import annotations

BLUE = (0.10, 0.42, 1.0)
ORANGE = (1.0, 0.30, 0.01)


def _grid_lines(nt, coords, normal, spacing, width):
    """0..1: how much a point sits on a grid line (planes every `spacing` along x, y and z, each family fading where the surface
    runs parallel to its planes, so lines stay thin on every face)."""
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coords, sep.inputs["Vector"])
    nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(normal, nsep.inputs["Vector"])

    def math(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = float(v)
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    def remap(v, lo, hi, to_lo, to_hi):
        r = nt.nodes.new("ShaderNodeMapRange")
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = lo, hi
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = to_lo, to_hi
        nt.links.new(v, r.inputs["Value"])
        return r.outputs["Result"]

    total = None
    for axis in ("X", "Y", "Z"):
        f = math("FRACT", math("DIVIDE", sep.outputs[axis], spacing))
        dist = math("MULTIPLY", math("SUBTRACT", 0.5, math("ABSOLUTE", math("SUBTRACT", f, 0.5))), spacing)
        on_line = remap(dist, 0.0, width, 1.0, 0.0)
        square = remap(math("ABSOLUTE", nsep.outputs[axis]), 0.55, 0.85, 1.0, 0.0)
        g = math("MULTIPLY", on_line, square)
        total = g if total is None else math("MAXIMUM", total, g)
    return total


def blueprint_material(name: str = "Xray blueprint"):
    """See-through blue that glows on the edges turned away from the camera (an x-ray outline), faint on faces turned to it, with a
    fine blueprint grid on every surface (lines each metre, stronger every five), so big faces read as drawn, not empty."""
    import bpy
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.0
    ramp.inputs["From Max"].default_value = 1.0
    ramp.inputs["To Min"].default_value = 0.08
    ramp.inputs["To Max"].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], ramp.inputs["Value"])
    fine = _grid_lines(nt, tc.outputs["Object"], tc.outputs["Normal"], 1.0, 0.018)
    major = _grid_lines(nt, tc.outputs["Object"], tc.outputs["Normal"], 5.0, 0.04)
    grid = nt.nodes.new("ShaderNodeMath")
    grid.operation = "MAXIMUM"
    fine_k = nt.nodes.new("ShaderNodeMath")
    fine_k.operation = "MULTIPLY"
    fine_k.inputs[1].default_value = 0.35
    nt.links.new(fine, fine_k.inputs[0])
    nt.links.new(fine_k.outputs[0], grid.inputs[0])
    major_k = nt.nodes.new("ShaderNodeMath")
    major_k.operation = "MULTIPLY"
    major_k.inputs[1].default_value = 0.7
    nt.links.new(major, major_k.inputs[0])
    nt.links.new(major_k.outputs[0], grid.inputs[1])
    fac = nt.nodes.new("ShaderNodeMath")
    fac.operation = "MAXIMUM"
    nt.links.new(ramp.outputs["Result"], fac.inputs[0])
    nt.links.new(grid.outputs[0], fac.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*BLUE, 1.0)
    em.inputs["Strength"].default_value = 2.2
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fac.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mt


def glow_material(name: str = "Xray glow", colour=ORANGE, strength: float = 5.0):
    """The mechanism as a glowing scan: bright, hot rims where the surface turns away (outline and edges), a dimmer see-through core,
    so parts behind parts still show. The strength is a node named "Glow strength" (Xray.set drives it)."""
    import bpy
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.4
    value = nt.nodes.new("ShaderNodeValue")
    value.name = value.label = "Glow strength"
    value.outputs[0].default_value = strength
    rim = nt.nodes.new("ShaderNodeMapRange")                  # core 0.35x, rim 1.4x the strength (brighter washes the orange out)
    rim.inputs["To Min"].default_value, rim.inputs["To Max"].default_value = 0.35, 1.4
    nt.links.new(lw.outputs["Facing"], rim.inputs["Value"])
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    nt.links.new(rim.outputs["Result"], k.inputs[0])
    nt.links.new(value.outputs[0], k.inputs[1])
    hot = nt.nodes.new("ShaderNodeMix")                         # the rims run hotter, toward yellow-white
    hot.data_type = "RGBA"
    nt.links.new(lw.outputs["Facing"], hot.inputs["Factor"])
    hot.inputs["A"].default_value = (*colour, 1.0)
    hot.inputs["B"].default_value = (1.0, 0.55, 0.15, 1.0)
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(hot.outputs["Result"], em.inputs["Color"])
    nt.links.new(k.outputs[0], em.inputs["Strength"])
    dense = nt.nodes.new("ShaderNodeMapRange")                  # 60 % opaque in the core, solid at the rim
    dense.inputs["To Min"].default_value, dense.inputs["To Max"].default_value = 0.6, 1.0
    nt.links.new(lw.outputs["Facing"], dense.inputs["Value"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(dense.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mt


def thermal_material(name: str = "Xray thermal"):
    """Heat in the x-ray look, the way a thermal camera shows it: an ironbow ramp (purple, red, orange, yellow, white) on an
    emission. The object's colour carries the heat: red = heat 0..1; green = 1 makes it fade along the object's own y (hot at
    the +y end), for a streak that cools behind what made it."""
    import bpy
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(oi.outputs["Color"], sep.inputs["Color"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    gy = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], gy.inputs["Vector"])
    fade = nt.nodes.new("ShaderNodeMapRange")                   # 0.15 at the -y end, 1 at the +y end
    fade.inputs["To Min"].default_value, fade.inputs["To Max"].default_value = 0.15, 1.0
    nt.links.new(gy.outputs["Y"], fade.inputs["Value"])
    pick = nt.nodes.new("ShaderNodeMix")                        # green 0: uniform; green 1: the fade
    pick.data_type = "FLOAT"
    nt.links.new(sep.outputs["Green"], pick.inputs["Factor"])
    pick.inputs["A"].default_value = 1.0
    nt.links.new(fade.outputs["Result"], pick.inputs["B"])
    heat = nt.nodes.new("ShaderNodeMath")
    heat.operation = "MULTIPLY"
    heat.use_clamp = True
    nt.links.new(sep.outputs["Red"], heat.inputs[0])
    nt.links.new(pick.outputs["Result"], heat.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.22, 0.02, 0.32, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (1.0, 0.97, 0.88, 1)
    for pos, col in ((0.35, (0.85, 0.07, 0.04, 1)), (0.62, (1.0, 0.42, 0.03, 1)), (0.84, (1.0, 0.82, 0.18, 1))):
        el = cr.elements.new(pos)
        el.color = col
    nt.links.new(heat.outputs[0], ramp.inputs["Fac"])
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.4
    rim = nt.nodes.new("ShaderNodeMapRange")                    # rims a little brighter, so the shapes still read
    rim.inputs["To Min"].default_value, rim.inputs["To Max"].default_value = 0.75, 1.3
    nt.links.new(lw.outputs["Facing"], rim.inputs["Value"])
    k = nt.nodes.new("ShaderNodeMapRange")                      # brighter as it heats
    k.inputs["To Min"].default_value, k.inputs["To Max"].default_value = 0.8, 6.0
    nt.links.new(heat.outputs[0], k.inputs["Value"])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    nt.links.new(k.outputs["Result"], st.inputs[0])
    nt.links.new(rim.outputs["Result"], st.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(st.outputs[0], em.inputs["Strength"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mt


class Xray:
    """Swaps materials on and off. mechanism: the objects that glow; spared: objects left as they are (e.g. the sea); every other
    mesh or curve turns blueprint blue. Originals are kept and restored exactly."""

    def __init__(self, mechanism, spared=()):
        self.mechanism = {ob.name for ob in mechanism}
        self.spared = {ob.name for ob in spared}
        self.saved = {}
        self.on = False

    def set(self, on: bool, glow_strength: float = 5.0):
        import bpy
        if on == self.on and not on:
            return
        blue, glow = blueprint_material(), glow_material(strength=glow_strength)
        glow.node_tree.nodes["Glow strength"].outputs[0].default_value = glow_strength
        for ob in bpy.context.scene.objects:
            if ob.type not in ("MESH", "CURVE") or ob.name in self.spared:
                continue
            if ob.name not in self.saved:
                self.saved[ob.name] = [s.material for s in ob.material_slots]
            for k, slot in enumerate(ob.material_slots):
                slot.material = (glow if ob.name in self.mechanism else blue) if on else self.saved[ob.name][k]
        self.on = on
