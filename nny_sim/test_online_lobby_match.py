"""기능 v1③ 로비 화면 쪼가리 — 로비(방)에서 짝지어 시작한 사람vs사람 매치의 자동 연결 자동 스모크
(nny_sim 폴더에서): python -m unittest test_online_lobby_match -v
방에 player 둘(ip 다름)이 있을 때 매치를 시작하면 그 둘의 ip 가 좌석0·1 에 자동으로 묶이고
(App.my_match(ip)가 매치 ID·참가 키를 그대로 돌려줌 — 화면이 수동으로 키를 받지 않아도 되는 바탕),
방을 거치지 않은(수동) 시작은 예전처럼 비워 둔다(호환)를 확인한다. 엔진·룰 레이어는 건드리지 않음 —
app/server.py 의 room·live_ips·my_match 만.
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


class LobbyAutoMatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_lobbymatch_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': os.path.join(self.tmp, 'user'), 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}
        self.app, self.srv = S.serve(self.paths, port=0, host='127.0.0.1')
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        self.token = self.app.token
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        if self.app.live: self.app.live.abort()
        self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def decks(self):
        st, d = req(self.base, self.token, 'GET', '/api/decks')
        self.assertEqual(st, 200)
        ids = [x['id'] for x in d if x['kind'] == 'official' and x['valid']]
        self.assertGreaterEqual(len(ids), 2)
        return ids[0], ids[1]

    def _room(self, ip, name, role='player'):
        self.app.room[ip] = {'name': name, 'role': role, 'joined': time.time(), 'last_seen': time.time()}

    def test_lobby_pair_auto_wires_both_seats(self):
        d1, d2 = self.decks()
        self._room('25.0.0.11', 'A'); self._room('25.0.0.12', 'B')
        start = self.app.start_match({'deck': d1, 'ai_deck': d2, 'humans': [True, True], 'learn': False, 'first': 'me'},
                                      ip='25.0.0.11')
        self.assertEqual(self.app.live_ips, {'25.0.0.11': 0, '25.0.0.12': 1})
        m_a = self.app.my_match('25.0.0.11'); m_b = self.app.my_match('25.0.0.12')
        self.assertEqual(m_a['seat'], 0); self.assertEqual(m_b['seat'], 1)
        self.assertEqual(m_a['id'], start['id']); self.assertEqual(m_b['id'], start['id'])
        self.assertEqual(m_a['key'], self.app.live.keys[0]); self.assertEqual(m_b['key'], self.app.live.keys[1])
        self.assertIsNone(self.app.my_match('25.0.0.99'), '방에 없던 ip 는 자동 연결되면 안 된다')
        self.app.live.abort()

    def test_my_match_via_http_boot_and_heartbeat(self):
        """실제 HTTP 호출(boot·heartbeat)에도 my_match 필드가 ip 기준으로 실린다 — 테스트 클라이언트는 항상
        127.0.0.1 로 오므로 그 ip 를 방의 player 로 넣어 확인한다"""
        d1, d2 = self.decks()
        self._room('127.0.0.1', '나'); self._room('25.0.0.12', '상대')
        start = self.app.start_match({'deck': d1, 'ai_deck': d2, 'humans': [True, True], 'learn': False, 'first': 'me'},
                                      ip='127.0.0.1')
        st, boot = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(boot['my_match']['id'], start['id']); self.assertEqual(boot['my_match']['seat'], 0)
        st, hb = req(self.base, self.token, 'POST', '/api/heartbeat')
        self.assertEqual(hb['my_match']['seat'], 0)
        self.app.live.abort()

    def test_manual_start_not_from_room_leaves_live_ips_empty(self):
        """방을 거치지 않고(수동) 사람vs사람을 시작하면 — 기존 매치 ID·참가 키 수동 공유 방식 그대로(호환)"""
        d1, d2 = self.decks()
        start = self.app.start_match({'deck': d1, 'ai_deck': d2, 'humans': [True, True], 'learn': False, 'first': 'me'},
                                      ip='25.0.0.50')  # 방에 없는 ip
        self.assertEqual(self.app.live_ips, {})
        self.assertIsNone(self.app.my_match('25.0.0.50'))
        self.assertIn(0, start['seats']); self.assertIn(1, start['seats'])
        self.app.live.abort()

    def test_room_has_three_people_but_only_two_players_still_pairs(self):
        """관전자가 섞여 있어도(player 둘만 자리 차지) 그 둘만 자동 연결된다"""
        d1, d2 = self.decks()
        self._room('25.0.0.11', 'A', 'player'); self._room('25.0.0.12', 'B', 'player')
        self._room('25.0.0.13', 'C', 'spectator')
        self.app.start_match({'deck': d1, 'ai_deck': d2, 'humans': [True, True], 'learn': False, 'first': 'me'},
                              ip='25.0.0.11')
        self.assertEqual(self.app.live_ips, {'25.0.0.11': 0, '25.0.0.12': 1})
        self.assertIsNone(self.app.my_match('25.0.0.13'), '관전자는 좌석에 자동으로 묶이면 안 된다')
        self.app.live.abort()


if __name__ == '__main__':
    unittest.main()
