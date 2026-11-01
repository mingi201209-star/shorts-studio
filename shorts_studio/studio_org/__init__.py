"""Shorts Studio organizational structure, as code.

Five departments, each with named divisions, connected by one shared Task
record (see task.py) instead of five separate silos. This module does not
replace or rewrite the existing render/QA engine (shorts_studio.factory,
benchmarks/road_safety/curious_mechanics_*); departments call into those real
functions where a connection already exists, and are explicit (via
NotImplementedError) where a real connection would require live rendering or
publishing that this minimal structure does not perform yet.

    기획부 (Planning):   소재조사 · 대본구성 · 장면설계
    렌더부 (Render):     자산 · 동작 · 촬영 · 렌더실행
    편집부 (Editing):    컷편집 · 음향 · 자막
    평가부 (Evaluation): 기술검수 · 대본화면일치 · 성과분석
    관리부 (Management): 작업통제 · 자원관리 · 기록복구

Technical QA, script/screen-content evaluation, and real publishing
performance are three distinct judgments (see departments/evaluation.py) and
are never collapsed into one pass/fail. Performance is always reported
UNVERIFIED here, because this project does not publish publicly.
"""
