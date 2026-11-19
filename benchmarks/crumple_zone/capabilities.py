"""What the EP.04 renderer can do today. A scene that needs anything marked False cannot go to a full render (shorts_studio.scene_spec.pipeline)."""
CAPABILITIES = {
    "structure_deformation": True,      # crush_map applied to the sedan mesh (hood buckle, fender bulge), front wheels pushed back, cell untouched
    "xray_reveal": True,                # scan-line ghost body, mid-crash (no replay)
    "structure_folding": True,          # crush rails and bumper beam folded by the same map
    "protected_cell_highlight": True,   # the cabin turns see-through after the front (no box); cell displacement is measured from the deformed geometry
    "rigid_stop_rebound": True,         # the rigid-front car stops in centimetres and the simulated rebound is shown (sequential, full screen, same camera start)
    "approach_run_up": True,            # tracked approach to the barrier before contact
    "two_situation_comparison": True,   # kept for older specs: sequential, never split screen
    "distance_time_bars": False,        # OUT OF SCOPE (owner): optional, no scene uses it
    "force_arrows": False,              # OUT OF SCOPE (owner)
    "restraint_occupant": True,         # the driver as a crash-test-dummy style figure (owner request 2026-11-18): belt/steering-wheel loading from the simulated pulse, green to red by chest load; illustrative, not calibrated
}
