"""AI 실력 트랙 — 학습 탭에 /api/analysis/decisions 리포트를 보여주는 화면 조각 자동 스모크
(nny_sim 폴더에서): python -m unittest test_online_decisions_ui -v
test_online_theme.py와 같은 패턴으로 서버를 띄워 index.html·app.js에 새 UI(버튼·출력 영역·
호출부)가 실제로 내려오는지, 그리고 그 엔드포인트를 실제로 호출했을 때 Store.decision_report()
(이미 test_decision_report.py로 검증됨)와 연결돼 응답이 오는지까지 확인한다.
"""
import os, shutil, sys, tempfile, threading, unittest, urllib.request, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S


class OnlineDecisionsUiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_decisions_ui_')
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

    def _get(self, path):
        r = urllib.request.Request(self.base + path, headers={'X-NNY-Token': self.token})
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, resp.read().decode('utf-8')

    def test_index_html_has_decisions_panel(self):
        st, html = self._get('/')
        self.assertEqual(st, 200)
        self.assertIn('id="l-decisions-refresh"', html)
        self.assertIn('id="l-decisions"', html)

    def test_app_js_calls_decisions_endpoint_on_learn_tab(self):
        st, js = self._get('/app.js')
        self.assertEqual(st, 200)
        self.assertIn('refreshDecisions', js)
        self.assertIn("api('analysis/decisions')", js)

    def test_api_endpoint_reachable_and_empty_without_replays(self):
        st, body = self._get('/api/analysis/decisions')
        self.assertEqual(st, 200)
        j = json.loads(body)
        self.assertIn('없다', j['report'])


if __name__ == '__main__':
    unittest.main()
