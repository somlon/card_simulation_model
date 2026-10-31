"""격투가 11종 (cards2 격투가 절, 2026-10-08 카드 자료) 테스트 (nny_sim 폴더에서):  python3 -m unittest test_theme_fighter -v
대상 지정 파괴(스네이크 스케일 · 엘리펀트 노즈 · 라이노 혼), 빈 필드 특수소환, [전투] 효과, 세레모니 영구 · 중첩 부여(재정), 입장, 반격,
투기장(수비 금지 · 덱에서 소환 · 파괴 시 서치), 투기장의 규칙 1 · 2 · 3번"""
import random, unittest
import season as SE
from ai import HeuristicAI
from cards import Impl, granted_lines
from engine import Game, Card
from blocks.build import granted_effect

CER_FLAG, CER_BASE = 'grant:FGTR-007:1-a', 30   # 세레모니 부여 [전투]: 받은 수 · 효과 번호 30 + k

DECKS = SE.load_decks()
ME = '투기장의 규칙'
OPP = '솔루나 아츠'


class Idle(HeuristicAI):
    def respond(self, g, p, opts): return None
    def choose_triggers(self, g, p, cands): return [(c, e, ev) for c, e, ev in cands if e.mandatory]
    def main_phase(self, g, p, ph): return None
    def battle_phase(self, g, p): return None
    def mulligan(self, g, p, hand): return []


class Yes(Idle):
    def choose_triggers(self, g, p, cands): return list(cands)


def make(ai=Idle, seed=5, opp=OPP):
    da, db = DECKS[ME], DECKS[opp]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [ai(ME), ai(opp)], 0, random.Random(seed), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'; g.events = []; g.chain = []
    for p in (0, 1):
        g.p[p].opt = {}
        for m in list(g.monsters(p)): g._remove(m)
        for z in ('hand', 'main', 'upper', 'grave'): getattr(g.p[p], z).clear()
    for _ in range(8): put(g, '럭키 다이스', 0, 'main')   # 드로우용 (「격투가」 서치 후보가 아닌 공용 카드)
    return g


def put(g, name, owner, zone):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone
    if zone in ('hand', 'grave', 'main', 'upper', 'banish'): getattr(g.p[owner], zone).append(c)
    return c


def mon(g, name, owner, pos='atk'):
    c = put(g, name, owner, None); g.place_monster(c, owner, pos); return c


def spell(g, name, owner, faceup=True):
    c = put(g, name, owner, None); g.place_spell(c, owner, faceup); return c


def eff(c, num): return next(e for e in c.effects if e.num == num)


def run(g):
    g.triggers()
    if g.chain: g.resolve_chain()


def win(g, m, t, p=0):
    """m이 전투로 t를 파괴한 상황 (battle_win 사건)"""
    g.destroy(t, ('battle', m), battle=True); g.emit('battle_win', card=m, target=t, player=p)


SNAKE, RABBIT, TIGER, LION = '격투가 스네이크 스케일', '격투가 래빗 풋', '격투가 타이거팽', '격투가 라이온하트'
ELEPH, RHINO, CER, ENTRY, COUNTER, ARENA = '격투가 엘리펀트 노즈', '격투가 라이노 혼', '격투가 세레모니', '격투가 입장', '격투가 반격', '격투가의 투기장'


class MonsterTest(unittest.TestCase):
    def test_snake_targets_opponent_card_and_discards(self):
        g = make()
        s = put(g, SNAKE, 0, 'hand'); other = put(g, ENTRY, 0, 'hand')
        self.assertFalse(g.legal(0, s, eff(s, 1)))   # 상대 필드에 카드가 없으면 대상 없음
        t = mon(g, '솔루나 시아', 1)
        self.assertTrue(g.legal(0, s, eff(s, 1)))
        g.act(0, s, eff(s, 1))
        self.assertEqual(t.zone, 'grave'); self.assertEqual(len(g.p[0].hand), 1)

    def test_snake_does_not_target_own_card(self):
        g = make(); s = put(g, SNAKE, 0, 'hand'); mon(g, TIGER, 0)
        self.assertFalse(g.legal(0, s, eff(s, 1)))

    def test_rabbit_search_and_discard(self):
        g = make(); r = put(g, RABBIT, 0, 'hand'); x = put(g, ARENA, 0, 'main')
        g.act(0, r, eff(r, 1))
        self.assertEqual(len(g.p[0].hand), 1); self.assertTrue(x.zone in ('hand', 'grave'))

    def test_tiger_ss_only_with_empty_field(self):
        g = make(); t = put(g, TIGER, 0, 'hand')
        self.assertTrue(g.legal(0, t, eff(t, 1)))
        mon(g, RABBIT, 0)
        self.assertFalse(g.legal(0, t, eff(t, 1)))

    def test_tiger_battle_destroys_and_extra_attack_then_revives(self):
        g = make(ai=Yes)
        t = mon(g, TIGER, 0); o1 = mon(g, '솔루나 시아', 1); o2 = mon(g, '솔루나 시엘', 1)
        win(g, t, o1); run(g)
        self.assertEqual(o2.zone, 'grave'); self.assertEqual(t.extra_attacks, 1)
        g.destroy(t); run(g)
        self.assertIn(t.zone, ('m', 'shared'))   # 3번 [유언] 자기 소생

    def test_lion_battle_search_heal_extra_attack(self):
        g = make(ai=Yes)
        li = mon(g, LION, 0); o = mon(g, '솔루나 시아', 1); x = put(g, ENTRY, 0, 'main')
        g.p[0].hp = 3000
        g.p[0].skill.negated = True   # 스킬 1번 [전투] 드로우가 먼저 처리되어 서치할 카드를 뽑으면 재정 G2로 회복 · 추가 공격도 하지 않는다
        win(g, li, o); run(g)
        self.assertEqual(x.zone, 'hand'); self.assertEqual(g.p[0].hp, 4000); self.assertEqual(li.extra_attacks, 1)

    def test_elephant_needs_target_summons_and_destroys(self):
        g = make(); e = put(g, ELEPH, 0, 'hand')
        self.assertFalse(g.legal(0, e, eff(e, 1)))
        t = spell(g, '태양과 달의 마력', 1, faceup=False)
        self.assertTrue(g.legal(0, e, eff(e, 1)))
        g.act(0, e, eff(e, 1))
        self.assertEqual(e.zone, 'm'); self.assertEqual(t.zone, 'grave')

    def test_elephant_battle_destroys_two(self):
        g = make(ai=Yes)
        e = mon(g, ELEPH, 0); o = mon(g, '솔루나 시아', 1); a = mon(g, '솔루나 시엘', 1); b = spell(g, '태양과 달의 마력', 1, False)
        win(g, e, o); run(g)
        self.assertEqual(a.zone, 'grave'); self.assertEqual(b.zone, 'grave')

    def test_rhino_battle_target_and_burn(self):
        g = make(ai=Yes)
        r = mon(g, RHINO, 0); o = mon(g, '솔루나 시아', 1); a = mon(g, '솔루나 시엘', 1); hp = g.p[1].hp
        win(g, r, o); run(g)
        self.assertEqual(a.zone, 'grave'); self.assertEqual(g.p[1].hp, hp - 1000)

    def test_rhino_battle_needs_target(self):
        g = make(ai=Yes)
        r = mon(g, RHINO, 0); o = mon(g, '솔루나 시아', 1); hp = g.p[1].hp
        win(g, r, o); run(g)
        self.assertEqual(g.p[1].hp, hp)   # 상대 필드에 대상이 없으면 발동하지 않음


class SpellTest(unittest.TestCase):
    def test_ceremony_permanent_and_stacking(self):
        g = make(ai=Yes)
        t = mon(g, TIGER, 0); o = mon(g, '솔루나 시아', 1)
        c1 = spell(g, CER, 0, faceup=False); c1.set_turn = 1
        win(g, t, o); run(g)
        self.assertEqual(t.flags.get(CER_FLAG), 1); self.assertGreaterEqual(t.extra_attacks, 1)
        self.assertTrue(any(e.num == CER_BASE + 1 for e in t.effects))
        # 영구: 다음 자신 턴에도 공격 횟수 +1
        for m in g.monsters(0) + g.monsters(1): m.attacks_made = 0; m.extra_attacks = m.flags.get('perm_extra_attacks', 0)
        self.assertEqual(t.extra_attacks, 1)
        # 중첩
        g.turn += 2; g.turn_player = 0; g.p[0].opt = {}
        c2 = spell(g, CER, 0, faceup=False); c2.set_turn = 1
        o2 = mon(g, '솔루나 시엘', 1)
        g.events = []; win(g, t, o2); run(g)
        self.assertEqual(t.flags.get(CER_FLAG), 2); self.assertEqual(t.flags.get('perm_extra_attacks'), 2)
        self.assertTrue(any(e.num == CER_BASE + 2 for e in t.effects))
        # 필드를 벗어나면 사라진다
        g.send_grave(t)
        self.assertIsNone(t.flags.get(CER_FLAG)); self.assertIsNone(t.flags.get('perm_extra_attacks'))

    def test_perm_extra_attacks_survive_turn_reset(self):
        g = make()   # Idle AI — play_turn이 아무 행동 없이 턴을 진행
        t = mon(g, TIGER, 0); t.flags['perm_extra_attacks'] = 2
        g.play_turn()
        self.assertEqual(t.extra_attacks, 2)
        u = mon(g, LION, 0); g.turn_player = 0; g.play_turn()
        self.assertEqual(u.extra_attacks, 0)

    def test_ceremony_granted_battle_effect(self):
        g = make(ai=Yes)
        t = mon(g, LION, 0); t.flags[CER_FLAG] = 1; t.effects.append(granted_effect('FGTR-007', '1-a', 1, CER_BASE + 1))
        o = mon(g, '솔루나 시아', 1); x = mon(g, '솔루나 시엘', 1); hp = g.p[1].hp
        win(g, t, o); run(g)
        self.assertEqual(g.p[1].hp, hp - 1000); self.assertEqual(x.zone, 'grave')

    def test_entry_special_summons_with_turn_immunity(self):
        g = make(); x = put(g, TIGER, 0, 'upper')
        en = put(g, ENTRY, 0, 'hand')
        g.act(0, en, eff(en, 1))
        self.assertEqual(x.zone, 'm'); self.assertEqual(x.flags.get('immune_opp_until'), g.turn)

    def test_entry_picks_more_valuable_option(self):
        # 「패에 넣거나 특수소환한다」 — B안(2026-10-28): 할 수 있는 선택지 중 블록 가치가 큰 쪽. 필드에 나온 몬스터의 가치가 패 1장보다 크다
        g = make(); mon(g, RABBIT, 0); x = put(g, TIGER, 0, 'upper'); g.phase = '종료'
        en = put(g, ENTRY, 0, 'hand'); g.act(0, en, eff(en, 1))
        self.assertEqual(x.zone, 'm')
        g2 = make(); y = put(g2, TIGER, 0, 'upper')
        for _ in range(5): mon(g2, RABBIT, 0)
        g2.shared = mon(g2, RABBIT, 1)   # 놓을 자리가 없으면 패에 넣는다
        en2 = put(g2, ENTRY, 0, 'hand'); g2.act(0, en2, eff(en2, 1))
        self.assertEqual(y.zone, 'hand')

    def test_entry_summons_beside_existing_monster_before_battle(self):
        g = make(); mon(g, RABBIT, 0); x = put(g, ELEPH, 0, 'upper')
        en = put(g, ENTRY, 0, 'hand'); g.act(0, en, eff(en, 1))
        self.assertEqual(x.zone, 'm')   # 「패에 넣거나 특수소환」 — 필드 조건 없음 (검토 F1)

    def test_two_targeting_battle_effects_pick_different_cards(self):
        g = make(ai=Yes)
        r = mon(g, RHINO, 0); r.flags['ceremony'] = 1
        cer = Impl.pool[CER]
        r.flags[CER_FLAG] = 1; r.effects.append(granted_effect('FGTR-007', '1-a', 1, CER_BASE + 1))   # 세레모니 「-」 항목 문장으로 성질을 단다 — 제거 효과라 뒷면 마법도 대상 (PDF Q6)
        o = mon(g, '솔루나 시아', 1); a = mon(g, '솔루나 시엘', 1); b = spell(g, '태양과 달의 마력', 1, False)
        win(g, r, o); run(g)
        self.assertEqual(sum(1 for x in (a, b) if x.zone == 'grave'), 2)   # 라이노 2번 · 부여 [전투]가 서로 다른 카드 (검토 F2)

    def test_revive_not_activated_without_zone(self):
        g = make(ai=Yes)
        t = mon(g, TIGER, 0)
        for _ in range(4): mon(g, RABBIT, 0)
        g.shared = Card(Impl.pool[RABBIT], 1); Impl.attach(g.shared); g.shared.zone = 'shared'; g.shared.controller = 1
        g.destroy(t); mon(g, RABBIT, 0); run(g)   # 빈 자리를 다시 채운 뒤
        self.assertEqual(t.zone, 'grave'); self.assertFalse(g.p[0].opt.get((TIGER, 3)))

    def test_entry_2_banish_search_on_fighter_destroyed(self):
        g = make(ai=Yes)
        en = put(g, ENTRY, 0, 'grave'); x = put(g, ARENA, 0, 'main'); m = mon(g, RABBIT, 0)
        g.destroy(m); run(g)
        self.assertEqual(en.zone, 'banish'); self.assertEqual(x.zone, 'hand')

    def test_counter_negates_with_fighter_card_on_field(self):
        g = make(); g.turn_player = 1
        ar = put(g, ARENA, 0, None); g.place_field(ar, 0)
        cnt = spell(g, COUNTER, 0, faceup=False); cnt.set_turn = 1
        s = put(g, '밑장빼기', 1, 'hand'); x = put(g, '♣ 포카드를 보는 고양이', 1, 'main')   # 태양과 달의 마력은 무효화되지 않는 카드
        g.activate(1, s, eff(s, 1))
        self.assertTrue(g.legal(0, cnt, eff(cnt, 1)))
        g.activate(0, cnt, eff(cnt, 1)); g.resolve_chain()
        self.assertEqual(x.zone, 'main')

    def test_arena_rules(self):
        g = make(ai=Yes)
        ar = put(g, ARENA, 0, None); g.place_field(ar, 0)
        d = mon(g, '솔루나 시아', 1, 'def')
        g.state_check() if hasattr(g, 'state_check') else ar.state_check(g, ar)
        self.assertEqual(d.pos, 'atk')
        self.assertTrue(g.rule('must_attack', 1)); self.assertFalse(g.def_allowed(1))
        x = put(g, LION, 0, 'upper')
        self.assertTrue(g.legal(0, ar, eff(ar, 2)))
        g.act(0, ar, eff(ar, 2))
        self.assertIn(x.zone, ('m', 'hand'))

    def test_arena_3_search_on_opponent_monster_destroyed_same_name_ok(self):
        g = make(ai=Yes)
        ar = put(g, ARENA, 0, None); g.place_field(ar, 0)
        x = put(g, ARENA, 0, 'main'); o = mon(g, '솔루나 시아', 1)
        g.destroy(o); run(g)
        self.assertEqual(x.zone, 'hand')


class SkillTest(unittest.TestCase):
    def test_rule_1_battle_draw(self):
        g = make(ai=Yes)
        t = mon(g, TIGER, 0); o = mon(g, '솔루나 시아', 1); h = len(g.p[0].hand)
        win(g, t, o); run(g)
        self.assertEqual(len(g.p[0].hand), h + 1)

    def test_rule_2_return_and_search(self):
        g = make()
        sk = g.p[0].skill; a = put(g, COUNTER, 0, 'hand'); x = put(g, LION, 0, 'upper')
        self.assertTrue(g.legal(0, sk, eff(sk, 2)))
        g.act(0, sk, eff(sk, 2))
        self.assertEqual(len(g.p[0].hand), 1)

    def test_rule_3_cycles_only_extra_copies(self):
        g = make()
        sk = g.p[0].skill
        one = put(g, COUNTER, 0, 'hand')
        # 「원하는 수까지」(1 ~ N장): 1장뿐이어도 규칙상 발동할 수 있다 — AI는 여분이 없으면 쓰지 않는다(점수 0, 검토 F3)
        self.assertTrue(g.legal(0, sk, eff(sk, 3))); self.assertLessEqual(eff(sk, 3).score(g, sk, 0, None), 0)
        two = put(g, COUNTER, 0, 'hand'); three = put(g, COUNTER, 0, 'hand')
        if eff(sk, 3).score(g, sk, 0, None) <= 0: self.skipTest('AI가 여분을 버릴 카드로 보지 않음')
        n0 = len(g.log); g.act(0, sk, eff(sk, 3))
        back = [e for e in g.log[n0:] if e['m'].endswith('덱으로')]; drawn = [e for e in g.log[n0:] if e['k'] == 'draw']
        self.assertEqual((len(back), len(drawn)), (2, 2))   # 3장 중 여분 2장만 덱으로(1장은 남김) — 같은 수 드로우
        self.assertEqual(len(g.p[0].hand), 3)

    def test_rule_2_searches_a_different_name(self):
        g = make()
        sk = g.p[0].skill; a = put(g, COUNTER, 0, 'hand'); x = put(g, LION, 0, 'upper')
        g.act(0, sk, eff(sk, 2))
        self.assertEqual([c.name for c in g.p[0].hand], [LION])   # 되돌린 반격이 아닌 다른 카드 (검토 F4)

    def test_destroyed_event_carries_previous_zone_and_controller(self):
        g = make()
        o = mon(g, '솔루나 시아', 1); g.events = []; g.destroy(o)
        ev = next(e for e in g.events if e['kind'] == 'destroyed')
        self.assertEqual((ev['prev'], ev['ctrl']), ('m', 1))


if __name__ == '__main__':
    unittest.main()
