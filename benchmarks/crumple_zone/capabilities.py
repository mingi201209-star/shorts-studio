"""What the EP.04 renderer can do today. A scene that needs anything marked False cannot go to a full render (shorts_studio.scene_spec.pipeline)."""
CAPABILITIES = {
    "structure_deformation": True,      # crush_map applied to the sedan mesh (hood buckle, fender bulge), front wheels pushed back, cell untouched
    "xray_reveal": True,                # scan-line ghost body, mid-crash (no replay)
    "structure_folding": True,          # crush rails and bumper beam folded by the same map
    "protected_cell_highlight": True,   # green safety-cell cage; cell displacement is measured from the deformed geometry
    "rigid_stop_rebound": True,         # the rigid-front car stops in centimetres and the simulated rebound is shown (sequential, full screen, same camera start)
    "approach_run_up": True,            # tracked approach to the barrier before contact
    "two_situation_comparison": True,   # kept for older specs: sequential, never split screen
    "distance_time_bars": False,        # OUT OF SCOPE (owner): optional, no scene uses it
    "force_arrows": False,              # OUT OF SCOPE (owner)
    "restraint_occupant": False,        # OUT OF SCOPE (owner)
}
