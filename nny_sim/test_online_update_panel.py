"""기능 v1⑧ 업데이트 패널 자동 스모크 (nny_sim 폴더에서): python -m unittest test_online_update_panel -v
/api/boot·/api/heartbeat 응답에 지금 돌고 있는 코드의 git 커밋 짧은 해시가 실리는지, git 이 없을 때도
조용히 None 으로 넘어가는지(서버가 죽지 않는지) 확인.
"""
import json, os, shutil, sys, tempfile, threading, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S


def req(base, token, method, path):
    r = urllib.request.Request(base + path, method=method, headers={'X-NNY-Token': token})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as ex: return ex.code, json.loads(ex.read())


class UpdatePanelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_update_')
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

    def test_boot_has_current_commit(self):
        self.start()
        st, body = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 200, body)
        self.assertEqual(body['commit'], S.commit_rev())
        self.assertTrue(body['commit'])  # 이 테스트는 실제 git 체크아웃 안에서 돈다

    def test_heartbeat_has_same_commit_as_boot(self):
        self.start()
        _, boot_body = req(self.base, self.token, 'GET', '/api/boot')
        st, hb_body = req(self.base, self.token, 'POST', '/api/heartbeat')
        self.assertEqual(st, 200, hb_body)
        self.assertEqual(hb_body['commit'], boot_body['commit'])

    def test_commit_rev_returns_none_without_raising_when_git_missing(self):
        import subprocess
        real_run = subprocess.run
        def boom(*a, **k): raise FileNotFoundError('git not installed')
        subprocess.run = boom
        try:
            self.assertIsNone(S.commit_rev())
        finally:
            subprocess.run = real_run


if __name__ == '__main__':
    unittest.main()
