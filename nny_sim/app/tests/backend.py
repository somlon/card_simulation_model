"""가짜 사람(무작위 선택)으로 사람 vs AI 2매치 — 판단 요청 · 학습 기록 · 재적용 · 재생 저장 확인. 사용자 폴더는 지우고 시작한다.
python3 backend.py <sim> <split> <cards> <library> <시험용 사용자 폴더> [git 주소(file:///…bare.git — 자동 올리기 확인)]
환경 변수 PAIRS=all: 기본 덱 전부를 사람 덱으로 1매치씩(AI 덱은 다음 덱) — 카드 블록 안 하위 선택 요청이 덱마다 나오는지 집계, REPEAT=n: 그 목록을 n번(시드는 매치마다 다름)"""
import sys, os, time, random, json, re
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM, SPLIT, CARDS, LIB, USER = (os.path.abspath(x) for x in sys.argv[1:6]); GIT = sys.argv[6] if len(sys.argv) > 6 else ''; sys.argv = ['x']
sys.path[:0] = [SIM, os.path.join(os.path.dirname(APP), 'viewer'), APP]
os.chdir(SIM)
import server
P = {'sim': SIM, 'split': SPLIT, 'cards': CARDS, 'library': LIB,
     'user': USER, 'static': APP + '/static', 'viewer': os.path.join(os.path.dirname(APP), 'viewer')}
import shutil; shutil.rmtree(P['user'], ignore_errors=True)
app = server.App(P)
if GIT: app.store.save_settings({'auto_push': True, 'git_url': GIT, 'git_base': 'data/main', 'git_branch': 'data/human-games-test'})
b = app.boot(); print('decks', len(b['decks']), 'skills', len(b['skills']), 'learning', b['learning']['matches'])
rng = random.Random(1)
GAMES = [('투기장의 규칙', '던전마스터 셔플!')] * 2
if os.environ.get('PAIRS') == 'all':
    ns = [d['id'][2:] for d in b['decks'] if d['id'].startswith('o:')]; GAMES = [(a, ns[(i + 1) % len(ns)]) for i, a in enumerate(ns)]
GAMES = GAMES * int(os.environ.get('REPEAT', 1))
total = {}
for game, (da, db) in enumerate(GAMES):
    r = app.start_match({'mode': 'human', 'deck': 'o:' + da, 'ai_deck': 'o:' + db, 'first': 'me', 'seed': 11 + game, 'learn': True})
    lid = r['id']; f = s = c = 0; asked = {}; sides = []; t0 = time.time()
    while True:
        res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
        f += len(res['frames']); s += len(res['states']); c += len(res['cards'])
        pd = res['pending']
        if pd:
            q = re.sub(r'「[^」]*」|\(.*\)|\d+(/\d+)?', '', pd['decision'].split(':')[0]).strip(); asked[q] = asked.get(q, 0) + 1; total[q] = total.get(q, 0) + 1
            idx = rng.randrange(len(pd['opts']))
            if '종료' in [o['label'] for o in pd['opts']] and rng.random() < 0.3: idx = [o['label'] for o in pd['opts']].index('종료')
            if pd['kind'] == 'side' and rng.random() < 0.35: idx = 0   # 전략 덱 교체: 「교체 끝」
            if pd['kind'] == 'side': sides.append(pd['opts'][idx]['label'])
            app.route('POST', '/api/match/answer', {}, {'rid': pd['id'], 'idx': idx})
        if res['status'] not in ('starting', 'running') and not pd:
            res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
            if res['replay_id'] or res['status'] in ('error',): break
        if time.time() - t0 > 300: print('timeout'); app.live.abort(); break
        time.sleep(0.005)
    print('game', game, da, 'vs', db, res['status'], 'frames', f, 'winner', res['result'] and res['result']['winner'], 'learned', res['learned'], 'replay', res['replay_id'], 'err', (res['error'] or '')[-300:])
    print('  prompts', sorted(asked.items(), key=lambda x: -x[1])[:12])
    if sides: print('  side', sides[:8], '| log', [x['m'] for x in app.store.replay(res['replay_id'])['frames'] if x['k'] == 'side'] if res['replay_id'] else None)
print('all prompts', sorted(total.items(), key=lambda x: -x[1]))
print('learning', {k: v for k, v in app.learning().items() if k != 'by_matchup'})
print('user replays', [(x['id'], x['title'], x['status']) for x in app.store.replays() if x['id'].startswith('u:')])
# 학습 기록 다시 적용 확인
import tables as T
t = T.matchup_table(P['split'], ['투기장의 규칙', '던전마스터 셔플!'], logs=[app.store.log_path]); print('applied on reload', t.applied)
