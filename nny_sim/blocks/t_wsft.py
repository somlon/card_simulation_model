"""조립표 — 소원의 분수 27종 (WSFT). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
자신의 메인 덱을 묘지로 보내는 것이 자원이 되는 테마 — 덱에서 묘지로 간 카드의 [유언]이 발동한다(Game.dump, 가치는 lib.lw_bonus).
[유언] 단서(덱에서 · 필드에서 · 자신의 효과를 발동하기 위해 묘지로 보내졌을 경우 발동하지 않음)는 text.notes가 읽는다(「자신」 = 이 카드, 사용자 답변 2026-10-20).
행운의 도적 2번 「자신의 「코인」 카드의 효과를 「…」로 변경할 수 있다」는 [지속] 효과 변경(status.k_swap — 처리 때 lib.swapped)."""
from blocks.dsl import *   # noqa: F401,F403

WISH4 = ('행운', '용기', '지혜', '희생')
OPP_FIELD = S('opp', 'field')
FIELD_ZONES = ('m', 's', 'shared', 'fieldz')
OWN_FIELD_TO_GRAVE = when('sent_grave', prev=FIELD_ZONES, ctrl='own')
SELF_FROM_HAND = send_grave(ref='SELF', ref_scope=S('own', 'hand'))
NOT_FROM_DECK = '(이 카드가 덱에서 묘지로 보내졌을 경우 이 효과는 발동하지 않는다.)'
NOT_COST = '(자신의 효과를 발동하기 위해 묘지로 보내졌을 경우, 이 효과는 발동하지 않는다.)'
NOT_FROM_FIELD = '(이 효과는 필드에서 묘지로 보내졌을 경우, 발동하지 않는다.)'


def coin_lastwill(code, own=True):
    fx(code, '2', f'[유언] {"자신의 " if own else ""}메인 덱의 위에서부터 카드를 {{n}}장 묘지로 보낸다. {NOT_FROM_DECK}',
       do=[mill('$n', dest='grave')])


def recycle_lw(code, key, group=None, where='묘지에서', note=''):
    what = f'「{group}」' if group else '다른'
    fx(code, key, f'[유언] {where} 이 카드와 {what} 카드 {{n}}장을 덱으로 되돌린다.' + (f' {note}' if note else ''),
       do=recycle(group, '$n'))


# ── 몬스터 ──
fx('WSFT-001', '1', '[소환] 메인 덱에서 「코인」 카드를 {n}장 패에 넣는다.', do=[search(S('own', 'main', group='코인'), '$n')])
fx('WSFT-001', '2', '[트리거] 자신의 「코인」 카드가 덱에서 묘지로 보내졌을 때 발동. 묘지에서 「코인」 몬스터 {n}장을 패에 넣는다.',
   when=[when('sent_grave', prev=('main', 'upper'), ctrl='own', filter=S(group='코인'))],
   do=[to_hand(scope=S('own', 'grave', 'monster', group='코인', pickable=True), n='$n', harm=False)])

fx('WSFT-002', '1', '[트리거] 자신 필드의 카드가 묘지로 보내졌을 때 발동. 이 카드를 패에서 버린다.',
   zones=HAND, when=[OWN_FIELD_TO_GRAVE], do=[SELF_FROM_HAND])
coin_lastwill('WSFT-002', own=False)

fx('WSFT-003', '1', '[유언] 자신 묘지에서 {lv}레벨 이하의 몬스터를 {n}장 특수소환한다.',
   do=[special(scope=S('own', 'grave', 'monster', level=('<=', '$lv')), n='$n')])

fx('WSFT-004', '1', '[트리거] 상대가 몬스터를 소환했을 때 발동. 이 카드를 패에서 버린다.',
   zones=HAND, when=[when('summoned', who='opp')], do=[SELF_FROM_HAND])
coin_lastwill('WSFT-004')

fx('WSFT-005', '1', '[유언] 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 파괴한다.',
   cost=[target('T', S('both', 'field'), n='$n')], do=[destroy(ref='T')])

fx('WSFT-006', '1', '[트리거] 상대가 마법 카드를 발동했을 때, 이 카드를 패에서 버린다.',
   zones=HAND, when=[when('activated_ev', who='opp', card_only=True, type='마법')], do=[SELF_FROM_HAND])
coin_lastwill('WSFT-006')

# 지혜의 사서 — 「필드의 카드」의 무효는 스킬도(예전 구현 · 솔루나와 같은 해석)
fx('WSFT-007', '1', '[유언] 필드의 카드 {n}장을 대상으로 하고 발동. 그 효과를 턴 종료 시까지 무효로 한다.',
   cost=[target('T', S('both', ('field', 'skill'), faceup=True, pred='not_negated'), n='$n')], do=[negate_card(ref='T')])

fx('WSFT-008', '1', '[신속] 이 카드를 패에서 보여주고 발동. 이 카드를 버린다.', zones=HAND, do=[SELF_FROM_HAND])
coin_lastwill('WSFT-008', own=False)

fx('WSFT-009', '1', '[유언] 덱에서 「행운」 카드를 {n}장 패에 넣는다.', do=[search(S('own', 'deck', group='행운'), '$n')])

# 행운의 도적 — 1번 코스트는 낼 수도 안 낼 수도(「발동할 수도 있다」), 낸 경우만 1장 더
fx('WSFT-010', '1', '[소환] 자신 필드의 카드 {n}장을 묘지로 보내고 발동할 수도 있다. 자신은 덱에서 {m}장 드로우한다. 카드를 묘지로 보내고 발동했을 경우, {k}장 더 드로우한다.',
   cost=[send_grave(scope=S('own', 'field'), n='$n', may=True, gain=(draw('$k'),), **{'as': 'SENT'})],
   do=[draw('$m'), branch(cond('ref_true', ref='SENT'), [draw('$k')])])
fx('WSFT-010', '2', '[지속] 자신의 「코인」 카드의 효과를 「메인 덱에서 카드 {n}장을 묘지로 보낸다」로 변경할 수 있다.',
   cont=[swap(S(group='코인'), [deck_to_grave('$n')], label='메인 덱에서 카드 1장을 묘지로 보낸다')])
recycle_lw('WSFT-010', '3', '행운')

fx('WSFT-011', '1', '[트리거] 상대가 효과를 발동했을 때 발동. 그 효과를 무효로 한다.',
   when=[when('activated', who='opp')], do=[negate_link()])
fx('WSFT-011', '2', '[트리거] 카드를 파괴하는 효과가 발동되었을 때 발동. 그 효과를 무효로 한다. (이 효과의 사용 후, 다음 턴까지 자신은 이 효과를 사용할 수 없다.)',
   when=[when('activated', destroys=True)], do=[negate_link()])
recycle_lw('WSFT-011', '3', '지혜')

fx('WSFT-012', '1', '[신속] 상대 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 파괴한다. 이 카드의 공격력은 턴 종료 시까지 {amt} 오른다.',
   cost=[target('T', OPP_FIELD, n='$n')], do=[destroy(ref='T'), stat('$amt', ref='SELF', harm=False)])
fx('WSFT-012', '2', '[지속] 이 카드가 존재하는 한, 자신 필드의 「용기」 몬스터는 {n}회 공격할 수 있다.',
   cont=[rule_to('double_attack', S('own', 'field', 'monster', group='용기'))])
recycle_lw('WSFT-012', '3', '용기')

# 희생의 성녀 — 2번: 묘지로 보내진 그 카드를 종류에 따라 되살린다(되살릴 수 있어야 발동)
fx('WSFT-013', '1', '[소환] 자신 묘지에서 몬스터를 {n}장 특수소환한다.', do=[special(scope=S('own', 'grave', 'monster'), n='$n')])
EV_GRAVE = S('both', 'grave')
fx('WSFT-013', '2', '[트리거] 자신 필드의 카드가 묘지로 보내졌을 경우, 이 카드를 묘지로 보내고 발동. 묘지로 보내진 카드에 따라 효과가 정해진다.\n'
   '- 몬스터: 그 카드를 자신 필드에 특수소환한다.\n- 지속 마법·필드 마법: 그 카드를 자신 필드에 앞면으로 놓는다.\n'
   '- 일반·트리거·신속 마법: 그 카드를 자신 필드에 세트한다.',
   when=[OWN_FIELD_TO_GRAVE], cond=[cond('ev_back')], cost=[send_grave(ref='SELF')],
   do=[branch(ev_card(kind='monster'), [special(ref='EV', ref_scope=EV_GRAVE, harm=False)],
              [branch(ev_card(kind='field_spell'), [place(None, ref='EV', ref_scope=EV_GRAVE)],
                      [branch(ev_card(kind=('cont',)), [place(None, ref='EV', ref_scope=EV_GRAVE)],
                              [place(None, ref='EV', ref_scope=EV_GRAVE, set=True)])])])])
recycle_lw('WSFT-013', '3', '희생')

# 기적의 영웅 — 3 · 4번은 공격력/수비력이 0에 도달하면 더는 발동할 수 없다(재정)
SHRINK = '공격력/수비력을 {amt} 내린다.'
fx('WSFT-014', '1', '[제약] 이 카드는 스킬 카드의 효과로만 특수소환할 수 있다.', card=[effect_only(by='skill')])
fx('WSFT-014', '2', '[지속] 필드의 이 카드는 릴리스할 수 없으며, 다른 카드의 효과를 받지 않는다. 필드의 이 카드는 「행운」·「용기」·「지혜」·「희생」 카드로도 취급한다.',
   cont=[card_flag('no_release'), card_flag('immune_others'), card_flag('also_groups', value=WISH4)])
fx('WSFT-014', '3', f'[신속] 상대 필드의 카드 {{n}}장을 파괴한다. 이 카드의 {SHRINK} (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cond=[cond('self_stat_pos')], do=[destroy(scope=OPP_FIELD, n='$n'), stat('-$amt', stat='both', ref='SELF', until=None)])
fx('WSFT-014', '4', f'[트리거] 상대가 카드의 효과를 발동했을 때 발동. 그 효과를 무효로 하고, 이 카드의 {SHRINK} (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   when=[when('activated', who='opp')], cond=[cond('self_stat_pos')],
   do=[negate_link(), stat('-$amt', stat='both', ref='SELF', until=None)])

# ── 마법 · 필드 ──
fx('WSFT-015', '1', '자신의 메인 덱 위에서부터 카드를 {n}장 묘지로 보낸다. 「행운」 카드가 묘지로 보내졌을 경우, 카드를 {m}장 드로우한다.',
   do=[mill('$n', dest='grave', **{'as': 'OUT'}), branch(cond('ref_has', ref='OUT', filter=S(group='행운')), [draw('$m')])])
recycle_lw('WSFT-015', '2', '행운', note=NOT_COST)
fx('WSFT-016', '1', '[신속] 상대 필드의 카드 {n}장을 파괴한다.', do=[destroy(scope=OPP_FIELD, n='$n')])
recycle_lw('WSFT-016', '2', '용기', where='묘지의', note=NOT_COST)
# 지혜의 원천 - 마도서 — 「상대가 카드를 발동했을 때」는 카드의 발동만(사용자 답변 2026-10-20)
fx('WSFT-017', '1', '[트리거] 상대가 카드를 발동했을 때 자신 필드의 카드 {n}장을 묘지로 보내고 발동. 그 효과를 무효로 한다.',
   when=[when('activated', who='opp', card_only=True)], cost=[send_grave(scope=S('own', 'field'), n='$n')], do=[negate_link()])
recycle_lw('WSFT-017', '2', '지혜', where='묘지의', note=NOT_COST)
fx('WSFT-018', '1', '[트리거] 자신 필드의 카드가 묘지로 보내졌을 때 발동. 자신 묘지에서 레벨 {lv} 이하의 몬스터를 {n}장 특수소환한다.',
   when=[OWN_FIELD_TO_GRAVE], do=[special(scope=S('own', 'grave', 'monster', level=('<=', '$lv')), n='$n')])
recycle_lw('WSFT-018', '2', '희생', where='묘지의', note=NOT_COST)

for i, grp_ in zip(range(19, 23), WISH4):
    code = f'WSFT-{i:03d}'
    fx(code, '1', '이 카드를 덱으로 되돌리고 {n}장 드로우한다.', do=[to_deck(ref='SELF', shuffle=True, harm=False), draw('$n')])
    fx(code, '2', f'[유언] 덱에서 「{grp_}」 카드를 특수소환하거나 패에 넣는다. {NOT_FROM_FIELD}',
       do=[choice([special(scope=S('own', 'deck', 'monster', group=grp_), n=1)], [search(S('own', 'deck', group=grp_), 1)])])

fx('WSFT-023', '1', '[트리거] 상대가 효과를 발동했을 때 발동. 덱에서 「코인」 카드를 패에 넣는다.',
   when=[when('activated', who='opp')], do=[search(S('own', 'deck', group='코인'), 1)])
recycle_lw('WSFT-023', '2', where='묘지의')
# 염원 — 「패에 넣었을 때」는 드로우 포함(사용자 답변 2026-10-28), 상대가 고른다
fx('WSFT-024', '1', '[트리거] 상대가 카드를 패에 넣었을 때 발동. 이하의 효과 중 1개를 적용한다. (적용할 효과는 상대가 고른다.)\n'
   '- 자신은 메인 덱 맨 위에서 카드를 {n}장 묘지로 보낸다.\n- 패에 넣은 카드를 제외한다.',
   when=[when('hand_added', who='opp')],
   do=[choice([mill('$n', dest='grave')], [banish(ref='EV', ref_scope=S('opp', 'hand'))], chooser='opp')])
recycle_lw('WSFT-024', '2', where='묘지의')
fx('WSFT-025', '1', '[트리거] 필드에 몬스터가 소환되었을 때, 자신의 메인 덱 위에서부터 카드를 {n}장 묘지로 보낸다.',
   when=[when('summoned')], do=[mill('$n', dest='grave')])
fx('WSFT-025', '2', f'[유언] 이 카드를 마법 존에 앞면 표시로 놓는다. {NOT_FROM_FIELD}', do=[place(None, ref='SELF', ref_scope=S('own', 'grave'))])
fx('WSFT-026', '1', '[지속] 자신이 메인 덱 맨 위에서부터 카드를 묘지로 보낼 때, {n}장을 추가로 보낼 수 있다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[player_rule('dump_extra', who='own')])
recycle_lw('WSFT-026', '2', where='묘지의')

# ── 스킬 ──
fx('WSFT-027', '1', '[신속] 자신의 묘지에서 「행운」·「용기」·「지혜」·「희생」 카드를 각각 {n}장씩 제외하고 발동한다. 상급 덱에서 「기적의 영웅」 {m}장을 특수소환한다.',
   cost=[kinds(S('own', 'grave'), WISH4, per='$n')], do=[special(scope=S('own', 'upper', 'monster', name='기적의 영웅'), n='$m')])
fx('WSFT-027', '2', '[신속] 자신 필드/묘지에서 「행운」·「용기」·「지혜」·「희생」 카드를 합계 {n}장 제외하고 발동한다. (같은 종류는 {cap}장까지) 상대 필드의 카드 {m}장을 묘지로 보낸다.',
   cost=[kinds(S('own', ('field', 'grave')), WISH4, total='$n', cap='$cap')], do=[send_grave(scope=OPP_FIELD, n='$m')])
