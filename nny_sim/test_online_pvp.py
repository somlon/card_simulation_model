"""온라인판 사람vs사람 자동 스모크 (nny_sim 폴더에서): python -m unittest test_online_pvp -v
가짜 HTTP 클라이언트로 「대전 2(좌석0·좌석1) + 관전 1」을 흉내낸다 — 좌석 라우팅 · 교차 응답 거부 · 관전 pending 없음을 확인.
서버는 --host 로 127.0.0.1 에 직접 연다(하마치 탐색은 app/test_server_bind.py 쪽에서 따로 확인).
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


class PvpSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_pvp_')
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

    def poll(self, mid, seat=None, key=None, spectate=False):
        q = f'?id={mid}'
        if seat is not None: q += f'&seat={seat}'
        if key is not None: q += f'&key={key}'
        if spectate: q += '&spectate=1'
        return req(self.base, self.token, 'GET', '/api/match/poll' + q)

    def test_pvp_seat_routing_and_spectator(self):
        d1, d2 = self.decks()
        st, start = req(self.base, self.token, 'POST', '/api/match/start',
                        {'deck': d1, 'ai_deck': d2, 'humans': [True, True], 'learn': False, 'first': 'me'})
        self.assertEqual(st, 200, start)
        mid = start['id']; seats = start['seats']
        self.assertEqual(set(seats), {'0', '1'})
        key0, key1 = seats['0'], seats['1']
        self.assertNotEqual(key0, key1)

        # /api/match/join: 키만으로 자기 좌석을 찾는다
        st, j = req(self.base, self.token, 'POST', '/api/match/join', {'id': mid, 'key': key1})
        self.assertEqual(st, 200, j); self.assertEqual(j['seat'], 1)
        st, j = req(self.base, self.token, 'POST', '/api/match/join', {'id': mid, 'key': 'wrong'})
        self.assertEqual(st, 400, j)

        answered = {0: 0, 1: 0}
        for _ in range(400):
            _, p0 = self.poll(mid, 0, key0)
            _, p1 = self.poll(mid, 1, key1)
            _, spec = self.poll(mid)   # 관전: 좌석 · 키 없음
            self.assertIsNone(spec['pending'], '관전자에게 판단 패널이 보이면 안 된다')

            pend, seat, key, other_key = (p0['pending'], 0, key0, key1) if p0['pending'] else \
                                         (p1['pending'], 1, key1, key0) if p1['pending'] else (None, None, None, None)
            if pend is None:
                if p0['status'] not in ('starting', 'running'): break
                time.sleep(0.02); continue

            rid = pend['id']
            # 교차 응답 거부: 상대 좌석의 키로 이 pending 에 답하면 안 된다
            st, bad = req(self.base, self.token, 'POST', '/api/match/answer', {'rid': rid, 'idx': 0, 'seat': seat, 'key': other_key})
            self.assertFalse(bad['ok'], '다른 좌석의 키로 응답이 받아들여졌다')
            # 틀린 좌석 번호로 poll 하면 그 pending 이 보이면 안 된다(상대 자리로 들여다보기 금지)
            _, wrong_seat_view = self.poll(mid, 1 - seat, key)
            self.assertIsNone(wrong_seat_view['pending'])

            st, ans = req(self.base, self.token, 'POST', '/api/match/answer', {'rid': rid, 'idx': 0, 'seat': seat, 'key': key})
            self.assertTrue(ans['ok'], ans)
            answered[seat] += 1

        self.assertGreater(answered[0] + answered[1], 0, '좌석 어느 쪽도 판단을 받지 못했다 — 라우팅이 끊겼다')
        self.app.live.abort()

    def test_legacy_human_vs_ai_unaffected(self):
        """사람vsAI(좌석0 하나) — seat · key 없이 poll · answer 해도 기존처럼 동작해야 한다(호환)"""
        d1, d2 = self.decks()
        st, start = req(self.base, self.token, 'POST', '/api/match/start', {'deck': d1, 'ai_deck': d2, 'mode': 'human', 'learn': False})
        self.assertEqual(st, 200, start)
        mid = start['id']
        self.assertEqual(list(start['seats']), ['0'])
        got = False
        for _ in range(200):
            _, p = self.poll(mid)   # seat · key 생략 — 사람 자리가 하나뿐이면 자동으로 그 자리
            if p['pending']:
                got = True
                st, ans = req(self.base, self.token, 'POST', '/api/match/answer', {'rid': p['pending']['id'], 'idx': 0})
                self.assertTrue(ans['ok'])
            elif p['status'] not in ('starting', 'running'):
                break
            else:
                time.sleep(0.02)
        self.assertTrue(got, '사람vsAI 기존 방식(좌석 · 키 없이)이 끊겼다')
        self.app.live.abort()

    def test_spectate_flag_hides_pending_even_for_solo_human(self):
        """관전(④) — 사람vsAI(좌석 하나)라도 spectate=1 로 명시한 요청은 기존 '사람 자리 하나면 자동 귀속' 지름길을
        타지 않고 pending · seat 를 절대 보여주지 않아야 한다(제3자 관전이 그 한 명의 판단 패널을 가로채면 안 됨)."""
        d1, d2 = self.decks()
        st, start = req(self.base, self.token, 'POST', '/api/match/start', {'deck': d1, 'ai_deck': d2, 'mode': 'human', 'learn': False})
        self.assertEqual(st, 200, start)
        mid = start['id']
        saw_pending_legacy = False
        for _ in range(200):
            _, legacy = self.poll(mid)                       # 기존 방식(좌석·키 없음, spectate 없음) — 그 한 명 취급(호환)
            _, spec = self.poll(mid, spectate=True)           # 관전 화면(spectate=1) — 아무리 사람 자리가 하나뿐이어도 안 보임
            self.assertIsNone(spec['pending'], '관전(spectate=1)인데 사람vsAI 판단 패널이 보였다')
            self.assertIsNone(spec['seat'], '관전(spectate=1)인데 좌석이 귀속됐다')
            if legacy['pending']: saw_pending_legacy = True; break   # 확인됐으면 더 돌 필요 없음(응답하지 않으면 매치가 끝나지 않음)
            if legacy['status'] not in ('starting', 'running'): break
            time.sleep(0.02)
        self.assertTrue(saw_pending_legacy, '기존 방식(사람vsAI, spectate 없이)에 판단 패널이 한 번도 안 보여 확인할 수 없었다')
        self.app.live.abort()


if __name__ == '__main__':
    unittest.main()
