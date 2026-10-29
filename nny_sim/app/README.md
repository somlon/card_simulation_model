# 뉴 네오 유희왕 시뮬레이터 — Windows 게임 프로그램 (app)

관전(재생 목록) · 나 vs AI 대전 · 덱 편집 · 사람 대전 학습을 하나로 묶은 싱글플레이 프로그램입니다.
엔진은 이 저장소의 시뮬레이터(`model/main`)를 그대로 쓰고, 화면은 로컬 서버(127.0.0.1)가 띄우는 웹 화면(Edge 앱 창)입니다.

## 사용자용

배포 zip(`NNY_Simulator_v<버전>_win64.zip`)을 풀고 `NNY_Simulator.exe` 를 실행합니다. 설명은 zip 안의 `읽어보기.txt`.

- **관전 · 재생 목록**: 기본 제공 AI 대전 녹화(11개 덱 55대진 + 10매치)를 골라 재생 목록을 만들고 이어서 재생(끝나면 다음 · 반복). 새 AI 대전 녹화.
- **AI 대전**: 나 vs AI(학습표 AI) Bo3 — 판단 패널에서 행동 · 대응 · 트리거 · 대상 · 서치 · 카드 고르기 · 멀리건 · 선후공을 고릅니다. AI vs AI 실시간 관전.
  대전 중에는 AI의 패 · 뒷면 카드 · 드로우한 카드 이름 · 판단 줄을 가리고, 끝나면 모두 공개(복기).
- **덱 편집**: 카드 풀(이미지)에서 덱을 짜고 `deck.validate` 규칙 검사 후 저장 → AI 대전 · 녹화에 사용.
- **학습**: 「AI 학습」을 켜고 대전하면, 매치가 끝날 때 AI와 사람의 판단 기록이 학습표에 더해집니다(아래).

## 학습 흐름 (사람 대전 → 저장소)

1. **프로그램 안(즉시, 인터넷 불필요)**: 대전 표(`tables.matchup_table`)의 갱신(`policy.Table.update` — L1 · L2 · L0)을 모아
   사용자 폴더 `learning/human_games.jsonl` 에 매치 1줄로 덧붙입니다(`id` 로 중복 방지). 다음 대전부터 불러올 때 다시 적용됩니다.
2. **GitHub 반영(인터넷 필요)**: 「학습」 화면의 「GitHub에 올리기」 또는 「대전이 끝날 때마다 자동으로 올리기」 —
   앱 전용 얕은 clone(사용자 폴더 `git/repo`, sparse)에 기록을 넣어 `data/human-games-<컴퓨터이름>` 브랜치로 커밋 · 푸시합니다(git · GitHub 로그인 필요).
   인터넷이 없을 때는 실패만 기록하고, 다음에 쌓인 기록을 통째로 다시 올립니다. 「내보내기」한 파일을 GitHub 웹에서 올려도 됩니다.
3. **저장소에서 합치기**: `merge_learning.py --policy <실행 폴더>/learned/policy.json.xz --logs <human_games 폴더>` —
   새 매치만 학습표에 더하고(`learned/human_games_merged.json` 에 합친 id), 그 표로 이어서 학습(`train_table.py`) · 리그 · 프로그램 빌드를 합니다.

## 개발 · 빌드

```bash
# 대전별 학습표 · 카드 이미지 · 기본 재생 기록
python3 -c "import sys,json,lzma; sys.path.insert(0,'nny_sim/app'); import tables as T; T.split('<sim>/learned/policy.json.xz','<split>', read=lambda p: json.load(lzma.open(p,'rt',encoding='utf-8')))"
python3 nny_sim/app/build_assets.py <cards>
python3 nny_sim/app/make_library.py --sim <sim(전체 표 없는 사본)> --split <split> --out <library> --all-pairs --workers 4
# 개발 실행(리눅스) — <sim> 에 learned/policy.json.xz 가 있으면 import 때 4GB를 읽으므로 그 파일을 뺀 사본을 쓴다
python3 nny_sim/app/main.py --sim <sim> --split <split> --cards <cards> --library <library> --user <사용자 폴더> --port 8765
# Windows 배포본(우분투: gcc-mingw-w64-x86-64 · Pillow)
python3 nny_sim/app/build_windows.py --sim <실행 폴더(전체 표 포함)> --nupkg python.3.13.17.nupkg --out <out> --split <split> --library <library>
```

Windows 파이썬은 NuGet의 파이썬 재단 공식 패키지 [`python`](https://www.nuget.org/packages/python)(3.13.17)을 씁니다(python.org 는 이 개발 환경 네트워크 정책에 막혀 있음).
실행기 `NNY_Simulator.exe` 는 `win/launcher.c` 를 mingw로 만든 것으로, `runtime\pythonw.exe -I -X utf8 app\main.py` 를 띄웁니다.
`wine` 으로 검증할 때는 `LC_ALL=C.UTF-8` 이 필요합니다(로캘이 POSIX면 wine이 한글 파일 이름을 깨뜨림 — 실제 Windows와 무관).

| 파일 | 내용 |
| --- | --- |
| `tables.py` | 학습표 덱 쌍별 분할 · 대전 몫 불러오기 · 학습 기록(jsonl) — 같은 시드에서 전체 표와 기록 동일 확인 |
| `human.py` | 사람 플레이어(HumanAI) — `LearnedAI.choose` 를 화면 입력으로. AI 운용 지침 거름망 없는 행동 목록, 블록 안 하위 선택 감싸기(엔진 함수 · 블록 실행부 — 엔진은 고치지 않음), 가치 계산(가정) 안에서는 묻지 않음 |
| `session.py` | 대전 세션(엔진 스레드 + 기록기 · 사람 전략 덱 교체), AI vs AI 녹화 작업, 사용자 폴더(덱 · 재생 기록 · 재생 목록 · 학습 기록 · 설정 · git 올리기) |
| `server.py` · `main.py` | 로컬 서버(토큰 필요) · 진입점(중복 실행 방지, 창 닫으면 자동 종료, Edge 앱 창) |
| `static/` | 화면: `board.js`(보드 · 재생 부품 — 단일 HTML 재생 파일 `viewer/replay.py` 도 같은 파일을 넣어 씀) · `app.js`(네 화면) |
| `make_library.py` · `build_assets.py` · `build_windows.py` · `win/` | 기본 재생 기록(`--rerecord` — 기록기를 바꾼 뒤 같은 매치 다시 녹화) · 카드 이미지 · Windows 배포본 |
| `merge_learning.py` | 저장소 쪽: 사람 대전 학습 기록 → policy 표 |
| `tests/` | `eq.py`(감싸기가 AI끼리 대전을 바꾸지 않는지 — 같은 시드 기록 비교, `all` 은 모든 덱 쌍) · `backend.py`(가짜 사람 대전 — 하위 선택 · 전략 덱 교체 요청 집계 · 학습 · 재생 저장, `PAIRS=all`) · `app_test.js`(화면 자동 시험, Playwright) |

## 알려진 한계

- 카드 블록 안의 하위 선택(1.1.0부터): 카드 n장 고르기(코스트 · 대상) · 서치 · 「A하거나 B한다」 선택지(상대가 고르는 문장이면 상대 자리) ·
  처리 때 특수소환할 몬스터 · 「원하는 수까지」 · 카운터를 놓을/뗄 카드와 「임의의 개수」 · 종류별 코스트(각각 n장씩 · 합계 n장) ·
  상대에게 보여 줄 카드 · 뒷면 카드 재배치 · 앞면으로 뒤집을 몬스터 · 덱에서 묘지로 보낼 카드 · 레벨/속성 부여 대상 · [지속] 효과 변경 여부를 사람에게 묻습니다.
  운(주사위 · 상대의 무작위 고르기)과 규칙으로 정해지는 처리, 번식지 서치처럼 행동 판단으로 이미 묻는 것은 그대로입니다.
  제물은 행동 목록의 후보(제물 포함)로 고릅니다. 선택지 이름표는 처리 블록 이름(「서치 1장」 · 「묘지로 보내기 2장」 등)이라 카드 텍스트와 함께 보세요.
- 라운드 사이 전략 덱 교체(1.1.0부터): 사람 덱도 2 · 3라운드 전에 화면에서 교체합니다. 넣을 카드를 펼쳐 뺄 카드를 고르고(한 번에 1:1 하나씩),
  「교체 끝」으로 확정합니다. 교체 후보는 AI와 같은 규칙(match.py — 같은 덱 종류 1:1 · 동명 3장 · 스킬 태그 · 고정 카드 제외 · 스킬 카드 교체)으로 서버가 만들고,
  확정 때 덱 규칙을 다시 검사합니다. 바뀐 덱은 그 매치 안에서만 쓰입니다(저장된 덱은 그대로).
- 서명하지 않은 실행 파일이라 처음 실행 때 Windows SmartScreen 경고가 나올 수 있습니다.
