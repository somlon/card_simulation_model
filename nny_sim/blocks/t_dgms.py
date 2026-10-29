"""조립표 — 던전마스터 18종 (DGMS). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
「트랩」(뒷면 운용 · 함정 마법) · 「다크」(파괴) · 「던전마스터」(보스 [지속]) 테마. 뒷면 전환 · 뒤집기 · 셔플! 1번 재배치 모델은 공용 함수(cards9.turn_face_down ·
flip_up · swap_cards · keep_set — 카드 이름 분기 없는 처리)를 블록이 쓴다. 효과 종류 표기가 없는 효과는 기동 효과(ASSUME, 예전과 같음).
「묘지」 · 「덱」(새크리파이스 2 · 매지션 1 · 컨트롤러 1)은 자신의 묘지 · 덱(사용자 답변 2026-10-22 Q35)."""
from blocks.dsl import *   # noqa: F401,F403

DM, TRAP, DARK = '던전마스터', '트랩', '다크'
BOX = '던전마스터 깜짝상자'
OPP_FIELD = S('opp', 'field')
BOTH_FIELD = S('both', 'field')
OPP_DRAW = '[유언] 상대는 카드를 {n}장 드로우한다. (이 효과는 강제로 발동한다.)'
FIELD_LIVE = '(이 효과는 1턴에 1번 제약을 받지 않는다.)'


def opp_draw(code, key='3'):
    fx(code, key, OPP_DRAW, do=[draw('$n', who='opp')])


def back_lw(code, key='2'):
    fx(code, key, '[유언] 이 카드를 덱으로 되돌린다.', do=[to_deck(ref='SELF', ref_scope=S('own', 'grave'), shuffle=True, harm=False)])


# ── 메인 덱 몬스터 ──
fx('DGMS-001', '1', '[신속] 이 카드를 앞면 수비 표시로 변경하고 발동. 상대 필드의 카드를 {n}장 파괴한다. 이 효과의 발동은, 원래 주인인 플레이어만 선언할 수 있다. (이 효과는 뒷면 표시일 때만 발동할 수 있다.)',
   owner_only=True, cond=[cond('self_facedown')], cost=[B('flip_up', ref='SELF', pos='def')],
   do=[destroy(scope=S('opp', 'field', not_self=True), n='$n')])
fx('DGMS-001', '2', '[유언] 이 카드를 덱으로 되돌린다. 뒷면 표시의 이 카드가 묘지로 보내졌을 경우, 카드를 {n}장 파괴한다.',
   do=[to_deck(ref='SELF', ref_scope=S('own', 'grave'), shuffle=True, harm=False),
       branch(cond('ev_was_facedown'), [destroy(scope=BOTH_FIELD, n='$n')])])
fx('DGMS-002', '1', '[트리거] 상대의 효과가 발동했을 때 이 카드를 릴리스하고 발동. 그 효과를 무효로 한다.',
   when=[when('activated', who='opp')], cost=[release(ref='SELF')], do=[negate_link()])
back_lw('DGMS-002')
fx('DGMS-003', '1', '[트리거] 상대가 몬스터를 소환했을 때 이 카드를 릴리스하고 상대 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 파괴한다.',
   when=[when('summoned', who='opp')], cost=[release(ref='SELF'), target('T', OPP_FIELD, n='$n')], do=[destroy(ref='T')])
fx('DGMS-003', '2', '[유언] 이 카드를 덱으로 되돌리고, 상급 덱에서 「던전마스터」 카드를 {n}장 패에 넣는다.',
   do=[to_deck(ref='SELF', ref_scope=S('own', 'grave'), shuffle=True, harm=False), search(S('own', 'upper', group=DM), '$n')])

# ── 상급 덱 몬스터 ──
DISCARD_SELF = send_grave(ref='SELF', ref_scope=S('own', 'hand'))
fx('DGMS-004', '1', '패의 이 카드를 버리고 발동. 덱에서 「던전마스터」 카드를 {n}장 패에 넣는다.', zones=HAND, cost=[DISCARD_SELF], do=[search(S('own', 'deck', group=DM), '$n')])
fx('DGMS-004', '2', '패의 이 카드를 버리고 발동. 묘지에서 「던전마스터」 몬스터를 {n}장 특수소환한다.', zones=HAND, cost=[DISCARD_SELF],
   do=[special(scope=S('own', 'grave', 'monster', group=DM, not_self=True), n='$n')])
fx('DGMS-004', '3', '패의 이 카드를 버리고 발동. 덱에서 「트랩」 또는 「다크」 마법 카드를 {n}장 세트한다.', zones=HAND, cost=[DISCARD_SELF],
   do=[place(S('own', 'deck', 'spell', group=(TRAP, DARK)), n='$n', set=True, upto=True)])
fx('DGMS-005', '1', '[신속] 덱에서 「트랩」 카드를 {n}장 세트한다. 이 효과로 세트한 카드는 이 턴에도 발동할 수 있다.',
   do=[place(S('own', 'deck', 'spell', group=TRAP), n='$n', set=True, act_this_turn=True)])
fx('DGMS-005', '2', '[신속] 자신 필드의 카드 {n}장과 상대 필드의 카드 {m}장을 대상으로 하고 발동. 그 2장을 뒷면 표시로 한다.',
   cost=[target('A', S('own', 'field', pred='turnable'), n='$n'), target('T', S('opp', 'field', pred='turnable'), n='$m')],
   do=[B('turn_down', ref='A', soft=True), B('turn_down', ref='T')])
opp_draw('DGMS-005')
fx('DGMS-006', '1', '[신속] 패에서 이 카드를 보여주고 발동. 이 카드를 특수소환한다. 필드의 카드 {n}장을 파괴한다. (이 효과는 1턴에 3번까지 사용할 수 있다.)',
   zones=HAND, cond=[cond('not_on_chain', num=1)], do=[special(ref='SELF', src_zone=('hand',)), destroy(scope=BOTH_FIELD, n='$n')])
fx('DGMS-006', '2', '이 카드를 릴리스하고 상대 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 파괴한다.',
   cost=[release(ref='SELF'), target('T', OPP_FIELD, n='$n')], do=[destroy(ref='T')])
opp_draw('DGMS-006')
fx('DGMS-007', '1', '덱에서 「다크」 마법 카드 {n}장을 패에 넣는다. 종료 단계에, 묘지에서 「던전마스터」 몬스터를 {m}장 패에 넣을 수 있다.',
   do=[search(S('own', 'deck', 'spell', group=DARK), '$n'),
       floating(when('phase', phase='end_step'), [to_hand(scope=S('own', 'grave', 'monster', group=DM, pickable=True), n='$m', harm=False, soft=True)])])
fx('DGMS-007', '2', '[신속] 필드의 카드 {n}장을 파괴한다.', do=[destroy(scope=BOTH_FIELD, n='$n')])
opp_draw('DGMS-007')
fx('DGMS-008', '1', '[신속] 패의 이 카드를 보여주고 발동. 패에서 「던전마스터」 몬스터 {n}장을 특수소환한다.',
   zones=HAND, do=[special(scope=S('own', 'hand', 'monster', group=DM, not_self=True), n='$n')])
fx('DGMS-008', '2', '[신속] 덱에서 「던전마스터 다크나이트」 {n}장을 특수소환한다.', do=[special(scope=S('own', 'deck', 'monster', name='던전마스터 다크나이트'), n='$n')])
opp_draw('DGMS-008')
OPP_MON = S('opp', 'field', 'monster')
fx('DGMS-009', '1', f'[지속] 이 카드가 필드에 존재하는 한, 공격력 {{n}} 이상의 상대 필드의 몬스터는 파괴된다. {FIELD_LIVE}',
   cont=[B('auto_destroy', stat='atk', n='$n', to=OPP_MON)])
fx('DGMS-009', '2', f'[지속] 이 카드가 필드에 존재하는 한, 수비력 {{n}} 이상의 상대 필드의 몬스터는 파괴된다. {FIELD_LIVE}',
   cont=[B('auto_destroy', stat='def', n='$n', to=OPP_MON)])
opp_draw('DGMS-009')
# 헬 1번 뒷문장 — 1번 처리 때 붙는 보호(사용자 답변 2026-10-22 Q33), 「망령」 몬스터 = 필드(양쪽)의 앞면 「던전마스터 망령」(설계도 확정)
MOURNER_ON = cnt(S('both', 'field', 'monster', name_has='망령', faceup=True))
fx('DGMS-010', '1', '자신 덱에서 「망령」 몬스터를 {n}장 특수소환한다. 이 카드는, 「망령」 몬스터가 존재하는 한 전투로는 파괴되지 않으며 효과를 받지 않는다.',
   card=[B('guard_while', flag='hell_guard', **{'while': MOURNER_ON})],
   do=[special(scope=S('own', 'deck', 'monster', name_has='망령'), n='$n'), B('set_flag', key='hell_guard', label='「망령」 몬스터가 존재하는 한 전투로 파괴되지 않고 효과를 받지 않음')])
fx('DGMS-010', '2', '[지속] 이 카드가 필드에 존재하는 한, 상대는 몬스터를 소환할 때마다 {amt}의 대미지를 받는다.',
   cont=[B('whenever', when=when('summoned', who='opp'), steps=(damage('$amt'),))])
opp_draw('DGMS-010')
fx('DGMS-011', '1', '덱 또는 묘지에서 「던전마스터」 몬스터를 특수소환한다.', do=[special(scope=S('own', ('main', 'upper', 'grave'), 'monster', group=DM), n=1)])
fx('DGMS-011', '2', '덱에서 「던전마스터」 카드를 패에 넣는다.', do=[search(S('own', 'deck', group=DM), 1)])
fx('DGMS-011', '3', '[유언] 이 카드를 덱으로 되돌린다. 상대는 카드를 {n}장 드로우한다. (이 효과는 강제로 발동한다.)',
   do=[to_deck(ref='SELF', ref_scope=S('own', 'grave'), shuffle=True, harm=False), draw('$n', who='opp')])
fx('DGMS-012', '1', f'[지속] 이 카드가 몬스터와 전투할 때, 상대 플레이어에게 가하는 대미지는 0이 된다. {FIELD_LIVE}', cont=[B('no_battle_damage_self')])
fx('DGMS-012', '2', f'[지속] 이 카드가 필드에 존재하는 한, 상대는 효과로 덱에서 카드를 패에 넣을 수 없다. {FIELD_LIVE}', cont=[forbid('no_deck_to_hand', who='opp')])
opp_draw('DGMS-012')

# ── 마법 ──
fx('DGMS-013', '1', '[트리거] 상대가 몬스터를 소환했을 때 발동. 그 카드를 파괴한다.',
   when=[when('summoned', who='opp')], do=[destroy(ref='EV', ref_scope=S('opp', 'field'))])
# 트랩: 깜짝상자 — 바뀐 효과는 그 카드의 효과(그 카드의 플레이어가 처리): 「상대」 = 이 카드의 플레이어가 자신의 덱에서 특수소환, 그 2장 = 그 카드 · 깜짝상자
fx('DGMS-014', '1', '[트리거] 상대가 효과를 발동했을 때 발동. 그 카드의 효과를 다음과 같이 변경한다 — 「상대는 덱에서 「던전마스터 깜짝상자」를 특수소환한다. 그 후, 그 2장을 뒷면 표시로 한다.」',
   when=[when('activated', who='opp')], cond=[can(special(scope=S('own', 'deck', 'monster', name=BOX)))],
   do=[replace([special(scope=S('own', 'deck', 'monster', name=BOX), who='opp', **{'as': 'B'}),
                B('turn_down', ref='B'), B('turn_down', ref='SELF', keep_set=True, soft=True)], label='상대는 덱에서 「던전마스터 깜짝상자」 특수소환 · 그 2장 뒷면')])
fx('DGMS-015', '1', '[트리거] 상대가 카드를 패에 넣었을 때 발동. 턴 종료 시까지 상대에게 이하의 효과를 적용한다.\n- 자신은 전투로 몬스터를 파괴할 수 없다.\n'
   '- 자신이 카드를 효과로 제거할 때마다, {amt} 대미지를 받는다.',
   when=[when('hand_added', who='opp')],
   do=[B('battle_shield'), floating(when('left_field', by_effect_of='opp'), [damage('$amt', who='opp')])])
# 지속 마법의 표기 없는 효과 — 카드의 발동 때 처리하고, 앞면으로 있는 동안 1턴 1번 기동 효과로도(재정 정리 2026-10-17)
fx('DGMS-016', '1', '묘지의 「트랩」 카드를 {n}장까지 덱으로 되돌린다. 자신은 카드를 {m}장 드로우한다.',
   spell_act=True, zones=HAND_FIELD, reuse=True,
   do=[to_deck(scope=S('own', 'grave', group=TRAP), n='$n', upto=True, harm=False, shuffle=True), draw('$m')])
fx('DGMS-017', '1', f'[지속] 자신의 [유언] 효과가 발동할 때, 그 효과를 「이 카드를 덱으로 되돌리고 「던전마스터」 카드를 {{n}}장 패에 넣는다.」로 변경할 수 있다. {FIELD_LIVE}',
   cont=[B('lw_replace', steps=(to_deck(ref='SELF', ref_scope=S('own', 'grave'), shuffle=True, harm=False), search(S('own', 'deck', group=DM), '$n')),
           label='덱으로 되돌리고 「던전마스터」 카드 서치')])
fx('DGMS-017', '2', '자신 묘지에서 「던전마스터」 몬스터 {n}장을 특수소환한다.', spell_act=True, zones=HAND_FIELD, reuse=True,
   do=[special(scope=S('own', 'grave', 'monster', group=DM), n='$n')])

# ── 스킬 ──
fx('DGMS-018', '1', '필드의 뒷면 표시 카드를 전부 원하는 대로 재배치한다. (단, 룰에 어긋나는 배치는 할 수 없다.)', do=[B('rearrange')])
fx('DGMS-018', '2', '[신속] 필드의 뒷면 표시 몬스터 {n}장을 앞면 표시로 뒤집는다.', do=[B('flip_pick')])
fx('DGMS-018', '3', '패에서 레벨 {lv} 이상의 몬스터를 특수소환한다.', do=[special(scope=S('own', 'hand', 'monster', level=('>=', '$lv')), n=1)])
