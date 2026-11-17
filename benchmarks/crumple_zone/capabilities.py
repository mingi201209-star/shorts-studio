"""What the EP.04 renderer can do today. A scene that needs anything marked False cannot go to a full render (shorts_studio.scene_spec.pipeline)."""
CAPABILITIES = {
    "structure_deformation": True,      # crush_map applied to the sedan mesh, front wheels pushed back, cell untouched
    "xray_reveal": True,                # scan-line ghost body
    "structure_folding": True,          # crush rails and bumper beam folded by the same map
    "two_situation_comparison": True,   # sequential full-screen CRUMPLE and RIGID, same speed, mass, barrier
    "protected_cell_highlight": True,   # green safety-cell cage; cell displacement is measured from the deformed geometry
    "distance_time_bars": False,  # OUT OF SCOPE for EP.04 (owner 2026-11-16): optional, no scene uses it;        # 3D bars for stopping distance and time: not implemented yet
    "force_arrows": False,  # OUT OF SCOPE for EP.04 (owner 2026-11-16): optional, no scene uses it;              # 3D average-force arrows: not implemented yet
    "restraint_occupant": False,  # OUT OF SCOPE for EP.04 (owner 2026-11-16): optional, no scene uses it;        # occupant + belt + airbag explanatory model: not implemented yet
}
