"""카드 구현 2차: 공용 8종 · 격투가 11종 (격투가는 2026-10-08 카드 자료로 갱신 — 아래 격투가 절 머리말).
※ 블록 체계(2026-10-28): 카드 효과는 조립표 blocks/t_comn.py · blocks/t_fgtr.py로 옮겼다. 이 모듈에는 블록 · 테스트가 쓰는 공용 함수 · 상수만 남았고, 아래 설명은 옛 구현 기준의 재정 · 가정 기록이다.
번성충 기생 축 6종은 사용자 지시(2026-10-13)로 카드 풀에서 삭제되어 구현도 지움 (git 기록에 남아 있음)."""
from engine import Effect, link_targets
from cards import best, ev_is, field_pick, VETO, text_attrs


def targets(g, p, cands, src=None):
    """p의 효과로 고를 수 있는 카드 (내성 제외). src = 효과의 주체 카드 — 주면 「「X」 카드 이외의 효과를 받지 않는다」를 그 카드로 판정한다
    (호박옥 효과가 상대의 봉인된 에이스를 고를 수 있게, 2026-10-15). 주지 않으면 전과 같다(주체를 모름 = 받지 않음)"""
    return [x for x in cands if not g.immune(x, p, src)]


# ═══════════════════════ 격투가 ═══════════════════════
# 2026-10-08 카드 자료(사용자 업로드 2026-10-13) 반영. 예전 텍스트에서 바뀐 것:
#  스네이크 스케일 1 · 엘리펀트 노즈 1 · 라이노 혼 1 · 2 · 세레모니가 「대상으로 하고 발동」(발동 시 고름), 엘리펀트 · 라이노 1번은 「대상으로 하고 발동.
#  이 카드를 특수소환하고, 그 카드를 파괴한다」, 세레모니 부여는 영구 · 중첩(재정), 투기장의 규칙에 [전투] 1장 드로우(1번)가 생기고
#  서치(2번)는 코스트가 아닌 처리 · 「덱」(메인 · 상급), 카드군 「격투가」가 생김.
# ASSUME:
#  - [전투] = 전투로 카드를 파괴하는 데 성공했을 때(엔진 battle_win, §7). 몬스터가 아닌 카드(세레모니 · 스킬 1번)의 [전투] = 자신 몬스터의 battle_win.
#  - 처리 순서(사용자 답변 2026-10-17): 텍스트 앞 효과를 처리해야 뒤 효과도 처리한다 — 스네이크 스케일 1번은 대상을 파괴하지 못하면 패를 버리지 않는다.
#    라이노 혼 2번도 대상을 파괴하지 못하면 1000 대미지를 주지 않는다.
#  - 엘리펀트 노즈 · 라이노 혼 1번: 「자신 필드에 몬스터가 존재하지 않을 경우」는 발동 조건, 특수소환하지 못하면 파괴도 하지 않는다.
#  - 세레모니: 대상 = 자신 필드의 앞면 「격투가」 몬스터(전투한 몬스터가 아니어도 됨). 부여(재정) — 그 몬스터가 필드에 있는 동안 영구:
#    매 턴 공격 횟수 +1(부여한 턴 포함) · 부여 [전투](효과 번호 30+k, k번째 부여분마다 · 몬스터 한 장마다 1턴 1번). 필드를 벗어나면 사라진다.
#    부여 [전투] 「필드의 카드 1장을 대상으로」: 상대 카드 우선, 상대 카드가 없으면 1000 대미지로 결착할 때만 자신 카드를 대상으로 쓴다.
#  - 격투가의 투기장 3번 「상대 필드의 몬스터가 파괴되었을 경우」: 파괴 직전 상대가 컨트롤하던 몬스터(to_grave 사건의 ctrl).
#  - 투기장의 규칙 2번: 되돌리기 · 서치 모두 처리(코스트 아님). AI는 되돌린 카드와 다른 이름을 서치(없으면 같은 이름도 가능).
#    3번(종류 표기 없음)은 기동 효과(1턴 1번, 기존 ASSUME) — AI는 같은 이름이 2장 이상인 카드의 여분(1장은 남김) 중 버릴 만한 것만 되돌린다.
#  - 격투가 반격 「필드에 「격투가」 카드가 존재할 때」 = 서로의 필드의 앞면 「격투가」 카드(세트된 카드는 세지 않음, 이 카드 자신 제외).
#  - 격투가 입장 1번 「패에 넣거나 특수소환한다」: AI는 자신 필드가 비었거나 이 턴 공격할 수 있을 때(자신 턴) · 상대 턴이면 특수소환.
#  - 한 번의 전투로 대상 지정 효과가 여럿 발동하면(라이노 혼 2번 · 세레모니 부여분) 체인 위 자신의 다른 발동이 고른 카드는 되도록 피한다.
#  - 투기장 1번(수비 표시 금지)은 투기장 컨트롤러의 효과를 받지 않는 몬스터에는 적용하지 않는다.


def taken_on_chain(g, p):
    """체인 위 p의 발동이 이미 대상으로 고른 카드 — 한 번의 전투로 대상 지정 효과가 여럿 발동할 때 같은 카드를 고르지 않게"""
    return {id(x) for lk in g.chain if lk.player == p for x in link_targets(lk)}


def battle(res, score=90, num=2, cond=None, cost=None, label='[전투]'):
    return Effect(num, 'battle', ('field',),
                  cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['card'] is c and (cond is None or cond(g, c, p, ev)),
                  cost=cost, res=res, score=score if callable(score) else (lambda *a, s=score: s), threat=700, label=label)


CER_BASE = 30   # 세레모니 부여 [전투]의 효과 번호: 31, 32, … (k번째 부여분 — 각각 1턴 1번, 재정)

def cer_effect(k, line='', name=''):
    """세레모니 k번째 부여 [전투]: 필드의 카드 1장을 대상으로 하고 발동 → 상대에게 1000 대미지, 그 카드를 파괴.
    line = 부여하는 카드(세레모니)의 「-」 항목 — 대상 지정 · 제거 효과 등의 성질을 그 문장에서 단다(cards.text_attrs). 제거 효과라 뒷면 마법도 대상으로 할 수 있다
    (사용자 답변 2026-10-23 PDF Q6 — 부여 효과는 카드에 붙을 때가 아니라 게임 중에 생기므로 Impl.attach를 거치지 않는다)"""
    def pool(g, p): return targets(g, p, g.all_field())
    def opp_pool(g, p):
        """대상으로 고를 수 있는 상대 카드 — 「상대 효과의 대상이 되지 않는다」를 반영(발동 판정과 같은 엄격한 관점, Game.probing)"""
        prev = getattr(g, 'probing', None); g.probing = p
        try: return [x for x in pool(g, p) if x.controller != p]
        finally: g.probing = prev
    def cond(g, c, p, ev): return c.flags.get('ceremony', 0) >= k and bool(pool(g, p))
    def cost(g, c, p, l):
        ts = pool(g, p)
        if not ts: return False
        tk = taken_on_chain(g, p)
        opp = [x for x in ts if x.controller != p]
        if not opp and g.p[1 - p].hp > 1000: return False   # 자신 카드를 파괴하게 되는데 결착도 아니면 쓰지 않는다 (점수가 이미 막음 — 안전장치)
        l.ctx['t'] = best(g, [x for x in opp if id(x) not in tk] or opp, p) if opp else field_pick(g, p, pool=ts); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        g.damage(1 - p, 1000, f'{c.name} (세레모니 부여 [전투])')
        t = l.ctx.get('t')
        if t is not None and g.on_field(t): g.destroy(t)
    def sc(g, c, p, ev):
        if opp_pool(g, p): return 90
        return 1000 if g.p[1 - p].hp <= 1000 else VETO   # 자신 카드를 파괴하게 되면 결착일 때만
    e = battle(res, sc, num=CER_BASE + k, cond=cond, cost=cost, label=f'[전투] (세레모니 부여 {k}) 1000 대미지 + 대상 파괴')
    e.opt_per_card = True   # 부여받은 효과 — 부여마다 별개의 1턴 1번(같은 이름 몬스터 2장이 각각 받아도 각각 1번, 사용자 답변 2026-10-17)
    text_attrs(e, line, name)
    return e
