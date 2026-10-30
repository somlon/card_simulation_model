"""기능 v1 추가 요구 — 화면 테마 3종(뉴네오·화이트·블랙) 자동 스모크 (nny_sim 폴더에서):
python -m unittest test_online_theme -v
서버가 내려주는 index.html에 테마 선택 셀렉트(3종 전부)가 실제로 있는지, app.css에 화이트·블랙
각각의 재정의 블록이 실제로 있는지 확인. 전환 자체는 순수 클라이언트(JS+localStorage)라 이
스모크는 "서버가 셀렉트·CSS를 올바르게 내려주는지"까지만 — 전환 동작은 수동 브라우저 확인으로 보완.
"""
import os, shutil, sys, tempfile, threading, unittest, urllib.request, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S


class OnlineThemeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_theme_')
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

    def test_index_html_has_theme_select_with_all_three(self):
        st, html = self._get('/')
        self.assertEqual(st, 200)
        self.assertIn('id="theme-select"', html)
        for v in ('neo', 'white', 'black'):
            self.assertIn(f'value="{v}"', html)

    def test_app_css_defines_white_and_black_overrides(self):
        st, css = self._get('/app.css')
        self.assertEqual(st, 200)
        self.assertIn(':root[data-theme="white"]', css)
        self.assertIn(':root[data-theme="black"]', css)
        self.assertIn('--headerbg', css)

    def test_app_js_applies_theme_from_storage_and_defaults_to_neo(self):
        st, js = self._get('/app.js')
        self.assertEqual(st, 200)
        self.assertIn("localStorage.getItem('nny-theme')", js)
        self.assertIn("savedTheme = 'neo'", js)


if __name__ == '__main__':
    unittest.main()
