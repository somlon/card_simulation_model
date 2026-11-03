"""조립표 — 번성충 15종 (SWRM). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
맹세 제약(「이 효과를 발동한 턴, 자신은 「번성충」 카드만 …」)은 발동할 때 건다(코스트 칸의 oath — 텍스트상 「발동한 턴」)."""
from blocks.dsl import *   # noqa: F401,F403

OATH = '이 효과를 발동한 턴, 자신은 「번성충」 카드만 사용할 수 있으며, 이 제약은 다음 상대 턴 종료 시까지 적용된다.'
DIRECT = '[지속] 이 카드는 상대 몬스터가 존재해도 직접공격할 수 있다. (이 효과는 1턴에 1번 제약을 받지 않는다.)'
BSC = '번성충'
SELF_HAND = dict(ref='SELF', src_zone=('hand',))
TO_GRAVE_SELF = send_grave(ref='SELF')

for i in range(1, 11):
    fx(f'SWRM-{i:03d}', '2', DIRECT, cont=[self_rule('direct_attack')])

fx('SWRM-001', '1', f'[신속] 상대 묘지의 카드 {{n}}장을 제외하고 발동. 이 카드를 패에서 특수소환한다. {OATH}',
   zones=HAND, cost=[banish(scope=S('opp', 'grave'), n='$n'), oath(BSC)], do=[special(**SELF_HAND)])
fx('SWRM-002', '1', f'[신속] 이 카드를 패에서 상대 필드의 앞면 표시 몬스터 {{n}}장에 장착 마법 카드 취급으로 장착하고 발동. '
   f'이 카드가 장착된 몬스터가 필드에서 벗어났을 경우, 덱에서 「번성충」 몬스터 {{m}}장을 패에 넣는다. {OATH}',
   zones=HAND,
   cost=[choose_at_act('T', S('opp', 'field', 'monster', faceup=True), n='$n'),
         equip(ref='T', from_hand=True, on_leave=(search(S('own', 'deck', 'monster', group=BSC), '$m'),)), oath(BSC)])
fx('SWRM-003', '1', f'[신속] 이 카드를 패에서 묘지로 보내고 발동. 이 턴, 상대가 몬스터를 소환할 때마다 덱에서 「번성충」 마법 카드 {{n}}장을 패에 넣는다. {OATH}',
   zones=HAND, cost=[TO_GRAVE_SELF, oath(BSC)],
   do=[floating(when('summoned', who='opp'), [search(S('own', 'deck', 'spell', group=BSC), '$n')])])
# 메뚜기여왕 1번: 상대 필드의 「몬스터」만 릴리스(사용자 지시 2026-10-29 — 카드 텍스트 「카드」 → 「몬스터」, data/fix-swrm004-text)
fx('SWRM-004', '1', f'[신속] 상대 필드의 몬스터 {{n}}장을 릴리스하고 발동. 이 카드를 패에서 특수소환한다. {OATH}',
   zones=HAND, cost=[release(scope=S('opp', 'field', 'monster', pred='releasable'), n='$n'), oath(BSC)], do=[special(**SELF_HAND)])
# 노린재 — 바뀐 효과의 「상대 플레이어」 = 노린재를 쓴 플레이어의 상대(바뀐 효과를 발동한 플레이어)가 드로우(예전 구현과 같은 해석)
fx('SWRM-005', '1', f'[트리거] 상대가 카드의 효과를 발동하였을 때, 이 카드를 패에서 묘지로 보내고 발동. '
   f'그 효과를 「상대 플레이어는 자신의 덱에서 카드 {{n}}장을 드로우한다」로 변경하여 처리한다. {OATH}',
   zones=HAND, when=[when('activated', who='opp')], cost=[TO_GRAVE_SELF, oath(BSC)],
   do=[replace([draw('$n', who='self')], label='상대 플레이어는 1장 드로우')])
fx('SWRM-006', '1', f'[신속] 상대 필드의 몬스터 {{n}}장을 대상으로 하고 발동. 이 카드를 패에서 특수소환한다. 그 카드를 장착카드로 취급하여 이 카드에 장착한다. {OATH}',
   zones=HAND, cost=[target('T', S('opp', 'field', 'monster'), n='$n'), oath(BSC)],
   do=[special(**SELF_HAND), equip_card(ref='T')])
fx('SWRM-007', '1', f'[신속] 이 카드를 패에서 묘지로 보내고 발동. 서로의 묘지에 있는 모든 카드를 각자의 덱으로 되돌려 셔플한다. {OATH}',
   zones=HAND, cost=[TO_GRAVE_SELF, oath(BSC)],
   do=[to_deck(scope=S('both', 'grave'), all=True, zero_ok=True, shuffle='both')])
fx('SWRM-008', '1', f'[신속] 상대 필드의 마법 카드 {{n}}장을 릴리스하고 발동. 이 카드를 패에서 특수소환한다. {OATH}',
   zones=HAND, cost=[release(scope=S('opp', 'field', 'spell', pred='releasable'), n='$n'), oath(BSC)], do=[special(**SELF_HAND)])
fx('SWRM-009', '1', f'[신속] 필드 존에 상대 카드가 있을 경우, 이 카드를 패에서 묘지로 보내고 발동. 자신의 덱에서 「번성충」 필드 카드 {{n}}장을 골라 발동한다. {OATH}',
   zones=HAND, cond=[cnt(S('opp', 'szone', 'field_spell'))], cost=[TO_GRAVE_SELF, oath(BSC)],
   do=[place(S('own', 'deck', 'field_spell', group=BSC))])
fx('SWRM-010', '1', f'[신속] 이 카드를 패에서 묘지로 보내고 발동. 이 턴, 상대 플레이어는 몬스터로 공격할 수 없다. {OATH}',
   zones=HAND, cost=[TO_GRAVE_SELF, oath(BSC)], do=[no_attack()])

BSC_GRAVE_MON = S('own', 'grave', 'monster', group=BSC)
fx('SWRM-015', '1', '상대 필드의 몬스터를 자신 묘지의 「번성충」 몬스터 수(최대 {cap}장)만큼 지정하고 발동. '
   '지정한 상대 필드의 몬스터를 전부 릴리스하고, 그 수만큼 자신 묘지의 「번성충」 몬스터를 특수소환한다.',
   cost=[target('T', S('opp', 'field', 'monster', pred='releasable'), n_count=(BSC_GRAVE_MON, '$cap'))],
   do=[release(ref='T', count_as='N'), special(scope=BSC_GRAVE_MON, n=('ref', 'N'))])
fx('SWRM-016', '1', '[트리거] 자신 필드의 「번성충」 몬스터가 상대의 몬스터 카드에 의해 묘지로 보내졌을 때, 그 상대 몬스터 {n}장을 고르고 발동. '
   '그 몬스터를 파괴하고, 덱에서 「번성충」 몬스터를 {m}장 패에 넣는다.',
   when=[when('sent_grave', prev=('m', 'shared'), ctrl='own', filter=S(kind='monster', group=BSC), by='opp_monster')],
   do=[destroy(ref='EVCAUSE'), search(S('own', 'deck', 'monster', group=BSC), '$m')])
# 대장정 — 덱 위를 확인한 뒤 고르기는 숨은 정보라, 고를 카드가 없으면 건너뛰고 나머지를 덱 아래로(soft)
fx('SWRM-017', '1', '자신의 상급 덱 위에서 카드 {n}장을 확인하고 그 중 「번성충」 카드 {a}장을 골라 자신의 패에 넣고, '
   '다른 「번성충」 몬스터 {b}장을 골라 자신의 묘지로 보낸다. 나머지 카드는 임의의 순서로 덱 아래로 되돌린다.',
   cond=[cnt(S('own', 'upper'))],
   do=[look('TOP', '$n'), to_hand(scope=S(among='TOP', group=BSC, look_n='$n'), n='$a', harm=False, soft=True),
       send_grave(scope=S(among='TOP', kind='monster', group=BSC, look_n='$n'), n='$b', soft=True), to_bottom('TOP')])
# 처리 시점: 종료 단계 c(패 7장 확인 뒤) — soltop_ 요청(2026-10-31, 디스코드 `?`)으로 a→c 변경, engine.py play_turn 참고
fx('SWRM-019', '1', '[지속] 각 턴의 종료 시에, 덱에서 「번성충」 카드 {n}장을 패에 넣는다.',
   cont=[end_process([search(S('own', 'deck', group=BSC), '$n', picker='breeding')], phase='c')])
# 대발생 — 자신 필드는 앞면만 센다(재정 Q48)
fx('SWRM-020', '1', '[지속] 자신 필드 및 자신 묘지의 「번성충」 카드의 수 × {amt} 만큼, 자신 필드의 「번성충」 몬스터의 공격력을 올린다.',
   cont=[stat_mod(S('own', 'field', 'monster', group=BSC, faceup=True), '$amt',
                  per=(S('own', 'field', group=BSC, faceup=True), S('own', 'grave', group=BSC)))])
