"""종류별 색인(사용자 지시 2026-10-28) 테스트 (nny_sim 폴더에서):  python -m unittest test_kind_index -v
[지속] 훅을 가진 카드를 판에서 한 번 모아 두고, 필드에 없으면 바로 빈 목록 — 결과는 색인 없이 continuous_sources()를 훑을 때와 같아야 한다"""
import unittest
from engine import Card
from cards import Impl
from test_new_mechanics import make, card, on_field


def scan(g, key):
    """색인 없이 훑은 결과 (Game.srcs_with와 같아야 한다)"""
    if key.startswith('rule:'):
        return [s for s in g.continuous_sources() if key[5:] in getattr(s, 'rules', {})]
    return [s for s in g.continuous_sources() if getattr(s, key, None)]



import databug_fixture   # 데이터버그 카드 · 덱(카드 풀에서 보류 중 — 사용자 지시 2026-10-30)을 이 모듈 시험 동안만 넣는다


def setUpModule(): databug_fixture.install()


def tearDownModule(): databug_fixture.uninstall()

class KindIndexTest(unittest.TestCase):
    def keys(self, g):
        return sorted(g.hook_index()) + ['rule:없는_규칙', 'atk_mod', 'on_event']

    def test_same_as_scan(self):
        g = make('세제', '호박옥 - 봉인의 계약')
        for k in self.keys(g): self.assertEqual(list(g.srcs_with(k)), scan(g, k), k)
        for name, p in (('세리 - 두플리카토르', 0), ('세리 - 릭토르', 0), ('호박옥의 수호자 - 카르분쿨루스', 1)):
            on_field(g, name, p)
            for k in self.keys(g): self.assertEqual(list(g.srcs_with(k)), scan(g, k), (name, k))

    def test_card_made_after_index_is_added_when_placed(self):
        g = make('투기장의 규칙', '데이터버그 패키지 프로그램')
        self.assertIn('_hook_ix', g.__dict__)                       # setup이 사건을 내며 색인을 만든다
        self.assertFalse(g.rule('cost_double', 0))
        on_field(g, '세리 - 두플리카토르', 1)                         # 색인을 만든 뒤 새로 만든 카드
        self.assertTrue(g.rule('cost_double', 0))

    def test_card_put_directly_in_shared_zone(self):
        g = make('투기장의 규칙', '데이터버그 패키지 프로그램')
        x = Card(Impl.pool['세리 - 델레가토르'], 0); Impl.attach(x)
        g.shareds[0] = x; x.zone = 'shared'; x.controller = 0; g.shared_owners[0] = 0
        self.assertEqual(g.cost_payer(0), 1)                         # place_*를 거치지 않아도 조회 때 더한다

    def test_no_holder_on_field_is_empty(self):
        g = make('투기장의 규칙', '데이터버그 패키지 프로그램')
        card(g, '세리 - 두플리카토르', 0, 'hand')
        self.assertEqual(g.srcs_with('rule:cost_double'), ())       # 패의 카드는 [지속] 출처가 아니다


if __name__ == '__main__':
    unittest.main()
