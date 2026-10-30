"""같은 타이밍 효과의 체인 순서 시험(화면 없이, 사용자 지시 2026-10-30): 나 vs AI(가짜 사람 — 무작위 답) · AI끼리 관전으로
① 같은 타이밍에 발동할 효과가 2개 이상이면 사람에게 「체인 순서(같은 타이밍)」를 묻고(체인 번호 · 있는 곳 · 효과 종류 설명), 고른 순서대로 체인에 올라가는지
② AI(학습표 · 휴리스틱 · 신경망)도 같은 판단으로 순서를 고르고, 학습을 켜면 사람 · AI의 순서가 학습 기록에 남는지.
python3 trigger_order_test.py <sim> <split> <cards> <library> <시험용 사용자 폴더>"""
import sys, os, time, random, shutil, re
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM, SPLIT, CARDS, LIB, USER = (os.path.abspath(x) for x in sys.argv[1:6]); sys.argv = ['x']
sys.path[:0] = [SIM, os.path.join(os.path.dirname(APP), 'viewer'), APP]
os.chdir(SIM)
import server, tables as T, policy as P
shutil.rmtree(USER, ignore_errors=True)
app = server.App({'sim': SIM, 'split': SPLIT, 'cards': CARDS, 'library': LIB, 'user': USER, 'static': APP + '/static',
                  'viewer': os.path.join(os.path.dirname(APP), 'viewer')})
rng = random.Random(5); ok = True; DEC = P.LearnedAI.ORDER_DECISION; asked = []


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
            if pd.get('decision') == DEC: asked.append(pd)
            app.route('POST', '/api/match/answer', {}, {'rid': pd['id'], 'idx': idx})
        elif res['status'] not in ('starting', 'running'):
            res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
            if res['replay_id'] or res['status'] == 'error': return res
        if time.time() - t0 > 400: app.live.abort(); return res
        time.sleep(0.003)


def in_order(g):
    """고른 순서를 지켜 체인에 올라갔는가: 이어서 선언된 그 묶음 후보의 효과들이 「고른 순서 + 남은 하나」와 같은 차례다.
    고른 효과가 선언 때 조건을 잃으면(같은 이름 1턴 1번 등 — Game.legal · keep_trigger) 건너뛸 수 있다"""
    picks, acts, cands = g; seq = acts[:1]
    for a in acts[1:]:
        if a[1] != seq[-1][1] + 1: break
        seq.append(a)
    seq = [lab for lab, _ in seq if not cands or lab in cands]
    j = 0
    for k, lab in enumerate(seq):
        while j < len(picks) and picks[j] != lab: j += 1
        if j == len(picks): return k == len(seq) - 1   # 고르지 않은 남은 하나는 마지막에만
        j += 1
    return bool(seq)


def groups(rep, who):
    """기록에서 who 의 체인 순서 판단 묶음 → [(고른 라벨들, 그 뒤 who 의 효과 발동 (라벨, 체인 번호)들, 후보 라벨들(학습표 AI 줄 — 사람은 빈 집합))]"""
    ms = [fr['m'] for fr in rep['frames']]; out = []; i = 0
    pat = re.compile(rf'^판단\[{re.escape(who)}\] {re.escape(DEC)}: (.*?)→ (.+?) \(')
    act = re.compile(rf'^{re.escape(who)} 「(.+)」 (\d+)번 효과 발동.* — 체인 (\d+)$')
    while i < len(ms):
        picks = []; cands = set()
        while i < len(ms) and pat.match(ms[i]):
            m = pat.match(ms[i])
            if not picks: cands = set(re.findall(r'(?:\{|, )([^{},=]+#\d+)=', m.group(1)))
            picks.append(m.group(2)); i += 1
        if picks:
            acts = [(f'{m.group(1)}#{m.group(2)}', int(m.group(3))) for m in (act.match(x) for x in ms[i:i + 40]) if m]
            out.append((picks, acts, cands))
        i += 1
    return out


human_groups = []; n = 0
for da, db in [('데이터버그 패키지 프로그램', '던전마스터 셔플!'), ('번성충-대발생', '데이터버그 패키지 프로그램'), ('던전마스터 셔플!', '희생제'),
               ('데이터버그 패키지 프로그램', '소원의 분수')]:
    res = play({'mode': 'human', 'deck': 'o:' + da, 'ai_deck': 'o:' + db, 'first': 'me', 'seed': 11 + n, 'learn': True}); n += 1
    rep = app.store.replay(res['replay_id']) if res.get('replay_id') else None
    if res['status'] != 'done' or not rep: check(f'대전 끝까지 {da} vs {db}', False, (res.get('error') or '')[-300:]); continue
    human_groups += groups(rep, '나')
    if len(asked) >= 4: break

check('사람에게 체인 순서를 묻는다(2개 이상일 때)', asked and all(len(a['opts']) >= 2 for a in asked)
      and all(o.get('sub', '').startswith('체인 ') and ('[' in o['sub']) for a in asked for o in a['opts']),
      f'({len(asked)}번 · 예: {[(o["label"], o.get("sub")) for o in asked[0]["opts"]] if asked else "-"})')
good = [g for g in human_groups if in_order(g)]
check('고른 순서대로 체인에 올라간다(먼저 고른 것이 낮은 체인 번호)', human_groups and len(good) == len(human_groups),
      f'({len(good)}/{len(human_groups)} · 예: {human_groups[0] if human_groups else "-"})')
recs = T.read_log(app.store.log_path)
keys = [k1 for r in recs for k1, _, _ in r['updates'] if f'|{DEC}|' in k1]
check('사람 · AI의 체인 순서가 학습 기록에(같은 판단 키)', keys, f'({len(keys)}개 · 예: {keys[:2]})')

# AI끼리: 학습표 · 휴리스틱 · 신경망 자리가 모두 순서를 고르고 학습 기록에 남는다
kinds = ['table', 'heuristic'] + (['nn'] if app.nn.ready() else [])
for k in kinds:
    res = play({'mode': 'ai', 'deck': 'o:데이터버그 패키지 프로그램', 'ai_deck': 'o:던전마스터 셔플!', 'first': 'me', 'seed': 21, 'learn': True, 'ai0_kind': k, 'ai_kind': k})
    rep = app.store.replay(res['replay_id']) if res.get('replay_id') else None
    nm = rep['meta']['names'] if rep else ['', '']
    lines = [fr['m'] for fr in rep['frames'] if DEC in fr['m']] if rep else []
    gs = groups(rep, nm[0]) + groups(rep, nm[1]) if rep else []
    rec = [r for r in T.read_log(app.store.ai_log_path) if r['ai_kinds'][0].startswith(k)]
    learned = [k1 for r in rec for k1, _, _ in r['updates'] if f'|{DEC}|' in k1]
    check(f'AI끼리({k}) 체인 순서 판단 · 순서대로 체인 · 학습 기록', res['status'] == 'done' and lines and learned
          and all(in_order(g) for g in gs), f'(판단 {len(lines)} · 묶음 {len(gs)} · 학습 {len(learned)} · 예: {lines[0][:90] if lines else "-"})')
print('결과:', '통과' if ok else '실패'); sys.exit(0 if ok else 1)
