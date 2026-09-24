import pytest
from pydantic import ValidationError
from shorts_studio.models import Project
from shorts_studio.timing import WordTiming, validate_timings
from shorts_studio.subtitles import segment, speech_gap_violations
from shorts_studio.qa import subtitle_qa

def words():
    return [WordTiming("1950년대",0.2,0.7),WordTiming("코멧이",0.72,1.1),WordTiming("등장했습니다",1.12,1.8)]

def test_manifest_validation():
    with pytest.raises(ValidationError): Project(title="x",width=1920,height=1080,scenes=[])

def test_tts_timing_monotonic(): validate_timings(words(),2.0)

def test_caption_uses_real_timestamps():
    c=segment(words(),2.0,lead=0)
    assert c[0].start==pytest.approx(0.2)

def test_caption_negative_timestamp_blocked():
    c=segment([WordTiming("안녕",0.05,0.3)],.4,lead=.2)
    assert c[0].start==0

def test_caption_audio_duration_clamp():
    c=segment([WordTiming("끝",.8,1.0)],1.0)
    assert c[-1].end<=1.0

def test_caption_gap_detection():
    w=words(); c=segment(w,2.0)
    assert speech_gap_violations(c,w)==[]

def test_korean_caption_segmentation():
    w=[WordTiming(str(i),i*.4,i*.4+.3) for i in range(10)]
    assert len(segment(w,4.2))>=2

def test_subtitle_qa(): assert subtitle_qa(segment(words(),2.0),words(),2.0)["status"]=="PASS"
