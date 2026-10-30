"""사람 모드 상급(제물) 일반소환 — 릴리스할 몬스터를 사람이 직접 고르는지 테스트 (nny_sim 폴더에서):
python -m unittest test_human_tribute_summon -v

세창 체크 요청 검증(NNY온라인_진행.md): app/human.py의 HumanAI는 ai.py HeuristicAI.extra_summon_options를 그대로 물려받아
'소환:{card}' 제물 소환 후보 자체는 뜨고 고를 수 있지만, 그 안에서 쓰는 ai.py pick_tributes가 릴리스할 몬스터를
가치가 낮은 순으로 자동으로 골라 버려서(사람에게 묻지 않음) 사람은 "무엇을 제물로 낼지"는 고를 수 없었다.
app/human.py만 고쳐 HumanAI.extra_summon_options·pick_release_tributes·do_extra로 그 선택을 사람에게 묻게 한다.
엔진(g.release_cands · g.tributes_needed · g.normal_summon)은 읽기 전용으로만 쓰고 고치지 않는다.
"""
import os, random, sys, threading, unittest

sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app')]

import season as SE
import policy as P
from cards import Impl, POOL
from engine import Game, Card
from human import Bridge, HumanAI

DECKS = SE.load_decks()


def empty_table():
    t = P.Table.__new__(P.Table); t.path = '/dev/null'; t.L0 = {}; t.L1 = {}; t.L2 = {}; t.games = 0
    return t


def put(g, name, owner, pos='atk'):
    """필드에 몬스터를 직접 놓는다 (test_facedown.py의 put과 같은 자리 — 뉴네오 테스트 공통 관용구)"""
    c = Card(POOL[name], owner); Impl.attach(c); c.zone = None
    g.place_monster(c, owner, pos); c.summon_turn = 0
    return c


def give_hand(g, name, owner):
    c = Card(POOL[name], owner); Impl.attach(c); c.zone = 'hand'
    g.p[owner].hand.append(c)
    return c


class TributeChoiceTest(unittest.TestCase):
    """좌석0(사람) 필드에 가치가 다른 릴리스 후보 2장, 패에 제물 1장이 필요한 레벨5 몬스터 1장을 두고,
    항상 '소환' 후보를 고르게 한 뒤, 제물 질문이 나오면 가치가 더 높은 쪽(기본 자동 선택과 반대)을 명시적으로 고른다.
    고친 코드는 사람이 고른 대로(가치 높은 쪽 릴리스) 되어야 하고, 안 고친 코드는 ai.py pick_tributes가 가치가
    낮은 쪽을 자동으로 골라 사람의 선택과 반대로 끝난다(이 테스트가 실패) — 고치기 전 코드로 실제 실패하는 것을
    git stash로 human.py만 되돌려 확인했다(커밋 메시지 참고)."""

    def setUp(self):
        self.bridge = Bridge()
        da, db = DECKS['솔루나 아츠'], DECKS['세제']
        ai0 = HumanAI(da['스킬'], self.bridge, empty_table(), learn=False)
        import ai as A
        ai1 = A.HeuristicAI(db['스킬'])
        self.g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [ai0, ai1], 0, random.Random(11), [], Impl)
        self.box = {}

    def _drive(self, want_high_value):
        g = self.g; box = self.box
        picked_summon = False

        def driver():
            try:
                g.setup()
                g.turn = 3; g.turn_player = 0; g.phase = '진행'
                g.p[0].hand = []
                box['low'] = put(g, '호박옥 - 결정충', 0, 'atk')        # 가치 낮음(공격력 100) — 자동 선택이면 이게 먼저 릴리스
                box['high'] = put(g, '데이터버그 리틀버그', 0, 'atk')    # 가치 높음(공격력 1500)
                give_hand(g, '격투가 래빗 풋', 0)                      # 레벨5 → 제물 1장 필요
                g.p[0].ai.main_phase(g, 0, '진행')
            finally:
                box['done'] = True

        t = threading.Thread(target=driver, daemon=True)
        t.start()
        for _ in range(500):
            t.join(0.05)
            if not t.is_alive() or box.get('done'): break
            req = self.bridge.pending
            if req is None: continue
            labs = [o['label'] for o in req['opts']]
            if req['decision'] == '진행 행동' and any(l.startswith('소환:격투가 래빗 풋') for l in labs):
                idx = next(i for i, l in enumerate(labs) if l.startswith('소환:격투가 래빗 풋'))
                picked_summon = True
            elif picked_summon and req['decision'].startswith('격투가 래빗 풋 제물로 릴리스할 몬스터'):
                box['asked_release'] = True
                want = box['high'].name if want_high_value else box['low'].name
                idx = next((i for i, l in enumerate(labs) if want in l), 0)
            else:
                idx = 0   # 멀리건 · 시작 트리거 등 이 테스트와 상관없는 질문은 기본값으로 넘긴다
            self.bridge.reply(req['id'], idx)
        t.join(5)
        self.assertTrue(box.get('done'), '대전 스레드가 끝나지 않음(교착)')

    def test_human_can_choose_which_monster_to_release_as_tribute(self):
        """사람이 '가치가 더 높은 쪽을 릴리스'하겠다고 명시적으로 고르면 — 실제로 그 몬스터가 릴리스돼야 한다
        (ai.py pick_tributes의 '가치 낮은 순 자동 선택'과는 반대 결과이므로, 사람의 선택이 실제로 반영됐는지 구분된다)"""
        self._drive(want_high_value=True)
        low, high = self.box['low'], self.box['high']
        self.assertTrue(self.box.get('asked_release'), '사람에게 제물로 릴리스할 몬스터를 묻지 않았다(여전히 자동 선택)')
        self.assertIn(high, self.g.p[0].grave, '사람이 고른 몬스터(가치 높은 쪽)가 릴리스되지 않았다')
        self.assertIn(low, self.g.p[0].m, '사람이 고르지 않은 몬스터(가치 낮은 쪽)가 대신 릴리스됐다')

    def test_human_choosing_the_low_value_monster_also_works(self):
        """반대로 가치가 낮은 쪽(자동 선택과 같은 결과)을 사람이 직접 골라도 똑같이 반영돼야 한다 — 우연히 같은
        결과가 나오는 경우를 가려내기 위해, 두 선택 모두 실제로 사람의 답을 거친다는 것을 확인한다"""
        self._drive(want_high_value=False)
        low, high = self.box['low'], self.box['high']
        self.assertTrue(self.box.get('asked_release'))
        self.assertIn(low, self.g.p[0].grave)
        self.assertIn(high, self.g.p[0].m)


if __name__ == '__main__':
    unittest.main()
