"""탐색 기반 판단 (결정화 몬테카를로, ISMCTS 경량판).

판단 지점마다 후보별로 R번씩 '가상 대전'을 굴려 승률이 가장 높은 후보를 고른다.
- 가상 대전은 게임 시작부터 지금까지의 모든 판단을 그대로 재현해 같은 상태에 도달한 뒤(재현),
  탐색하는 쪽이 모르는 정보 — 자기 덱 순서, 상대 패와 덱 — 를 무작위로 다시 섞고(결정화),
  후보를 적용한 다음 끝까지 학습 정책으로 진행한다(롤아웃).
- 상대 패를 들여다보지 않으므로 실제 대전과 같은 정보 조건에서 판단한다.
- 학습이 필요 없어 어떤 덱 · 카드에도 같은 방식으로 즉시 적용된다.
"""
import random, time
from engine import Game, GameOver
from cards import Impl
from policy import LearnedAI, POLICY, ReplayDesync

class SearchAI(LearnedAI):
    KEY = ('대응', '우선권', '진행 행동', '정비 행동', '공격', '트리거:', '번식지')

    def __init__(self, skill, rollouts=8, max_cands=4, split_override=None, key_only=False, depth=None):
        super().__init__(skill, split_override, learn=False)
        self.R = rollouts; self.M = max_cands
        self.key_only = key_only      # 주요 판단만 탐색, 나머지는 학습 정책
        self.depth = depth            # 롤아웃을 현재 턴 + depth 턴에서 끊고 형세로 판정 (None = 끝까지)
        self.evaluator = _default_eval()   # 형세 판정: RF 형세 모델(부분 채택, 2026-09-23) — 파일이 없으면 수동 공식
        self.stats = {'decisions': 0, 'searched': 0, 'rollouts': 0, 'desync': 0, 'time': 0.0}

    def choose(self, g, p, decision, opts, scale=40.0, log=True):
        if getattr(g, 'script', None) is not None or len(opts) < 2 or (self.key_only and not decision.startswith(self.KEY)):
            return super().choose(g, p, decision, opts, scale, log)
        self.stats['decisions'] += 1
        if decision.startswith('멀리건') or decision.startswith('서치') and len(opts) == 2 and False:
            pass
        t0 = time.time()
        # 1) 학습 정책 값으로 후보를 추려 상위 M개만 탐색
        me = g.p[p].skill.name; op = g.p[1 - p].skill.name
        base = f'{me} vs {op}|{decision}|'; b = self.bucket(g, p)
        from policy import prior_of
        pri = []
        for i, (lab, h, pay) in enumerate(opts):
            k1 = base + lab; v, _, _ = POLICY.value(k1, k1 + '|' + b, prior_of(h, scale)); pri.append((v, i, lab))
        pri.sort(key=lambda x: -x[0]); cands = pri[:self.M]
        # 2) 후보별 롤아웃
        res = []
        for v, i, lab in cands:
            w = n = 0
            for r in range(self.R):
                out = self.rollout(g, p, i, seed=hash((g.seed, len(g.dlog), i, r)) & 0xffffffff)
                if out is None: continue
                n += 1; w += out
            res.append(((w + 0.5 * 2) / (n + 2), i, lab, w, n))   # 사전 2판(50%)으로 평활
        self.stats['searched'] += 1; self.stats['time'] += time.time() - t0
        res.sort(key=lambda x: (-x[0], [c[1] for c in cands].index(x[1])))
        best = res[0]
        if log:
            cs = ', '.join(f'{lab}={w}/{n}' for _, _, lab, w, n in res)
            g.L(f'판단[{g.pname(p)}] {decision} — 탐색 {self.R}회×{len(cands)}후보: {{{cs}}} → {best[2]}', 'decision')
        return self._rec(g, p, best[1], opts)

    def rollout(self, g, p, idx, seed):
        rng2 = random.Random(seed)
        snap = self.snapshot(g)
        def determinize(h, pl):
            if self.snapshot(h) != snap: raise ReplayDesync()   # 재현 상태가 실제와 다르면 폐기
            me = h.p[pl]; op = h.p[1 - pl]
            rng2.shuffle(me.main); rng2.shuffle(me.upper)
            for kind, deck in (('메인', op.main), ('상급', op.upper)):
                hand_k = [c for c in op.hand if c.deck_kind() == kind]
                pool = hand_k + deck; rng2.shuffle(pool)
                newhand = pool[:len(hand_k)]; rest = pool[len(hand_k):]
                for c in hand_k: op.hand.remove(c)
                for c in newhand: c.zone = 'hand'; op.hand.append(c)
                deck[:] = rest
                for c in rest: c.zone = 'main' if kind == '메인' else 'upper'
            h.rng = rng2
        h = Game(g.decks, [LearnedAI(g.decks[0]['스킬'], learn=False), LearnedAI(g.decks[1]['스킬'], learn=False)],
                 g.first, random.Random(g.seed), [], Impl)
        h.seed = g.seed
        if self.depth is not None: h.turn_cap = (g.turn + self.depth, p)
        h.evaluator = getattr(self, 'evaluator', None)
        h.script = {'seq': list(g.dlog), 'pos': 0, 'force': idx, 'forced': False, 'player': p, 'determinize': determinize}
        self.stats['rollouts'] += 1
        try:
            w, why = h.run()
        except ReplayDesync:
            self.stats['desync'] += 1; return None
        if w == 'eval': return why
        return None if w is None else int(w == p)


def _snap(g):
    return (g.turn, g.phase, tuple(x.hp for x in g.p), tuple(tuple(sorted(c.name for c in x.hand)) for x in g.p),
            tuple(tuple(sorted(c.name for c in g.field_cards(i))) for i in (0, 1)), tuple(len(x.main) + len(x.upper) for x in g.p))
SearchAI.snapshot = staticmethod(_snap)


def new_game(decks, ais, first, seed, log):
    g = Game(decks, ais, first, random.Random(seed), log, Impl)
    g.seed = seed; g.dlog = []
    return g


_EV = {}
def _default_eval():
    import os
    if 'ev' not in _EV:
        _EV['ev'] = rf_evaluator() if os.path.exists('learned/rf_state.pkl') else None
    return _EV['ev']


def rf_evaluator(path='learned/rf_state.pkl'):
    """RF 형세 모델(8그루)을 탐색 절단 판정기로 — rf_eval.py 결과 수동 공식보다 예측이 크게 정확(AUC 0.74 → 0.90)"""
    import pickle, numpy as np
    from rf_eval import feats
    m = pickle.load(open(path, 'rb')); rf = m['rf']
    def ev(g, p):
        sk = [g.p[0].skill.name, g.p[1].skill.name]
        sn = dict(turn=g.turn, tp=g.turn_player, hp=[x.hp for x in g.p], field=[len(g.field_cards(i)) for i in (0, 1)],
                  mons=[len(g.monsters(i)) for i in (0, 1)], hand=[len(x.hand) for x in g.p], grave=[len(x.grave) for x in g.p],
                  atk=[sum(g.atk(mm) for mm in g.monsters(i)) for i in (0, 1)], deck=[len(x.main) + len(x.upper) for x in g.p])
        return float(rf.predict_proba(np.array([feats(sn, p, sk, g.first)], dtype=np.float32))[0, 1])
    return ev
