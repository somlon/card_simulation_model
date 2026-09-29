# workflow.md — 작업 진척 기록

모든 세션은 작업 전에 이 파일을 확인하고, 작업 후 갱신한다 (CLAUDE.md R4).
원본은 `default` 브랜치의 이 파일이다.

마지막 갱신: 2026-09-29

## 현재 상태 요약

- 저장소 규정 체계(CLAUDE.md · 세션 시작 훅 · workflow.md) 구축 완료.
- 시뮬레이터 코드(`nny_sim`)는 **아직 저장소에 없다** — 업로드된 압축 파일(nny_sim_1.zip)로만 분석함.
- 코드 해설서(.docx)를 만들어 사용자에게 전달함(저장소에는 올리지 않음).

## 완료

| 날짜 | 작업 | 브랜치 · 결과 |
| --- | --- | --- |
| 2026-09-29 | CLAUDE.md 작성 (R1 main 보호, R2 역할별 브랜치, R3 외부 업로드 제한) | `default` → PR #1로 `main` 머지 |
| 2026-09-29 | nny_sim 코드 해설서 작성 (파일 · 클래스 · 아키텍처 + 코드 리뷰 18건) | 파일로 전달 (저장소 미반영) |
| 2026-09-29 | 세션 시작 훅, R0 · R2 개정 · R4 추가, workflow.md 생성 | `default` |
| 2026-09-29 | main에 훅과 새 규정 반영 (workflow.md 제외) | `config/sync-rules-to-main` → PR #2로 `main` 머지 |

## 진행 중

- (없음)

## 다음 할 일 (우선순위 순)

1. `nny_sim` 코드를 저장소에 올릴지 결정 — 올린다면 `model/main` · `data/main` 계열로 (사용자 확인 필요).
2. 해설서 리뷰의 높은 심각도 항목 수정 (`model` 계열):
   - R1 RF 형세 모델 특징 수 불일치로 SearchAI 오류 → `model/fix-rf-feature-mismatch`
   - R2 run.py · batch.py 실행 시 학습표가 갱신되는 문제 → `model/run-no-learn-default`
   - R3 실행 위치(상대 경로) 의존 → `model/fix-relative-paths`
3. 중간 심각도: R4 학습 파일 원자적 저장, R5 제외 존 복귀 시 카드 소실.
4. 번성충-기생 덱 승률 5.0% 원인 조사 (`analysis` 계열).

## 브랜치 현황

| 브랜치 | 용도 | 상태 |
| --- | --- | --- |
| `main` | 최종 결과물 | CLAUDE.md · 세션 시작 훅 반영됨 (PR #1, #2) |
| `default` | 규정 · 진척 원본 (CLAUDE.md, workflow.md, 훅) | 사용 중 |
| `config/sync-rules-to-main` | main 규정 동기화용 | 머지 완료, 삭제 가능 |
| `claude/lucid-goodall-6570m1` | 첫 세션 자동 생성 브랜치 (내용은 default와 같음) | 삭제 권장 (원격 삭제 권한 없음) |
