"""서치 효과("덱에서 … 패에 넣는다")가 사람·AI의 선택(ai.pick_search)을 무시하고 엔진이 멋대로 고르던 문제
재현·회귀 테스트 (nny_sim 폴더에서): python -m unittest test_search_player_choice -v

디스코드 soltop_ 제보(2026-10-31, 채널 1565883143074877450) — 「격투가」전투 단계에서 모든 몬스터가 공격한
뒤 「투기장의 규칙」(FGTR-011) 2번 효과로 「격투가 입장」(FGTR-008)을 서치해 체인으로 이어 활동하려 했으나,
활동 직후 바로 정비 단계로 넘어가 원하는 플레이를 못 했다는 버그. 원인: blocks/lib.py do_search의
이름 없는 일반 서치 분기(541행 name_ref 분기와 달리)가 Game.search()(ai.pick_search를 거쳐 사람·AI가
직접 고름)를 쓰지 않고, 하드코딩된 가치 휴리스틱(hand_pick_val+card_pri)으로 후보 중 하나를 멋대로 패에
넣고 있었다 — 그래서 사람이 특정 카드(격투가 입장 등)를 노리고 서치해도 다른 카드가 나와 의도한
후속 플레이(그 카드를 활동 → 효과 처리)가 아예 생기지 않고, 전투 단계가 할 일이 없어져 그대로 끝났다.
"""
import unittest
from test_new_mechanics import make, card, eff, Idle


class ForcedPickAI(Idle):
    """서치 후보 중 이름이 target인 카드를 강제로 고른다(지정이 없으면 기존 가치 휴리스틱과 다르게 '가장 약한
    카드'를 고름) — do_search가 이 선택을 실제로 쓰는지(아니면 무시하고 하드코딩 휴리스틱으로 딴 카드를
    집는지) 확인한다"""
    target = '격투가 입장'

    def pick_search(self, g, p, cands, why):
        hit = next((c for c in cands if c.name == self.target), None)
        return hit if hit is not None else min(cands, key=lambda c: self.card_pri(g, p, c))


class SearchUsesPlayerChoiceTest(unittest.TestCase):
    def _game(self, ai=ForcedPickAI):
        g = make('투기장의 규칙', '세제', ai=ai)
        g.p[0].hand.clear()
        card(g, '격투가 라이노 혼', 0, 'hand')   # 효과2 코스트(패의 「격투가」 카드 1장을 덱으로 되돌림)
        # 패에 「격투가 입장」이 미리 있으면 서치 전부터 손에 있어 재현이 안 된다 — 덱에만 있는지 확인
        self.assertFalse(any(c.name == '격투가 입장' for c in g.p[0].hand))
        self.assertTrue(any(c.name == '격투가 입장' for c in g.p[0].main + g.p[0].upper),
                         '격투가 입장이 덱에 없음 — 재현 조건 불충분')
        return g

    def test_search_brings_the_card_the_ai_actually_picked(self):
        g = self._game()
        skill = g.p[0].skill
        eff2 = eff(skill, 2)
        ok = g.act(0, skill, eff2)
        self.assertTrue(ok, '투기장의 규칙 2번 발동 실패')
        self.assertTrue(any(c.name == '격투가 입장' for c in g.p[0].hand),
                         'ai.pick_search가 고른 「격투가 입장」이 패에 들어오지 않음 — '
                         'do_search가 pick_search 결과를 무시하고 하드코딩 휴리스틱으로 딴 카드를 넣었을 가능성')

    def test_different_ai_choice_changes_the_result(self):
        """같은 상황에서 ai.pick_search가 다른 카드를 고르면 결과도 따라 바뀌어야 한다(엔진이 결과를
        미리 정해 두고 있지 않다는 확인) — '격투가의 투기장'을 대신 고르는 AI로 같은 조작을 반복"""
        class ForcedArena(ForcedPickAI):
            target = '격투가의 투기장'

        g = self._game(ai=ForcedArena)
        skill = g.p[0].skill
        g.act(0, skill, eff(skill, 2))
        self.assertTrue(any(c.name == '격투가의 투기장' for c in g.p[0].hand))
        self.assertFalse(any(c.name == '격투가 입장' for c in g.p[0].hand))


if __name__ == '__main__':
    unittest.main()
