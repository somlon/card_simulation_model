# 블록 라이브러리 목록 — 생성 스크립트

카드 효과 조립식 전환 검토(2026-10-25 ~ 10-28)에서 만든 블록 목록 PDF의 원본. 2026-10-25 ~ 10-27 세션(session_016w2Gxny1G67zJxAoJUWAY6)의
스크래치에만 있던 것을 그 세션 기록(파일 작성 · 수정 명령)에서 되살려 보관한다 — 39개판 PDF(16쪽)를 그대로 재현함을 확인(2026-10-28).

| 파일 | 내용 |
| --- | --- |
| `blocks.html` | 옛 블록 124개 목록(2026-10-25 PDF 원본) — `survey.py`가 블록 이름 · 분류를 읽는다 |
| `ann.py` | 전수 조사 대응표: 카드 코드 → 효과 번호 → 옛 블록 ID (418행) |
| `survey.py` | 카드 텍스트 ↔ 대응표 검사, 사용 횟수 · 구현 대응 → `out.json` |
| `consolidate.py` | 124 → 39개판 통합 규칙 → `new.json` |
| `consolidate27.py` | 39 → 27개판 추가 통합(2026-10-27 결정) · 재정 ① 행동 세금 행 → `new27.json` |
| `gen2.py` · `gen3.py` | `new.json` · `new27.json` → HTML (39개판 · 27개판) |
| `pdf.js` | HTML → PDF (Playwright Chromium, A4 가로는 HTML의 @page) |

```bash
# 실행 폴더: 코드(model 계열) + 데이터(data/main)를 합친 nny_sim
python3 -I survey.py <nny_sim> blocks.html out.json
python3 -I consolidate.py out.json new.json        # 39개판
python3 -I consolidate27.py out.json new27.json    # 27개판
python3 -I gen3.py new27.json blocks27.html && node pdf.js $PWD/blocks27.html $PWD/블록_라이브러리_목록_통합판27.pdf
```
