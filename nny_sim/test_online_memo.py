"""기능 v1⑤ 룰미스 메모 자동 스모크: python -m unittest test_online_memo -v
체인·효과 발동 로그 줄(프레임 번호)에 매치 중 클라이언트 로컬에 쌓인 메모를, 매치가 끝난 뒤
기존 replay_dict()/store.replays() 경로의 `memos` 필드로 묶어 저장하는 쪽(Store.add_memo)과
그 위의 HTTP 엔드포인트(/api/replay/memo)를 확인한다. 엔진·룰 레이어는 건드리지 않음 — 저장소 쪼가리만.
"""
import json, os, shutil, sys, tempfile, threading, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S
import session as SESS


def req(base, token, method, path, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                                headers={'X-NNY-Token': token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as ex: return ex.code, json.loads(ex.read())


def dummy_rec():
    return {'schema': 1, 'meta': {'names': ['A', 'B'], 'decks': ['스킬1', '스킬2'], 'winner': 0, 'status': 'done',
                                   'created': SESS.now(), 'rounds': []},
            'cards': {}, 'pool': {}, 'states': [], 'frames': [{'k': 'act', 'm': '발동: 더미'}]}


class MemoStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_memo_')
        self.store = SESS.Store(os.path.join(self.tmp, 'user'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_memo_appends_and_dedupes(self):
        rid = 'u:' + self.store.save_replay(dummy_rec())
        r = self.store.add_memo(rid, [{'i': 3, 'text': '체인 처리 순서가 이상함', 'who': 'A'}])
        self.assertTrue(r['ok']); self.assertEqual(r['added'], 1); self.assertEqual(r['total'], 1)
        r2 = self.store.add_memo(rid, [{'i': 3, 'text': '체인 처리 순서가 이상함', 'who': 'A'}])   # 같은 메모는 또 늘지 않음
        self.assertEqual(r2['added'], 0); self.assertEqual(r2['total'], 1)
        r3 = self.store.add_memo(rid, [{'i': 3, 'text': '같은 줄, 다른 메모', 'who': '관전'}])
        self.assertEqual(r3['added'], 1); self.assertEqual(r3['total'], 2)
        rec = self.store.replay(rid)
        self.assertEqual(len(rec['memos']), 2); self.assertEqual(rec['memos'][0]['i'], 3)
        reps = self.store.replays()
        self.assertEqual(next(x for x in reps if x['id'] == rid)['memos'], 2)   # index.json 에도 반영(1순위가 나중에 이걸로 찾음)

    def test_add_memo_rejects_library_and_missing(self):
        self.assertFalse(self.store.add_memo('l:somefile', [{'i': 0, 'text': 'x', 'who': ''}])['ok'])
        self.assertFalse(self.store.add_memo('u:없음', [{'i': 0, 'text': 'x', 'who': ''}])['ok'])

    def test_add_memo_ignores_blank_text(self):
        rid = 'u:' + self.store.save_replay(dummy_rec())
        r = self.store.add_memo(rid, [{'i': 0, 'text': '   ', 'who': ''}])
        self.assertEqual(r['added'], 0); self.assertEqual(r['total'], 0)

    def test_fresh_replay_has_zero_memos_in_listing(self):
        rid = 'u:' + self.store.save_replay(dummy_rec())
        reps = self.store.replays()
        self.assertEqual(next(x for x in reps if x['id'] == rid)['memos'], 0)


class MemoHttpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_memo_http_')
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

    def test_replay_memo_endpoint_roundtrips(self):
        rid = 'u:' + self.app.store.save_replay(dummy_rec())
        st, body = req(self.base, self.token, 'POST', '/api/replay/memo',
                        {'id': rid, 'memos': [{'i': 0, 'text': '효과 처리 순서 확인 필요', 'who': '관전'}]})
        self.assertEqual(st, 200, body); self.assertTrue(body['ok']); self.assertEqual(body['total'], 1)
        st, rec = req(self.base, self.token, 'GET', '/api/replay?id=' + rid)
        self.assertEqual(st, 200, rec)
        self.assertEqual(len(rec['memos']), 1); self.assertEqual(rec['memos'][0]['who'], '관전')
        st, reps = req(self.base, self.token, 'GET', '/api/replays')
        self.assertEqual(next(x for x in reps if x['id'] == rid)['memos'], 1)

    def test_replay_memo_endpoint_rejects_bad_id(self):
        st, body = req(self.base, self.token, 'POST', '/api/replay/memo', {'id': 'u:없음', 'memos': [{'i': 0, 'text': 'x'}]})
        self.assertEqual(st, 200, body); self.assertFalse(body['ok'])


if __name__ == '__main__':
    unittest.main()
