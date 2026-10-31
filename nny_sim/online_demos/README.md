# AI 방식 3안 — 실행 데모

세창이 방식을 고를 수 있게, 각 안이 **실제로 돌고 어떻게 진행되는지** 보여주는 데모.
전부 판단 레이어만 쓰고 룰 엔진은 수정하지 않는다. 실행(호스트 PC, zip 원본 전제):

```
cd Desktop\NNY_Simulator
runtime\python.exe -X utf8 <이 폴더>\demo_방식1_복기.py --sim sim
runtime\python.exe -X utf8 <이 폴더>\demo_방식2_모방.py --sim sim
runtime\python.exe -X utf8 <이 폴더>\demo_방식3_가치지도.py --sim sim
```

결과는 바탕화면 `NNY_AI분석\` 에 저장된다. 2026-10-30 실측:
- 방식1: 한 판(73판단) 중 4곳 복기 — 후보별 롤아웃 승률로 1~5순위 매김(마작 타패 순위식)
- 방식2: AI 기보 24판 학습 → 수 일치율 58.5% (7,004판단) — 사람 기보가 쌓이면 같은 코드
- 방식3: 3대진×8판 자기대전 → 덱별 행동 리턴(%p)·콤보 루트 마인드맵(md+json)
