"""방식 3 데모 — 「AI 자기대전 가치 지도」.

AI vs AI 를 여러 판 돌려 행동(소환·발동·공격)마다 **리턴(그 행동을 쓴 판의 승률 변화)**과
사용 빈도를 집계하고, 자주 이어지는 행동 사슬(콤보 루트)을 뽑아 **마인드맵(트리)** 형태로
저장한다 — "이걸 내면 리턴 +x" 식 리스크-리턴 수치의 시연판. 본구현은 HP 스윙·자원
소모까지 리스크 축에 넣는다. 룰 엔진 수정 없음(판단 기록만 관찰).

출력: <out>/방식3_가치지도_<시각>.md (+ .json)
"""
import collections, json, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from demo_common import attach_sim, load_decks, recording_ai

A = attach_sim()
from engine import Game
from cards import Impl

PAIRS = [('시제_투기장의_규칙.deck', '시제_던전마스터_셔플!.deck'),
         ('시제_번성충_대발생.deck', '시제_솔루나_아츠.deck'),
         ('시제_올인.deck', '시제_세리_세제.deck')]
N = A.n or 8   # 대진당 판수

ACT = ('소환:', '발동:', '세트:', '공격', '직접')
use = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))   # 덱 → 라벨 → [쓴 판 수, 그중 승리]
base = collections.defaultdict(lambda: [0, 0])                                   # 덱 → [판, 승]
routes = collections.defaultdict(collections.Counter)                            # 덱 → (A→B) 횟수

for da_n, db_n in PAIRS:
    a, b = load_decks(da_n, db_n)
    for k in range(N):
        rec = []
        ds = [dict(a, _seat=0), dict(b, _seat=1)]
        ais = [recording_ai(ds[i]['스킬'], rec) for i in (0, 1)]
        g = Game(ds, ais, k % 2, random.Random(1000 + k), [], Impl)
        g.seed = 1000 + k; g.dlog = []
        try:
            w, _ = g.run()
        except Exception:
            continue
        for seat in (0, 1):
            name = ds[seat]['스킬']
            base[name][0] += 1; base[name][1] += int(w == seat)
            picks = [r['labels'][r['pick']] for r in rec if r['p'] == seat]
            acts = [p for p in picks if p.startswith(ACT) or '→' in p]
            for lab in set(acts):
                use[name][lab][0] += 1; use[name][lab][1] += int(w == seat)
            for x, y in zip(acts, acts[1:]):
                if x != y: routes[name][(x, y)] += 1

stamp = time.strftime('%m%d_%H%M')
lines = [f'# 방식3 「AI 자기대전 가치 지도」 데모 — {time.strftime("%Y-%m-%d %H:%M")}', '',
         f'대진 {len(PAIRS)}쌍 × {N}판 자기대전. 리턴 = (그 행동을 쓴 판 승률 − 덱 평균 승률), 단위 %p.',
         '본구현은 HP 스윙·자원 소모를 리스크 축으로 추가한다.', '']
tree = {}
for name, (gn, gw) in sorted(base.items()):
    avg = gw / max(gn, 1)
    lines.append(f'## {name} — {gn}판 평균 승률 {100 * avg:.0f}%')
    node = tree[name] = {'판': gn, '평균승률': round(100 * avg, 1), '행동': {}, '루트': []}
    rows = sorted(use[name].items(), key=lambda x: -x[1][0])[:10]
    for lab, (n, wn) in rows:
        d = 100 * (wn / n - avg)
        node['행동'][lab] = {'사용판': n, '리턴': round(d, 1)}
        lines.append(f'- {lab} — 사용 {n}판 · 리턴 {d:+.0f}%p')
    lines.append('  - 자주 이어지는 루트(콤보 후보):')
    for (x, y), c in routes[name].most_common(5):
        node['루트'].append([x, y, c])
        lines.append(f'    - {x} → {y} ({c}회)')
    lines.append('')
md = os.path.join(A.out, f'방식3_가치지도_{stamp}.md')
open(md, 'w', encoding='utf-8').write('\n'.join(lines))
json.dump(tree, open(os.path.join(A.out, f'방식3_가치지도_{stamp}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('저장:', md)
