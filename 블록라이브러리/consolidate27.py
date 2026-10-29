"""블록 통합 27개판: 옛 블록 124개 → (39개판 대응 규칙 consolidate.py) → 2026-10-27 추가 통합 결정으로 27개.
사용: python3 -I consolidate27.py out.json new27.json"""
import json, sys, os, collections
o = json.load(open(sys.argv[1], encoding='utf-8'))

# 39개판의 표(NEW · VALUE · FRAME · M · OVR · P28_TIMING · MODE_OF)를 그대로 읽는다
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'consolidate.py'), encoding='utf-8').read()
ns = {'o': o, 'json': json, 'sys': sys, 'collections': collections}
exec(src[src.index('# 새 블록:'):src.index('rows_new = []')], ns)
NEW39, VALUE, FRAME, M, OVR, P28_TIMING, MODE_OF = (ns[k] for k in ('NEW', 'VALUE', 'FRAME', 'M', 'OVR', 'P28_TIMING', 'MODE_OF'))

# ── 39 → 27 (사용자 결정 2026-10-27 「소모 시간이 적은 쪽, 같으면 메모리가 적은 쪽」) ──
MERGE = {'C2': 'C1', 'S2': 'S1', 'A4': 'A2', 'A5': 'A2', 'A11': 'A9', 'A20': 'A17', 'A21': 'A17', 'A26': 'A17', 'A25': 'A1'}
def to27(t, b):
    """39개판 블록 t(옛 블록 b에서 온 것) → 27개판 블록 목록, 효과 틀"""
    if t == 'A10':   # 공개 · 확인 해체: 「패에서 보여주고 발동」 → 효과 틀 F02 발동 위치(패), 확인하고 고르기 → 고르기, 확인한 나머지를 덱으로 → 이동
        return {'K05': ([], 'F02'), 'D15': (['S1'], None), 'D17': (['A2'], None)}[b]
    if t == 'A24': return [], 'F14'           # 소환 절차 → 효과 틀 F14 (발동 코스트 아님)
    if t == 'J3': return ['S1', 'J2'], None   # 택1 → 고르기(선택지) + 분기
    return [MERGE.get(t, t)], None

D = lambda k: NEW39[k][3]
NEW = {
 'E1': NEW39['E1'], 'E2': NEW39['E2'], 'E3': NEW39['E3'], 'E4': NEW39['E4'], 'E5': NEW39['E5'], 'E6': NEW39['E6'],
 'C1': ('조건', 'condition', '조건', '어디에 무엇이 몇 장 있는가 · 그 카드(이 카드 · 앞에서 정한 카드)가 …인가를 하나로 — 집합(필드 · 이 카드 · 앞 결과 …) × '
        '필터(위치 · 앞뒷면 · 카운터 · 종류 · 카드군 · 장착 중) × 수량 비교(n 이상 · 없음 · 정확히 · 각 「X」마다). 「필드」 범위는 쓰는 곳마다 값으로(Q37 · Q41). '
        '조립은 코드 생성 + 같은 문장 캐시(프로세스 단위)'),
 'S1': ('고르기', 'select', '대상 · 고르기', '카드 · 값 · 선택지를 고른다 — 고르는 것: 카드 / 레벨 · 속성 등 값(옛 선언) / 선택지(옛 택1 — 뒤 처리는 J2 분기). '
        '대상 지정 여부(카드일 때 기본값 없는 필수 값) · 고르는 때(발동 시/처리 시) · 고르는 사람(자신/상대/무작위) · 고르는 제약(같은/연속 레벨 · 같은 속성 · 종류별 매수) · '
        '후보 범위(덱 위 n장 확인 포함) · 공개 여부. 선언 · 택1의 결정 방식은 지금 고정 규칙 그대로'),
 'A1': ('파괴', 'destroy', '처리', D('A1') + ' / 적용 모드: [지속] 조건 자동 파괴(옛 A25 — 인페르노: 대상을 먼저 모아 동시 파괴, 내성은 확인만 · 1턴 횟수를 쓰지 않음 — 재정 ②)'),
 'A2': ('이동', 'move', '처리', D('A2') + ' / 이름 붙은 설정: 「드로우」(덱 위에서 패로 — 턴 드로우와 같은 행위, 옛 A4) · 「덱 위 보내기」(덱 위 n장 제외 · 묘지로, '
        '부족분 다른 덱 · 덱아웃 패배 · 1장 추가, 옛 A5). 사건은 카드마다'),
 'A3': NEW39['A3'], 'A6': NEW39['A6'], 'A7': NEW39['A7'], 'A8': NEW39['A8'],
 'A9': ('필드 안 이동', 'move_on_field', '처리', '필드 안에서 자리를 바꾼다 — 컨트롤 이동(다른 쪽 자리, 돌아오는 때 — 옛 A9) · 뒷면 카드 재배치(맞바꾸기 — 옛 A11). '
        '「다른 쪽 자리 허용」은 기본값 「아니오」인 명시 값(다른 쪽이면 컨트롤 이동 규칙 — 빈 자리 · 필드 매수 제한). 필드를 벗어나지 않음(E3 없음) · 카운터 · 표시 형식 · 뒷면 유지'),
 'A12': NEW39['A12'], 'A13': NEW39['A13'], 'A14': NEW39['A14'], 'A15': NEW39['A15'], 'A16': NEW39['A16'],
 'A17': ('상태 · 보정', 'status', '처리', '카드 · 플레이어에 상태나 보정을 건다 — 종류 표(5장): 카드 상태(내성 · 불가 · 공격 횟수 · 취급, 옛 A20) · 플레이어 규칙(금지 · 배율 · 코스트, 옛 A21) · '
        '공격력 · 수비력 증감(옛 A17) · 다른 효과의 값 변경(옛 A26) · 행동 세금(재정 ①). 모드: 처리(기간) / [지속] 적용(조건 동안 · 1턴 횟수). '
        '받는 쪽이 카드인 종류는 전부 내성 검사(재정 ③), 종류별 색인으로 조회'),
 'A18': NEW39['A18'], 'A19': NEW39['A19'], 'A22': NEW39['A22'], 'A23': NEW39['A23'],
 'J1': NEW39['J1'], 'J2': (NEW39['J2'][0], NEW39['J2'][1], NEW39['J2'][2], NEW39['J2'][3] + ' (옛 택1의 갈래 포함)'),
}

# 재정 ①(사용자 답변 2026-10-27 · 10-28): 「서로가 …할 때마다, 그 플레이어는 자신의 덱의 위에서부터 카드를 n장 제외한다」는 사건 뒤 자동 처리(F13 + 시점 블록)가 아니라
# 그 행동에 붙는 코스트 — 상태 · 보정의 「행동 세금」 종류 + 이동(덱 위 보내기)의 코스트 모드 (engine.Game.pay_tax)
TAX_ROWS = {('TAXM-009', '1'), ('TAXM-010', '1'), ('TAXM-011', '1')}

rows_new = []
use = collections.defaultdict(list); modes = collections.defaultdict(set); src_old = collections.defaultdict(set)
frame_old = collections.defaultdict(set)
for r in o['rows']:
    news, frames = [], set()
    for b in r['blocks']:
        if b.startswith('F') or b in VALUE: continue
        if b in FRAME: frames.add(FRAME[b])
        tgt = OVR.get((r['code'], r['key'], b))
        if tgt is None:
            if b == 'P28': tgt = P28_TIMING
            elif b in FRAME or b == 'P31': tgt = []
            else: tgt = [M[b]]
        for t39 in tgt:
            ts, fr = to27(t39, b)
            if fr: frames.add(fr); frame_old[fr].add(b)
            for t in ts:
                news.append(t); src_old[t].add(b)
                if b in M or (r['code'], r['key'], b) in OVR: modes[t].add(MODE_OF(b) if b not in ('P27', 'P28') else 'do')
    news = list(dict.fromkeys(news))
    if (r['code'], r['key']) in TAX_ROWS:
        news = ['A17', 'A2']; frames.discard('F13'); modes['A17'].add('apply'); modes['A2'].add('cost')
    for t in news: use[t].append(f"{r['code']} #{r['key']}")
    rows_new.append({'code': r['code'], 'key': r['key'], 'name': r['name'], 'old': [b for b in r['blocks'] if not b.startswith('F')], 'new': news, 'frames': sorted(frames)})
missing = [k for k in NEW if not use.get(k)]
old_all = [k for k in o['cat'] if not k.startswith('F')]
stats = []
for k, (nm, en, cat, desc) in NEW.items():
    us = use.get(k, [])
    stats.append({'id': k, 'name': nm, 'en': en, 'cat': cat, 'desc': desc, 'effects': len(us), 'cards': len({u.split(' #')[0] for u in us}),
                  'uses': us, 'old': sorted(src_old.get(k, ())), 'modes': sorted(modes.get(k, ()))})
# 옛 블록 → 27개판
old2new = {}
FR_NAME = {'F02': '효과 틀 F02 발동 위치(패)', 'F12': '효과 틀 F12', 'F13': '효과 틀 F13', 'F14': '효과 틀 F14 소환 절차'}
for b in old_all:
    if b in VALUE: old2new[b] = '값 문법'
    elif b in FRAME: old2new[b] = f'효과 틀 {FRAME[b]}'
    elif b == 'P28': old2new[b] = '효과 틀 F13 + E4'
    elif b == 'P31': old2new[b] = 'A14 · E3 · C1 조합'
    elif b == 'C05': old2new[b] = '삭제(쓰이지 않음)'
    else:
        t39s = [M[b]] + sorted({t for (c, k, ob), ts in OVR.items() if ob == b for t in ts} - {M[b]})
        outs = []
        for i, t39 in enumerate(t39s):
            ts, fr = to27(t39, b)
            lab = ' · '.join(ts + ([FR_NAME[fr]] if fr else [])) or '—'
            outs.append(lab if i == 0 else f'일부 {lab}')
        extra = [x for x in dict.fromkeys(outs[1:]) if x != '일부 ' + outs[0]]
        old2new[b] = outs[0] + (f" ({' · '.join(extra)})" if extra else '')
# 39개판 → 27개판
map39 = {}
for k in NEW39:
    if k == 'A10': map39[k] = 'S1 고르기(확인하고 고르기) · A2 이동(나머지를 덱으로) · 효과 틀 F02 발동 위치(패에서 보여주기)'
    elif k == 'A24': map39[k] = '효과 틀 F14 소환 절차(발동 코스트 아님)'
    elif k == 'J3': map39[k] = 'S1 고르기(선택지) + J2 분기'
    else: map39[k] = MERGE.get(k, k)
json.dump({'stats': stats, 'rows': rows_new, 'old2new': old2new, 'oldcat': o['cat'], 'missing': missing, 'map39': map39,
           'new39': {k: v[0] for k, v in NEW39.items()}, 'frame_old': {k: sorted(v) for k, v in frame_old.items()}},
          open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('new blocks', len(NEW), 'unused', missing)
for s in sorted(stats, key=lambda s: -s['effects']): print(f"{s['id']:4} {s['name']:10} {s['effects']:4} {s['cards']:4} {'/'.join(s['modes']):16} {' '.join(s['old'])}")
