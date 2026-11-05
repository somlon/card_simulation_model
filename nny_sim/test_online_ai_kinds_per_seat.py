"""자리별 AI 종류(오프라인판 app/main #99 · #101 이식, 2026-11-05) 자동 스모크 (nny_sim 폴더에서):
python -m unittest test_online_ai_kinds_per_seat -v

AI vs AI 관전 · 녹화에서 P1(ai0_kind) · P2(ai_kind) 자리의 AI 종류를 따로 고르면 그 자리에 그 AI 가 앉는지,
재생 기록 정보에 ai(P1) · ai2(P2) 가 남는지, 사람 vs AI 에서는 ai0_kind 를 쓰지 않는지, 모르는 종류는 400 으로 거부하는지.
"""
import json, os, shutil, sys, tempfile, threading, time, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S
import session as SS
import policy as P

WAIT = 120   # 초 — 매치 · 녹화 하나가 끝나기를 기다리는 시간


def req(base, token, method, path, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={'X-NNY-Token': token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as ex: return ex.code, json.loads(ex.read())


class AiKindsPerSeatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_aiseat_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': os.path.join(self.tmp, 'user'), 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}
        self.app, self.srv = S.serve(self.paths, port=0, host='127.0.0.1')
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'; self.token = self.app.token
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        st, d = req(self.base, self.token, 'GET', '/api/decks')
        self.ids = [x['id'] for x in d if x['kind'] == 'official' and x['valid']]
        self.assertGreaterEqual(len(self.ids), 2)
        # 어느 자리에 어떤 AI 가 앉았는지 — 만들어지는 AI 를 스킬(덱) 이름으로 적어 둔다
        self.made = []; made = self.made
        self._heur, self._learned = SS.HeuristicAI, P.LearnedAI

        class H(self._heur):
            def __init__(s, skill, *a, **kw): made.append(('heuristic', skill)); super().__init__(skill, *a, **kw)

        class L(self._learned):
            def __init__(s, skill, *a, **kw): made.append(('table', skill)); super().__init__(skill, *a, **kw)
        SS.HeuristicAI, P.LearnedAI = H, L

    def tearDown(self):
        SS.HeuristicAI, P.LearnedAI = self._heur, self._learned
        for m in list(self.app.lives.values()): m.abort()
        self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def skill(self, did): return self.app.store.deck(did)['스킬']

    def wait_match(self, mid):
        t = time.time()
        while time.time() - t < WAIT:
            st, poll = req(self.base, self.token, 'GET', f'/api/match/poll?id={mid}')
            if poll.get('status') not in ('starting', 'running') and poll.get('replay_id'): return poll
            time.sleep(0.05)
        self.fail('매치가 끝나지 않음')

    def replay(self, rid):
        st, boot = req(self.base, self.token, 'GET', '/api/boot')
        return next(r for r in boot['replays'] if r['id'] == rid)

    def test_ai_vs_ai_each_seat_gets_its_kind(self):
        a, b = self.ids[0], self.ids[1]
        st, r = req(self.base, self.token, 'POST', '/api/match/start',
                    {'deck': a, 'ai_deck': b, 'humans': [False, False], 'learn': False, 'first': 'me', 'seed': 7,
                     'ai0_kind': 'heuristic', 'ai_kind': 'table'})
        self.assertEqual(st, 200, r)
        poll = self.wait_match(r['id'])
        self.assertEqual(poll['status'], 'done', poll)
        kinds = {k for k, sk in self.made if sk == self.skill(a)}, {k for k, sk in self.made if sk == self.skill(b)}
        if self.skill(a) != self.skill(b):
            self.assertEqual(kinds, ({'heuristic'}, {'table'}), self.made)
        rp = self.replay(poll['replay_id'])
        self.assertEqual((rp['ai'], rp.get('ai2')), ('heuristic', 'table'))

    def test_record_job_uses_both_kinds(self):
        a, b = self.ids[0], self.ids[1]
        st, job = req(self.base, self.token, 'POST', '/api/record',
                      {'pairs': [[a, b]], 'matches': 1, 'seed': 3, 'ai0_kind': 'table', 'ai_kind': 'heuristic'})
        self.assertEqual(st, 200, job)
        t = time.time()
        while time.time() - t < WAIT:
            st, jobs = req(self.base, self.token, 'GET', '/api/jobs')
            j = next(x for x in jobs if x['id'] == job['id'])
            if j['status'] != 'running': break
            time.sleep(0.1)
        self.assertEqual(j['status'], 'done', j)
        rid = self.app.jobs[job['id']].done[0]['replay_id']
        rp = self.replay(rid)
        self.assertEqual((rp['ai'], rp.get('ai2')), ('table', 'heuristic'))
        self.assertIn(('heuristic', self.skill(b)), self.made)

    def test_human_vs_ai_ignores_ai0_kind(self):
        a, b = self.ids[0], self.ids[1]
        st, r = req(self.base, self.token, 'POST', '/api/match/start',
                    {'deck': a, 'ai_deck': b, 'humans': [True, False], 'learn': False, 'first': 'me',
                     'ai0_kind': '없는종류', 'ai_kind': 'heuristic'})   # 좌석0이 사람이면 ai0_kind 는 보지 않는다
        self.assertEqual(st, 200, r)
        m = self.app.lives[r['id']]
        self.assertEqual((m.ai_kind, m.ai0_kind), ('heuristic', 'heuristic'))

    def test_unknown_kinds_rejected(self):
        a, b = self.ids[0], self.ids[1]
        st, err = req(self.base, self.token, 'POST', '/api/match/start',
                      {'deck': a, 'ai_deck': b, 'humans': [False, False], 'learn': False, 'ai0_kind': '없는종류'})
        self.assertEqual(st, 400); self.assertIn('AI', err['error'])
        st, err = req(self.base, self.token, 'POST', '/api/record', {'pairs': [[a, b]], 'ai0_kind': '없는종류'})
        self.assertEqual(st, 400); self.assertIn('AI', err['error'])


if __name__ == '__main__':
    unittest.main()
