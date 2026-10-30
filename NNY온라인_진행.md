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

로비(③) 화면 쪼가리(참가/관전/나가기 패널 + 방 인원 2명이 모이면 매치 시작 자동 연결) 완성
(바로 아래 완료 기록 참고, 커밋 `5fdd823`) — **다음은 관전(④) 화면 진입**: 지금 `#g-lobby`의
"관전" 버튼은 서버 쪽 room 에만 등록될 뿐 화면이 실제로 관전 모드로 들어가지는 않는다(poll() 이
좌석 없는 조회엔 이미 pending 을 안 주므로 패 숨김 자체는 서버 쪽에 이미 돼 있음 — 화면 연결만
빠져 있음). 방에 매치가 떠 있을 때(`/api/boot`·`/api/heartbeat` 의 `live`/`my_match` 로 알 수 있음)
관전 버튼을 누른 사람은 `stages.play.startLive(...)` 를 좌석 없이(또는 양쪽 다 가린 채) 호출해
그 매치를 따라가게 — `/api/match/poll` 은 이미 seat·key 없이 호출하면 관전처럼 동작한다(기존
`test_online_pvp.py` 의 관전 테스트 참고). 매치가 중간에 시작됐을 때 관전자가 처음부터가 아니라
중간부터 자연스럽게 따라붙는지(f/s/c 카운터를 0 부터 보낼 때 과거 프레임을 다 받아도 괜찮은지)도
같이 확인할 것. ⑤(룰미스 메모)·⑥(기보 수집)은 그 다음.

다음에 손댈 사람이 참고할 것(이번 회차에 일부러 안 건드림): 로비 참가자 이름이 등록된 하마치
유저 이름과 자동으로 맞춰지지 않음(지금은 `#lobby-name` 에 직접 타이핑) — 서버의 `_users()` 역방향
조회(이미 `connected()` 가 쓰는 그 패턴)를 `/api/room/join` 쪼가리에도 붙이면 자연스러움.

## 루틴 확인 필요 — 2순위(디스코드 질문 답변) 이번 회차 보류

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

## 사용자 결정 대기

- 친구들(세창 포함)의 하마치 IP — 받으면 online_users.json 에 추가
- 세창의 AI 방식 선택 (docs/AI_방식_선택지.md)
- 디스코드 루틴 답변(2순위) 토큰 사용 여부 — 위 "루틴 확인 필요" 참고

## 완료 기록

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
