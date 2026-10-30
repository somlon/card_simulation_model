"""기능 v1④ 관전 — 관전 중 로비 "나가기"가 관전 화면을 끊도록 한 수정의 자동 스모크
(nny_sim 폴더에서): python -m unittest test_online_spectate_leave -v

이 수정은 전부 클라이언트 쪼가리(app.js, lobby-leave 핸들러)라 서버 API는 하나도 안 바꿨다 —
그래서 이 테스트는 두 부분으로 나뉜다.
1) 서버가 내려주는 app.js에 수정이 실제로 들어 있는지(구조 확인, test_online_theme.py와 같은 방식 —
   전환 자체는 순수 클라이언트 로직이라 실제 브라우저 클릭 없이는 "화면이 정말 멈추는지"까지는 못 본다).
2) 가짜 HTTP 클라이언트로 「대전 2(좌석0·좌석1) + 관전 1」을 끝까지 돌려, 이 수정이 필요했던 이유인
   서버 쪽 사실(= `/api/room/leave`는 room 멤버십만 바꾸고 매치 poll 자체는 전혀 막지 않는다)이
   여전히 그대로인지 확인한다 — 이게 그대로이기 때문에 클라이언트가 스스로 멈춰야 한다.
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


class SpectateLeaveJsTest(unittest.TestCase):
    """app.js 구조 확인 — test_online_theme.py 와 같은 방식."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_specleave_js_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.user_dir = os.path.join(self.tmp, 'user'); os.makedirs(self.user_dir, exist_ok=True)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': self.user_dir, 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}
        self.app, self.srv = S.serve(self.paths, port=0, host='127.0.0.1')
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        self.token = self.app.token
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        if getattr(self, 'app', None) and self.app.live: self.app.live.abort()
        if getattr(self, 'srv', None): self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _js(self):
        r = urllib.request.Request(self.base + '/app.js', headers={'X-NNY-Token': self.token})
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.read().decode('utf-8')

    def test_lobby_leave_stops_spectating_when_spectating(self):
        js = self._js()
        self.assertIn('function stopSpectating()', js)
        # lobby-leave 핸들러가 room/leave 호출 뒤 관전 중이면(그리고 아직 끝나지 않았으면) stopSpectating 을 부른다
        m = js.find("$('lobby-leave').onclick")
        self.assertNotEqual(m, -1, "lobby-leave 핸들러를 못 찾음")
        handler = js[m:m + 400]
        self.assertIn("api('room/leave'", handler)
        self.assertIn('if (G.spectating && !G.done) stopSpectating();', handler)

    def test_stop_spectating_clears_poll_and_ends_live_view(self):
        js = self._js()
        m = js.find('function stopSpectating()')
        self.assertNotEqual(m, -1)
        body = js[m:m + 500]
        self.assertIn('clearTimeout(G.poll)', body, '관전 중 나가면 폴링을 멈춰야 한다')
        self.assertIn('st.endLive()', body, '숨겼던 패를 공개하고 보드 상태를 정리해야 한다')
        self.assertIn('G.spectating = false', body)
        self.assertIn('G.id = null', body, '매치 id 를 비워야 로비에서 같은 매치를 다시 관전할 수 있다')

    def test_player_leaving_room_is_unaffected(self):
        """참가자(player)의 매치는 room/leave 로 건드리지 않는다 — abort 로 따로 그만두는 것과 다름,
        이 회차 수정은 관전자(spectate)만 다룬다(의도적으로 참가자 쪽은 안 건드림)."""
        js = self._js()
        m = js.find("$('lobby-leave').onclick")
        handler = js[m:m + 400]
        # 참가자 매치를 끝내는 abort 호출이 lobby-leave 핸들러 안에는 없어야 한다
        self.assertNotIn("match/abort", handler)


class SpectateLeaveServerFactsTest(unittest.TestCase):
    """가짜 클라이언트 「대전 2 + 관전 1」 — 이 수정이 필요했던 서버 쪽 사실이 그대로인지 확인."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_specleave_srv_')
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

    def test_room_leave_does_not_stop_match_poll_for_spectator(self):
        """대전 2(좌석0·좌석1) + 관전 1 끝까지 — 관전자가 room/leave 해도 spectate poll 은 계속 동작한다
        (서버가 안 막아 준다는 것, 즉 클라이언트가 스스로 멈춰야 하는 이유)."""
        d1, d2 = self.decks()
        st, start = req(self.base, self.token, 'POST', '/api/match/start',
                        {'deck': d1, 'ai_deck': d2, 'humans': [True, True], 'learn': False, 'first': 'me'})
        self.assertEqual(st, 200, start)
        mid = start['id']; seats = start['seats']
        key0, key1 = seats['0'], seats['1']

        # 관전자: 로비에 들어온다(room/join, spectator) — 본 매치의 ip 와는 다른 척(테스트 클라이언트는
        # 항상 127.0.0.1 이라 room 딥만 흉내, poll 자체는 room 멤버십과 무관하게 동작하는지가 핵심)
        st, room = req(self.base, self.token, 'POST', '/api/room/join', {'name': '관전자', 'role': 'spectator'})
        self.assertEqual(st, 200, room)

        answered = {0: 0, 1: 0}
        left_room = False
        for _ in range(400):
            _, p0 = self.poll(mid, 0, key0)
            _, p1 = self.poll(mid, 1, key1)
            _, spec = self.poll(mid, spectate=True)
            self.assertIsNone(spec['pending'], '관전(spectate=1)인데 판단 패널이 보였다')
            self.assertIsNone(spec['seat'])

            if not left_room:   # 중간에 로비에서 나가 본다 — room/leave 는 room 멤버십만 바꾼다
                st, room = req(self.base, self.token, 'POST', '/api/room/leave', {})
                self.assertEqual(st, 200, room)
                self.assertEqual(room['members'], [], 'room/leave 뒤에도 관전자가 room 에 남아 있으면 안 된다')
                left_room = True

            # room 을 나간 뒤에도 서버는 spectate poll 을 계속 똑같이 돌려준다(막지 않음) —
            # 바로 이 사실 때문에 클라이언트(app.js)가 로비 나가기 때 스스로 화면을 끊어야 한다.
            _, spec_after_leave = self.poll(mid, spectate=True)
            self.assertIsNone(spec_after_leave['pending'])
            self.assertIn(spec_after_leave['status'], ('starting', 'running', 'done', 'aborted', 'stalled', 'error'))

            pend, seat, key, other_key = (p0['pending'], 0, key0, key1) if p0['pending'] else \
                                         (p1['pending'], 1, key1, key0) if p1['pending'] else (None, None, None, None)
            if pend is None:
                if p0['status'] not in ('starting', 'running'): break
                time.sleep(0.02); continue
            rid = pend['id']
            st, ans = req(self.base, self.token, 'POST', '/api/match/answer', {'rid': rid, 'idx': 0, 'seat': seat, 'key': key})
            self.assertTrue(ans['ok'], ans)
            answered[seat] += 1

        self.assertTrue(left_room, '관전자가 room/leave 를 실제로 호출하지 못했다')
        self.assertGreater(answered[0] + answered[1], 0, '대전 2쪽 어느 좌석도 판단을 받지 못했다 — 매치가 안 돌았다')
        self.app.live.abort()


if __name__ == '__main__':
    unittest.main()
