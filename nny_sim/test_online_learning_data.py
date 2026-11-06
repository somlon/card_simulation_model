"""학습 데이터(오프라인판 app/main #102 · #113 이식 — 학습표만, 2026-11-06 온라인 O3) 자동 스모크 (nny_sim 폴더에서):
python -m unittest test_online_learning_data -v

① 사람 vs AI(가짜 사람) 는 human_games.jsonl(출처 human) · AI끼리 관전은 ai_games.jsonl(출처 ai)에 매치 키 · 자리별 AI 종류와 함께 남는다
② 기록을 다시 적용할 때 출처별 가중치(사람 3 : AI 1) ③ 매치 · 판단 단위로 빼면 학습표 다시 적용 · 내보내기 · 통계에서 빠지고 다시 넣을 수 있다
④ 빼고 넣기는 서버 컴퓨터(로컬) · 방장만 — 다른 접속은 거절(공유 서버). 녹화도 「학습 데이터로 남기기」면 AI끼리 기록.
"""
import json, os, random, shutil, sys, tempfile, threading, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S
import tables as T
import learndata as LD

WAIT = 150   # 초 — 매치 하나가 끝나기를 기다리는 시간


class LearningDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='nny_learn_')
        cards = os.path.join(cls.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        cls.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(cls.tmp, 'split'), 'cards': cards,
                     'library': os.path.join(cls.tmp, 'library'), 'user': os.path.join(cls.tmp, 'user'),
                     'static': os.path.abspath('app/static'), 'viewer': os.path.abspath('viewer')}
        cls.app, cls.srv = S.serve(cls.paths, port=0, host='127.0.0.1')
        cls.ids = [d['id'] for d in cls.app.store.deck_list() if d['kind'] == 'official' and d['valid']]
        a, b = cls.ids[0], cls.ids[1]
        # 사람 vs AI — 가짜 사람(무작위 답)
        r = cls.app.start_match({'deck': a, 'ai_deck': b, 'humans': [True, False], 'learn': True, 'first': 'me', 'seed': 3})
        m = cls.app.lives[r['id']]; rng = random.Random(2); t0 = time.time()
        while m.status in ('starting', 'running') and time.time() - t0 < WAIT:
            pd = m.bridges[0].pending
            if pd: m.answer(pd['id'], 0 if pd['kind'] == 'side' else rng.randrange(len(pd['opts'])), 0, m.keys[0])
            time.sleep(0.002)
        m.thread.join(WAIT); cls.hm = m
        # AI끼리 관전(P1 휴리스틱 · P2 학습표)
        r = cls.app.start_match({'deck': a, 'ai_deck': b, 'humans': [False, False], 'learn': True, 'first': 'me', 'seed': 4,
                                 'ai0_kind': 'heuristic', 'ai_kind': 'table'})
        cls.am = cls.app.lives[r['id']]; cls.am.thread.join(WAIT)

    @classmethod
    def tearDownClass(cls):
        for x in list(cls.app.lives.values()): x.abort()
        cls.srv.server_close(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def recs(self, path): return T.read_log(path)

    def test_records_by_source(self):
        st = self.app.store
        h = [r for r in self.recs(st.log_path) if r.get('match') == self.hm.match_uid]
        a = [r for r in self.recs(st.ai_log_path) if r.get('match') == self.am.match_uid]   # 매치 키로 — 다른 시험의 녹화 기록이 뒤에 붙을 수 있다
        self.assertTrue(h and a, (len(h), len(a)))
        self.assertEqual(h[0]['source'], 'human'); self.assertEqual(h[0]['ai_kinds'], ['human', 'table'])
        self.assertEqual(a[0]['source'], 'ai'); self.assertEqual(a[0]['ai_kinds'], ['heuristic', 'table'])
        items = {it['key']: it for it in st.learning_items()}
        self.assertEqual(items[self.hm.match_uid]['weight'], LD.HUMAN_WEIGHT); self.assertEqual(items[self.am.match_uid]['weight'], LD.AI_WEIGHT)

    def test_weighted_reapply(self):
        st = self.app.store; h = next(r for r in self.recs(st.log_path) if r.get('match') == self.hm.match_uid)
        decks = sorted({k1.split(' vs ')[0] for k1, _, _ in h['updates']} | {h['decks'][0], h['decks'][1]})
        t = T.matchup_table(self.paths['split'], decks, logs=[st.log_path], exclude=LD.Exclusion())
        k1 = h['updates'][0][0]
        n = sum(1 for u in h['updates'] if u[0] == k1)
        self.assertAlmostEqual(t.L1[k1][1], LD.HUMAN_WEIGHT * n)   # 사람 대전 기록은 갱신마다 가중치 3

    def test_exclude_match_and_parts(self):
        st = self.app.store; key = self.am.match_uid
        before = st.learning_stats()['updates']
        n_ai = len(next(r for r in self.recs(st.ai_log_path) if r.get('match') == key)['updates'])
        st.set_excluded([key], True)
        self.assertNotIn(key, [LD.record_key(r) for r in st.learning_records()])
        self.assertEqual(st.learning_stats()['updates'], before - n_ai)
        out = st.export_learning(); self.assertNotIn(key, open(out, encoding='utf-8').read())
        st.set_excluded([key], False)
        self.assertEqual(st.learning_stats()['updates'], before)
        # 판단 단위: 사람 대전의 첫 판단 2개를 빼면 다시 적용에서 빠진다
        hk = self.hm.match_uid
        self.assertEqual(st.set_parts(hk, [0, 1], (), True), 2)
        d = st.decisions(hk); self.assertEqual([x['excluded'] for x in d['table'][:3]], [True, True, False])
        rec = next(r for r in st.learning_records() if LD.record_key(r) == hk)
        self.assertEqual(len(rec['updates']), len(d['table']) - 2)
        st.set_parts(hk, [0, 1], (), False)
        self.assertFalse(any(x['excluded'] for x in st.decisions(hk)['table']))
        # 글로 한꺼번에: 「시작 패」가 들어간 판단
        n = st.set_decision_text([hk, key], '시작 패', True); self.assertGreater(n, 0)
        st.set_decision_text([hk, key], '시작 패', False)

    def test_curation_only_local_or_host(self):
        app = self.app; key = self.am.match_uid
        with self.assertRaises(ValueError): app.route('POST', '/api/learning/exclude', {}, {'keys': [key], 'excluded': True}, ip='25.0.0.9')
        self.assertFalse(app.route('GET', '/api/learning', {}, {}, ip='25.0.0.9')['can_curate'])
        self.assertTrue(app.route('GET', '/api/learning', {}, {}, ip='127.0.0.1')['can_curate'])
        app.room_join('25.0.0.9', '방장', 'spectator')   # 방에 먼저 들어온 사람 = 방장
        try:
            r = app.route('POST', '/api/learning/exclude', {}, {'keys': [key], 'excluded': True}, ip='25.0.0.9'); self.assertTrue(r['ok'])
            app.route('POST', '/api/learning/exclude', {}, {'keys': [key], 'excluded': False}, ip='25.0.0.9')
        finally: app.room_leave('25.0.0.9')
        self.assertTrue(app.route('GET', '/api/learning/items', {}, {}, ip='25.0.0.9'))   # 보기는 누구나

    def test_record_job_learn_option(self):
        st = self.app.store; n0 = len(self.recs(st.ai_log_path))
        job = self.app.start_record({'pairs': [[self.ids[0], self.ids[1]]], 'matches': 1, 'seed': 9, 'learn': True})
        j = self.app.jobs[job['id']]; t0 = time.time()
        while j.status == 'running' and time.time() - t0 < WAIT: time.sleep(0.1)
        self.assertEqual(len(self.recs(st.ai_log_path)), n0 + 1)
        job = self.app.start_record({'pairs': [[self.ids[0], self.ids[1]]], 'matches': 1, 'seed': 10})   # 기본: 남기지 않음
        j = self.app.jobs[job['id']]; t0 = time.time()
        while j.status == 'running' and time.time() - t0 < WAIT: time.sleep(0.1)
        self.assertEqual(len(self.recs(st.ai_log_path)), n0 + 1)


if __name__ == '__main__':
    unittest.main()
