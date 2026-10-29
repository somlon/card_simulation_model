"""조립표 — 격투가 11종 (FGTR-001 ~ 011). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
[전투] = 이 카드가 전투로 카드를 파괴했을 때(엔진 battle_win, §7). 몬스터가 아닌 카드(세레모니 · 투기장의 규칙 1번)는 자신의 몬스터가 파괴했을 때(재정 Q6)."""
from blocks.dsl import *   # noqa: F401,F403

OPP_FIELD = S('opp', 'field')
FGTR_DECK = S('own', 'deck', group='격투가')
FGTR_MON_DECK = S('own', 'deck', 'monster', group='격투가')
NO_OWN_MON = cnt(S('own', 'field', 'monster'), '==', 0)

fx('FGTR-001', '1', '[신속] 패에서 이 카드를 보여주고 상대 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 파괴하고 자신의 패를 {m}장 버린다.',
   zones=HAND, cost=[target('T', OPP_FIELD, n='$n')],
   do=[destroy(ref='T'), discard('$m')])
fx('FGTR-001', '2', '[유언] 덱에서 「격투가」 카드 {n}장을 패에 넣는다.', do=[search(FGTR_DECK, '$n')])

fx('FGTR-002', '1', '[신속] 패에서 이 카드를 보여주고 발동. 덱에서 「격투가」 카드를 {n}장 패에 넣는다. 자신의 패를 {m}장 버린다.',
   zones=HAND, do=[search(FGTR_DECK, '$n'), discard('$m')])
fx('FGTR-002', '2', '[유언] 덱에서 「격투가」 몬스터 {n}장을 패에 넣는다.', do=[search(FGTR_MON_DECK, '$n')])

for code in ('FGTR-003', 'FGTR-004'):
    fx(code, '1', '[신속] 자신 필드에 몬스터가 존재하지 않을 경우 발동. 이 카드를 패에서 특수소환할 수 있다.',
       zones=HAND, cond=[NO_OWN_MON], do=[special(ref='SELF', src_zone=('hand',))])
    fx(code, '3', '[유언] 이 카드를 묘지에서 특수소환한다.', do=[special(ref='SELF', src_zone=('grave',))])
fx('FGTR-003', '2', '[전투] 상대 필드의 카드 {n}장을 파괴한다. 이 카드는 {a}회 더 공격할 수 있다.',
   do=[destroy(scope=OPP_FIELD, n='$n'), extra_attack('$a')])
fx('FGTR-004', '2', '[전투] 덱에서 「격투가」 카드를 {n}장 패에 넣고, 자신의 HP를 {amt} 회복한다. 이 카드는 {a}회 더 공격할 수 있다.',
   do=[search(FGTR_DECK, '$n'), heal('$amt'), extra_attack('$a')])

for code in ('FGTR-005', 'FGTR-006'):
    fx(code, '1', '[신속] 자신 필드에 몬스터가 존재하지 않을 경우 상대 필드의 카드 {n}장을 대상으로 하고 발동. 이 카드를 특수소환하고, 그 카드를 파괴한다.',
       zones=HAND, cond=[NO_OWN_MON], cost=[target('T', OPP_FIELD, n='$n')],
       do=[special(ref='SELF', src_zone=('hand',)), destroy(ref='T')])
fx('FGTR-005', '2', '[전투] 상대 필드의 카드를 {n}장 파괴한다.', do=[destroy(scope=OPP_FIELD, n='$n')])
fx('FGTR-006', '2', '[전투] 상대 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 파괴한다. 상대에게 {amt} 대미지를 준다.',
   cost=[target('T', OPP_FIELD, n='$n')], do=[destroy(ref='T'), damage('$amt')])

# 격투가 세레모니 — 부여는 영구 · 중첩(재정): 매 턴 공격 횟수 +1, 부여 [전투]는 부여마다 효과 번호 30 + k(부여마다 별개의 1턴 1번, 재정 G3)
fx('FGTR-007', '1', '[전투] 자신 필드의 「격투가」 몬스터 {n}장을 대상으로 하고 발동. 그 카드는 {a}회 더 공격할 수 있으며, 다음의 효과를 얻는다.',
   when=[when('battle_win', any_own=True)],
   cost=[target('T', S('own', 'field', 'monster', group='격투가', faceup=True), n='$n', harm=False)],
   do=[extra_attack('$a', ref='T', perm=True), grant('1-a', ref='T', base=30, stack=True)])
fx('FGTR-007', '1-a', '[전투] 필드의 카드 {n}장을 대상으로 하고 발동. 상대에게 {amt} 대미지를 주고, 그 카드를 파괴한다.',
   granted=True, grant_name='격투가 세레모니',
   cost=[target('T', S('both', 'field'), n='$n')], do=[damage('$amt'), destroy(ref='T')])

# 격투가 입장
fx('FGTR-008', '1', '[신속] 덱에서 「격투가」 몬스터를 {n}장 패에 넣거나 특수소환한다. 이 효과로 특수소환한 몬스터는 이 턴에 상대의 효과를 받지 않는다.',
   do=[choice([search(FGTR_MON_DECK, '$n')],
              [special(scope=FGTR_MON_DECK, n='$n', **{'as': 'X'}), status('immune_opp', ref='X', harm=False)])])
fx('FGTR-008', '2', '[트리거] 자신의 「격투가」 카드가 파괴되었을 때, 묘지의 이 카드를 제외하고 발동한다. 덱에서 「격투가」 카드를 {n}장 패에 넣는다.',
   zones=GRAVE, when=[when('destroyed', who='own', filter=S(group='격투가'))],
   cost=[banish(ref='SELF')], do=[search(FGTR_DECK, '$n')])

# 격투가 반격 — 「존재할 때」는 앞면만(재정 Q47)
fx('FGTR-009', '1', '[트리거] 필드에 「격투가」 카드가 존재할 때, 상대가 효과를 발동하면 발동. 그 효과를 무효로 한다.',
   when=[when('activated', who='opp')], cond=[cnt(S('both', 'field', group='격투가', faceup=True))],
   do=[negate_link()])

# 격투가의 투기장
fx('FGTR-010', '1', '[지속] 상대 필드의 몬스터는 수비 표시로 존재할 수 없다. 상대 필드에 몬스터가 존재할 경우, 상대는 반드시 공격해야 한다. '
   '(이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[forbid('no_defense', who='opp'), forbid('must_attack', who='opp')])
fx('FGTR-010', '2', '[신속] 자신 필드에 몬스터가 존재하지 않을 때 발동. 덱에서 「격투가」 몬스터 {n}장을 패에 넣거나 특수소환한다.',
   cond=[NO_OWN_MON],
   do=[choice([search(FGTR_MON_DECK, '$n')], [special(scope=FGTR_MON_DECK, n='$n')])])
fx('FGTR-010', '3', '[트리거] 상대 필드의 몬스터가 파괴되었을 경우 발동. 덱에서 「격투가」 카드를 {n}장 패에 넣는다. (이 효과로 동명의 카드를 패에 넣을 수 있다.)',
   when=[when('destroyed', who='opp', zone=('m', 'shared'))], do=[search(FGTR_DECK, '$n')])

# 투기장의 규칙 (스킬)
fx('FGTR-011', '1', '[전투] 자신은 덱에서 {n}장 드로우한다.', when=[when('battle_win', any_own=True)], do=[draw('$n')])
fx('FGTR-011', '2', '[신속] 자신 패의 「격투가」 카드를 {n}장 덱으로 되돌린다. 덱에서 「격투가」 카드를 {m}장 패에 넣는다.',
   do=[to_deck(scope=S('own', 'hand', group='격투가'), n='$n', shuffle=True), search(FGTR_DECK, '$m')])
fx('FGTR-011', '3', '자신 패의 「격투가」 카드를 원하는 수까지 덱으로 되돌린다. 그 수만큼 덱에서 카드를 드로우한다.',
   do=[to_deck(scope=S('own', 'hand', group='격투가'), want=True, count_as='N', shuffle=True), draw(('ref', 'N'))])
