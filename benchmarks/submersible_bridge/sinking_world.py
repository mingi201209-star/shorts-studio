"""EP.27 world layout (pure numpy), in sinking_motion's frame: the canal runs along +y, the water surface is z = 0, the road crosses
along x at y = 0 on quays 1.2 m above the water. Toward -y the canal opens between two breakwaters into the sea; toward +y it cuts
deeper and deeper into the limestone (walls rising to about 50 m). At the bridge the channel widens into a chamber between vertical
concrete quays (x = +-16.6) where the 33 m deck sits; a pit in the bed takes its girders when it is down."""
from __future__ import annotations

import numpy as np

from benchmarks.submersible_bridge import sinking_motion as sm

QUAY_X = 16.6                            # chamber walls at the bridge
CHAMBER_Y = 6.0                          # the chamber runs |y| < CHAMBER_Y, then narrows to the canal
CANAL_HW = sm.CANAL_W / 2                # 12.3 at the waterline
ROAD_Z = sm.Z_UP
MOLE_Y = -70.0                           # the breakwaters end here; the open sea beyond
PIT_Y = sm.DECK_W / 2 + 0.25


def smooth(e0, e1, x):
    u = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def noise2(x, y, seed=0.0):
    return (0.5 * np.sin(0.21 * x + 0.7 + seed) * np.sin(0.17 * y + 1.1 * seed) + 0.3 * np.sin(0.6 * x + 1.3 * y + 2.0 + seed)
            + 0.2 * np.sin(1.7 * x - 0.9 * y + 4.0 + 2 * seed))


def canal_half_width(y):
    y = np.asarray(y, float)
    a = np.abs(y)
    hw = np.where(a <= CHAMBER_Y, QUAY_X, QUAY_X + (CANAL_HW - QUAY_X) * smooth(CHAMBER_Y, CHAMBER_Y + 6.0, a))
    return np.where(y < MOLE_Y, CANAL_HW + (-MOLE_Y + y) * -0.0, hw)


def wall_slope(y):
    """How steep the channel's sides are: near-vertical concrete quays at the bridge, steep rock in the cut."""
    a = np.abs(np.asarray(y, float))
    return 40.0 + (6.0 - 40.0) * smooth(14.0, 22.0, a)


def land_level(x, y):
    """The land surface away from the canal: flat 1.2 m quays and coast at the bridge, rising inland, dropping into the sea."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    inland = 50.0 * smooth(25.0, 190.0, y) + 25.0 * smooth(300.0, 1400.0, y) * (0.6 + 0.4 * noise2(x * 0.004, y * 0.004, 1.0))
    hills = 60.0 * smooth(160.0, 900.0, np.abs(x)) * smooth(-300.0, 200.0, y) * (0.7 + 0.3 * noise2(x * 0.003, y * 0.003, 2.0))
    flat = 1.0 - smooth(18.0, 40.0, np.abs(y)) * smooth(-1.0, 1.0, y)                      # the flat quays around the bridge
    rough = (1.0 - flat) * (1.6 * noise2(x * 0.05, y * 0.05, 3.0) + 0.5 * noise2(x * 0.3, y * 0.3, 4.0)) * smooth(30.0, 60.0, np.abs(x) + np.maximum(y, 0))
    z = ROAD_Z + inland + hills + rough
    sea = smooth(-45.0, -130.0, y) * (1.0 - smooth(40.0, 25.0, np.abs(x)) * 0.0)
    shore = ROAD_Z - 1.2 - 16.0 * smooth(-45.0, -160.0, y)
    mole = (np.abs(np.abs(x) - 20.0) < 6.0) & (y > MOLE_Y) & (y < -30.0)                  # breakwaters along the canal mouth
    z = np.where(sea > 0, z * (1 - sea) + shore * sea, z)
    z = np.where(mole, np.maximum(z, ROAD_Z + 0.3), z)
    return z


def ground_z(x, y):
    """The land with the canal cut into it (and the pit for the deck's girders under the bridge)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    hw = canal_half_width(y)
    channel = np.maximum(sm.CANAL_BED, (np.abs(x) - hw) * wall_slope(y))
    z = np.minimum(land_level(x, y), channel)
    pit = (np.abs(x) < QUAY_X - 0.05) & (np.abs(y) < PIT_Y)
    return np.where(pit, sm.PIT, z)


def surface_kind(x, y):
    """Per point: 'quay' concrete, 'cliff' rock, 'bed' sand, 'beach' sand, 'land' dry scrub (for the material)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    z = ground_z(x, y)
    land = land_level(x, y)
    hw = canal_half_width(y)
    on_wall = (z < land - 0.05) & (z > sm.CANAL_BED + 0.05) & (np.abs(x) > hw - 3.0)
    quay = on_wall & (np.abs(y) < 16.0)
    cliff = on_wall & ~quay
    bed = z <= sm.CANAL_BED + 0.05
    beach = (~on_wall) & (~bed) & (y < -35.0) & (z < 3.0)
    return quay.astype(float), cliff.astype(float), bed.astype(float), beach.astype(float)
