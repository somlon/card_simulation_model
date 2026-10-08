"""매치 시뮬레이션 기록 · 비교 테스트 (nny_sim 폴더에서):  python -m unittest test_sim_report -v
- 결과 메타: 학습표 · 모델 파일 해시, 코드 커밋
- 라운드 기록: 판단 데이터 보유 수, 처리 실패 건수 → 요약 집계
- 처리 실패 회귀 검사: 규칙상 할 수 없는 행동을 시도해 실패하는 일이 없어야 한다(발동 뒤 상황이 바뀐 정당한 불발은 허용)
- compare: 같은 일정의 두 실행을 매치 단위로 짝지어 비교"""
import copy, json, os, tempfile, unittest
import match_sim as MS
import season as SE

NAMES = sorted(SE.load_decks())
# 엔진이 미리 막아야 하는 실패 — 표본에서 0이어야 한다. 「대상 없음」 · 「불발」은 발동 뒤 상황 변화로 생길 수 있어 제외
MUST_BE_ZERO = ('같은 이름 특수소환 불가', '발동 취소(코스트/대상)', '릴리스 불가')


class RecordTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        MS._init({'ai': 'table', 'policy': None, 'side': None})
        cls.records = MS._job(MS.schedule(NAMES, 2, seed=11))
        cls.summary = MS.summarize(cls.records)

    def test_round_records_carry_decisions_and_failures(self):
        r = next(r for r in self.records if r.get('type', 'round') == 'round')
        self.assertEqual(r['schema'], 2)
        self.assertEqual(len(r['decisions']), 2)
        for d in r['decisions']:
            self.assertLessEqual(d['with_data'], d['total'])
        self.assertIsInstance(r['failures'], dict)

    def test_summary_has_coverage_and_failures(self):
        for d, v in self.summary['decks'].items():
            c = v['decision_coverage']
            self.assertGreater(c['decisions'], 0)
            self.assertTrue(0 <= c['rate'] <= 100)
        self.assertIn('failures', self.summary)
        self.assertIn('판단 데이터 보유율', MS.to_markdown(self.summary))

    def test_no_rule_impossible_attempts(self):
        fails = self.summary['failures']
        for k in MUST_BE_ZERO:
            self.assertEqual(fails.get(k, {}).get('count', 0), 0, k)

    def test_old_records_without_new_fields_still_summarize(self):
        old = [dict(r) for r in self.records[:6]]
        for r in old:
            r.pop('decisions', None); r.pop('failures', None)
        s = MS.summarize(old)
        self.assertEqual(s['failures'], {})


class MetaTest(unittest.TestCase):
    def test_table_inputs_are_hashed(self):
        ins = MS.input_files({'ai': 'table', 'policy': None, 'side': None})
        self.assertEqual(len(ins['policy']['sha1']), 40)
        self.assertIn('side', ins)

    def test_missing_file_is_marked(self):
        self.assertTrue(MS.file_info('/없는/파일.json')['missing'])

    def test_code_version(self):
        v = MS.code_version()
        if v is not None:   # git이 없는 실행 환경이면 None
            self.assertIn('commit', v); self.assertIn('dirty', v)


class CompareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        MS._init({'ai': 'table', 'policy': None, 'side': None})
        cls.records = MS._job(MS.schedule(NAMES[:2], 3, seed=7))

    def write(self, d, records):
        os.makedirs(d, exist_ok=True)
        MS.write_records(os.path.join(d, 'rounds.jsonl.gz'), records)
        json.dump({'seed': 7, 'matches_per_pair': 3, 'decks_list': NAMES[:2]}, open(os.path.join(d, 'meta.json'), 'w'))

    def test_identical_runs_have_zero_difference(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = os.path.join(t, 'a'), os.path.join(t, 'b')
            self.write(a, self.records); self.write(b, self.records)
            c = MS.compare(a, b)
        self.assertTrue(c['same_schedule'])
        self.assertEqual(c['paired_matches'], 12)
        for r in c['decks'].values():
            self.assertEqual((r['diff'], r['changed_matches']), (0, 0))

    def test_flipped_match_is_detected(self):
        recs = copy.deepcopy(self.records)
        mid = next(r['match_id'] for r in recs if r.get('type', 'round') == 'round' and r['decks'][0] != r['decks'][1])
        for r in recs:
            if r.get('match_id') == mid: r['match_winner_seat'] = 1 - r['match_winner_seat']
        with tempfile.TemporaryDirectory() as t:
            a, b = os.path.join(t, 'a'), os.path.join(t, 'b')
            self.write(a, self.records); self.write(b, recs)
            c = MS.compare(a, b)
        changed = sum(r['changed_matches'] for r in c['decks'].values())
        self.assertEqual(changed, 2)                         # 그 매치의 두 자리
        self.assertEqual(sum(r['diff'] * r['n'] for r in c['decks'].values()), 0)   # 한쪽 +1, 다른 쪽 −1


if __name__ == '__main__':
    unittest.main()
