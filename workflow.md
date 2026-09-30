# workflow.md — 작업 진척 기록

모든 세션은 작업 전에 이 파일을 확인하고, 작업 후 갱신한다 (CLAUDE.md R4).
원본은 `default` 브랜치의 이 파일이다.

마지막 갱신: 2026-09-30

## 현재 상태 요약

- 저장소 규정 체계(CLAUDE.md · 세션 시작 훅 · workflow.md) 구축 완료.
- PR #3 ~ #8 모두 계열 기준 브랜치에 머지 완료 (2026-09-30, 「Create a merge commit」 방식). **`main` 에는 미반영** (사용자 지시).
  - `model/main` = nny_sim 코드 최신 (#3 원본 + #5 규칙 명세서 반영 + #7 결착 우선 + #8 R1 수정)
  - `data/main` = nny_sim 데이터 최신 (#4 원본 + #6 전략 덱 20장)
  - 두 브랜치는 같은 `nny_sim/` 폴더에 겹치지 않는 파일을 담는다. 실행하려면 둘 다 필요 (합쳐도 충돌 없음 확인, 7개 덱 21매치 스모크 오류 0).
- `model/main` · `data/main` 은 `main` 에서 분기함 (사용자 지시: main에 연결).
- 규칙 명세서 파일 자체는 저장소에 없음(업로드 파일로만 받음). 코드 주석의 §번호가 이 문서를 가리킴.
- zip의 문서 `.md` 8개(README, 규칙명세, 보고서, 기보 등)는 아직 저장소에 없음.
- 코드 해설서(.docx)를 만들어 사용자에게 전달함(저장소에는 올리지 않음).

## 완료

| 날짜 | 작업 | 브랜치 · 결과 |
| --- | --- | --- |
| 2026-09-29 | CLAUDE.md 작성 (R1 main 보호, R2 역할별 브랜치, R3 외부 업로드 제한) | `default` → PR #1로 `main` 머지 |
| 2026-09-29 | nny_sim 코드 해설서 작성 (파일 · 클래스 · 아키텍처 + 코드 리뷰 18건) | 파일로 전달 (저장소 미반영) |
| 2026-09-29 | 세션 시작 훅, R0 · R2 개정 · R4 추가, workflow.md 생성 | `default` |
| 2026-09-29 | main에 훅과 새 규정 반영 (workflow.md 제외) | `config/sync-rules-to-main` → PR #2로 `main` 머지 |
| 2026-09-29 | 계열 기준 브랜치 `model/main` · `data/main` 생성 (`main` 에서 분기) | `model/main`, `data/main` |
| 2026-09-29 | nny_sim 코드 36개(.py 35 + builder_template.html) PR | `model/add-nny-sim-code` → PR #3 (`model/main`) |
| 2026-09-29 | nny_sim 데이터 41개(card_pool.json, decks/, learned/, 덱_등록기.html) PR | `data/add-nny-sim-data` → PR #4 (`data/main`) |
| 2026-09-30 | 규칙 명세서 기준 코드 수정 (종료 단계 [유언], [전투] 조건, 공유 존 마커, 제외 존 앞면, 덱 지정 제외, 1턴 1회 · 무효, 강제/임의, 「필드의 카드」 양쪽, 전략 덱 20장 등). 스모크 4,200판 오류 0 | `model/align-rules-spec` → PR #5 (base: `model/add-nny-sim-code`) |
| 2026-09-30 | PR #5 질문 7건 사용자 재정 반영: 수비 표시 공격 불가 유지, 턴 상한 · HP 판정 제거(1000턴 안전장치만), 전략 덱 방침 20장, 덱 미지정 제외는 문장 주어가 선택, 공유 존 마커는 처음 놓은 쪽 → 이후 비어도 유지 · 규칙대로 뒤집힘, AI에 제물 · 수비 소환 · 표시 형식 변경 · 전략 덱 스킬 교체 추가, 일반 · 지속 마법은 자신 턴 · 체인 없음 | `model/align-rules-spec` 2번째 커밋 → PR #5 |
| 2026-09-30 | 제물은 자신 필드의 몬스터만(재정). 레시피 학습기 채우기 모드: 후보를 「기여도 최저 카드와 1장 바꾼 시험 덱」 승률로 순위 매김(단순 추가는 평가 결과가 같아 무의미했음), 안전장치 중단 매치는 판정 없음 처리 | `model/align-rules-spec` 3번째 커밋 → PR #5 |
| 2026-09-30 | 7개 덱 전략 덱 10 → 20장 채움 (레시피 학습기, 메인 · 상급 불변). 세제 · 데쿠마 learned/decks 신규 | `data/fill-strategy-20` → PR #6 (base: `data/add-nny-sim-data`) |
| 2026-09-30 | A 결착 우선 지침: 이번 공격으로 상대 HP 0이면 반드시 공격 (학습 대상 아님). 결착 누락 0건, 무한 진행 재현 해소 | `model/lethal-first` → PR #7 (base: `model/align-rules-spec`) |
| 2026-09-30 | R1 수정: RF 형세 판정이 모델 파일에 저장된 학습 당시 스킬 목록으로 특징을 만듦(28개 일치). 탐색 AI 10매치 오류 0 · 재현 불일치 0. 옛 규칙 모델이지만 새 규칙에서도 AUC 0.87/0.81 (수동 공식 0.72/0.73) | `model/fix-rf-feature-mismatch` → PR #8 (base: `model/lethal-first`) |
| 2026-09-30 | 학습표 B(감쇠 0.1 후 이어서) vs C(초기화 후 재학습) 비교 실험 (방식당 4만 매치): B · C 차이 없음, 둘 다 현행보다 우세 → C 채택 권고. 보고서 · 스크립트는 .docx로 대화창에 전달 (저장소 미반영 — 사용자 지시) | 저장소 반영 없음 |
| 2026-09-30 | PR 순서대로 머지 (main 반영 없음 — 사용자 지시). 쌓인 PR은 base를 계열 기준 브랜치로 바꾼 뒤 변경분 · 충돌 확인 후 머지 | `data/main`: #4 `b2c5419` → #6 `366f910` / `model/main`: #3 `92b5ba7` → #5 `89d9a23` → #7 `4e6acd3` → #8 `4b1e0a7` |

## 실행 환경 메모

- 2026-09-30 세션에서 numpy 2.4.6 · scipy 1.17.1 · scikit-learn 1.8.0(RF 모델 저장 버전과 일치) 설치 — **세션 한정**. 유지하려면 클라우드 환경 설정의 Setup script에 `pip install numpy==2.4.6 scipy==1.17.1 scikit-learn==1.8.0` 추가 (사용자에게 안내함).
- RF 형세 모델: R1 수정(PR #8)으로 형세 판정 정상. 7개 덱 · 새 규칙으로 재학습(`python rf_eval.py <초>`)하면 더 정확해질 수 있음.

## 진행 중

- 계열 기준 브랜치(`model/main` · `data/main`) → `main` 반영: R1에 따라 사용자 지시 대기.
- PR #5 남은 확인 사항 (사용자 확인 대기): 투기장 「수비 표시로 존재할 수 없다」 → 공격 표시 전환(ASSUME), 표시 형식 변경 시점(자신 턴 · 체인 없음 — 투기장과는 별개 항목).
- 학습표 결정 대기: C 학습표 채택 여부, 저장 방식(105MB — GitHub 100MB 한도 초과: gzip 압축 추천 / L2 정리 / Git LFS), 채택 전 R2 · R4 수정. 학습된 표는 임시 컨테이너에만 있음(세션 종료 시 소실, 스크립트로 재생성 약 30분).

## 다음 할 일 (우선순위 순)

1. 머지 후속 작업 (사용자 확인):
   - `덱_등록기.html`(data)을 새 템플릿으로 다시 생성 (전략 덱 20장 · 스킬 카드 전략 덱 추가) → `data/` 새 작업 브랜치.
   - `시제_*.deck` 은 전략 10장 그대로 — 갱신 여부 사용자 확인.
   - 새 AI 선택지(제물 · 수비 소환, 표시 형식 변경, 스킬 교체)는 학습표에 데이터가 없음 → season/train 학습 필요 (analysis 계열). C 학습표 채택 결정과 함께 진행.
   - PR #5 남은 확인 사항 반영은 `model/main` 에서 새 작업 브랜치로 (`model/align-rules-spec` 은 머지 완료).
   - 머지된 작업 브랜치 삭제 (사용자가 GitHub에서 — 원격 삭제 권한 없음).
2. 해설서 리뷰의 높은 심각도 항목 수정 (`model` 계열, 사용자 지시 후 — "수정은 나중에 명령"):
   - R2 run.py · batch.py 실행 시 학습표가 갱신되는 문제 → `model/run-no-learn-default`
   - R3 실행 위치(상대 경로) 의존 → `model/fix-relative-paths`
3. 중간 심각도: R4 학습 파일 원자적 저장, R5 제외 존 복귀 시 카드 소실.
4. 문서 `.md` 8개를 올릴지 결정 — README · 규칙명세 · 미해결 재정 목록은 `docs`, 보고서 · 결과 · 분석 · 기보는 `analysis` 계열 후보.
5. 번성충-기생 덱 승률 5.0% 원인 조사 (`analysis` 계열).

## 브랜치 현황

| 브랜치 | 용도 | 상태 |
| --- | --- | --- |
| `main` | 최종 결과물 | CLAUDE.md · 세션 시작 훅 반영됨 (PR #1, #2) |
| `default` | 규정 · 진척 원본 (CLAUDE.md, workflow.md, 훅) | 사용 중 |
| `model/main` | model 계열 기준 (`main` 에서 분기) | PR #3 · #5 · #7 · #8 머지됨 (`4b1e0a7`), main 미반영 |
| `model/add-nny-sim-code` | nny_sim 코드 원본 | PR #3 머지 완료, 삭제 가능 |
| `data/main` | data 계열 기준 (`main` 에서 분기) | PR #4 · #6 머지됨 (`366f910`), main 미반영 |
| `data/add-nny-sim-data` | nny_sim 데이터 원본 | PR #4 머지 완료, 삭제 가능 |
| `model/align-rules-spec` | 규칙 명세서 기준 코드 수정 | PR #5 머지 완료, 삭제 가능 |
| `data/fill-strategy-20` | 전략 덱 20장 채우기 결과 | PR #6 머지 완료, 삭제 가능 |
| `model/lethal-first` | 결착 우선 지침 | PR #7 머지 완료, 삭제 가능 |
| `model/fix-rf-feature-mismatch` | R1 수정 | PR #8 머지 완료, 삭제 가능 |
| `exp/main` | exp 계열 기준 (`main` 에서 분기, 내용은 main과 같음) | 실험 파일은 올리지 않음 |
| `config/sync-rules-to-main` | main 규정 동기화용 | 머지 완료, 삭제 가능 |
| `claude/lucid-goodall-6570m1` | 첫 세션 자동 생성 브랜치 (내용은 default와 같음) | 삭제 권장 (원격 삭제 권한 없음) |
