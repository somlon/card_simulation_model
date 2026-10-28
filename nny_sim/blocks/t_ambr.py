"""조립표 — 호박옥 23종 (AMBR-001 ~ 018 + 봉인을 푸는 자 UNSL-001 ~ 005). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
스킬이 라운드 시작 시 에이스(아우렘 티라누스 · 녹스 솜니페르)를 필드에 내고, 봉인 카운터가 놓여 있는 동안 에이스 · 수호자가 보호되는 테마.
「이 카드에 봉인 카운터가 놓여 있는 한」 [지속]은 조건부 플래그(status.card_flag while_counter — 앞면 · 1개 이상 · 무효 아님).
대상 지정: 「대상으로 하고」만 대상(발동 시 고름), 「고르고」는 처리 때 고르는 비대상(카르분쿨루스 · 마르모르 판정 — 엔진 Game.immune).
효과 종류 표기가 없는 효과(아우렘 4번 · 수액정 1번 · 반혼체 1번 · 태고의 수해 3번 · 봉인을 푸는 자 3번)는 기동 효과(ASSUME, 예전과 같음).
「(이 효과는 강제로 발동한다.)」 트리거 마법은 패 · 세트한 카드 모두 조건이 갖춰지면 발동(사용자 답변 2026-10-17)."""
from blocks.dsl import *   # noqa: F401,F403

SEAL, AMB, UNS = '봉인', '호박옥', '봉인을 푸는 자'
AUREM, NOX = '호박옥 - 아우렘 티라누스', '호박옥 - 녹스 솜니페르'
OPP_FIELD = S('opp', 'field')
OWN_MON = S('own', 'field', 'monster', faceup=True)
AMB_GRAVE_OTHER = S('own', 'grave', group=AMB, not_self=True)
W = dict(while_counter=SEAL)
GUARD_LW = '[유언] 묘지의 「호박옥」 카드 {n}장을 제외하고 발동. 이 카드를 특수소환한다.'
NOT_ONCE = '(이 효과는 1턴에 1번 제약을 받지 않는다.)'


def seals(n): return counter(SEAL, n, scope=OWN_MON)
def guard_lastwill(code):
    fx(code, '4', GUARD_LW, cost=[banish(scope=AMB_GRAVE_OTHER, n='$n')], do=[special(ref='SELF', src_zone=('grave',))])


def summon_seals(code, pre=''):
    fx(code, '1', f'[소환] {pre}이 카드에 봉인 카운터를 {{n}}개 놓는다.', do=[counter(SEAL, '$n', ref='SELF')])


ACE_GUARD = f'[지속] 이 카드에 봉인 카운터가 놓여 있는 한, 이 카드는 「호박옥」 카드 이외의 카드의 효과를 받지 않고, 전투로는 파괴되지 않으며, 릴리스되지 않는다. {NOT_ONCE}'
ACE_GUARD_BLOCKS = [card_flag('immune_except_group', value=AMB, **W), B('self_rule', key='indestructible', battle='battle', **W),
                    card_flag('no_release', **W)]

# ── 에이스 ──
summon_seals('AMBR-001')
fx('AMBR-001', '2', ACE_GUARD, cont=ACE_GUARD_BLOCKS)
fx('AMBR-001', '3', f'[지속] 이 카드에 봉인 카운터가 놓여 있는 한, 이 카드는 표시 형식을 변경할 수 없으며 공격할 수 없다. {NOT_ONCE}',
   cont=[card_flag('no_pos_change', **W), card_flag('no_attack', **W)])
# 4번 「임의의 개수」 — AI는 파괴할 상대 카드 수만큼, 보호용 1개는 남기고(lib._any_n)
fx('AMBR-001', '4', '1턴에 1번, 이 카드의 봉인 카운터를 임의의 개수만큼 제거하고 발동. 제거한 개수까지 상대 필드의 카드를 고르고 파괴한다.',
   cost=[counter(SEAL, op='remove_any', ref='SELF', fit=OPP_FIELD, count_as='N')],
   do=[destroy(scope=OPP_FIELD, n=('ref', 'N'), upto=True)])

fx('AMBR-006', '1', '[소환] 이 카드가 특수소환되었을 경우에 발동. 이 카드에 봉인 카운터를 {n}개 놓는다.',
   when=[when('summoned', self=True, how='special')], do=[counter(SEAL, '$n', ref='SELF')])
fx('AMBR-006', '2', ACE_GUARD, cont=ACE_GUARD_BLOCKS)
fx('AMBR-006', '3', '[지속] 자신 필드에 이 카드 이외의 몬스터가 존재하지 않을 경우, 상대는 자신에게 직접공격할 수 있다. (이 카드는 「필드에 몬스터가 있으면 직접공격할 수 없다」 규칙의 예외가 된다.)',
   forced=True, cont=[B('rule_to', key='direct_attack', to=S('opp', 'field', 'monster'),
                        **{'while': cnt(S('own', 'mzone', 'monster', not_self=True), '==', 0)})])
fx('AMBR-006', '4', '[트리거] 이 카드에 봉인 카운터가 {k}개 이상 놓여 있을 때, 턴 종료 시에 발동. 상대 필드의 앞면 표시 몬스터 {n}장을 고르고, 그 몬스터를 뒷면 수비 표시로 한다. (이 효과는 강제로 발동한다.)',
   when=[when('phase', phase='end')], cond=[self_counters_ge(SEAL, '$k')],
   do=[face_down('def', scope=S('opp', 'field', 'monster', faceup=True), n='$n')])

# ── 수호자 ──
for code in ('AMBR-002', 'AMBR-003', 'AMBR-004', 'AMBR-005'):
    guard_lastwill(code)
for code in ('AMBR-002', 'AMBR-003'):
    summon_seals(code)
fx('AMBR-002', '2', f'[지속] 이 카드에 봉인 카운터가 놓여 있는 한, 이 카드는 릴리스되지 않고, 효과로 파괴되지 않는다. {NOT_ONCE}',
   cont=[card_flag('no_release', **W), B('self_rule', key='indestructible', battle='effect', **W)])
fx('AMBR-002', '3', '[트리거] 상대가 효과를 발동했을 때 발동. 필드의 몬스터에게 봉인 카운터를 {n}개 놓는다. (이 효과는 1턴에 2번까지 사용할 수 있다.)',
   when=[when('activated', who='opp')], do=[counter(SEAL, '$n', scope=S('both', 'field', 'monster', faceup=True))])
fx('AMBR-003', '2', f'[지속] 이 카드에 봉인 카운터가 놓여 있는 한, 이 카드는 릴리스되지 않고, 파괴 이외의 방법으로 필드를 벗어나지 않는다. {NOT_ONCE}',
   cont=[card_flag('no_release', **W), card_flag('leave_only_destroy', **W)])
fx('AMBR-003', '3', '[트리거] 상대가 효과를 발동했을 때 발동. 「호박옥」 카드 {n}장을 덱/묘지에서 패에 넣는다. (이 효과는 1턴에 2번까지 사용할 수 있다.)',
   when=[when('activated', who='opp')],
   do=[choice([search(S('own', 'deck', group=AMB), '$n')], [to_hand(scope=S('own', 'grave', group=AMB, pickable=True), n='$n', harm=False)])])
# 마르모르 · 카르분쿨루스 1번 — 「필드의 릴리스 가능한 몬스터」 = 자신 필드(ASSUME), 3개는 자신 필드의 몬스터에서 합계로
SS1 = ('[신속] 자신 필드의 몬스터 {n}장을 릴리스하고 발동. 이 카드를 특수소환한다. 필드의 릴리스 가능한 몬스터가 없는 경우, 대신 봉인 카운터 {k}개를 제거하고 소환할 수 있다.')
SS1_COST = [alt(release(scope=S('own', 'field', 'monster', pred='releasable'), n='$n'),
                counter(SEAL, '$k', op='remove', total=True, scope=S('own', 'field', 'monster')))]
DUMP_UPPER = send_grave(scope=S('own', 'upper', 'monster', group=AMB), n='$n')
for code in ('AMBR-004', 'AMBR-005'):
    fx(code, '1', SS1, zones=HAND, cost=SS1_COST, do=[special(ref='SELF', src_zone=('hand',))])
fx('AMBR-004', '2', f'[지속] 이 카드에 봉인 카운터가 놓여 있는 한, 이 카드는 릴리스되지 않고, 상대 카드의 대상을 지정하지 않는 효과를 받지 않는다. {NOT_ONCE}',
   cont=[card_flag('no_release', **W), card_flag('immune_opp_untargeted', **W)])
fx('AMBR-004', '3', '[소환] 상급 덱에서 「호박옥」 몬스터를 {n}장 묘지로 보내고 발동. 필드의 카드 {m}장을 턴 종료 시까지 무효로 한다. (이 효과는 1턴에 2번까지 사용할 수 있다.)',
   cost=[DUMP_UPPER], do=[negate_card(scope=S('both', ('field', 'skill'), faceup=True, not_self=True, pred='not_negated'), n='$m')])
fx('AMBR-005', '2', f'[지속] 이 카드에 봉인 카운터가 놓여 있는 한, 이 카드는 릴리스되지 않고, 상대 효과의 대상이 되지 않는다. {NOT_ONCE}',
   cont=[card_flag('no_release', **W), card_flag('untargetable_opp', **W)])
fx('AMBR-005', '3', '[소환] 상급 덱에서 「호박옥」 몬스터를 {n}장 묘지로 보내고 발동. 필드의 카드 {m}장을 파괴한다. (이 효과는 1턴에 2번까지 사용할 수 있다.)',
   cost=[DUMP_UPPER], do=[destroy(scope=S('both', 'field', not_self=True), n='$m')])

# ── 메인 덱 몬스터 ──
fx('AMBR-007', '1', '[소환] 덱에서 몬스터 이외의 「호박옥」 카드 {n}장을 패에 넣는다.', do=[search(S('own', 'deck', 'not_monster', group=AMB), '$n')])
fx('AMBR-007', '2', '[신속] 이 카드를 패 또는 필드에서 묘지로 보내고 발동. 자신 필드의 몬스터 {m}장에 봉인 카운터를 {n}개 놓는다.',
   zones=HAND_FIELD, cost=[send_grave(ref='SELF')], do=[counter(SEAL, '$n', scope=S('own', 'field', 'monster', faceup=True, not_self=True))])
fx('AMBR-007', '3', '[신속] 자신 필드에 「호박옥」 카드 이외의 카드가 없다면, 이 카드를 패에서 수비 표시로 특수소환한다.',
   zones=HAND, cond=[cnt(S('own', 'field', not_group=AMB), '==', 0)], do=[special(ref='SELF', src_zone=('hand',), pos='def')])
fx('AMBR-008', '1', '[신속] 자신 필드에 「아우렘 티라누스」 이외의 몬스터가 존재하지 않을 때 발동. 이 카드를 패에서 수비 표시로 특수소환한다.',
   zones=HAND, cond=[cnt(S('own', 'mzone', 'monster', name_not_has='아우렘 티라누스'), '==', 0)],
   do=[special(ref='SELF', src_zone=('hand',), pos='def')])
fx('AMBR-009', '1', '자신 필드에 봉인 카운터가 놓인 몬스터가 존재할 때 발동. 이 카드를 패에서 특수소환할 수 있다.',
   zones=HAND, cond=[cnt(S('own', 'mzone', 'monster', counter=SEAL))], do=[special(ref='SELF', src_zone=('hand',))])
for code in ('AMBR-008', 'AMBR-009'):
    fx(code, '2', '[유언] 자신 필드의 몬스터 {m}장에 봉인 카운터를 {n}개 놓는다.', do=[seals('$n')])
fx('AMBR-010', '1', '자신 묘지의 「호박옥」 카드 {n}장을 덱으로 되돌리고 발동. 자신 묘지의 「호박옥」 몬스터 {m}장을 특수소환한다. 이 효과로 특수소환한 몬스터는 이 턴에 공격할 수 없다.',
   cond=[cnt(S('own', 'grave', group=AMB), '>=', '$n', plus=-1)],
   cost=[to_deck(scope=S('own', 'grave', group=AMB), n='$n', shuffle=True, spare=S('own', 'grave', 'monster', group=AMB))],
   do=[special(scope=S('own', 'grave', 'monster', group=AMB), n='$m', **{'as': 'SS'}), status('no_attack', ref='SS')])
fx('AMBR-010', '2', '[유언] 이 카드가 묘지로 보내졌을 경우에 발동. 덱에서 「호박옥」 카드 {n}장을 묘지로 보낸다.',
   do=[send_grave(scope=S('own', 'deck', group=AMB), n='$n')])
fx('UNSL-001', '1', '[소환] 이 카드가 소환에 성공했을 경우에 발동. 자신 덱에서 「봉인을 푸는 자」 트리거 마법 {n}장을 골라 상대에게 보여주고, 상대는 그중 {m}장을 무작위로 고른다. '
   '그 카드를 자신의 마법 존에 세트한다. 나머지 {k}장은 덱으로 되돌리고 셔플한다.',
   do=[show_set(S('own', 'deck', ('trigger',), group=UNS), '$n', '$m')])
fx('UNSL-001', '2', f'[지속] 이 카드가 공유 존에 존재할 경우, 1번 효과 처리 시에 상대는 {{n}}장을 고른다. {NOT_ONCE}',
   cont=[card_flag('pick_n', value='$n', while_zone='shared')])
fx('UNSL-001', '3', '1턴에 1번, 자신 묘지의 「봉인을 푸는 자」 트리거 마법 {n}장을 대상으로 하고 발동. 그 카드를 패에 넣는다.',
   cost=[target('T', S('own', 'grave', ('trigger',), group=UNS), n='$n', harm=False)], do=[to_hand(ref='T', ref_scope=S('own', 'grave'))])

# ── 마법 · 필드 ──
fx('AMBR-011', '1', '메인 덱에서 「호박옥」 몬스터 {n}장을 수비 표시로 특수소환하고, 자신 필드의 몬스터 {k}장에 봉인 카운터를 {m}개 놓는다. '
   '이 효과를 발동한 턴, 자신은 「호박옥」 카드만 사용할 수 있으며, 이 제약은 다음 상대 턴 종료 시까지 적용된다.',
   cost=[oath(AMB)], do=[special(scope=S('own', 'main', 'monster', group=AMB), n='$n', pos='def'), seals('$m')])
fx('AMBR-012', '1', '[신속] 1턴에 1번, 상대가 효과를 발동했을 때 자신 필드의 몬스터 {k}장에서 봉인 카운터를 {n}개 제거하고 발동. 그 발동을 무효로 한다.',
   kind='resp', when=[when('activated', who='opp')],
   cost=[counter(SEAL, '$n', op='remove', scope=S('own', 'field', 'monster', counter=(SEAL, '$n')))], do=[negate_link()])
fx('AMBR-012', '2', '[트리거] 이 카드가 상대의 효과로 필드를 벗어났을 때 발동. 자신 필드의 몬스터 {k}장에 봉인 카운터를 {n}개 놓는다.',
   zones=('grave', 'hand', 'deck', 'banish'), when=[when('left_field', self=True, ctrl='own', by='opp', cause='effect')],
   card=[card_flag('deck_trigger')], do=[seals('$n')])
fx('AMBR-013', '1', '[트리거] 자신 필드의 몬스터가 상대의 효과의 대상이 되었을 때 또는 상대가 자신 필드의 카드를 필드에서 벗어나게 하는 효과를 발동했을 때 발동. '
   '자신 필드의 몬스터 {k}장에 봉인 카운터를 {n}개 놓는다.',
   when=[when('activated', who='opp', hit_own=True)], do=[seals('$n')])
fx('AMBR-014', '1', '[신속] 자신 필드의 몬스터 {k}장의 봉인 카운터를 전부 제거하고 발동. 제거한 개수만큼 필드의 카드를 고르고 파괴한다.',
   cost=[counter(SEAL, op='remove_all', scope=S('own', 'field', 'monster', counter=SEAL), fit=OPP_FIELD, count_as='N')],
   do=[destroy(scope=S('both', 'field', not_self=True), n=('ref', 'N'), upto=True)])
# 임시 봉인 — 「다른 카드의 효과를 받지 않는다」는 마지막에(먼저 걸면 이 카드의 다른 처리도 막힌다)
TEMP = dict(ref='T', until='next')
fx('AMBR-015', '1', '[신속] 필드의 「호박옥」 몬스터 {n}장을 대상으로 하고 발동. 그 몬스터는 다음 턴 종료 시까지 표시 형식을 변경할 수 없으며 다른 카드의 효과를 받지 않고, 전투로는 파괴되지 않으며, 릴리스되지 않는다.',
   cost=[target('T', S('both', 'field', 'monster', group=AMB, faceup=True), n='$n', harm=False)],
   do=[status('no_pos_change', **TEMP), status('battle_indestr', **TEMP), status('no_release', **TEMP), status('immune_all', **TEMP)])
fx('AMBR-016', '1', '[지속] 각 턴의 종료 시에, 자신 필드의 몬스터 {k}장에 봉인 카운터를 {n}개 놓는다.', cont=[end_process([seals('$n')])])
fx('AMBR-016', '2', '[지속] 봉인 카운터가 놓인 자신의 몬스터는 전투로는 파괴되지 않는다.',
   cont=[B('rule_to', key='indestructible', to=S('own', 'field', 'monster', counter=SEAL), battle=True)])
fx('AMBR-016', '3', '묘지의 이 카드를 제외하고 발동. 덱에서 「호박옥」 카드 {n}장을 패에 넣는다.',
   zones=GRAVE, cost=[banish(ref='SELF')], do=[search(S('own', 'deck', group=AMB), '$n')])

# ── 스킬 ──
def upkeep(n_hole, dmg_hole, scope):
    return end_process([counter(SEAL, n_hole, op='remove', total=True, partial=True, scope=scope, short_as='SHORT'),
                        damage(dmg_hole, who='self', times=('ref', 'SHORT'))], whose='own')


fx('AMBR-017', '1', '라운드 시작 시에 자신의 상급 덱에서 「호박옥 - 아우렘 티라누스」 {n}장을 수비 표시로 특수소환한다.', no_effect=True,
   card=[round_start([special(scope=S('own', 'upper', 'monster', name=AUREM), n='$n', pos='def')])])
fx('AMBR-017', '2', '[지속] 자신 턴의 종료 시에, 자신 필드의 몬스터에서 봉인 카운터를 합계 {n}개 제거한다. 제거하지 못하면 대신 제거하지 못한 카운터 × {a} 대미지를 받는다.',
   forced=True, cont=[upkeep('$n', '$a', S('own', 'field', 'monster'))])
fx('AMBR-017', '3', f'[지속] 자신 필드에 봉인 카운터가 놓인 몬스터가 존재하는 한, 자신이 받는 전투 대미지는 절반이 된다. {NOT_ONCE}',
   cont=[B('player_rule', key='half_battle_damage', who='own', **{'while': cnt(S('own', 'mzone', 'monster', counter=SEAL))})])
fx('AMBR-018', '1', '라운드 시작 시에 발동한다. 자신의 상급 덱에서 「호박옥 - 녹스 솜니페르」 {n}장을 앞면 수비 표시로 특수소환한다.',
   kind='trigger', mandatory=True, opt=None, when=[when('game_start')],
   do=[special(scope=S('own', 'upper', 'monster', name=NOX), n='$n', pos='def')])
fx('AMBR-018', '2', '[지속] 자신 턴의 종료 시에, 자신 필드에서 봉인 카운터를 합계 {n}개 제거한다. 제거하지 못하면 대신 제거하지 못한 카운터 × {a} 대미지를 받는다.',
   forced=True, cont=[upkeep('$n', '$a', S('own', 'field'))])

# ── 봉인을 푸는 자 트리거 마법 (강제) ──
AMB_MON_FU = S('own', 'field', 'monster', group=AMB, faceup=True)
fx('UNSL-002', '1', '[트리거] 자신 필드의 「호박옥」 몬스터에 놓인 봉인 카운터의 합계가 {k}개 이상이 되었을 때 발동. 자신 필드의 「호박옥」 몬스터에서 봉인 카운터를 {n}개 제거한다. '
   '상대 필드의 모든 몬스터를 뒷면 수비 표시로 한다. (이 효과는 강제로 발동한다.)',
   when=[when('counter_sum', name=SEAL, scope=AMB_MON_FU, n='$k')],
   do=[counter(SEAL, '$n', op='remove', total=True, scope=AMB_MON_FU), face_down('def', scope=S('opp', 'field', 'monster'), all=True, zero_ok=True)])
fx('UNSL-003', '1', '[트리거] 상대가 자신 필드의 「호박옥」 몬스터를 전투로 파괴했을 때 발동. 파괴한 몬스터를 뒷면으로 한다. (이 효과는 강제로 발동한다.)',
   when=[when('sent_grave', prev=('m', 'shared'), ctrl='own', filter=S(kind='monster', group=AMB), battle=True)],
   do=[face_down(None, ref='EVCAUSE', ref_scope=S('opp', 'field', 'monster', faceup=True))])
fx('UNSL-004', '1', '[트리거] 자신의 HP가 {hp} 이하가 되었을 때 자신 필드의 「호박옥 - 녹스 솜니페르」에 놓인 봉인 카운터를 전부 제거하고 발동. '
   '제거한 카운터 수까지 묘지에서 「호박옥」 몬스터를 특수소환한다. (이 효과는 강제로 발동한다.)',
   when=[when('hp_below', n='$hp')],
   cost=[counter(SEAL, op='remove_all', scope=S('own', 'field', name=NOX, faceup=True, counter=SEAL), count_as='N')],
   do=[special(scope=S('own', 'grave', 'monster', group=AMB), n=('ref', 'N'), upto=True)])
fx('UNSL-005', '1', '[트리거] 자신 필드의 「호박옥 - 녹스 솜니페르」가 필드에서 벗어났을 때 발동. 필드의 모든 몬스터를 파괴한다. (이 효과는 강제로 발동한다.)',
   when=[when('left_field', ctrl='own', filter=S(name=NOX))], do=[destroy(scope=S('both', 'field', 'monster'), all=True, zero_ok=True)])
