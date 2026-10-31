"""랜덤 포레스트 비교 실험 1단계: 판단 데이터 수집.
학습형 정책(탐색 20%)으로 매치를 돌리며, 각 판단에서 고른 후보 1건을 (상황 특징 · 판단 종류 · 후보 · 표 기반 예측 승률 → 그 판의 승패)로 기록."""
import random, sys, time, json, pickle
import deck as D, policy as P, match as M

FEAT_NUM = ['turn', 'my_turn', 'first', 'hp_me', 'hp_op', 'hp_diff', 'f_me', 'f_op', 'm_me', 'm_op', 'h_me', 'h_op', 'dk_me', 'dk_op', 'gy_me', 'gy_op']

def state_feats(g, p):
    o = 1 - p; a = g.p[p]; b = g.p[o]
    return [g.turn, int(g.turn_player == p), int(g.first == p), a.hp, b.hp, a.hp - b.hp, len(g.field_cards(p)), len(g.field_cards(o)),
            len(g.monsters(p)), len(g.monsters(o)), len(a.hand), len(b.hand), len(a.main) + len(a.upper), len(b.main) + len(b.upper),
            len(a.grave), len(b.grave)]

class RecAI(P.LearnedAI):
    rows = None
    def choose(self, g, p, decision, opts, scale=40.0, log=True):
        pay = super().choose(g, p, decision, opts, scale, log=False)
        if len(opts) >= 2 and getattr(g, 'script', None) is None:
            idx = next(i for i, o in enumerate(opts) if o[2] is pay)
            lab = opts[idx][0]; me = g.p[p].skill.name; op = g.p[1 - p].skill.name
            k1 = f'{me} vs {op}|{decision}|{lab}'; k2 = k1 + '|' + self.bucket(g, p)
            v = P.POLICY.value(k1, k2, P.prior_of(opts[idx][1], scale))[0]
            self.buf.append([state_feats(g, p), me, decision.split(':')[0] if decision.startswith(('멀리건', '트리거', '서치', '대상')) else decision, lab, v, k1, k2])
        return pay
    def end_game(self, g, p, winner):
        super().end_game(g, p, winner)
        if winner is not None:
            for r in self.buf: RecAI.rows.append(r + [int(winner == p), g.seed if hasattr(g, 'seed') else 0])
        self.buf = []

if __name__ == '__main__':
    a = D.load('decks/시제_번성충_대발생.deck')[0]; b = D.load('decks/시제_솔루나_아츠.deck')[0]
    import season as S
    ds = S.load_decks(); a = ds['번성충-대발생']; b = ds['솔루나 아츠']
    budget = float(sys.argv[1]); RecAI.rows = []; rng = random.Random(7); t0 = time.time(); n = 0
    def mk(d):
        x = RecAI(d['스킬'], learn=False, eps=0.2); x.buf = []; return x
    while time.time() - t0 < budget:
        M.play_match(a, b, n % 2, rng, [], mk, learn_side=False); n += 1
    pickle.dump(RecAI.rows, open('rf_rows.pkl', 'wb'))
    print(n, '매치', len(RecAI.rows), '판단 행')
