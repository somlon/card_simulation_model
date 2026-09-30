"""RF 부분 활용 검토: 탐색 AI의 형세 판정(롤아웃 절단 시 승률 추정)을 수동 공식 대신 RF로 할 수 있는가.
1) 턴 시작 형세 → 그 판 승패 데이터 수집  2) 수동 공식 vs RF 예측 정확도 비교"""
import random, time, math, pickle, sys, itertools, json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import log_loss, roc_auc_score
from engine import Game
from cards import Impl
import policy as P, season as S
SK = sorted(S.load_decks())
def feats(sn, p, skills, first):
    o = 1 - p
    f = [sn['turn'], int(sn['tp'] == p), int(first == p), sn['hp'][p], sn['hp'][o], sn['hp'][p] - sn['hp'][o],
         sn['field'][p], sn['field'][o], sn['mons'][p], sn['mons'][o], sn['hand'][p], sn['hand'][o], sn['grave'][p], sn['grave'][o],
         sn['atk'][p], sn['atk'][o], sn['deck'][p], sn['deck'][o]]
    return f + [int(skills[p] == k) for k in SK] + [int(skills[o] == k) for k in SK]
def formula(sn, p):
    o = 1 - p
    s = (sn['hp'][p] - sn['hp'][o]) / 1000 + 0.6 * (sn['field'][p] - sn['field'][o]) + 0.3 * (sn['hand'][p] - sn['hand'][o]) + (sn['atk'][p] - sn['atk'][o]) / 2000
    return 1 / (1 + math.exp(-s))
if __name__ == '__main__':
    decks = S.load_decks(); rng = random.Random(3); X = []; y = []; fm = []; gid = []; t0 = time.time(); n = 0
    pairs = list(itertools.combinations(SK, 2))
    while time.time() - t0 < float(sys.argv[1]):
        a, b = rng.choice(pairs); g = Game([decks[a], decks[b]], [P.LearnedAI(a, learn=False), P.LearnedAI(b, learn=False)], n % 2, rng, [], Impl)
        w, _ = g.run(); n += 1
        if w is None: continue
        for sn in g.snaps:
            for p in (0, 1):
                X.append(feats(sn, p, [a, b], g.first)); y.append(int(w == p)); fm.append(formula(sn, p)); gid.append(n)
    X = np.array(X, dtype=np.float32); y = np.array(y); fm = np.clip(np.array(fm), 1e-3, 1 - 1e-3); gid = np.array(gid)
    tr = gid <= int(n * 0.8); te = ~tr
    out = {'판수': n, '표본': int(len(y)), '수동 공식': [round(log_loss(y[te], fm[te]), 4), round(roc_auc_score(y[te], fm[te]), 4)]}
    for k in (8, 16, 64):
        rf = RandomForestClassifier(n_estimators=k, min_samples_leaf=30, random_state=0).fit(X[tr], y[tr])
        pr = np.clip(rf.predict_proba(X[te])[:, 1], 1e-3, 1 - 1e-3)
        out[f'RF {k}그루'] = [round(log_loss(y[te], pr), 4), round(roc_auc_score(y[te], pr), 4)]
        if k == 8: pickle.dump({'rf': rf, 'SK': SK}, open('learned/rf_state.pkl', 'wb'))
    json.dump(out, open('learned/rf_state_result.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))
