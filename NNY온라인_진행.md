# NNY 온라인판 — 진행 기록

루틴(「NNY 온라인판 작업」, 매시 7분)의 상태 파일. 회차마다 ①읽고 ②과제 하나 ③갱신.

## 부트스트랩 상태 (2026-10-30, 사용자 세션)

- online/main 생성됨 (기준 model/main) + v1.1.0 빌드의 `nny_sim/app/`·`nny_sim/viewer/` 소스 투입.
  **주의 해소(이번 회차): app/sim 짝 자체는 어긋나지 않았다 — 진짜 문제는 `nny_sim/card_pool.json` ·
  `nny_sim/decks/` · `nny_sim/learned/decks/` 가 online/main 에 전혀 커밋돼 있지 않아 엔진이 import 단계에서부터
  죽는 것이었다(이 파일들은 data 트랙 산출물 — `.gitignore` 없이 그냥 data/main 에만 있음). data/main 의 최신
  스냅샷을 온라인판에도 들여왔다 — **주의: data/main 이 새 카드·덱을 받으면 이 세 가지도 다시 받아와야 어긋나지
  않는다(다음에 손대는 회차가 data/main 최신인지 먼저 diff 해볼 것).**
- 문서: 온라인_접속_안내.md · online_users.json(장인준=25.0.242.63) · docs/AI_방식_선택지.md ·
  README_온라인판.md · 시작_온라인서버.bat · 재정질문/README.md
- `시작_온라인서버.bat` 에 있던 깨진 문자(이번 회차에 고침): `\r`·`\a`·`\v` 가 글자 그대로 들어가 있어서
  `runtime\python.exe` 가 실제로는 캐리지리턴+`untime\python.exe` 였다(파이썬 비-raw 문자열로 만들 때 생긴
  손상으로 보임). `%BASE%\runtime\python.exe` · `nny_sim\app\main.py` · `nny_sim\viewer` 로 고쳤다 — Windows 에서
  실제로 실행해 본 적은 없음(리눅스 세션이라 .bat 자체 구동 확인은 못 함, 내용만 바이트 단위로 검증).
- AI 방식 3안 데모(nny_sim/online_demos/)는 사용자 세션이 로컬 검증 후 추가 커밋 예정 —
  이미 있으면 그대로 쓰고, 없으면 기능 v1 작업을 먼저 한다 (데모 작성은 사용자 세션 몫).

## 다음 회차 지시

기능 v1 ① 계속 — 이번 회차는 서버 쪽(하마치 바인딩 · 좌석별 Bridge · 참가 키 라우팅)만 했고 **화면(static/app.js
· board.js · index.html)은 아직 손대지 않았다** — 지금은 사람vs사람을 치려면 fetch 를 직접 짜야 한다(실제 유저
관점에서는 안 됨). 다음 회차: 로비 없이 최소한만 — 방 시작 화면에 「사람 대 사람」 버튼 추가, 시작 응답의
`seats` 중 내 좌석 키를 세션에 쥐고 poll·answer 에 `seat`·`key` 를 자동으로 붙이게, 상대 좌석 키는 복사해서
건네줄 수 있게 표시, 받는 쪽은 `/api/match/join` 으로 입력해 들어오게. ③ 로비가 생기면 이 키 교환은 로비가
대신하므로 지금은 가장 단순한 형태로.

## 사용자 결정 대기

- 친구들(세창 포함)의 하마치 IP — 받으면 online_users.json 에 추가
- 세창의 AI 방식 선택 (docs/AI_방식_선택지.md)

## 완료 기록

- 2026-10-30 (루틴): 기능 v1 ① 서버 쪽 — `nny_sim/app/server.py` 에 하마치 어댑터(25.x) 자동 탐색 ·
  미발견 시 `HamachiNotFound`(main.py 가 한국어 안내 후 조용히 끝남, 개발·스모크용 `--host` 탈출구 있음).
  `nny_sim/app/session.py` 의 `LiveMatch` 가 `human=(bool,bool)` 을 받아 좌석마다 독립 `Bridge`·참가 키를
  가지도록(`self.bridges`·`self.keys`) 바꿈 — 기존 사람vsAI(좌석 하나)는 seat·key 없이 그대로 동작(호환).
  `/api/match/join`(참가 키로 좌석 찾기) · `/api/match/poll`·`/api/match/answer` 에 `seat`·`key` 추가.
  검증: `nny_sim/test_online_pvp.py`(가짜 HTTP 클라이언트, unittest) — 「대전 2(좌석0·좌석1) + 관전 1」 자동
  스모크로 좌석 라우팅 · 교차 응답 거부(다른 좌석 키로 응답 불가) · 관전자 pending 없음을 확인. 5회 연속 통과.
  가는 길에 레이스 하나 고침: `human.py` 의 `Bridge.reply()` 가 `pending` 을 바로 비우지 않아, 빠른 재poll 이
  이미 답한 판단을 또 보고 다시 답하려다 거부당하는 경우가 있었음(관찰 가능한 벤치마크 기준 5/5 → 고친 뒤 5/5
  재현 없음) — `reply()` 성공 시 `pending` 도 같이 비우도록 한 줄 수정.
  `python -m py_compile`(5개 파일) · `python -m unittest test_online_pvp -v`(2/2 통과) ·
  `python -m unittest test_match_sim test_table test_blocks`(27/28 통과 — 나머지 1개는 scipy 미설치로 이 회차
  전후 동일하게 실패, 무관) 전부 실행 확인. 서버 기동(`main.py --no-browser`, `--host` 로) 핑 스모크도 통과.
  데이터 보강: `nny_sim/card_pool.json` · `nny_sim/decks/`(공식 덱 11개) · `nny_sim/learned/decks/` 를
  data/main 최신에서 가져옴(온라인판이 아예 뜨지도 못하던 원인) — `nny_sim/app/tables.py` 의 `matchup_table` 도
  분할표 manifest.json 이 없을 때(새 설치) 죽지 않고 휴리스틱 기본값으로 가도록 고침.
  `시작_온라인서버.bat` 의 손상된 이스케이프 문자(`\r`·`\a`·`\v`) 바로잡음.
  **거짓 보고 없음 표시**: static/app.js·board.js·index.html(화면)은 이번 회차에 전혀 건드리지 않았다 —
  사람vs사람은 지금 서버 API 로만 가능하고 화면에서는 아직 못 쓴다(다음 회차 지시 참고).

## 추가 요구 (2026-10-30, 사용자 — 기능 v1 ③·④ 즈음 함께)

- **화면 테마 3종**: ① 화이트 모드 ② 블랙 모드 ③ 「뉴 네오」 고유 테마(깔끔하고 수수한
  톤 — 과하지 않게, 사람이 한 컷처럼 정돈된 디자인). 설정에서 전환, 기본은 ③.
- 디자인·UX 개선 아이디어가 보이면 기존과 비교해 더 낫다고 판단되는 것은 **기록해 두고
  바로 실행해도 됨**(사용자 재량 위임). 단 룰 레이어 불가침은 그대로.
- 만들고 나면 최적화 반복 전제 — 잘못된 방식이면 다시 만드는 과정을 두려워하지 말 것.

## 추가 요구 2차 (2026-10-30 심야, 사용자)

- **기능이 완벽하게 돌아가는 것이 최우선.** 프로그램 리워크/리메이크급 변경은 세창 허락이 선행.
- **인게임 메신저(수다)**: 접속자끼리 채팅 + 그 로그를 기보와 함께 수집(가져올 수 있게). 기능 v1 ③~④ 즈음.
- 접속자 **이름 설정/확인**(② 등록 유저제에 포함) — 메모·재정 논의에 작성자가 남게.
- AI 방식 3안 데모가 `nny_sim/online_demos/` 에 들어옴(사용자 세션 실측 완료) — 세창 선택 참고용.

## 세창 체크 요청 검증 (2026-10-30 01시 카톡 → 코드 확인 완료)

세창이 짚은 두 가지를 v1.1.0 코드로 검증한 결과:

1. **덱 미지목 이동(덱→묘지/제외)의 덱 선택** — ✅ **구현돼 있음.** `engine.mill(deck=None)` 이
   chooser(기본 = 덱 소유자)에게 메인/상급을 고르게 하고(§6-7·§15-1), 사람 자리는
   `HumanAI.choose_mill_deck` 으로 화면에서 묻는다. ※루틴 할 일: mill 을 안 거치는
   덱→묘지/제외 경로가 있는지 전수 점검(있으면 같은 선택 연결).
2. **상급(제물) 일반소환의 릴리스 몬스터 선택** — ❌ **사람 모드에 누락(세창 의심 적중).**
   `app/human.py` 행동 목록(145행)이 `tributes_needed > 0` 몬스터를 후보에서 제외만 하고,
   AI 쪽(`ai.py pick_tributes`·제물 소환 후보 410~419행)에 있는 제물 소환 경로가 사람에겐 없다
   → **사람은 제물 일반소환을 아예 할 수 없음.**
   **수정 과제(기능 v1 ①과 같은 묶음, app 레이어)**: human.py 행동 목록에 제물 소환 후보 추가
   + 제물로 릴리스할 몬스터를 사람이 고르는 질문(조합 선택) 추가 — `ai.py pick_tributes` 의
   후보 생성 재사용, 엔진 `normal_summon(c, p, tributes)` 그대로 호출(룰 불가침 유지).
3. AIvsAI·관전 쪽은 영향 없음(두 기능 모두 AI 경로에는 존재).
