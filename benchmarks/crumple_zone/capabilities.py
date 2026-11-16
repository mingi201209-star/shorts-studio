"""What the EP.04 renderer can do today. A scene that needs anything marked False cannot go to a full render (shorts_studio.scene_spec.pipeline)."""
CAPABILITIES = {
    "structure_deformation": True,      # crush_map applied to the sedan mesh, front wheels pushed back, cell untouched
    "xray_reveal": True,                # scan-line ghost body
    "structure_folding": True,          # crush rails and bumper beam folded by the same map
    "two_situation_comparison": True,   # CRUMPLE / RIGID stack, same speed, mass, barrier
    "protected_cell_highlight": True,   # green safety-cell cage; cell displacement is measured from the deformed geometry
    "distance_time_bars": False,        # 3D bars for stopping distance and time: not implemented yet
    "force_arrows": False,              # 3D average-force arrows: not implemented yet
    "restraint_occupant": False,        # occupant + belt + airbag explanatory model: not implemented yet
}
