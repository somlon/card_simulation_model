"""new27.json → 블록 라이브러리 목록 (통합판 27개) HTML.  사용: python3 -I gen3.py new27.json 출력.html"""
import json, sys, html
d = json.load(open(sys.argv[1], encoding='utf-8')); OUT = sys.argv[2]
E = html.escape
OC = d['oldcat']
n_new = len(d['stats']); n_old = len([k for k in OC if not k.startswith('F')])
star = [s for s in d['stats'] if s['cards'] == 1]
n_frame_old = sum(1 for v in d['old2new'].values() if v.startswith('효과 틀'))

css = """
@page { size: A4 landscape; margin: 11mm 11mm 12mm 11mm; }
:root { --ink:#1d2330; --mute:#5b6475; --line:#d0d6e0; --acc:#2f5fb3; --acc2:#b4532a; --ok:#2e7d4f; }
body { font-family:"WenQuanYi Zen Hei", sans-serif; color:var(--ink); font-size:8.7pt; line-height:1.48; background:#fff; margin:0; }
h1 { font-size:17pt; margin:0 0 1mm; }
h2 { font-size:12.5pt; margin:5mm 0 1.8mm; padding-bottom:0.8mm; border-bottom:2px solid var(--acc); page-break-after:avoid; }
h3 { font-size:10.5pt; margin:3.5mm 0 1.2mm; color:var(--acc); page-break-after:avoid; }
p { margin:1mm 0; } .sub { color:var(--mute); font-size:8.4pt; }
table { border-collapse:collapse; width:100%; margin:1mm 0 2.5mm; }
th, td { border:1px solid var(--line); padding:0.9mm 1.5mm; vertical-align:top; text-align:left; }
th { background:#e8edf6; font-size:8.3pt; } thead { display:table-header-group; } tr { page-break-inside:avoid; }
td.n { text-align:right; white-space:nowrap; } td.c { text-align:center; white-space:nowrap; }
.mono { font-family:"WenQuanYi Zen Hei Mono", monospace; font-size:7.8pt; } .en { font-family:"WenQuanYi Zen Hei Mono", monospace; font-size:7.6pt; color:var(--acc); display:block; }
.small { font-size:7.4pt; color:#3a4252; } .star { color:var(--acc2); font-weight:bold; }
.box { background:#f3f5f9; border-left:4px solid var(--acc); padding:2mm 3mm; margin:2mm 0; } .box.ok { border-left-color:var(--ok); } .box.warn { border-left-color:var(--acc2); }
.kpi { display:flex; gap:2.5mm; margin:2mm 0; } .kpi div { flex:1; border:1px solid var(--line); border-radius:2mm; padding:1.6mm 2.4mm; } .kpi b { display:block; font-size:14pt; }
.pb { page-break-before:always; } .grp td { background:#f6f7fa; font-weight:bold; }
ul, ol { margin:1mm 0 1.5mm; padding-left:5mm; } li { margin:0.5mm 0; }
.tag { display:inline-block; font-size:7.4pt; padding:0 1.2mm; border-radius:1mm; background:#e3ecfa; color:var(--acc); margin-right:0.6mm; }
.tag.cost { background:#fbeee7; color:var(--acc2); } .tag.apply { background:#e6f3eb; color:var(--ok); }
"""
H = [f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>블록 라이브러리 목록 통합판 27</title><style>{css}</style></head><body>']
A = H.append
A('<h1>블록 라이브러리 목록 — 통합판 (27개)</h1>')
A('<div class="sub">2026-10-28 · 앞서 보낸 통합판(39개, 2026-10-27)에 추가 통합 결정(39 → 27, 기준 「소모 시간이 적은 쪽, 같으면 메모리가 적은 쪽」 — 사용자 지시 2026-10-27)과 '
  '재정 답변(2026-10-27 · 10-28)을 반영 · 대응표는 전수 조사 418행(2026-10-25)을 다시 대응 · 데이터 <span class="mono">data/main</span> 3969ea9</div>')
A('<div class="kpi">'
  f'<div>블록<b>{n_old} → 39 → {n_new}개</b></div>'
  f'<div>대응되지 않는 문장<b>0행</b><span class="small">418행 전부 27개 블록으로 다시 대응</span></div>'
  f'<div>쓰이지 않는 블록<b>{len(d["missing"])}개</b></div>'
  f'<div>값 문법으로 옮김<b>9개</b><span class="small">수량 8 · 참조 1</span></div>'
  f'<div>효과 틀 속성으로 옮김<b>{n_frame_old}개</b><span class="small">부속 · 자동 처리 · 발동 위치 · 소환 절차</span></div>'
  f'<div>카드 1장 전용<b>{len(star)}개</b><span class="small">39개판 6개</span></div>'
  '</div>')
A('<div class="box ok"><b>결론</b><ul>'
  f'<li><b>39개 → {n_new}개.</b> 두 블록이 <b>값만 다르면 합치고</b>, 처리 순서 · 규칙 흐름이 다르면 남겼습니다(1장 · 3장). 합친 9건 가운데 시간이 늘어나는 방식은 고르지 않았고, '
  '시간이 같으면 메모리가 적은 쪽을 골랐습니다(측정 근거 1장 · 6장).</li>'
  '<li>가장 큰 통합은 <b>A17 「상태 · 보정」</b>입니다 — 공격력 · 수비력 증감 · 카드 상태 · 플레이어 규칙 · 다른 효과 값 변경이 「대상 · 종류 · 값 · 기간 · 근원 카드」라는 같은 기록이라 하나로 묶고, '
  '종류는 종류 표(4장)로 둡니다. 함께 넣기로 한 <b>종류별 색인</b>은 엔진에 먼저 구현했습니다 — 같은 시드 1,100판 기록 동일 · 24 ~ 27% 빠름(PR #81).</li>'
  '<li><b>재정 반영</b>(5장): ① 「서로가 …할 때마다 … n장 제외」 = 행동에 붙는 코스트(상태 · 보정의 「행동 세금」 종류 + 이동의 코스트 모드, PR #79) · '
  '② 1턴 1번 파괴 내성은 인페르노 파괴를 그 턴 내내 버팀(파괴의 적용 모드 — 내성은 확인만) · ③ 「다른 카드의 효과를 받지 않는」 카드는 자기편 [지속]도 받지 않음(상태 · 보정의 카드 대상 종류 전부 내성 검사) · '
  '④ 「패에 넣었을 때」에 드로우 포함(E3의 출발지 덱 · 이동의 드로우 설정을 함께 봄).</li>'
  '<li>합치지 않은 블록과 이유도 표로 정리했습니다(3장) — 파괴 · 릴리스(내성이 행위에 걸림) · 특수소환 · 마법 놓기 · 장착 · 무효 3종 · 효과 변경 · 효과 부여 · HP ↔ 카운터 · 표시 형식 · 승리.</li>'
  '</ul></div>')

# ── 1. 39 → 27 결정 ──
A('<h2>1. 39 → 27 추가 통합 — 결정과 근거</h2>')
A('<p>측정: <span class="mono">model/main</span> a925f24 엔진 + <span class="mono">data/main</span> 덱 11개, 55개 대전 조합 같은 시드(2026-10-27). 시간의 48%가 <span class="mono">legal()</span>, '
  '그 안의 <span class="mono">rule()</span>이 30% — 부를 때마다 [지속] 카드 7 ~ 11장을 훑지만 그 규칙을 가진 카드는 평균 0.3장 미만. 메모리는 판을 거듭해도 늘지 않음(220판 뒤 0.10 MB).</p>')
MERGES = [
 ('S1 고르기 + S2 선언 → <b>S1 고르기</b>', '−1', '둘 다 「플레이어가 결정하고 뒤 처리가 그 결과를 참조」 — 고르는 것이 카드냐 값이냐만 다름. 카드 영역만 「대상 지정 여부」(필수 값) · 처리 때 유효 확인',
  '선언의 결정 방식은 지금 고정 규칙 그대로 — 학습 정책으로 바꾸면 시간 +0.1% · 학습표 약 +0.5%'),
 ('A9 컨트롤 이동 + A11 재배치 → <b>A9 필드 안 이동</b>', '−1', '필드 안에서 자리만 바뀜, 다른 쪽 자리면 컨트롤 이동 규칙. 지금 셔플 맞바꾸기(swap_cards) · 넓적배사마귀가 컨트롤 이동 검사(빈 자리 · 필드 매수 제한)를 건너뛰는 불일치를 한 곳에서 고침',
  '늘어나는 검사는 재정(10-20)상 원래 필요한 것, 색인으로 비용 거의 없음. A8 장착은 호스트와의 관계라 유지'),
 ('A17 + A20 + A21 + A26 → <b>A17 상태 · 보정</b>', '−3', '블록의 카드 / 플레이어 경계가 엔진 구조와 어긋남(파괴 내성은 블록상 카드 상태인데 엔진에서는 전역 규칙, 효과 내성은 flags · rules 두 갈래, 옛 P07이 A20 · A21로 갈림). '
  '넷 다 「대상 · 종류 · 값 · 기간 · 근원」', '<b>종류별 색인</b> 시제품 440판 기록 동일 · 28 ~ 35% 빠름(70 → 48 ms/판), 메모리 증가 없음 → 엔진에 구현(PR #81: 1,100판 동일 · 24 ~ 27%). '
  '「이 카드」 대상 기록은 카드에 둠(전체 훑기면 약 20% 느려짐). 기간 기록은 수명 칸으로 일괄 정리'),
 ('A4 드로우 + A5 덱 위 보내기 → <b>A2 이동</b>', '−2', '재정 Q46이 드로우를 「덱 → 패 이동」으로 봄(같은 금지 검사가 draw · to_hand에 두 번). 덱 위 처리 함수 셋(draw · mill · dump)의 사건이 제각각',
  '「드로우」 · 「덱 위 보내기」는 A2의 이름 붙은 설정으로 남김. 사건은 지금처럼 카드마다(카드마다 내도 165판 +1,257건, 시간 차이 측정 오차 안 · 기록 동일). 재정 ①로 드로우 도중에 끼어드는 [지속]이 사라져 합칠 수 있게 됨'),
 ('J3 택1 → <b>S1 고르기(선택지) + J2 분기</b>', '−1', '「…하거나」 결정 11건 중 10건을 카드 코드의 고정 규칙이 정함(학습 정책을 거치는 것은 인카운터 1건)',
  '결정 방식은 지금 고정 규칙 그대로(선언과 같은 이유 — +0.1% · +0.5%). 실행할 수 없는 선택지는 S1의 후보 검사가 거름'),
 ('C1 존재 + C2 그 카드가 …인가 → <b>C1 조건</b>', '−1', 'C2(x) = 「{x} 가운데 필터에 맞는 카드가 1장 이상」. 옛 C04 · C06이 카드마다 C1 · C2로 갈려 손으로 지정한 곳 4건',
  '조건 한 번 판정(C2형 / C1형): 지금 손으로 쓴 코드 109 / 972 ns, <b>코드 생성 120 / 1006 ns(같은 수준)</b>, 클로저 조립 201 / 1075 ns, 판정 때 해석 780 / 2116 ns. '
  '같은 문장은 캐시(프로세스 단위 — 카드 객체마다 두면 판마다 쌓여 누수)'),
 ('A25 조건 자동 파괴 → <b>A1 파괴의 적용 모드</b>', '−1', '인페르노 구현이 하는 일 넷(대상 먼저 모으기 · 재진입 막기 · 직전 재확인 · 파괴) 중 셋은 상태 점검의 공통 일, 마지막은 A1 그 자체',
  '내성은 「확인만(횟수 안 씀)」 = 재정 ②와 같음, 주인에게 적용 여부를 묻는 호출도 없어 더 빠름. E5로 바꾸지 않음(이미 2000 이상인 몬스터도 파괴 — 「상태」 조건)'),
 ('A10 공개 · 확인 → <b>해체</b>', '−1', '엔진은 공개 상태를 기록하지 않음, 「보여주고 발동」은 지불이 아님(두플리카토르 dupcost.py · 델레가토르 parse_cost). 8건은 효과 틀의 발동 위치(패), 대장정 · 월식의 「덱 위 n장 확인 → 고르기」는 S1의 후보 범위',
  '시간 같음, 블록 하나 줄어듦. 「공개」는 값으로 남김(숨은 정보 추론 AI용)'),
 ('A24 소환 절차 → <b>효과 틀 F14</b>', '−1', '엔진은 이미 처리 블록이 아니라 효과의 속성으로 구현(Effect.procedure — 발동 사건 · 발동 횟수 없음, 일반소환형 alt_normal)',
  '시간 같음. 「발동 코스트 아님」 표시 필수 — 틀 안의 비용 블록이 발동 코스트로 잡히면 두플리카토르 · 델레가토르가 걸림'),
]
A('<table><thead><tr><th style="width:22%">통합</th><th style="width:4%">블록</th><th style="width:37%">코드에서 찾은 근거</th><th>시간 · 메모리 근거와 조건</th></tr></thead>')
for a, n, b, c in MERGES: A(f'<tr><td>{a}</td><td class="c">{n}</td><td>{b}</td><td>{c}</td></tr>')
A('</table>')
A('<div class="box"><b>먼저 검토한 3건(39 → 37):</b> S1 + S2 · A9 + A11은 위 표에 포함, <b>A12 ~ A14 무효 3종은 유지</b> — 대상(발동 / 진행 중인 소환 / 카드) · 결과 · 시점 · 부수 처리(횟수 반환) · '
  '<span class="mono">negated</span> 사건(소환 무효만 안 냄)이 모두 달라, 하나로 묶으면 「종류」 값이 블록 이름이 되고 안쪽은 세 갈래 분기로 남는 겉모양 통합(3장).</div>')

# ── 2. 새 블록 목록 ──
A('<h2 class="pb">2. 새 블록 목록 (27개)</h2>')
A('<p>모드: <span class="tag cost">cost</span> 코스트로 씀 · <span class="tag">do</span> 처리로 씀 · <span class="tag apply">apply</span> [지속] 적용으로 씀(지금 카드 풀에서 실제로 쓰이는 모드). '
  '효과 수 · 카드 수는 전수 조사 418행을 27개 블록으로 다시 센 값. ★ = 카드 1장만 씀. ID는 39개판 번호를 이어 쓰고, 합친 블록은 가장 작은 번호(39개판 → 27개판 ID는 8장).</p>')
A('<table><thead><tr><th style="width:4%">ID</th><th style="width:11%">블록</th><th>하는 일 · 값</th><th style="width:9%">모드</th><th style="width:4.5%">효과 수</th><th style="width:4.5%">카드 수</th><th style="width:20%">합친 옛 블록</th></tr></thead>')
cur = None
for s in d['stats']:
    if s['cat'] != cur:
        cur = s['cat']; A(f'<tr class="grp"><td colspan="7">{E(cur)}</td></tr>')
    md = ''.join(f'<span class="tag {m if m != "do" else ""}">{m}</span>' for m in s['modes']) if s['id'][0] in 'AS' or s['id'] == 'J2' else '—'
    st = ' <span class="star">★</span>' if s['cards'] == 1 else ''
    oldn = ', '.join(E(OC[o][0]) for o in s['old'] if o in OC)
    A(f'<tr><td class="mono">{s["id"]}</td><td><b>{E(s["name"])}</b>{st}<span class="en">{E(s["en"])}</span></td><td>{E(s["desc"])}</td><td>{md}</td>'
      f'<td class="n">{s["effects"]}</td><td class="n">{s["cards"]}</td><td class="small"><span class="mono">{E(" ".join(s["old"]))}</span><br>{oldn}</td></tr>')
A('</table>')

# ── 3. 합치지 않은 것 ──
A('<h2 class="pb">3. 합치지 않은 블록과 이유</h2>')
KEEP = [
 ('A1 파괴 · A3 릴리스 ↔ A2 이동', '내성이 <b>행위</b>에 걸림 — 「파괴되지 않는다」면 카드가 아예 움직이지 않고, 「파괴 이외로 벗어나지 않는다」(실렉스)는 파괴만 통과, 릴리스 불가 성질 · 「릴리스되었을 때」(도착지와 무관 — 질문 1, 39개판 2장). '
  '블록은 남기고 엔진 안의 이동 경로만 하나로 합침(grave_redirect 경로가 released 표시를 잃는 버그를 막음)'),
 ('A6 특수소환 · E1 ↔ A2 · E3', '처리 순서가 다름 — [제약]은 필드 밖에서 판정, 같은 이름 규칙(3-6 f), 소환 무효를 [소환] 효과보다 먼저 물음'),
 ('A7 마법 놓기', '세트 규칙 · 마법 존 빈자리 · 뒷면 마법은 무효를 받지 않음(10-25)'),
 ('A8 장착', '자리가 아니라 호스트와의 관계 — 호스트가 떠나거나 뒷면이 되면 묘지로(Q12), 호스트 무효 · 장착 해제, 패에서 장착(바이러스 모스키토 · 맵시기생벌)'),
 ('A12 · A13 · A14 무효 3종', '대상(발동 / 진행 중인 소환 / 카드) · 결과 · 시점(체인 응답 / 소환 무효 창 / 처리 · [지속]) · 부수 처리(횟수 반환 §6-5) · negated 사건(소환 무효만 안 냄)이 모두 다름'),
 ('A14 카드 무효 ↔ A17 상태 · 보정', '무효는 다른 보정의 <b>근원 자체를 끄는 상위 층</b>(is_neg) — 같은 층에 넣으면 자기 참조로 순환 계산이 필요'),
 ('A22 효과 부여 ↔ A17 상태 · 보정', '상태는 「이 종류가 있나」를 한 번 묻고, 부여는 「이 카드의 효과 전부」를 나열해야 함(트리거 수집 · 발동 목록 · AI 라벨)'),
 ('A16 HP ↔ A19 카운터', 'E5에서 합친 것은 문턱 계산이 같아서 — 처리 규칙은 겹치지 않음(대미지 절반 · 0, HP 0 패배 / 카운터를 놓을 수 있는 카드 PDF Q2). 공통 부분(E5 사건)은 엔진 도우미 하나로(지금 heal은 사건을 내지 않음)'),
 ('A18 표시 형식', '뒷면이 되면 카운터 제거 · 무효 해제 · 장착 카드 묘지로(Q12) 같은 부수 효과'),
 ('A15 효과 변경 ↔ A12 발동 무효', '무효만 negated 사건을 냄 — 저주 - 강령이 그 사건을 들음'),
 ('A23 승리', '하나뿐인 게임 종료 행위'),
 ('E6 무효화 ↔ E2 발동 · E5 값 변화', '엔진이 내는 사건(발동 무효 · 카드 무효 · 장착 무효 모두 negated) — E2에 「무효됨」을 넣으면 체인 응답 시점과 처리 뒤 트리거 시점이 섞임'),
 ('S1 고르기의 「대상 지정 여부」', '합쳤지만 <b>기본값 없는 필수 값</b> — 내성 · 뒷면 카드 · 제거 효과(Q6) 판정을 좌우하므로 빠뜨리면 조립 오류'),
]
A('<table><thead><tr><th style="width:24%">블록</th><th>합치지 않은 이유</th></tr></thead>')
for a, b in KEEP: A(f'<tr><td>{E(a)}</td><td>{b}</td></tr>')
A('</table>')

# ── 4. 서치 · 덤핑 · 샐비지 ──
A('<h3>영역 사이 이동은 어느 블록인가</h3>')
A('<table><thead><tr><th style="width:24%">효과</th><th style="width:26%">블록</th><th>예</th></tr></thead>'
  '<tr><td>서치(덱 → 패, 골라서)</td><td>A2 이동(덱 → 패)</td><td>래빗 풋 #1 · 캐터필러 #1</td></tr>'
  '<tr><td>드로우(덱 위 → 패)</td><td>A2 이동 「드로우」 설정</td><td>투기장의 규칙 #1 · 턴 시작 드로우</td></tr>'
  '<tr><td>덱 위에서 n장(고르지 않음)</td><td>A2 이동 「덱 위 보내기」 설정</td><td>코인 #2 · 조커 #1 · 세리 코스트</td></tr>'
  '<tr><td>덱에서 골라 묘지로</td><td>A2 이동(덱 → 묘지) + S1</td><td>반혼체 #2 · 마르모르 · 카르분쿨루스 #3 코스트</td></tr>'
  '<tr><td>샐비지(묘지 → 패)</td><td>A2 이동(묘지 → 패)</td><td>잔월의 유산 #1 · 꿈이 가득한 아이 #2</td></tr>'
  '<tr><td>제외 존 → 덱 / 필드 복귀</td><td>A2 이동(코스트 모드 · 기간 값)</td><td>세리 [유언] 코스트 · 월영침식 #1</td></tr>'
  '<tr><td>필드 안에서 자리 · 컨트롤</td><td>A9 필드 안 이동</td><td>월영잠행 · 셔플 #1 · 원페어(부여 2-a)</td></tr></table>')

# ── 5. 상태 · 보정 종류 표 ──
A('<h2 class="pb">4. 상태 · 보정(A17) 종류 표</h2>')
A('<p>종류는 블록이 아니라 A17의 값입니다. 종류마다 엔진이 판정하는 자리(지금 코드의 플래그 · 규칙 키)가 있고, 블록은 등록만 합니다. 열: 받는 쪽(카드 / 플레이어 / 효과) · 값 · 기본 1턴 횟수 · 쓰는 효과 · 엔진 판정. '
  '받는 쪽이 카드인 종류는 전부 <b>내성 검사</b>(재정 ③ — 엔진 Game.receives · rule_reaches).</p>')
ST = [
 ('공격력 · 수비력 증감', 'D24 · P17', '카드', '합계 · 한 번 적용(기간) / [지속] 계산식', '텍스트에 없으면 제한 없음(10-22)', 'COMN-004 #1 · DTBG-010 #2 · WSFT-012 #1 · PKBS-004 #1', 'atk_mod · def_mod · mods'),
 ('효과 내성', 'P01 · D32', '카드', '출처(상대 · 다른 카드 · 「X」 이외) · 비대상만 · 카운터는 받음 · 기간/조건', '1번', 'DTBG-011 #2 · TAXM-004 #1 · WSFT-014 #2 · COMN-004(기간)', 'Game.immune · blocked · rule immune'),
 ('대상 내성', 'P02', '카드', '상대 효과의 대상이 되지 않음', '1번', 'AMBR-005 #2', 'untargetable_opp'),
 ('파괴 내성', 'P03 · D32', '카드', '전투 · 효과', '1번(인페르노에는 확인만 — 재정 ②)', 'PKBS-001 #1 · AMBR-002 #2 · AMBR-016 #2 · AMBR-015(기간)', 'rule indestructible'),
 ('릴리스 불가', 'P04 · D32', '카드', '—', '1번', 'AMBR-001 #2 · CRSD-008 #1 · COMN-004(기간)', 'releasable · no_release'),
 ('필드 이탈 불가', 'P05', '카드', '파괴 이외의 방법', '1번', 'AMBR-003 #2', 'Game.stays'),
 ('표시 형식 고정', 'P06 · D32', '카드', '—', '1번', 'AMBR-001 #3 · AMBR-015(기간)', 'can_change_pos'),
 ('공격 불가', 'P10 · D32', '카드', '공격 · 공격 선언', '1번', 'AMBR-001 #3 · PKBS-001-1 #2 · AMBR-010 #1(기간)', 'can_attack_with'),
 ('효과 발동 불가', 'D32', '카드', '기간', '—', 'DTBG-022', 'no_act_until'),
 ('공격 횟수 +n · 전체 공격', 'D25 · P08 · P09', '카드', '이 턴 / 지속 · 필터', '1번', 'FGTR-003 #2 · DTBG-007 #1 · WSFT-012 #2 · SLNA-004 #3', 'extra_attacks · double_attack · attack_all'),
 ('직접공격 가능', 'P07', '카드', '상대 몬스터가 있어도 · 상대가 자신에게(AMBR-006 #3)', '1번', 'SWRM-001 ~ 010 #2 (번성충 10장) · AMBR-006 #3', 'rule direct_attack'),
 ('다른 카드군 · 속성으로도 취급 · 레벨 · 속성 부여', 'P18 · D30', '카드', '카드군 · 속성 목록 · 레벨 · 몬스터 취급', '1번', 'WSFT-014 #2 · PKBS-005 #1 · PKBS-011 #1 · PKBS-016 #2-a', 'also_groups · all_suits · clear_on_leave'),
 ('묘지 대신 덱', 'P29', '카드', '—', '1번', 'SLNA-003 #2 · SLNA-004 #2', 'grave_redirect'),
 ('소환 제한 ([제약], 어디서나)', 'R01 · R02', '카드', '효과로만 · 스킬로만 · 다른 카드의 효과로 소환 불가', '—', 'SLNA-003 #1 · WSFT-014 #1 · DTBG-013 #1', 'effect_only · ss_by_skill_only · ss_self_only'),
 ('다른 효과의 값 변경', 'P26', '효과', '대상 효과 · 바꿀 값', '1번', 'UNSL-001 #2', '카드 함수'),
 ('금지', 'P14 · D33', '플레이어', '트리거 마법 발동 · 효과로 덱→패 · 몬스터로 공격 · 대미지 주기 · 전투로 파괴 · 발동 n회 제한', '상대 금지는 사실상 제한 없음', 'COMN-006 #2 · DGMS-012 #2 · DTBG-014 #3 · SWRM-010 #1 · CRSD-002 #1', 'rule no_trigger_spell · no_deck_to_hand · act_limit · no_damage'),
 ('공격 강제 · 수비 표시 불가', 'P11 · P12', '플레이어', '조건 · 대상 필터', '1번', 'FGTR-010 #1', 'rule must_attack · no_defense'),
 ('전투 대미지 배율', 'P13', '플레이어', '0 · 절반 · 조건', '1번', 'DGMS-012 #1 · AMBR-017 #3', 'rule half/no_battle_damage'),
 ('필드 매수 제한', 'P15', '플레이어', '카드군 · 수', '1번', 'SLNA-024 #1', 'rule field_limit'),
 ('코스트 배수 · 대납 · 특정 코스트 매수', 'P19 · P20 · P21', '플레이어', '누구 · 배수(「이 카드」만이면 2배 아님 — 10-25) · 매수', '제한 없음(단서)', 'TAXM-002 #1 · TAXM-001 #1 · TAXM-010 #2', 'rule cost_double · cost_transfer · seri_lw_one'),
 ('<b>행동 세금(코스트 추가)</b> — 재정 ①', 'P27(옛 자동 처리)', '플레이어', '행동(효과의 발동 / 드로우 · 덱→패 / 특수소환) · 매수. 반드시 하는 행동은 발동할 때, 그 밖은 행동 직전, 두플리카토르 2배 · 델레가토르 대납 · 두 덱 합 부족 시 덱아웃', '제한 없음(단서)', 'TAXM-010 #1 · TAXM-011 #1 · TAXM-009 #1', 'Game.pay_tax · tax_before (PR #79)'),
 ('추가 일반소환 · 패에서 [신속] · 덱 위 추가 보내기 · 시작 패 매수', 'P22 · P23 · P24 · D33 · D36', '플레이어', '필터 · 횟수 · 기간 · 수', '1번', 'PKBS-009 #1 · PKBS-015 #1 · WSFT-026 #1 · PKBS-016 #1', 'extra_normal · pk_hand_quick · dump_extra · hand7'),
 ('맹세', 'R05', '플레이어', '카드군 · 기간(다음 상대 턴 종료 시까지)', '—', 'SWRM-001 ~ 010 #1 (번성충 10장) · AMBR-011', 'oath'),
]
A('<table><thead><tr><th style="width:15%">종류</th><th style="width:7%">옛 블록</th><th style="width:5%">받는 쪽</th><th style="width:20%">값</th><th style="width:10%">기본 1턴 횟수</th><th>쓰는 효과</th><th style="width:14%">엔진 판정</th></tr></thead>')
for r in ST:
    A('<tr>' + ''.join(f'<td{" class=mono" if i in (1, 6) else ""}>{x if i == 0 else E(x)}</td>' for i, x in enumerate(r)) + '</tr>')
A('</table>')

# ── 6. 재정 반영 ──
A('<h2 class="pb">5. 재정 답변이 블록에 주는 것 (2026-10-27 · 10-28)</h2>')
A('<table><thead><tr><th style="width:23%">재정</th><th style="width:30%">답변</th><th>블록 · 엔진 반영</th></tr></thead>'
  '<tr><td>① 세 - 아이라리움 1번 (+ 같은 문장의 세제 1번 · 취득세 1번)</td><td>「…할 때마다 … n장 제외」는 그 행동을 하는 플레이어가 내는 코스트 — 반드시 하는 행동은 발동할 때, 조건 · 선택 · 상대 효과 · 턴 시작 드로우는 행동 직전, '
  '1번에 n장, 두플리카토르 · 델레가토르 적용, 두 덱 합이 모자라면 덱아웃</td><td>A17 상태 · 보정의 「행동 세금」 종류 + A2 이동(덱 위 보내기)의 코스트 모드. 39개판의 「F13 자동 처리 + 시점 블록」 대응을 바꿈(TAXM-009 · 010 · 011 #1). '
  '엔진 Game.pay_tax · tax_before · 텍스트 판정 cards.action_taxes · sure_acts — <b>PR #79</b></td></tr>'
  '<tr><td>② 1턴 1번 파괴 내성 vs 인페르노</td><td>그 턴 내내 버틴다</td><td>A1 파괴의 적용 모드: 내성은 「확인만(횟수 안 씀)」 — 지금 구현과 같음</td></tr>'
  '<tr><td>③ 「다른 카드의 효과를 받지 않는다」</td><td>자기편 카드의 효과도 받지 않는다</td><td>A17의 받는 쪽이 카드인 종류 전부에 내성 검사(규칙이 맞은 뒤에만, 내성 표시 없는 카드는 바로 통과) — 파괴 내성 · 효과 내성 부여 · 직접공격 · 2회 공격 · '
  '공격 대상 불가 · 올인 효과 부여(A22). 엔진 Game.receives · rule_reaches</td></tr>'
  '<tr><td>④ 「패에 넣었을 때」의 드로우</td><td>드로우 포함(턴 시작 드로우 포함)</td><td>E3 「카드가 옮겨졌을 때」(도착지 = 패)가 A2의 「드로우」 설정도 함께 봄 — 카드마다 값으로 나누지 않음. '
  '사기 감지 · 염원 · 거짓 샘물 · 쇠망치도 드로우에 반응(예전 구현은 드로우 제외), 엔진 공통 판정 cards.hand_add</td></tr></table>')

# ── 7. 효율 ──
A('<h2>6. 효율 — 시간 · 공간</h2>')
A('<table><thead><tr><th style="width:18%">항목</th><th>검토</th></tr></thead>'
  '<tr><td>실행 시간</td><td>효과는 카드가 만들어질 때 한 번 조립되고 게임 중에는 조립된 함수를 부르기만 함 — 블록 종류 수는 호출 비용에 들어가지 않음. 단 조립 방식이 좌우: '
  '판정 때 해석하면 가장 뜨거운 경로(legal)에서 2 ~ 7배 → 게임 전체 약 10% 느려짐(추정), <b>코드 생성은 지금 손으로 쓴 코드와 같은 수준</b>(1장 C1 조건).</td></tr>'
  '<tr><td>종류별 색인</td><td>훅(규칙 키 · 공격력/수비력 증감 · 사건 처리 · 상태 점검 · 행동 세금 · 추가 일반소환)을 가진 카드를 판에서 처음 조회할 때 한 번 모으고, 그 카드가 필드에 없으면 바로 빈 목록. '
  '<b>엔진 구현 완료(PR #81)</b> — 같은 시드 1,100판(시드 11 · 23 · 37) 기록 동일, 24 ~ 27% 빠름. 테스트 342개 통과.</td></tr>'
  '<tr><td>메모리</td><td>블록 정의는 블록 종류 수에 비례(코드), 효과마다 값은 418행 × 수 개 — 학습표(약 2.9GB)에 비해 무시할 수준. 색인은 판과 함께 사라짐(220판 뒤 0.10 MB 그대로). '
  '조건 코드 캐시는 프로세스 단위(카드 객체 단위는 누수).</td></tr>'
  '<tr><td>합치지 않은 이유의 비용</td><td>흐름이 다른 블록을 합치면 블록 안이 원인별 분기로 채워져 값이 엉뚱한 종류에 붙어 조용히 무시될 위험(3장) — 그래서 종류가 많은 A17은 종류 표로 허용 값을 조립 때 검사.</td></tr></table>')

# ── 8. 값 · 효과 틀 · 전제 조건 ──
A('<h2 class="pb">7. 블록에서 빠져 값 · 효과 틀로 옮긴 것, 엔진 전제 조건</h2>')
A('<table><thead><tr><th style="width:20%">옮긴 곳</th><th style="width:18%">옛 블록</th><th>내용</th></tr></thead>'
  '<tr><td>값 문법 — 수량식</td><td class="mono">V01 ~ V08</td><td>n · n까지 · 원하는 만큼 · 가능한 만큼 · 「…의 수 × k」(상한) · 앞 결과 수 · 주사위 · 선언 값</td></tr>'
  '<tr><td>값 문법 — 참조</td><td class="mono">T04</td><td>그 카드 · 그 효과 · 파괴한 몬스터 · 묘지로 보낸 카드 · 장착된 몬스터 …(앞 블록의 결과)</td></tr>'
  '<tr><td>고르기의 값</td><td class="mono">K08 · K09 · T06 · J04 · D15</td><td>고르는 제약(같은/연속 레벨 · 같은 속성 · 종류별 매수) · 선언하는 값 · 선택지(택1) · 후보 범위(덱 위 n장 확인)</td></tr>'
  '<tr><td>코스트 모드</td><td class="mono">K01 ~ K04 · K06</td><td>코스트 블록을 따로 두지 않고 처리 블록을 코스트 모드로 — 두플리카토르(「이 카드」만이면 2배 아님) · 델레가토르(지불자) · 내성 무시를 모드 규칙으로 한 곳에서</td></tr>'
  '<tr><td>분기</td><td class="mono">K07 · J04</td><td>「…없는 경우 대신 …」 대체 코스트 · 택1의 갈래 → J2 분기</td></tr>'
  '<tr><td>효과 틀 F02 발동 위치(패) <b>(새로 옮김)</b></td><td class="mono">K05</td><td>「패에서 이 카드를 보여주고 발동」 — 지불이 아니라 발동 위치 + 「공개」 값</td></tr>'
  '<tr><td>효과 틀 F12 부속</td><td class="mono">J06</td><td>「1번 효과 처리 시에 …(별도의 발동 처리를 필요로 하지 않는다)」</td></tr>'
  '<tr><td>효과 틀 F13 처리 방식</td><td class="mono">P27 · P28</td><td>발동(체인에 오름) / 자동(체인 없음 — 「턴 종료 시에」 · 유지비 · 희생제 4번 Q56). 「…할 때마다 … n장 제외」 3장은 재정 ①로 A17 행동 세금으로 바뀜</td></tr>'
  '<tr><td>효과 틀 F14 소환 절차 <b>(새로 옮김)</b></td><td class="mono">R03 · R04</td><td>「…해야만 패에서 특수소환할 수 있다」 · 「…하는 것으로 일반소환할 수 있다」 — 발동이 아님(발동 사건 · 횟수 없음), 소환 무효는 적용, 「발동 코스트 아님」 표시 필수</td></tr>'
  '<tr><td>조합</td><td class="mono">P31</td><td>장착 중 적용 = C1(장착 중) + A14 카드 무효(조건 동안) / E3(장착된 몬스터가 필드에서 벗어났을 때) + A2</td></tr>'
  '<tr><td>삭제</td><td class="mono">C05</td><td>쓰이지 않음</td></tr></table>')
A('<h3>27개판이 제대로 동작하기 위한 엔진 전제 조건</h3><ol>'
  '<li><b>이동 사건 통일</b> — 모든 이동 경로가 (출발지 · 도착지 · 원인 · 주체 · 이동 전 앞면 여부)를 사건에 담는다. 릴리스 원인은 도착지와 무관하게(지금 묘지 대신 덱 경로에서 빠짐 — 질문 1, 39개판 2장). E5 값 변화의 설계(사건 차분)는 39개판 5장 그대로.</li>'
  '<li><b>모드 규칙을 한 곳에서</b> — 코스트(효과가 아님 → 내성 무시, 두플리카토르 · 델레가토르) · 처리(기간) · 적용(조건 동안, [지속] 1턴 횟수, 무효가 되면 해제).</li>'
  '<li><b>종류 표 검증</b> — A17 종류마다 허용 값 · 받는 쪽 · 엔진 판정 위치 · 1턴 횟수 단위를 표로 두고 조립 때 검사. 기본값 없는 필수 값(S1 대상 지정 여부 · A9 다른 쪽 자리 허용)은 빠지면 조립 오류.</li>'
  '<li><b>조건 코드 생성</b> — C1 조건은 조립 때 파이썬 식으로 만들어 한 번 compile, 같은 문장은 프로세스 캐시.</li>'
  '<li><b>학습표 호환</b> — 판단 이름(「카드명#번호」 · 「서치:이유」 · 「인카운터 분기」)은 지금과 같게.</li></ol>')

# ── 9. 39 → 27 ID ──
A('<h2 class="pb">8. 39개판 → 27개판 ID</h2>')
items = list(d['map39'].items())
half = (len(items) + 1) // 2
A('<table><thead><tr>' + '<th style="width:5%">39개판</th><th style="width:14%">이름</th><th>27개판</th>' * 2 + '</tr></thead>')
for i in range(half):
    row = ''
    for j in (i, i + half):
        if j < len(items):
            k, v = items[j]; changed = v != k
            row += f'<td class="mono">{k}</td><td>{E(d["new39"][k])}</td><td class="small">{"<b>" if changed else ""}{E(v)}{"</b>" if changed else ""}</td>'
        else: row += '<td></td><td></td><td></td>'
    A('<tr>' + row + '</tr>')
A('</table>')

# ── 10. 옛 → 새 ──
A('<h2 class="pb">9. 옛 블록(124개) → 27개판 대응표</h2>')
items = [(k, OC[k][0], d['old2new'][k]) for k in OC if not k.startswith('F')]
half = (len(items) + 2) // 3
cols = [items[i * half:(i + 1) * half] for i in range(3)]
A('<table><thead><tr>' + '<th style="width:5%">옛</th><th style="width:15%">이름</th><th style="width:13%">새</th>' * 3 + '</tr></thead>')
for i in range(half):
    A('<tr>' + ''.join((f'<td class="mono">{E(c[i][0])}</td><td>{E(c[i][1])}</td><td class="small">{E(c[i][2])}</td>' if i < len(c) else '<td></td><td></td><td></td>') for c in cols) + '</tr>')
A('</table>')

# ── 11. 블록별 쓰는 효과 ──
A('<h2 class="pb">10. 27개 블록별 쓰는 효과 (전수)</h2>')
A('<table><thead><tr><th style="width:5%">ID</th><th style="width:12%">블록</th><th style="width:5%">효과 수</th><th>쓰는 효과(카드 코드 #번호)</th></tr></thead>')
for s in d['stats']:
    A(f'<tr><td class="mono">{s["id"]}</td><td>{E(s["name"])}</td><td class="n">{s["effects"]}</td><td class="small">{" · ".join(E(u) for u in s["uses"])}</td></tr>')
A('</table>')
A('</body></html>')
open(OUT, 'w', encoding='utf-8').write('\n'.join(H)); print('ok')
