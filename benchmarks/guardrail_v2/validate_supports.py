"""Audit splice bolts against the actual deformed beam, not stored metadata."""
import bpy
from mathutils import Vector


def support_errors(scene, rail):
    bolts = [o for o in scene.objects if o.name.startswith('W-beam splice bolt head')]
    if len(bolts) != 24:
        return [{'frame': 0, 'check': 'SUPPORT_BOLTS_MISSING', 'value': len(bolts)}], []
    keys = rail.data.shape_keys.key_blocks
    basis = keys[0]
    columns = sorted({round(v.co.x, 4) for v in basis.data})
    dx = columns[1] - columns[0]
    nz = len(basis.data) // len(columns)
    posts = [o for o in scene.objects if o.name.startswith('Steel support post ')]
    if len(posts) != 12:
        return [{'frame': 0, 'check': 'SUPPORT_POSTS_MISSING', 'value': len(posts)}], []
    scene.frame_set(scene.frame_start)
    bpy.context.view_layer.update()
    feet = []
    for post in posts:
        low = min(v.co.z for v in post.data.vertices)
        for index, vertex in enumerate(post.data.vertices):
            if abs(vertex.co.z-low) < 1e-6:
                feet.append((post, index, post.matrix_world @ vertex.co))
    errors, frames = [], []
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        points = [v.co.copy() for v in basis.data]
        for key in keys[1:]:
            if key.value:
                for idx, point in enumerate(points):
                    point += (key.data[idx].co-basis.data[idx].co)*key.value
        points = [rail.matrix_world @ p for p in points]
        gaps = []
        for bolt in bolts:
            centre = sum((bolt.matrix_world @ v.co for v in bolt.data.vertices), Vector()) / len(bolt.data.vertices)
            # Interpolate longitudinally: the 10 cm grid must not inflate the
            # tolerance at post stations that fall between rail columns.
            i = max(0, min(len(columns)-2, int((centre.x-columns[0])/dx)))
            alpha = max(0., min(1., (centre.x-columns[i])/dx))
            section = [points[i*nz+j].lerp(points[(i+1)*nz+j], alpha) for j in range(nz)]
            # Include the corrugation segments, not just sampled vertices.
            distances = []
            for a, b in zip(section, section[1:]):
                edge = b-a
                t = max(0., min(1., (centre-a).dot(edge)/edge.length_squared))
                distances.append((centre-(a+t*edge)).length)
            gap = min(distances)
            gaps.append(gap)
            if gap > .025:
                errors.append({'frame': frame, 'check': 'SUPPORT_BOLT_DETACHED', 'value': [bolt.name, round(gap, 6)]})
        foot_shift = 0.
        for post, index, initial in feet:
            point = post.data.vertices[index].co.copy()
            shape_keys = post.data.shape_keys
            if shape_keys:
                basis_post = shape_keys.key_blocks[0]
                for key in shape_keys.key_blocks[1:]:
                    if key.value:
                        point += (key.data[index].co-basis_post.data[index].co)*key.value
            foot_shift = max(foot_shift, (post.matrix_world @ point-initial).length)
        if foot_shift > .001:
            errors.append({'frame': frame, 'check': 'POST_SOIL_ANCHOR_MOVED', 'value': round(foot_shift, 6)})
        frames.append({'frame': frame, 'max_bolt_rail_gap_m': round(max(gaps), 6), 'max_soil_foot_shift_m': round(foot_shift, 6)})
    return errors, frames
