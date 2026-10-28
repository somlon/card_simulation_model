"""효과의 코스트 칸 · 문장 성질표 테스트 (nny_sim 폴더에서):  python3 -m unittest test_cost_slot -v
번호가 있는 효과는 모두 자기 문장에 연결된다(부여 효과는 부여하는 카드의 「-」 항목 — Effect.grant_of, 블록 A22 효과 부여).
문장 성질표(cards.text_sheet)는 문장마다 한 번 만들어 모든 카드 · 판이 같은 값을 공유한다"""
import unittest
import cards
import cards2
from cards import Impl, POOL, CostItem, parse_cost
from engine import Card


def built(name, owner=0):
    c = Card(POOL[name], owner); Impl.attach(c); return c


class SentenceBindingTest(unittest.TestCase):
    def test_every_numbered_effect_has_sentence(self):
        # 문장 없는 효과는 대상 지정 여부 · 코스트 칸 등 성질이 「모름」이 된다(올인 이슈의 원인) — 0번(카드를 놓기만 하는 발동)만 문장이 없을 수 있다
        bad = [(n, e.num) for n in cards.IMPL if n in POOL for e in built(n).effects if e.num and not getattr(e, 'text_line', '')]
        self.assertEqual(bad, [])
        self.assertTrue(cards2.cer_effect(1, '격투가 세레모니').text_line)   # 게임 중에 생기는 부여 효과(세레모니)

    def test_allin_granted_effects(self):
        es = {e.num: e for e in built('◆ 플러쉬를 노리는 늑대').effects}
        pair, triple = es[21], es[22]
        self.assertEqual(pair.text_line, cards.granted_lines(POOL['올인'])[0])
        self.assertFalse(pair.targets_text); self.assertFalse(triple.targets_text)   # 「골라」 · 대상 없음 — 대상 지정 효과가 아니다
        self.assertEqual([(i.this_card, i.deck, i.opp) for i in pair.cost_items], [(True, False, False)])
        self.assertEqual([(i.this_card, i.deck, i.opp) for i in triple.cost_items], [(False, False, True)])


class SheetTest(unittest.TestCase):
    def test_shared_between_cards(self):
        # 같은 문장의 성질은 카드 · 판마다 새로 만들지 않고 한 객체를 함께 쓴다
        a, b = built('세리 - 델레가토르', 0), built('세리 - 델레가토르', 1)
        for x, y in zip(a.effects, b.effects):
            self.assertIs(x.cost_items, y.cost_items); self.assertIs(x.sure_acts, y.sure_acts)

    def test_cost_items(self):
        it = parse_cost('1. [신속] 자신의 덱의 위에서부터 카드를 3장 제외하고 발동. 카드를 1장 드로우한다.')
        self.assertIsInstance(it, tuple)
        self.assertEqual(it, (CostItem('[신속] 자신의 덱의 위에서부터 카드를 3장 제외하', False, True, False),))
        self.assertEqual(parse_cost('1. 필드의 카드 1장을 대상으로 하고 발동. 그 카드를 파괴한다.'), ())   # 대상 지정은 코스트가 아니다
        self.assertTrue(parse_cost('1. [신속] 서로의 필드의 몬스터 1장을 릴리스하고 발동.')[0].opp)
        self.assertFalse(parse_cost('1. 상대가 몬스터를 소환했을 때 자신 필드의 몬스터 1장을 릴리스하고 발동.')[0].opp)   # 쉼표 없는 조건 구절의 「상대」


if __name__ == '__main__':
    unittest.main()
