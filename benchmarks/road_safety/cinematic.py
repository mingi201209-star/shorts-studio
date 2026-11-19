"""Look-development helpers shared by the road-safety episodes: a physically
based sky and matching sun, depth of field, and the colour grade applied in
the final encode. No external assets are used (everything is procedural), so
a render is reproducible from the repository alone.

The sky is Blender's Nishita model (air and dust scattering). The sun lamp
and the sky's sun are aligned through `sun_vector`; the sky's own disc is
switched off so the lamp is the only direct sun.
"""
from __future__ import annotations

import math

LOOK_STANDARD = "standard"
LOOK_CINEMATIC = "cinematic"


def sun_vector(azimuth_dir: tuple[float, float], elevation_deg: float) -> tuple[float, float, float]:
    """Unit vector pointing from the scene toward the sun. `azimuth_dir` is the
    horizontal (x, y) direction of the sun; it is normalised here."""
    h = math.hypot(*azimuth_dir) or 1.0
    el = math.radians(elevation_deg)
    return (azimuth_dir[0] / h * math.cos(el), azimuth_dir[1] / h * math.cos(el), math.sin(el))


def sky_rotation(sun: tuple[float, float, float]) -> float:
    """Value of the Sky Texture's sun_rotation that puts the sky's sun on `sun`
    (Cycles places it at (cos(el) sin(rot), -cos(el) cos(rot), sin(el)))."""
    return math.atan2(sun[0], -sun[1])


def light_direction(sun: tuple[float, float, float]) -> tuple[float, float, float]:
    """Direction the sunlight travels (the opposite of the vector toward the sun)."""
    return (-sun[0], -sun[1], -sun[2])


def apply_sky(scene, sun: tuple[float, float, float], strength: float = 1.0, dust: float = 2.5, air: float = 1.0):
    import bpy  # noqa: F401  (only inside Blender)
    world = scene.world
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    sky = tree.nodes.new("ShaderNodeTexSky")
    # Blender 5.0 renamed the Nishita model; fall back to the older name for earlier versions
    types = [item.identifier for item in sky.bl_rna.properties["sky_type"].enum_items]
    sky.sky_type = "MULTIPLE_SCATTERING" if "MULTIPLE_SCATTERING" in types else "NISHITA"
    el = math.asin(max(-1.0, min(1.0, sun[2])))
    sky.sun_elevation = el
    sky.sun_rotation = sky_rotation(sun)
    sky.sun_disc = False
    sky.air_density = air
    for name in ("aerosol_density", "dust_density"):      # renamed in Blender 5.0
        if hasattr(sky, name):
            setattr(sky, name, dust)
            break
    sky.ozone_density = 1.0
    background = tree.nodes.new("ShaderNodeBackground")
    background.inputs["Strength"].default_value = strength
    output = tree.nodes.new("ShaderNodeOutputWorld")
    tree.links.new(sky.outputs["Color"], background.inputs["Color"])
    tree.links.new(background.outputs["Background"], output.inputs["Surface"])


def apply_dof(cam, focus_distance: float, fstop: float = 2.4) -> None:
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = max(0.2, focus_distance)
    cam.data.dof.aperture_fstop = fstop


#: Colour grade applied in the final encode, before the captions are burned
#: in. Deliberately light: the render already carries the colour. A touch of
#: contrast and saturation, a soft bloom on the brightest areas, a gentle
#: vignette and very fine grain. (The black caption band is repainted after
#: this filter by the caption filter, so none of it touches the safe area.)
GRADE_FILTER = (
    # RGB planes (gbrp): eq/noise treat planes 1/2 as chroma and tint the picture,
    # so contrast is a curves S-curve and nothing here is YUV-specific.
    "format=gbrp,curves=all='0/0 0.25/0.23 0.75/0.78 1/1',split[g0][g1];"
    "[g1]curves=all='0/0 0.78/0.78 1/1',gblur=sigma=18[bloom];"
    "[g0][bloom]blend=all_mode=screen:all_opacity=0.10,"
    "vignette=angle=0.35,format=yuv420p"
)
