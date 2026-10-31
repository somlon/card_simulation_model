"""블록 체계 테스트 (nny_sim 폴더에서):  python3 -m unittest test_blocks -v
조립표의 문장 틀이 카드 텍스트와 맞는지(텍스트가 바뀌면 여기서 실패 — 조립표를 고친다), 조립된 효과의 기본 성질."""
import unittest
import cards
from cards import Impl, POOL
from engine import Card
import blocks
from blocks import dsl, build, text


def card_of(code):
    return next(d for d in POOL.values() if d.get('code') == code)


class TemplateTest(unittest.TestCase):
    def test_all_templates_match_text(self):
        bad = []
        for code, specs in dsl.TABLE.items():
            d = card_of(code); sents = text.sentences(d)
            for key, spec in specs.items():
                try: build.compile_spec(spec, sents.get(key), d)
                except build.TemplateMismatch as ex: bad.append(str(ex))
        self.assertEqual(bad, [], '\n'.join(bad))

    def test_every_sentence_of_assembled_card_has_spec(self):
        # 조립된 카드는 텍스트의 효과 문장마다 조립표 줄이 있어야 한다(빠뜨린 효과 없음)
        miss = [(code, k) for code in dsl.TABLE for k in text.sentences(card_of(code)) if k not in dsl.TABLE[code]]
        self.assertEqual(miss, [])

    def test_template_holes_read_numbers(self):
        self.assertEqual(text.match('카드 {n}장을 {n}장', '카드 2장을 2장'), {'n': 2})
        self.assertIsNone(text.match('카드 {n}장을 {n}장', '카드 2장을 3장'))
        self.assertIsNone(text.match('상대 필드의 카드 {n}장', '자신 필드의 카드 1장'))


class AssembleTest(unittest.TestCase):
    def test_instances_share_effects(self):
        # 같은 카드의 인스턴스는 조립된 Effect를 함께 쓴다(문장마다 한 번 조립 — 카드 정의 시간 · 메모리)
        a, b = Card(card_of('COMN-005'), 0), Card(card_of('COMN-005'), 1)
        Impl.attach(a); Impl.attach(b)
        self.assertTrue(all(x is y for x, y in zip(a.effects, b.effects)))

    def test_text_attrs_from_sentence(self):
        c = Card(card_of('COMN-005'), 0); Impl.attach(c)
        e2 = next(e for e in c.effects if e.num == 2)
        self.assertTrue(e2.targets_text)                      # 「대상으로 하고」
        self.assertEqual(e2.kind, 'quick')
        e3 = next(e for e in c.effects if e.num == 3)
        self.assertTrue(e3.mandatory)                         # 「(이 효과는 강제로 발동한다.)」

    def test_notes(self):
        self.assertEqual(text.notes('… (이 효과는 1턴에 2번까지 사용할 수 있다.)'), {'opt': 2})
        self.assertEqual(text.notes('… (이 효과는 1턴에 1번 제약을 받지 않는다.)'), {'opt': None})


if __name__ == '__main__':
    unittest.main()
