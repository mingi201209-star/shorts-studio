import json
import sys

import pytest

from shorts_studio.cli import main


def _write_pitch(tmp_path, **overrides):
    base = dict(
        topic_id="t1", domain="disaster",
        hook_sentence="1919년, 초당 14미터로 밀려온 당밀 파도가 보스턴 도심을 덮쳐 21명이 죽었습니다.",
        first_second_visual="무너진 거대한 당밀 저장탱크와 거리로 쏟아지는 갈색 파도의 실제 사진",
        familiar_subject="달콤한 시럽, 당밀",
        unexpected_fact="시속 56km 파도가 되어 건물을 부수고 사람을 익사시킨 산업 재해",
        conflict_or_problem="탱크는 완공 직후부터 이음새가 새고 삐걱거렸지만 회사는 계속 방치하며 가동했다",
        mid_change="1919년 1월 15일, 기온이 급등한 오후에 탱크가 폭발하듯 붕괴하며 거리 전체가 당밀에 잠겼다",
        ending_payoff="유가족의 소송 승소가 미국 최초로 기술자 도면에 전문 엔지니어의 서명 날인을 의무화하는 규정으로 이어졌다",
        visual_evidence=["탱크 잔해", "거리", "구조 작업", "고가철도 지지대", "신문 1면", "법원 문서", "건설 당시 사진", "청소 작업"],
        estimated_beats_needed=16,
    )
    base.update(overrides)
    path = tmp_path / "pitch.json"
    path.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    return path


def test_cli_idea_gate_exits_zero_for_a_passing_pitch(tmp_path, monkeypatch, capsys):
    path = _write_pitch(tmp_path)
    monkeypatch.setattr(sys, "argv", ["shorts_studio", "idea-gate", str(path)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "PASS"


def test_cli_idea_gate_exits_nonzero_for_a_failing_pitch(tmp_path, monkeypatch, capsys):
    path = _write_pitch(tmp_path, hook_sentence="안녕하세요! 오늘은 당밀 홍수에 대해 알아보겠습니다.")
    monkeypatch.setattr(sys, "argv", ["shorts_studio", "idea-gate", str(path)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "FAIL"
