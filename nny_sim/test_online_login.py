"""로그인 게이트(입장 암호) 자동 스모크 (2026-11-03, 장인준 — 하마치 없이 링크로 들어오기): python -m unittest test_online_login -v
암호가 없으면 게이트 꺼짐(기존 하마치 IP 게이트만) · 암호가 있고 IP 가 미등록이면 첫 화면이 로그인 페이지 · 틀린 암호 400 ·
맞으면 쿠키가 생기고 그 쿠키로 /api/boot 가 열리며 로비 이름이 로그인 이름으로 잡힘 · 로그아웃하면 다시 막힘.
"""
import json, os, shutil, sys, tempfile, threading, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S


def req(base, method, path, body=None, headers=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method, headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as ex: return ex.code, ex.read(), ex.headers


class LoginGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_login_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        user = os.path.join(self.tmp, 'user'); os.makedirs(user, exist_ok=True)
        # 등록 유저제 켬(하마치 IP 하나) — 테스트 클라이언트(127.0.0.1)는 미등록이라 게이트에 걸린다
        with open(os.path.join(user, 'online_users.json'), 'w', encoding='utf-8') as f: json.dump({'장인준': '25.0.242.63'}, f)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': user, 'static': os.path.abspath('app/static'), 'viewer': os.path.abspath('viewer')}
        self.app, self.srv = S.serve(self.paths, port=0, host='127.0.0.1')
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def set_pw(self, pw):
        with open(self.app.login_path, 'w', encoding='utf-8') as f: json.dump({'암호': pw}, f)

    def test_gate_off_without_password(self):
        self.assertIsNone(self.app.login_password())
        st, body, _ = req(self.base, 'GET', '/')
        self.assertEqual(st, 403)                       # 암호 없으면 기존 그대로: 미등록 IP 는 막힘
        st, body, _ = req(self.base, 'POST', '/api/login', {'name': '갑', 'password': 'x'})
        self.assertEqual(st, 400)

    def test_login_page_then_cookie_opens_app(self):
        self.set_pw('비밀1234')
        st, body, _ = req(self.base, 'GET', '/')
        self.assertEqual(st, 200); self.assertIn('입장 암호'.encode('utf-8'), body)   # 로그인 페이지
        st, body, _ = req(self.base, 'GET', '/api/boot', headers={'X-NNY-Token': self.app.token})
        self.assertEqual(st, 403)
        st, body, _ = req(self.base, 'POST', '/api/login', {'name': '세창', 'password': '틀림'})
        self.assertEqual(st, 400)
        st, body, hdr = req(self.base, 'POST', '/api/login', {'name': '세창', 'password': '비밀1234'})
        self.assertEqual(st, 200)
        cookie = hdr.get('Set-Cookie').split(';')[0]
        self.assertTrue(cookie.startswith('nny_sid='))
        st, body, _ = req(self.base, 'GET', '/', headers={'Cookie': cookie})
        self.assertEqual(st, 200); self.assertIn(b'nny-token', body)                     # 본 화면
        st, body, _ = req(self.base, 'GET', '/api/boot', headers={'X-NNY-Token': self.app.token, 'Cookie': cookie})
        self.assertEqual(st, 200)
        st, body, _ = req(self.base, 'POST', '/api/room/join', {'name': '딴이름', 'role': 'player'},
                          headers={'X-NNY-Token': self.app.token, 'Cookie': cookie})
        self.assertEqual(json.loads(body)['members'][0]['name'], '세창')   # 로그인 이름이 등록 이름 노릇
        st, body, _ = req(self.base, 'POST', '/api/logout', {}, headers={'X-NNY-Token': self.app.token, 'Cookie': cookie})
        self.assertEqual(st, 200)
        st, body, _ = req(self.base, 'GET', '/api/boot', headers={'X-NNY-Token': self.app.token, 'Cookie': cookie})
        self.assertEqual(st, 403)

    def test_env_password_and_ping_flag(self):
        os.environ['NNY_LOGIN_PASSWORD'] = 'env암호'
        try:
            st, body, _ = req(self.base, 'GET', '/api/ping')
            self.assertTrue(json.loads(body)['login_gate'])
            st, body, _ = req(self.base, 'POST', '/api/login', {'name': '을', 'password': 'env암호'})
            self.assertEqual(st, 200)
        finally: del os.environ['NNY_LOGIN_PASSWORD']


if __name__ == '__main__':
    unittest.main()
