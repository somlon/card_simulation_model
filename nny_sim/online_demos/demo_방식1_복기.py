"""방식 1 데모 — 「한 판 전수 복기」.

한 판을 두고(학습 정책), 그 판의 판단 지점 몇 곳을 골라 **미래를 모른다는 전제**
(상대 패·덱을 다시 섞는 결정화)로 후보마다 롤아웃을 돌려 "이 상황의 1순위/2순위 수"를
사후에 매긴다 — 실제로 골랐던 수와 비교해 잘한 판단/아쉬운 판단을 가려낸다.
엔진의 재현(script)·결정화 장치(search.py 와 같은 방식)를 그대로 쓴다. 룰 수정 없음.

출력: <out>/방식1_복기_<시각>.md — 마작 타패 순위표 같은 복기 보고서.
"""
import random, time, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from demo_common import attach_sim, load_decks, recording_ai

A = attach_sim()
import deck as D
from engine import Game
from cards import Impl
from policy import LearnedAI, ReplayDesync

decks = load_decks('시제_투기장의_규칙.deck', '시제_던전마스터_셔플!.deck')
SEED = 424242; FIRST = 0
K = A.n or 4          # 복기할 판단 지점 수
R = 6                 # 후보당 롤아웃 수
M = 4                 # 후보 상한

# ── 1) 한 판을 두면서 판단을 기록한다 ──
rec = []
ds = [dict(decks[0], _seat=0), dict(decks[1], _seat=1)]
ais = [recording_ai(ds[i]['스킬'], rec) for i in (0, 1)]
g = Game(ds, ais, FIRST, random.Random(SEED), [], Impl)
g.seed = SEED; g.dlog = []
w, why = g.run()
full_seq = list(g.dlog)
print(f'본판: 승자={ds[w]["이름"] if w is not None else "무"} ({why}, {g.turn}턴) · 판단 {len(rec)}개 기록')


def rollout(prefix_len, player, force_idx, seed):
    """판단 지점(prefix_len)까지 재현 → 결정화 → force_idx 후보 강제 → 끝까지 학습 정책."""
    rng2 = random.Random(seed)

    def determinize(h, pl):
        me = h.p[pl]; op = h.p[1 - pl]
        rng2.shuffle(me.main); rng2.shuffle(me.upper)
        for kind, dk in (('메인', op.main), ('상급', op.upper)):
            hand_k = [c for c in op.hand if c.deck_kind() == kind]
            pool = hand_k + dk; rng2.shuffle(pool)
            newhand = pool[:len(hand_k)]; rest = pool[len(hand_k):]
            for c in hand_k: op.hand.remove(c)
            for c in newhand: c.zone = 'hand'; op.hand.append(c)
            dk[:] = rest
            for c in rest: c.zone = 'main' if kind == '메인' else 'upper'
        h.rng = rng2

    h = Game([dict(decks[0], _seat=0), dict(decks[1], _seat=1)],
             [LearnedAI(decks[0]['스킬'], learn=False), LearnedAI(decks[1]['스킬'], learn=False)],
             FIRST, random.Random(SEED), [], Impl)
    h.seed = SEED; h.dlog = []
    h.script = {'seq': full_seq[:prefix_len], 'pos': 0, 'force': force_idx,
                'forced': False, 'player': player, 'determinize': determinize}
    try:
        hw, _ = h.run()
    except ReplayDesync:
        return None
    return 1 if hw == player else 0


# ── 2) 후보가 둘 이상이던 판단 지점에서 K곳 표본 ──
pts = [r for r in rec if len(r['labels']) >= 2]
random.Random(7).shuffle(pts)
pts = sorted(pts[:K], key=lambda r: r['dlog_len'])
lines = [f'# 방식1 「한 판 전수 복기」 데모 — {time.strftime("%Y-%m-%d %H:%M")}',
         '', f'대진: {ds[0]["이름"]} vs {ds[1]["이름"]} · 시드 {SEED} · 승자 {ds[w]["이름"] if w is not None else "무"} ({why})',
         f'기록된 판단 {len(rec)}개 중 {len(pts)}곳 복기 · 후보당 롤아웃 {R}회 (결정화 — 상대 패·덱 재셔플)', '']
for r in pts:
    cand = sorted(set(list(range(len(r['labels'])))[:M]) | {r['pick']})
    res = []
    for i in cand:
        wn = n = 0
        for k in range(R):
            out = rollout(r['dlog_len'], r['p'], i, seed=hash((SEED, r['dlog_len'], i, k)) & 0xffffffff)
            if out is None: continue
            n += 1; wn += out
        res.append(((wn + 1) / (n + 2), i, wn, n))
    res.sort(key=lambda x: -x[0])
    actual = r['pick']
    rank = next(j for j, x in enumerate(res) if x[1] == actual) + 1
    lines += [f'## {r["turn"]}턴 · {ds[r["p"]]["이름"]} · 「{r["decision"]}」 — 실제 선택: {r["labels"][actual]} (복기 순위 {rank}위/{len(res)})', '']
    for j, (v, i, wn, n) in enumerate(res):
        mark = ' ◀ 실제 선택' if i == actual else ''
        lines.append(f'{j + 1}순위. {r["labels"][i]} — 롤아웃 승률 {wn}/{n}{mark}')
    lines.append('')
out = os.path.join(A.out, f'방식1_복기_{time.strftime("%m%d_%H%M")}.md')
open(out, 'w', encoding='utf-8').write('\n'.join(lines))
print('저장:', out)
