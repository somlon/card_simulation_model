"""동시 매치 2개(2026-11-04, 장인준) 자동 스모크 (nny_sim 폴더에서): python -m unittest test_online_two_matches -v
① AI vs AI 매치 둘을 동시에 돌려 둘 다 끝나고 기록(frames)이 서로 섞이지 않는지(기록 훅·사람 자리 훅은 프로세스 전역이지만
   Game·Recorder 는 매치별이어야 한다) ② 세 번째 매치는 거부 ③ 대기실 플레이어 4명 · 방장이 상대를 골라 두 판을 띄우면
   my_match 가 각자 자기 판으로 라우팅 ④ poll·answer·abort 가 매치 id 로 갈린다. 엔진·룰 레이어는 건드리지 않음(app 레이어만).
"""
import json, os, shutil, sys, tempfile, threading, time, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S


def req(base, token, method, path, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={'X-NNY-Token': token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as ex: return ex.code, json.loads(ex.read())


def wait_done(m, timeout=60):
    t = time.time()
    while m.status in ('starting', 'running') and time.time() - t < timeout: time.sleep(0.05)
    m.thread.join(max(1, timeout - (time.time() - t)))   # status 는 기보 저장(replay_id) 전에 바뀐다 — 스레드가 끝까지 가도록
    return m.status


class TwoMatchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_two_')
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
        ids = [d['id'] for d in self.app.store.deck_list() if d['kind'] == 'official' and d['valid']]
        self.assertGreaterEqual(len(ids), 4)
        self.d = ids[:4]

    def tearDown(self):
        for m in list(self.app.lives.values()): m.abort()
        self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _aivai(self, a, b, seed, ip=None):
        return self.app.start_match({'deck': a, 'ai_deck': b, 'humans': [False, False], 'learn': False, 'seed': seed, 'first': 'me'}, ip=ip)

    def test_two_ai_matches_run_concurrently_without_mixing(self):
        ra = self._aivai(self.d[0], self.d[1], 1); rb = self._aivai(self.d[2], self.d[3], 2)
        self.assertNotEqual(ra['id'], rb['id'])
        self.assertEqual(len(self.app.running_lives()) + len([m for m in self.app.lives.values() if m.status == 'done']), 2)
        ma, mb = self.app.lives[ra['id']], self.app.lives[rb['id']]
        self.assertEqual(wait_done(ma), 'done', ma.error); self.assertEqual(wait_done(mb), 'done', mb.error)
        self.assertGreater(len(ma.rec.frames), 0); self.assertGreater(len(mb.rec.frames), 0)
        self.assertIsNot(ma.rec, mb.rec)
        # 기록 줄의 이름은 자기 매치 것만 — 상대 매치의 덱 이름이 끼어들면 훅이 섞인 것
        msgs_a = ' '.join(fr['m'] for fr in ma.rec.frames); msgs_b = ' '.join(fr['m'] for fr in mb.rec.frames)
        for nm in rb['names']: self.assertNotIn(nm, msgs_a, f'매치 A 기록에 매치 B 이름 「{nm}」')
        for nm in ra['names']: self.assertNotIn(nm, msgs_b, f'매치 B 기록에 매치 A 이름 「{nm}」')
        for nm in ra['names']: self.assertIn(nm, msgs_a)
        for nm in rb['names']: self.assertIn(nm, msgs_b)
        self.assertEqual(ma.result['decks'], [self.app.store.deck(self.d[0])['스킬'], self.app.store.deck(self.d[1])['스킬']])
        self.assertEqual(mb.result['decks'], [self.app.store.deck(self.d[2])['스킬'], self.app.store.deck(self.d[3])['스킬']])
        self.assertTrue(ma.replay_id and mb.replay_id and ma.replay_id != mb.replay_id)   # 기보도 따로 저장

    def _pvp(self, a, b, ip):   # 사람 대 사람 — 사람 답을 기다리느라 멈춰 있으니 "진행 중" 상태를 확실히 잡는다
        return self.app.start_match({'deck': a, 'ai_deck': b, 'humans': [True, True], 'learn': False, 'first': 'me'}, ip=ip)

    def test_third_match_rejected_but_own_restart_replaces(self):
        ra = self._pvp(self.d[0], self.d[1], '25.0.0.11'); rb = self._pvp(self.d[2], self.d[3], '25.0.0.12')
        self.assertEqual(len(self.app.running_lives()), 2)
        with self.assertRaises(ValueError): self._pvp(self.d[0], self.d[2], '25.0.0.13')
        st, body = req(self.base, self.token, 'POST', '/api/match/start',
                       {'deck': self.d[0], 'ai_deck': self.d[2], 'humans': [False, False], 'learn': False, 'seed': 3})
        self.assertEqual(st, 400); self.assertIn('2개까지', body['error'])
        # 자기 판을 두고 다시 시작하면 그 판만 그만두고 새 판(옛 단일 매치 동작)
        rc = self._pvp(self.d[0], self.d[2], '25.0.0.11')
        self.assertEqual(wait_done(self.app.lives[ra['id']], 10), 'aborted')
        self.assertIn(self.app.lives[rb['id']].status, ('starting', 'running'))
        self.assertEqual({m.id for m in self.app.running_lives()}, {rb['id'], rc['id']})

    def _room(self, ip, name, deck, role='player'):
        self.app.room_join(ip, name, role, deck)

    def test_lobby_four_players_two_matches_routing(self):
        self._room('25.0.0.11', '갑', self.d[0]); self._room('25.0.0.12', '을', self.d[1])
        self._room('25.0.0.13', '병', self.d[2]); self._room('25.0.0.14', '정', self.d[3])
        st = self.app.room_status()
        self.assertEqual(st['players'], 4); self.assertFalse(st['open_seat']); self.assertEqual(st['max_players'], 4)
        with self.assertRaises(ValueError): self.app.room_join('25.0.0.15', '무', 'player', self.d[0])   # 다섯째 플레이어는 없다
        # 방장(갑)이 상대로 병을 골라 1판 — 갑·병
        r1 = self.app.room_start('25.0.0.11', {'mode': 'pvp', 'learn': False, 'opponent': '25.0.0.13'})
        self.assertEqual(r1['my_match']['seat'], 0)
        self.assertEqual(self.app.my_match('25.0.0.13')['id'], r1['id']); self.assertEqual(self.app.my_match('25.0.0.13')['seat'], 1)
        self.assertIsNone(self.app.my_match('25.0.0.12')); self.assertIsNone(self.app.my_match('25.0.0.14'))
        st = self.app.room_status()
        self.assertEqual({m['name']: m['match'] for m in st['members']}, {'갑': r1['id'], '병': r1['id'], '을': None, '정': None})
        self.assertEqual(len(st['lives']), 1)
        # 이미 대전 중인 병을 다시 상대로 고르면 거부, 상대 없이 시작하면 남은 둘(을·정)
        with self.assertRaises(ValueError): self.app.room_start('25.0.0.11', {'mode': 'pvp', 'learn': False, 'opponent': '25.0.0.13'})
        r2 = self.app.room_start('25.0.0.11', {'mode': 'pvp', 'learn': False})
        self.assertNotEqual(r1['id'], r2['id'])
        self.assertEqual(self.app.my_match('25.0.0.12')['id'], r2['id']); self.assertEqual(self.app.my_match('25.0.0.12')['seat'], 0)
        self.assertEqual(self.app.my_match('25.0.0.14')['id'], r2['id']); self.assertEqual(self.app.my_match('25.0.0.14')['seat'], 1)
        self.assertEqual(self.app.my_match('25.0.0.11')['id'], r1['id'])   # 갑은 여전히 1판
        self.assertEqual(len(self.app.room_status()['lives']), 2)
        with self.assertRaises(ValueError): self.app.room_start('25.0.0.11', {'mode': 'aivai', 'deck': self.d[0], 'ai_deck': self.d[1]})
        self.assertEqual(self.app.live_ips, {'25.0.0.11': 0, '25.0.0.13': 1, '25.0.0.12': 0, '25.0.0.14': 1})   # 호환 속성

    def test_poll_answer_abort_routed_by_match_id(self):
        self._room('25.0.0.11', '갑', self.d[0]); self._room('25.0.0.12', '을', self.d[1])
        self._room('25.0.0.13', '병', self.d[2]); self._room('25.0.0.14', '정', self.d[3])
        r1 = self.app.room_start('25.0.0.11', {'mode': 'pvp', 'learn': False, 'opponent': '25.0.0.12'})
        r2 = self.app.room_start('25.0.0.11', {'mode': 'pvp', 'learn': False})
        m1, m2 = self.app.lives[r1['id']], self.app.lives[r2['id']]
        self.assertEqual(self.app.my_match('25.0.0.13')['id'], r2['id'])
        # HTTP: boot/heartbeat 에 lives 둘, poll 은 id 별로 자기 상태
        st, boot = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 200); self.assertEqual({li['id'] for li in boot['lives']}, {r1['id'], r2['id']}); self.assertEqual(boot['max_live'], 2)
        st, p1 = req(self.base, self.token, 'GET', f'/api/match/poll?id={r1["id"]}&spectate=1')
        st, p2 = req(self.base, self.token, 'GET', f'/api/match/poll?id={r2["id"]}&spectate=1')
        self.assertEqual((p1['id'], p2['id']), (r1['id'], r2['id'])); self.assertIsNone(p1['pending']); self.assertIsNone(p2['pending'])
        st, px = req(self.base, self.token, 'GET', '/api/match/poll?id=nope')
        self.assertEqual(px['status'], 'none')
        # 사람 자리 질문은 각 매치의 bridge 에 따로 선다 — 틀린 키로는 답할 수 없고, 1판의 키로 2판에 답할 수 없다
        t = time.time()
        while (m1.bridges[0].pending is None or m2.bridges[0].pending is None) and time.time() - t < 20: time.sleep(0.05)
        self.assertIsNotNone(m1.bridges[0].pending); self.assertIsNotNone(m2.bridges[0].pending)
        self.assertFalse(m2.answer(m2.bridges[0].pending['id'], 0, seat=0, key=m1.keys[0]))
        st, ans = req(self.base, self.token, 'POST', '/api/match/answer', {'id': r2['id'], 'rid': m2.bridges[0].pending['id'], 'idx': 0, 'seat': 0, 'key': m1.keys[0]})
        self.assertFalse(ans['ok'])
        # abort 는 id 로 그 판만
        st, ab = req(self.base, self.token, 'POST', '/api/match/abort', {'id': r1['id'], 'key': m1.keys[0]})
        self.assertEqual(st, 200)
        self.assertEqual(wait_done(m1, 10), 'aborted')
        self.assertIn(m2.status, ('starting', 'running'))
        self.assertEqual(len(self.app.running_lives()), 1); self.assertEqual(self.app.room_status()['lives'][0]['id'], r2['id'])
        self.assertIsNone(self.app.my_match('25.0.0.11')); self.assertEqual(self.app.my_match('25.0.0.13')['id'], r2['id'])
        # 끝난 1판 자리가 비었으니 갑·을이 다시 붙을 수 있다
        r3 = self.app.room_start('25.0.0.11', {'mode': 'pvp', 'learn': False})
        self.assertEqual(sorted(self.app.live_meta[r3['id']]['ips']), ['25.0.0.11', '25.0.0.12'])


if __name__ == '__main__':
    unittest.main()
