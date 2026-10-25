"""데이터버그 23종 (cards10) 테스트 (nny_sim 폴더에서):  python3 -m unittest test_theme_databug -v
손패 트리거 연쇄 · 1턴 1번(카드명) · [소환] · 서치/특수소환 같은 이름 규칙 · 소환 절차(더 바이러스 · 더 딜리트) · 소환 무효 근사 ·
콜로니 발동 제한 · 버터플라이 효과 대미지 내성 · 더 딜리트 덱→패 금지 · 패키지 프로그램 추가 일반소환 · 공유 존 훅"""
import random, unittest
import season as SE
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card
import cards10 as D

DECKS = SE.load_decks()
ME = '데이터버그 패키지 프로그램'
KILLER = '매수당한 킬러'


class Idle(HeuristicAI):
    """아무 것도 하지 않는 AI (강제 트리거만) — 테스트가 직접 조작한다"""
    def respond(self, g, p, opts): return None
    def choose_triggers(self, g, p, cands): return [(c, e, ev) for c, e, ev in cands if e.mandatory]
    def main_phase(self, g, p, ph): return None
    def battle_phase(self, g, p): return None
    def mulligan(self, g, p, hand): return []


class Yes(Idle):
    """임의 트리거도 모두 발동 (후보 순서대로)"""
    def choose_triggers(self, g, p, cands): return list(cands)


def make(ai=Idle, seed=5):
    """데이터버그 미러, 3턴 A(0)의 진행 단계. 패 · 덱 · 묘지는 비운다 (테스트가 채운다)"""
    d = DECKS[ME]
    g = Game([dict(d, 이름='A'), dict(d, 이름='B')], [ai(ME), ai(ME)], 0, random.Random(seed), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'; g.events = []
    for p in (0, 1):
        for z in ('hand', 'main', 'upper', 'grave'): getattr(g.p[p], z).clear()
    return g


def put(g, name, owner, zone):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone
    if zone in ('hand', 'grave', 'main', 'upper', 'banish'): getattr(g.p[owner], zone).append(c)
    return c


def mon(g, name, owner, pos='atk'):
    c = put(g, name, owner, None); g.place_monster(c, owner, pos, allow_shared=False); return c


def spell(g, name, owner, faceup=True):
    c = put(g, name, owner, None); g.place_spell(c, owner, faceup); return c


def eff(c, num): return next(e for e in c.effects if e.num == num)


def run(g):
    g.triggers()
    if g.chain: g.resolve_chain()


def names(cs): return sorted(x.name for x in cs)


# ═══════════════════════ 손패 트리거 · [소환] ═══════════════════════
class HandTrapTest(unittest.TestCase):
    def test_hand_ss_chain_once_per_card_name_and_ant_summons_ants(self):
        g = make(Yes)
        a1 = put(g, D.ANT, 0, 'hand'); a2 = put(g, D.ANT, 0, 'hand'); h = put(g, D.HERC, 0, 'hand')
        a3 = put(g, D.ANT, 0, 'upper')
        x = put(g, D.CATER, 0, 'hand'); g.special_summon(x, 0)
        run(g)
        self.assertTrue(g.on_field(h))
        self.assertEqual(sum(1 for c in (a1, a2) if g.on_field(c)), 1)      # 같은 이름 손패 트리거는 1턴에 1번
        self.assertEqual(sum(1 for c in (a1, a2) if c.zone == 'hand'), 1)
        self.assertTrue(g.on_field(a3))                                        # 앤트 2번: 덱의 앤트 특수소환 (자기 이름 → 같은 이름 예외)

    def test_own_field_only_hand_trap(self):
        g = make(Yes)
        q = put(g, D.QUEEN, 0, 'hand'); h = put(g, D.HERC, 0, 'hand')
        x = put(g, D.CATER, 1, 'hand'); g.special_summon(x, 1)
        ev = g.events[-1]
        self.assertFalse(g.legal(0, q, eff(q, 3), ev))   # 퀸 비 3번: 「자신 필드에」
        self.assertTrue(g.legal(0, h, eff(h, 2), ev))    # 헤라클레스 2번: 「필드에」(서로)

    def test_little_bug_summon_ss_main_deck_and_search(self):
        g = make(Yes)
        for n in (D.CATER, D.LITTLE, D.FLY): put(g, n, 0, 'main')
        lb = put(g, D.LITTLE, 0, 'hand')
        g.normal_summon(lb, 0); g.after_action(0)
        cat = next(c for c in g.monsters(0) if c.name == D.CATER)
        self.assertTrue(g.on_field(cat))                                          # 1번: 메인 덱에서 특수소환 (캐터필러 우선)
        self.assertTrue(any(c.name == D.FLY for c in g.monsters(0)))             # 2번 서치 → 플라이 1번으로 바로 특수소환
        self.assertEqual([c.name for c in g.p[0].main], [D.LITTLE])              # 같은 이름은 고르지 않음

    def test_fly_added_to_hand_or_drawn(self):
        g = make(Yes)
        put(g, D.COLONY, 0, 'main'); fly = put(g, D.FLY, 0, 'main')
        g.to_hand(fly); run(g)
        self.assertTrue(g.on_field(fly))
        self.assertEqual(names(g.p[0].hand), [D.COLONY])                         # 「데이터버그」 마법 서치
        g2 = make(Yes)
        f2 = put(g2, D.FLY, 0, 'main')
        g2.draw(0, 1, 'main'); run(g2)
        self.assertTrue(g2.on_field(f2))                                         # 드로우도 「패에 넣어졌을 때」

    def test_fly_second_effect_yields_to_first(self):
        g = make()
        fly = put(g, D.FLY, 0, 'main'); g.to_hand(fly)
        x = put(g, D.CATER, 0, 'hand'); g.special_summon(x, 0)
        g.cur_evs = list(g.events)
        sev = next(e for e in g.events if e['kind'] == 'summon')
        self.assertLess(eff(fly, 2).score(g, fly, 0, sev), 0)                   # 같은 묶음에서 1번이 특수소환 + 서치

    def test_worm_summon_revives_and_wasp_too(self):
        g = make(Yes)
        cat = put(g, D.CATER, 0, 'grave'); w = put(g, D.WORM, 0, 'hand')
        g.special_summon(w, 0); run(g)
        self.assertTrue(g.on_field(cat))

    def test_queen_bee_summon_search(self):
        g = make(Yes)
        put(g, D.LITTLE, 0, 'main'); q = put(g, D.QUEEN, 0, 'hand')
        g.special_summon(q, 0); run(g)
        self.assertTrue(any(c.name == D.LITTLE for c in g.p[0].hand + g.monsters(0)))


# ═══════════════════════ 기동 · 신속 ═══════════════════════
class IgnitionTest(unittest.TestCase):
    def test_caterpillar_release_two_searches_not_same_name(self):
        g = make()
        for n in (D.LITTLE, D.COLONY, D.CATER): put(g, n, 0, 'main')
        c = mon(g, D.CATER, 0)
        self.assertTrue(g.legal(0, c, eff(c, 1)))
        g.act(0, c, eff(c, 1))
        self.assertEqual(c.zone, 'grave')
        self.assertEqual(names(g.p[0].hand), sorted([D.LITTLE, D.COLONY]))

    def test_cocoon_release_and_hand_swap(self):
        g = make()
        for n in (D.HERC, D.DWORM, D.ANT): put(g, n, 0, 'upper')
        co = mon(g, D.COCOON, 0)
        g.act(0, co, eff(co, 1))
        self.assertEqual(len(g.p[0].hand), 2)
        self.assertTrue(all(x.deck_kind() == '상급' for x in g.p[0].hand))
        g2 = make(Yes)
        put(g2, D.HERC, 0, 'upper'); co2 = put(g2, D.COCOON, 0, 'hand')
        x = put(g2, D.CATER, 1, 'hand'); g2.special_summon(x, 1); run(g2)   # 상대 필드의 데이터버그 소환에도 발동
        self.assertEqual(co2.zone, 'main')
        self.assertEqual(names(g2.p[0].hand), [D.HERC])

    def test_evolution_master_unlimited_and_hand_swap(self):
        g = make()
        for n in (D.LITTLE, D.FLY): put(g, n, 0, 'main')
        evo = mon(g, D.EVO, 0)
        f1 = mon(g, D.FLY, 0); f2 = mon(g, D.CATER, 0); l1 = mon(g, D.FLY, 0); l2 = mon(g, D.LITTLE, 0)
        g.p[0].opt[(D.CATER, 1)] = 1                          # 캐터필러 1번은 이미 씀 (남은 효과 없는 0/0)
        g.act(0, evo, eff(evo, 1))
        self.assertEqual({f1.zone, f2.zone}, {'grave'})        # 가치가 낮은 쪽부터 릴리스 (에볼루션 자신은 뒤로)
        self.assertTrue(g.legal(0, evo, eff(evo, 1)))           # 횟수 제한 없음
        g.act(0, evo, eff(evo, 1))
        self.assertEqual(l1.zone, 'grave'); self.assertTrue(g.on_field(l2) != g.on_field(evo))
        self.assertEqual(len(g.p[0].hand), 2)

    def test_ant_discard_search_upper_not_ant(self):
        g = make()
        put(g, D.ANT, 0, 'upper'); put(g, D.HERC, 0, 'upper')
        a = put(g, D.ANT, 0, 'hand')
        g.act(0, a, eff(a, 1))
        self.assertEqual(a.zone, 'grave'); self.assertEqual(names(g.p[0].hand), [D.HERC])

    def test_worm_quick_from_hand(self):
        g = make()
        put(g, D.LITTLE, 0, 'main')
        cat = mon(g, D.CATER, 0); w = put(g, D.WORM, 0, 'hand')
        self.assertTrue(g.legal(0, w, eff(w, 1)))
        g.act(0, w, eff(w, 1))
        self.assertEqual((w.zone, cat.zone), ('grave', 'grave'))
        self.assertTrue(any(c.name == D.LITTLE for c in g.monsters(0)))

    def test_queen_bee_release_two_for_spell(self):
        g = make()
        put(g, D.COLONY, 0, 'main')
        q = mon(g, D.QUEEN, 0); f1 = mon(g, D.FLY, 0); f2 = mon(g, D.FLY, 0)
        g.act(0, q, eff(q, 2))
        self.assertEqual((f1.zone, f2.zone), ('grave', 'grave')); self.assertTrue(g.on_field(q))
        self.assertEqual(names(g.p[0].hand), [D.COLONY])

    def test_union_master_atk_and_revive(self):
        g = make()
        u = mon(g, D.UNION, 0); f = mon(g, D.FLY, 0); lb = mon(g, D.LITTLE, 0)
        spell(g, D.COLONY, 0); spell(g, D.RAID, 0, faceup=False)        # 세트 카드는 세지 않음
        o = mon(g, KILLER, 1)
        self.assertEqual(g.atk(u), 2000 + 400); self.assertEqual(g.atk(f), 300 + 400)
        self.assertEqual(g.atk(o), o.base_atk())
        h = put(g, D.HERC, 0, 'grave')
        g.act(0, u, eff(u, 1))
        self.assertEqual((f.zone, lb.zone), ('grave', 'grave'))
        self.assertTrue(g.on_field(h))

    def test_digital_worm_both_destroys(self):
        g = make()
        dw = mon(g, D.DWORM, 0); o1 = mon(g, KILLER, 1); o2 = mon(g, D.FLY, 1)
        g.act(0, dw, eff(dw, 1))
        self.assertEqual(o1.zone, 'grave')                      # 가치가 높은 카드
        f = mon(g, D.FLY, 0)
        g.act(0, dw, eff(dw, 2))
        self.assertEqual((f.zone, o2.zone), ('grave', 'grave'))
        self.assertTrue(g.on_field(dw))


# ═══════════════════════ 전투 · 대응 ═══════════════════════
class BattleRespTest(unittest.TestCase):
    def test_hercules_battle_destroy_damage_extra_attack(self):
        g = make(Yes); g.phase = '전투'
        h = mon(g, D.HERC, 0); t = mon(g, D.CATER, 1); o2 = mon(g, KILLER, 1)
        g.attack(h, t)
        self.assertEqual(t.zone, 'grave'); self.assertEqual(o2.zone, 'grave')
        self.assertEqual(g.p[1].hp, 5000 - 2500 - 1000)
        self.assertEqual(h.extra_attacks, 1)

    def test_butterfly_negates_and_blocks_opponent_effect_damage(self):
        g = make()
        b = mon(g, D.BUTTER, 0); dw = mon(g, D.DWORM, 1)
        g.src = dw; g.damage(0, 500, dw.name); g.src = None
        self.assertEqual(g.p[0].hp, 4500)                      # 「데이터버그」 마법이 없으면 받는다
        spell(g, D.LOADING, 0)
        g.src = dw; g.damage(0, 500, dw.name); g.src = None
        self.assertEqual(g.p[0].hp, 4500)                      # 상대의 효과 대미지를 받지 않음
        g.damage(0, 300, dw.name)                              # 처리 중인 효과 없음 · 출처가 상대 카드 이름
        self.assertEqual(g.p[0].hp, 4500)
        g.battle_damage(0, 300, '전투')
        self.assertEqual(g.p[0].hp, 4200)                      # 전투 대미지는 받는다
        g.src = b; g.damage(0, 100, b.name); g.src = None
        self.assertEqual(g.p[0].hp, 4100)                      # 자신의 효과
        g.turn_player = 1
        l = g.activate(1, dw, eff(dw, 1))
        self.assertTrue(g.legal(0, b, eff(b, 1), g.chain))
        g.activate(0, b, eff(b, 1)); g.resolve_chain()
        self.assertTrue(l.negated); self.assertTrue(g.on_field(b))

    def test_wasp_negates_activation_and_sends_continuous_spell(self):
        g = make()
        w = mon(g, D.WASP, 0)
        g.turn_player = 1
        col = put(g, D.COLONY, 1, 'hand')
        l = g.activate(1, col, eff(col, 0))
        self.assertTrue(g.legal(0, w, eff(w, 2), g.chain))
        g.activate(0, w, eff(w, 2)); g.resolve_chain()
        self.assertTrue(l.negated); self.assertEqual(col.zone, 'grave')


# ═══════════════════════ 더 바이러스 · 더 딜리트 ═══════════════════════
class BossTest(unittest.TestCase):
    def test_virus_procedure_is_not_an_activation(self):
        g = make()
        for n in (D.FLY, D.FLY): mon(g, n, 0)
        v = put(g, D.VIRUS, 0, 'hand')
        self.assertFalse(g.legal(0, v, eff(v, 1)))              # 몬스터 2장 — 불가
        ms = [mon(g, D.CATER, 0)] + list(g.monsters(0))
        g.act_limit[0] = (g.turn, 0)                            # 비비안 제한: 발동은 막혀도 소환 절차는 가능
        self.assertTrue(g.legal(0, v, eff(v, 1)))
        seen = []; fl = lambda g_, ev: seen.append(ev['kind']); g.floating.append(fl)
        g.act(0, v, eff(v, 1))
        self.assertTrue(g.on_field(v)); self.assertTrue(all(m.zone == 'grave' for m in ms))
        self.assertNotIn('activate', seen); self.assertIn('summon', seen)
        self.assertEqual(g.act_count.get((0, g.turn), 0), 0)
        self.assertTrue(v.flags.get('no_normal'))
        v2 = put(g, D.VIRUS, 0, 'grave')
        self.assertNotIn(v2, D.gy_mons(g, 0))                   # 다른 카드의 효과로 소환할 수 없다

    def test_virus_summon_negation_cancels_summon_effect(self):
        g = make(Yes)
        g.turn_player = 1
        v = mon(g, D.VIRUS, 0)
        put(g, D.LITTLE, 1, 'main'); q = put(g, D.QUEEN, 1, 'hand')
        g.special_summon(q, 1); run(g)
        self.assertEqual(q.zone, 'grave')
        self.assertEqual([c.name for c in g.p[1].main], [D.LITTLE])   # 퀸 비 [소환] 서치는 처리되지 않음
        self.assertEqual(g.p[1].opt.get((D.QUEEN, 1), 0), 0)        # 사용 횟수 반환
        self.assertTrue(g.on_field(v))

    def test_virus_negates_and_destroys(self):
        g = make()
        v = mon(g, D.VIRUS, 0); t = mon(g, D.CATER, 0); dw = mon(g, D.DWORM, 1)
        g.turn_player = 1
        l = g.activate(1, dw, eff(dw, 1))
        self.assertTrue(g.legal(0, v, eff(v, 3), g.chain))
        g.activate(0, v, eff(v, 3)); g.resolve_chain()
        self.assertTrue(l.negated); self.assertEqual(dw.zone, 'grave'); self.assertTrue(g.on_field(t))

    def test_delete_destroy_trigger_and_no_deck_to_hand(self):
        g = make(Yes)
        d = mon(g, D.DELETE, 0); a = mon(g, D.CATER, 1); b = mon(g, KILLER, 1)
        g.destroy(a); run(g)
        self.assertEqual(b.zone, 'grave'); self.assertTrue(g.on_field(d))
        f = put(g, D.FLY, 1, 'main')
        self.assertEqual(g.search_cands(1, lambda x: True), [])
        g.to_hand(f); self.assertEqual(f.zone, 'main')                 # 상대는 효과로 덱에서 패에 넣을 수 없다
        mon(g, D.BUTTER, 1); spell(g, D.LOADING, 1)                    # 버터플라이 2번: 그 플레이어는 받지 않는다
        self.assertEqual(g.search_cands(1, lambda x: True), [f])

    def test_butterfly_player_immunity_needs_databug_spell(self):
        # 버터플라이 2번 (2026-10-25 텍스트): 자신 필드에 「데이터버그」 마법 카드가 존재하는 한, 자신은 상대의 효과를 받지 않는다
        g = make()
        bt = mon(g, D.BUTTER, 1); dw = mon(g, D.DWORM, 0)
        g.src = dw; hp = g.p[1].hp
        g.damage(1, 500, dw.name)
        self.assertEqual(g.p[1].hp, hp - 500)                           # 「데이터버그」 마법이 없으면 받는다
        self.assertFalse(g.player_unaffected(1, dw))
        spell(g, D.LOADING, 1, faceup=False)
        self.assertFalse(g.player_unaffected(1, dw))                    # 뒷면 마법은 세지 않는다
        spell(g, D.LOADING, 1)
        self.assertTrue(g.player_unaffected(1, dw))
        self.assertFalse(g.player_unaffected(1, bt))                    # 자신의 효과는 받는다
        g.damage(1, 500, dw.name)
        self.assertEqual(g.p[1].hp, hp - 500)                           # 상대의 효과 대미지를 받지 않는다
        self.assertFalse(g.player_unaffected(0, bt))                    # 상대 플레이어는 그대로
        g.src = None


# ═══════════════════════ 마법 ═══════════════════════
class SpellTest(unittest.TestCase):
    def test_loading_search_once_per_turn_and_release_from_both_fields(self):
        g = make()
        put(g, D.HERC, 0, 'upper'); put(g, D.ANT, 0, 'upper')
        l1 = put(g, D.LOADING, 0, 'hand'); l2 = put(g, D.LOADING, 0, 'hand')
        g.act(0, l1, eff(l1, 0))
        self.assertTrue(g.on_field(l1) and l1.faceup)
        self.assertEqual(names([x for x in g.p[0].hand if x.name != D.LOADING]), [D.ANT])
        self.assertTrue(g.legal(0, l2, eff(l2, 0)))   # 카드의 발동 자체는 1턴 1번이 아니다 (검토 2026-10-13)
        g.act(0, l2, eff(l2, 0))
        self.assertTrue(g.on_field(l2))
        self.assertEqual(names([x for x in g.p[0].hand]), [D.ANT])   # 같은 턴 두 번째 발동: 1번 서치 없음
        g.turn += 2; g.p[0].opt = {}
        l3 = put(g, D.LOADING, 0, 'hand')
        g.act(0, l3, eff(l3, 0))
        self.assertEqual(names([x for x in g.p[0].hand]), sorted([D.ANT, D.HERC]))
        put(g, D.LITTLE, 0, 'main')
        o1 = mon(g, D.FLY, 1); o2 = mon(g, D.CATER, 1); own = mon(g, D.FLY, 0)
        g.act(0, l1, eff(l1, 2))
        self.assertEqual((o1.zone, o2.zone), ('grave', 'grave')); self.assertTrue(g.on_field(own))   # 상대 데이터버그부터 릴리스
        self.assertIn(D.LITTLE, names(g.p[0].hand))

    def test_backup_resummons_and_fetches_same_name(self):
        g = make()
        put(g, D.LITTLE, 0, 'main'); put(g, D.CATER, 0, 'main')
        lb = mon(g, D.LITTLE, 0); bk = put(g, D.BACKUP, 0, 'hand')
        g.act(0, bk, eff(bk, 1))
        self.assertTrue(g.on_field(lb)); self.assertEqual(lb.summon_turn, g.turn)
        self.assertEqual(names(g.p[0].hand), [D.LITTLE]); self.assertEqual(bk.zone, 'grave')
        g2 = make()
        v = mon(g2, D.VIRUS, 0); bk2 = put(g2, D.BACKUP, 0, 'hand')
        g2.act(0, bk2, eff(bk2, 1))
        self.assertEqual(v.zone, 'grave')                                # 더 바이러스는 다시 특수소환할 수 없다

    def test_download_summon_then_grave_still_triggers_hand(self):
        g = make(Yes)
        put(g, D.CATER, 0, 'main'); put(g, D.LITTLE, 0, 'main')
        h = put(g, D.HERC, 0, 'hand'); dl = put(g, D.DOWNLOAD, 0, 'hand')
        g.act(0, dl, eff(dl, 1))
        self.assertEqual(names(g.p[0].grave), sorted([D.DOWNLOAD, D.LITTLE]))
        self.assertTrue(g.on_field(h))
        self.assertEqual([c.name for c in g.p[0].main], [D.CATER])

    def test_aroma_discards_then_revives(self):
        g = make()
        put(g, D.CATER, 0, 'grave')
        dw = put(g, D.DWORM, 0, 'hand'); put(g, D.COCOON, 0, 'hand'); ar = put(g, D.AROMA, 0, 'hand')
        g.p[0].opt[(D.DWORM, 3)] = 1                                     # 이번 턴 패에서 나올 수 없는 디지털 웜
        g.act(0, ar, eff(ar, 1))
        self.assertTrue(g.on_field(dw))                                  # 버리고 되살림
        self.assertEqual(names(g.p[0].hand), [D.COCOON])

    def test_raid_cost_destroy_then_revive_two(self):
        g = make()
        f = mon(g, D.FLY, 0); c = mon(g, D.CATER, 0); k = mon(g, KILLER, 1)
        h = put(g, D.HERC, 0, 'grave'); r = put(g, D.RAID, 0, 'hand')
        g.act(0, r, eff(r, 1))
        self.assertEqual(k.zone, 'grave')
        self.assertTrue(g.on_field(h)); self.assertEqual(len(g.monsters(0)), 2)
        g2 = make()   # 서로의 필드: 상대 「데이터버그」도 코스트 — 단 파괴할 상대 카드 1장은 남긴다
        own = mon(g2, D.FLY, 0); mon(g2, D.CATER, 0); o1 = mon(g2, D.LITTLE, 1); o2 = mon(g2, D.FLY, 1); r2 = put(g2, D.RAID, 0, 'hand')
        g2.act(0, r2, eff(r2, 1))
        self.assertEqual((o1.zone, o2.zone), ('grave', 'grave'))         # o1 코스트 · o2 파괴 (또는 반대)
        g3 = make()
        mon(g3, D.FLY, 0); o3 = mon(g3, D.LITTLE, 1); r3 = put(g3, D.RAID, 0, 'hand')
        self.assertFalse(g3.legal(0, r3, eff(r3, 1)))                     # 상대의 유일한 카드를 코스트로 쓰면 파괴할 카드가 없다

    def test_revenge_on_opponent_effect(self):
        g = make(Yes)
        lb = mon(g, D.LITTLE, 0); rv = put(g, D.REVENGE, 0, 'hand')
        k = mon(g, KILLER, 1); h = put(g, D.HERC, 0, 'grave')
        g.src = k; g.send_grave(lb); g.src = None
        run(g)
        self.assertEqual(k.zone, 'grave'); self.assertTrue(g.on_field(h)); self.assertEqual(rv.zone, 'grave')
        g2 = make(Yes)
        lb2 = mon(g2, D.LITTLE, 0); rv2 = put(g2, D.REVENGE, 0, 'hand')
        g2.src = lb2; g2.send_grave(lb2); g2.src = None
        run(g2)
        self.assertEqual(rv2.zone, 'hand')                               # 자신의 효과로는 발동하지 않음

    def test_colony_summoned_monster_cannot_activate_this_turn(self):
        g = make()
        col = spell(g, D.COLONY, 0); mon(g, D.FLY, 0); mon(g, KILLER, 1)
        dw = put(g, D.DWORM, 0, 'upper')
        g.act(0, col, eff(col, 1))
        self.assertTrue(g.on_field(dw))
        self.assertFalse(g.legal(0, dw, eff(dw, 1)))
        g.turn += 1
        self.assertTrue(g.legal(0, dw, eff(dw, 1)))
        g.turn -= 1
        g.to_hand(dw)
        self.assertNotIn('no_act_until', dw.flags)                       # 필드를 벗어나면 풀린다
        g2 = make(Yes)
        col2 = spell(g2, D.COLONY, 0); mon(g2, D.FLY, 0)
        q = put(g2, D.QUEEN, 0, 'upper'); put(g2, D.VIRUS, 0, 'upper')   # 더 바이러스는 콜로니로 특수소환할 수 없다
        g2.act(0, col2, eff(col2, 1))
        self.assertTrue(g2.on_field(q))
        self.assertEqual(g2.p[0].hand, [])                                # 퀸 비 [소환](서치) 발동 불가


# ═══════════════════════ 스킬 ═══════════════════════
class SkillTest(unittest.TestCase):
    def test_package_program_extra_normal_with_six(self):
        g = make()
        for n in (D.FLY, D.FLY, D.CATER, D.LITTLE, D.LITTLE): mon(g, n, 0)
        sk = g.p[0].skill
        self.assertFalse(g.legal(0, sk, eff(sk, 1)))
        x = put(g, D.CATER, 0, None); g.shared = x; x.zone = 'shared'; x.controller = 0; g.shared_owner = 0
        self.assertTrue(g.legal(0, sk, eff(sk, 1)))
        g.p[0].normal_summons = 0
        self.assertFalse(g.can_normal(0))
        g.act(0, sk, eff(sk, 1))
        self.assertTrue(g.can_normal(0)); self.assertEqual(g.extra_normal_left(0), 1)
        g.turn += 1
        self.assertEqual(g.extra_normal_left(0), 0)

    def test_shared_zone_hook_for_sixth_monster(self):
        g = make()
        for n in (D.FLY, D.FLY, D.CATER, D.LITTLE, D.LITTLE): mon(g, n, 0)
        x = put(g, D.CATER, 0, 'hand')
        sk = g.p[0].skill
        self.assertIsNone(sk.wants_shared(g, 0, x))                     # 패에 제물 소환할 몬스터 없음
        put(g, D.HERC, 0, 'hand')
        self.assertTrue(sk.wants_shared(g, 0, x))
        self.assertTrue(g.p[0].ai.use_shared(g, 0, x, full=True))
        g.special_summon(x, 0)
        self.assertEqual(x.zone, 'shared')


if __name__ == '__main__':
    unittest.main()
