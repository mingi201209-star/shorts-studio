# EP.06 storyboard v1 (720x1280 renders, Cycles 24 samples)

`storyboard-v1.jpg`, left to right:
1. s01 at 1.15 s: split screen. Top = ABS car, already moving into the left lane. Bottom = locked wheels, skid marks, heading straight for the box.
2. s01 at 1.75 s: top car passes the box (0.62 m gap in the model); bottom car hits it at about 40 km/h (model).
3. s02: locked car, side view, wheel not turning while the car slides (motion only visible in the film).
4. s04: see-through front wheel: brake disc, ABS tone ring (gold teeth), wheel-speed sensor (cyan tip pulses as each tooth passes).
5. s05: caliper close-up: it glows with the brake pressure, which ABS eases and reapplies 10 times a second.

Model (benchmarks/abs_brake/abs_motion.py, gate `abs_physics` PASS): 80 km/h, hard braking at t = 0, the same steering in both cars,
lane change of 2.0 m inside the tyre's friction limit, locked wheels slide straight. Not calibrated to a real car.

Known weak points: the tone ring sits on the outside of the disc for visibility (on real cars it is usually inboard); the caliper is a plain block;
the pads' movement is too small to see at this scale, so the caliper glow shows the pressure instead.
