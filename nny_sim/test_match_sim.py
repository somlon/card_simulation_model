"""match_sim 테스트 (nny_sim 폴더에서):  python -m unittest test_match_sim -v"""
import json, os, tempfile, unittest
import match_sim as MS
import season as SE

NAMES = sorted(SE.load_decks())


class FactorTest(unittest.TestCase):
    def test_damage_kind(self):
        self.assertEqual(MS.damage_kind('솔루나 시아 직접공격'), '직접공격')
        self.assertEqual(MS.damage_kind('전투'), '전투')
        self.assertEqual(MS.damage_kind('전투(수비 반사)'), '전투')
        self.assertEqual(MS.damage_kind('공유 존 마커'), '공유 존 마커')
        self.assertEqual(MS.damage_kind('자해 (홀로 선 달)'), '자해')
        self.assertEqual(MS.damage_kind('세레모니'), '효과')


class AttributionTest(unittest.TestCase):
    def test_self_and_marker_damage_not_credited_to_opponent(self):
        class P_:
            hp = 0; hand = []; main = []; upper = []; grave = []; banish = []
        class G_:
            p = [P_(), P_()]; opening = [[], []]
            def monsters(self, i): return []
            def spells(self, i): return []
        log = [{'m': 'A 1000 대미지 (자해 (홀로 선 달)) → HP 4000'}, {'m': 'A 500 대미지 (공유 존 마커) → HP 3500'},
               {'m': 'A 1200 대미지 (어떤 몬스터 직접공격) → HP 2300'}, {'m': 'B 800 대미지 (전투) → HP 4200'}]
        a = MS._player_block(G_(), 0, 'A', log); b = MS._player_block(G_(), 1, 'B', log)
        self.assertEqual(a['damage_taken'], {'자해': 1000, '공유 존 마커': 500, '직접공격': 1200})
        self.assertEqual(b['damage_dealt'], {'직접공격': 1200})            # 자해 · 마커는 B가 준 대미지가 아님
        self.assertEqual(a['damage_dealt'], {'전투': 800})


class NoLearningTest(unittest.TestCase):
    def test_heuristic_run_does_not_touch_breeding_table(self):
        import ai as A, copy
        before = copy.deepcopy(A.BREEDING.t)
        MS._init({'ai': 'heuristic'})
        MS._job(MS.schedule(['번성충-기생', '번성충-대발생'], 2, seed=3))
        self.assertEqual(A.BREEDING.t, before)

    def test_match_error_is_recorded_and_run_continues(self):
        import match as M
        MS._init({'ai': 'table'})
        orig = M.play_match
        def boom(*a, **k): raise KeyError('카드 구현 오류 흉내')
        M.play_match = boom
        try:
            recs = MS._job([(NAMES[0], NAMES[1], 0, 1, 0), (NAMES[1], NAMES[0], 1, 2, 1)])
        finally:
            M.play_match = orig
        self.assertEqual([r['type'] for r in recs], ['error_match', 'error_match'])
        s = MS.summarize(recs); self.assertEqual((s['matches'], s['error_matches']), (0, 2))


class StalledTest(unittest.TestCase):
    def test_stalled_matches_are_counted_not_scored(self):
        r = {'type': 'stalled_match', 'match_id': 99, 'decks': [NAMES[0], NAMES[1]], 'seed': 1, 'ai': 'table', 'first_seat': 0, 'rounds_done': 1}
        s = MS.summarize([r])
        self.assertEqual((s['matches'], s['stalled_matches']), (0, 1))


class MatchSimTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        MS._init({'ai': 'table', 'policy': None, 'side': None})
        names = NAMES[:3]                                   # 3개 덱 → 순서쌍 9개(미러전 3개 포함)
        cls.sched = MS.schedule(names, 2, seed=5)
        cls.records = MS._job(cls.sched)
        cls.rounds = [r for r in cls.records if r['type'] == 'round']
        cls.stalled = sum(r['type'] == 'stalled_match' for r in cls.records)
        cls.summary = MS.summarize(cls.records)

    def test_schedule_covers_all_ordered_pairs_with_mirrors(self):
        pairs = {(a, b) for a, b, *_ in self.sched}
        self.assertEqual(len(pairs), 9)
        self.assertTrue(all((n, n) in pairs for n in NAMES[:3]))

    def test_match_structure(self):
        by = {}
        for r in self.rounds:
            by.setdefault(r['match_id'], []).append(r)
        self.assertEqual(len(by) + self.stalled, len(self.sched))
        for mid, rs in by.items():
            rs.sort(key=lambda r: r['round'])
            self.assertIn(len(rs), (2, 3))
            self.assertEqual([r['round'] for r in rs], list(range(1, len(rs) + 1)))
            wins = [sum(r['winner_seat'] == s for r in rs) for s in (0, 1)]
            self.assertEqual(max(wins), 2)
            self.assertEqual(rs[0]['match_winner_seat'], wins.index(2))
            sch = next(x for x in self.sched if x[4] == mid)
            self.assertEqual(rs[0]['first_seat'], sch[2])           # 1라운드 선공 = 일정
            for prev, cur in zip(rs, rs[1:]):                       # 2 · 3라운드: 직전 패자가 정함(기본 지침: 선공)
                self.assertEqual(cur['first_seat'], 1 - prev['winner_seat'])

    def test_records_have_factors(self):
        r = self.rounds[0]
        for k in ('reason', 'turns', 'tags', 'players', 'final_blow', 'side_swaps_before', 'winner_min_hp_lead'):
            self.assertIn(k, r)
        self.assertEqual(len(r['players']), 2)
        for p in r['players']:
            for k in ('hp', 'damage_dealt', 'damage_taken', 'cards_used', 'mulligan', 'opening_hand', 'first', 'skill'):
                self.assertIn(k, p)
        hp0 = [r for r in self.rounds if 'HP 0' in r['reason']]
        self.assertTrue(hp0 and all(r['final_blow'] for r in hp0))
        # 결정타 대미지는 패자가 받은 대미지에 들어 있다
        for r in hp0:
            loser = r['players'][1 - r['winner_seat']]
            self.assertGreaterEqual(sum(loser['damage_taken'].values()), r['final_blow']['amount'])
            self.assertLessEqual(loser['hp'], 0)

    def test_mirror_counts_exactly_half(self):
        mirror = [r for r in self.rounds if r['mirror']]
        self.assertTrue(mirror)
        sub = MS.summarize(mirror)
        for d, v in sub['decks'].items():
            self.assertEqual(v['match']['rate'], 50.0); self.assertEqual(v['round_overall']['rate'], 50.0)

    def test_summary_consistency(self):
        s = self.summary
        n_match_seats = sum(v['match']['games'] for v in s['decks'].values())
        self.assertEqual(n_match_seats, 2 * s['matches'])
        for d, v in s['decks'].items():
            per_round = sum(x['games'] for x in v['rounds'].values())
            self.assertEqual(per_round, v['round_overall']['games'])
            self.assertEqual(v['in_ideal_range'], 49.0 <= v['match']['rate'] <= 51.0)

    def test_summary_recomputes_from_saved_records(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'rounds.jsonl.gz')
            MS.write_records(p, self.records)
            again = MS.summarize(MS.read_records(p))
        self.assertEqual(json.dumps(again, sort_keys=True, ensure_ascii=False), json.dumps(self.summary, sort_keys=True, ensure_ascii=False))

    def test_markdown_renders(self):
        md = MS.to_markdown(self.summary)
        self.assertIn('덱별 종합 승률', md); self.assertIn('1R 선공', md)


if __name__ == '__main__':
    unittest.main()
