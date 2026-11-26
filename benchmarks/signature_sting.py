"""The channel's signature cut-away sting (owner plan 2026-11-26: "make people look forward to the next video"): every Short from EP.32
on has one shot where the device is opened up to show its hidden mechanism, and this same sound marks that moment every time, so it
becomes the channel's recognisable beat. A short airy rise into a bright metallic "shing" with a soft low thump under it; the shing
lands on the cut. Pure numpy, deterministic (fixed seed): the same samples in every episode."""
from __future__ import annotations

import numpy as np

SR = 48000
RISE_S = 0.32            # the rise runs this long before the cut; place the sting at (cut time - RISE_S)


def reveal_sting(sr: int = SR) -> np.ndarray:
    rng = np.random.default_rng(20261126)
    rise_n, tail_n = int(RISE_S * sr), int(0.9 * sr)
    n = rise_n + tail_n
    t = np.arange(n) / sr
    out = np.zeros(n)
    # the rise: noise brightening towards the cut (a moving one-pole low-pass)
    noise = rng.standard_normal(rise_n)
    y, acc = np.zeros(rise_n), 0.0
    for i in range(rise_n):
        k = 0.02 + 0.5 * (i / rise_n) ** 2
        acc += k * (noise[i] - acc)
        y[i] = acc
    out[:rise_n] = y * np.linspace(0.0, 1.0, rise_n) ** 2 * 0.5
    # the shing: a few inharmonic metal partials with a fast attack and a ringing decay
    tt = t[rise_n:] - t[rise_n]
    shing = sum(a * np.sin(2 * np.pi * f * tt + ph) * np.exp(-tt / d)
                for f, a, d, ph in ((1567.0, 0.55, 0.32, 0.0), (2349.0, 0.35, 0.22, 1.1), (3135.0, 0.22, 0.14, 2.3), (4699.0, 0.12, 0.08, 0.4)))
    shing *= np.minimum(1.0, tt / 0.003)
    thump = np.sin(2 * np.pi * (70.0 * tt + 30.0 * (1 - np.exp(-tt / 0.05)))) * np.exp(-tt / 0.12) * 0.6
    out[rise_n:] += shing + thump
    return out / (np.max(np.abs(out)) + 1e-9)
