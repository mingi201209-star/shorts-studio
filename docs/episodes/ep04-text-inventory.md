# EP.04 on-screen text inventory (2026-11-16)

Rule (owner): the film shows real 3D phenomena, not slides. Narration captions stay; no titles, explanation sentences or decorative text; only the minimum label needed to tell compared things apart.
Every text element ever added to EP.04 (code search: `render_crumple_3d.py`, `captions.py`, `assemble_crumple_preview.py`, the scene spec, the workflows) and its class:

| Element | Where | Class | Decision |
|---|---|---|---|
| Narration captions (burned-in, single line, curated phrases <= 24 chars) | `captions.py` -> `film.ass`, rows 1408-1540 | REQUIRED | keep; not changed |
| 3D sign `CRUMPLE` / `RIGID` (one word per car) | comparison segments C, C2, C3 | REQUIRED, minimal (two identical sedans cannot be told apart otherwise) | keep, but shrunk (0.30 -> 0.18) and moved: it used to sit on the caption rows of the lower panel; now it is on the road under each car, rows 340-433 / 1303-1389, inside the mobile safe area (gate `text_safe_area`) |
| Title card / intro text / on-screen explanation sentences | - | never existed in EP.04 | none added |
| Distance/time bars, force arrows, occupant, their value labels | - | OPTIONAL, out of scope (owner) | never implemented, no text |
| Scene-spec `description` / `movement` strings | spec JSON | metadata, not drawn | n/a |

Checked for 'same information without text': the stopping-distance / force idea is carried by the real crush depth and the CRUMPLE/RIGID replay, the hidden structure by the X-ray scan line and folding rails, the protected cabin by the green cell cage that stays unchanged. Nothing was removed that carried information.
Quality gates were not relaxed; `text_safe_area` is a new gate (it fails on the old placement, tested). Voice-off understanding stays NOT_VERIFIED until a person watches the continuous video.
