"""기능 v1② 접속중 명단 자동 스모크 (nny_sim 폴더에서): python -m unittest test_online_clients -v
heartbeat 호출 IP가 짧은 TTL로 기억되어 /api/boot·/api/heartbeat 응답의 'online' 목록에 뜨는지,
등록된 이름으로 표시되는지, TTL 이 지나면 빠지는지 확인.
"""
import json, os, shutil, sys, tempfile, threading, time, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S


def req(base, token, method, path):
    r = urllib.request.Request(base + path, method=method, headers={'X-NNY-Token': token})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as ex: return ex.code, json.loads(ex.read())


class OnlineClientsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_clients_')
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

    def test_boot_online_empty_before_any_heartbeat(self):
        self.start()
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 200, body)
        self.assertEqual(body['online'], [])

    def test_heartbeat_appears_in_boot_online_list(self):
        self.start()
        st, body = req(self.base, self.token, 'POST', '/api/heartbeat')
        self.assertEqual(st, 200, body)
        self.assertEqual(body['online'], [{'ip': '127.0.0.1', 'name': '127.0.0.1'}])
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(body['online'], [{'ip': '127.0.0.1', 'name': '127.0.0.1'}])

    def test_registered_name_shown_instead_of_ip(self):
        self.write_users(장인준='127.0.0.1')
        self.start()
        req(self.base, self.token, 'POST', '/api/heartbeat')
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(body['online'], [{'ip': '127.0.0.1', 'name': '장인준'}])

    def test_stale_heartbeat_drops_out_after_ttl(self):
        self.start()
        req(self.base, self.token, 'POST', '/api/heartbeat')
        self.app.clients['127.0.0.1'] = time.time() - S.CLIENT_TTL - 1
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(body['online'], [])


if __name__ == '__main__':
    unittest.main()
