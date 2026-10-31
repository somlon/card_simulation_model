"""번성충-맵시기생벌(SWRM-002) 「장착 몬스터 이탈」 서치 타이밍 (soltop_ 제보 6번, 디스코드 ?, 2026-10-31):
  python -m unittest test_swrm002_leave_timing -v
soltop_ 제보 원문: "맵시기 생벌의 처리가 끝나지 않았을때 묘지로 보내지면 서치하는 문제.
처리 후에 묘지로 보내져야 동작하러가야함." — 장착 대상이 '어떤 처리의 중간 단계'로 필드를 벗어나도
engine._remove가 그 자리에서 곧바로 on_host_leave를 동기 실행해, 그 처리가 끝나기도 전에 서치가
먼저 끝나 버리던 문제. [유언]과 같은 다른 「…했을 경우」 효과는 모두 Game.triggers()(체인이 다
끝난 뒤에만 불리는 지점)를 거쳐야 발동 여부를 묻는데, on_host_leave만 이 트리거 대기열을 건너뛰고
있었다 — on_leave를 쓰는 카드는 이 카드 하나뿐(blocks 전수 확인, 2026-10-31)이라 영향 범위는 좁다."""
import unittest
from blocks.dsl import search, S
from blocks.lib import steps_run
from test_new_mechanics import make, card, on_field, eff


def equip_swrm002(g, host, owner):
    """do_equip(blocks/lib.py)이 성공했을 때 남기는 상태를 그대로 재현(장착·on_host_leave 등록) —
    발동 자체(choose_at_act 대상 선택)는 이 타이밍 버그와 무관해 건너뛴다."""
    c = card(g, '번성충-맵시기생벌', owner, None)
    g.place_spell(c, owner, True)
    c.flags['stay'] = True; c.flags['as_spell'] = True
    c.equip_to = host; host.equips.append(c)
    steps = (search(S('own', 'deck', 'monster', group='번성충'), 1),)

    def host_leave(g, e, host, steps=steps):
        g.L(f'{e} 장착 몬스터 {host} 이탈 → 처리', 'sys'); steps_run(g, e, e.controller, steps)
    c.on_host_leave = host_leave
    return c


class Swrm002LeaveTimingTest(unittest.TestCase):
    def setUp(self):
        self.g = g = make('소원의 분수', '세제')
        card(g, '번성충-먹이바구미', 0, 'main')   # 서치될 번성충 몬스터
        self.host = on_field(g, '솔루나 시엘', 1)
        self.swrm = equip_swrm002(g, self.host, 0)
        self.hand0 = len(g.p[0].hand)

    def test_search_waits_for_triggers_checkpoint_not_instant(self):
        g, host = self.g, self.host
        g._remove(host)   # 호스트가 '어떤 처리'의 중간 단계로 필드를 벗어나는 상황을 흉내(그 처리는 아직 안 끝남)
        self.assertEqual(len(g.p[0].hand), self.hand0,
                          '_remove 직후(= 다른 처리가 끝나기 전)에는 아직 서치가 일어나면 안 된다')
        g.triggers()   # 체인·처리가 다 끝난 뒤의 체크포인트
        self.assertEqual(len(g.p[0].hand), self.hand0 + 1,
                          'triggers() 체크포인트에 이르러서야 서치가 일어나야 한다')
        self.assertEqual(g.p[0].hand[-1].name, '번성충-먹이바구미')

    def test_equip_itself_untouched_by_unrelated_removal(self):
        """맵시기생벌 자신이 아니라 호스트가 다른 이유로 필드를 벗어나는 경우만 다룬다 — 장착 카드
        자신의 이탈(묘지행)은 engine._remove의 별도 경로(on_equip_leave)로 이번 수정과 무관함을 확인"""
        g, swrm = self.g, self.swrm
        g._remove(swrm)
        self.assertEqual(len(g.p[0].hand), self.hand0)
        g.triggers()
        self.assertEqual(len(g.p[0].hand), self.hand0,
                          '장착 카드 자신이 떠난 것은 on_host_leave(호스트 이탈) 대상이 아니다')


if __name__ == '__main__':
    unittest.main()
