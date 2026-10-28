"""블록 통합안: 옛 블록 124개 → 새 블록. 전수 조사 대응표(out.json의 418행)를 새 블록으로 옮겨 사용 횟수를 다시 센다.
사용: python3 -I consolidate.py out.json new.json"""
import json, sys, collections
o = json.load(open(sys.argv[1], encoding='utf-8'))

# 새 블록: ID → (이름, 영문, 분류, 하는 일)
NEW = {
 'E1': ('소환되었을 때', 'summoned', '발동 시점', '몬스터가 소환되었을 때(이 카드 포함). 누가 · 어느 필드 · 일반/특수 · 어디서 · 필터'),
 'E2': ('발동했을 때', 'activated', '발동 시점', '효과 · 카드가 발동(선언)되었을 때. 누가 · 무엇 · 성질(파괴하는 · 필드에서 벗어나게 하는) · 그 발동의 대상(「…가 대상이 되었을 때」)'),
 'E3': ('카드가 옮겨졌을 때', 'moved', '발동 시점', '카드 이동 사건 하나에 거르기 값: 출발지 · 도착지 · 원인(파괴/릴리스/전투/효과/코스트) · 누구에 의해 · 이 카드. '
        '릴리스는 「원인」으로 식별 — 도착지와 무관(질문 1)'),
 'E4': ('시점', 'timing', '발동 시점', '라운드 시작 · 턴 시작 · 종료 단계가 되었을 때 · 턴 종료 시 (누구의 턴)'),
 'E5': ('값 변화', 'value_changed', '발동 시점', '값이 기준에 닿은 순간 — 값: 이 카드의 카운터 수 · 필터에 맞는 카드들의 카운터 합계 · 플레이어 HP / '
        '기준: 정확히 n이 됨 · n 이상이 됨 · n 이하가 됨 / 방향(증가만 · 감소만) · 원인. 사건 차분 방식 — 그 값의 변화 사건 때 직전 값 = 지금 값 − 변화량(5장)'),
 'E6': ('무효화되었을 때', 'negated', '발동 시점', '자신 카드의 효과가 무효화되었을 때 — 발동 무효 · 카드 무효 모두(엔진의 negated 사건)'),
 'C1': ('존재', 'exists', '조건', '어디에 무엇이 몇 장 있는가(각 「X」마다 · n 이상/없음/정확히, 카운터 수 포함)'),
 'C2': ('그 카드가 …인가', 'is', '조건', '이 카드 · 앞에서 정한 카드(대상 · 결과)가 조건을 만족하는가(위치 · 앞뒷면 · 카운터 · 종류 · 카드군 · 장착 중)'),
 'S1': ('고르기', 'select', '대상 · 고르기', '카드를 고른다. 대상 지정 여부(필수 값) · 고르는 때(발동 시/처리 시) · 고르는 사람(자신/상대/무작위) · '
        '고르는 제약(같은/연속 레벨 · 같은 속성 · 종류별 매수)'),
 'S2': ('선언', 'declare', '대상 · 고르기', '레벨 · 속성 등 값을 선언'),
 'A1': ('파괴', 'destroy', '처리', '카드를 파괴(파괴 내성 · 「파괴되었을 때」 · 「파괴 이외로 벗어나지 않음」과 맞물림)'),
 'A2': ('이동', 'move', '처리', '카드를 옮긴다 — 도착지: 묘지 · 제외(기간) · 덱(위/아래 · 섞기) · 패 · 상대 패 / 출발지: 필드 · 패(=버리기) · 묘지 · 제외 존 · 덱(=서치). '
        '필드에서 옮기면 제거 효과 성질(PDF Q6)이 자동'),
 'A3': ('릴리스', 'release', '처리', '카드를 릴리스(릴리스 불가 성질 · 「릴리스되었을 때」 원인 표시)'),
 'A4': ('드로우', 'draw', '처리', '덱 위에서 뽑는다(턴 드로우와 같은 「드로우」 행위)'),
 'A5': ('덱 위 보내기', 'mill', '처리', '덱 위에서 n장 제외 · 묘지로(부족분 다른 덱 · 덱 아웃)'),
 'A6': ('특수소환', 'special_summon', '처리', '몬스터를 특수소환(소환 조건 · 같은 이름 규칙 · 소환 무효 · [소환] 트리거)'),
 'A7': ('마법 놓기', 'place', '처리', '마법 · 필드 카드를 놓는다 — 세트(이 턴에도 발동 가능 여부) / 앞면 · 발동'),
 'A8': ('장착', 'equip', '처리', '장착 카드로 붙인다'),
 'A9': ('컨트롤 이동', 'control', '처리', '컨트롤을 옮긴다(돌아오는 때)'),
 'A10': ('공개 · 확인', 'reveal', '처리', '보여준다 · 덱 위 n장을 확인한다(지불이 아님). 뒤 처리는 고르기 · 이동으로'),
 'A11': ('재배치', 'rearrange', '처리', '뒷면 카드를 다시 배치'),
 'A12': ('발동 무효', 'negate_activation', '처리', '발동 · 효과를 무효로(묘지에서 발동한 효과 전부 등)'),
 'A13': ('소환 무효', 'negate_summon', '처리', '소환을 무효로'),
 'A14': ('카드 무효', 'negate_card', '처리', '카드의 효과를 무효로(기간 · 장착 중 · 조건 동안)'),
 'A15': ('효과 변경', 'replace_effect', '처리', '발동한 효과를 「…」로 바꿔 처리(한 번 · 지속적으로 「바꿀 수 있다」)'),
 'A16': ('HP 증감', 'hp', '처리', '대미지 · 회복'),
 'A17': ('공격력 · 수비력', 'stat', '처리', '증감 — 한 번 적용(기간) / [지속] 계산식(수량식)'),
 'A18': ('표시 형식', 'position', '처리', '앞면 · 뒷면 · 공격 · 수비로'),
 'A19': ('카운터', 'counter', '처리', '카운터를 놓는다 · 뗀다 · 전부 뗀다'),
 'A20': ('카드 상태', 'status', '처리', '카드에 상태를 준다 — 종류는 「카드 상태 종류」 표(내성 · 파괴 내성 · 릴리스 불가 · 공격 관련 · 취급 · 소환 제한 …). 기간 / 조건 동안 / 어디서나([제약])'),
 'A21': ('플레이어 규칙', 'rule', '처리', '플레이어에게 규칙을 건다 — 종류는 「플레이어 규칙 종류」 표(금지 · 전투 대미지 · 코스트 · 소환 횟수 · 맹세 …). 기간 / 조건 동안'),
 'A22': ('효과 부여', 'grant', '처리', '카드 · 플레이어가 효과를 얻는다(효과는 블록으로 조립) — 기간 / 조건 동안'),
 'A23': ('승리', 'win', '처리', '게임에서 승리'),
 'A24': ('소환 절차', 'summon_procedure', '처리', '「…해야만 특수소환 · …하는 것으로 일반소환할 수 있다」(발동이 아님, 비용은 코스트 모드 블록)'),
 'A25': ('조건 자동 파괴', 'auto_destroy', '처리', '조건을 만족한 몬스터는 파괴된다(상태 점검)'),
 'A26': ('다른 효과 값 변경', 'modify_effect', '처리', '같은 카드의 다른 번호 효과의 값을 바꾼다'),
 'J1': ('차례로', 'seq', '연결', '처리를 차례로 — 「그 후」(앞이 되었을 때만) 여부를 값으로'),
 'J2': ('분기', 'branch', '연결', '조건 · 값에 따라 처리를 나눔(「…경우」 · 종류별 · 주사위 · 「없는 경우 대신」)'),
 'J3': ('택1', 'choose', '연결', '「…하거나」 · 「이하 중 1개」 — 고르는 사람'),
}
VALUE = {'V01', 'V02', 'V03', 'V04', 'V05', 'V06', 'V07', 'V08', 'T04'}   # 블록에서 값 문법으로
FRAME = {'J06': 'F12', 'P27': 'F13', 'P28': 'F13'}                       # 효과 틀 속성으로
M = {
 'W01': 'E1', 'W02': 'E1', 'W03': 'E2', 'W15': 'E2', 'W04': 'E3', 'W05': 'E3', 'W06': 'E3', 'W07': 'E3', 'W08': 'E3', 'W09': 'E3', 'W10': 'E3',
 'W11': 'E4', 'W12': 'E4', 'W13': 'E5', 'W14': 'E6', 'W16': 'E5',
 'C01': 'C1', 'C02': 'C1', 'C03': 'C2', 'C04': 'C2', 'C06': 'C2', 'C07': 'C2',
 'K01': 'A2', 'K02': 'A3', 'K03': 'A5', 'K04': 'A19', 'K05': 'A10', 'K06': 'A18', 'K07': 'J2', 'K08': 'S1', 'K09': 'S1',
 'T01': 'S1', 'T02': 'S1', 'T03': 'S1', 'T05': 'S1', 'T06': 'S2',
 'D01': 'A1', 'D02': 'A2', 'D03': 'A2', 'D04': 'A2', 'D05': 'A2', 'D07': 'A2', 'D17': 'A2', 'D06': 'A4', 'D08': 'A5', 'D09': 'A6', 'D10': 'A3',
 'D11': 'A7', 'D12': 'A7', 'D13': 'A8', 'D14': 'A9', 'D15': 'A10', 'D16': 'A11', 'D18': 'A12', 'D19': 'A13', 'D20': 'A14', 'D21': 'A15',
 'D22': 'A16', 'D23': 'A16', 'D24': 'A17', 'D25': 'A20', 'D26': 'A18', 'D27': 'A18', 'D28': 'A19', 'D29': 'A19', 'D30': 'A20', 'D31': 'A22',
 'D32': 'A20', 'D33': 'A21', 'D34': 'A22', 'D35': 'A23', 'D36': 'A21',
 'P01': 'A20', 'P02': 'A20', 'P03': 'A20', 'P04': 'A20', 'P05': 'A20', 'P06': 'A20', 'P07': 'A20', 'P08': 'A20', 'P09': 'A20', 'P10': 'A20',
 'P11': 'A21', 'P12': 'A20', 'P13': 'A21', 'P14': 'A21', 'P15': 'A21', 'P16': 'A25', 'P17': 'A17', 'P18': 'A20', 'P19': 'A21', 'P20': 'A21',
 'P21': 'A21', 'P22': 'A21', 'P23': 'A21', 'P24': 'A21', 'P25': 'A15', 'P26': 'A26', 'P29': 'A20', 'P30': 'A22',
 'R01': 'A20', 'R02': 'A20', 'R03': 'A24', 'R04': 'A24', 'R05': 'A21',
 'J01': 'J1', 'J02': 'J1', 'J03': 'J2', 'J05': 'J2', 'J04': 'J3',
}
# 같은 옛 블록이 효과에 따라 다른 새 블록이 되는 곳 (문장을 보고 정함)
OVR = {
 ('SLNA-011', '1', 'K01'): ['A9'],                 # 「상대 몬스터 존으로 이동시키고」 — 컨트롤을 넘기는 코스트
 ('SWRM-002', '1', 'K06'): ['A8'],                 # 「장착하고 발동」 — 장착 코스트
 ('UNSL-001', '1', 'D17'): ['A10'],                # 확인한 나머지를 덱으로 섞기 — 공개 · 확인의 값
 ('AMBR-006', '3', 'P07'): ['A21'],                # 「상대는 자신에게 직접공격할 수 있다」 — 플레이어 규칙
 ('AMBR-009', '1', 'C04'): ['C1'], ('CRSD-001', '1', 'C04'): ['C1'], ('AMBR-017', '3', 'C04'): ['C1'],   # 「자신 필드에 …가 존재」
 ('CRSD-007', '2', 'C06'): ['C1'],                 # 「제외 존에 3장 모였을 경우」
 ('COMN-002', '1', 'P31'): ['A14', 'C2'],          # 장착되어 있는 한 그 몬스터의 효과 무효 — 카드 무효(조건 동안) + 장착 중
 ('SWRM-002', '1', 'P31'): ['E3'],                 # 장착된 몬스터가 필드에서 벗어났을 경우 — 이동 사건
 # 「…할 때마다」 · 「…시에」 자동 처리: 시점 블록 + 처리 블록 (효과 틀 F13 자동 처리)
 ('DGMS-010', '2', 'P27'): ['E1', 'A16'], ('TAXM-009', '1', 'P27'): ['E1'], ('TAXM-010', '1', 'P27'): ['E3'],
 ('TAXM-011', '1', 'P27'): ['E2'], ('PKBS-003-1', '2', 'P27'): ['E2'], ('DGMS-015', '1', 'P27'): ['E3', 'A16'],
}
P28_TIMING = ['E4']
MODE_OF = lambda old: 'cost' if old[0] == 'K' else ('apply' if old[0] == 'P' or old in ('R01', 'R02') else 'do')

rows_new = []
use = collections.defaultdict(list); modes = collections.defaultdict(set); src_old = collections.defaultdict(set)
for r in o['rows']:
    news, frames = [], set()
    for b in r['blocks']:
        if b.startswith('F'): continue
        if b in VALUE: continue
        if b in FRAME: frames.add(FRAME[b])
        tgt = OVR.get((r['code'], r['key'], b))
        if tgt is None:
            if b == 'P28': tgt = P28_TIMING
            elif b in FRAME: tgt = []
            elif b == 'P31': tgt = []
            else: tgt = [M[b]]
        for t in tgt:
            news.append(t); src_old[t].add(b)
            if b in M or (r['code'], r['key'], b) in OVR: modes[t].add(MODE_OF(b) if b not in ('P27', 'P28') else 'do')
    news = list(dict.fromkeys(news))
    for t in news: use[t].append(f"{r['code']} #{r['key']}")
    rows_new.append({'code': r['code'], 'key': r['key'], 'name': r['name'], 'old': [b for b in r['blocks'] if not b.startswith('F')], 'new': news, 'frames': sorted(frames)})
missing = [k for k in NEW if not use.get(k)]
old_all = [k for k in o['cat'] if not k.startswith('F')]
unmapped = [k for k in old_all if k not in M and k not in VALUE and k not in FRAME and k not in ('P31', 'C05', 'P28')]
stats = []
for k, (nm, en, cat, desc) in NEW.items():
    us = use.get(k, [])
    stats.append({'id': k, 'name': nm, 'en': en, 'cat': cat, 'desc': desc, 'effects': len(us), 'cards': len({u.split(' #')[0] for u in us}),
                  'uses': us, 'old': sorted(src_old.get(k, ())), 'modes': sorted(modes.get(k, ()))})
old2new = {}
for b in old_all:
    if b in VALUE: old2new[b] = '값 문법'
    elif b in FRAME: old2new[b] = f'효과 틀 {FRAME[b]}'
    elif b == 'P28': old2new[b] = '효과 틀 F13 + E4'
    elif b == 'P31': old2new[b] = 'A14 · E3 · C2 조합'
    elif b == 'C05': old2new[b] = '삭제(쓰이지 않음)'
    else:
        alts = sorted({t for (c, k, ob), ts in OVR.items() if ob == b for t in ts})
        old2new[b] = M[b] + ((' (일부 ' + ' · '.join(a for a in alts if a != M[b]) + ')') if any(a != M[b] for a in alts) else '')
json.dump({'stats': stats, 'rows': rows_new, 'old2new': old2new, 'oldcat': o['cat'], 'missing': missing, 'unmapped': unmapped},
          open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('new blocks', len(NEW), 'unused', missing, 'unmapped old', unmapped)
for s in sorted(stats, key=lambda s: -s['effects']): print(f"{s['id']:4} {s['name']:12} {s['effects']:4} {s['cards']:4} {'/'.join(s['modes']):16} {' '.join(s['old'])}")

