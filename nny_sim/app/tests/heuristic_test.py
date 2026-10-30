"""휴리스틱 AI 시험(화면 없이, 사용자 지시 2026-10-30 「휴리스틱 모델의 AI도 .exe 파일에서 동작할 수 있게」 · 「휴리스틱 AI도 학습으로 발전」):
나 vs 휴리스틱 AI(가짜 사람) · AI vs AI 관전(P2 휴리스틱) · 휴리스틱 AI끼리 녹화 → 끝까지 진행 · 재생 기록 정보(ai · ai2) ·
휴리스틱 AI 자리의 전술 판단은 규칙(학습표 형식 아님), 전략 판단(시작 패 · 멀리건 · 드로우 덱 · 선후공 · 번식지)은 학습표 형식 · 학습 기록에 전략 키만.
python3 heuristic_test.py <sim> <split> <cards> <library> <시험용 사용자 폴더>"""
import sys, os, time, random, shutil
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM, SPLIT, CARDS, LIB, USER = (os.path.abspath(x) for x in sys.argv[1:6]); sys.argv = ['x']
sys.path[:0] = [SIM, os.path.join(os.path.dirname(APP), 'viewer'), APP]
os.chdir(SIM)
import server
shutil.rmtree(USER, ignore_errors=True)
app = server.App({'sim': SIM, 'split': SPLIT, 'cards': CARDS, 'library': LIB, 'user': USER, 'static': APP + '/static',
                  'viewer': os.path.join(os.path.dirname(APP), 'viewer')})
rng = random.Random(7); ok = True
TABLE_STYLE = '%(n'   # 학습표 AI(policy.LearnedAI.choose)의 판단 줄 — 후보마다 「승률%(n 표본 수)」. 휴리스틱 AI 전술은 「후보 {라벨=점수}」
STRATEGY = ('시작 패 배분', '시작 패 재배분', '멀리건:', '드로우 덱', '번식지', '선후공 선택')   # 학습하는 휴리스틱 AI가 학습표로 고르는 판단(session.LearningHeuristicAI.STRATEGY)


def strategic(m):
    d = m.split('] ', 1)[-1]
    return d.startswith(STRATEGY) or '라운드 선후공' in d


def heuristic_ok(lines):
    """휴리스틱 자리: 전술 줄은 학습표 형식이 아니고, 학습표 형식 줄은 모두 전략 판단이며 하나 이상 있다"""
    return bool(lines) and not any(TABLE_STYLE in m for m in lines if not strategic(m)) and any(TABLE_STYLE in m for m in lines if strategic(m))


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
            idx = 0 if pd['kind'] == 'side' else rng.randrange(len(pd['opts']))
            app.route('POST', '/api/match/answer', {}, {'rid': pd['id'], 'idx': idx})
        elif res['status'] not in ('starting', 'running'):
            res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
            if res['replay_id'] or res['status'] == 'error': return res
        if time.time() - t0 > 400: app.live.abort(); return res
        time.sleep(0.004)


def ai_lines(rep, name):
    return [fr['m'] for fr in rep['frames'] if fr['k'] == 'decision' and fr['m'].startswith(f'판단[{name}]')]


for da, db in [('투기장의 규칙', '던전마스터 셔플!'), ('번성충-대발생', '희생제'), ('올인', '호박옥 - 봉인의 계약')]:
    res = play({'mode': 'human', 'deck': 'o:' + da, 'ai_deck': 'o:' + db, 'first': 'me', 'seed': 3, 'learn': True, 'ai_kind': 'heuristic'})
    rep = app.store.replay(res['replay_id']) if res.get('replay_id') else None
    lines = ai_lines(rep, 'AI') if rep else []
    check(f'나 vs 휴리스틱 AI {da} vs {db}', res['status'] == 'done' and rep and rep['meta'].get('ai2') == 'heuristic' and heuristic_ok(lines),
          f'({res["status"]} · ai2 {rep and rep["meta"].get("ai2")} · AI 판단 줄 {len(lines)} · 예: {lines[0][:70] if lines else "-"} · 오류 {(res.get("error") or "")[-200:]})')

res = play({'mode': 'ai', 'deck': 'o:세제', 'ai_deck': 'o:솔루나 아츠', 'first': 'me', 'seed': 5, 'ai_kind': 'heuristic'})
rep = app.store.replay(res['replay_id']) if res.get('replay_id') else None
names = rep['meta']['names'] if rep else ['', '']
check('AI vs AI 관전: P1 학습표 · P2 휴리스틱', rep and rep['meta']['ai'] == 'table' and rep['meta'].get('ai2') == 'heuristic'
      and any(TABLE_STYLE in m for m in ai_lines(rep, names[0]) if not strategic(m)) and heuristic_ok(ai_lines(rep, names[1])),
      f'({res["status"]})')

job = app.route('POST', '/api/record', {}, {'pairs': [['o:데이터버그 패키지 프로그램', 'o:소원의 분수']], 'matches': 2, 'ai_kind': 'heuristic', 'learn': True})
t0 = time.time()
while app.jobs[job['id']].status == 'running' and time.time() - t0 < 600: time.sleep(0.5)
info = app.jobs[job['id']].info()
reps = [app.store.replay(x['replay_id']) for x in info['items'] if x['replay_id']]
check('휴리스틱 AI끼리 녹화', info['status'] == 'done' and len(reps) == 2 and all(r['meta']['ai'] == 'heuristic' and 'ai2' not in r['meta'] for r in reps)
      and all(heuristic_ok(ai_lines(r, n)) for r in reps for n in r['meta']['names']),
      f'({info["status"]} · {[x["status"] for x in info["items"]]})')
import tables as T
recs = [x for x in T.read_log(app.store.ai_log_path) if x['ai_kinds'] == ['heuristic', 'heuristic']]
keys = [k1.split('|')[1] for x in recs for k1, _, _ in x['updates']]
check('휴리스틱 AI끼리 녹화(학습) — 학습 기록에 전략 판단만', len(recs) == 2 and keys and all(k.startswith(STRATEGY) for k in keys),
      f'(갱신 {len(keys)} · 종류 {sorted(set(k.split("(")[0].split(":")[0] for k in keys))})')
lst = [r for r in app.store.replays() if r.get('ai') == 'heuristic' or r.get('ai2') == 'heuristic']
check('재생 목록 정보에 AI 종류', len(lst) >= 6, f'({len(lst)}개)')
# 다른 종류의 AI끼리(자리별 AI 종류): 녹화 P1 휴리스틱 vs P2 학습표 · 관전 P1 휴리스틱 vs P2 휴리스틱 아님
job = app.route('POST', '/api/record', {}, {'pairs': [['o:세제', 'o:올인']], 'matches': 1, 'ai0_kind': 'heuristic', 'ai_kind': 'table'})
t0 = time.time()
while app.jobs[job['id']].status == 'running' and time.time() - t0 < 600: time.sleep(0.5)
info = app.jobs[job['id']].info(); r = app.store.replay(info['items'][0]['replay_id']) if info['items'] and info['items'][0]['replay_id'] else None
nm = r['meta']['names'] if r else ['', '']
check('다른 종류의 AI끼리 녹화(P1 휴리스틱 · P2 학습표)', r and r['meta']['ai'] == 'heuristic' and r['meta'].get('ai2') == 'table'
      and heuristic_ok(ai_lines(r, nm[0])) and any(TABLE_STYLE in m for m in ai_lines(r, nm[1]) if not strategic(m)), f'({info["status"]})')
res = play({'mode': 'ai', 'deck': 'o:번성충-대발생', 'ai_deck': 'o:희생제', 'first': 'me', 'seed': 6, 'ai0_kind': 'heuristic', 'ai_kind': 'table'})
rep = app.store.replay(res['replay_id']) if res.get('replay_id') else None
check('다른 종류의 AI끼리 관전(P1 휴리스틱 · P2 학습표)', rep and rep['meta']['ai'] == 'heuristic' and rep['meta'].get('ai2') == 'table', f'({res["status"]})')
try:
    app.route('POST', '/api/record', {}, {'pairs': [['o:세제', 'o:올인']], 'ai_kind': 'random'}); check('알 수 없는 AI 종류는 거절', False)
except ValueError as ex: check('알 수 없는 AI 종류는 거절', True, f'({ex})')
print('결과:', '통과' if ok else '실패'); sys.exit(0 if ok else 1)
