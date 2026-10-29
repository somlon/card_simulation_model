"""조립표 — 공용 10종 (COMN-001 ~ 010). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md"""
from blocks.dsl import *   # noqa: F401,F403

OPP_FIELD = S('opp', 'field')
OPP_TRIGGER_SPELL = dict(who='opp', card_only=True, sub=('trigger',))

# 사기 감지 — 「패에 넣었을 때」에 드로우 포함 (사용자 답변 2026-10-28)
fx('COMN-001', '1', '[트리거] 상대가 덱에서 카드를 패에 넣었을 때 발동. 그 카드를 묘지로 보낸다.',
   when=[when('hand_added', who='opp', src='deck')],
   do=[send_grave(ref='EV', ref_scope=S('opp', 'hand'))])

# 바이러스 모스키토
fx('COMN-002', '1', '[신속] 상대 필드의 몬스터 {n}장을 대상으로 하고 발동. 이 카드를 장착 마법 카드 취급으로 장착한다. '
   '이 카드가 장착되어 있는 한, 그 몬스터의 효과를 무효로 한다. (이 효과는 패에서도 발동할 수 있다.)',
   cost=[target('T', S('opp', 'field', 'monster', faceup=True), n='$n')],
   do=[equip(ref='T', negate=True)])

# 태양과 달의 마력 — 「대상으로 하고」가 없어 처리 때 고른다(비대상, 재정 Q2)
fx('COMN-003', '1', '상대 필드의 카드 {n}장을 제외한다. (이 카드는 무효화되지 않으며, 이 효과에 대하여 상대는 효과를 발동할 수 없다.)',
   unnegatable=True, no_resp=True,
   do=[banish(scope=OPP_FIELD, n='$n')])

# 고대의 봉인 — 「다른 카드의 효과를 받지 않는다」는 마지막에(먼저 걸면 이 카드의 다른 처리도 막힌다)
fx('COMN-004', '1', '[신속] 자신 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드는 공격력이 {amt} 내려가는 대신 턴 종료 시까지 릴리스할 수 없으며, '
   '다른 카드의 효과를 받지 않는다.',
   cost=[target('T', S('own', 'field'), n='$n', harm=False)],
   do=[stat('-$amt', ref='T'), status('no_release', ref='T'), status('immune_all', ref='T')])

# 매수당한 킬러
fx('COMN-005', '1', '[신속] 이 카드를 패에서 특수소환한다.', zones=HAND,
   do=[special(ref='SELF', src_zone=('hand',))])
fx('COMN-005', '2', '[신속] 상대 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 파괴한다.',
   cost=[target('T', OPP_FIELD, n='$n')],
   do=[destroy(ref='T')])
fx('COMN-005', '3', '[트리거] 상대 턴 종료 시에 발동. 이 카드를 파괴한다. (이 효과는 강제로 발동한다.)',
   when=[when('phase', phase='end', whose='opp')],
   do=[destroy(ref='SELF')])

# 선택받은 용사 — 1번은 패에서 특수소환 (사용자 답변 Q57)
fx('COMN-006', '1', '[트리거] 상대의 트리거 마법이 발동했을 때 발동. 이 카드를 특수소환한다. 이 효과로 특수소환한 카드는 상대의 효과를 받지 않는다.',
   zones=HAND, when=[when('activated', **OPP_TRIGGER_SPELL)],
   do=[special(ref='SELF', src_zone=('hand',)), status('immune_opp', until='perm', ref='SELF', harm=False)])
fx('COMN-006', '2', '[지속] 이 카드가 필드에 존재하는 한, 상대는 트리거 마법을 발동할 수 없다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[forbid('no_trigger_spell', who='opp')])
fx('COMN-006', '3', '[트리거] 자신 턴 종료 시 발동. 이 카드를 묘지로 보낸다.',
   when=[when('phase', phase='end', whose='own')],
   do=[send_grave(ref='SELF')])

# 해주
fx('COMN-007', '1', '이 턴에 상대의 지속 마법을 전부 무효화한다. 이 턴에, 자신은 상대에게 대미지를 입힐 수 없다.',
   do=[negate_card(scope=S('opp', 'szone', ('cont',), faceup=True), all=True), no_damage()])

# 럭키 다이스 — 주사위 눈에 따라(J2). 발동하려면 상대 필드에 카드가 1장 이상(가장 적은 눈의 처리를 할 수 있어야 — 재정 G2)
fx('COMN-008', '1', '주사위를 굴려 나온 눈의 수에 따라 효과를 적용한다.\n- 1: 상대 필드의 카드를 {a}장 파괴한다.\n'
   '- 2 ~ 5: 상대 필드의 카드를 {b}장 파괴한다.\n- 6: 상대 필드의 카드를 {c}장 파괴한다.',
   cond=[cnt(OPP_FIELD, '>=', 1)],
   do=[roll('D'),
       branch(ref_in('D', 1), [destroy(scope=OPP_FIELD, n='$a')],
              [branch(ref_in('D', 6), [destroy(scope=OPP_FIELD, n='$c')], [destroy(scope=OPP_FIELD, n='$b')], prob=0.2)],
              prob=1 / 6)])

# 명계의 징벌
GRAVE_BACK = when_any(when('hand_added', who='opp', src='grave'), when('summoned', who='opp', how='special', prev=('grave',)))
fx('COMN-009', '1', '[트리거] 상대가 묘지의 카드를 패에 넣거나 특수소환했을 때 발동. 그 카드를 제외한다. (이 카드의 발동에 대하여, 상대는 효과를 발동할 수 없다.)',
   when=[GRAVE_BACK],
   do=[banish(ref='EV', ref_scope=S('opp', ('hand', 'field')))])
fx('COMN-009', '2', '[트리거] 이 카드가 묘지에 존재하는 상태에서, 상대가 묘지의 카드를 패에 넣거나 특수소환했을 때 묘지의 이 카드를 제외하고 발동. '
   '상대 필드의 카드 {n}장을 파괴한다.',
   zones=GRAVE, when=[GRAVE_BACK],
   cost=[banish(ref='SELF')],
   do=[destroy(scope=OPP_FIELD, n='$n')])

# 명계의 규율 — 사용자 지시(2026-10-29): 이 카드보다 먼저 발동해 처리를 기다리는 효과 중, 효과를 발동한 카드의 위치가 묘지인 것만 전부 무효
# (자신 것 포함 — 발동 위치는 체인의 ctx['from_zone'])
fx('COMN-010', '1', '[트리거] 상대가 묘지의 카드의 효과를 발동했을 때 발동. 이 카드를 발동하기 전에 묘지에서 발동한 효과는 전부 무효화된다.',
   when=[when('activated', who='opp', from_zone=('grave',))],
   do=[negate_chain(from_zone=('grave',))])
