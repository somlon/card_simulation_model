"""학습하는 휴리스틱 AI(오프라인판 app/main #103 이식, 2026-11-06 온라인 O4) 자동 스모크 (nny_sim 폴더에서):
python -m unittest test_online_heuristic_learning -v

'heuristic' 자리는 전술(발동 · 대응 · 공격 등)은 ai.HeuristicAI 규칙, 전략 판단(시작 패 배분 · 재배분 · 멀리건 · 드로우 덱 · 선후공 · 번식지 ·
같은 타이밍 체인 순서)만 학습표로 고르고 학습한다 — 휴리스틱 AI끼리 학습을 켜고 두면 학습 기록의 판단이 모두 전략 판단이고, 전술 메서드는 규칙 그대로.
"""
import json, os, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S
import session as SS
import tables as T
from ai import HeuristicAI

STRATEGY = ('시작 패 배분', '시작 패 재배분', '멀리건:', '드로우 덱', '번식지', '선후공 선택', '체인 순서')   # 학습표 판단 이름의 앞부분
WAIT = 150


class HeuristicLearningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='nny_heur_')
        cards = os.path.join(cls.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        paths = {'sim': os.path.abspath('.'), 'split': os.path.join(cls.tmp, 'split'), 'cards': cards,
                 'library': os.path.join(cls.tmp, 'library'), 'user': os.path.join(cls.tmp, 'user'),
                 'static': os.path.abspath('app/static'), 'viewer': os.path.abspath('viewer')}
        cls.app, cls.srv = S.serve(paths, port=0, host='127.0.0.1')
        ids = [d['id'] for d in cls.app.store.deck_list() if d['kind'] == 'official' and d['valid']]
        cls.ms = []
        for i in range(2):
            r = cls.app.start_match({'deck': ids[i], 'ai_deck': ids[i + 1], 'humans': [False, False], 'learn': True, 'first': 'me',
                                     'seed': 30 + i, 'ai0_kind': 'heuristic', 'ai_kind': 'heuristic'})
            m = cls.app.lives[r['id']]; m.thread.join(WAIT); cls.ms.append(m)

    @classmethod
    def tearDownClass(cls):
        for x in list(cls.app.lives.values()): x.abort()
        cls.srv.server_close(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_tactics_are_rules(self):
        for n in SS.LearningHeuristicAI.TACTICS:
            self.assertIs(getattr(SS.LearningHeuristicAI, n), getattr(HeuristicAI, n), n)
        self.assertIn('order_triggers', SS.LearningHeuristicAI.STRATEGY)

    def test_learning_records_have_only_strategy_decisions(self):
        recs = [r for r in T.read_log(self.app.store.ai_log_path) if r.get('match') in {m.match_uid for m in self.ms}]
        self.assertEqual(len(recs), 2, [m.status for m in self.ms])
        keys = [k1.split('|')[1] for r in recs for k1, _, _ in r['updates']]
        self.assertTrue(keys)
        self.assertTrue(all(k.startswith(STRATEGY) or '라운드 선후공' in k for k in keys), sorted(set(keys))[:10])
        self.assertTrue(all(r['ai_kinds'] == ['heuristic', 'heuristic'] for r in recs))


if __name__ == '__main__':
    unittest.main()
