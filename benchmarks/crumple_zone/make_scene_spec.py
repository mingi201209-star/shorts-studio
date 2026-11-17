import json
beats=[b['narration_en'] for b in json.load(open('./examples/experiments/crumple-zone-speech-plan.json'))['variants'][0]['beats']]
def chk(id,desc,kind,crit,**kw): return {"id":id,"description":desc,"kind":kind,"criterion":crit,**kw}
def subj(sid,names,share=0.8): return chk(f"{sid}-subjects","the named parts are on screen","subjects_in_view","subject_present",subjects=names,value=share)
def noobs(sid): return chk(f"{sid}-not-obscured","the action is not hidden by the captions","not_obscured","not_obscured",metric="caption.overlap",value=0.2)
def mute(sid,text): return chk(f"{sid}-sound-off",text,"manual","sound_off_understandable")
def scene(sid,beat,narr,cue,subjects,kind,desc,onset_metric,onset_thr,cam,effects,checks,expl=False):
    return {"id":sid,"beat":beat,"narration":narr,"cue":cue,"subjects":subjects,"phenomenon":{"kind":kind,"description":desc,"onset_metric":onset_metric,"onset_threshold":onset_thr,"explanation_only":expl},
            "camera":cam,"effects":effects,"success":checks,"silent_readable":True}
S=[]
S.append(scene("s01",1,"Cars are designed to crush.","Cars are designed",["car_front","barrier"],"structure_deformation",
 "A car drives into a rigid barrier at 50 km/h (tracked approach, then slow motion) and its front visibly starts to crush; the first contact is inside the first second",
 "crumple.stroke_m",0.01,{"kind":"K","movement":"tracking shot of the approach, then close on the crushing nose"},["structure_deformation","approach_run_up"],
 [subj("s01",["car_front","barrier"]),
  chk("s01-first-contact","the first contact happens inside the first 1.5 s of the film","onset_within_s","timing",metric="crumple.stroke_m",onset_threshold=0.01,value=1.5),
  chk("s01-crushes","the nose has crushed at least 3 cm by the end of the sentence","metric_reaches","action_performed",metric="crumple.stroke_m",value=0.03),
  chk("s01-no-penetration","the deformed nose never goes through the barrier (<= 5 mm)","metric_at_most","physically_consistent",metric="nose.penetration_mm",value=5.0),
  noobs("s01"),mute("s01","with the sound off a car hits a wall and its front crumples")]))
S.append(scene("s02",2,"Watch the hood buckle and the whole front fold back.","Watch the hood buckle",["car_front"],"structure_deformation",
 "The hood folds upwards and the whole front is pushed back while the crash runs on in slow motion","body.max_rise_m",0.01,{"kind":"K","movement":"close high three-quarter view of the nose"},["structure_deformation"],
 [subj("s02",["car_front"]),
  chk("s02-hood","the hood buckles upwards by at least 5 cm while it is narrated","metric_increase","action_performed",metric="body.max_rise_m",value=0.05),
  chk("s02-front-folds","the crushed depth of the front grows by at least 15 cm while it is narrated","metric_increase","timing",metric="crumple.crushed_depth_m",value=0.15),
  noobs("s02"),mute("s02","with the sound off the hood is seen folding up and the front folding back")]))
S.append(scene("s03a",3,"Hidden rails inside fold like an accordion","Hidden rails inside",["crush_rails","bumper_beam","safety_cell"],"xray_reveal",
 "The body turns into a ghost while the crash is still going on (no replay) and the hidden rails and bumper beam are seen folding","xray.factor",0.02,{"kind":"K","movement":"the camera rises to a high chase view as the scan line passes over the car"},["xray_reveal","structure_folding"],
 [subj("s03a",["crush_rails","bumper_beam"],0.5),
  chk("s03a-ghost","the body becomes see-through (scan line completes)","metric_reaches","action_performed",metric="xray.factor",value=0.99),
  chk("s03a-onset","the reveal starts when the words 'hidden rails' are spoken","onset_near_cue","timing",metric="xray.factor",onset_threshold=0.02,value=0.5),
  chk("s03a-continuous","the crash is still in progress when the reveal starts (same crash, nothing replayed)","metric_increase","physically_consistent",metric="crumple.stroke_m",value=0.03),
  noobs("s03a"),mute("s03a","with the sound off the car turns see-through and the beams inside are seen folding")]))
S.append(scene("s03b",3,"absorbing the crash energy and stretching the stop over a longer distance and time.","absorbing the crash",["crush_rails","bumper_beam"],"structure_folding",
 "The rails keep shortening until the car has stopped: the stop is stretched over a long stroke","rails.shortening_m",0.01,{"kind":"K","movement":"high chase view of the folding rails"},["structure_folding"],
 [subj("s03b",["crush_rails","bumper_beam"],0.7),
  chk("s03b-fold","the rails shorten by at least 15 cm while it is narrated","metric_increase","action_performed",metric="rails.shortening_m",value=0.15),
  chk("s03b-timing","the folding is going on inside the spoken window (the rails keep shortening while it is narrated)","metric_increase","timing",metric="rails.shortening_m",value=0.05,window="scene"),
  chk("s03b-cell-intact","the safety cell does not move (<= 1 mm)","metric_at_most","physically_consistent",metric="cell.max_displacement_mm",value=1.0),
  noobs("s03b"),mute("s03b","with the sound off the beams are seen folding up until the car stops")]))
S.append(scene("s04a",4,"The passenger compartment keeps its shape.","The passenger",["safety_cell","whole_car"],"protected_cell_highlight",
 "With the front fully crushed the whole car is seen with its green safety cell unchanged","cell.highlight",0.5,{"kind":"K","movement":"the camera pulls back to the whole car and starts a slow orbit"},["protected_cell_highlight"],
 [subj("s04a",["safety_cell","whole_car"],0.8),
  chk("s04a-front-crushed","the front is crushed by at least 80 cm of structure while the cell is shown","metric_reaches","action_performed",metric="crumple.crushed_depth_m",value=0.8),
  chk("s04a-cell-intact","the safety cell does not move (<= 1 mm)","metric_at_most","physically_consistent",metric="cell.max_displacement_mm",value=1.0),
  chk("s04a-cage-on","the cage is on screen during the whole sentence","metric_at_least","timing",metric="cell.highlight",value=0.99),
  noobs("s04a"),mute("s04a","with the sound off the crushed front and the intact cabin are seen together")]))
S.append(scene("s04b",4,"The pillars, doors and roof stay where they were.","The pillars, doors",["safety_cell","whole_car"],"protected_cell_highlight",
 "The orbit shows the cabin from other sides: pillars, doors and roof line are exactly where they were","cell.highlight",0.5,{"kind":"K","movement":"slow orbit around the deformed car"},["protected_cell_highlight"],
 [subj("s04b",["safety_cell","whole_car"],0.8),
  chk("s04b-front-still-crushed","the crushed front is still seen (the cabin is compared with it)","metric_reaches","action_performed",metric="crumple.crushed_depth_m",value=0.8),
  chk("s04b-cell-intact","the safety cell does not move (<= 1 mm)","metric_at_most","physically_consistent",metric="cell.max_displacement_mm",value=1.0),
  chk("s04b-cage-on","the cage is on screen during the whole sentence","metric_at_least","timing",metric="cell.highlight",value=0.99),
  noobs("s04b"),mute("s04b","with the sound off the cabin keeps its outline while the front is wrecked")]))
S.append(scene("s05a",5,"Now the same speed and the same wall but a rigid front.","Now the same speed",["rigid_car_front"],"rigid_stop_rebound",
 "A different (blue) car with a rigid front drives into the same wall at the same speed: tracked approach","nose.world_y_m",-7.0,{"kind":"R","movement":"tracking shot of the approach from the same camera start as the first crash"},["rigid_stop_rebound","approach_run_up"],
 [subj("s05a",["rigid_car_front"],0.8),
  chk("s05a-approach","the car closes at least 3 m on the wall while it is narrated","metric_increase","action_performed",metric="nose.world_y_m",value=3.0),
  chk("s05a-onset","the approach starts when the sentence starts","onset_within_s","timing",metric="nose.world_y_m",onset_threshold=-9.0,value=60.0),
  noobs("s05a"),mute("s05a","with the sound off a second, different car drives at the same wall")]))
S.append(scene("s05b",5,"It has almost nothing to crush so it stops almost","almost nothing to crush",["rigid_car_front","barrier"],"rigid_stop_rebound",
 "The rigid front touches the wall and stops within centimetres (same time scale as the first crash)","rigid.stroke_m",0.01,{"kind":"R","movement":"close high three-quarter view of the nose (same pose as the first crash)"},["rigid_stop_rebound"],
 [subj("s05b",["rigid_car_front"],0.8),
  chk("s05b-onset","the rigid car touches the wall when 'nothing to crush' is spoken","onset_near_cue","timing",metric="rigid.stroke_m",onset_threshold=0.01,value=0.6),
  chk("s05b-short","the rigid car crushes by less than 6 cm","metric_at_most","action_performed",metric="rigid.stroke_m",value=0.06),
  chk("s05b-no-penetration","the nose never goes through the barrier (<= 5 mm)","metric_at_most","physically_consistent",metric="nose.penetration_mm",value=5.0),
  noobs("s05b"),mute("s05b","with the sound off the blue car stops dead at the wall")]))
S.append(scene("s05c",5,"instantly and the car bounces back.","instantly and the car",["rigid_car_front"],"rigid_stop_rebound",
 "After the stop the car moves back away from the wall (simulated rebound) and the camera follows it","rigid.rebound_m",0.05,{"kind":"R","movement":"the camera follows the car as it moves away from the wall"},["rigid_stop_rebound"],
 [subj("s05c",["rigid_car_front","barrier"],0.6),
  chk("s05c-rebound","the car moves back at least 1 m from the wall while it is narrated","metric_reaches","action_performed",metric="rigid.rebound_m",value=1.0),
  chk("s05c-speed","it leaves the wall at a readable speed (>= 1 m/s on screen)","metric_reaches","physically_consistent",metric="rigid.speed_away_mps",value=1.0),
  chk("s05c-onset","the bounce is under way when 'bounces back' is spoken","onset_within_s","timing",metric="rigid.rebound_m",onset_threshold=0.05,value=90.0),
  noobs("s05c"),mute("s05c","with the sound off the car is seen bouncing back from the wall")]))
S.append(scene("s06a",6,"The front is meant to deform.","The front is meant",["car_front"],"structure_deformation",
 "Back to the first car, stopped: the front is seen crushed (no replay of the crash)","final_pose.front_crush_m",0.5,{"kind":"C","movement":"cut to the first car at rest, slow move over the crushed front"},["structure_deformation"],
 [subj("s06a",["car_front"],0.8),
  chk("s06a-crushed","the crushed front is on screen","metric_reaches","action_performed",metric="final_pose.front_crush_m",value=0.8),
  chk("s06a-onset","the closing view starts when the sentence starts","onset_near_cue","timing",metric="final_pose.front_crush_m",onset_threshold=0.5,value=0.5),
  noobs("s06a"),mute("s06a","with the sound off the wrecked front of the first car is shown")]))
S.append(scene("s06b",6,"The cabin isn't.","The cabin isn't.",["safety_cell"],"protected_cell_highlight",
 "The body turns see-through and the green cage shows the cabin unchanged","cell.highlight",0.5,{"kind":"C","movement":"slow push towards the cabin as the scan line passes"},["protected_cell_highlight","xray_reveal"],
 [subj("s06b",["safety_cell"],0.6),
  chk("s06b-cage","the see-through body shows the cage (scan line completes)","metric_reaches","action_performed",metric="xray.factor",value=0.99),
  chk("s06b-cell-intact","the safety cell does not move (<= 1 mm)","metric_at_most","physically_consistent",metric="cell.max_displacement_mm",value=1.0),
  chk("s06b-onset","the cage appears when 'the cabin' is spoken","onset_near_cue","timing",metric="cell.highlight",onset_threshold=0.5,value=1.0),
  noobs("s06b"),mute("s06b","with the sound off the cage shows the cabin untouched")]))
spec={"episode":"ep04-crumple-zone","title":"This Car Is Designed to Crush.","target_seconds":32.0,"narration":beats,"scenes":S,
 "assumptions":["Scope (owner, 2026-11-16/17): no on-screen text except the narration captions; no bars, arrows or occupant; X-ray only where the rails are hidden (continuing the same crash, never a replay); the two crashes are shown once each, one after the other, full screen.",
  "The film is slow motion with a changing time scale (run-up at real speed, crash roughly 200x slower, bounce at a readable speed); both cars use the same crush time scale. Illustrative simulation, not a calibrated crash test; stated in the description file, not on screen.",
  "Gates and thresholds of the earlier spec (cell <= 1 mm, no penetration, rigid stroke <= 6 cm, captions not obscured) are kept; checks that depended on the old structure were replaced by the checks above."]}
json.dump(spec,open('./examples/episodes/ep04-crumple-zone-scene-spec.json','w'),indent=1,ensure_ascii=False)
print(len(S),'scenes')
