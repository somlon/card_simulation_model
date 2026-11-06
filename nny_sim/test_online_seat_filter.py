"""좌석별 기록 거르기(app/seatview, 2026-11-06 온라인 O2) 자동 스모크 (nny_sim 폴더에서): python -m unittest test_online_seat_filter -v

사람 대 사람 매치를 가짜 사람 둘(무작위 답)로 실제로 두고, 좌석0 · 좌석1 · 관전자가 poll 로 받은 기록에 비공개 정보가 새지 않는지 본다.
새지 않음 = 받은 카드 등록표의 이름 · 기록 줄의 「카드 이름」이 모두 (자기 카드 · 대전 중 공개 자리에 있었던 카드 · 「공개」 줄의 카드) 중 하나,
숨기는 좌석의 판단 줄에 내용이 없고, 숨기는 좌석의 패 · 뒷면 카드는 별칭(음수) 또는 공개된 적 있는 카드. 프레임 · 상태 수는 원본과 같다.
AI끼리 대전은 원본 그대로(관전 화면이 모두 공개하는 규칙과 같음).
"""
import json, os, random, re, shutil, sys, tempfile, threading, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S
import seatview as SV

PLAY_SECONDS = 150   # 매치 하나를 두는 시간 상한(넘으면 그만두고 거기까지 검사)
NAME_RE = re.compile(r'「([^」]+)」')


class SeatFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='nny_seat_')
        cards = os.path.join(cls.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        paths = {'sim': os.path.abspath('.'), 'split': os.path.join(cls.tmp, 'split'), 'cards': cards,
                 'library': os.path.join(cls.tmp, 'library'), 'user': os.path.join(cls.tmp, 'user'),
                 'static': os.path.abspath('app/static'), 'viewer': os.path.abspath('viewer')}
        cls.app, cls.srv = S.serve(paths, port=0, host='127.0.0.1')
        ids = [d['id'] for d in cls.app.store.deck_list() if d['kind'] == 'official' and d['valid']]
        cls.ids = ids
        r = cls.app.start_match({'deck': ids[0], 'ai_deck': ids[1], 'humans': [True, True], 'learn': False, 'first': 'me', 'seed': 5})
        cls.m = m = cls.app.lives[r['id']]
        rng = random.Random(1)
        views = {0: {'f': 0, 's': 0, 'c': 0, 'frames': [], 'states': [], 'cards': {}},
                 1: {'f': 0, 's': 0, 'c': 0, 'frames': [], 'states': [], 'cards': {}},
                 'spec': {'f': 0, 's': 0, 'c': 0, 'frames': [], 'states': [], 'cards': {}}}
        cls.pendings = []
        t0 = time.time()

        def pull(v):
            w = views[v]
            if v == 'spec': res = m.poll(None, None, w['f'], w['s'], w['c'], spectate=True)
            else: res = m.poll(v, m.keys[v], w['f'], w['s'], w['c'])
            w['frames'] += res['frames']; w['states'] += res['states']; w['cards'].update(res['cards'])
            w['f'] += len(res['frames']); w['s'] += len(res['states']); w['c'] += len(res['cards'])
            return res
        while m.status in ('starting', 'running') and time.time() - t0 < PLAY_SECONDS:
            for seat in (0, 1):
                res = pull(seat); pd = res['pending']
                if pd:
                    cls.pendings.append((seat, pd))
                    m.answer(pd['id'], 0 if pd['kind'] == 'side' else rng.randrange(len(pd['opts'])), seat, m.keys[seat])
            pull('spec'); time.sleep(0.002)
        if m.status in ('starting', 'running'): m.abort(); m.thread.join(10)
        for v in views: pull(v)
        cls.views = views

    @classmethod
    def tearDownClass(cls):
        for x in list(cls.app.lives.values()): x.abort()
        cls.srv.server_close(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def allowed_names(self, hidden):
        """보는 사람이 알 수 있는 이름: 보이는 좌석의 카드 + 원본 상태에서 공개 자리에 있었던 카드 + 「공개」 줄의 카드"""
        rec = self.m.rec; out = {nm for nm, owner in rec.cards.values() if owner not in hidden}
        sv = SV.SeatView(rec, self.m.names, hidden)
        for st in rec.states:
            present, private = sv._scan(st)
            out |= {rec.cards[u][0] for u in present - private}
        for fr in rec.frames:
            if ' 공개' in fr['m']: out |= set(NAME_RE.findall(fr['m']))
        return out

    def check_view(self, key, hidden):
        w = self.views[key]; rec = self.m.rec
        self.assertEqual(len(w['frames']), len(rec.frames)); self.assertEqual(len(w['states']), len(rec.states))
        ok = self.allowed_names(hidden) | {'?', ''}
        reg = {int(u): v for u, v in w['cards'].items()}
        leaked = {v[0] for u, v in reg.items() if u >= 0 and v[0] not in ok}
        self.assertFalse(leaked, f'{key}: 등록표에 비공개 카드 이름 {sorted(leaked)[:5]}')
        self.assertTrue(all(v[0] == '' for u, v in reg.items() if u < 0), f'{key}: 별칭 등록표에 이름')
        cardnames = {nm for nm, _ in rec.cards.values()}   # 이 대전의 카드 이름만 센다(효과 문장의 따옴표 · 카드군 이름 「망령」 등은 빼고)
        said = set()
        for fr in w['frames']: said |= set(NAME_RE.findall(fr['m'])) & cardnames
        self.assertFalse(said - ok, f'{key}: 기록 줄에 비공개 카드 이름 {sorted(said - ok)[:5]}')
        names = self.m.names
        for fr in w['frames']:
            if fr['k'] == 'decision' and any(fr['m'].startswith(f'판단[{names[s]}]') for s in hidden):
                self.assertEqual(set(fr.get('d') or {}) - {'p'}, set(), f'{key}: 숨기는 좌석 판단 내용 {fr}')
        known = {u for u, v in reg.items() if u >= 0}
        for st in w['states']:
            for s in hidden:
                for u in st['P'][s]['hand']: self.assertTrue(u < 0 or u in known)
        return sum(1 for u in reg if u < 0), sum(fr['m'].count('「?」') for fr in w['frames'])

    def test_match_was_played(self):
        self.assertGreater(len(self.m.rec.frames), 50)
        self.assertTrue(self.pendings)

    def test_seat0_sees_no_private_info_of_seat1(self):
        aliases, masked = self.check_view(0, {1})
        self.assertGreater(aliases + masked, 0, '좌석0 에게 숨긴 것이 하나도 없다 — 거르기가 돌지 않았다')

    def test_seat1_sees_no_private_info_of_seat0(self):
        self.check_view(1, {0})

    def test_spectator_sees_no_private_info_of_both(self):
        self.check_view('spec', {0, 1})

    def test_own_hand_is_real(self):
        w = self.views[0]; reg = {int(u): v for u, v in w['cards'].items()}
        for st in w['states']:
            for u in st['P'][0]['hand']: self.assertGreaterEqual(u, 0); self.assertTrue(reg[u][0])

    def test_pending_marks_use_viewer_ids(self):
        for seat, pd in self.pendings:
            for o in pd.get('opts', []):
                for u in o.get('u') or []: self.assertIsInstance(u, int)

    def test_ai_vs_ai_is_unfiltered(self):
        r = self.app.start_match({'deck': self.ids[0], 'ai_deck': self.ids[1], 'humans': [False, False], 'learn': False, 'first': 'me', 'seed': 2})
        m = self.app.lives[r['id']]; m.thread.join(PLAY_SECONDS)
        res = m.poll(None, None, 0, 0, 0, spectate=True)
        self.assertEqual(len(res['cards']), len(m.rec.cards))
        self.assertEqual([fr['m'] for fr in res['frames']], [fr['m'] for fr in m.rec.export_frames()])


if __name__ == '__main__':
    unittest.main()
