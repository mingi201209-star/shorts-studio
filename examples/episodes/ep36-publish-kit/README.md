# EP.36 publish kit: how do you stop a runaway train at the end of the line? (draft; the owner uploads, nothing here uploads)

Series: part five of "Built to Get Hit" (the owner's go-ahead for parts 4-6, 2026-11-27; "시작", 2026-11-28). EP.35 v3 ends with
this film's first shot and "Subscribe for part five: what stops a runaway train?" in Bumper's voice. This film already ends with
part six's teaser from its first build (owner, 2026-11-28: "처음 만들 때부터 예고를 붙여"): EP.37's opening, an elevator full of
people caught by its safety gear, and "Subscribe for part six: what stops a falling elevator?".

Frame 1: a six-car train already shoving a friction buffer stop along the rails at the end of a station track, the buffers
squashed, sparks flying off the shoes, held through the first line. The channel's identity throughout (playbook section 11):
Bumper's voice; Bumper at the train's controls (and, in the comparison, a dummy thrown forward in a car braking hard); the x-ray
reveal on the shoes and buffers with the channel's sting, and a thermal look for the heat; the caption look.

## Title (recommended)
**How Do You Stop a Runaway Train at the End of the Line? 🚆**

Alternatives:
1. This Buffer Stop Is Built to Slide 😳
2. Why Train Buffers Slide Instead of Stopping Dead 🤯

## Description
How do you stop a runaway train at the end of the line? Hitting a solid wall would wreck it, so this buffer stop is built to slide. It's clamped to the rails by steel friction shoes, bolted on tight. When a train hits, its hydraulic buffers squash first, then the whole stop gets shoved along the rails, and the friction turns the train's speed into heat. A six-car train at 15 mph stops in about 60 feet, gentler than slamming on the brakes in your car. Afterwards, crews loosen the bolts, push it back, and tighten them again.

Part 5 of Built to Get Hit. I'm Bumper, the crash-test dummy who narrates this channel.

Simplified animation for explanation; not a specific product, station or train.

#Shorts #Trains #Railway #Engineering #HowItWorks #Physics

## Pinned comment
Would you trust a sliding stop with your train? 👇 Part 6 is next: what stops a falling elevator? 👀

## Upload
- Upload ep05-review/EP36-friction-buffer-stop.mp4 (it already ends with part six's teaser).
- After EP.35 (whose v3 ends with this film's opening), on the steady days; add to the "Built to Get Hit" playlist.
- Related video: the long video "7 Clever Ways Roads Stop Things That Are Out of Control" (LF01), same theme.

## Tags
buffer stop, friction buffer stop, train buffer, end of the line, railway safety, sliding buffer stop, runaway train, hydraulic
buffer, how it works, engineering, Built to Get Hit, Curious Mechanics

## Claims check
- Friction buffer stops absorb a train's energy by sliding: Rawie's "rail brake" design bolts friction grips with bronze inserts to
  the rail head, and its stops convert kinetic energy into heat over a pre-calculated braking distance, the number of friction
  elements worked out for the train (Trackopedia, "Buffer stops"). Rawie developed its energy-absorbing stops after a buffer stop
  accident at Frankfurt am Main in 1902 (Wikipedia, "Buffer stop").
- Oleo's sliding friction buffer stops: friction shoes fitted to the rail profile; when hit, the energy goes through the frame to
  the shoes and the stop slides along the rails, absorbing it; each pair of shoes gives up to 50 kN; combined designs use
  gas-hydraulic buffers with the shoes, the buffers taking low-energy hits without sliding (Oleo data sheets).
- "A six-car train at fifteen miles an hour stops in about sixty feet": Oleo's sliding friction data lists a six-car, 246 t train
  stopping in about 18 m (59 ft) at 25 km/h (15.5 mph), and in about 7 m at 10 km/h (Oleo Buffer Stop Sliding Friction).
- "Gentler than slamming on the brakes in your car": the model's peak is 0.23 g and its average 0.14 g (18 m from 25 km/h).
  Late-model cars with ABS average 0.87-1.08 g in hard stops on dry asphalt and concrete from about 40 mph (Miller et al., SAE
  2023-01-0616). The comparison car is drawn at 0.8 g, the conservative side. Norway's rail authority caps a buffer stop's
  deceleration at 10 m/s2, about 1 g (Bane NOR technical regulations, "Buffer stops").
- "Hitting a solid wall would wreck it": the same train stopped by crushing 0.3 m of its front would take about 8 g.
- Reset: friction stops are re-installed after an impact by loosening the clamping bolts, moving the stop back to its place and
  tightening them again (US patent 5,209,165, "Buffer stop"); stops are checked and readjusted after a collision.
- A first script said the coffee in the cab would not spill; the model showed a cup with 15 mm of headroom would, at the stop's
  0.23 g kick, so the line was replaced before rendering.
- The model (benchmarks/buffer_stop/stop_motion.py) is a simplified explanation model, not a product's test data:
  - a 246 t, six-car train at 25 km/h; a 4.5 t stop with eight pairs of shoes at 40.5 kN each;
  - two gas-hydraulic buffers (spring and oil, capped by the oil's relief pressure, 0.6 m stroke) that squash 0.48 m;
  - it stops in 59 ft (18.0 m) in 5.3 s; the shoes take 98 % of the 5.9 MJ as heat.

## Not verified
The voice and the mix by ear, the cab and car panels at phone size, a human first view.
