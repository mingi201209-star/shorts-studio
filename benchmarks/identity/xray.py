"""The channel's reveal look (identity, owner 2026-11-27, playbook section 11). When a film opens a machine up, everything but the
mechanism turns into see-through blueprint blue and the mechanism glows safety orange; the channel's sting plays on that cut
(benchmarks/signature_sting.py). Blender only (imports bpy when used)."""
from __future__ import annotations

BLUE = (0.10, 0.42, 1.0)
ORANGE = (1.0, 0.30, 0.01)


def blueprint_material(name: str = "Xray blueprint"):
    """See-through blue that glows on the edges facing away from the camera (an x-ray outline), faint on faces turned to it."""
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
    lw.inputs["Blend"].default_value = 0.35
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.0
    ramp.inputs["From Max"].default_value = 1.0
    ramp.inputs["To Min"].default_value = 0.08
    ramp.inputs["To Max"].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], ramp.inputs["Value"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*BLUE, 1.0)
    em.inputs["Strength"].default_value = 2.2
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(ramp.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mt


def glow_material(name: str = "Xray glow", colour=ORANGE, strength: float = 5.0):
    import bpy
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    b = mt.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*colour, 1.0)
    b.inputs["Emission Color"].default_value = (*colour, 1.0)
    b.inputs["Emission Strength"].default_value = strength
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
        glow.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = glow_strength
        for ob in bpy.context.scene.objects:
            if ob.type not in ("MESH", "CURVE") or ob.name in self.spared:
                continue
            if ob.name not in self.saved:
                self.saved[ob.name] = [s.material for s in ob.material_slots]
            for k, slot in enumerate(ob.material_slots):
                slot.material = (glow if ob.name in self.mechanism else blue) if on else self.saved[ob.name][k]
        self.on = on
