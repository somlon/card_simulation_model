"""호박옥 23종 (cards7) 테스트 (nny_sim 폴더에서):  python3 -m unittest test_theme_amber -v
스킬 1번(라운드 시작 시 에이스) · 2번 유지비 · 봉인의 계약 3번 · 봉인 카운터 조건부 내성 · 아우렘 4번 · 녹스 3 · 4번 ·
침전 · 황금봉랍 · 균열 · 임시 봉인 · 실렉스 · 카르분쿨루스 · 월식 · 깨어남의 종 · 꿈의 파열"""
import random, unittest
import season as SE
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card
import cards7 as A

DECKS = SE.load_decks()
SEALC, DREAMC = '호박옥 - 봉인의 계약', '호박옥 - 몽식의 계약'
OPP = '솔루나 아츠'


class Idle(HeuristicAI):
    """아무 것도 하지 않는 AI (강제 트리거만) — 테스트가 직접 조작한다"""
    def respond(self, g, p, opts): return None
    def choose_triggers(self, g, p, cands): return [(c, e, ev) for c, e, ev in cands if e.mandatory]
    def main_phase(self, g, p, ph): return None
    def battle_phase(self, g, p): return None
    def mulligan(self, g, p, hand): return []


class Yes(Idle):
    def choose_triggers(self, g, p, cands): return list(cands)


def make(me=SEALC, ai=Idle, seed=5, opp=OPP, clear=True):
    da, db = DECKS[me], DECKS[opp]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [ai(me), ai(opp)], 0, random.Random(seed), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'; g.events = []
    if clear:
        g.chain = []
        for x in g.p: x.opt = {}   # 시작 시 처리(스킬 1번 → 에이스 [소환])가 쓴 1턴 1번 기록도 지운다
        for p in (0, 1):
            for m in list(g.monsters(p)): g._remove(m)
            for z in ('hand', 'main', 'upper', 'grave'): getattr(g.p[p], z).clear()
    return g


def put(g, name, owner, zone):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone
    if zone in ('hand', 'grave', 'main', 'upper', 'banish'): getattr(g.p[owner], zone).append(c)
    return c


def mon(g, name, owner, pos='atk', seals=0):
    c = put(g, name, owner, None); g.place_monster(c, owner, pos, allow_shared=False)
    if seals: g.add_counter(c, A.SEAL, seals)
    return c


def spell(g, name, owner, faceup=True):
    c = put(g, name, owner, None); g.place_spell(c, owner, faceup); return c


def eff(c, num, zone=None):
    return next(e for e in c.effects if e.num == num and (zone is None or zone in e.zones))


def run(g):
    g.triggers()
    if g.chain: g.resolve_chain()


class SkillTest(unittest.TestCase):
    def test_seal_contract_places_aurem_at_round_start(self):
        g = make(clear=False)
        au = [m for m in g.monsters(0) if m.name == A.AUREM]
        self.assertEqual(len(au), 1); self.assertEqual(au[0].pos, 'def')

    def test_dream_contract_summons_nox(self):
        g = make(DREAMC, clear=False); run(g)
        self.assertTrue(any(m.name == A.NOX for m in g.monsters(0)))

    def test_upkeep_removes_counters_or_damages(self):
        g = make()
        m = mon(g, A.AUREM, 0, 'def', seals=3)
        g.p[0].skill.end_process(g, g.p[0].skill)
        self.assertEqual(A.seals(m), 1)            # 봉인의 계약: 2개 제거
        hp0 = g.p[0].hp
        g.p[0].skill.end_process(g, g.p[0].skill)   # 1개뿐 → 1개 모자람 × 1000
        self.assertEqual(A.seals(m), 0); self.assertEqual(g.p[0].hp, hp0 - 1000)

    def test_upkeep_only_on_own_turn(self):
        g = make(); m = mon(g, A.AUREM, 0, 'def', seals=3); g.turn_player = 1
        g.p[0].skill.end_process(g, g.p[0].skill)
        self.assertEqual(A.seals(m), 3)

    def test_half_battle_damage_with_seals(self):
        g = make()
        self.assertFalse(g.rule('half_battle_damage', 0))
        mon(g, A.AUREM, 0, 'def', seals=1)
        self.assertTrue(g.rule('half_battle_damage', 0))


class AceTest(unittest.TestCase):
    def test_amber_effect_can_pick_opponents_sealed_ace(self):
        # 봉인된 에이스는 「「호박옥」 카드 이외의」 효과만 받지 않는다 — 호박옥 미러: 아우렘 4번이 상대의 봉인된 아우렘을 고를 수 있다
        g = make(opp=SEALC)
        me = mon(g, A.AUREM, 0, 'def', seals=3); them = mon(g, A.AUREM, 1, 'def', seals=3)
        self.assertTrue(g.legal(0, me, eff(me, 4)))
        g.act(0, me, eff(me, 4))
        self.assertFalse(g.on_field(them))
        # 호박옥이 아닌 카드의 효과는 여전히 받지 않는다
        g2 = make(opp=SEALC); them2 = mon(g2, A.AUREM, 1, 'def', seals=3)
        self.assertTrue(g2.immune(them2, 0, put(g2, '매수당한 킬러', 0, 'hand')))

    def test_aurem_summon_puts_three_seals(self):
        g = make(ai=Yes); au = put(g, A.AUREM, 0, 'upper')
        g.special_summon(au, 0, 'def'); run(g)
        self.assertEqual(A.seals(au), 3)

    def test_sealed_aurem_immune_except_amber(self):
        g = make()
        au = mon(g, A.AUREM, 0, 'def', seals=1)
        foe = mon(g, '솔루나 시아', 1); amb = spell(g, '호박옥 - 균열', 0)
        self.assertTrue(g.immune(au, 1, foe)); self.assertTrue(g.immune(au, 0, spell(g, '태양과 달의 마력', 0)))
        self.assertFalse(g.immune(au, 0, amb))
        g.remove_counter(au, A.SEAL, 1)
        self.assertFalse(g.immune(au, 1, foe))

    def test_sealed_aurem_battle_indestructible_no_release_no_attack(self):
        g = make()
        au = mon(g, A.AUREM, 0, 'atk', seals=1)
        self.assertTrue(g.rule('indestructible', au, True))
        self.assertFalse(g.releasable(au)); self.assertTrue(g.attack_banned(au))
        g.remove_counter(au, A.SEAL, 1)
        self.assertTrue(g.releasable(au)); self.assertFalse(g.attack_banned(au))

    def test_sealed_aurem_ignores_opponent_stat_modifier(self):
        g = make()
        au = mon(g, A.AUREM, 1, 'atk', seals=1)
        a0 = g.atk(au)
        mon(g, '♣ 메이드에 실패한 고양이', 0); put(g, '◆ 플러쉬를 노리는 늑대', 0, 'grave')
        self.assertEqual(g.atk(au), a0)            # 「호박옥」 이외의 [지속] 증감도 받지 않는다 (검토 2026-10-13)
        g.remove_counter(au, A.SEAL, 1)
        self.assertEqual(g.atk(au), a0 - 100)

    def test_aurem_4_destroys_up_to_removed(self):
        g = make()
        au = mon(g, A.AUREM, 0, 'def', seals=3)
        o1 = mon(g, '솔루나 시아', 1); o2 = mon(g, '솔루나 시엘', 1)
        e = eff(au, 4)
        self.assertTrue(g.legal(0, au, e)); g.act(0, au, e)
        self.assertEqual(A.seals(au), 1)           # 내성용 1개는 남긴다 (AI)
        self.assertTrue(o1.zone == 'grave' and o2.zone == 'grave')

    def test_nox_direct_attack_rule(self):
        g = make(DREAMC)
        nx = mon(g, A.NOX, 0, 'def', seals=1); att = mon(g, '솔루나 시아', 1)
        self.assertTrue(g.rule('direct_attack', att))
        mon(g, '호박옥 - 결정충', 0, 'def')
        self.assertFalse(g.rule('direct_attack', att))

    def test_nox_4_end_phase_face_down(self):
        g = make(DREAMC)
        nx = mon(g, A.NOX, 0, 'def', seals=3); t = mon(g, '솔루나 시아', 1)
        g.turn_player = 1; g.emit('end_phase', player=1); run(g)
        self.assertFalse(t.faceup); self.assertEqual(t.pos, 'def')

    def test_nox_4_needs_three(self):
        g = make(DREAMC)
        mon(g, A.NOX, 0, 'def', seals=2); t = mon(g, '솔루나 시아', 1)
        g.turn_player = 1; g.emit('end_phase', player=1); run(g)
        self.assertTrue(t.faceup)


class GuardTest(unittest.TestCase):
    def test_silex_leaves_only_by_destruction(self):
        g = make()
        sx = mon(g, '호박옥의 수호자 - 실렉스', 0, 'def', seals=1)
        g.banish(sx, ('effect', mon(g, '솔루나 시아', 1)))
        self.assertTrue(g.on_field(sx))
        g.destroy(sx)
        self.assertFalse(g.on_field(sx))

    def test_carbunculus_untargetable_by_opponent_cost(self):
        g = make()
        cb = mon(g, '호박옥의 수호자 - 카르분쿨루스', 0, 'def', seals=1)
        g.costing = type('L', (), {'player': 1})()
        try: self.assertTrue(g.immune(cb, 1))
        finally: g.costing = None
        self.assertFalse(g.immune(cb, 1))   # 대상을 지정하지 않는 효과는 받는다


class SpellTest(unittest.TestCase):
    def test_sediment_summons_from_deck_and_seals(self):
        g = make()
        x = put(g, '호박옥 - 결정충', 0, 'main'); s = put(g, '호박옥 - 침전', 0, 'hand')
        self.assertTrue(g.legal(0, s, eff(s, 1)))
        g.act(0, s, eff(s, 1))
        self.assertEqual(x.zone, 'm'); self.assertEqual(x.pos, 'def')
        self.assertEqual(A.side_seals(g, 0), 2)
        self.assertFalse(g.oath_ok(0, spell(g, '태양과 달의 마력', 0)))   # 맹세: 이 턴 「호박옥」 카드만

    def test_golden_wax_negates_with_two_seals(self):
        g = make(); g.turn_player = 1
        au = mon(g, A.AUREM, 0, 'def', seals=3)
        w = spell(g, '호박옥 - 황금봉랍', 0)
        s = put(g, '밑장빼기', 1, 'hand'); x = put(g, '♣ 포카드를 보는 고양이', 1, 'main')
        g.activate(1, s, eff(s, 1))
        e = eff(w, 1); self.assertTrue(g.legal(0, w, e))
        g.activate(0, w, e); g.resolve_chain()
        self.assertEqual(x.zone, 'main'); self.assertEqual(A.seals(au), 1)

    def test_rift_destroys_as_many_as_removed(self):
        g = make()
        m = mon(g, '호박옥 - 결정충', 0, 'def', seals=2)
        o1 = mon(g, '솔루나 시아', 1); o2 = mon(g, '솔루나 시엘', 1); o3 = mon(g, '솔루나 시아', 1)
        r = put(g, '호박옥 - 균열', 0, 'hand')
        g.act(0, r, eff(r, 1))
        self.assertEqual(A.seals(m), 0)
        self.assertEqual(sum(1 for o in (o1, o2, o3) if o.zone == 'grave'), 2)

    def test_temp_seal_protects_and_can_pick_sealed_ace(self):
        g = make()
        au = mon(g, A.AUREM, 0, 'def', seals=1)
        ts = put(g, '호박옥 - 임시 봉인', 0, 'hand')
        self.assertTrue(g.legal(0, ts, eff(ts, 1)))
        g.act(0, ts, eff(ts, 1))
        self.assertEqual(au.flags.get('immune_all_until'), g.turn + 1)

    def test_eclipse_on_sum_reaching_five(self):
        g = make(ai=Yes)
        m = mon(g, A.AUREM, 0, 'def', seals=4)
        ec = spell(g, '월식', 0, faceup=False); ec.set_turn = 1
        t = mon(g, '솔루나 시아', 1)
        g.events = []; g.add_counter(m, A.SEAL, 1); run(g)
        self.assertFalse(t.faceup); self.assertEqual(A.seals(m), 0)

    def test_eclipse_not_when_already_five(self):
        g = make(ai=Yes)
        m = mon(g, A.AUREM, 0, 'def', seals=5)
        ec = spell(g, '월식', 0, faceup=False); ec.set_turn = 1
        t = mon(g, '솔루나 시아', 1)
        g.events = []; g.add_counter(m, A.SEAL, 1); run(g)
        self.assertTrue(t.faceup)

    def test_wake_bell_revives_on_hp_threshold(self):
        g = make(DREAMC, ai=Yes)
        nx = mon(g, A.NOX, 0, 'def', seals=2)
        bell = spell(g, '깨어남의 종', 0, faceup=False); bell.set_turn = 1
        a = put(g, '호박옥 - 결정충', 0, 'grave'); b = put(g, '호박옥 - 잔편', 0, 'grave')
        g.p[0].hp = 3000; g.events = []
        g.damage(0, 1500, '시험'); run(g)
        self.assertEqual(A.seals(nx), 0)
        self.assertTrue(a.zone == 'm' and b.zone == 'm')

    def test_dream_burst_destroys_all_monsters_when_nox_leaves(self):
        g = make(DREAMC, ai=Yes)
        nx = mon(g, A.NOX, 0, 'def'); o = mon(g, '솔루나 시아', 1); own = mon(g, '호박옥 - 결정충', 0, 'def')
        bu = spell(g, '꿈의 파열', 0, faceup=False); bu.set_turn = 1
        g.events = []; g.destroy(nx); run(g)
        self.assertEqual(o.zone, 'grave'); self.assertEqual(own.zone, 'grave')


if __name__ == '__main__':
    unittest.main()
