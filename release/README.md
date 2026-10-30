# NNY 시뮬레이터 Windows 배포본

| 파일 | 크기 | SHA-256 |
| --- | --- | --- |
| `NNY_Simulator_v1.3.2_win64.zip` | 102.6MB | `6b2f50f9a6af94a017f9efec6d14cac12405c4a6199ad46d4195bf5c37d7599b` |
| `NNY_Simulator_v1.3.1_win64.zip` | 102.6MB | `b250a112278cfa03c18ecc7156406d759b1a5988cc66c18c9233adc1f790c21d` |
| `NNY_Simulator_v1.3.0_win64.zip` | 102.6MB | `834fb80f6e2e799fbee7c16b72027ec2b9ee730b0ed63b5d89f7ac9ad3b9469d` |
| `NNY_Simulator_v1.1.0_win64.zip` | 90.4MB | `03494a7326a55510087a823d0216c5b50f5cde08f9f5281e98b1f88c58d43731` |
| `NNY_Simulator_v1.0.0_win64.zip` | 90.3MB | `7bc238f0036939468c22a09b5061030f037c5acbb9f15c527435a058c2aa0a0f` |

**v1.3.2 (2026-10-30)** — 필드: 몬스터 존 3칸(예전 1 · 3 · 5번 자리) · 공유 존 2칸(칸마다 마커, 예전 스킬 존 자리) · 스킬 존은 1 · 5번 몬스터 존 위 · 필드 존은 가운데(매트 v2),
대전 중 상대 세트(뒷면) 카드 이름 감춤, 학습 데이터 판단 단위 정리. 코드 `claude/vibrant-euler-jekich` aa836bb(app/hide-set-cards · app/decision-curation · app/shared-zones 병합),
엔진 `model/shared-zones` 9dd654c, 데이터 `data/main` · 기본 신경망 base_v2, 기본 재생 기록 `release/library_v1.3.2`(새 규칙으로 같은 65매치 다시 녹화).
검증: wine 9.0 — AI끼리 관전 · 나 vs 휴리스틱 AI · 녹화 · 내보내기 정상(신경망 기능은 wine 에서 꺼짐 — 이전과 같음).

**v1.3.1 (2026-10-30)** — 「…하고 발동할 수도 있다」 선택 코스트 · 「…할 수 있다」 선택 처리를 사람이 직접 고름, 대상을 지정하지 않는 코스트는 효과 내성을 보지 않음(기적의 영웅을 행운의 도적 코스트로),
체인 처리 뒤 우선권을 다시 엶(횟수가 남은 [신속]을 이어서 사용), 효과 처리 뒤 필드를 바로 화면에. 코드 `claude/vibrant-euler-jekich` 8f5aea7(= `app/main` 2830c43 + 읽어보기),
엔진 `model/main` b66758c, 데이터 `data/main` · 기본 신경망 base_v2 · 기본 재생 기록 `release/library_v1.2.1`. 검증: wine 9.0 — AI끼리 관전 · 나 vs 휴리스틱 AI · 녹화 · 내보내기 정상(신경망 기능은 wine 에서 꺼짐 — 이전과 같음).

**v1.3.0 (2026-10-30)** — AI끼리 관전 · 녹화에서 자리(P1 · P2)마다 AI 종류(학습표 · 신경망 · 휴리스틱 — 다른 종류의 AI끼리 대전),
AI끼리 대전도 학습 데이터로(학습 기록 `ai_games.jsonl` · 신경망 표본 · 내보내기 · GitHub 올리기), 사람 대전 데이터 3배 가중치(학습표 · 신경망 · 저장소 합치기),
「학습 데이터 정리」(출처 · 덱 · AI 종류로 걸러 매치마다 빼기/넣기), 학습하는 휴리스틱 AI(전술은 규칙, 전략 판단은 학습표로 고르고 학습).
코드 `claude/vibrant-euler-jekich` 708ff76(= `app/heuristic-learning` 5b84ddd ← `app/learning-data` f06b864 ← `app/ai-kinds-per-seat` 3b8777a + 읽어보기),
엔진 `model/table-weights` 6fb94be(`model/main` 74c285e + Table.update 가중), 데이터 `data/main` · 기본 신경망 `data/drl-base-v2` a57e839, 기본 재생 기록 `release/library_v1.2.1`, numpy 2.4.6(PyPI 공식 휠).
검증: wine 9.0 그대로 빌드 — 신경망 기능만 꺼지고 AI끼리 관전(휴리스틱 vs 학습표) · 나 vs 휴리스틱 AI · 녹화 · 학습 데이터 정리 · 내보내기 정상 /
시험용 shim 사본(`tests/wine_numpy`) — 휴리스틱 vs 신경망 관전 · 신경망 학습(사람 대전 119 · AI끼리 221 표본) · 신경망 내보내기 정상.

**v1.1.0 (2026-10-29)** — 사람 자리에서 카드 효과 처리 중의 하위 선택(선택지 · 소환할 몬스터 · 카운터 · 종류별 코스트 · 공개할 카드 · 재배치 · 뒤집기 · 덱에서 묘지로 · 효과 변경 여부 등)을 직접 고름,
라운드 사이 사람 전략 덱 교체(넣을 카드 → 뺄 카드, AI와 같은 교체 규칙 · 덱 규칙 재검사). 재생 화면 시각화 개선(공유 존 마커 흑백 코인 · 재생 약 1.6배 느리게 · 공격/효과 화살표 · 오른쪽 체인 순서 — 1번이 위)도 포함.
기본 재생 기록은 `release/library_v1.1/`(새 기록기로 같은 덱 · 시드 · 선공 65매치 다시 녹화).

**기본 재생 기록 v1.2** — `release/library_v1.2/`: 체인 표시를 고친 기록기(`app/chain-order-display` 40891c9 — 발동 중인 고리를 상태에 넣어 체인 패널이 높은 번호부터 「처리 중」)와
엔진 `model/play-fixes-1029` 95231f4 · 데이터 `data/fix-swrm004-text` 5a9590f 로 v1.1 과 같은 덱 · 시드 · 선공 65매치를 다시 녹화(res 연출 빠짐 0 / 4,527).

**실행**: zip을 풀고 `NNY_Simulator/NNY_Simulator.exe` 를 실행합니다(Windows 10/11 64비트, 인터넷 불필요). 자세한 내용은 zip 안의 `읽어보기.txt`.
처음 실행 때 「알 수 없는 게시자」 경고(SmartScreen)가 나오면 「추가 정보 → 실행」(서명하지 않은 프로그램).

**기능**: 관전 · 재생 목록(기본 제공 AI 대전 65매치 — 11개 덱 55대진 + 10), 나 vs AI 대전(Bo3, 판단 패널), AI vs AI 실시간 관전 · 녹화,
덱 편집(규칙 검사 · 저장 → AI 대전에 사용), 사람 대전 학습(매치가 끝나면 프로그램 안에서 바로 반영, 기록 내보내기 · GitHub 올리기 · 자동 올리기).

**구성 · 출처**
- 코드: v1.1.0 `claude/vibrant-euler-jekich` cbe59ca(시험 도구 c1e71fb), v1.0.0 23e66ce 의 `nny_sim/app/` · `nny_sim/viewer/record.py`, 엔진 `model/main` 9d6d5ae (블록 체계 · 명계의 규율 반영)
- 데이터: `data/main` 3969ea9 — 카드 풀 200장 · 덱 11개 · 학습 덱 레시피 · 교체표, 학습표 `policy.json.xz`(10-14 재학습판)를 덱 쌍별로 나눈 것
- 카드 이미지: 사용자 업로드 매트 · 뒷면 · 카드 시트 11장(2026-10-29, `nny_sim/viewer/assets/src`)
- Windows 파이썬 3.13.17: NuGet의 파이썬 재단 공식 패키지 `python` — https://www.nuget.org/packages/python/3.13.17
  (`python.3.13.17.nupkg` SHA-256 `dce409744b088f94c6e37ba41f8100c384c27e029e843237364c602d30d475e5`)
- 실행기: `nny_sim/app/win/launcher.c` 를 우분투 `gcc-mingw-w64-x86-64` 로 컴파일

**검증(빌드 환경)**: v1.1.0 — 감싸기가 AI끼리 대전을 바꾸지 않음(66 덱 쌍 같은 시드 기록 동일), 가짜 사람 44매치 오류 0, wine 9.0에서 사람 vs AI Bo3 끝까지(판단 351번 · 전략 덱 교체 패널 사용) 화면 오류 0.
v1.0.0 — wine 9.0(LC_ALL=C.UTF-8)에서 실행기 → 서버 기동, 브라우저 자동 조작으로 관전 · 덱 편집 · 사람 vs AI Bo3 한 판(판단 181번) · 학습(판단 290개) · 재생 저장 · 학습 화면 — 화면 오류 0.
실제 Windows PC에서의 실행은 아직 확인하지 않았습니다.
