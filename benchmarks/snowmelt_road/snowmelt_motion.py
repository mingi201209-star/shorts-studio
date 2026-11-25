"""EP.31 snow-melting sprinkler road (pure Python + numpy): Japan's shosetsu pipes (Nagaoka, Niigata, from 1961): a pipe under the
middle of the street feeds a row of nozzles that spray groundwater over the road while it snows. Groundwater in Japan stays about
8-18 C all year; the model uses 12 C (54 F, "around fifty degrees"). Render-world frame: the street runs along +y, its centre
line at x = 0, nozzles every NOZZLE_PITCH m along it.

Physics: the water gives up its warmth cooling to 0 C and that melts the snow landing on the road (latent heat 334 kJ/kg); the
spray rate is the usual design figure per square metre of road. The gate checks the claims in the film: the water's temperature,
that it melts a heavy snowfall as it lands, that the film stays liquid when the air is near freezing (and would not in a much
colder city), how much water a kilometre of street uses, and that the newer closed-pipe design keeps the surface above freezing
with the same heat. Simplified explanation model, not a design guide."""
from __future__ import annotations

import math

C_WATER = 4186.0
L_FUSION = 334000.0
T_WATER = 12.0                          # groundwater (C)
SPRAY = 0.30 / 60.0                     # kg per square metre per second (0.30 L/min/m^2)
ROAD_W = 10.0                           # m of road sprayed across
NOZZLE_PITCH = 3.0
SNOW_RATE_CM_H = 2.5                    # a heavy snowfall (cm of new snow an hour)
SNOW_DENSITY = 100.0                    # kg/m^3 fresh snow
T_AIR_NAGAOKA = 0.5                     # air near freezing while it snows
T_AIR_COLD = -10.0                      # a much colder city
H_AIR = 15.0                            # W/m^2/K heat loss of a wet surface to the air (wind)
PIPE_FLUX = 250.0                       # W/m^2 the newer closed pipes give the pavement


def melt_capacity_cm_h(spray: float = SPRAY, t_water: float = T_WATER) -> float:
    """Fresh snow (cm an hour) the spray can melt: the water's warmth down to 0 C, spent as latent heat."""
    q = spray * C_WATER * t_water                    # W/m^2
    kg_per_s = q / L_FUSION
    return kg_per_s * 3600.0 / SNOW_DENSITY * 100.0


def snow_load_w() -> float:
    """Heat (W/m^2) the falling snow needs to melt."""
    kg_per_s = SNOW_RATE_CM_H / 100.0 * SNOW_DENSITY / 3600.0
    return kg_per_s * L_FUSION


def film_margin(t_air: float) -> float:
    """Heat left over (W/m^2) after melting the snow and losing heat to the air: below zero the film starts to freeze."""
    supply = SPRAY * C_WATER * T_WATER
    loss = H_AIR * max(0.0, 0.0 - t_air)
    return supply - snow_load_w() - loss


def water_per_km_m3_h() -> float:
    return SPRAY * ROAD_W * 1000.0 * 3600.0 / 1000.0


def snowmelt_physics() -> dict:
    problems = []
    t_f = T_WATER * 9 / 5 + 32
    if not 45.0 <= t_f <= 58.0:
        problems.append(f"the water is {t_f:.0f} F (narration: around fifty degrees)")
    cap = melt_capacity_cm_h()
    if not cap >= SNOW_RATE_CM_H:
        problems.append(f"the spray melts {cap:.1f} cm of snow an hour, less than the {SNOW_RATE_CM_H} cm falling")
    if not film_margin(T_AIR_NAGAOKA) > 0:
        problems.append("the water film freezes even with the air near freezing")
    if not film_margin(T_AIR_COLD) < 0:
        problems.append("the film would not freeze in a much colder city")
    w = water_per_km_m3_h()
    if not w > 100.0:
        problems.append(f"a kilometre of street uses only {w:.0f} m^3 an hour")
    if not PIPE_FLUX >= snow_load_w():
        problems.append("the closed pipes do not give the pavement enough heat")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "water_c": T_WATER, "water_f": round(t_f), "spray_l_min_m2": round(SPRAY * 60, 2),
            "melts_cm_per_h": round(cap, 2), "snow_cm_per_h": SNOW_RATE_CM_H, "snow_load_w_m2": round(snow_load_w()),
            "film_margin_near_freezing_w_m2": round(film_margin(T_AIR_NAGAOKA)), "film_margin_cold_city_w_m2": round(film_margin(T_AIR_COLD)),
            "water_per_km_m3_h": round(w), "pipe_flux_w_m2": PIPE_FLUX}


if __name__ == "__main__":
    import json
    print(json.dumps(snowmelt_physics(), indent=1))
