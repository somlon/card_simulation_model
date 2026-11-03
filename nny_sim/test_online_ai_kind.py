"""온라인판 AI 종류 선택(ai_kind) 자동 스모크 (nny_sim 폴더에서): python -m unittest test_online_ai_kind -v
디스코드 요청(jdiejd7788/세창, 2026-11-03): 오프라인판엔 있던 AI 모델 선택이 온라인판엔 없었다 — 이 서버 환경엔
numpy가 없어 신경망(nn) AI는 빼고, 기존 학습표(table) AI에 규칙 기반(heuristic, ai.HeuristicAI) 선택지를 더한다.
가짜 HTTP 클라이언트로 AI vs AI 매치를 heuristic AI 종류로 실제로 끝까지 돌려 본다 + 잘못된 AI 종류는 400으로 거부되는지 확인.
"""
import json, os, shutil, sys, tempfile, threading, time, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S
import session as SS


def req(base, token, method, path, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                                headers={'X-NNY-Token': token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as ex: return ex.code, json.loads(ex.read())


class AiKindSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_aikind_')
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

    def test_boot_lists_ai_kinds(self):
        st, boot = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 200)
        self.assertEqual(set(boot['ai_kinds']), SS.AI_KINDS)

    def test_heuristic_ai_vs_ai_match_completes(self):
        d1, d2 = self.decks()
        st, start = req(self.base, self.token, 'POST', '/api/match/start',
                        {'deck': d1, 'ai_deck': d2, 'humans': [False, False], 'learn': False, 'first': 'me',
                         'ai_kind': 'heuristic'})
        self.assertEqual(st, 200, start)
        mid = start['id']
        for _ in range(200):
            st, poll = req(self.base, self.token, 'GET', f'/api/match/poll?id={mid}')
            self.assertEqual(st, 200)
            if poll.get('status') in ('done', 'aborted', 'error', 'stalled'): break
            time.sleep(0.05)
        self.assertEqual(poll.get('status'), 'done', poll)

    def test_unknown_ai_kind_rejected(self):
        d1, d2 = self.decks()
        st, err = req(self.base, self.token, 'POST', '/api/match/start',
                      {'deck': d1, 'ai_deck': d2, 'humans': [False, False], 'learn': False, 'first': 'me',
                       'ai_kind': '없는종류'})
        self.assertEqual(st, 400)
        self.assertIn('AI', err['error'])


if __name__ == '__main__':
    unittest.main()
