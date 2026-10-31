"""랜덤 포레스트 비교 실험 2단계: 트리 수 엘보우 곡선 + 예측 성능 비교."""
import pickle, random, time, json, math, sys
import numpy as np, scipy.sparse as sp
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import log_loss, roc_auc_score
rows = pickle.load(open('rf_rows.pkl', 'rb'))
n = len(rows); cut = int(n * 0.8)
rng = random.Random(0)
tr = rng.sample(range(cut), 150000); te = rng.sample(range(cut, n), 80000)
cats = {}
def cid(k):
    if k not in cats: cats[k] = len(cats)
    return cats[k]
for i in tr:
    r = rows[i]; cid('D:' + r[1]); cid('T:' + r[2]); cid('L:' + r[2] + '|' + r[3])
def build(idx):
    num = np.array([rows[i][0] for i in idx], dtype=np.float32)
    ri, ci = [], []
    for j, i in enumerate(idx):
        r = rows[i]
        for k in ('D:' + r[1], 'T:' + r[2], 'L:' + r[2] + '|' + r[3]):
            if k in cats: ri.append(j); ci.append(cats[k])
    cat = sp.csr_matrix((np.ones(len(ri), dtype=np.float32), (ri, ci)), shape=(len(idx), len(cats)))
    return sp.hstack([sp.csr_matrix(num), cat]).tocsr(), np.array([rows[i][-2] for i in idx])
Xtr, ytr = build(tr); Xte, yte = build(te)
print('특징 수', Xtr.shape[1], '학습', Xtr.shape[0], '평가', Xte.shape[0], flush=True)
res = {}
# 표 기반 모델 (현재 사용 중) — 기존 학습표 예측값 그대로
tab = np.clip(np.array([rows[i][4] for i in te]), 1e-3, 1 - 1e-3)
res['표(현행 학습표)'] = (log_loss(yte, tab), roc_auc_score(yte, tab))
# 표 기반 모델을 같은 학습 데이터로 다시 맞춘 것 (공정 비교)
A = 20.0; L1 = {}; L2 = {}
for i in tr:
    r = rows[i]; y = r[-2]
    a = L1.setdefault(r[5], [0, 0]); a[0] += y; a[1] += 1
    b = L2.setdefault(r[6], [0, 0]); b[0] += y; b[1] += 1
base = ytr.mean()
def tabv(r):
    w1, n1 = L1.get(r[5], (0, 0)); m1 = (w1 + A * base) / (n1 + A)
    w2, n2 = L2.get(r[6], (0, 0)); return (w2 + A * m1) / (n2 + A)
tab2 = np.clip(np.array([tabv(rows[i]) for i in te]), 1e-3, 1 - 1e-3)
res['표(같은 데이터로 재학습)'] = (log_loss(yte, tab2), roc_auc_score(yte, tab2))
print({k: (round(v[0], 4), round(v[1], 4)) for k, v in res.items()}, flush=True)
# 엘보우: 트리 수를 늘려 가며 평가 손실 측정 (warm_start)
grid = [1, 2, 4, 8, 16, 32, 64, 128, 192]
rf = RandomForestClassifier(n_estimators=1, warm_start=True, min_samples_leaf=50, max_features='sqrt', n_jobs=1, random_state=0)
curve = []; t0 = time.time()
for k in grid:
    rf.set_params(n_estimators=k); rf.fit(Xtr, ytr)
    pr = np.clip(rf.predict_proba(Xte)[:, 1], 1e-3, 1 - 1e-3)
    curve.append((k, log_loss(yte, pr), roc_auc_score(yte, pr), round(time.time() - t0)))
    print('트리', k, round(curve[-1][1], 5), round(curve[-1][2], 4), f'{curve[-1][3]}s', flush=True)
    if time.time() - t0 > 200: break
# 엘보(knee): 정규화 곡선에서 첫점-끝점 직선과의 거리가 최대인 점 (log 스케일 트리 수)
xs = np.log2([c[0] for c in curve]); ys = np.array([c[1] for c in curve])
xn = (xs - xs.min()) / (xs.max() - xs.min()); yn = (ys - ys.min()) / (ys.max() - ys.min() + 1e-12)
dist = [abs((yn[-1] - yn[0]) * x - (xn[-1] - xn[0]) * y + xn[-1] * yn[0] - yn[-1] * xn[0]) for x, y in zip(xn, yn)]
knee = curve[int(np.argmax(dist))][0]
print('엘보 트리 수', knee, flush=True)
rf_k = RandomForestClassifier(n_estimators=knee, min_samples_leaf=50, max_features='sqrt', random_state=0).fit(Xtr, ytr)
prk = np.clip(rf_k.predict_proba(Xte)[:, 1], 1e-3, 1 - 1e-3)
res[f'랜덤 포레스트 ({knee}그루)'] = (log_loss(yte, prk), roc_auc_score(yte, prk))
res['기준선(전체 평균)'] = (log_loss(yte, np.full(len(yte), base)), 0.5)
pickle.dump({'rf': rf_k, 'cats': cats, 'knee': knee}, open('learned/rf_model.pkl', 'wb'))
json.dump({'curve': curve, 'knee': knee, 'res': {k: [round(a, 5), round(b, 4)] for k, (a, b) in res.items()}},
          open('learned/rf_result.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: [round(a, 4), round(b, 4)] for k, (a, b) in res.items()}, ensure_ascii=False))
