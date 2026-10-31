"""기능 v1② 등록 유저제 자동 스모크 (nny_sim 폴더에서): python -m unittest test_user_gate -v
online_users.json(파일 없음/등록 없음 → 게이트 비활성, 등록된 IP만 허용 → 미등록 거부) 를 확인.
서버는 --host 로 127.0.0.1 에 직접 연다 — 테스트 요청은 모두 127.0.0.1 에서 온다.
"""
import json, os, shutil, sys, tempfile, threading, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S


def req(base, token, method, path):
    r = urllib.request.Request(base + path, method=method, headers={'X-NNY-Token': token})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, resp.read()
    except urllib.error.HTTPError as ex: return ex.code, ex.read()


class UserGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_gate_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.user_dir = os.path.join(self.tmp, 'user'); os.makedirs(self.user_dir, exist_ok=True)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': self.user_dir, 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}

    def start(self):
        self.app, self.srv = S.serve(self.paths, port=0, host='127.0.0.1')
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        self.token = self.app.token
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        if getattr(self, 'app', None) and self.app.live: self.app.live.abort()
        if getattr(self, 'srv', None): self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_users(self, **ip_by_name):
        with open(os.path.join(self.user_dir, 'online_users.json'), 'w', encoding='utf-8') as f:
            json.dump(ip_by_name, f, ensure_ascii=False)

    def test_no_users_file_allows_everyone(self):
        self.start()
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 200, body)

    def test_empty_registration_allows_everyone(self):
        self.write_users(_설명='이름:하마치IP')  # 메타 키만, 실제 등록 없음
        self.start()
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 200, body)

    def test_unregistered_ip_rejected(self):
        self.write_users(장인준='25.0.242.63')  # 테스트는 127.0.0.1 에서 오므로 미등록
        self.start()
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 403, body)
        st, _ = req(self.base, self.token, 'GET', '/')
        self.assertEqual(st, 403)

    def test_registered_ip_allowed(self):
        self.write_users(장인준='127.0.0.1')
        self.start()
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 200, body)
        st, _ = req(self.base, self.token, 'GET', '/')
        self.assertEqual(st, 200)

    def test_ping_always_open(self):
        self.write_users(장인준='25.0.242.63')  # 미등록 IP라도
        self.start()
        st, body = req(self.base, self.token, 'GET', '/api/ping')
        self.assertEqual(st, 200, body)


if __name__ == '__main__':
    unittest.main()
