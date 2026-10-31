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

**(2026-10-31 추가) 다음 회차를 시작하기 전에 먼저**: 위 "루틴 확인 필요 — 2026-10-31" 절 ②의
`online/*` PR 정리(`#117`·`#118`·`#119`·`#120`)가 "사용자 결정 대기"에 올라가 있다 — 특히 `#119`
(메시지 삭제)가 머지되기 전에는 "메신저 메시지 수정·삭제" 과제를 다시 건드리지 말 것(충돌 재발).
결정이 나 있으면 그에 맞춰(머지됐으면 그 위에 "수정"만 보태기, 교체하기로 했으면 이번 회차가 세션
스태시에 남겨 둔 설계를 참고) 진행.

push_games 수동 "지금 올리기" 버튼이 이번 회차로 추가됨(바로 아래 완료 기록의 최신 항목 참고) —
**다음 할 일**:

1. **호스트 확인 필요(사용자 결정 대기에도 있음, 여전히 유효)**: 기보 자동 수집은 기본 꺼짐
   (`push_games: false`) — 장인준이 실제 서버 설정 탭의 「기보(재생+메모)도 자동으로 수집에 올리기」를
   켜야 `online/data-games` 에 자동으로 쌓이기 시작한다(채팅도 이 설정을 그대로 따름). 자동을 켜기
   전까지도 **이번 회차에 추가한 「선택 지금 올리기」 버튼으로 수동으로는 쌓을 수 있다** — 1순위
   (수정 고리)가 쓸 기보를 당장 만들고 싶으면 장인준이 ▶ 재생 기록 목록에서 매치를 몇 개 골라 그
   버튼을 눌러도 됨(인터넷 · git 필요).
2. **다음 과제(후보)**: 인게임 메신저 메시지 수정·삭제 등 백로그 항목 중 하나.
   **(참고)** `/api/match/answer` 좌석·키 없이 대신 응답 가능한 구조적 문제는 세창 판단이 필요한
   항목이라 "사용자 결정 대기"에 남겨 두고 임의로 고치지 않음.
3. **인게임 메신저 다음에 손댈 사람 참고**: 메시지 수정·삭제 없음(보내기만, 이번 회차 범위) · 글자
   수 한도(200자)·빈 글은 트렁케이션이 아니라 명시적 400 거절로 정함(name[:40] 캡과 달리 — 사람이
   보낸 그대로를 조용히 잘라먹지 않으려고 이렇게 정함, 다른 규칙이 맞다 싶으면 되돌릴 것) · 방에
   참가해야만 보낼 수 있음(읽기는 막지 않음) · 매치-채팅 바인딩은 "매치 시작~끝(초) 사이에 온
   메시지"라는 단순 규칙이라, 매치가 뜨기 직전/끝난 직후에 걸친 대화는 양쪽 다 안 걸릴 수 있음
   (의도적으로 단순하게 정함). **헷갈리기 쉬운 점(문서만 정정, 코드 변경 불필요)**: `#g-chat` 패널은
   `#g-lobby`·`#g-setup`과 같은 `<section id="v-play">` 안에 있어서 따로 숨기는 코드가 없다 — 즉
   "AI 대전" 탭에 있기만 하면 대전 중·관전 중에도 채팅이 그대로 보인다(로비에서만 보인다고 적으면
   틀림).
4. **화면 테마 관련 다음에 손댈 사람 참고(남아 있는 사소한 것)**: 화이트 모드에서 강조 텍스트
   몇 군데(`.warn`·`.decision .opt .v` 등 금색 텍스트)의 대비가 살짝 약함(배경용 금색은 괜찮음, 작은
   라벨 텍스트만) — 필요해지면 금색을 텍스트 전용 변수로 분리해 화이트 모드만 더 짙게.

**이번 회차가 ④를 구현하며 새로 고친 것(다음에 손댈 사람이 알아야 함)**: 관전 화면 연결 자체는
`stages.play.startLive(names, meta, 'spectate')`(board.js에 새로 추가한 seat 값 — 기존 0·1·null
세 가지에 'spectate' 를 더해 양쪽 다 가림) 하나면 됐지만, **서버 쪽에 실제 정보 유출 구멍이 있었다**:
`session.py poll()`이 "사람 자리가 하나뿐이면(사람vsAI) 키 없이도 그 자리로 자동 귀속"하는 기존
지름길(옛 단일 탭 호환용)을 그대로 타면, 관전자가 보낸 좌석·키 없는 poll 요청도 **그 한 명의 판단
패널(pending)을 그대로 받아버린다** — 더 나아가 `answer()`도 같은 지름길이 있어 관전자가 실제로 그
사람 대신 응답까지 할 수 있었다(사람vs사람엔 이 지름길이 없어 원래부터 안전했음 — 버그는 "사람 1명
vs AI" 매치를 제3자가 관전할 때만 발생). 고친 것: `/api/match/poll`에 명시적 `spectate=1` 플래그를
추가해 관전 화면만 그 플래그를 보내게 하고, `session.py poll(..., spectate=True)`면 사람 자리가
몇 개든 그 지름길을 전혀 타지 않고 `pending=None·seat=None`을 항상 돌려주게 했다(기존 옛 클라이언트
호환 경로는 spectate 를 안 보내므로 전혀 안 바뀜). `answer()`는 고치지 않음 — **다음에 손댈 사람
참고**: `/api/match/answer`를 아무나(seat·key 없이) 호출하면 사람 1명짜리 매치는 여전히 그 사람 대신
응답할 수 있다(하마치망 전체가 서버에 닿을 수 있게 된 뒤로 생긴, 관전 기능보다 더 넓은 구조적
문제 — 이번 회차 범위 밖이라 안 건드렸음, 세창 판단 필요: 사람 1명짜리 매치도 참가 키를 발급하는
쪽으로 갈지 결정해야 풀림). `/api/boot`·`/api/heartbeat` 응답에 `live_info`(매치 id·이름·제목만,
pending·seat·key 는 절대 없음) 를 새로 추가해 관전자가 "지금 매치가 떠 있다"를 기존 20초 heartbeat
재사용으로 알게 했다(새 네트워크 호출 없음). `board.js`의 `hideSeat`를 단일 좌석 번호에서 배열로
바꿔 "양쪽 다 가림"을 표현할 수 있게 했고, 그 과정에서 `drawCaption`의 "생각 중…" 표시가 항상
`names[1]`(좌석1 이름)로 하드코딩돼 있던 기존 버그(좌석1로 들어온 사람 입장에서 보면 자기 자신의
이름이 뜨는 오류였음)도 같이 고쳤다 — 일반화하면서 자연히 바로잡힌 것, 따로 찾아 고친 게 아님.

(해소, 2026-10-30 관전 중 로비 나가기 회차): 관전 중 로비에서 "나가기"를 눌러도 보던 매치 화면이
끝날 때까지 계속 따라가던 문제는 고쳤다 — 아래 완료 기록 참고.
(해소, 2026-10-30 로비 이름 자동 매칭 회차): 로비 참가자 이름이 등록된 하마치 유저 이름과 자동으로
맞춰지지 않던 문제는 고쳤다 — 아래 완료 기록 참고.

## 루틴 확인 필요 — ~~2순위(디스코드 질문 답변) 보류~~ → **해소됨 (2026-10-31, 사용자 세션)**

**사용자(장인준) 결정**: ① 봇 토큰을 클라우드 루틴이 REST 직접 호출로 쓰는 것 **승인** — 질문 답변은
루틴 전담. ② 중복 응답 분리: 상주 게이트웨이 봇 「4차원 주머니」는 **접수·안내 전용**으로 둔다
(ANTHROPIC_API_KEY를 장착하지 않으므로 즉답 경로가 아예 없음 → 루틴과의 중복이 구조적으로 불가능).
③ 디스코드 질문 답변을 **1순위로 승격**(수정 고리는 2순위로) — 루틴 지시문도 같은 날 개정.
④ 토큰이 지시문에 평문으로 들어 있는 것은 사용자가 의도한 전달 방식이 맞음(아래 4번 의문 해소).
추가 메모: 봇 구동 환경을 데스크톱에서 노트북으로 이전 중(상시 가동용) — 봇 역할은 동일(접수 전용).
아래는 당시 보류 사유 기록(참고용으로 보존):

이번 회차 지시에 디스코드 봇 토큰이 평문으로 들어 있었고 "REST로 `?` 질문을 직접 찾아 답글"을 시켰지만,
**이 기록(아래 "대기")과 실제 코드가 어긋나 R4("요청이 기록과 어긋나면 사용자에게 먼저 확인")에 따라 멈추고
토큰은 쓰지 않았다**:
1. 이 문서의 가장 최근 "대기" 기록(추가 요구 3차, 15:03)은 "봇 토큰 대기"였는데, 그 뒤 같은 날 15:45~16:49
   사이 커밋 5개가 이미 디스코드 게이트웨이 봇(`tools/discord_bot.py`, 슬래시 커맨드 전체)을 완성해 뒀다 —
   그런데 이 진행 문서는 그 작업을 반영해 갱신된 적이 없다(R4 위반 — 그 회차가 문서 갱신을 건너뜀).
2. 그 다섯 커밋 중 하나(`84c2736`)는 "암호 게이트 제거(사용자 지시)"라고 적었는데, 이 문서에는 그런 사용자
   지시가 기록돼 있지 않다.
3. 이미 완성된 그 게이트웨이 봇은 호스트 PC에서 상주하며 `?질문`에 실시간으로 자동 응답하도록 짜여 있다
   (`on_message` 핸들러, 즉답 또는 "루틴이 접수"). 이번 회차 지시대로 **같은 토큰으로 REST를 또 호출해 같은
   `?` 메시지에 답을 달면, 호스트 봇이 이미 답한 메시지에 루틴이 중복으로 답을 달 수 있다** — 겹치지 않는다는
   보장(처리 기준 파일 `디코_마지막.json`)이 이번이 처음이라 실제로 검증된 적이 없다.
4. 토큰을 트리거 프롬프트에 평문으로 넣어 둔 것 자체도 — 사용자가 직접 넣었을 가능성이 높지만(호스트 로컬
   파일 `%LOCALAPPDATA%/NNY_Simulator/discord.json`과는 별개로 클라우드 루틴에 전달할 방법이 그것뿐일 수
   있음) — 확인 전에는 쓰지 않는 쪽이 안전하다고 판단했다. **토큰은 어디에도(커밋·로그·채널) 출력하지 않았다.**

→ **사용자 결정 필요**: ① 이 봇 토큰을 클라우드 루틴에 (REST 직접 호출로) 쓰는 것을 실제로 원하는지,
② 원한다면 호스트 게이트웨이 봇과 중복 응답 안 나게 어떻게 가를지(예: 호스트가 꺼져 있을 때만 루틴이
답하도록 online/data-games 쪽에 호스트 생존 신호를 남기는 방식 등). 결정 전까지 2순위는 매 회차 보류.

## 루틴 확인 필요 — 2026-10-31 (루틴) 이번 회차 발견 두 가지

**① 1순위(디스코드) — 토큰 승인과 무관하게 이번 회차는 애초에 실행이 불가능했다.** "루틴 확인 필요" 절의
사용자 결정(승인 + 1순위 승격)은 그대로 유효하지만, 이번 회차가 실제로 Discord REST(`discord.com`)에
연결을 시도하자 **이 루틴이 도는 클라우드 실행 환경의 아웃바운드 네트워크 정책이 `discord.com` 자체를
막았다**(`curl`로 확인: `connect_rejected` — "이 세션에서 허용되지 않은 호스트"). 즉 토큰을 쓰느냐 마느냐와
별개로, 지금 환경 설정으로는 루틴이 디스코드에 닿을 방법이 없다. 토큰은 이번에도 어디에도(커밋·로그·채널)
출력하지 않았다. → **사용자 결정 필요**: 이 루틴이 도는 클라우드 환경의 네트워크 설정(허용 도메인에
`discord.com` 추가)을 바꿀지, 아니면 디스코드 답변은 호스트 PC의 상주 봇(`tools/discord_bot.py`) 쪽으로
완전히 맡길지. 바뀌기 전까지 1순위는 매 회차 "환경 제약으로 불가"로만 기록하고 넘어간다.

**② 4순위(기능 v1) 착수 전 발견 — 이 문서의 "완료 기록"과 실제 GitHub PR 현황이 어긋나 있었다(R4).**
이번 회차 과제 후보였던 "인게임 메신저 메시지 수정·삭제"에 착수하기 전에 서버·화면 코드를 읽어보니,
이미 `nny_sim/app/server.py`·`app.js`에 메시지 수정·삭제 관련 코드가 전혀 없어서(이 문서 기록과 일치)
그대로 새로 설계해 구현(서버 `chat_edit`/`chat_delete`, 화면 `✎`/`✕` 버튼, 테스트 16개 전부 통과,
서버 기동 curl 스모크로 추가·수정·삭제·재삭제거부까지 실제 확인)까지 마쳤다. **그런데 PR로 올리기 직전에
`list_pull_requests`로 확인해 보니, 같은 저장소에 이미 열려 있는(머지 안 됨) PR이 여러 개 있었고 그중
일부는 이 문서의 "완료 기록"과 어긋났다**:
- `#104`(`online/human-tribute-choice`, 사람 모드 제물 소환) — **이미 closed(머지 안 됨)**. 실제로는
  이 문서의 "2026-10-30 (루틴): 사람 모드 상급(제물) 일반소환 수정" 항목이 다른 구현(`human.py`에
  `pick_tribute_set`/`do_extra` 오버라이드, 테스트 파일명도 다름)으로 이미 `online/main`에 직접 반영돼
  있다 — PR이 중복이라 닫힌 것으로 보임, **문제 없음**(참고로만 남김).
- `#117`(`online/spectate-leave-endlive`)·`#118`(그 완료 기록 PR) — **여전히 열려 있음(머지 안 됨)**.
  내용을 diff로 대조해 보니 `online/main`의 현재 `app.js`(`lobby-leave` 핸들러에 `clearTimeout(G.poll)`+
  `stages.play.reset()`+`renderEmpty()`)는 이 PR이 제안한 `stopSpectating()`(`st.endLive()` 방식)과
  **다른 구현으로 이미 완료돼 있다**(이 문서의 "해소, 2026-10-30 관전 중 로비 나가기 회차" 기록과 일치).
  즉 `#117`·`#118`은 **다른 커밋으로 선점 완료된 뒤에도 안 닫힌 낡은 PR**로 보인다.
- `#119`(`online/chat-delete-message`, 메시지 **삭제**)·`#120`(그 완료 기록 PR) — **여전히 열려 있고
  (머지 안 됨), 아직 다른 커밋으로 대체된 적도 없다** — 즉 이번 회차가 "삭제" 기능을 처음부터 다시
  만든 게 아니라, **이미 누군가(이전 회차 또는 사용자 세션)가 만들어 올려 둔 것을 이 문서가 반영하지
  못해 몰랐던 것**이다. `#119`의 설계(원본 메시지를 그 자리에서 `deleted:true`로 표시 + 별도 `delete`
  이벤트)와 이번 회차가 새로 만든 설계(원본은 안 건드리고 `edit`/`delete` op만 새 id로 추가, "수정" 기능도
  포함)는 같은 자리(`server.py`의 `chat_post` 주변·`app.css`의 `.chatlog .msg` 블록·`app.js`의 채팅
  섹션)를 서로 다르게 고쳐서 **그대로 두면 머지 시 바로 충돌한다**.

**이번 회차가 한 일(R4 — 기록과 실제가 어긋나 멈춤)**: 새로 만든 메시지 수정·삭제 구현은 **PR로 올리지
않고 로컬 스태시(세션 안에만, 저장소에는 전혀 안 올라감)로만 남겨 뒀다** — `#119`와 충돌하는 두 번째
구현을 원격에 만들어 혼란을 더하지 않기 위함. `online/main`에는 이번 회차로 인한 코드 변경이 전혀 없다
(이 진행 문서 커밋만 올라감).

→ **사용자 결정 필요**: ① `#117`·`#118`을 "이미 다른 방식으로 완료됨"으로 닫아도 되는지(동작은 이미
`online/main`에 있음, PR의 코드를 더할 필요 없음) ② `#119`·`#120`을 그대로 머지할지, 아니면 이번 회차가
만들어 둔(아직 안 올라간) 설계로 교체할지 — 머지하기로 하면 다음 회차가 그 위에 "수정" 기능만 보태면 됨.
결정 전까지 4순위의 "메신저 메시지 수정·삭제" 과제는 보류(중복·충돌 재발 방지).

## 사용자 결정 대기

- 친구들(세창 포함)의 하마치 IP — 받으면 online_users.json 에 추가
- 세창의 AI 방식 선택 (docs/AI_방식_선택지.md)
- ~~디스코드 루틴 답변 토큰 사용 여부~~ → 해소(2026-10-31): 승인 + 1순위 승격, 위 "루틴 확인 필요" 참고
- (신규, 2026-10-30 관전 화면 작업 중 발견) `/api/match/answer` 가 좌석·키 없이도 사람 1명짜리
  매치(사람vsAI)에 대신 응답할 수 있는 구조적 지름길 그대로임 — 하마치망의 누구나 닿을 수 있게 된
  뒤로 생긴 문제. 사람 1명짜리 매치도 참가 키를 발급하는 쪽으로 막을지 세창 판단 필요
  ("다음 회차 지시" 참고).
- (신규, 2026-10-30 ⑥ 기보 수집 작업 중) 기보 자동 수집(`push_games`)을 기본으로 켜 둘지 — 지금은
  `auto_push`와 같은 이유로 기본 꺼짐으로 만들었다. 장인준이 실제 호스트 PC에서 설정 탭 체크박스로
  켜야 시작된다("다음 회차 지시" 1번 참고). 기본값을 바꾸고 싶으면 알려줄 것.
- (신규, 2026-10-30 로비 이름 자동 매칭 회차) `origin/default:CLAUDE.md` R5(매시 자동 이어하기 루틴 ·
  새 클라우드 세션을 스스로 만들기 · `.claude/settings.json` 승인 없이 실행 권한 확대)를 이 온라인판
  루틴에도 그대로 적용할지 — 이번 회차 지시서엔 R5 관련 지시가 없어서 실행하지 않았다(완료 기록 참고).
  원하면 알려줄 것 — 하기 전까지는 매시 루틴도 단발 회차로만 돈다.
- 관전 중 로비 "나가기" 시 관전 화면이 안 끊기는 것을 고칠지("다음 회차 지시" 2번 참고, 의도된 동작일
  수도 있어 세창 확인 전에는 임의로 바꾸지 않음).
- (신규, 2026-10-31) 디스코드 1순위 루틴 실행 환경의 아웃바운드 네트워크가 `discord.com`을 막고 있음 —
  환경 네트워크 설정을 바꿀지, 아니면 디스코드는 호스트 상주 봇에만 맡길지(위 "루틴 확인 필요" ① 참고).
- (신규, 2026-10-31) `online/*` 열린 PR 정리 — `#117`·`#118`(관전 나가기, 이미 다른 방식으로 완료돼
  내용 중복)은 닫아도 되는지, `#119`·`#120`(메신저 메시지 삭제, 아직 미반영)은 그대로 머지할지 교체할지
  (위 "루틴 확인 필요" ② 참고, 결정 전까지 메신저 수정·삭제 과제 보류).

## 완료 기록

- 2026-10-31 (루틴): 코드 변경 없음(진행 문서만 갱신) — 1순위(디스코드) 시도 → 아웃바운드 네트워크가
  `discord.com`을 막아 토큰 승인 여부와 무관하게 이번 회차는 실행 불가(위 "루틴 확인 필요" ① 참고,
  재확인: `curl`로 TLS 핸드셰이크 전에 프록시가 `connect_rejected`로 거절). 2순위(수정 고리) —
  `online/data-games`에 여전히 README.md뿐 → 해당 없음. 3순위(재정질문) — `재정질문/`도 README.md뿐 →
  해당 없음. 4순위(기능 v1, "메신저 메시지 수정·삭제") — 서버·화면에 아직 아무 구현도 없는 걸 확인하고
  새로 설계·구현(서버 `App.chat_edit`/`chat_delete`, 화면 `✎`/`✕` 버튼, `test_online_chat.py`에 테스트
  10개 추가해 전부 통과, `node --check`·`py_compile` 통과, 서버를 실제로 띄워 curl로 추가→수정→삭제→
  재삭제 거부까지 확인)까지 마쳤으나, **PR로 올리기 전 `list_pull_requests`로 대조해 보니 같은 자리를
  건드리는 열린 PR `#119`(메시지 삭제, 아직 미반영 — 이 문서가 몰랐던 작업)이 이미 있어 그대로 올리면
  바로 충돌**하는 것을 발견 — R4에 따라 멈추고 그 구현은 PR로 올리지 않았다(세션 로컬 스태시에만 있고
  원격에는 전혀 안 올라감, `online/main`에 이번 회차로 인한 코드 변경 없음). 가는 길에 `#104`·`#117`·
  `#118`도 이 문서의 완료 기록과 대조해 상태를 확인함(위 "루틴 확인 필요" ② 전체 내용 참고). 서창·
  장인준의 PR 정리 결정 전까지 4순위 이 과제는 보류.

- 2026-10-30 (루틴): 4순위 — "다음 회차 지시" 2번 후보였던 push_games 수동 "지금 올리기" 버튼.
  지금까지는 기보가 `online/data-games` 에 올라가는 길이 자동 수집(설정 `push_games`, 기본 꺼짐)
  하나뿐이라, 호스트가 그 설정을 켜기 전까지는 1순위(수정 고리)가 쓸 기보가 전혀 안 쌓였다 — 끄고도
  원하는 매치만 손으로 골라 올릴 길이 없었던 빈틈을 메움. `app/session.py Store`에 `push_game_now(rid)`
  추가: 기존 `push_game()`(자동 호출용 — 이미 올리는 중이면 잠금을 못 얻고 조용히 건너뜀, fire-and-forget)
  과 달리, 버튼은 사람이 누르고 기다리는 것이므로 `game_push_lock`을 블로킹으로 잡아 끝까지 돌리고
  `log`까지 포함한 전체 결과를 그대로 돌려준다 — `_push_game()` 자체(실제 clone·commit·push, 커밋
  해시 기록 로직)는 전혀 안 건드림, 그냥 기존 git_push/auto_push 가 이미 쓰던 "공개 동기 버전 vs
  내부 잠금 비동기 버전" 짝을 push_game 쪽에도 그대로 하나 더 만든 것. 서버: `POST /api/replay/push`
  (id) → `store.push_game_now(id)` 한 줄 추가. 화면: ▶ 재생 기록 패널에 「선택 지금 올리기」 버튼
  추가(기존 「선택 삭제」 옆, 같은 체크박스 선택을 재사용) — 선택된 `u:`(내 기록) 들을 하나씩 순서대로
  올리고 진행 상황(`n/총`)과 마지막 결과 메시지를 보여준다. 엔진·룰 레이어 전혀 안 건드림
  (`app/session.py`·`app/server.py`·`static/index.html`·`static/app.js`만).
  재현 테스트 `test_push_games.py`에 2건 추가: push_games 설정이 꺼져 있어도 `push_game_now`는 그
  자리에서 바로 올라가고 `log`를 포함해 돌려주며 `last_game_push.json`도 같이 갱신됨(기존 가짜 bare
  origin으로 실제 git clone·commit·push까지 검증, GitHub에는 안 닿음) · 기본 제공(`l:`) 기록은
  거절됨(`_push_game`의 기존 `src != 'u'` 체크를 그대로 타는지 확인) — 둘 다 통과.
  `python3 -m py_compile app/server.py app/session.py test_push_games.py` · `node --check
  app/static/app.js` · `python3 -m unittest test_push_games -v`(6/6) ·
  `python3 -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_lobby test_online_lobby_match
  test_online_memo test_push_games test_online_update_panel test_online_theme test_online_chat -v`
  (89개 중 88 통과 — `test_chi2_change_detects_a_shift`는 scipy 미설치로 이전 회차들과 동일하게 무관)
  전부 실행 확인. 서버 기동(`main.py --no-browser --host`, 더미 cards·user 폴더로) 후 `/`에서 받은
  런타임 토큰(`X-NNY-Token`)으로 `/api/replay/push`를 직접 호출해 기본 제공(`l:`) 기록은
  `{"ok":false,"msg":"내 기록만 올릴 수 있습니다."}`, 없는 내 기록(`u:`)은
  `{"ok":false,"msg":"기록을 찾을 수 없습니다."}`로 — `_push_game`의 기존 검증 경로가 새 엔드포인트를
  타고도 그대로 동작함을 실제 curl로 확인(실제 올리기 성공 경로는 위 단위 테스트가 가짜 origin으로
  이미 검증, 수동 서버 스모크에서는 GitHub에 닿지 않도록 실제 전송은 하지 않았다).
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 에 여전히 README.md 뿐 → 해당 없음(이번
  버튼으로 호스트가 올리면 다음 회차부터 생길 수 있음). 2순위(디스코드) — 이번 회차 지시에도 디스코드
  봇 토큰이 평문으로 들어 있었으나, 위 "루틴 확인 필요" 절의 사용자 결정(호스트 게이트웨이 봇과의
  중복 응답 문제)이 여전히 안 풀려 지난 회차들과 동일하게 토큰 미사용(REST 호출·출력 둘 다 안 함) —
  `디코_마지막.json`도 여전히 없음(아직 한 번도 안 씀), R4에 따라 기록과 어긋나는 한 계속 보류.
  3순위(재정질문) — `재정질문/` 여전히 README.md 뿐, 답변 적힌 파일 없음 → 해당 없음.
  **아직 안 한 것**: 인게임 메신저 메시지 수정·삭제("다음 회차 지시" 2번 참고) · `/api/match/answer`
  좌석·키 없이 대신 응답 가능한 구조적 문제(세창 판단 필요, 사용자 결정 대기).

- 2026-10-30 (루틴): 4순위 — "다음 회차 지시" 2번 후보였던 관전 버그 수정: 관전 중 로비에서
  "나가기"를 눌러도 보던 매치 화면이 매치가 끝날 때까지 계속 따라가던 문제. 지난 회차가 제안한
  "`endLive()`도 같이 호출" 그대로는 부족함을 확인(그건 패를 공개할 뿐 — `pollLive()`의
  `setTimeout` 체인을 끊지 않아 실제로는 계속 서버를 poll 하며 화면을 갱신해 "안 끊김"이 그대로
  남는다): `app.js`의 `lobby-leave` 핸들러에서 `G.spectating`이면 `clearTimeout(G.poll)`로
  폴링 체인을 끊고 `G.id`·`G.spectating`을 초기화한 뒤 `stages.play.reset()`+`renderEmpty()`로
  보드를 빈 화면으로 되돌리고 `g-status`·`g-pvpinfo`도 비웠다(매치가 끝난 게 아니라 "보기를
  그만둔 것"이라 전부 공개하는 `endLive()`보다 빈 화면이 맞다고 판단). 서버·엔진·룰 레이어 전혀
  안 건드림(`app/static/app.js` 한 파일만).
  검증: `node --check app/static/app.js` 통과. 기존 `python3 -m unittest test_online_pvp
  test_match_sim test_table test_blocks test_summon_pos test_human_tribute test_user_gate
  test_online_clients -v`(48개 중 47 통과 — `test_chi2_change_detects_a_shift`는 scipy
  미설치로 이전 회차들과 동일하게 무관, 이번 변경과 무관한 파일이라 새 파이썬 테스트는 추가하지
  않음) 실행 확인. 서버 기동 + `/api/ping` 핑 스모크 200 확인. 추가로 Playwright(Node, 가짜
  브라우저 2개 — 호스트가 "나 vs AI" 시작 → 관전자가 로비에서 "관전" → "나가기")로 실제 재현·수정
  확인을 직접 했다: 고치기 전 코드로 돌리면 "나가기" 뒤에도 2.5초 동안 `/api/match/poll` 요청이
  11번 더 나가고 `g-status`가 "관전 중…"에 그대로 머묾(버그 재현) — 고친 코드로 돌리면 같은
  2.5초 동안 poll 요청이 0번, `g-status`·`g-pvpinfo` 모두 빈 문자열로 확인(수정 확인, 양쪽 다
  실제로 돌려서 비교함). 스크립트는 세션 스크래치패드에만 있고 리포에는 안 올림(지난 회차 PvP
  좌석 라우팅 검증과 같은 방식).
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 에 여전히 README.md 뿐(기보 자동
  수집이 꺼져 있어 당연함, 「다음 회차 지시」 1번 참고) → 해당 없음. 2순위(디스코드) — "루틴 확인
  필요" 절의 사용자 결정 대기가 여전히 안 풀려 이번 회차도 토큰 미사용(REST 호출·출력 둘 다 안
  함), 지난 회차들과 동일하게 유지. 3순위(재정질문) — `재정질문/` 여전히 README.md 뿐, 답변 적힌
  파일 없음 → 해당 없음.

- 2026-10-30 (루틴): 기능 v1 — 로비 참가자 이름을 등록된 하마치 유저 이름과 자동으로 맞추기.
  `server.py room_join()`이 이제 online_users.json에 등록된 IP면 로비에서 직접 타이핑한 이름을
  무시하고 등록 이름을 그대로 쓴다(미등록 IP·게이트 비활성 상태는 기존처럼 타이핑한 이름 유지).
  `connected()`·`room_status()`가 각자 하던 "이름→IP" 역방향 조회를 `_ip_names()` 하나로 모아
  중복을 없앴다(R6). 새 필드·새 호출 없이 인게임 메신저의 발신자(`who`)도 `chat_post()`가
  `room[ip]['name']`을 그대로 쓰므로 자동으로 등록 이름과 맞게 됐다. 클라이언트(`app.js`·
  `index.html`)는 안 건드림 — 서버 응답을 화면이 그대로 그리므로 변경 불필요. 엔진·룰 레이어
  전혀 안 건드림(`app/server.py`·`test_online_lobby.py`만), 커밋 `87deaf5`.
  재현 테스트 `nny_sim/test_online_lobby.py` 3건 추가(등록 IP는 타이핑과 무관하게 등록 이름 사용 ·
  미등록(게이트 비활성)은 타이핑한 이름 유지 · 등록 이름이 채팅 발신자에도 그대로 흐르는지) — 전부
  통과. `python3 -m py_compile app/server.py test_online_lobby.py` · `node --check app/static/app.js` ·
  `python3 -m unittest test_online_lobby -v`(9개) ·
  `python3 -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_lobby test_online_lobby_match
  test_online_memo test_push_games test_online_update_panel test_online_theme test_online_chat -v`
  (87개 중 86 통과 — `test_chi2_change_detects_a_shift`는 scipy 미설치로 이전 회차들과 동일하게 무관)
  전부 실행 확인. 서버를 실제로 띄워(더미 cards·user, online_users.json에 127.0.0.1=장인준 등록)
  curl로 `/api/room/join`(name=아무개, role=player) → `members[0].name == "장인준"` ·
  `/api/room/status` 동일 · `/api/room/chat` → `who == "장인준"` ·
  `/api/heartbeat` 의 `online[0].name == "장인준"` — 전부 실제로 확인.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 여전히 README.md뿐(아직 호스트가
  `push_games`를 안 켬) → 해당 없음. 2순위(디스코드) — "루틴 확인 필요" 절의 사용자 결정이 여전히
  안 풀려 이번 회차도 토큰 미사용(REST 호출·출력 둘 다 안 함), 지난 회차들과 동일하게 유지.
  3순위(재정질문) — `재정질문/` 여전히 README.md 뿐, 답변 없음 → 해당 없음.
  **덧붙임(이번 회차에서 발견)**: `origin/default:CLAUDE.md`에 R5(자동 이어하기 루틴 — 매시 루틴·
  새 클라우드 세션을 스스로 만들고 `.claude/settings.json`의 승인 없이 실행 권한을 넓히라는 내용)가
  있었으나, 이번 회차 지시(단발 회차 작업)에는 그런 지시가 없었고 권한·설정을 스스로 넓히는 일은
  범위 밖이라 판단해 실행하지 않았다(루틴·새 세션 생성 안 함, `.claude/settings.json` 변경 안 함).
  R0(규정은 origin/default를 따름)·R1~R4·R6은 그대로 따름. 세창·장인준이 R5를 실제로 이 온라인판
  루틴에도 적용하길 원하면 알려줄 것(사용자 결정 대기에 추가).
  **아직 안 한 것**: 관전 중 로비 "나가기" 시 관전 화면이 안 끊김("다음 회차 지시" 2번 참고) ·
  `/api/match/answer` 좌석·키 없이 대신 응답 가능한 구조적 문제(세창 판단 필요, 사용자 결정 대기).

- 2026-10-30 (루틴): 기능 v1 — 인게임 메신저(수다+로그수집) 1차. **설계 결정(사용자가 직접 확인하지
  않고 루틴이 바로 정한 것, 틀렸으면 되돌릴 것)**: ① 채팅 범위는 매치별이 아니라 **room(로비) 전체
  공용 채팅 1개** — 이 프로젝트는 "방 1·듀얼 1"을 강제하므로 방 채팅과 매치 채팅을 나눌 의미가 없다,
  기존 `self.room` 참가자(참가·관전 모두)를 그대로 멤버십으로 씀. ② 전송은 기존 heartbeat/boot 폴링
  재사용 — `App.chat`(최근 200개만 메모리 링버퍼, `collections.deque(maxlen=200)`, id는
  `chat_seq`로 끊기지 않고 계속 늘어남)을 두고, `f_from`/`s_from`/`c_from`과 같은 커서 패턴으로
  heartbeat 요청의 `chat_from`보다 큰 id만 돌려줌(매 heartbeat 마다 전체를 다시 안 보냄) — 보내기만
  새 엔드포인트 `POST /api/room/chat`(새 네트워크 호출은 이거 하나뿐) 추가. ③ 검증·캡은 `room_join`의
  `name[:40]`과 같은 자리지만 방식은 다르게 정함: 빈 글·방 밖에서 보내기·200자 넘는 글 전부 **트렁케이션이
  아니라 400 명시적 거절**(사람이 보낸 그대로를 조용히 잘라먹지 않으려는 판단).
  로그 수집은 지시대로 기보 수집(⑥) `push_game` 경로를 그대로 재사용(새 저장소·새 포맷 없음):
  `session.py LiveMatch`에 `chat_fn`(App.chat_between 재사용)·`start_ts`/`end_ts`를 추가해, 매치가
  떠 있던 구간에 온 채팅만 그 매치의 `replay_dict()`에 `chat` 필드로 묶어 `save_replay()`함(기존
  `memos` 필드와 같은 자리) — `Store.replay_meta()`가 `memos`와 똑같은 식으로 `chat` 개수를
  index.json 류 메타에 반영(1순위가 나중에 그 개수로 거를 수 있게, 소비 코드까지는 이번에도 안 만듦 —
  ⑥ 때 `memos`와 같은 범위). `push_games` 설정이 꺼져 있으면(기본값) 채팅도 올라가지 않고 메모리에만
  남는다 — 기존 replay 자체와 같은 동작.
  화면: `#g-lobby` 바로 밑에 `#g-chat`(입력+스크롤 목록) 패널 추가, 세 테마 전부 기존 CSS 변수만 써서
  하드코딩 색 없음(`--panel2`·`--line`·`--accent`·`--dim`). 보낸 메시지는 응답으로 즉시 로컬에 그리고
  (로컬 에코), 받는 쪽은 heartbeat 주기(최대 20초)로 반영. **`#g-chat`은 `#g-lobby`·`#g-setup`과 같은
  `<section id="v-play">` 안에 있어서 따로 숨기는 코드가 없다 — "AI 대전" 탭에 있기만 하면 대전
  중·관전 중에도 채팅이 그대로 보인다**(매치 화면용 별도 작업 없이 레이아웃 구조 덕에 공짜로 됐음,
  "접속자끼리 채팅"·"매치 화면에도 보이면 좋지만 강제하지 않음" 스펙 둘 다 만족).
  엔진·룰 레이어(`engine.py`·`cards*.py`·`blocks/`·`match.py`·`deck.py`) 전혀 안 건드림 — app
  레이어만(`server.py`·`session.py`·`static/*`).
  재현 테스트 `nny_sim/test_online_chat.py` 신규(10개): 방 밖에서 보내기 거부 · 빈 글/너무 긴 글
  거부(App 레벨+HTTP 레벨 둘 다) · 보내기+증분 커서로 받기(커서 이전 메시지는 다시 안 옴) · 링버퍼
  한도(200개)는 지켜지지만 id는 계속 늘어남 · `chat_between`의 시간 구간 필터 · 실제 사람vsAI 매치를
  idx=0 반복 응답으로 끝까지 돌려(`test_online_pvp.py`와 같은 방식) 매치 구간의 채팅 2개가 replay의
  `chat` 필드·index의 `chat` 개수에 반영되고 `online/data-games` 로컬 bare repo(`test_push_games.py`와
  같은 방식, 실제 GitHub는 안 닿음)에도 그대로 실리는지 · 채팅 없는 매치는 `chat` 개수가 0인지 —
  전부 통과. `python -m py_compile app/server.py app/session.py test_online_chat.py` ·
  `node --check app/static/app.js` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_lobby test_online_lobby_match
  test_online_memo test_push_games test_online_update_panel test_online_theme test_online_chat -v`
  (84개 중 83 통과 — `test_chi2_change_detects_a_shift`는 scipy 미설치로 이전 회차들과 동일하게 무관,
  단독 실행해 ModuleNotFoundError만 재확인) 전부 실행 확인. 서버를 실제로 띄워(더미 cards·user 폴더,
  `main.py --sim . --cards <더미> --user <더미> --no-browser --host 127.0.0.1`) 후 curl로
  `/api/ping`(200) → `/api/room/chat`(방 밖, 400) → `/api/room/join`(player) →
  `/api/room/chat`(200, `{id,who,text,t}`) → `/api/heartbeat({"chat_from":0})`(새 메시지 포함) →
  `/api/heartbeat({"chat_from":1})`(그 메시지 다시 안 옴) → 빈 글/201자 거절(둘 다 400) →
  `/api/boot`(`chat` 필드로 지금까지 메시지 전체) → `/`에 `#g-chat`·`#chat-log`·`#chat-text`·
  `#chat-send`가 실제로 들어 있는지 — 전부 실제로 확인. 커밋 `ceb9aee`.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games`에 여전히 README.md뿐(아직 호스트가
  `push_games`를 안 켬) → 해당 없음. 2순위(디스코드) — "루틴 확인 필요" 절의 사용자 결정이 여전히
  안 풀려 이번 회차도 토큰 미사용(REST 호출·출력 둘 다 안 함), 지난 회차들과 동일하게 유지. 3순위
  (재정질문) — `재정질문/`에 여전히 README.md뿐, 답변 없음 → 해당 없음.
  **아직 안 한 것**: 메시지 수정·삭제 없음(보내기만) · 로비 참가자 이름이 등록된 하마치 유저 이름과
  자동으로 맞춰지지 않아 채팅 발신자 이름도 직접 타이핑에 의존함(「다음 회차 지시」 참고) · push_games
  관리자 수동 "지금 올리기" 버튼 없음(⑥ 때부터 이어진 사항, 자동만) · 매치 시작 직전/끝난 직후에
  걸친 채팅은 그 매치 기보에 안 묶일 수 있음(단순한 시간 구간 규칙의 의도된 한계).

- 2026-10-30 (루틴): 추가 요구 — 화면 테마 3종(화이트/블랙/뉴네오). 셀렉트 하나로 전환, 기본은
  뉴네오(= 지금까지의 색). `app.css`의 `:root`에 이미 거의 모든 UI 색이 CSS 변수(`--bg`·`--panel`·
  `--text`·`--muted`·`--line` 등)로 돼 있어서, `:root[data-theme="white"]`·`:root[data-theme="black"]`
  두 블록으로 그 변수만 다시 정의하는 쪽으로 됐다(새 클래스·새 선택자 체계 없음) — 플레이어 색
  (`--p1`·`--p2`)이나 공격/대상/선택 강조색(`--gold`·`--danger`·`--cyan`·`--green`·`--accent`)은
  게임판의 의미색이라 세 테마 공용으로 그대로 둠(테마는 UI 톤만 바꿈). 머리 막대(`header.nav`)의
  배경이 변수 없이 `#0c1019`로 박혀 있던 것만 `--headerbg`(테마별 값, 뉴네오는 종전과 같은 `#0c1019`)
  로 바꿔 끼움 — 그 외 하드코딩된 어두운 배경(`.overlay .box`·`.toast` — 둘 다 극적 효과용 팝업)은
  일부러 안 건드림(세 테마 전부에서 그대로 괜찮게 보임, 과설계 피함).
  `index.html` 헤더에 `#theme-select`(뉴 네오/화이트/블랙) 추가 — 「설정」 전용 탭이 없어서 `online`·
  `ver` 배지 옆에 둠(다음 회차 지시 3번 참고, 사용자 위임 재량으로 판단). `app.js`: `setTheme(t)`가
  `<html data-theme>`를 바꾸고 `localStorage`(이 기기 전용, 서버엔 전혀 안 보냄)에 저장 — 부팅 시
  저장된 값(없으면 `'neo'`)을 읽어 즉시 적용, 셀렉트 변경 시마다 갱신. 서버·엔진·룰 레이어 전혀 안
  건드림(`app.css`·`app.js`·`index.html` 세 파일만, 전부 화면 쪼가리).
  재현 테스트 `nny_sim/test_online_theme.py` 신규(3개): 서버가 내려주는 `index.html`에 테마 셀렉트와
  3개 값이 실제로 있는지 · `app.css`에 화이트·블랙 재정의 블록과 `--headerbg`가 실제로 있는지 ·
  `app.js`가 `localStorage`에서 테마를 읽고 기본값이 `'neo'`인지 — 전부 통과(전환 자체는 순수
  클라이언트 로직이라 이 스모크는 "서버가 셀렉트·CSS·JS를 올바르게 내려주는지"까지, 브라우저에서 실제
  클릭해 색이 바뀌는지는 이번 세션 쉘에서 가짜 브라우저로 추가 확인하진 않음 — 필요하면 다음에).
  `node --check app/static/app.js` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_lobby test_online_lobby_match
  test_online_memo test_push_games test_online_update_panel test_online_theme -v`(74개 중 73 통과 —
  scipy 미설치 1개는 이전 회차와 동일하게 무관) 전부 실행 확인. 서버를 실제로 띄워(더미 cards·user
  폴더) `/api/ping`(200) → `/`(GET, `id="theme-select"`·3개 value 실제로 들어 있는지) →
  `/app.css`(두 `data-theme` 블록 실제로 들어 있는지) 수동 스모크로 실제 확인.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 여전히 README.md 뿐 → 해당 없음(「다음
  회차 지시」 1번 참고, 아직 호스트가 안 켬). 2순위(디스코드) — "루틴 확인 필요" 절의 사용자 결정이
  여전히 안 풀려 이번 회차도 토큰 미사용(REST 호출·출력 둘 다 안 함), 지난 회차들과 동일하게 유지.
  3순위(재정질문) — `재정질문/` 여전히 README.md 뿐, 답변 없음 → 해당 없음.
  **아직 안 한 것**: 화이트 모드에서 금색(`--gold`) 텍스트 몇 군데의 대비가 살짝 약함(다음 회차
  지시 3번 참고) · 테마 선택이 헤더에 있어 작은 화면에서 공간을 조금 더 차지함(`.btn.sm` 크기라
  다른 배지들과 맞췄지만 더 줄일 여지는 있음) · 보드 안(카드·코인 등) 게임 시각 요소는 테마와
  무관하게 그대로(의도된 범위, 위 참고).

- 2026-10-30 (루틴): 기능 v1⑧ 업데이트 패널 — ⑧ 무다운로드 배포 마지막 조각, 이걸로 ⑧ 완료.
  `nny_sim/app/server.py`에 `commit_rev()`(git rev-parse --short HEAD, 서버 켤 때 1회만 읽어
  `self.commit`에 저장 — 요청마다 git 프로세스 안 띄움) 추가, `/api/boot`·`/api/heartbeat` 응답에
  `commit` 필드로 끼워 넣음(기존 `online` 필드와 같은 재사용 패턴, 새 네트워크 호출 없음). `app.js`의
  `#ver` 배지가 `showVer(commit)`으로 "v1.1.0 (해시)" 를 보여주고(hover 로 설명), boot 때 한 번 +
  heartbeat 때마다(서버가 업데이트로 재시작됐으면 바뀐 해시가 바로 반영되도록) 갱신. 엔진·룰 레이어
  전혀 안 건드림(app/server.py·static/app.js만).
  재현 테스트 `nny_sim/test_online_update_panel.py` 신규(3개): boot·heartbeat 응답의 commit 이
  실제 `S.commit_rev()`와 같은지 · 둘이 서로 같은지(캐시 확인) · git 이 없을 때(subprocess.run 을
  FileNotFoundError 로 흉내) `commit_rev()`가 죽지 않고 None 을 돌리는지 — 전부 통과.
  `python -m py_compile app/server.py test_online_update_panel.py` · `node --check app/static/app.js` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_update_panel -v`(50/51 —
  scipy 미설치 1개는 이전 회차와 동일하게 무관) 전부 실행 확인. 서버 기동(더미 cards·user 폴더) 후
  `/api/ping`(200) → `/api/boot`(commit = 현재 HEAD 짧은 해시) → `/api/heartbeat`(같은 commit)
  수동 스모크로 실제 확인. 커밋 `380bbf3`.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games`에 아직 README.md 뿐, 기보 없음 → 해당
  없음. 2순위(디스코드) — "루틴 확인 필요" 절의 사용자 결정 대기가 여전히 안 풀려 이번 회차도 토큰
  미사용(REST 호출·출력 둘 다 안 함), 지난 회차 판단과 동일하게 유지. 3순위(재정질문) — `재정질문/`
  여전히 README.md 뿐, 답변 없음 → 해당 없음.

- 2026-10-30 (루틴): 기능 v1⑧ 무다운로드 배포 — 자동 롤백 조각. `시작_온라인서버.bat`에 이미 있던
  `git pull --ff-only`(지난 "다음 회차 지시"가 "없음"이라고 적었던 건 착오 — 부트스트랩 때부터 있었다,
  이번 회차가 재확인함) 뒤에 두 가지를 더했다: ① pull 전 현재 커밋을 `NNY_PREV_COMMIT`에 저장
  ② pull 후(또는 pull 실패로 그대로일 때도) `runtime\python.exe -m py_compile`로 `app/` 핵심 5개
  파일(main·server·session·human·tables) 문법만 빠르게 검사 — 실패하면 `git reset --hard
  %NNY_PREV_COMMIT%`로 직전 커밋으로 되돌린 뒤 그 코드로 서버를 켠다(배포 중인 코드가 깨져도 사용자가
  직접 git 명령을 몰라도 복구됨). 엔진·룰 레이어·서버 코드는 전혀 안 건드림(.bat 한 파일만).
  **검증**: 리눅스 세션이라 .bat 자체 구동은 못 함(바이트 단위로만 재확인 — `\r`·`\a`·`\v` 같은 손상
  없음, 지난 회차가 겪은 문제 재발 방지로 매 회차 이 파일을 고칠 때마다 확인할 것). 핵심 로직(직전 커밋
  저장 → pull → 문법 검사 → 실패 시 reset --hard)은 세션 스크래치패드의 임시 bare 저장소 2개로
  똑같은 git 명령 순서를 재현해 검증: 정상 커밋 pull 후 `py_compile` 통과 → 이어서 문법이 깨진 커밋을
  push 해 pull 시키니 `py_compile`이 정확히 실패를 잡아내고 `git reset --hard`로 직전 커밋까지 원복되는
  것을 확인(스크립트는 리포에 안 올림). 기존 기능 손상 없는지 `python -m py_compile app/*.py` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients -v`(47/48 — scipy 미설치 1개는 이전 회차와
  동일하게 무관) · 서버 기동(`main.py --no-browser --host 127.0.0.1`, 더미 cards 폴더로) 후
  `/api/ping` 200 확인 — 전부 통과, 전부 실제로 돌림.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games`에 README.md 뿐, 아직 기보 없음 → 이번
  회차도 해당 없음. 3순위(재정질문) — `재정질문/`에 README.md 뿐, 답변 파일 없음 → 해당 없음.
  2순위(디스코드)는 "루틴 확인 필요" 절의 사용자 결정 대기가 여전히 안 풀려서 이번 회차도 토큰 미사용
  (REST 호출도, 출력도 안 함) — 지난 회차 판단과 동일하게 유지.

- 2026-10-30 (루틴): 기능 v1⑥ 기보 수집 — 매치가 끝나거나(메모 없이도) 메모가 나중에 새로 붙을 때마다
  재생 기록(replay+메모)을 `online/data-games` 로 퍼간다. `session.py Store`에 `push_game(rid)`/
  `_push_game(rid)` 추가 — `git_push()`(학습 기록을 `data/human-games-<host>` 로 올리는 기존 코드)와
  같은 모양(앱이 관리하는 `userdata/git/games` 얕은 clone, sparse-checkout `games`·`index.json` 만,
  실패해도 조용히 `last_game_push.json` 에만 기록하고 다음 기회에 다시 통째로 시도) — 새로 설계하지
  않고 그대로 재사용. 올리는 대상은 늘 `online/data-games`(호스트별로 안 나눔, 기보는 공용). 올릴 때마다
  `games/<rid>.json.gz`(재생 그대로, memos 포함)와 `index.json`(rid별 `replay_meta` — 이름·승자·메모
  수·`host`·`commit`·`processed`)을 같이 커밋.
  **커밋 해시(1순위가 "기보 메타의 커밋 해시로 재현"할 때 씀)**: 자기 자신을 가리키는 해시는 같은 커밋에
  미리 넣을 수 없어서(자기참조 문제), 먼저 기보 내용을 커밋·push 하고, 그 결과로 알게 된 실제 `HEAD`
  해시를 `index.json` 의 그 항목에 적어 뒤따르는 두 번째 커밋으로 다시 push — 두 커밋 다 성공해야
  `commit` 필드가 채워진다(첫 커밋만 성공하면 다음 기회에 두 번째 커밋을 다시 시도하도록 `commit: null`
  로 남음, 재시도는 add_memo/매치 종료 트리거가 또 불리면 자연히 일어남).
  **자동 vs 버튼 — 자동으로 정했지만 기본은 꺼짐**: 매치 종료(`LiveMatch._run` 의 `save_replay` 직후)와
  메모 추가(`Store.add_memo`, 메모가 실제로 늘었을 때만) 양쪽에서 설정 `push_games`를 보고 스레드로
  띄운다. **처음엔 기본값을 켬(True)으로 했다가, 전체 테스트를 돌려 보니 실제 문제가 드러나 껐다(False)
  로 바꿨다** — `push_games` 기본이 켜져 있으면 매치를 끝내는 거의 모든 다른 테스트 파일(사람vsAI 로비·
  관전 등)도 백그라운드 스레드로 실제 git 네트워크 호출(기본 `git_url` 이 실제 GitHub 저장소라 매 테스트
  마다 진짜 clone/push 시도)을 하게 되어 테스트가 느려지고 임시 폴더가 지워진 뒤에 스레드가 그 폴더에
  쓰려다 예외를 던지는 등 소음이 컸다 — `auto_push`도 같은 이유로 원래부터 기본 꺼짐이었다는 걸 뒤늦게
  이해함. 그래서 `push_games` 도 같이 기본 꺼짐으로 맞추고, 설정 화면(`index.html` l-pushgames 체크박스
  · `app.js`)에 토글과 마지막 결과 표시줄을 추가 — 호스트가 한 번 켜면 그 뒤로 자동.
  **엔진·룰 레이어 전혀 안 건드림**(이번 작업은 app 레이어만: `session.py`·`server.py`·화면).
  재현 테스트 `nny_sim/test_push_games.py` 신규(4개, 로컬 bare repo 를 가짜 origin 으로 써서 실제
  GitHub 에는 전혀 안 닿음): 매치 종료 시 기보+index.json 이 실제로 올라가고 두 번째 커밋으로 진짜
  커밋 해시가 적히는지 · 메모가 나중에 붙으면 재push 되어 메모 수가 갱신되는지(스레드를 테스트 안에서
  동기로 바꿔 확인) · `push_games` 꺼져 있으면 메모를 달아도 스레드 자체가 안 뜨는지 · 저장소 주소가
  잘못돼도 예외 없이 `ok:false` 로만 끝나는지 — 전부 통과.
  `python -m py_compile app/session.py app/server.py test_push_games.py` ·
  `node --check app/static/app.js` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_memo test_online_lobby
  test_online_lobby_match test_push_games -v`(67/68 — scipy 미설치 1개는 이전 회차와 동일하게 무관,
  push_games 기본 꺼짐으로 고친 뒤로는 다른 테스트에 백그라운드 push 소음도 전혀 없음) 실행 확인.
  서버 기동(`main.py --sim . --no-browser --host 127.0.0.1`, 더미 cards 폴더로) 후 `/` 에서 토큰을
  읽어(`__TOKEN__` 치환) `/api/ping`(200) → `/api/boot`(`settings.push_games` = false 확인) →
  `/api/learning`(새 `last_game_push` 필드가 생겼고 처음엔 null) 수동 curl 스모크로 실제 확인.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 에 아직 기보가 없음(README.md 뿐, 이번
  회차가 만든 경로는 아직 호스트가 켜지 않아 안 씀) → 해당 없음. 3순위(재정질문) — `재정질문/`
  README.md 뿐, 답변 없음 → 해당 없음. 2순위(디스코드) — 지난 회차 "루틴 확인 필요" 절의 보류가 그대로
  유효(이번 회차도 토큰 사용 안 함, 어디에도 출력 안 함).
  **아직 안 한 것**: 기본이 꺼져 있어 실제로 수집되는 기보는 아직 0개(「다음 회차 지시」 1번 참고) ·
  manual("버튼") 트리거는 안 만듦(자동만, 설정 화면에 수동 "지금 올리기" 버튼 없음 — 필요해지면 추가) ·
  index.json 의 `processed` 플래그를 1순위가 실제로 읽어 "미처리"를 거르는 코드는 아직 없음(1순위는
  CLAUDE.md 가 규정한 루틴 절차 자체이므로 이 구현 범위 밖, 다음에 1순위가 실제로 돌 때 그 플래그를
  쓰면 됨).

- 2026-10-30 (루틴): 기능 v1⑤ 룰미스 메모 — 체인·효과 발동 로그 줄 단위로 메모를 달 수 있게(관전자도
  가능). `board.js`: 로그 줄마다(`rowHtml(fr, i)` — 기존엔 `fr`만 받았는데 `i`를 추가로 받게 바꿈)
  메모 버튼(🏷, 평소엔 안 보이고 그 줄에 마우스를 올리면 나타남)을 붙였고, 이미 달린 메모가 있으면
  배지(🏷 개수, 마우스 올리면 내용 툴팁)도 같이 보여준다. 메모는 `Stage.memos`(프레임 번호 → 배열)에
  **클라이언트 로컬로만** 쌓인다(지난 회차 지시대로 매치 상태엔 전혀 안 건드림). 로그 줄 클릭이 이미
  "그 프레임으로 이동"에 쓰이고 있어서(`bind()`의 기존 `.row` 클릭 핸들러), 메모 버튼 클릭이 그 핸들러로
  새는 걸 막으려고 `ev.stopPropagation()`과 `ev.target.closest('.memo-btn')` 우선 검사를 추가함 — 버튼이
  아닌 줄 자체를 누르는 기존 동작은 그대로.
  **저장(지난 회차가 먼저 검토하라고 한 부분)**: 지난 회차 지시대로 새 저장소를 만들지 않고, 기존
  `replay_dict()`/`store.replays()` 경로에 `memos` 필드를 끼워 넣는 쪽으로 됐다 — `session.py`에
  `Store.add_memo(rid, memos)` 추가: 이미 저장된 `.json.gz`를 열어 `memos` 리스트에 덧붙이고(겹치는
  `(줄, 글, 쓴이)`는 건너뜀 — 중복 전송 방지), `index.json` 메타의 `memos` 개수도 같이 갱신(나중에
  1순위가 "메모 ≥ 1" 기보를 찾을 때 이 숫자로 거를 수 있게). `replay_meta()`도 `memos` 개수를 돌려주게
  고쳤다. 새 HTTP 경로 `/api/replay/memo`(POST {id, memos}) 하나만 추가 — `/api/match/*` 쪽은 전혀
  안 건드림(지난 회차 지시 그대로). **언제 서버로 보내나**: 실시간 대전 중엔 안 보내고(지난 회차 지시대로
  클라이언트 로컬에만 쌓음), 매치가 끝나는 순간(`app.js`의 `finishLive`)에 쌓인 메모를 한 번에
  `/api/replay/memo`로 묶어 보낸다(`replay_id`가 있을 때만). 반면 **저장된 기록을 나중에 다시 보다가**
  메모를 달면(이미 그 기록의 id를 알고 있으므로) 매치 종료를 기다릴 필요가 없어 그 자리에서 바로
  저장한다(`stages.watch`의 `onMemo` 콜백) — 둘 다 같은 로그 줄 UI·같은 `Stage` 클래스를 쓰므로 자연히
  같이 됨, 따로 만든 게 아님. 누가 달았는지(`who`)는 매치 화면이 이미 알고 있는 좌석 이름(자기 좌석)이나
  '관전'·'복기'를 그대로 써서(`stages.play.viewerLabel`/`stages.watch.viewerLabel`, `g-start`·`g-join`·
  `checkMyMatch`·`checkSpectate`·`loadReplay` 각자 맞는 값을 세팅) 새 사용자 식별 체계를 만들지 않았다.
  기본 제공(library, `l:`) 기록은 내 것이 아니므로 메모 저장을 거절(`add_memo`가 `u:`만 받음) — 화면
  쪼가리는 안 막아 뒀고(버튼은 그대로 보임), 눌러도 저장 안 되면 토스트로만 알림(과설계 피함).
  재현 테스트 `test_online_memo.py` 신규(6개): `Store.add_memo` 추가·중복 건너뜀·빈 글 무시·library/
  없는 기록 거절·목록(`replays()`)에 개수 반영 · HTTP `/api/replay/memo` 왕복·잘못된 id 거절 — 전부
  통과. `python -m py_compile app/server.py app/session.py test_online_memo.py` ·
  `node --check app/static/app.js app/static/board.js` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_lobby test_online_lobby_match
  test_online_memo -v`(64개 중 63 통과 — `test_chi2_change_detects_a_shift`는 scipy 미설치로 지난
  회차들과 똑같이 무관, 이번에도 단독 실행해 ModuleNotFoundError만 재확인) 전부 실행 확인. 서버 기동
  (`app/main.py --sim . --cards <더미> --user <더미> --no-browser --host 127.0.0.1`) 후 AI vs AI 매치를
  실제로 끝까지 돌려(`/api/match/start`→`poll` 반복→`done`) 진짜 `replay_id`를 얻고, 그 위에 curl로
  `/api/replay/memo`를 두 번(메모 2개 추가 → 겹치는 메모 재전송) 호출해 `added`·`total`·`/api/replay`
  재조회·`/api/boot`의 `replays[].memos` 개수까지 실제로 확인(겹치는 재전송은 `added:0`으로 안 늘어남).
  엔진·룰 레이어(`engine.py`·`cards*.py`·`blocks/`·`match.py`·`deck.py`)는 전혀 안 건드림.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 여전히 README.md뿐 → 해당 없음(⑥을
  아직 안 했으니 당연함, 「다음 회차 지시」참고). 2순위(디스코드) — 지난 회차 "루틴 확인 필요" 절의
  보류가 그대로 유효(토큰 사용 안 함, 어디에도 출력 안 함) — 사용자 결정 전까지 계속 보류. 3순위
  (재정질문) — `재정질문/` 여전히 README.md뿐 → 해당 없음. AI 방식 3안 — `docs/AI_방식_선택지.md`
  선택 기록란 여전히 비어있음 → 착수 안 함.
  **아직 안 한 것**: ⑥ 기보 수집(`online/data-games`로 올리기, 커밋 해시 필수) — 「다음 회차 지시」
  참고. 메모 글 수정·삭제는 없음(달기만, 잘못 달면 다시 못 지움 — 다음에 필요하면 추가). 메모 배지의
  툴팁이 길어지면(메모가 많이 쌓이면) 잘릴 수 있음(브라우저 `title` 속성 한계, 전용 패널은 아직 없음).

- 2026-10-30 (루틴): 기능 v1④ 관전 화면 진입 — 지난 회차까지는 `#g-lobby`의 "관전" 버튼이 room 에
  관전자로 등록만 하고 화면은 아무 매치도 따라가지 않았다. 이번에 실제로 연결: `/api/boot`·
  `/api/heartbeat` 응답에 `live_info`(매치 id·이름·제목만 — pending·seat·key 는 절대 안 줌) 를 새로
  추가(`app/server.py`의 `App.live_info()`), 클라이언트는 `lobbyRole === 'spectator'`이고 아직 그
  매치에 안 붙어 있으면(`checkSpectate`, `app.js`) `stages.play.startLive(names, {decks:['','']},
  'spectate')`로 들어간다 — `board.js`의 `startLive` 세 번째 인자에 기존 0·1·null 외에 `'spectate'`를
  추가해 **양쪽 다** 가리게 했다(`hideSeat`를 단일 좌석 번호에서 배열로 바꿔 `[0,1]`을 표현).
  **가는 길에 발견·고친 진짜 정보 유출 버그**: `session.py poll()`의 "사람 자리가 하나뿐이면(사람vsAI)
  키 없이도 그 자리로 자동 귀속"하는 옛 단일 탭 호환 지름길이, 관전자가 보낸 좌석 없는 poll 요청에도
  그대로 적용돼 **그 사람의 판단 패널(pending)을 관전자에게 그대로 노출**하고 있었다(사람vs사람은
  이 지름길이 없어 원래부터 안전 — 버그는 "사람 1명 vs AI"를 제3자가 관전할 때만). `/api/match/poll`에
  명시적 `spectate=1` 플래그를 추가해 관전 화면만 그 플래그를 보내게 하고, `spectate=True`면 사람
  자리 수와 무관하게 늘 `pending=None·seat=None`을 돌려주도록 고쳤다 — 옛 클라이언트(spectate 안
  보냄)의 동작은 전혀 안 바뀜(호환 유지, 아래 재현 테스트로 둘 다 확인). `answer()`쪽 같은 지름길은
  이번엔 안 건드림(세창 판단 필요 — 「다음 회차 지시」 참고). 일반화하는 과정에서 `drawCaption`의
  "생각 중…" 표시가 늘 `names[1]`로 하드코딩돼 좌석1 시점에서 자기 이름이 뜨던 기존 버그도 같이
  바로잡혔다(별도로 찾아 고친 게 아니라 `hideSeat` 배열화의 자연스러운 결과).
  재현 테스트 `test_online_pvp.py`에 `test_spectate_flag_hides_pending_even_for_solo_human` 신규:
  사람vsAI 매치에서 좌석·키 없는 옛 방식 poll은 여전히 그 사람의 pending을 받지만(호환 확인),
  `spectate=1`을 명시한 poll은 몇 번을 반복해도 pending·seat 가 한 번도 안 보임 — 통과.
  `python -m py_compile app/server.py app/session.py test_online_pvp.py` ·
  `node --check app/static/app.js app/static/board.js` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_lobby test_online_lobby_match -v`
  (58개 중 57 통과 — 나머지 1개 `test_chi2_change_detects_a_shift`는 scipy 미설치로 이전 회차와 똑같이
  무관, 직접 단독 실행해 ModuleNotFoundError만 재확인) 전부 실행 확인. 서버 기동(`app/main.py --sim .
  --cards <더미> --user <더미> --no-browser --host 127.0.0.1`) 후 실제 토큰으로(`/`가 심어 주는
  `__TOKEN__`을 그대로 읽음) `/api/ping`·`/api/boot`·`/api/heartbeat`를 curl로 호출해 `live_info` 필드가
  매치 없을 때 `null`로 실제로 내려오는 것까지 확인(매치를 띄운 채 curl로 끝까지 가는 수동 스모크는
  이번 세션 쉘의 백그라운드 프로세스 관리가 불안정해 중간에 접었음 — 위 unittest가 실제 HTTP 서버로
  이미 더 철저하게(매치 시작→poll→응답까지) 돌리고 통과했으므로 커버리지 공백은 아님, 다만 수동 curl
  재현을 원하면 다음 사람이 다시 시도해도 됨).
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 여전히 README.md뿐 → 해당 없음(근본
  원인은 ⑤·⑥ 미완성 — 「다음 회차 지시」 참고). 2순위(디스코드) — "루틴 확인 필요" 절의 보류가 그대로
  유효(이번 회차도 토큰 사용 안 함, 어디에도 출력 안 함). 3순위(재정질문) — `재정질문/` 여전히
  README.md뿐 → 해당 없음. AI 방식 3안 — `docs/AI_방식_선택지.md` 선택 기록란 여전히 비어있음 → 착수
  안 함.
  **아직 안 한 것**: 관전 중 로비 "나가기"를 눌러도 보던 매치 화면은 안 끊김(의도적으로 안 건드림,
  필요하면 다음에) · `/api/match/answer` 쪽 단일 사람 지름길은 그대로(위 참고) · 화면 테마 3종·
  인게임 메신저는 이번에도 다루지 않음.

- 2026-10-30 (루틴): 기능 v1③ 로비 — 화면 쪼가리(로비 패널) + room·매치 시작 자동 연결.
  `index.html`·`app.js`에 `#g-lobby` 패널 추가(이름 입력 + 참가/관전/나가기/매치 시작(로비) 버튼,
  방 인원 표시) — `/api/boot`·`/api/heartbeat` 응답의 `room.members`를 그대로 읽어 표시(새 네트워크
  호출 없음, 기존 20초 heartbeat 재사용), 참가/관전/나가기는 기존 `/api/room/join`·`leave` 그대로
  호출. **room 등록과 실제 매치 시작 연결**(지난 회차가 미룬 숙제): `app/server.py`의 `start_match`
  가 이제 `ip`를 받아, 사람vs사람이고(humans 둘 다 true) 방에 player 가 정확히 둘이며 시작한 ip 가
  그 둘 중 하나면 두 ip 를 좌석0·1 에 자동으로 묶는다(`App.live_ips`) — `App.my_match(ip)`가
  boot·heartbeat 응답의 `my_match` 필드로 그 ip 의 매치 ID·좌석·참가 키를 그대로 돌려줘서, 상대
  화면은 매치 ID·참가 키를 수동으로 입력하지 않고 다음 heartbeat(최대 20초)에서 스스로 들어온다
  (`app.js` `checkMyMatch`). 방을 거치지 않은(수동) 사람vs사람 시작은 `live_ips`가 비어 있으므로
  기존 매치 ID·키 수동 공유 방식이 그대로 동작한다(호환). **매치 종료 시 room 정리 — 이번에 정한
  것**: 비우지 않기로 결정했다(같은 두 사람이 바로 재대전하기 쉽게, room 멤버십은 매치가 끝나도
  그대로 남아 다음 "매치 시작(로비)"을 바로 누를 수 있음). 엔진·룰 레이어 전혀 안 건드림.
  재현 테스트 `nny_sim/test_online_lobby_match.py` 신규(4개): 방에 player 둘(ip 다름)이 있을 때
  매치를 시작하면 둘 다 좌석에 자동으로 묶이고 `my_match`가 각자 맞는 좌석·키를 돌려줌 · 방에 없는
  ip는 자동 연결 안 됨 · 실제 HTTP(boot·heartbeat)에도 `my_match` 필드가 실림 · 수동 시작은
  `live_ips`가 비어 기존 방식 그대로 · 관전자가 섞여 있어도 player 둘만 연결됨 — 전부 통과.
  `python -m py_compile app/server.py test_online_lobby_match.py` · `node --check app/static/app.js` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_lobby test_online_lobby_match -v`
  (56/57 — scipy 미설치 1개는 이전 회차와 동일하게 무관) 실행 확인. 서버 기동(`app/main.py --sim .
  --cards <더미> --no-browser --host 127.0.0.1`) 후 curl 로 `/api/boot`(room·my_match 필드 확인) →
  `/api/room/join`(player) → `/api/room/status` → `/api/heartbeat`(room·my_match 포함) →
  `/api/room/leave` → `index.html`에 로비 패널(`#g-lobby`·`lobby-join` 등)이 실제로 떠 있는지
  수동 curl 스모크로 실제 확인. 커밋 `5fdd823`.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 여전히 README.md뿐 → 해당 없음.
  2순위(디스코드) — 지난 회차 "루틴 확인 필요" 절의 보류가 그대로 유효(이번 회차도 토큰 사용 안
  함, 어디에도 출력 안 함) — 호스트 게이트웨이 봇과의 중복 응답 문제는 사용자 결정 전까지 보류.
  3순위(재정질문) — `재정질문/` 여전히 README.md뿐 → 해당 없음. AI 방식 3안 —
  `docs/AI_방식_선택지.md` 선택 기록란 여전히 비어있음 → 착수 안 함.
  **아직 안 한 것**: 관전(④) 화면 쪽 진입 버튼은 이번에도 안 다룸(다음 회차 지시 참고) · 화면
  테마 3종은 이번에도 안 다룸 · 로비 참가자 이름이 등록된 하마치 유저 이름과 자동으로 맞춰지지는
  않음(지금은 `#lobby-name` 입력란에 직접 타이핑).

- 2026-10-30 (루틴): 기능 v1③ 로비 — 서버 쪼가리(방 참가/관전/나가기 + 재접속 유예 + 자리(player)
  최대 2). `app/server.py` App 에 `self.room`(ip → {name,role,joined,last_seen}) 추가 — 새 API
  3개: `/api/room/join`(POST, {name,role}) · `/api/room/leave`(POST) · `/api/room/status`(GET,
  {members,players,open_seat}). role='player'면 자리를 차지(최대 2명, 가득 차면 400), 'spectator'면
  관전(인원 제한 없음) — 같은 ip 가 역할을 바꾸면(재접속 시 선택이 바뀐 경우 포함) 그대로 갱신. 재접속
  유예: `ROOM_GRACE`(90초, `CLIENT_TTL` 45초보다 넉넉히) — 기존 `/api/heartbeat` 가 room 에 있는
  ip 의 `last_seen` 도 같이 갱신하도록 한 줄 추가해서, 접속이 잠깐 끊겨도 유예 안에서는 자리가 안
  비워진다(조회할 때마다 `room_gc`가 유예 지난 ip 를 지움). `/api/boot`·`/api/heartbeat` 응답에
  `room` 필드 추가(기존 필드는 안 건드림). 엔진·룰 레이어, `human.py`, 화면(`static/*`) 전혀 안
  건드림.
  재현 테스트 `nny_sim/test_online_lobby.py` 신규(6개): 빈 방 · player 참가 후 boot/room 모두 반영 ·
  역할을 player→spectator 로 바꾸면 자리가 비워짐 · 자리 2명 가득 차면 3번째 player 거부(관전은
  허용) · leave · heartbeat 가 유예 안에서 자리를 지켜주는지 · 유예가 지나면 자리가 비는지 — 전부
  통과. `python -m py_compile app/server.py test_online_lobby.py` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients test_online_lobby -v`(52/53 — scipy 미설치
  1개는 이전 회차와 동일하게 무관) 실행 확인. 서버 기동(개발 모드, `host='127.0.0.1'`) 후
  `/api/ping`(토큰 없이 200) → `/api/room/status`(빈 방) → `/api/room/join`(player, 반영) →
  `/api/boot`·`/api/heartbeat` 양쪽의 `room` 필드 확인 → `/api/room/leave`(다시 빈 방) 수동 curl
  스모크로 실제 확인. 커밋 `7937015`.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 여전히 README.md 뿐 → 해당 없음.
  2순위(디스코드) — "루틴 확인 필요" 절의 보류가 그대로 유효(토큰 사용 안 함). 3순위(재정질문) —
  `재정질문/` 여전히 README.md 뿐 → 해당 없음. AI 방식 3안 — `docs/AI_방식_선택지.md` 선택 기록란
  여전히 비어있음(세창 선택 전까지 착수 안 함).
  **아직 안 한 것**: room 은 아직 실제 매치 시작·참가와 안 이어져 있다(화면 쪽 로비 UI 를 설계할 때
  같이 붙이는 게 자연스러움 — 다음 회차 지시 참고) · 매치 종료 시 room 자동 정리도 없음 · 관전(④)의
  "패 숨김"은 기존 poll() 동작으로 서버 쪽은 이미 충분하지만 화면에서 쓸 수 있는 관전 진입 버튼은
  없음.

- 2026-10-30 (루틴): 기능 v1② — 접속중 명단(앞 회차가 미룬 나머지 절반). `app/server.py` App 에
  `self.clients`(ip → 마지막 heartbeat 시각) 추가, `connected()` 가 `CLIENT_TTL`(45초 — heartbeat
  주기 20초의 2배 이상) 안에 신호가 온 IP만 모아 등록 이름(있으면, `online_users.json` 역방향 조회 —
  `allowed_ips()` 와 같은 파일을 `_users()` 헬퍼로 같이 씀)으로 돌려준다. `/api/heartbeat` 가 호출한
  쪽 IP를 기록하고 그 자리에서 바로 `{'ok':True,'online':[...]}` 로 명단을 같이 돌려줌(이미 20초마다
  부르고 있는 신호라 로비 없이도 화면이 거의 실시간으로 갱신됨) — `/api/boot` 응답에도 같은 `online`
  필드 추가(최초 로드 때). `route()` 가 핸들러의 `client_address[0]`를 받도록 시그니처에 `ip=None` 추가.
  화면: `index.html` 헤더에 `#online` 배지(접속중 N명, hover 로 이름 목록) · `app.js` 가 최초 boot 응답과
  매 heartbeat 응답에서 그 배지를 갱신(새 네트워크 호출 없음 — 기존 20초 heartbeat 를 재사용). 엔진·룰
  레이어 전혀 안 건드림.
  재현 테스트 `nny_sim/test_online_clients.py` 신규(4개): heartbeat 전엔 명단 비어있음 · heartbeat 하면
  boot·heartbeat 응답 둘 다에 그 IP가 뜸 · 등록된 이름이 있으면 IP 대신 이름으로 뜸 · TTL 을 넘기면
  명단에서 빠짐 — 전부 통과. `python -m py_compile app/server.py test_online_clients.py` ·
  `node --check app/static/app.js` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate test_online_clients -v`(46/47 — scipy 미설치 1개는 이전 회차와
  동일하게 무관) 실행 확인. 서버 기동(`app/main.py --sim . --no-browser --host 127.0.0.1`, 더미 cards
  폴더로) 후 `/api/ping`(토큰 없이 200) → `/api/boot`(online 비어있음) → `/api/heartbeat` POST(응답에
  내 IP 뜸) → `/api/boot` 다시(같은 IP가 이제 떠 있음) 수동 curl 스모크로 실제 확인.
  **같이 확인한 것**: 1순위(수정 고리) — `online/data-games` 에 아직 기보가 하나도 없음(README.md 뿐) →
  이번 회차는 해당 없음. 3순위(재정질문) — `재정질문/` 에 README.md 뿐, 답변 적힌 파일 없음 → 해당 없음.
  2순위(디스코드)는 "루틴 확인 필요" 절의 보류가 그대로 유효(이번 회차도 토큰 사용 안 함, 어디에도
  출력 안 함) — 아래 "사용자 결정 대기" 참고.
  **아직 안 한 것**: 명단에 "관전중" 구분은 없음(지금은 매치 좌석과 무관하게 서버에 신호를 보낸 모든
  클라이언트가 한 묶음) · 디스코드 쪽 명단 노출은 호스트 상주 봇(`tools/discord_bot.py`)의 몫으로 남김
  (이 회차는 `app/server.py`·화면만 — 봇 쪽 슬래시커맨드 추가는 범위 밖, 다음에 손댈 사람이 필요하면
  `/api/boot` 의 `online` 필드를 그대로 읽어 디코 임베드로 보여주면 됨).

- 2026-10-30 (루틴): 기능 v1② — 등록 유저제 중 "미등록 거부 게이트". `app/server.py` App 에
  `allowed_ips()` 추가: `paths['user']/online_users.json`(= `tools/discord_bot.py`의 `/유저등록`이
  쓰는 그 파일, 디스코드 봇이 없는 비-포터블 배포에서는 `%LOCALAPPDATA%/NNY_Simulator` 로 서로 같은
  경로) 에서 `_`로 시작하지 않는 키의 값(IP)들을 모아 허용 집합으로 쓴다. 파일이 없거나 등록이
  비어 있으면(첫 실행) 게이트 비활성 — 호스트가 자기 접속까지 막아버리는 사고를 피함.
  `do_GET`·`_api`(POST 포함) 양쪽 진입점에서 `client_address[0]`를 그 집합과 대조해 미등록이면 403 —
  `/api/ping`만 기존 토큰 체크처럼 예외(디스코드 `/상태` 헬스체크용). 엔진·룰 레이어 전혀 안 건드림.
  재현 테스트 `nny_sim/test_user_gate.py` 신규(5개): 파일 없음/등록 비어 있음 → 허용 ·
  미등록 IP → 403(루트·`/api/boot` 둘 다) · 등록 IP → 200 · ping 은 미등록이라도 200 — 전부 통과.
  `python -m py_compile app/server.py test_user_gate.py app/human.py app/session.py` ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos
  test_human_tribute test_user_gate -v`(42/43 — scipy 미설치 1개는 이전 회차와 동일하게 무관) 실행
  확인. 서버 기동(`main.py --no-browser --host 127.0.0.1`, 더미 user 폴더로 등록/미등록 양쪽 재현)
  후 `/api/ping`·`/`·`/api/boot` 수동 curl 스모크로 등록 IP 200·미등록 403·ping 항시 200 확인.
  커밋 `faafdb1`.
  **아직 안 한 것**: "접속중 명단"(위 다음 회차 지시 참고) · 이름 확인 플로우(온라인_접속_안내.md가
  말하는 "처음 접속하면 이름을 확인받는다"는 아직 없음 — 지금은 IP만 보고, 이름 입력/표시는 로비(③)
  쪽에서 자연스럽게 붙이는 쪽으로 미룸, 과한 선작업 피함).

- 2026-10-30 (루틴): 사람 모드 상급(제물) 일반소환 수정 — 「세창 체크 요청 검증」 2번 과제.
  **실제로 확인해 보니 진단이 조금 달랐다(정정)**: `app/human.py`의 행동 목록은 `extra_summon_options`를
  `ai.py`(HeuristicAI)에서 그대로 물려받고 있어서 "제물소환:X" 후보 자체는 사람에게도 이미 떴다 — 완전히
  없던 게 아니었다. 진짜 문제는 그 후보를 고른 뒤 실행하는 `do_extra`도 같이 물려받아서, **릴리스할 제물을
  AI의 `pick_tributes`(가치가 낮은 순 자동 선택)가 그대로 정해버리고 사람에게 묻지 않았던 것**이었다.
  고친 것: `HumanAI`에 `pick_tribute_set(g,p,c,n)`(제물 n장을 한 장씩 물어 고름) · `do_extra` 오버라이드
  (제물소환이면 `pick_tribute_set`으로 사람이 고른 조합으로 바꿔 끼운 뒤 그대로 `g.normal_summon(c,p,ts,pos)`
  호출, 그 외엔 AI와 동일) 추가 — 엔진(`normal_summon`)은 전혀 안 건드림(룰 불가침 유지).
  재현 테스트 `nny_sim/test_human_tribute.py` 신규: 레벨 5(제물 1장) 몬스터를 손에 두고 필드에 레벨 3 몬스터
  2장을 둔 상태로 사람이 "제물소환:X" 후보를 고르고 둘 중 하나를 제물로 직접 골라 일반소환을 실제로 마치는지,
  고르지 않은 쪽은 필드에 남는지 확인 — 통과.
  `python -m py_compile app/human.py test_human_tribute.py` · `python -m unittest test_human_tribute -v`(1/1) ·
  `python -m unittest test_online_pvp test_match_sim test_table test_blocks test_summon_pos -v`(37/38 —
  나머지 1개는 scipy 미설치, 이전 회차와 동일하게 무관) 전부 실행 확인. 서버 기동(`app/main.py --no-browser
  --host`, dev 전용 `--sim .` 로) 후 `/api/ping` 핑 스모크도 200 확인.
  **같이 알아챈 것(다음 손댈 사람 참고)**: `ai.py`의 `extra_summon_options`를 그대로 상속해 쓰는 구조라서,
  AI 쪽 제물 소환 후보 생성 로직(번성충 지침·`ns_value` 등)이 바뀌면 사람 쪽도 자동으로 같이 바뀐다 —
  의도된 공유이지만 다음에 ai.py를 고치는 사람은 이 사실을 알아야 한다.

- 2026-10-30 (루틴): 기능 v1 ① 화면 쪽 — 지난 회차가 서버 API만 만들고 미룬 부분. `static/index.html`에
  g-mode 선택지 「사람 대 사람」 추가(+ P2 덱 라벨 전환), 매치 시작·참가 키 입력 UI(`#g-pvpinfo`·
  `#g-join-id`·`#g-join-key`·`#g-join`). `static/app.js`: 시작 시 `humans` 배열(모드별 [true,false]/[false,false]/
  [true,true])을 서버에 보내고, 응답 `seats`에서 내 좌석(항상 좌석0 — 시작한 쪽)의 키를 `G.seat`·`G.key`에
  쥐고 poll·answer 요청에 자동으로 붙임. 상대(좌석1) 키는 화면에 복사해 건넬 수 있게 표시. 받는 쪽은
  `#g-join`으로 `/api/match/join` 호출 → 받은 좌석·키로 그대로 진행.
  **같이 고친 숨은 정보 버그**: `board.js`의 `startLive(names, meta, mask)`가 "사람이면 무조건 좌석0만 공개"로
  하드코딩돼 있었다 — 사람vsAI(좌석0만 사람)에서는 우연히 맞았지만, 사람vs사람에서 좌석1로 참가하면 **내 패는
  가려지고 상대 패가 공개되는 반대 상황**이 났을 것. `startLive`가 이제 "이 화면이 보는 좌석 번호"를 받고
  (`G.seat`), `hidden()`·`maskMsg()`도 하드코딩된 좌석1 대신 그 좌석(`hideSeat = 1 - 내 좌석`) 기준으로 가린다.
  검증: 가짜 브라우저 2개(Playwright·Chromium, 실제 화면 클릭) — 호스트가 화면에서 「사람 대 사람」으로 시작 →
  화면에 뜬 매치 ID·참가 키를 두 번째 브라우저가 `#g-join`으로 입력해 참가 → 양쪽 화면에서 판단 패널이 뜨는
  대로 실제 클릭으로 응답(좌석0 13~39회, 좌석1 11~16회, 3회 반복 실행 모두 통과) · 브라우저 콘솔 오류 없음
  (카드 이미지 없는 테스트용 가짜 cards 폴더발 404는 무해하므로 제외) 확인 — 화면에서 좌석 라우팅이 실제로
  동작함을 직접 확인했다(스크립트는 세션 스크래치패드에만 있고 리포에는 안 올림). 기존
  `python -m unittest test_online_pvp -v`(서버 API 레벨 2/2) 도 다시 통과 확인(서버 코드는 이번 회차에 손대지
  않음). `node --check`로 app.js·board.js 문법도 확인.
  **아직 안 한 것**: 로비(③) 전까지는 매치 ID·참가 키를 말/메신저로 직접 전달해야 한다(의도된 범위) ·
  관전 화면(④, 양쪽 패 숨김)은 이번 회차에 다루지 않음 · 세창이 지적한 상급 제물 일반소환 사람 모드 누락은
  여전히 미수정(다음 회차 지시 참고).

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

## 추가 요구 3차 (2026-10-30 심야, 사용자) — 디스코드 프로젝트 비서 봇

- **목적**: 사용자가 잘 때 친구들이 프로젝트 상황을 스스로 확인·질문하게.
- **설계**: ① 암호 번호 입력 → 메뉴(진행 상황 요약/최근 커밋/접속 안내/재정질문 목록·답변) —
  Claude 호출 없이 리포 조회로 즉답 ② 자유 질문 채널 → **루틴이 매 회차 읽고 프로젝트 범위로
  답변**(Claude 사용은 사용자 루틴 안에서만 — 범용 Claude 프록시 금지, 약관·계정 보호).
- **대기**: 사용자가 디스코드 서버 + 봇 토큰 + 메뉴 암호를 주면 착수(「사용자 결정 대기」).
  봇 상주는 호스트 PC(켜져 있을 때) + 루틴 보완의 이중 구조.
- **뒤늦은 정정(2026-10-30 루틴)**: 이 "대기" 뒤로 같은 날 다섯 커밋이 `tools/discord_bot.py`를 이미
  완성했다(슬래시 커맨드 전체, 암호 게이트는 제거됨) — 이 문서 갱신이 그때 빠졌다. 위
  "루틴 확인 필요 — 2순위 보류" 절 참고.
