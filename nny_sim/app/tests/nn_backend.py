"""신경망 학습 흐름 시험(화면 없이): 가짜 사람(무작위 선택)으로 나 vs AI 대전 → 신경망 표본 저장 → 「신경망 학습」 작업 →
내 모델로 신경망 AI 대전 → 기본 모델로 되돌리기. 사용자 폴더는 지우고 시작한다.
python3 nn_backend.py <sim> <split> <cards> <library> <시험용 사용자 폴더> <기본 모델.npz>   (환경 변수 GAMES=n: 표본용 대전 수, 기본 2)"""
import sys, os, time, random, re
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM, SPLIT, CARDS, LIB, USER, BASE = (os.path.abspath(x) for x in sys.argv[1:7]); sys.argv = ['x']
sys.path[:0] = [SIM, os.path.join(os.path.dirname(APP), 'viewer'), APP]
os.chdir(SIM)
import server
P = {'sim': SIM, 'split': SPLIT, 'cards': CARDS, 'library': LIB, 'user': USER, 'static': APP + '/static',
     'viewer': os.path.join(os.path.dirname(APP), 'viewer'), 'nn_base': BASE}
import shutil; shutil.rmtree(USER, ignore_errors=True)
app = server.App(P)
rng = random.Random(1)
print('status', {k: v for k, v in app.nn.status().items() if k in ('available', 'using', 'samples')})


def play(da, db, seed, ai_kind):
    r = app.start_match({'mode': 'human', 'deck': 'o:' + da, 'ai_deck': 'o:' + db, 'first': 'me', 'seed': seed, 'learn': True, 'ai_kind': ai_kind})
    lid = r['id']; f = s = c = 0; t0 = time.time(); asked = 0
    while True:
        res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
        f += len(res['frames']); s += len(res['states']); c += len(res['cards'])
        pd = res['pending']
        if pd:
            idx = rng.randrange(len(pd['opts'])); asked += 1
            if '종료' in [o['label'] for o in pd['opts']] and rng.random() < 0.3: idx = [o['label'] for o in pd['opts']].index('종료')
            if pd['kind'] == 'side' and rng.random() < 0.5: idx = 0
            app.route('POST', '/api/match/answer', {}, {'rid': pd['id'], 'idx': idx})
        if res['status'] not in ('starting', 'running') and not pd:
            res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
            if res['replay_id'] or res['status'] in ('error',): break
        if time.time() - t0 > 400: print('timeout'); app.live.abort(); break
        time.sleep(0.005)
    nn_lines = sum(1 for fr in app.store.replay(res['replay_id'])['frames'] if fr['k'] == 'decision' and '(DRL)' in fr['m']) if res['replay_id'] else 0
    meta = res['result'] or {}
    print(f'  {ai_kind:5s} {da} vs {db}: {res["status"]} 승자 {meta.get("winner")} 묻기 {asked} 표본 {res["nn_saved"]} 학습표 갱신 {res["learned"]} '
          f'신경망 판단 줄 {nn_lines} ai2 {meta.get("ai2")} 오류 {(res["error"] or "")[-300:]}')
    return res


n = int(os.environ.get('GAMES', 2))
pairs = [('투기장의 규칙', '던전마스터 셔플!'), ('세제', '솔루나 아츠'), ('번성충-대발생', '희생제'), ('호박옥 - 몽식의 계약', '올인')]
for k in range(n):
    play(*pairs[k % len(pairs)], 21 + k, 'nn' if k % 2 == 0 else 'table')
st = app.nn.status(); print('samples', st['samples']['matches'], st['samples']['samples'], st['samples']['by_matchup'])
app.route('POST', '/api/nn/train', {}, {'epochs': 2}); t0 = time.time()
while app.nn.busy():
    time.sleep(1)
j = app.nn.status()['job']; print('train', j['status'], j['msg'], 'sec', round(time.time() - t0, 1), (j.get('error') or '')[-500:])
if j.get('log'):
    L = j['log']; print('  samples', L['samples'], 'val', L['val_samples'], 'before', L['before'], '\n  after', L['after'])
st = app.nn.status(); print('using', st['using'], 'local', st['local'] and {k: st['local'][k] for k in ('stage', 'created', 'samples', 'matches')})
play('투기장의 규칙', '던전마스터 셔플!', 99, 'nn')
st = app.route('POST', '/api/nn/reset', {}, {}); print('reset → using', st['using'], 'backups', os.listdir(os.path.join(USER, 'learning', 'nn', 'backups')))
