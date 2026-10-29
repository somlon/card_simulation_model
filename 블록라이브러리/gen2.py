"""new.json → 블록 라이브러리 목록 (통합판) HTML"""
import json, sys, html
d = json.load(open(sys.argv[1], encoding='utf-8')); OUT = sys.argv[2]
E = html.escape
S = {s['id']: s for s in d['stats']}
OC = d['oldcat']
n_new = len(d['stats']); n_old = len([k for k in OC if not k.startswith('F')])
star = [s for s in d['stats'] if s['cards'] == 1]

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
H = [f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>블록 라이브러리 목록 통합판</title><style>{css}</style></head><body>']
A = H.append
A('<h1>블록 라이브러리 목록 — 통합판</h1>')
A('<div class="sub">2026-10-27 · 앞서 보낸 목록(124개)과 전수 조사 대응표(418행)를 기준으로 통합을 검토 · 코드 기준 <span class="mono">model/main</span> a925f24 (PR #77 · #78 머지 뒤) · 데이터 <span class="mono">data/main</span> 3969ea9 · <b>개정: E5 카운터 + E7 HP → 「값 변화」(사건 차분), E6 유지 (사용자 지시)</b></div>')
A('<div class="kpi">'
  f'<div>블록<b>{n_old} → {n_new}개</b></div>'
  f'<div>대응되지 않는 문장<b>0행</b><span class="small">418행 전부 새 블록으로 다시 대응</span></div>'
  f'<div>쓰이지 않는 블록<b>0개</b></div>'
  f'<div>값 문법으로 옮김<b>9개</b><span class="small">수량 8 · 참조 1</span></div>'
  f'<div>효과 틀 속성으로 옮김<b>3개</b><span class="small">부속 · 자동 처리</span></div>'
  f'<div>카드 1장 전용<b>{len(star)}개</b><span class="small">앞 목록 29개</span></div>'
  '</div>')
A('<div class="box ok"><b>결론</b><ul>'
  f'<li><b>124개 → {n_new}개로 통합합니다.</b> 통합 기준은 아래 4가지를 <b>모두</b> 만족할 때만입니다 — 같은 게임 행위(같은 엔진 판정 위치), 차이가 값으로 표현됨, 재정이 걸리는 성질(대상 지정 · 제거 효과 · 코스트 여부 · 발동 여부)이 값에서 정확히 나옴, 그 차이를 구분하는 재정이 없음.</li>'
  '<li>가장 큰 통합은 <b>「모드」</b>입니다 — 같은 행위가 코스트(<span class="tag cost">cost</span>) · 처리(<span class="tag">do</span>) · [지속] 적용(<span class="tag apply">apply</span>)에 따로 블록으로 있던 것을 '
  '하나로 합치고, 모드별 규칙(코스트는 효과가 아님 → 내성 무시 · 두플리카토르 적용 / 처리는 기간 / [지속]은 조건 동안 · 1턴 횟수)을 엔진 한 곳에서 처리합니다.</li>'
  '<li><b>합치지 않은 것</b>도 표로 정리했습니다(4장) — 파괴 · 릴리스 · 드로우 · 덱 위 보내기 · 특수소환 · 무효 3종 · 카드 상태와 플레이어 규칙은 재정이 서로 다른 행위로 다루므로 그대로 둡니다.</li>'
  '<li>실행 속도 · 메모리: 블록 종류 수는 실행 중 계산량을 바꾸지 않습니다(조립 때 값을 풀어 두면 통합 전과 같음). 대신 통합으로 「사건 → 효과」 · 「규칙 종류 → 출처」 색인을 한 곳에서 만들 수 있게 되어, '
  '지금 엔진의 실제 병목(사건마다 전 효과의 발동 가능 판정, [지속] 규칙 조회마다 필드 전체 훑기)을 줄일 길이 생깁니다(3장).</li>'
  '<li><b>E5 값 변화</b>: 카운터 수 · 카운터 합계 · HP가 기준에 닿은 순간을 하나로 — 상태를 기억해 두는 방식이 아니라 그 값의 변화 사건 때 직전 값을 계산하는 <b>사건 차분 방식</b>(5장). E6 무효화는 그대로.</li>'
  '<li>질문 1(릴리스)에 따라 W09는 「묘지로 보내졌을 때」에 합치지 않았습니다 — 새 이동 사건 E3에서 릴리스는 <b>원인</b>으로 식별하며 도착지와 무관합니다(2장).</li>'
  '</ul></div>')

# ── 1. 새 블록 목록 ──
A('<h2>1. 새 블록 목록</h2>')
A('<p>모드: <span class="tag cost">cost</span> 코스트로 씀 · <span class="tag">do</span> 처리로 씀 · <span class="tag apply">apply</span> [지속] 적용으로 씀(지금 카드 풀에서 실제로 쓰이는 모드). '
  '효과 수 · 카드 수는 전수 조사 418행을 새 블록으로 다시 센 값. ★ = 카드 1장만 씀.</p>')
A('<table><thead><tr><th style="width:4%">ID</th><th style="width:12%">블록</th><th>하는 일 · 값</th><th style="width:10%">모드</th><th style="width:5%">효과 수</th><th style="width:5%">카드 수</th><th style="width:19%">합친 옛 블록</th></tr></thead>')
cur = None
for s in d['stats']:
    if s['cat'] != cur:
        cur = s['cat']; A(f'<tr class="grp"><td colspan="7">{E(cur)}</td></tr>')
    md = ''.join(f'<span class="tag {m if m != "do" else ""}">{m}</span>' for m in s['modes']) if s['id'][0] in 'AS' or s['id'] == 'J2' else '—'
    st = ' <span class="star">★</span>' if s['cards'] == 1 else ''
    old = ' '.join(f'{o}' for o in s['old'])
    oldn = ', '.join(E(OC[o][0]) for o in s['old'] if o in OC)
    A(f'<tr><td class="mono">{s["id"]}</td><td><b>{E(s["name"])}</b>{st}<span class="en">{E(s["en"])}</span></td><td>{E(s["desc"])}</td><td>{md}</td>'
      f'<td class="n">{s["effects"]}</td><td class="n">{s["cards"]}</td><td class="small"><span class="mono">{E(old)}</span><br>{oldn}</td></tr>')
A('</table>')

# ── 2. 질문 1 ──
A('<h2 class="pb">2. 릴리스(W09) — 질문 1에 대한 정리</h2>')
A('<div class="box warn"><ul>'
  '<li>앞 PDF의 「W09 릴리스되었을 때 → W05 묘지로 보내졌을 때의 원인 값으로 합치기」 제안은 <b>철회합니다.</b> 지적대로 릴리스는 행위(원인)이고 묘지는 도착지입니다. '
  '릴리스된 카드가 묘지 대신 다른 곳(덱 등)으로 가도 「릴리스되었을 때」는 성립해야 합니다.</li>'
  '<li>통합판에서는 이동 사건 E3 하나에 <b>출발지 · 도착지 · 원인</b>을 따로 둡니다. 「릴리스되었을 때」 = E3(원인 = 릴리스), 도착지 값은 비움 → 어디로 가든 성립합니다. '
  '「묘지로 보내졌을 때」 = E3(도착지 = 묘지). 둘은 서로 다른 값이라 섞이지 않습니다.</li>'
  '<li><b>지금 엔진에서 확인한 빈틈:</b> 릴리스는 <span class="mono">Game.tribute → send_grave(released=True)</span>로 처리되는데, 「묘지로 보내질 경우 덱으로 되돌아간다」(코로나 · 리퍼 2번 — grave_redirect) 경로에서는 '
  '<span class="mono">leave_field</span> 사건에 released 표시가 빠지고 <span class="mono">to_grave</span> 사건은 나지 않습니다. 지금 「릴리스되었을 때」를 가진 카드(표시목 · 짐승조커)에는 이 경로가 없어 실제 결과는 바뀌지 않지만, '
  '조립식 전환 때 「모든 이동 경로가 원인을 사건에 담는다」를 엔진 전제 조건으로 고칩니다(7장).</li></ul></div>')

# ── 3. 복잡도 ──
A('<h2>3. 효율 검토 — 시간 · 공간 복잡도와 구조</h2>')
A('<table><thead><tr><th style="width:18%">항목</th><th>검토</th></tr></thead>'
  '<tr><td>실행 시간</td><td>효과는 카드가 만들어질 때 한 번 조립되고, 게임 중에는 조립된 함수를 부르기만 합니다. 블록 종류 수(124 · 40)는 이 호출 비용에 들어가지 않으므로 '
  '<b>점근 복잡도는 같습니다.</b> 단, 통합 블록이 값을 매 호출마다 해석하면 상수 비용이 늘어나므로 <b>조립 시점에 값을 풀어 전용 함수로 고정</b>합니다(부분 평가) — 그러면 통합 전과 같은 비용입니다.</td></tr>'
  '<tr><td>메모리</td><td>블록 정의는 블록 종류 수에 비례(코드), 효과마다 값은 효과 수 × 값 수(418행 × 수 개) — 어느 쪽도 게임 상태 · 학습표(약 2.9GB)에 비해 무시할 수준. '
  '통합하면 블록 구현 코드와 같은 판정의 중복이 줄어듭니다.</td></tr>'
  '<tr><td>지금 엔진의 실제 병목<br><span class="small">(코드 구조 기준)</span></td><td>① 트리거 창: 사건 묶음마다 <span class="mono">collect</span>가 두 플레이어의 패 · 필드 · 묘지 · 제외 · 스킬의 모든 트리거 효과 × 사건 수만큼 '
  '<span class="mono">legal()</span>(가장 비싼 판정)을 부릅니다. ② [지속] 규칙 조회 <span class="mono">rule()</span>: 부를 때마다 [지속] 출처 전체를 훑고, AI가 후보마다 여러 번 부릅니다. '
  '③ <span class="mono">emit()</span>마다 모든 [지속] 출처의 <span class="mono">on_event</span>를 부릅니다.</td></tr>'
  '<tr><td>통합이 주는 효율</td><td>① 발동 시점 블록이 6개로 줄고 엔진 사건과 바로 대응 → 조립 때 효과마다 「구독하는 사건」이 정해져 <b>사건 → 효과 색인</b>을 만들 수 있습니다. '
  '트리거 창의 <span class="mono">legal()</span> 호출을 「그 사건을 구독한 효과」로만 줄입니다(지금은 모든 트리거 효과). '
  '② 카드 상태(A20) · 플레이어 규칙(A21)이 등록의 유일한 통로 → <b>종류 → 출처 색인</b>을 등록 · 해제 때 유지하면 <span class="mono">rule()</span> 조회가 「출처 전체」에서 「그 종류의 출처」로 줄어듭니다. '
  '③ 모드별 재정(코스트 · 기간 · 1턴 횟수)이 한 곳에 모여, 재정을 한 번 고치면 모든 카드에 적용됩니다(지금은 카드 함수마다 흩어짐).</td></tr>'
  '<tr><td>통합의 비용</td><td>A20 · A21처럼 종류가 많은 블록은 「종류 표」(종류마다 허용 값 · 엔진 판정 위치 · 1턴 횟수 단위)를 두고 조립 때 검사해야 합니다 — 잘못된 값이 조용히 무시되면 찾기 어려운 버그가 되기 때문입니다(6장 · 7장).</td></tr>'
  '</table>')

# ── 4. 합치지 않은 것 ──
A('<h2 class="pb">4. 합치지 않은 것과 이유</h2>')
KEEP = [
 ('A1 파괴 ↔ A2 이동', '「파괴」는 재정상 따로 다루는 행위 — 파괴 내성, 「파괴되었을 때」 트리거, 실렉스 「파괴 이외의 방법으로 필드를 벗어나지 않는다」. 합치면 모든 이동에 파괴 판정 분기가 섞임'),
 ('A3 릴리스 ↔ A2 이동', '릴리스 불가 성질(아우렘 · 수호자 · 퇴마의 부적 …), 「릴리스되었을 때」가 도착지와 무관(질문 1)'),
 ('A4 드로우 ↔ A2 이동(덱 → 패)', '드로우는 따로 세는 행위 — 아이라리움 1번이 「드로우하거나 덱에서 패에 넣을 때마다」로 둘을 나눠 적음, 플라이 1번(Q38) · 덱→패 금지(Q46), 턴 시작 드로우'),
 ('A5 덱 위 보내기 ↔ A2 이동', '고르지 않고 위에서부터, 부족분 다른 덱에서, 덱이 모자라면 패배, 간절한 마음 「1장 추가」는 이 행위에만'),
 ('A6 특수소환 ↔ A2 · A7', '소환 규칙 전체 — 소환 조건([제약]) · 같은 이름 규칙(3-6 f) · 소환 무효 · [소환] 트리거 · 표시 형식 선택'),
 ('A12 · A13 · A14 무효 3종', '무효의 대상이 다름(발동 / 소환 / 카드) — 희생제 4번(Q56) · 스킬 무효는 턴 종료 시까지 · 뒷면 마법은 카드 무효를 받지 않음 · 내성 카드의 발동은 무효로 할 수 없음(Q60)'),
 ('A17 공격력 · 수비력 ↔ A20 카드 상태', '수치 계산(기준값 + 증감, [지속] 증감은 매번 다시 계산, 내성 카드에는 적용 안 됨) ↔ 있다/없다 상태'),
 ('A20 카드 상태 ↔ A21 플레이어 규칙', '받는 쪽이 카드인가 플레이어인가 — 내성 판정이 다름(버터플라이 2번 「자신」을 카드로 보느냐 플레이어로 보느냐에 따라 결과가 갈렸던 사례)'),
 ('E1 소환 ↔ E3 이동', '소환 사건은 소환 종류(일반 · 특수)와 「소환 무효를 [소환] 효과보다 먼저」 순서가 따로'),
 ('E2 발동 ↔ E3 이동', '발동은 체인에 오르는 사건 — 응답 · 무효의 대상'),
 ('S1 고르기의 「대상 지정 여부」', '합쳤지만 <b>기본값 없는 필수 값</b>으로 둠 — 대상 지정 여부가 내성 · 뒷면 카드 · 제거 효과(Q6) 판정을 좌우하므로 빠뜨리면 조립 오류로 막음'),
 ('E6 무효화 ↔ E2 발동 · E5 값 변화', '무효화는 엔진이 내는 사건(발동 무효 · 카드 무효 · 장착 무효 모두 negated) — 지금 형태가 사건 모델에 맞음. E2에 「무효됨」 단계를 넣으면 체인 응답 시점과 처리 뒤 트리거 시점이 한 블록에 섞여 E2를 쓰는 32개 효과 모두가 단계 값을 가져야 함, 카드 무효를 상태로 보면 카드마다 기억이 필요(5장)'),
 ('A11 · A13 · A23 · A25 · A26', '다른 블록과 기능이 겹치지 않음 — 카드 1장 전용이어도 유지'),
]
A('<table><thead><tr><th style="width:24%">블록</th><th>합치지 않은 이유</th></tr></thead>')
for a, b in KEEP: A(f'<tr><td>{E(a)}</td><td>{b}</td></tr>')
A('</table>')

# ── 5. E5 값 변화 ──
A('<h2 class="pb">5. E5 값 변화 — 설계와 검토</h2>')
A('<table><thead><tr><th style="width:15%">쓰는 효과</th><th style="width:24%">값</th><th style="width:20%">기준</th><th style="width:14%">방향 · 원인</th><th>구독 사건 · 직전 값</th></tr></thead>'
  '<tr><td>희생제 #3 (CRSD-018)</td><td>이 카드의 저주 카운터 수</td><td>정확히 4가 됨 (3 → 5는 아님 — 사용자 답변 2026-10-20)</td><td>증가만(「놓였을 때」)</td><td><span class="mono">counter</span> — 직전 = 지금 − 변화량</td></tr>'
  '<tr><td>월식 (UNSL-002)</td><td>자신 필드 앞면 「호박옥」 몬스터의 봉인 카운터 합계</td><td>5 이상이 됨</td><td>—</td><td><span class="mono">counter</span> — 바뀐 카드가 집합에 속할 때만 변화량 반영</td></tr>'
  '<tr><td>깨어남의 종 (UNSL-004)</td><td>자신의 HP</td><td>2000 이하가 됨</td><td>대미지(자해 포함)</td><td><span class="mono">damage</span> — 직전 = 지금 + 대미지</td></tr></table>')
A('<h3>규칙</h3><ol>'
  '<li><b>값은 사건의 변화량으로 직전 값을 계산할 수 있는 것만</b> 허용하고 조립 때 검사 — 지금은 카운터 수 · 카운터 합계 · HP.</li>'
  '<li><b>기준</b>: 정확히 n이 됨 · n 이상이 됨 · n 이하가 됨 — 직전 값과 지금 값으로 판정(직전에 이미 만족했으면 발동하지 않음).</li>'
  '<li><b>방향 · 원인</b> 값을 둔다 — 「놓였을 때」는 증가만. 감소로 기준에 닿는 경우를 막는다.</li>'
  '<li><b>구독 사건은 값 종류에서 자동</b>(카운터 → counter, HP → damage) — 그 사건에서만 계산, 기억해 둘 상태가 없다(메모리 0).</li>'
  '<li><b>값은 사건이 난 순간에 계산해 사건에 적는다</b> — 트리거를 모을 때는 상태가 더 바뀌었을 수 있다(지금 월식 · 깨어남의 종 코드가 쓰는 방식을 한 곳으로).</li>'
  '<li><b>한계</b>: 그 사건으로 오지 않는 변화(컨트롤 이동으로 합계가 바뀜 등)는 보지 않는다 — 지금 동작과 같다(회귀 없음). 재정이 그런 경우도 발동이라고 하면, 엔진이 그 사건을 내도록 고친 뒤 구독 목록에 더한다.</li></ol>')
A('<h3>검토한 다른 안 — 「조건이 참이 되었을 때」(상태 감시, E5 · E6 · E7 통합) — 철회</h3>')
A('<p>조건의 참/거짓을 기억해 두었다가 사건마다 다시 계산해 거짓 → 참이 되면 발동하는 방식. 지금 엔진에서 아래 문제가 확인되어 채택하지 않았습니다.</p>')
A('<table><thead><tr><th style="width:18%">문제</th><th>경우 (코드 근거)</th></tr></thead>'
  '<tr><td>(a) 잘못 발동</td><td>희생제 #3을 「= 4」로 쓰면 6개에서 처키 코스트로 2개를 떼어 4개가 될 때도 발동(「놓였을 때」가 아님). 「≥ 4」로 쓰면 3 → 5에서 발동(재정 위반). 상태만으로는 증가로 됐는지 알 수 없음</td></tr>'
  '<tr><td>(b) 발동 누락</td><td><span class="mono">Game.heal</span>은 사건을 내지 않음 — HP 1500(참) → 회복 3000(기억 갱신 안 됨) → 대미지 1800: 발동해야 하는데 참 → 참이라 안 함(지금 호박옥 덱에는 회복 카드가 없어 드러나지 않음)</td></tr>'
  '<tr><td>(c) 발동 누락</td><td><span class="mono">Game.change_control</span>도 사건을 내지 않음 — 상대가 원페어로 내 호박옥 몬스터를 가져가 합계가 조용히 줄면, 다시 5가 되어도 참 → 참</td></tr>'
  '<tr><td>(d) 잘못 발동 위험</td><td>패 · 세트 상태에서 조건을 보는 카드(월식 · 깨어남의 종)는 영역에 들어오는 순간마다 기억을 초기화해야 함 — 빠뜨리면 「이미 5개 이상인데 1개 더」에서 발동(테스트 <span class="mono">test_eclipse_not_when_already_five</span>)</td></tr>'
  '<tr><td>(e) 발동 누락</td><td>강령(E6 흡수 시) — 「무효인 자신 카드가 있다」 하나로 기억하면, 이미 무효인 카드가 있을 때 두 번째 카드가 무효가 되어도 참 → 참. 카드마다 기억이 필요</td></tr>'
  '<tr><td>비효율</td><td>가장 자주 불리는 <span class="mono">emit</span>마다 감시 중인 모든 카드(패 · 세트 포함)의 조건을 다시 계산 — 범용 조건이라 나중에 비싼 조건이 붙으면 모든 사건에 숨은 비용. '
  '(b)(c)를 막으려면 엔진의 모든 상태 변경이 사건을 내도록 고쳐야 함 — 블록 1개를 줄이는 이득보다 큰 공사</td></tr></table>')

# ── 5. 종류 표 ──
A('<h2 class="pb">6. 종류 표 — 카드 상태(A20) · 플레이어 규칙(A21)</h2>')
A('<p>종류는 블록이 아니라 그 블록의 값입니다. 종류마다 엔진이 판정하는 자리가 이미 따로 있으므로(지금 코드의 플래그 · 규칙 키), 블록은 등록만 하고 판정은 엔진이 합니다.</p>')
ST = [
 ('효과 내성', 'P01 · D32', '출처(상대 · 다른 카드 · 「X」 이외 이름 · 카드군 이외) · 비대상만 · 카운터는 받음 · 기간/조건', 'DTBG-011 #2 · TAXM-004 #1 · WSFT-014 #2 · COMN-004(기간)', 'Game.immune · blocked'),
 ('대상 내성', 'P02', '상대 효과의 대상이 되지 않음', 'AMBR-005 #2', 'Game.immune (untargetable_opp)'),
 ('파괴 내성', 'P03 · D32', '전투 · 효과', 'PKBS-001 #1 · AMBR-002 #2 · AMBR-016 #2 · AMBR-015(기간)', 'rule indestructible'),
 ('릴리스 불가', 'P04 · D32', '—', 'AMBR-001 #2 · CRSD-008 #1 · COMN-004(기간)', 'releasable · no_release'),
 ('필드 이탈 불가', 'P05', '파괴 이외의 방법', 'AMBR-003 #2', 'Game.stays'),
 ('표시 형식 고정', 'P06 · D32', '—', 'AMBR-001 #3 · AMBR-015(기간)', 'can_change_pos'),
 ('공격 불가', 'P10 · D32', '공격 · 공격 선언', 'AMBR-001 #3 · PKBS-001-1 #2 · AMBR-010 #1(기간)', 'can_attack_with'),
 ('효과 발동 불가', 'D32', '기간', 'DTBG-022', 'no_act_until'),
 ('공격 횟수 +n', 'D25 · P09', '이 턴 / 지속 · 필터', 'FGTR-003 #2 · DTBG-007 #1 · WSFT-012 #2', 'extra_attacks · double_attack'),
 ('전체 공격', 'P08', '—', 'SLNA-004 #3', 'attack_all'),
 ('직접공격 가능', 'P07', '상대 몬스터가 있어도', 'SWRM-001 ~ 010 #2 (번성충 10장)', 'rule direct_attack'),
 ('수비 표시 불가', 'P12', '대상 필터(상대 필드 몬스터)', 'FGTR-010 #1', 'rule no_defense'),
 ('다른 카드군 · 속성으로도 취급', 'P18', '카드군 · 속성 목록', 'WSFT-014 #2 · PKBS-005 #1 · PKBS-006 #1', 'also_groups · all_suits'),
 ('레벨 · 속성 부여', 'D30', '레벨 · 속성 · 몬스터 취급', 'PKBS-011 #1 · PKBS-014 #1 · PKBS-016 #2-a', 'clear_on_leave'),
 ('묘지 대신 덱', 'P29', '—', 'SLNA-003 #2 · SLNA-004 #2', 'grave_redirect'),
 ('소환 제한 ([제약], 어디서나)', 'R01 · R02', '효과로만 · 스킬로만 · 다른 카드의 효과로 소환 불가', 'SLNA-003 #1 · WSFT-014 #1 · DTBG-013 #1', 'effect_only · ss_by_skill_only · ss_self_only'),
]
A('<h3>카드 상태 종류 (A20)</h3><table><thead><tr><th style="width:15%">종류</th><th style="width:8%">옛 블록</th><th style="width:25%">값</th><th>쓰는 효과</th><th style="width:16%">엔진 판정</th></tr></thead>')
for r in ST: A('<tr>' + ''.join(f'<td{" class=mono" if i in (1, 4) else ""}>{E(x)}</td>' for i, x in enumerate(r)) + '</tr>')
A('</table>')
RU = [
 ('금지', 'P14 · D33', '트리거 마법 발동 · 효과로 덱→패 · 몬스터로 공격 · 대미지 주기 · 전투로 몬스터 파괴 · 발동 n회 제한', 'COMN-006 #2 · DGMS-012 #2 · DTBG-014 #3 · SWRM-010 #1 · COMN-007 · DGMS-015 · CRSD-002 #1', 'rule no_trigger_spell · no_deck_to_hand · act_limit · no_damage'),
 ('직접공격 허용(상대가 자신에게)', 'P07', '조건', 'AMBR-006 #3', 'rule direct_attack'),
 ('공격 강제', 'P11', '조건', 'FGTR-010 #1', 'rule must_attack'),
 ('전투 대미지 배율', 'P13', '0 · 절반 · 조건', 'DGMS-012 #1 · AMBR-017 #3', 'rule half/no_battle_damage'),
 ('필드 매수 제한', 'P15', '카드군 · 수', 'SLNA-024 #1', 'rule field_limit'),
 ('코스트 배수', 'P19', '누구 · 배수(「이 카드」 제외)', 'TAXM-002 #1', 'rule cost_double'),
 ('코스트 대납', 'P20', '누구', 'TAXM-001 #1', 'rule cost_transfer'),
 ('특정 코스트 매수', 'P21', '대상 효과 · 매수', 'TAXM-010 #2', 'rule seri_lw_one'),
 ('추가 일반소환', 'P22 · D33', '필터 · 횟수 · 기간', 'PKBS-009 #1 · PKBS-003 #1 · DTBG-023', 'extra_normal'),
 ('패에서 [신속] 발동', 'P23', '필터 · 횟수', 'PKBS-015 #1', 'rule pk_hand_quick'),
 ('덱 위 추가 보내기', 'P24', '수', 'WSFT-026 #1', 'rule dump_extra'),
 ('시작 패 매수', 'D36', '매수', 'PKBS-016 #1', '스킬 규칙'),
 ('맹세', 'R05', '카드군 · 기간(다음 상대 턴 종료 시까지)', 'SWRM-001 ~ 010 #1 (번성충 10장) · AMBR-011', 'oath'),
]
A('<h3>플레이어 규칙 종류 (A21)</h3><table><thead><tr><th style="width:15%">종류</th><th style="width:8%">옛 블록</th><th style="width:25%">값</th><th>쓰는 효과</th><th style="width:16%">엔진 판정</th></tr></thead>')
for r in RU: A('<tr>' + ''.join(f'<td{" class=mono" if i in (1, 4) else ""}>{E(x)}</td>' for i, x in enumerate(r)) + '</tr>')
A('</table>')

# ── 6. 값 문법 · 효과 틀 · 전제 조건 ──
A('<h2 class="pb">7. 블록에서 빠져 값 · 효과 틀로 옮긴 것, 엔진 전제 조건</h2>')
A('<table><thead><tr><th style="width:20%">옮긴 곳</th><th style="width:20%">옛 블록</th><th>내용</th></tr></thead>'
  '<tr><td>값 문법 — 수량식</td><td class="mono">V01 ~ V08</td><td>n · n까지 · 원하는 만큼 · 가능한 만큼 · 「…의 수 × k」(상한) · 앞 결과 수 · 주사위 · 선언 값 — 블록의 「매수 · 수치」 값 자리에 들어가는 식</td></tr>'
  '<tr><td>값 문법 — 참조</td><td class="mono">T04</td><td>그 카드 · 그 효과 · 파괴한 몬스터 · 묘지로 보낸 카드 · 장착된 몬스터 …(앞 블록의 결과를 가리킴)</td></tr>'
  '<tr><td>고르기의 제약</td><td class="mono">K08 · K09</td><td>같은/연속 레벨 · 같은 속성 · 종류별 매수 — S1 고르기의 「고르는 제약」 값</td></tr>'
  '<tr><td>코스트 모드</td><td class="mono">K01 ~ K06</td><td>코스트 블록을 따로 두지 않고 처리 블록을 코스트 모드로 씀 — 두플리카토르(「이 카드」 제외 매수 2배) · 델레가토르(지불자) · 내성 무시가 모드 규칙으로 한 곳에서</td></tr>'
  '<tr><td>분기</td><td class="mono">K07</td><td>「…없는 경우 대신 …」 대체 코스트 → J2 분기</td></tr>'
  '<tr><td>효과 틀 F12 부속</td><td class="mono">J06</td><td>「1번 효과 처리 시에 …(별도의 발동 처리를 필요로 하지 않는다)」</td></tr>'
  '<tr><td>효과 틀 F13 처리 방식(새)</td><td class="mono">P27 · P28</td><td>발동(체인에 오름) / 자동(체인 없음 — 「…할 때마다」 · 「턴 종료 시에」 · 유지비 · 희생제 4번 Q56). 자동 처리는 시점 블록(E) + 처리 블록(A)으로 조립</td></tr>'
  '<tr><td>조합</td><td class="mono">P31</td><td>장착 중 적용 = C2(장착 중) + A14 카드 무효(조건 동안) / E3(장착된 몬스터가 필드에서 벗어났을 때) + A2</td></tr>'
  '<tr><td>삭제</td><td class="mono">C05</td><td>쓰이지 않음(F09 · E4 · F13의 값으로 표현됨)</td></tr></table>')
A('<h3>통합판이 제대로 동작하기 위한 엔진 전제 조건</h3><ol>'
  '<li><b>이동 사건 통일</b> — 모든 이동 경로가 (출발지 · 도착지 · 원인 · 주체 · 이동 전 앞면 여부)를 사건에 담는다. 특히 릴리스 원인은 도착지와 무관하게(질문 1 — 지금 묘지 대신 덱 경로에서 빠짐).</li>'
  '<li><b>모드 규칙을 한 곳에서</b> — 코스트(효과가 아님 → 내성 무시, 두플리카토르 · 델레가토르, 지불할 수 없으면 발동 불가) · 처리(기간) · 적용(조건 동안, [지속] 1턴 횟수, 무효가 되면 해제).</li>'
  '<li><b>종류 표 검증</b> — A20 · A21 종류마다 허용 값 · 엔진 판정 위치 · 1턴 횟수 단위를 표로 두고 조립 때 검사. 기본값 없는 필수 값(S1 대상 지정 여부)은 빠지면 조립 오류.</li>'
  '<li><b>자동 처리(F13)</b> — 체인에 오르지 않는 처리를 엔진의 종료 시 처리 · 사건 처리 경로로 조립.</li>'
  '<li><b>학습표 호환</b> — 판단 이름(「카드명#번호」 · 「서치:이유」)은 지금과 같게 만든다.</li></ol>')

# ── 7. 옛 → 새 대응표 ──
A('<h2 class="pb">8. 옛 블록 → 새 블록 대응표 (124개)</h2>')
items = [(k, OC[k][0], d['old2new'][k]) for k in OC if not k.startswith('F')]
half = (len(items) + 2) // 3
cols = [items[i * half:(i + 1) * half] for i in range(3)]
A('<table><thead><tr>' + '<th style="width:5%">옛</th><th style="width:15%">이름</th><th style="width:13%">새</th>' * 3 + '</tr></thead>')
for i in range(half):
    A('<tr>' + ''.join((f'<td class="mono">{E(c[i][0])}</td><td>{E(c[i][1])}</td><td class="small">{E(c[i][2])}</td>' if i < len(c) else '<td></td><td></td><td></td>') for c in cols) + '</tr>')
A('</table>')

# ── 8. 블록별 쓰는 효과 ──
A('<h2 class="pb">9. 새 블록별 쓰는 효과 (전수)</h2>')
A('<table><thead><tr><th style="width:5%">ID</th><th style="width:12%">블록</th><th style="width:5%">효과 수</th><th>쓰는 효과(카드 코드 #번호)</th></tr></thead>')
for s in d['stats']:
    A(f'<tr><td class="mono">{s["id"]}</td><td>{E(s["name"])}</td><td class="n">{s["effects"]}</td><td class="small">{" · ".join(E(u) for u in s["uses"])}</td></tr>')
A('</table>')
A('</body></html>')
open(OUT, 'w', encoding='utf-8').write('\n'.join(H)); print('ok')
