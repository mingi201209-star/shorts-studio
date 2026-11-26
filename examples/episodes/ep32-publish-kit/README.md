# EP.32 publish kit: the truck that's built to get hit (draft; the owner uploads, nothing here uploads)

Owner brief 2026-11-26: "숏폼으로 만들어" (make Shorts), after the retention plan ("make people like the videos, keep watching and
look forward to the next one"). Topic in the shape of the two best Shorts (EP.21 rockfall net, EP.13 guardrail end): a big piece of
road hardware catching something huge by giving way. Frame 1: a red car already crushing into the yellow crash cushion on the back
of an orange work truck parked in the lane, torn aluminum and bumper plastic flying, held through the first line. Comment hooks: "why
would anyone park in the lane", the honeycomb, "39 times".

First Short made under the retention plan (docs/episode-playbook.md section 9):
- the signature reveal: line 4 opens the cushion from the back, straight into the honeycomb, then slides the three blocks apart;
  the channel's sting (benchmarks/signature_sting.py) lands on that cut, the same sound in every Short from now on;
- the end punch: the last line is the surprising number (39 hits in one state in under eight months);
- the next-episode teaser: in the pinned comment (below), so the Short's loop stays intact.

## Title (recommended)
**The Truck That's Built to Get Hit 🚧**

Alternatives:
1. Why Road Crews Park a Truck in Your Lane 😳
2. This Truck Wants You to Crash Into It 🤯

## Description
Why would road crews park a truck right in your lane? It's a shield between traffic and the workers. On its back is a crash cushion full of aluminum honeycomb that crushes row by row, so a car slows down over about eight feet instead of hitting solid steel. They're built to stop a 5,000-pound pickup at 62 mph.

Simplified animation for explanation; no real crash test, product or agency is shown.

#Shorts #RoadSafety #Engineering #WorkZone #Physics #HowItWorks

## Pinned comment
Have you ever seen one of these trucks on the highway? Next: what stops a giant ship from knocking down a bridge 👀

(Change the "Next:" half if the next upload is a different topic.)

## Upload
- Related video: the long video "7 Clever Ways Roads Stop Things That Are Out of Control" (LF01), same theme.
- Keep the upload days steady (owner plan 2026-11-26: for example Shorts Mon/Wed/Fri, US evening).

## Tags
truck mounted attenuator, TMA, crash cushion, shadow vehicle, work zone safety, highway work zone, aluminum honeycomb, crash test,
how it works, road safety engineering, Curious Mechanics

## Claims check
- Road crews park a protective (shadow) truck in the closed lane upstream of the workers on purpose, so an errant vehicle hits it
  instead of them; its crash cushion is a truck-mounted attenuator (TMA). A TMA's cartridge holds energy absorbers such as aluminum
  honeycomb, steel crush members or elastomers, mounted on the truck; this film shows the honeycomb kind. Units fold up for travel
  and lower behind the truck in the work zone. (IMSA work zone study guide, TMAs and shadow vehicles:
  https://open-exam-prep.com/study-guides/imsa-work-zone/ch6/tmas-shadow-vehicles)
- Test level 3 TMAs are evaluated for impacts at up to 62 mph (100 km/h); the basic TMA tests are head-on at 100 km/h with a small
  car and a pickup (NCHRP 350 tests 3-50 and 3-51: 820 kg car, 2,000 kg pickup; FHWA eligibility letters, e.g.
  https://highways.dot.gov/safety/rwd/reduce-crash-severity/hardware-eligibility-letters/safety-eligibility-letter-cc-78). MASH,
  required for TMAs bought after 2019 in for example Minnesota (https://dot.state.mn.us/products/temporarytrafficcontrol/truck-trailer-attenuators.html),
  uses the 1100C car and the 2270P pickup (5,000 lb) at the same 62 mph: "built to stop a five-thousand-pound pickup at sixty-two
  miles an hour".
- "In one state, drivers hit thirty-nine of them in under eight months": MoDOT reported 39 truck- or trailer-mounted attenuators hit
  in Missouri work zones by late August 2020, against 19 at the same point of 2019 (MoDOT, reported by the National Work Zone Safety
  Information Clearinghouse: https://workzonesafety.org/publication/missouri-dot-experiencing-surge-in-work-zone-crashes/ and AASHTO
  Journal).
- The truck rolling forward after a hit is real (the roll-ahead the crew's buffer space is chosen for; one test recorded 4.1 m):
  the film's few feet come from the model below.
- The model (benchmarks/attenuator_truck/tma_motion.py): a 1,400 kg car at 62 mph into three honeycomb blocks crushing at 120, 200
  and 380 kN (back to front) on a 22,000 lb truck braked at 0.40 of its weight: the car crushes 8.0 ft of the 10.5 ft stroke in
  0.14 s and the truck is shoved 4.6 ft; the 5,000 lb pickup crushes 10.1 ft and stops inside the stroke. A simplified explanation
  model, not a crash-test simulation or a product's data.

## Not verified
The sound mix and voice by ear, readability with the sound off, a human first view.
