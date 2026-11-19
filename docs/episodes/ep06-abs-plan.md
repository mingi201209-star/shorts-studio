# EP.06 plan: why ABS lets you steer while braking (DRAFT v1, nothing built)

Channel "Curious Mechanics": weekly English 9:16 Short, about 25 s, 100% 3D, captions only.
Built on the EP.05 retention finding: the film opens on the comparison itself (split screen from frame 1).

## Why this topic
- A comparison that reads in one frame: same car, same speed, same hard stop, an obstacle ahead.
  Top: ABS car steers around it. Bottom: locked wheels, the car slides straight on.
- Same "designed to" framing as the best Short: the brakes are designed to let go on purpose.
- Reuses the car, road and crash assets of EP.03/EP.04.

## Claims (kept qualitative and true)
1. Without ABS, a hard stop can lock the wheels. A sliding tyre cannot steer, so the car keeps going straight.
2. ABS measures each wheel's speed. When a wheel starts to lock, it briefly releases the brake pressure and then reapplies it, many times a second.
3. The tyres keep rolling, so they can still grip and turn.
4. The pulsing felt in the brake pedal is ABS working.

Not claimed: no stopping-distance claim (ABS is not always shorter, e.g. on gravel or deep snow), no numbers from a real car, no brand.

## Narration draft v1 (about 62 words, about 24 s; not final until the owner approves)
1. Same emergency stop. Only one car can still steer.
2. Without ABS, slam the brakes and the wheels lock.
3. A sliding tire can't steer, so the car goes straight.
4. ABS watches how fast every wheel is turning.
5. The moment one starts to lock, it eases the brake, then squeezes again,
6. many times a second.
7. So the tires keep rolling, and they can still turn.
8. That buzz in the pedal? That's ABS working.

## Scene list
| id | narration | picture |
|---|---|---|
| s01 | 1 | Split screen from frame 1: both cars already braking toward a box on the road. Top swerves around it, bottom slides straight into it by 1.5 s |
| s02 | 2 | Bottom car, low side view: wheel stops turning (spoke marks frozen) while the car still moves; tyre smoke streak |
| s03 | 3 | Top view of the bottom car: front wheels turned, car still travelling straight |
| s04 | 4 | Inside the top car's wheel: toothed ring and speed sensor, ring spinning |
| s05 | 5-6 | Brake caliper on the disc: pads clamp, release, clamp (pressure glow pulses), wheel keeps turning |
| s06 | 7 | Top car from above: wheels turned, car follows them around the box |
| s07 | 8 | Driver's foot on the pedal, pedal vibrating; cut back to the opening split screen (loop) |

## Gates (reused + new)
- Reused from EP.05: split_opening (both halves at the same simulated time), scene alignment to real cues, smoothness, captions at the film fps, no scene text, black opening, frozen audio.
- New `abs_physics`: locked wheel has zero rotation while the car moves; ABS wheel slip stays under the threshold; locked car's heading does not follow the steering input; ABS car's does.

## Steps
1. Owner approves the narration (change words now, not after the voice is recorded).
2. Storyboard stills for s01, s04, s05.
3. Frozen audio, whole-film preview with every gate, publish kit.
