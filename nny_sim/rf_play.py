"""랜덤 포레스트 비교 실험 3단계: 실제 대전 강도 비교 (RF 정책 vs 현행 학습표 정책, Bo3 매치)."""
import pickle, random, time, sys, json
import numpy as np, scipy.sparse as sp
import policy as P, match as M, season as S
from rf_data import state_feats
m = pickle.load(open('learned/rf_model.pkl', 'rb')); RF = m['rf']; CATS = m['cats']

class RFAI(P.LearnedAI):
    """판단마다 후보별 (상황 + 후보) 특징으로 RF 승률을 예측해 최댓값을 고른다. RF가 본 적 없는 후보는 학습표 값을 쓴다."""
    def choose(self, g, p, decision, opts, scale=40.0, log=True):
        if len(opts) < 2 or getattr(g, 'script', None) is not None:
            return super().choose(g, p, decision, opts, scale, log)
        me = g.p[p].skill.name; op = g.p[1 - p].skill.name
        dt = decision.split(':')[0] if decision.startswith(('멀리건', '트리거', '서치', '대상')) else decision
        base = state_feats(g, p); ri, ci, known = [], [], []
        for j, (lab, h, pay) in enumerate(opts):
            ks = ['D:' + me, 'T:' + dt, 'L:' + dt + '|' + lab]
            for k in ks:
                if k in CATS: ri.append(j); ci.append(CATS[k])
            known.append(ks[2] in CATS)
        X = sp.hstack([sp.csr_matrix(np.array([base] * len(opts), dtype=np.float32)),
                       sp.csr_matrix((np.ones(len(ri), dtype=np.float32), (ri, ci)), shape=(len(opts), len(CATS)))]).tocsr()
        pr = RF.predict_proba(X)[:, 1]
        b = self.bucket(g, p); vals = []
        for j, (lab, h, pay) in enumerate(opts):
            if known[j]: vals.append(pr[j])
            else:
                k1 = f'{me} vs {op}|{decision}|{lab}'; vals.append(P.POLICY.value(k1, k1 + '|' + b, P.prior_of(h, scale))[0])
        idx = int(np.argmax(vals))
        if log:
            g.L(f'판단[{g.pname(p)}] {decision} (RF): ' + ', '.join(f'{o[0]}={v*100:.1f}%' for o, v in sorted(zip(opts, vals), key=lambda x: -x[1])[:4]) + f' → {opts[idx][0]}', 'decision')
        return self._rec(g, p, idx, opts)

if __name__ == '__main__':
    ds = S.load_decks(); a = ds['번성충-대발생']; b = ds['솔루나 아츠']
    who = int(sys.argv[1]); n = int(sys.argv[2]); rng = random.Random(100 + who); t0 = time.time(); w = m_ = 0
    for i in range(n):
        mk = lambda d: RFAI(d['스킬'], learn=False) if d['스킬'] == [a, b][who]['스킬'] else P.LearnedAI(d['스킬'], learn=False)
        mw, _ = M.play_match(a, b, i % 2, rng, [], mk, learn_side=False)
        if mw is not None: m_ += 1; w += (mw == who)
        if time.time() - t0 > 250: break
    print(json.dumps({'RF 쪽': [a, b][who]['스킬'], '매치': m_, 'RF 쪽 매치 승': w, '승률': round(w / m_ * 100, 1), '초': round(time.time() - t0)}, ensure_ascii=False))
