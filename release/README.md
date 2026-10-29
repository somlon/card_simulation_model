# NNY 시뮬레이터 Windows 배포본

| 파일 | 크기 | SHA-256 |
| --- | --- | --- |
| `NNY_Simulator_v1.0.0_win64.zip` | 90.3MB | `7bc238f0036939468c22a09b5061030f037c5acbb9f15c527435a058c2aa0a0f` |

**실행**: zip을 풀고 `NNY_Simulator/NNY_Simulator.exe` 를 실행합니다(Windows 10/11 64비트, 인터넷 불필요). 자세한 내용은 zip 안의 `읽어보기.txt`.
처음 실행 때 「알 수 없는 게시자」 경고(SmartScreen)가 나오면 「추가 정보 → 실행」(서명하지 않은 프로그램).

**기능**: 관전 · 재생 목록(기본 제공 AI 대전 65매치 — 11개 덱 55대진 + 10), 나 vs AI 대전(Bo3, 판단 패널), AI vs AI 실시간 관전 · 녹화,
덱 편집(규칙 검사 · 저장 → AI 대전에 사용), 사람 대전 학습(매치가 끝나면 프로그램 안에서 바로 반영, 기록 내보내기 · GitHub 올리기 · 자동 올리기).

**구성 · 출처**
- 코드: `claude/vibrant-euler-jekich` 23e66ce 의 `nny_sim/app/` · `nny_sim/viewer/record.py`, 엔진 `model/main` 9d6d5ae (블록 체계 · 명계의 규율 반영)
- 데이터: `data/main` 3969ea9 — 카드 풀 200장 · 덱 11개 · 학습 덱 레시피 · 교체표, 학습표 `policy.json.xz`(10-14 재학습판)를 덱 쌍별로 나눈 것
- 카드 이미지: 사용자 업로드 매트 · 뒷면 · 카드 시트 11장(2026-10-29, `nny_sim/viewer/assets/src`)
- Windows 파이썬 3.13.17: NuGet의 파이썬 재단 공식 패키지 `python` — https://www.nuget.org/packages/python/3.13.17
  (`python.3.13.17.nupkg` SHA-256 `dce409744b088f94c6e37ba41f8100c384c27e029e843237364c602d30d475e5`)
- 실행기: `nny_sim/app/win/launcher.c` 를 우분투 `gcc-mingw-w64-x86-64` 로 컴파일

**검증(빌드 환경)**: wine 9.0(LC_ALL=C.UTF-8)에서 실행기 → 서버 기동, 브라우저 자동 조작으로 관전 · 덱 편집 · 사람 vs AI Bo3 한 판(판단 181번) · 학습(판단 290개) · 재생 저장 · 학습 화면 — 화면 오류 0.
실제 Windows PC에서의 실행은 아직 확인하지 않았습니다.
