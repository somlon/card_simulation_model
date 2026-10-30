"""학습 데이터 시험(화면 없이, 사용자 지시 2026-10-30 ③ ⑤ ⑥):
AI끼리 관전 · 녹화가 학습 기록(ai_games.jsonl) · 신경망 표본에 출처 'ai' 로 잡히는지, 사람 대전은 출처 'human',
학습 데이터 정리(제외)가 학습표 다시 적용 · 신경망 표본 불러오기 · 내보내기 · 신경망 나누기 · GitHub 올리기(로컬 bare 저장소)에서 빠지는지,
가중치(사람 대전 HUMAN_WEIGHT : AI끼리 AI_WEIGHT)가 학습표 · 신경망 학습 손실에 반영되는지.
python3 learning_data_test.py <sim> <split> <cards> <library> <시험용 사용자 폴더>"""
import sys, os, time, random, shutil, json, subprocess, zipfile
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM, SPLIT, CARDS, LIB, USER = (os.path.abspath(x) for x in sys.argv[1:6]); sys.argv = ['x']
sys.path[:0] = [SIM, os.path.join(os.path.dirname(APP), 'viewer'), APP]
os.chdir(SIM)
import numpy as np
import server, learndata as LD, nn_samples as NS, nn_train as NT, tables as T
shutil.rmtree(USER, ignore_errors=True)
app = server.App({'sim': SIM, 'split': SPLIT, 'cards': CARDS, 'library': LIB, 'user': USER, 'static': APP + '/static',
                  'viewer': os.path.join(os.path.dirname(APP), 'viewer')})
st = app.store; rng = random.Random(11); ok = True


def check(name, cond, extra=''):
    global ok
    ok = ok and bool(cond); print(('통과 ' if cond else '실패 ') + name, extra)


def play(body):
    r = app.start_match(body); lid = r['id']; f = s = c = 0; t0 = time.time()
    while True:
        res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
        f += len(res['frames']); s += len(res['states']); c += len(res['cards'])
        pd = res['pending']
        if pd:
            app.route('POST', '/api/match/answer', {}, {'rid': pd['id'], 'idx': 0 if pd['kind'] == 'side' else rng.randrange(len(pd['opts']))})
        elif res['status'] not in ('starting', 'running'):
            res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
            if res['replay_id'] or res['status'] == 'error': return res
        if time.time() - t0 > 400: app.live.abort(); return res
        time.sleep(0.004)


NN = app.nn.ready(); print('신경망 기능', NN, app.nn.np_msg)

# ① AI끼리 관전(학습 켬, 학습표 vs 신경망) → ai_games.jsonl · 신경망 표본(출처 ai)
res = play({'mode': 'ai', 'deck': 'o:세제', 'ai_deck': 'o:솔루나 아츠', 'first': 'me', 'seed': 5, 'learn': True,
            'ai0_kind': 'table', 'ai_kind': 'nn' if NN else 'table'})
ai_recs = T.read_log(st.ai_log_path)
check('AI끼리 관전 → ai_games.jsonl', res['status'] == 'done' and len(ai_recs) == 1 and ai_recs[0]['source'] == 'ai' and ai_recs[0]['updates']
      and ai_recs[0]['ai_kinds'][0] == 'table' and not os.path.exists(st.log_path), f'(학습 {res["learned"]} · 표본 {res["nn_saved"]})')
idx = NS.read_index(USER)
if NN:
    check('AI끼리 관전 → 신경망 표본(같은 매치 키)', res['nn_saved'] > 0 and len(idx) == 1
          and list(idx.values())[0]['source'] == 'ai' and list(idx.values())[0]['match'] == ai_recs[0]['match'])

# ② AI끼리 녹화(학습 데이터로 남기기) — 휴리스틱 vs 학습표 / 남기지 않기
job = app.route('POST', '/api/record', {}, {'pairs': [['o:호박옥 - 봉인의 계약', 'o:소원의 분수']], 'matches': 1, 'ai0_kind': 'heuristic', 'ai_kind': 'table', 'learn': True})
t0 = time.time()
while app.jobs[job['id']].status == 'running' and time.time() - t0 < 600: time.sleep(0.5)
job2 = app.route('POST', '/api/record', {}, {'pairs': [['o:세제', 'o:희생제']], 'matches': 1})
while app.jobs[job2['id']].status == 'running' and time.time() - t0 < 900: time.sleep(0.5)
ai_recs = T.read_log(st.ai_log_path)
check('녹화(학습 데이터로 남기기) → ai_games.jsonl, 남기지 않은 녹화는 없음',
      len(ai_recs) == 2 and ai_recs[1]['ai_kinds'] == ['heuristic', 'table'] and app.jobs[job['id']].done[0]['learned'] > 0
      and app.jobs[job2['id']].done[0]['learned'] == 0, f'({[r["ai_kinds"] for r in ai_recs]})')

# ③ 나 vs AI(가짜 사람) → human_games.jsonl(출처 human)
res = play({'mode': 'human', 'deck': 'o:투기장의 규칙', 'ai_deck': 'o:던전마스터 셔플!', 'first': 'me', 'seed': 3, 'learn': True})
h = T.read_log(st.log_path)
check('나 vs AI → human_games.jsonl', res['status'] == 'done' and len(h) == 1 and h[0]['source'] == 'human' and h[0]['human_seat'] == 0
      and h[0]['ai_kinds'] == ['human', 'table'])

# ④ 학습 데이터 정리 목록 · 통계
items = app.route('GET', '/api/learning/items', {}, {})
L = app.learning()
check('정리 목록: 매치 3개 · 출처 · 가중치', len(items) == 3 and sorted(i['source'] for i in items) == ['ai', 'ai', 'human']
      and all(i['weight'] == LD.weight_of(i['source']) for i in items) and L['by_source']['ai']['matches'] == 2 and L['by_source']['human']['matches'] == 1,
      f'({[(i["label"], i["updates"], i["samples"]) for i in items]})')

# ⑤ 가중치: 학습표 다시 적용 — 사람 대전 기록 HUMAN_WEIGHT, AI끼리 AI_WEIGHT
def l2_total(t): return sum(v[1] for v in t.L2.values())
for src, path, rec in (('human', st.log_path, h[0]), ('ai', st.ai_log_path, ai_recs[0])):
    decks = set(rec['decks'])
    base = T.matchup_table(SPLIT, decks); one = os.path.join(USER, f'only_{src}.jsonl'); st.write_records(one, [rec])
    t = T.matchup_table(SPLIT, decks, logs=[one])
    n = sum(1 for k1, _, _ in rec['updates'] if (T.key_owner(k1) or [None])[0] in decks)
    check(f'학습표 가중치 {src} = {LD.weight_of(src)}', n and abs((l2_total(t) - l2_total(base)) - LD.weight_of(src) * n) < 1e-6,
          f'(갱신 {n} · 늘어난 표본 {l2_total(t) - l2_total(base)})')

# ⑥ 제외: 사람 대전 1개 · AI끼리 관전 1개를 뺀다
keys = [h[0]['match'], ai_recs[0]['match']]
app.route('POST', '/api/learning/exclude', {}, {'keys': keys, 'excluded': True})
recs = st.learning_records()
check('제외 → learning_records', [r['match'] for r in recs] == [ai_recs[1]['match']])
t = T.matchup_table(SPLIT, set(h[0]['decks']), logs=st.log_paths, exclude=st.excluded())
check('제외 → 학습표 다시 적용 안 함', t.applied == sum(1 for k1, _, _ in ai_recs[1]['updates'] if (T.key_owner(k1) or [None])[0] in set(h[0]['decks'])))
out = st.export_learning(); ex_lines = [json.loads(x) for x in open(out, encoding='utf-8')]
check('제외 → 내보내기', [r['match'] for r in ex_lines] == [ai_recs[1]['match']] and ex_lines[0]['source'] == 'ai')
if NN:
    P, matches, info = NS.load_all(USER)
    idx = NS.read_index(USER)
    left = [k for k, m in idx.items() if m.get('match') not in keys]
    check('제외 → 신경망 표본 불러오기 · 통계', info['files'] == len(left) and info['excluded'] == len(idx) - len(left)
          and NS.stats(USER)['matches'] == len(left), f'({info})')
    z = app.nn.export(os.path.join(USER, 'export'), 'test')
    with zipfile.ZipFile(z) as zz:
        npz = [n for n in zz.namelist() if n.endswith('.npz')]; zi = json.loads(zz.read('samples/index.json'))
    check('제외 → 신경망 내보내기', sorted(n.split('/')[-1] for n in npz) == sorted(left) == sorted(zi))
    # 가중치: 표본 sw — 사람 대전 3 · AI끼리 1
    app.route('POST', '/api/learning/exclude', {}, {'keys': keys, 'excluded': False})
    P, matches, info = NS.load_all(USER); idx = NS.read_index(USER)
    want = np.concatenate([np.full(m['samples'], LD.weight_of(m['source']), np.float32) for n, m in sorted(idx.items())])
    check('신경망 표본 가중치 sw', P is not None and np.allclose(np.sort(P['sw']), np.sort(want)) and set(np.unique(P['sw'])) <= {LD.HUMAN_WEIGHT, LD.AI_WEIGHT},
          f'({info["by_source"]})')
    # 손실: 가중 평균 — 표본 하나의 가중치를 키우면 그 표본 손실 쪽으로 기운다
    from drl import model as MD
    arrays, _ = MD.load_arrays(app.nn.base); w = {k: np.asarray(v, np.float32) for k, v in arrays.items()}
    b = NT.batch(P, np.arange(min(64, len(P['idx'])))); lg = NT.forward(w, b); bp = NT.seg_softmax(lg, b)[0]
    per = []
    for i in range(b['n']):
        bi = NT.batch(P, [i]); per.append(NT.loss_grad(NT.forward(w, bi), bi, NT.seg_softmax(NT.forward(w, bi), bi)[0])[0])
    per = np.array(per); sw = b['sw'].astype(np.float64)
    check('신경망 손실 = 표본 가중 평균', abs(NT.loss_grad(lg, b, bp)[0] - (per * sw).sum() / sw.sum()) < 1e-4)
    app.route('POST', '/api/learning/exclude', {}, {'keys': keys, 'excluded': True})

# ⑦ GitHub 올리기(로컬 bare 저장소) — 제외한 매치는 올라가지 않는다
bare = os.path.join(USER, 'bare.git'); seed_repo = os.path.join(USER, 'seed')
g = lambda *a, cwd=None: subprocess.run(['git', *a], cwd=cwd, check=True, capture_output=True)
g('init', '-q', '--bare', bare); g('init', '-q', seed_repo); open(os.path.join(seed_repo, 'README'), 'w').write('x')
g('add', '.', cwd=seed_repo); g('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init', cwd=seed_repo)
g('push', '-q', bare, 'HEAD:data/main', cwd=seed_repo)
st.save_settings({'git_url': 'file://' + bare, 'git_base': 'data/main', 'git_branch': ''})
r = st.git_push()
pushed = subprocess.run(['git', '--git-dir', bare, 'show', f'{r.get("branch")}:{server.SS.GIT_LEARN_DIR}/{st.host()}.jsonl'],
                        capture_output=True, text=True).stdout if r['ok'] else ''
pl = [json.loads(x) for x in pushed.splitlines() if x.strip()]
check('GitHub 올리기 — 제외 반영 · 줄마다 출처', r['ok'] and [p['match'] for p in pl] == [ai_recs[1]['match']] and pl[0]['source'] == 'ai', r['msg'])

# ⑧ 다시 넣기
app.route('POST', '/api/learning/exclude', {}, {'keys': keys, 'excluded': False})
check('다시 넣기', len(st.learning_records()) == 3 and not any(i['excluded'] for i in st.learning_items()))

print('전체', '통과' if ok else '실패'); sys.exit(0 if ok else 1)
