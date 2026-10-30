"""기능 v1③ 로비 서버 쪼가리 자동 스모크 (nny_sim 폴더에서): python -m unittest test_online_lobby -v
참가(player)·관전(spectator)·나가기 · 자리(player) 최대 2 · 재접속 유예(heartbeat 가 이어지면 안 비워짐,
ROOM_GRACE 지나면 비워짐)를 확인한다. 엔진·룰 레이어는 건드리지 않음 — app/server.py 의 room_* 메서드만.
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


class RoomLobbyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_room_')
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

    def test_room_empty_before_anyone_joins(self):
        st, body = req(self.base, self.token, 'GET', '/api/room/status')
        self.assertEqual(st, 200, body)
        self.assertEqual(body, {'members': [], 'players': 0, 'open_seat': True})

    def test_join_as_player_then_spectator_shows_in_boot_and_room(self):
        # 같은 IP(127.0.0.1)에서 테스트하므로 역할 전환으로 확인 — player 로 먼저 들어간다
        st, body = req(self.base, self.token, 'POST', '/api/room/join', {'name': '장인준', 'role': 'player'})
        self.assertEqual(st, 200, body)
        self.assertEqual(body['players'], 1); self.assertTrue(body['open_seat'])
        self.assertEqual(body['members'], [{'ip': '127.0.0.1', 'name': '장인준', 'role': 'player'}])
        st, boot = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(boot['room']['players'], 1)
        # 역할을 관전으로 바꾸면(재접속 시 선택이 달라진 경우) player 자리가 비워진다
        st, body = req(self.base, self.token, 'POST', '/api/room/join', {'name': '장인준', 'role': 'spectator'})
        self.assertEqual(body['players'], 0); self.assertEqual(body['members'][0]['role'], 'spectator')

    def test_room_full_rejects_third_player(self):
        # 같은 서버 안에서 가짜 IP 두 개를 직접 room 에 채워 자리(2명) 가득 참을 흉내낸다
        self.app.room['25.0.0.11'] = {'name': 'A', 'role': 'player', 'joined': time.time(), 'last_seen': time.time()}
        self.app.room['25.0.0.12'] = {'name': 'B', 'role': 'player', 'joined': time.time(), 'last_seen': time.time()}
        st, body = req(self.base, self.token, 'POST', '/api/room/join', {'name': 'C', 'role': 'player'})
        self.assertEqual(st, 400, body)
        self.assertIn('가득', body['error'])
        # 관전으로는 그대로 들어갈 수 있다(자리 제한은 player 에만 적용)
        st, body = req(self.base, self.token, 'POST', '/api/room/join', {'name': 'C', 'role': 'spectator'})
        self.assertEqual(st, 200, body); self.assertEqual(body['players'], 2)

    def test_leave_removes_from_room(self):
        req(self.base, self.token, 'POST', '/api/room/join', {'name': '장인준', 'role': 'player'})
        st, body = req(self.base, self.token, 'POST', '/api/room/leave')
        self.assertEqual(st, 200, body)
        self.assertEqual(body, {'members': [], 'players': 0, 'open_seat': True})

    def test_heartbeat_keeps_room_seat_alive_reconnect_grace(self):
        req(self.base, self.token, 'POST', '/api/room/join', {'name': '장인준', 'role': 'player'})
        self.app.room['127.0.0.1']['last_seen'] = time.time() - (S.ROOM_GRACE - 5)  # 유예 안(거의 다 됐지만 아직 안 끊김)
        st, hb = req(self.base, self.token, 'POST', '/api/heartbeat')
        self.assertEqual(hb['room']['players'], 1, 'heartbeat 가 오면 유예 안에서는 자리가 유지돼야 한다')

    def test_room_grace_expires_after_timeout(self):
        req(self.base, self.token, 'POST', '/api/room/join', {'name': '장인준', 'role': 'player'})
        self.app.room['127.0.0.1']['last_seen'] = time.time() - S.ROOM_GRACE - 1  # 유예 지남 — heartbeat 없이 조회
        st, body = req(self.base, self.token, 'GET', '/api/room/status')
        self.assertEqual(body, {'members': [], 'players': 0, 'open_seat': True}, '유예가 지나면 자리를 비워야 한다')

    def write_users(self, **ip_by_name):
        """등록 유저 파일(online_users.json, 이름→IP) — test_user_gate.py 와 같은 방식."""
        os.makedirs(self.paths['user'], exist_ok=True)
        with open(os.path.join(self.paths['user'], 'online_users.json'), 'w', encoding='utf-8') as f:
            json.dump(ip_by_name, f, ensure_ascii=False)

    def test_registered_ip_join_uses_registered_name_not_typed(self):
        # 「다음 회차 지시」 2번 — 등록된 유저가 로비에서 다른 이름을 타이핑해도 등록 이름이 그대로 쓰인다
        self.write_users(장인준='127.0.0.1')
        st, body = req(self.base, self.token, 'POST', '/api/room/join', {'name': '아무개', 'role': 'player'})
        self.assertEqual(st, 200, body)
        self.assertEqual(body['members'], [{'ip': '127.0.0.1', 'name': '장인준', 'role': 'player'}])

    def test_unregistered_ip_join_keeps_typed_name(self):
        # 게이트 비활성(등록 없음) 상태에서는 기존 그대로 직접 타이핑한 이름을 쓴다
        # (등록이 있으면 게이트가 서서 미등록 IP 자체가 403 으로 막히므로 — test_user_gate.py 참고 —
        # "등록 있음 + 이 IP 는 미등록" 조합은 room_join 전에 이미 걸러져 room_join 단계까지 오지 않는다)
        self.write_users(_설명='이름:하마치IP')  # 메타 키만, 실제 등록 없음 → 게이트 비활성
        st, body = req(self.base, self.token, 'POST', '/api/room/join', {'name': '아무개', 'role': 'player'})
        self.assertEqual(st, 200, body)
        self.assertEqual(body['members'], [{'ip': '127.0.0.1', 'name': '아무개', 'role': 'player'}])

    def test_registered_name_flows_into_chat_sender(self):
        # 로비 이름이 등록 이름으로 맞춰지면, 인게임 메신저의 발신자(who)도 직접 타이핑에 의존하지 않고 자동으로 맞는다
        self.write_users(장인준='127.0.0.1')
        req(self.base, self.token, 'POST', '/api/room/join', {'name': '아무개', 'role': 'player'})
        st, msg = req(self.base, self.token, 'POST', '/api/room/chat', {'text': '안녕'})
        self.assertEqual(st, 200, msg)
        self.assertEqual(msg['who'], '장인준')


if __name__ == '__main__':
    unittest.main()
