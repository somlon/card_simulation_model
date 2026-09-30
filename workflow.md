# workflow.md — 작업 진척 기록

모든 세션은 작업 전에 이 파일을 확인하고, 작업 후 갱신한다 (CLAUDE.md R4).
원본은 `default` 브랜치의 이 파일이다.

마지막 갱신: 2026-09-30

## 현재 상태 요약

- 저장소 규정 체계(CLAUDE.md · 세션 시작 훅 · workflow.md) 구축 완료.
- `nny_sim` 을 원본 그대로(수정 없음) 코드 · 데이터로 나눠 PR로 올림 — **머지 대기 중**.
  - 코드: `model/add-nny-sim-code` → `model/main` (PR #3)
  - 데이터: `data/add-nny-sim-data` → `data/main` (PR #4)
  - 두 PR은 같은 `nny_sim/` 폴더에 겹치지 않는 파일을 올린다. 실행하려면 둘 다 필요.
- `model/main` · `data/main` 은 `main` 에서 분기함 (사용자 지시: main에 연결).
- 규칙 명세서(LLM 적용본, 2026-09-29)를 기준으로 코드를 수정해 PR #5로 올림 — PR #3 브랜치 위에 쌓은 PR이라 #3 머지 후 base를 `model/main`으로 변경해야 함.
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

## 진행 중

- PR #3 · #4 · #5 사용자 검토 · 머지 대기.
- PR #5의 「확인이 필요한 사항」 7건 사용자 답변 대기: 수비 표시 몬스터 공격, 턴 상한 40턴, 전략 덱 채우기(10/20장), 덱 미지정 제외의 선택 주체, §10-3 a 해석, AI가 쓰지 않는 합법 행동(제물 소환 등), 일반 · 지속 마법 발동 시점.

## 다음 할 일 (우선순위 순)

1. PR #3 · #4 머지 → PR #5 base를 `model/main`으로 변경 후 머지 (사용자 확인).
   - PR #5 머지 후 `덱_등록기.html`(data)을 새 템플릿으로 다시 생성 (전략 덱 20장 · 스킬 카드 전략 덱 추가).
   - PR #5 답변 반영은 같은 브랜치 `model/align-rules-spec` 에 이어서.
2. 해설서 리뷰의 높은 심각도 항목 수정 (`model` 계열, 사용자 지시 후 — "수정은 나중에 명령"):
   - R1 RF 형세 모델 특징 수 불일치로 SearchAI 오류 → `model/fix-rf-feature-mismatch`
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
| `model/main` | model 계열 기준 (`main` 에서 분기) | PR #3 대상 |
| `model/add-nny-sim-code` | nny_sim 코드 원본 | PR #3 열림 |
| `data/main` | data 계열 기준 (`main` 에서 분기) | PR #4 대상 |
| `data/add-nny-sim-data` | nny_sim 데이터 원본 | PR #4 열림 |
| `model/align-rules-spec` | 규칙 명세서 기준 코드 수정 (`model/add-nny-sim-code` 에서 분기) | PR #5 열림 |
| `config/sync-rules-to-main` | main 규정 동기화용 | 머지 완료, 삭제 가능 |
| `claude/lucid-goodall-6570m1` | 첫 세션 자동 생성 브랜치 (내용은 default와 같음) | 삭제 권장 (원격 삭제 권한 없음) |
