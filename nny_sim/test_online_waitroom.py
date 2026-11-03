"""대기실(방) 개편 자동 스모크 (2026-11-03, 장인준 요청 — 화면을 메뉴로 나누고 방에서 플레이어/관전·시작·나가기):
python -m unittest test_online_waitroom -v

App 레벨만 본다(서버 기동 없음) — 방장(먼저 들어온 사람)만 시작 · 내 덱 고르기(room_deck) · 방식별 시작 조건
(사람 대 사람 = 플레이어 둘 다 덱 고름 · 사람 vs AI = 플레이어 하나 + AI 덱 · AI vs AI = 방 전체 관전) ·
시작 뒤 좌석 자동 귀속(my_match). 엔진·룰 레이어는 건드리지 않음(app 레이어만).
"""
import json, os, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S


class WaitRoomTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_lobby_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': os.path.join(self.tmp, 'user'), 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}
        self.app = S.App(self.paths)
        ids = [d['id'] for d in self.app.store.deck_list() if d['kind'] == 'official' and d['valid']]
        self.assertGreaterEqual(len(ids), 2)
        self.d1, self.d2 = ids[0], ids[1]

    def tearDown(self):
        if self.app.live: self.app.live.abort()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_host_is_first_in_and_only_host_starts(self):
        self.app.room_join('25.0.0.11', '갑', 'player', self.d1)
        self.app.room_join('25.0.0.12', '을', 'player', self.d2)
        st = self.app.room_status()
        self.assertEqual(st['host'], '갑')
        self.assertEqual([m['host'] for m in st['members']], [True, False])
        with self.assertRaises(ValueError): self.app.room_start('25.0.0.12', {'mode': 'pvp'})
        self.app.room_leave('25.0.0.11')
        self.assertEqual(self.app.room_status()['host'], '을')   # 방장이 나가면 다음 사람

    def test_room_deck_requires_membership_and_valid_deck(self):
        with self.assertRaises(ValueError): self.app.room_deck('25.0.0.11', self.d1)
        self.app.room_join('25.0.0.11', '갑', 'spectator')
        with self.assertRaises(ValueError): self.app.room_deck('25.0.0.11', 'o:없는덱')
        st = self.app.room_deck('25.0.0.11', self.d1)
        me = st['members'][0]
        self.assertEqual(me['deck'], self.d1); self.assertTrue(me['deck_label'])
        self.app.room_join('25.0.0.11', '갑', 'player')   # 역할만 바꿔도 덱은 남는다
        self.assertEqual(self.app.room_status()['members'][0]['deck'], self.d1)

    def test_pvp_needs_two_seated_players_with_decks(self):
        self.app.room_join('25.0.0.11', '갑', 'player', self.d1)
        with self.assertRaises(ValueError): self.app.room_start('25.0.0.11', {'mode': 'pvp'})
        self.app.room_join('25.0.0.12', '을', 'player')
        with self.assertRaises(ValueError): self.app.room_start('25.0.0.11', {'mode': 'pvp'})   # 을이 덱 안 고름
        self.app.room_deck('25.0.0.12', self.d2)
        r = self.app.room_start('25.0.0.11', {'mode': 'pvp', 'learn': False})
        self.assertEqual(r['mode'], 'pvp'); self.assertEqual(r['my_match']['seat'], 0)
        self.assertEqual(self.app.my_match('25.0.0.12')['seat'], 1)
        self.assertEqual(sorted(r['seats']), [0, 1])
        with self.assertRaises(ValueError): self.app.room_start('25.0.0.11', {'mode': 'pvp'})   # 이미 진행 중

    def test_human_vs_ai_from_lobby(self):
        self.app.room_join('25.0.0.11', '갑', 'player', self.d1)
        self.app.room_join('25.0.0.13', '병', 'spectator')
        with self.assertRaises(ValueError): self.app.room_start('25.0.0.11', {'mode': 'ai'})   # AI 덱 없음
        r = self.app.room_start('25.0.0.11', {'mode': 'ai', 'ai_deck': self.d2, 'learn': False})
        self.assertEqual(r['my_match']['seat'], 0)
        self.assertIsNone(self.app.my_match('25.0.0.13'))        # 관전자는 좌석이 없다
        self.assertEqual(list(self.app.live.humans), [True, False])
        self.assertTrue(self.app.live_info())                    # 관전 화면이 따라붙을 정보는 있다

    def test_ai_vs_ai_everyone_spectates(self):
        self.app.room_join('25.0.0.11', '갑', 'player', self.d1)
        r = self.app.room_start('25.0.0.11', {'mode': 'aivai', 'deck': self.d1, 'ai_deck': self.d2})
        self.assertIsNone(r['my_match'])
        self.assertEqual(list(self.app.live.humans), [False, False])
        self.assertEqual(self.app.live_ips, {})

    def test_keyless_shortcut_only_for_match_owner(self):
        """사람vsAI 의 키 없는 poll/answer 지름길은 시작한 ip 에게만 — 다른 ip 는 관전으로 떨어지고 answer 는 거부."""
        r = self.app.start_match({'deck': self.d1, 'ai_deck': self.d2, 'humans': [True, False], 'learn': False}, ip='25.0.0.11')
        mid = r['id']
        p = self.app.route('GET', '/api/match/poll', {'id': [mid]}, {}, ip='25.0.0.11')
        self.assertEqual(p['seat'], 0)                                          # 시작한 사람: 키 없이도 자기 자리
        p = self.app.route('GET', '/api/match/poll', {'id': [mid]}, {}, ip='25.0.0.99')
        self.assertIsNone(p['seat']); self.assertIsNone(p['pending'])          # 남: 관전으로만
        self.assertFalse(self.app.route('POST', '/api/match/answer', {}, {'rid': 0, 'idx': 0}, ip='25.0.0.99')['ok'])
        p = self.app.route('GET', '/api/match/poll', {'id': [mid], 'seat': ['0'], 'key': [r['seats'][0]]}, {}, ip='25.0.0.99')
        self.assertEqual(p['seat'], 0)                                          # 키를 들고 오면 기존대로

    def test_heartbeat_tells_me_my_ip(self):
        hb = self.app.heartbeat('25.0.0.11')
        self.assertEqual(hb['me_ip'], '25.0.0.11')
        self.assertIn('live', hb['room'])


if __name__ == '__main__':
    unittest.main()
