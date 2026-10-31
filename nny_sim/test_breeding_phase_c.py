"""soltop_ 제보 2/9 (디스코드 `?`, 2026-10-31): 「번성충 - 번식지를 종료 페이즈의 c단계에서 처리하도록 변경」 재현 테스트
(nny_sim 폴더에서):  python -m unittest test_breeding_phase_c -v

종전: SWRM-019([지속] 각 턴의 종료 시에 「번성충」 카드 1장을 패에 넣는다)가 종료 단계 a에서 바로 처리돼,
패가 7장일 때 서치로 8장이 된 뒤 b단계 패 상한 검사에 걸려 그 자리에서 1장을 도로 버렸다(검사 순서상
서치한 카드 자체가 버려질 수도 있었음). 요청대로 처리 시점을 c단계(패 7장 확인 뒤)로 옮기면, 패 상한
검사는 서치 전 패 수(7장, 상한 이내)로 통과하고 서치는 그 뒤에 일어나 패가 8장으로 끝난다 — 종전 동작과
다른 최종 패 수(8 vs 7)로 두 동작이 구별된다."""
import unittest
from engine import Card
from cards import Impl
from test_end_phase import make, Idle


class BreedingGroundEndPhaseCTest(unittest.TestCase):
    def setUp(self):
        self.g = g = make('번성충-대발생', '솔루나 아츠', ai=Idle, first=0)
        self.den = Card(Impl.pool['번성충-번식지'], 0); Impl.attach(self.den)
        g.place_field(self.den, 0)
        # 선공 1턴째는 드로우 없음(§4) — 패 수를 그대로 7장으로 맞춘다(모자라면 메인 덱에서 채우고, 넘치면 되돌림)
        pl = g.p[0]
        while len(pl.hand) < 7:
            g.draw(0, 1, 'main', cause=('rule', None))
        while len(pl.hand) > 7:
            c = pl.hand.pop(); c.zone = 'main'; pl.main.append(c)
        self.assertEqual(len(pl.hand), 7)

    def test_search_runs_after_hand_limit_check_not_before(self):
        g = self.g; pl = g.p[0]
        deck_before = len(pl.main) + len(pl.upper)
        n0 = len(g.log)
        g.play_turn()
        logs = [e['m'] for e in g.log[n0:]]
        discard_logs = [m for m in logs if m.startswith('패 상한 — ')]
        search_logs = [m for m in logs if '번성충-번식지' in m and '패에 넣음' in m]
        self.assertEqual(len(search_logs), 1, msg=f'서치가 정확히 1번 일어나야 한다: {logs}')
        self.assertEqual(discard_logs, [], msg=f'c단계로 옮겼다면 서치 전(7장) 패 상한 검사를 통과해 버림이 없어야 한다: {logs}')
        self.assertEqual(len(pl.hand), 8, msg='서치가 패 상한 검사 뒤에 일어나 최종 패는 8장이어야 한다(종전 동작이면 7장)')
        self.assertEqual(len(pl.main) + len(pl.upper), deck_before - 1)

    def test_end_phase_is_not_an_activation(self):
        # [지속] 종료 시 처리이지 발동이 아니다(희생제 4번과 같은 재정, 2026-10-23 Q56) — 체인에 오르지 않는다
        g = self.g
        n0 = len(g.log)
        g.play_turn()
        self.assertFalse(any('「번성충-번식지」 1번 효과 발동' in e['m'] for e in g.log[n0:]))


if __name__ == '__main__':
    unittest.main()
