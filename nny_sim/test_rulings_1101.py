"""재정질문/003 답변(세창 2026-11-01, 디스코드) 테스트 (nny_sim 폴더에서):  python -m unittest test_rulings_1101 -v
지혜의 원천 - 마도서 1번 — 「카드의 발동」(card_only) → 「효과의 발동」으로 확장(2026-10-20 재정을 뒤집음).
몬스터 효과 발동에도 응답해야 한다(기존에는 마법/함정 카드 발동에만 응답)."""
import unittest
import databug_fixture
from test_new_mechanics import make, card, on_field, eff


# 데이터버그 디지털 웜(몬스터 효과 발동 · 상대 필드 파괴)을 쓴다 — 데이터버그 테마는 2026-10-30 카드 풀에서 빠져 보류 자료로 모듈 동안만 넣는다(#115 와 같은 방식)
def setUpModule(): databug_fixture.install()
def tearDownModule(): databug_fixture.uninstall()


class WisdomSourceRespondsToEffectTest(unittest.TestCase):
    def _setup(self):
        g = make('소원의 분수', '소원의 분수')
        wsft = card(g, '지혜의 원천 - 마도서', 0, None); g.place_spell(wsft, 0, True)
        on_field(g, '세리 - 엑삭토르', 0)   # 데이터버그의 파괴 대상(상대 필드 카드)
        src = on_field(g, '데이터버그 디지털 웜', 1)
        return g, wsft, src

    def test_responds_to_opponent_monster_effect_activation(self):
        g, wsft, src = self._setup()
        g.activate(1, src, eff(src, 1))   # 몬스터 효과 발동(카드의 발동이 아님)
        self.assertTrue(g.legal(0, wsft, eff(wsft, 1), g.chain))

    def test_still_responds_to_opponent_card_activation(self):
        g, wsft, src = self._setup()
        spell = card(g, '용기의 무기 - 검', 1, 'hand')   # [신속] 마법 — spell_act(카드의 발동)
        link = g.activate(1, spell, eff(spell, 1))
        self.assertTrue(link)
        self.assertTrue(g.legal(0, wsft, eff(wsft, 1), g.chain))

    def test_does_not_respond_to_own_activation(self):
        g, wsft, src = self._setup()
        own = on_field(g, '데이터버그 디지털 웜', 0)   # src(필드 1)가 파괴 대상
        g.activate(0, own, eff(own, 1))
        self.assertFalse(g.legal(0, wsft, eff(wsft, 1), g.chain))


if __name__ == '__main__':
    unittest.main()
