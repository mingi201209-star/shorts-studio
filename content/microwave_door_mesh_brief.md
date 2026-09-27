# Microwave door mesh — production brief

Baseline: main@47c22dcd26d1b5c88c5c6da148e6ec77928b7b91

## Single improvement for this video
Tighter story pacing only. Do not change stable engine behavior, visual cadence rules, subtitle layout, or QA thresholds.

## Topic
전자레인지 문에는 왜 검은 점들이 붙어 있을까?

## Narrative
0–2s: 전자레인지 문에 붙은 검은 점들은 장식이 아닙니다.
2–5s: 안은 보이는데, 전자레인지의 마이크로파는 밖으로 거의 빠져나오지 못합니다.
Build: 문 안쪽의 금속 망에는 아주 작은 구멍들이 촘촘하게 뚫려 있습니다. 가시광선의 파장은 이 구멍보다 훨씬 짧아서 눈까지 통과할 수 있지만, 전자레인지가 사용하는 마이크로파의 파장은 훨씬 길어서 이 촘촘한 금속 구조를 쉽게 통과하지 못합니다. 그래서 우리는 음식이 돌아가는 모습은 볼 수 있으면서 마이크로파는 금속 챔버 안에 가둘 수 있습니다.
Ending: 우리가 보는 검은 점들은 시야를 남겨두면서 마이크로파를 막는 금속 차폐 구조의 일부입니다.

## Visual states
1. 실제 전자레인지 문 전체 + 점무늬 위치 강조.
2. 문 단면: 유리/금속 메시/조리실의 관계.
3. 메시 구멍 확대 + 가시광선이 통과하는 표현.
4. 같은 메시에서 긴 파장의 마이크로파가 차폐되는 표현.
5. 빛과 마이크로파의 파장 규모 차이를 직관적으로 비교.
6. 최종 실물 문으로 돌아와 '보이지만 마이크로파는 가둔다'를 결론으로 연결.

Every visual change must add new semantic information. Reframing/crop/zoom/pan/rotation of the same image does not count as a state change.

## Production rules
- No greeting or preview.
- Do not pad to a duration target; end when the explanation is complete.
- Keep factual wording conservative: the perforated conductive screen attenuates microwave leakage; do not claim absolute zero leakage.
- Preserve black surround, central visual area, title/subtitle safe areas, and no subtitle/image overlap.
- Do not weaken existing semantic or meaningful-visual-change gates.
- Full regression, manifest validation, real CI production render, and human frame review are required.
- Never upload to YouTube automatically. Deliver the final MP4 for manual upload only.