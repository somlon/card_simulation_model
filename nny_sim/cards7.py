"""카드 구현 7차: 호박옥 23종 (카드 자료 2026-10-08, 호박옥 AMBR-001~018 + 봉인을 푸는 자 UNSL-001~005)
스킬이 라운드 시작 시 에이스(아우렘 티라누스 · 녹스 솜니페르)를 필드에 내고, 봉인 카운터를 유지하는 동안 에이스가 완전 내성을 갖는 테마.
봉인 카운터를 늘리는 카드([소환] · [유언] · 각성의 태동 등)와, 카운터를 써서 효과를 내는 카드(아우렘 4번 · 균열 · 황금봉랍 · 월식)가 맞물린다.

구현 방식:
- 「이 카드에 봉인 카운터가 놓여 있는 한」 [지속]은 callable 플래그(Game.flag)로 그때그때 계산한다 — 앞면이고 카운터가 1개 이상일 때만 켜진다.
  무효 상태는 엔진이 따로 거른다(immune · releasable는 is_neg를 본다). 「전투로는 / 효과로 파괴되지 않는다」는 rules['indestructible'].
- 대상 지정: 엔진에 대상/비대상 구분이 없으므로, 이 코드베이스의 관례(「대상으로 하고」는 코스트 단계에서 골라 l.ctx에 넣는다)를 그대로
  기준으로 쓴다 — 발동 시(코스트 단계)에 고른 카드 = 대상(engine.link_targets), 처리 시에 고르는 카드 = 대상을 지정하지 않는 효과.
  · 카르분쿨루스 「상대 효과의 대상이 되지 않는다」 = 상대의 코스트 단계 선택에서 빠진다(flags['untargetable_opp']).
  · 마르모르 「상대 카드의 대상을 지정하지 않는 효과를 받지 않는다」 = 상대 효과가 발동 시 고른 대상이 아니면 받지 않는다
    (flags['immune_opp_untargeted']; [지속] 처리 · 처리 시 「고르고」 선택 · 대상이 없는 효과 모두 받지 않음).
- 월식 「봉인 카운터의 합계가 5개 이상이 되었을 때」: 카운터 사건이 생길 때(emit) 호박옥 카드 · 스킬의 on_event가 그 순간의 합계를 사건에
  적어 둔다(amber_sum / amber_prev) — 트리거를 모으는 시점에는 합계가 이미 바뀌었을 수 있어서. 깨어남의 종의 HP도 같은 방식(hp_after).

ASSUME:
- 효과 종류 표기가 없는 효과(아우렘 4번 · 수액정 1번 · 반혼체 1번 · 태고의 수해 3번 · 봉인을 푸는 자 3번)는 기동 효과(자신 턴 진행/정비 단계 · 체인 없음).
- [소환] 효과(아우렘 · 레시나 · 실렉스 1번 등)는 「(강제)」 문구가 없으므로 임의 효과(§6-3). AI는 언제나 발동한다.
- 「상대가 효과를 발동했을 때」 [트리거](레시나 · 실렉스 3번, 황금봉랍 1번 [신속])는 체인에 대응하는 발동(resp)으로 처리한다.
- 「(이 효과는 강제로 발동한다.)」 트리거 마법(월식 · 몽마의 도래 · 깨어남의 종 · 꿈의 파열): 세트한 카드는 조건이 갖춰지면 반드시 발동하고,
  패에서는 발동 여부를 고를 수 있다(패에서 강제로 발동해야 하면 패의 꿈의 파열이 자신 필드까지 쓸어버리므로).
- 녹스 솜니페르 4번 「턴 종료 시」 = 양쪽 플레이어의 턴 종료 시(end_phase 사건). 에이스 2번 · 수호자 2번의 「릴리스되지 않는다」 등은 앞면일 때만.
- 녹스 솜니페르 4번 · 월식의 「뒷면 수비 표시로 한다」: Game.set_face_down 뒤 표시 형식을 수비로 바꾼다. 이미 뒷면 공격 표시인 상대 몬스터(월식)는
  표시 형식만 수비로 바꾼다. 뒷면이 된 몬스터의 카운터는 그대로 둔다(엔진 ASSUME).
- 마르모르 · 카르분쿨루스 1번 「필드의 릴리스 가능한 몬스터가 없는 경우, 대신 봉인 카운터 3개를 제거」: 「필드」 = 자신 필드(코스트로 릴리스하는
  「자신 필드의 몬스터」와 같은 범위), 3개는 자신 필드의 몬스터들에서 합계로 뗄 수 있다.
- 수호자 4번 [유언]의 코스트 「묘지의 「호박옥」 카드 1장」은 자신 묘지의, 이 카드 이외의 카드. 덱에서 묘지로 보내진 경우에도 발동한다(단서 없음).
- 반혼체 1번: 덱으로 되돌릴 2장은 특수소환할 몬스터를 남기도록 고르고, 특수소환할 몬스터는 처리 시에 고른다(대상 지정 없음).
- 황금봉랍 2번 「이 카드가 상대의 효과로 필드를 벗어났을 때」: 엔진상 묘지 · 패에 있을 때만 발동할 수 있다(덱 · 제외 존의 카드는 발동 불가).
  「상대의 효과」 = 상대 카드의 효과(사건의 cause가 'effect'이고 그 주체가 상대가 컨트롤하는 카드).
- 각성의 태동 「상대가 자신 필드의 카드를 필드에서 벗어나게 하는 효과를 발동했을 때」: 그 효과 번호의 처리 문장(「…발동.」 뒤)에서 「자신 필드」를
  지운 뒤 「필드」와 파괴 · 제외 · 덱으로 · 패에 넣 · 묘지로 보내 · 릴리스 · 되돌 중 하나가 있으면 그런 효과로 본다(문장 판정). 대상이 자신 필드의
  몬스터인 발동은 문장과 무관하게 해당.
- 균열 「제거한 개수만큼 필드의 카드를 고르고 파괴한다」: 정확히 그 개수(상대 카드가 모자라면 자신 카드도 — 균열 자신은 제외). AI는 넘치지 않게
  카운터 수를 고른다. 아우렘 4번은 「개수까지」이므로 상대 카드만.
- 임시 봉인 「다음 턴 종료 시까지」 = 발동한 턴의 다음 턴 종료 시까지. 「다른 카드의 효과를 받지 않는다」는 자신 · 상대 카드 모두(카운터는 내성과
  무관하게 놓인다 — 엔진 add_counter).
- 봉인을 푸는 자 1번: 덱의 「봉인을 푸는 자」 트리거 마법이 3장 미만이면 있는 만큼 보여 주고, 1장 이상이면 발동할 수 있다. 같은 이름도 보여 줄 수
  있다(서로 다른 이름을 먼저). 세트할 빈 마법 존이 없으면 발동하지 않는다. 2번(공유 존): 2장을 고르게 하고 빈 마법 존만큼 세트.
- 깨어남의 종: 녹스에 봉인 카운터가 1개 이상 있어야 발동한다(0개를 「전부 제거」하면 특수소환할 수가 0). HP가 2000 초과에서 2000 이하로
  바뀐 대미지(자해 포함)에만.
- 몽식의 계약 1번은 「발동한다」이므로 체인에 올리는 강제 트리거(game_start), 봉인의 계약 1번은 「발동」 문구가 없으므로 [지속] 처리(희생제와 같은 on_event).
- 스킬 2번 유지비: 제거는 필수(가능하면 반드시 제거), 어느 몬스터에서 뗄지는 AI가 고른다 — 보호에 필요한 1개를 남길 수 있는 몬스터부터.
  봉인의 계약 2번 「자신 필드의 몬스터」 · 몽식의 계약 2번 「자신 필드」 모두 뒷면 몬스터의 카운터도 셀 수 있다.
- 봉인의 계약 3번: 전투 대미지 절반은 1의 자리 버림(정수 나눗셈).
- 침전의 맹세 제약(「호박옥」 카드만 사용)은 발동 시 적용 — 「봉인을 푸는 자」 카드군만 가진 트리거 마법(월식 등)도 그동안 발동할 수 없다.
- 실렉스 2번 「파괴 이외의 방법으로 필드를 벗어나지 않는다」: 효과 · 코스트로 묘지 · 덱 · 패 · 제외로 보내는 것을 막는다. 규칙 처리(공유 존 마커
  페널티 · 장착 대상 이탈 등)는 막지 않는다.

- (검토 2026-10-13) 자신 턴 종료 시에는 스킬 2번 유지비(봉인 카운터 제거)가 녹스 솜니페르 4번 「턴 종료 시」 판정보다 먼저 처리된다 —
  유지비는 녹스 이외의 몬스터에서 먼저 뗀다(keep_of: 녹스 3개). 녹스만 카운터를 가지고 있으면 3개 → 2개가 되어 4번이 발동하지 않는다.
- (검토 2026-10-13) 「대상으로 하고」 판정의 시점 차이: 발동 판정은 대상 지정 여부를 모르는 상태로 보고, 코스트 단계에서 대상 지정으로 본다.
  상대 필드에 봉인된 카르분쿨루스(대상이 되지 않음)만 있을 때는 발동 판정은 통과해도 코스트에서 취소될 수 있다(AI는 같은 단계에서 다시 고르지 않음).
  임시 봉인은 이 카드를 주체로 내성을 판정한다 — 봉인된 아우렘 · 녹스(「호박옥」 카드의 효과는 받음)도 고를 수 있다.
재정 질문:
1. 「강제로 발동한다」 트리거 마법을 패에 들고 있을 때도 조건이 갖춰지면 반드시 발동해야 하는가 (지금: 세트한 카드만 강제).
2. 「대상을 지정하는 효과」의 범위 — 이 시뮬레이터는 「대상으로 하고 발동」 문구가 있는 효과만 대상 지정으로 본다. 「고르고」 효과는 비대상으로 보아
   마르모르(봉인 카운터가 있을 때)는 「상대 필드의 카드 1장을 고르고 파괴」 같은 효과를 받지 않는다. 맞는가.
3. 녹스 솜니페르 4번 「턴 종료 시」는 자신 턴만인가, 양쪽 턴 모두인가 (지금: 양쪽).
4. 봉인을 푸는 자 1번: 덱에 「봉인을 푸는 자」 트리거 마법이 3장 미만이면 발동할 수 있는가 / 같은 이름 카드를 함께 보여 줄 수 있는가.
5. 마르모르 · 카르분쿨루스 1번의 「필드의 릴리스 가능한 몬스터」는 자신 필드만인가 (지금: 자신 필드). 봉인 카운터 3개는 여러 몬스터에서 합계로 떼도 되는가.
6. 황금봉랍 2번: 상대 효과로 덱 · 제외 존으로 간 경우에도 발동하는가 (지금: 묘지 · 패만 — 엔진 제약).
7. 균열 「제거한 개수만큼」: 상대 필드의 카드가 모자라면 자신 카드도 골라 파괴해야 하는가 (지금: 그렇다).
8. 실렉스 2번이 막는 범위에 규칙 처리(공유 존 마커 페널티로 덱으로 되돌리기)도 들어가는가 (지금: 효과 · 코스트만).
9. 월식 처리 시 봉인 카운터가 5개 미만으로 줄어 있으면 — 있는 만큼 제거하고 뒷면으로 하는가 (지금: 그렇다).
10. 자신 턴 종료 시 스킬 2번 유지비와 녹스 솜니페르 4번(「봉인 카운터 3개 이상일 때 턴 종료 시」)의 처리 순서 — 지금: 유지비 먼저.
11. 상대 필드에 봉인된 카르분쿨루스(「상대 효과의 대상이 되지 않는다」) · 마르모르(「대상을 지정하지 않는 효과를 받지 않는다」)만 남았을 때
    코스트가 있는 효과를 발동할 수 있는가 — 지금: 발동 판정을 가장 엄격하게 보아 둘 다 후보에서 뺀다(마르모르를 「대상으로 하는」 효과도 발동 불가).

엔진 변경 (engine.py · ai.py · policy.py, 추가 · 플래그가 없는 카드의 동작은 그대로):
- engine.link_targets(link): 발동 시 고른 카드(=대상) 목록.
- Game.flag(c, key): callable 플래그 계산. immune(immune_except_group) · releasable(no_release) · can_change_pos(no_pos_change)가 이것으로 읽는다.
- Game.costing / Game.resolving_link(activate의 코스트 단계 · resolve_chain의 처리 중 Link), targeting_now · targeted_by,
  immune()에 flags['untargetable_opp'] · flags['immune_opp_untargeted'] 판정 추가.
- Game.stays + flags['leave_only_destroy']: send_grave(파괴 제외) · to_deck · to_hand · banish에서 확인.
- Game.attack_banned(no_attack 플래그 · no_attack_until 턴) — can_attack_with와 HeuristicAI(소환 표시 형식 · 공격자 · lethal_damage) ·
  LearnedAI(공격자)가 쓴다. 예전에는 HeuristicAI만 flags['no_attack']를 봤다.
- flags['battle_indestr_until'] · ['no_pos_change_until'] · ['no_attack_until'](턴까지, 필드를 벗어나면 지움).
- Game.battle_damage + [지속] 규칙 'half_battle_damage'(p): attack()의 전투 대미지 4곳이 이것을 거친다.
- ai.DECK_POLICY: 「호박옥 - 봉인의 계약」 · 「호박옥 - 몽식의 계약」.
"""
import re
from engine import Effect, link_targets
from cards import card, grp, best, value, own_turn, main_ok, opp_cards, oath, last_opp_link, threat, cause_card, ev_is, VETO, field_pick
from cards2 import targets

SEAL = '봉인'
AMBER = '호박옥'; UNSEAL = '봉인을 푸는 자'
AUREM = '호박옥 - 아우렘 티라누스'; NOX = '호박옥 - 녹스 솜니페르'
CONTRACT = '호박옥 - 봉인의 계약'; DREAM = '호박옥 - 몽식의 계약'
RESINA, SILEX, MARMOR, CARBUN = ('호박옥의 수호자 - 레시나', '호박옥의 수호자 - 실렉스', '호박옥의 수호자 - 마르모르', '호박옥의 수호자 - 카르분쿨루스')
GUARDS = (RESINA, SILEX, MARMOR, CARBUN)
ACES = (AUREM, NOX)
PROTECTED = ACES + GUARDS          # 봉인 카운터가 있어야 [지속] 보호가 켜지는 카드
SHARD, SAP, REVENANT, FIELD_SPELL = '호박옥 - 잔편', '호박옥 - 수액정', '호박옥 - 반혼체', '호박옥 - 태고의 수해'

AMB = lambda x: grp(x, AMBER)
AMB_MON = lambda x: grp(x, AMBER) and x.is_monster()
UNSL_TRIG = lambda x: grp(x, UNSEAL) and x.type == '마법' and x.d.get('subtype') == '트리거'


# ═══════════════════════ 봉인 카운터 공통 ═══════════════════════
def seals(c): return c.counters.get(SEAL, 0)
def sealed(c): return c.faceup and seals(c) > 0
def side_seals(g, p): return sum(seals(m) for m in g.monsters(p))
def amber_seals(g, p): return sum(seals(m) for m in g.monsters(p) if m.faceup and AMB_MON(m))
def own_faceup(g, p): return [m for m in g.monsters(p) if m.faceup]
def keep_of(m): return 3 if m.name == NOX else 1 if m.name in PROTECTED else 0   # 녹스 4번은 3개 이상일 때 — 다른 몬스터에서 먼저 뗀다


def annotate(g, src, ev):
    """[지속] 사건 기록 (발동 아님): 봉인 카운터 사건에 그 순간의 「자신 필드의 「호박옥」 몬스터에 놓인 봉인 카운터 합계」(월식),
    대미지 사건에 대미지 뒤 HP(깨어남의 종)를 적어 둔다. 같은 사건은 한 번만"""
    k = ev['kind']
    if k == 'counter' and ev.get('name') == SEAL and 'amber_sum' not in ev:
        x = ev['card']; q = x.controller
        s = amber_seals(g, q)
        ev['amber_side'] = q; ev['amber_sum'] = s
        ev['amber_prev'] = s - ev['delta'] if (AMB_MON(x) and x.faceup and g.on_field(x)) else s
    elif k == 'damage' and 'hp_after' not in ev:
        ev['hp_after'] = g.p[ev['player']].hp


def seal_pick(g, p, pool=None):
    """봉인 카운터를 놓을 몬스터 (AI): 카운터가 없어 보호가 꺼진 에이스 > 수호자 > 녹스(3개 미만) > 에이스 > 「호박옥」 > 그 밖. 상대 몬스터는 마지막"""
    cands = [m for m in (own_faceup(g, p) if pool is None else pool) if m.faceup and g.on_field(m)]
    if not cands: return None
    def key(m):
        s = seals(m); k = 0
        if m.name in PROTECTED and s == 0: k += 100 + (50 if m.name in ACES else 0)
        if m.name == NOX and s < 3: k += 60
        k += 30 if m.name in ACES else 20 if m.name in GUARDS else 10 if AMB(m) else 0
        if m.controller != p: k -= 1000
        return (k, value(g, m))
    return max(cands, key=key)


def put_seals(g, p, n, pool=None, why=''):
    t = seal_pick(g, p, pool)
    if t is None: g.L(f'{why}: 봉인 카운터를 놓을 몬스터 없음', 'sys'); return None
    g.add_counter(t, SEAL, n); return t


def pay_seals(g, p, n, pool=None):
    """봉인 카운터를 합계 n개 제거 (나누는 방법은 AI): 보호에 필요한 1개를 남기고도 남는 개수가 많은 몬스터부터, 같으면 가치가 낮은 쪽.
    반환: 실제로 제거한 개수"""
    pool = [m for m in (g.monsters(p) if pool is None else pool) if seals(m) > 0]
    left = {m.uid: seals(m) for m in pool}; plan = {}
    for _ in range(n):
        cs = [m for m in pool if left[m.uid] > 0]
        if not cs: break
        m = max(cs, key=lambda m: (left[m.uid] - keep_of(m), -value(g, m)))
        left[m.uid] -= 1; plan[m.uid] = plan.get(m.uid, 0) + 1
    got = 0
    for m in pool:
        if plan.get(m.uid): got += g.remove_counter(m, SEAL, plan[m.uid])
    return got


def upkeep_need(g, p):
    sk = g.p[p].skill
    return 2 if sk is not None and sk.name == CONTRACT else 1 if sk is not None and sk.name == DREAM else 0


def upkeep_short(g, p, keep=False):
    """자신 턴 종료 시 스킬 2번 유지비에 모자라는 봉인 카운터 수 (태고의 수해 1번이 먼저 1개 놓는 것을 셈). keep: 에이스의 1개까지 남기려면"""
    if not own_turn(g, p): return 0
    need = upkeep_need(g, p)
    if need <= 0: return 0
    have = side_seals(g, p)
    if g.fieldz is not None and g.fieldz.name == FIELD_SPELL and g.fieldz.controller == p and g.fieldz.faceup and own_faceup(g, p): have += 1
    if keep and any(m.name in ACES and m.faceup for m in g.monsters(p)): need += 1
    return max(0, need - have)


def seal_need(g, p):
    """지금 봉인 카운터를 늘릴 이유의 크기 (AI 점수)"""
    mons = own_faceup(g, p); s = 0
    if any(m.name in ACES and seals(m) == 0 for m in mons): s = max(s, 60)
    if any(m.name in GUARDS and seals(m) == 0 for m in mons): s = max(s, 35)
    if upkeep_short(g, p) > 0: s = max(s, 45)
    elif upkeep_short(g, p, keep=True) > 0: s = max(s, 25)
    if any(m.name == NOX and seals(m) < 3 for m in mons): s = max(s, 30)
    return s


def threatened(g, p):
    """체인 맨 위의 상대 발동이 노리는 자신 필드의 몬스터 (발동 시 고른 대상)"""
    l = last_opp_link(g, p)
    if l is None: return []
    return [x for x in link_targets(l) if x.controller == p and g.on_field(x) and x.is_monster()]


def seal_gain_score(g, p, spend=0):
    """봉인 카운터를 늘리는 [신속] · 대응의 점수: 보호가 꺼진 에이스 · 수호자가 상대 효과의 대상이면 크게, 아니면 자신 턴에 필요할 때만"""
    if any(x.name in PROTECTED and seals(x) == 0 and x.faceup for x in threatened(g, p)): return 75 - spend
    s = seal_need(g, p)
    if s <= 0: return 0
    if main_ok(g, p) or (own_turn(g, p) and g.phase == '종료'): return max(0, s - spend)
    return 0


def face_down_def(g, t):
    """「뒷면 수비 표시로 한다」: 앞면이면 Game.set_face_down 뒤 수비 표시로, 이미 뒷면이면 표시 형식만 수비로"""
    if not g.on_field(t) or not t.is_monster(): return False
    if t.faceup:
        if not g.set_face_down(t): return False
        t.pos = 'def'; g.L(f'{t} 뒷면 수비 표시'); return True
    if t.pos != 'def' and not g.blocked(t, ('effect', g.src)):
        t.pos = 'def'; g.L(f'{t} 뒷면 수비 표시로'); return True
    return False


_LEAVE = re.compile(r'파괴|제외|덱으로|패에 넣|패로|묘지로 보내|릴리스|되돌')

def eff_text(c, num):
    lines, on = [], False
    for x in (c.d.get('text') or '').split('\n'):
        if re.match(r'^\d+\.', x): on = x.startswith(f'{num}.')
        if on: lines.append(x)
    return ' '.join(lines)

def removes_field(link):
    """그 발동이 「필드의 카드를 필드에서 벗어나게 하는 효과」인가 — 처리 문장(「…발동.」 뒤)에서 발동한 쪽의 「자신 필드」를 지우고 판정 (ASSUME)"""
    t = eff_text(link.card, link.eff.num)
    if '발동.' in t: t = t.split('발동.', 1)[1]
    t = t.replace('자신 필드', '')
    return '필드' in t and bool(_LEAVE.search(t))


def amber_common(c):
    c.on_event = annotate


def protect_flags(c, release=True):
    amber_common(c)
    if release: c.flags['no_release'] = lambda g, x: sealed(x)


def summon_seals(n, special_only=False):
    """1번 [소환] 이 카드에 봉인 카운터를 n개 놓는다"""
    return Effect(1, 'summon', ('field',),
                  cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and (not special_only or ev['how'] == 'special'),
                  res=lambda g, c, p, l: g.on_field(c) and c.faceup and g.add_counter(c, SEAL, n),
                  score=lambda *a: 95, threat=300, label=f'[소환] 봉인 카운터 {n}')


def ace_guard(c):
    """에이스 2번 [지속]: 봉인 카운터가 놓여 있는 한 「호박옥」 카드 이외의 카드의 효과를 받지 않고, 전투로는 파괴되지 않으며, 릴리스되지 않는다"""
    protect_flags(c)
    c.flags['immune_except_group'] = lambda g, x: AMBER if sealed(x) else None
    c.rules['indestructible'] = lambda g, src, x, battle: battle and x is src and seals(src) > 0


def gy_value(g, p, x):
    """묘지에서 코스트로 제외 · 덱으로 되돌릴 때 남겨 둘 가치 (낮을수록 먼저 쓴다): 묘지 효과가 있는 카드 · 되살릴 몬스터는 남긴다"""
    v = g.p[p].ai.card_pri(g, p, x) * 0.1
    if x.name == FIELD_SPELL: v += 5
    if x.is_monster(): v += 3 + (4 if x.name == AUREM else 2 if x.name in PROTECTED else 0)
    return v


def guard_lastwill():
    """수호자 4번 [유언] 묘지의 「호박옥」 카드 1장을 제외하고 발동. 이 카드를 특수소환한다"""
    def others(g, c, p): return [x for x in g.p[p].grave if x is not c and AMB(x)]
    def cost(g, c, p, l):
        xs = others(g, c, p)
        free = [x for x in xs if not any(lk.card is x for lk in g.chain)]   # 자신의 효과가 체인에 올라 있는 카드(함께 묘지로 간 수호자)는 되도록 남긴다
        x = min(free or xs, key=lambda x: gy_value(g, p, x))
        g.L(f'코스트: 묘지의 {x} 제외'); g.banish(x, ('cost', c))
    return Effect(4, 'lastwill', ('grave',),
                  cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c and c.zone == 'grave' and bool(others(g, c, p)) and g.can_special(c, p),
                  cost=cost, res=lambda g, c, p, l: c.zone == 'grave' and g.special_summon(c, p),
                  score=lambda *a: 80, threat=500, label='[유언] 묘지 1장 제외 → 자신 특수소환')


def dump_value(g, p, x):
    """덱에서 묘지로 보낼 카드의 가치: 묘지로 가자마자 쓰이는 [유언] · 묘지 효과가 있는 카드를 우선"""
    gy_amb = sum(1 for y in g.p[p].grave if AMB(y))
    if x.name in GUARDS: return 6 if gy_amb >= 1 and g.can_place(x, p) else 1
    if x.name in (SHARD, SAP): return 5 if own_faceup(g, p) else 1
    if x.name == REVENANT: return 4
    if x.name == AUREM: return 3.5 if any(m.name == REVENANT and m.faceup for m in g.monsters(p)) else 0.5
    if x.name == FIELD_SPELL: return 3
    return 0


def dump_pick(g, p, cands):
    return max(cands, key=lambda x: (dump_value(g, p, x), -g.p[p].ai.card_pri(g, p, x)))


def forced_trigger(cond, res, sc, threat=600, label='', cost=None):
    """「(이 효과는 강제로 발동한다.)」 트리거 마법 1번: 세트한 카드는 반드시 발동, 패에서는 고를 수 있다 (ASSUME)"""
    return [Effect(1, 'trigger', ('field',), spell_act=True, mandatory=True, cond=cond, cost=cost, res=res, score=sc, threat=threat, label=label + ' (강제)'),
            Effect(1, 'trigger', ('hand',), spell_act=True, cond=cond, cost=cost, res=res, score=sc, threat=threat, label=label + ' (패에서)')]


# ═══════════════════════ 에이스 ═══════════════════════
@card(AUREM)
def _(c):
    ace_guard(c)
    lock = lambda g, x: sealed(x) and not g.is_neg(x)   # 3번 [지속]: 표시 형식 변경 · 공격 불가
    c.flags['no_pos_change'] = lock; c.flags['no_attack'] = lock
    def plan_k(g, c, p):
        ts = targets(g, p, opp_cards(g, p)); s = seals(c)
        if not ts or s <= 0: return 0
        return max(1, min(len(ts), s - 1 if s >= 2 else s))   # 내성용 1개는 되도록 남긴다
    def cost4(g, c, p, l):
        k = plan_k(g, c, p); l.ctx['k'] = g.remove_counter(c, SEAL, k)
        g.L(f'코스트: {c}의 봉인 카운터 {l.ctx["k"]}개 제거')
    def res4(g, c, p, l):
        pool = targets(g, p, opp_cards(g, p)); ch = []
        for _ in range(l.ctx.get('k', 0)):   # 「제거한 개수까지 상대 필드의 카드를 고르고」 — 처리 시 고른다(대상 지정 없음)
            t = best(g, [x for x in pool if x not in ch], p)
            if t is None: break
            ch.append(t)
        for t in ch:
            if g.on_field(t): g.destroy(t)
    def sc4(g, c, p, ev):
        ts = targets(g, p, opp_cards(g, p))
        if not ts: return VETO
        k = plan_k(g, c, p)
        vals = sorted((value(g, x) for x in ts), reverse=True)[:k]
        return 15 + 15 * sum(vals) - (25 if seals(c) - k <= 0 else 0) - 10 * upkeep_short(g, p)
    c.effects = [summon_seals(3),
                 Effect(4, 'ignition', ('field',), cond=lambda g, c, p, ev: seals(c) > 0 and bool(targets(g, p, opp_cards(g, p))),
                        cost=cost4, res=res4, score=sc4, threat=1200, label='봉인 카운터 제거 → 그 개수까지 상대 카드 파괴')]


@card(NOX)
def _(c):
    ace_guard(c)
    # 3번 [지속]: 자신 필드에 이 카드 이외의 몬스터가 없으면 상대는 자신에게 직접공격할 수 있다 (x = 공격하는 몬스터)
    c.rules['direct_attack'] = lambda g, src, x: x.controller != src.controller and not any(m is not src for m in g.monsters(src.controller))
    def cands4(g, p): return targets(g, p, [m for m in g.monsters(1 - p) if m.faceup])
    def res4(g, c, p, l):
        t = best(g, cands4(g, p), p)
        if t: face_down_def(g, t)
    c.effects = [summon_seals(1, special_only=True),
                 Effect(4, 'trigger', ('field',), mandatory=True,
                        cond=lambda g, c, p, ev: ev_is(ev, 'end_phase') and seals(c) >= 3 and bool(cands4(g, p)),
                        res=res4, score=lambda *a: 80, threat=700, label='턴 종료 시 상대 몬스터 1장 뒷면 수비 (강제)')]


# ═══════════════════════ 수호자 (상급) ═══════════════════════
def guard_resp(num, res, score, label, cond=None):
    """3번 [트리거] 상대가 효과를 발동했을 때 발동 (1턴에 2번까지)"""
    return Effect(num, 'resp', ('field',), opt=2,
                  cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and (cond is None or cond(g, c, p, ev)),
                  res=res, score=score, threat=300, label=label)


@card(RESINA)
def _(c):
    protect_flags(c)
    c.rules['indestructible'] = lambda g, src, x, battle: (not battle) and x is src and seals(src) > 0   # 2번: 효과로 파괴되지 않는다
    def all_mons(g): return [m for m in g.monsters(0) + g.monsters(1) if m.faceup]
    c.effects = [summon_seals(2),
                 guard_resp(3, lambda g, c, p, l: put_seals(g, p, 2, pool=all_mons(g), why=c.name), lambda g, c, p, ev: 60,
                            '상대 발동 → 필드의 몬스터에 봉인 카운터 2', cond=lambda g, c, p, ev: bool(all_mons(g))),
                 guard_lastwill()]


def fetch_amber(g, c, p, why):
    """「「호박옥」 카드 1장을 덱/묘지에서 패에 넣는다」 — 덱 · 묘지 후보를 합쳐 AI가 고른다 (효과 주체와 같은 이름은 제외)"""
    deck = g.search_cands(p, AMB)
    gy = [x for x in g.p[p].grave if AMB(x) and x.name != c.name]
    cands = deck + gy
    if not cands: g.L(f'{why}: 대상 없음', 'sys'); return None
    x = g.p[p].ai.pick_search(g, p, cands, why)
    from_deck = x.zone in ('main', 'upper')
    g.L(f'{g.pname(p)} {why}: {"덱" if from_deck else "묘지"}의 {x} 패에 넣음'); g.to_hand(x)
    if from_deck: g.shuffle(p)
    return x


@card(SILEX)
def _(c):
    protect_flags(c)
    c.flags['leave_only_destroy'] = lambda g, x: sealed(x)   # 2번: 파괴 이외의 방법으로 필드를 벗어나지 않는다
    c.effects = [summon_seals(2),
                 guard_resp(3, lambda g, c, p, l: fetch_amber(g, c, p, c.name), lambda g, c, p, ev: 55, '상대 발동 → 「호박옥」 덱/묘지 → 패',
                            cond=lambda g, c, p, ev: g.can_search(p, AMB) or any(AMB(x) and x.name != c.name for x in g.p[p].grave)),
                 guard_lastwill()]


def guard_ss():
    """1번 [신속] 자신 필드의 몬스터 1장을 릴리스하고 발동. 이 카드를 (패에서) 특수소환한다.
    필드의 릴리스 가능한 몬스터가 없는 경우, 대신 봉인 카운터 3개를 제거하고 소환할 수 있다"""
    def rel(g, c, p): return [m for m in g.monsters(p) if m.is_monster() and g.releasable(m)]
    def tribute_pick(g, p, cs):   # [유언]으로 봉인 카운터를 놓는 잔편 · 수액정이 가장 좋은 제물
        return min(cs, key=lambda m: (0 if m.name in (SHARD, SAP) else 1, value(g, m)))
    def cond(g, c, p, ev):
        if g.rule('no_special', c, p) or g.same_name_blocked(c): return False
        r = rel(g, c, p)
        if r: return g.can_place(c, p) or any(m.zone == 'm' for m in r)
        return side_seals(g, p) >= 3 and g.can_place(c, p)
    def cost(g, c, p, l):
        r = rel(g, c, p)
        if r:
            m = tribute_pick(g, p, r); g.L(f'코스트: {m} 릴리스'); g.tribute(m, ('cost', c))
        else:
            n = pay_seals(g, p, 3); g.L(f'코스트: 릴리스할 수 있는 몬스터가 없어 봉인 카운터 {n}개 제거')
    def sc(g, c, p, ev):
        r = rel(g, c, p)
        if r and value(g, tribute_pick(g, p, r)) >= value(g, c): return VETO   # 더 강한 몬스터를 바치지 않는다
        if not r and upkeep_short(g, p, keep=True) + 3 > 0 and side_seals(g, p) - 3 < upkeep_need(g, p) and own_turn(g, p): return 0
        if main_ok(g, p): return 55
        if not own_turn(g, p) and g.phase == '종료' and not g.chain: return 30
        return 0
    return Effect(1, 'quick', ('hand',), cond=cond, cost=cost, res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
                  score=sc, threat=800, label='릴리스(또는 봉인 카운터 3) → 패에서 특수소환')


def guard_summon3(res, label, purpose):
    """3번 [소환] 상급 덱에서 「호박옥」 몬스터를 1장 묘지로 보내고 발동 (1턴에 2번까지)"""
    def ups(g, p): return [x for x in g.p[p].upper if AMB_MON(x)]
    def pool(g, c): return [x for x in g.all_field() if x is not c and (purpose != 'negate' or (x.faceup and not g.is_neg(x)))]
    def cost(g, c, p, l):
        x = dump_pick(g, p, ups(g, p)); g.deck_to_grave(p, x, f'{c.name} 3번 코스트')
    def sc(g, c, p, ev):
        ts = targets(g, p, [x for x in pool(g, c) if x.controller != p])
        return (60 + 15 * max(value(g, x) for x in ts)) if ts else VETO
    return Effect(3, 'summon', ('field',), opt=2,
                  cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and bool(ups(g, p)) and bool(targets(g, p, pool(g, c))),
                  cost=cost, res=lambda g, c, p, l: res(g, c, p, field_pick(g, p, purpose, targets(g, p, pool(g, c)))),
                  score=sc, threat=900, label=label)


@card(MARMOR)
def _(c):
    protect_flags(c)
    c.flags['immune_opp_untargeted'] = lambda g, x: sealed(x)   # 2번: 상대 카드의 대상을 지정하지 않는 효과를 받지 않는다
    def res3(g, c, p, t):
        if t and g.on_field(t) and g.negate_card(t, c): g.L(f'{t} 턴 종료 시까지 무효')
    c.effects = [guard_ss(), guard_summon3(res3, '[소환] 상급 덱 1장 묘지로 → 필드의 카드 1장 무효', 'negate'), guard_lastwill()]


@card(CARBUN)
def _(c):
    protect_flags(c)
    c.flags['untargetable_opp'] = lambda g, x: sealed(x)   # 2번: 상대 효과의 대상이 되지 않는다
    def res3(g, c, p, t):
        if t and g.on_field(t): g.destroy(t)
    c.effects = [guard_ss(), guard_summon3(res3, '[소환] 상급 덱 1장 묘지로 → 필드의 카드 1장 파괴', 'remove'), guard_lastwill()]


# ═══════════════════════ 메인 덱 몬스터 ═══════════════════════
def seal_lastwill(num=2):
    """[유언] 자신 필드의 몬스터 1장에 봉인 카운터를 2개 놓는다"""
    return Effect(num, 'lastwill', ('grave',),
                  cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c and c.zone == 'grave' and bool(own_faceup(g, p)),
                  res=lambda g, c, p, l: put_seals(g, p, 2, why=c.name), score=lambda *a: 70, threat=300, label='[유언] 봉인 카운터 2')


@card('호박옥 - 결정충')
def _(c):
    amber_common(c)
    NONMON = lambda x: AMB(x) and not x.is_monster()
    def no_other(g, p): return not any(not AMB(x) for x in g.field_cards(p))
    def sc3(g, c, p, ev):
        if main_ok(g, p): return 50 if g.can_search(p, NONMON) else 30
        return 20 if not own_turn(g, p) and g.phase == '종료' and not g.chain else 0
    c.effects = [
        Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and g.can_search(p, NONMON),
               res=lambda g, c, p, l: g.search(p, NONMON, why=c.name), score=lambda *a: 85, threat=300, label='[소환] 몬스터 이외의 「호박옥」 서치'),
        Effect(2, 'quick', ('hand', 'field'), cond=lambda g, c, p, ev: any(m is not c for m in own_faceup(g, p)),
               cost=lambda g, c, p, l: (g.L(f'코스트: {c} 묘지로'), g.send_grave(c, ('cost', c))) and None,
               res=lambda g, c, p, l: put_seals(g, p, 1, why=c.name),
               score=lambda g, c, p, ev: seal_gain_score(g, p, 15 if c.zone == 'hand' else 5), threat=200, label='자신을 묘지로 → 봉인 카운터 1'),
        Effect(3, 'quick', ('hand',), cond=lambda g, c, p, ev: no_other(g, p) and g.can_special(c, p),
               res=lambda g, c, p, l: c.zone == 'hand' and no_other(g, p) and g.special_summon(c, p, 'def'),
               score=sc3, threat=200, label='패에서 수비 표시로 특수소환')]


@card(SHARD)
def _(c):
    amber_common(c)
    def alone(g, p): return not any('아우렘 티라누스' not in m.name for m in g.monsters(p))
    def sc1(g, c, p, ev):
        if main_ok(g, p): return 35
        return 20 if not own_turn(g, p) and g.phase == '종료' and not g.chain else 0
    c.effects = [
        Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: alone(g, p) and g.can_special(c, p),
               res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p, 'def'), score=sc1, threat=200, label='패에서 수비 표시로 특수소환'),
        seal_lastwill(2)]


@card(SAP)
def _(c):
    amber_common(c)
    c.effects = [
        Effect(1, 'ignition', ('hand',), cond=lambda g, c, p, ev: any(seals(m) > 0 for m in g.monsters(p)) and g.can_special(c, p),
               res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p), score=lambda g, c, p, ev: 40, threat=200, label='패에서 특수소환'),
        seal_lastwill(2)]


@card(REVENANT)
def _(c):
    amber_common(c)
    def gy(g, p): return [x for x in g.p[p].grave if AMB(x)]
    def mons(g, p): return [x for x in g.p[p].grave if AMB_MON(x) and g.can_special(x, p)]
    def rank(g, p, x): return (x.name == AUREM, x.name in PROTECTED, x.base_atk(), g.p[p].ai.card_pri(g, p, x))
    def cost1(g, c, p, l):
        keep = max(mons(g, p), key=lambda x: rank(g, p, x))   # 되살릴 몬스터는 남긴다 (처리 시에 고른다)
        xs = sorted([x for x in gy(g, p) if x is not keep], key=lambda x: gy_value(g, p, x))[:2]
        for x in xs: g.to_deck(x, ('cost', c))
        g.shuffle(p); g.L(f'코스트: 묘지의 {", ".join(map(str, xs))} 덱으로')
    def res1(g, c, p, l):
        cs = mons(g, p)
        if not cs: g.L('특수소환할 「호박옥」 몬스터 없음', 'sys'); return
        x = max(cs, key=lambda x: rank(g, p, x))
        if g.special_summon(x, p): x.flags['no_attack_until'] = g.turn; g.L(f'{x}은(는) 이 턴에 공격할 수 없음')
    def sc1(g, c, p, ev):
        cs = mons(g, p)
        if not cs: return VETO
        x = max(cs, key=lambda x: rank(g, p, x))
        return 45 + (35 if x.name == AUREM else 15 if x.name in PROTECTED else 0)
    def cond2(g, c, p, ev):
        return ev_is(ev, 'to_grave') and ev['card'] is c and c.zone == 'grave' and any(AMB(x) for x in g.deck_cards(p))
    c.effects = [
        Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: len(gy(g, p)) >= 3 and bool(mons(g, p)),
               cost=cost1, res=res1, score=sc1, threat=700, label='묘지 2장 덱으로 → 묘지의 「호박옥」 몬스터 특수소환'),
        Effect(2, 'lastwill', ('grave',), cond=cond2,
               res=lambda g, c, p, l: (lambda cs: cs and g.deck_to_grave(p, dump_pick(g, p, cs), c.name))([x for x in g.deck_cards(p) if AMB(x)]),
               score=lambda *a: 65, threat=300, label='[유언] 덱에서 「호박옥」 1장 묘지로')]


@card('봉인을 푸는 자')
def _(c):
    amber_common(c)
    def deck_trig(g, p): return [x for x in g.deck_cards(p) if UNSL_TRIG(x)]
    def res1(g, c, p, l):
        cs = deck_trig(g, p)
        if not cs or not g.free_s(p): g.L('세트할 「봉인을 푸는 자」 트리거 마법 · 빈 마법 존 없음', 'sys'); return
        shown = []
        for x in sorted(cs, key=lambda x: -g.p[p].ai.card_pri(g, p, x)):   # 서로 다른 이름을 먼저 (ASSUME)
            if len(shown) < 3 and x.name not in [y.name for y in shown]: shown.append(x)
        for x in cs:
            if len(shown) < 3 and x not in shown: shown.append(x)
        n = 2 if (c.zone == 'shared' and c.faceup and not g.is_neg(c)) else 1   # 2번 [지속]: 공유 존에 있으면 상대가 2장을 고른다
        picks = g.rng.sample(shown, min(n, len(shown)))
        g.L(f'{g.pname(p)} 덱에서 {", ".join(map(str, shown))} 공개 → {g.pname(1-p)} 무작위로 {", ".join(map(str, picks))}', 'decision')
        for x in picks:
            if not g.free_s(p): break
            g._remove(x); g.place_spell(x, p, False); g.L(f'{x} 마법 존에 세트')
        g.shuffle(p)
    def cost3(g, c, p, l):
        l.ctx['t'] = max([x for x in g.p[p].grave if UNSL_TRIG(x)], key=lambda x: g.p[p].ai.card_pri(g, p, x)); g.L(f'대상: 묘지의 {l.ctx["t"]}')
    def res3(g, c, p, l):
        t = l.ctx['t']
        if t.zone == 'grave': g.to_hand(t); g.L(f'{t} 패에 넣음')
    c.effects = [
        Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and bool(deck_trig(g, p)) and bool(g.free_s(p)),
               res=res1, score=lambda *a: 80, threat=400, label='[소환] 트리거 마법 3장 공개 → 상대가 무작위로 고른 카드 세트'),
        Effect(3, 'ignition', ('field',), cond=lambda g, c, p, ev: any(UNSL_TRIG(x) for x in g.p[p].grave),
               cost=cost3, res=res3, score=lambda *a: 40, threat=300, label='묘지의 트리거 마법 회수')]


# ═══════════════════════ 마법 · 필드 ═══════════════════════
@card('호박옥 - 침전')
def _(c):
    amber_common(c)
    def cands(g, p): return [x for x in g.p[p].main if AMB_MON(x) and g.can_special(x, p)]
    def res(g, c, p, l):
        cs = cands(g, p)
        if cs:
            x = g.p[p].ai.pick_search(g, p, cs, c.name); g.special_summon(x, p, 'def'); g.shuffle(p)
        put_seals(g, p, 2, why=c.name)
    def sc(g, c, p, ev):
        if not main_ok(g, p): return 0
        lost = sum(1 for x in g.p[p].hand if x is not c and not AMB(x))   # 맹세 제약으로 묶이는 패
        return 60 - 8 * lost
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(cands(g, p)),
                        cost=lambda g, c, p, l: oath(g, p, AMBER), res=res, score=sc, threat=500,
                        label='메인 덱 「호박옥」 몬스터 수비 특수소환 + 봉인 카운터 2 (맹세: 「호박옥」만)')]


@card('호박옥 - 황금봉랍')
def _(c):
    amber_common(c)
    def payers(g, p): return [m for m in g.monsters(p) if seals(m) >= 2]
    def cost1(g, c, p, l):
        m = max(payers(g, p), key=lambda m: (seals(m) - 2 - keep_of(m) >= 0, seals(m), -value(g, m)))
        l.ctx['t'] = g.chain[-1]; g.remove_counter(m, SEAL, 2); g.L(f'코스트: {m}의 봉인 카운터 2개 제거')
    def sc1(g, c, p, ev):
        t = threat(g, p)
        return 65 if t >= 800 else 40 if t >= 600 else 0
    def cond2(g, c, p, ev):
        if not (ev_is(ev, 'leave_field') and ev['card'] is c and ev['ctrl'] == p): return False
        ca = ev.get('cause') or ('', None)
        return ca[0] == 'effect' and ca[1] is not None and ca[1].controller == 1 - p and bool(own_faceup(g, p))
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True,
               score=lambda g, c, p, ev: 5 if any(x.name == c.name and x.faceup for x in g.spells(p)) else 40, threat=300),
        Effect(1, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and bool(payers(g, p)),
               cost=cost1, res=lambda g, c, p, l: g.negate(l.ctx['t'], by=c), score=sc1, threat=800, label='봉인 카운터 2 → 상대 발동 무효'),
        Effect(2, 'trigger', ('grave', 'hand'), cond=cond2, res=lambda g, c, p, l: put_seals(g, p, 2, why=c.name),
               score=lambda *a: 70, threat=300, label='상대 효과로 필드를 벗어남 → 봉인 카운터 2')]


@card('호박옥 - 각성의 태동')
def _(c):
    amber_common(c)
    def cond(g, c, p, ev):
        l = last_opp_link(g, p)
        if l is None or not own_faceup(g, p): return False
        if threatened(g, p): return True                       # 자신 필드의 몬스터가 상대 효과의 대상
        return bool(g.field_cards(p)) and removes_field(l)     # 상대가 자신 필드의 카드를 벗어나게 하는 효과를 발동
    c.effects = [Effect(1, 'resp', ('hand', 'field'), spell_act=True, cond=cond, res=lambda g, c, p, l: put_seals(g, p, 2, why=c.name),
                        score=lambda g, c, p, ev: 60, threat=300, label='상대의 대상 지정 · 제거 효과 발동 → 봉인 카운터 2')]


@card('호박옥 - 균열')
def _(c):
    amber_common(c)
    def pick(g, c, p):
        cs = [m for m in g.monsters(p) if seals(m) > 0]
        if not cs: return None
        n = len(targets(g, p, [x for x in opp_cards(g, p) if x is not c]))
        return max(cs, key=lambda m: (min(seals(m), n) - max(0, seals(m) - n) - (0.8 if m.name in ACES else 0.4 if m.name in GUARDS else 0), -value(g, m)))
    def cost(g, c, p, l):
        m = pick(g, c, p); l.ctx['n'] = g.remove_counter(m, SEAL, seals(m)); g.L(f'코스트: {m}의 봉인 카운터 {l.ctx["n"]}개 전부 제거')
    def res(g, c, p, l):
        n = l.ctx.get('n', 0); ch = []
        for _ in range(n):   # 「제거한 개수만큼 필드의 카드를 고르고」 — 상대 카드부터, 모자라면 자신 카드(ASSUME)
            pool = [x for x in targets(g, p, g.all_field()) if x is not c and x not in ch]
            if not pool: break
            ch.append(field_pick(g, p, 'remove', pool))
        for t in ch:
            if g.on_field(t): g.destroy(t)
    def sc(g, c, p, ev):
        m = pick(g, c, p)
        opp = sorted((value(g, x) for x in targets(g, p, opp_cards(g, p))), reverse=True)
        if m is None or not opp: return VETO
        s = seals(m); k = min(s, len(opp))
        base = 15 + 15 * sum(opp[:k]) - 25 * max(0, s - len(opp)) - (20 if m.name in ACES else 0)
        return base if main_ok(g, p) or threat(g, p) >= 900 else 0
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: any(seals(m) > 0 for m in g.monsters(p)),
                        cost=cost, res=res, score=sc, threat=1000, label='봉인 카운터 전부 제거 → 그 개수만큼 필드의 카드 파괴')]


@card('호박옥 - 임시 봉인')
def _(c):
    amber_common(c)
    # 「호박옥」 카드의 효과는 받는 에이스(봉인 카운터가 있는 아우렘 · 녹스)도 고를 수 있게 이 카드를 주체로 내성 판정
    def cands(g, p, c): return [m for m in g.monsters(0) + g.monsters(1) if m.faceup and AMB_MON(m) and not g.immune(m, p, c)]
    def cost(g, c, p, l):
        cs = cands(g, p, c); th = threatened(g, p)
        if not cs: return False   # 발동 판정 뒤 대상으로 할 수 없게 됨 (카르분쿨루스 「상대 효과의 대상이 되지 않는다」)
        own = [m for m in cs if m.controller == p]
        l.ctx['t'] = max(own or cs, key=lambda m: (m in th, m.name in ACES, value(g, m))); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if not (t and g.on_field(t)) or g.blocked(t, ('effect', c)): return
        u = g.turn + 1   # 다음 턴 종료 시까지
        t.flags.update(immune_all_until=u, no_release_until=u, battle_indestr_until=u, no_pos_change_until=u)
        g.L(f'{t}: 다음 턴 종료 시까지 표시 형식 변경 불가 · 다른 카드의 효과를 받지 않음 · 전투로 파괴되지 않음 · 릴리스되지 않음')
    def sc(g, c, p, ev):
        if any(m.controller == p and AMB_MON(m) and m.flags.get('immune_all_until', -1) < g.turn for m in threatened(g, p)): return 60
        l = last_opp_link(g, p)
        if l is not None and threat(g, p) >= 900 and removes_field(l) and any(m.controller == p for m in cands(g, p, c)): return 35
        return 0
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(cands(g, p, c)),
                        cost=cost, res=res, score=sc, threat=400, label='「호박옥」 몬스터 1장 다음 턴 종료 시까지 보호')]


@card(FIELD_SPELL)
def _(c):
    amber_common(c)
    def end1(g, src):
        """1번 [지속] 각 턴의 종료 시 처리 — 발동이 아님"""
        p = src.controller
        if own_faceup(g, p): put_seals(g, p, 1, why=src.name)
    c.end_process = end1
    c.rules['indestructible'] = lambda g, src, x, battle: battle and x.controller == src.controller and x.is_monster() and seals(x) > 0 and g.on_field(x)
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True,
               score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.name == c.name and g.fieldz.controller == p) else 55, threat=500),
        Effect(3, 'ignition', ('grave',), cond=lambda g, c, p, ev: g.can_search(p, AMB),
               cost=lambda g, c, p, l: (g.L(f'코스트: 묘지의 {c} 제외'), g.banish(c, ('cost', c))) and None,
               res=lambda g, c, p, l: g.search(p, AMB, why=c.name), score=lambda *a: 45, threat=300, label='묘지에서 제외 → 「호박옥」 서치')]


# ═══════════════════════ 봉인을 푸는 자 트리거 마법 ═══════════════════════
@card('월식')
def _(c):
    def cond(g, c, p, ev):
        return ev_is(ev, 'counter') and ev.get('amber_side') == p and ev.get('amber_prev', 99) < 5 <= ev.get('amber_sum', 0)
    def res(g, c, p, l):
        n = pay_seals(g, p, 5, [m for m in g.monsters(p) if m.faceup and AMB_MON(m)])
        g.L(f'봉인 카운터 {n}개 제거')
        for m in list(g.monsters(1 - p)): face_down_def(g, m)
    def sc(g, c, p, ev):
        n = sum(1 for m in g.monsters(1 - p) if m.faceup)
        return 30 + 20 * n if n else VETO
    c.effects = forced_trigger(cond, res, sc, 1200, '봉인 카운터 5개 → 상대 몬스터 전부 뒷면 수비')


@card('몽마의 도래')
def _(c):
    def killer(ev):
        ca = ev.get('cause') or ('', None)
        return ca[1] if ca[0] == 'battle' else None
    def cond(g, c, p, ev):
        if not (ev_is(ev, 'to_grave') and ev.get('battle') and ev.get('destroyed') and ev['ctrl'] == p and AMB_MON(ev['card'])): return False
        a = killer(ev)
        return a is not None and a.controller == 1 - p and g.on_field(a) and a.faceup
    def res(g, c, p, l):
        a = killer(l.ctx['ev'])
        if a is not None and g.on_field(a) and a.controller == 1 - p and a.faceup: g.set_face_down(a)
    c.effects = forced_trigger(cond, res, lambda *a: 70, 700, '전투로 파괴한 상대 몬스터 뒷면')


@card('깨어남의 종')
def _(c):
    def nox_on(g, p): return [m for m in g.monsters(p) if m.name == NOX and m.faceup and seals(m) > 0]
    def cond(g, c, p, ev):
        if not (ev_is(ev, 'damage') and ev['player'] == p): return False
        after = ev.get('hp_after', g.p[p].hp)
        return after <= 2000 < after + ev['amount'] and bool(nox_on(g, p))
    def cost(g, c, p, l):
        m = max(nox_on(g, p), key=seals); l.ctx['n'] = g.remove_counter(m, SEAL, seals(m))
        g.L(f'코스트: {m}의 봉인 카운터 {l.ctx["n"]}개 전부 제거')
    def res(g, c, p, l):
        for _ in range(l.ctx.get('n', 0)):
            cs = [x for x in g.p[p].grave if AMB_MON(x) and g.can_special(x, p)]
            if not cs: break
            g.special_summon(max(cs, key=lambda x: (x.name in PROTECTED, x.base_atk())), p)
    def sc(g, c, p, ev):
        return 60 if any(AMB_MON(x) for x in g.p[p].grave) else VETO
    c.effects = forced_trigger(cond, res, sc, 600, 'HP 2000 이하 → 녹스의 카운터 수까지 묘지 「호박옥」 몬스터 특수소환', cost=cost)


@card('꿈의 파열')
def _(c):
    def cond(g, c, p, ev):
        return ev_is(ev, 'leave_field') and ev['card'].name == NOX and ev['ctrl'] == p
    def res(g, c, p, l):
        for m in list(g.monsters(0) + g.monsters(1)): g.destroy(m)
    def sc(g, c, p, ev):
        d = sum(value(g, m) for m in g.monsters(1 - p)) - sum(value(g, m) for m in g.monsters(p))
        return 20 + 15 * d if d > 0 else VETO
    c.effects = forced_trigger(cond, res, sc, 1200, '녹스 이탈 → 필드의 모든 몬스터 파괴')


# ═══════════════════════ 스킬 ═══════════════════════
def upkeep(n, per):
    """스킬 2번 [지속] 자신 턴의 종료 시: 봉인 카운터를 합계 n개 제거, 제거하지 못한 개수 × per 대미지 (발동이 아님)"""
    def end(g, src):
        p = src.controller
        if g.turn_player != p: return
        got = pay_seals(g, p, n)
        g.L(f'{src.name} 2번: 봉인 카운터 {got}/{n}개 제거', 'sys')
        if got < n: g.damage(p, (n - got) * per, f'자해 ({src.name} 2번)')
    return end


@card(CONTRACT)
def _(c):
    def on_ev(g, src, ev):
        annotate(g, src, ev)
        if ev['kind'] != 'game_start': return
        p = src.controller
        xs = [x for x in g.p[p].upper if x.name == AUREM]
        if not xs or not g.can_special(xs[0], p): g.L(f'{CONTRACT} 1번: 상급 덱에 「{AUREM}」 없음 / 특수소환 불가', 'sys'); return
        g.L(f'{CONTRACT} 1번: 라운드 시작 시 {xs[0]} 수비 표시로 특수소환', 'sys')
        g.special_summon(xs[0], p, 'def')
    c.on_event = on_ev
    c.end_process = upkeep(2, 1000)
    c.rules = {'half_battle_damage': lambda g, src, p: p == src.controller and any(seals(m) > 0 for m in g.monsters(p))}
    c.effects = []


@card(DREAM)
def _(c):
    c.on_event = annotate
    c.end_process = upkeep(1, 2000)
    def res1(g, c, p, l):
        xs = [x for x in g.p[p].upper if x.name == NOX and g.can_special(x, p)]
        if xs: g.special_summon(xs[0], p, 'def')
        else: g.L(f'{DREAM} 1번: 특수소환할 「{NOX}」 없음', 'sys')
    c.effects = [Effect(1, 'trigger', ('skill',), mandatory=True, opt=None,
                        cond=lambda g, c, p, ev: ev_is(ev, 'game_start') and any(x.name == NOX for x in g.p[p].upper),
                        res=res1, threat=300, label='라운드 시작 시 녹스 솜니페르 앞면 수비 특수소환')]
