"""조립표 — 솔루나 24종 (SLNA). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
아츠 2단 구조: 「n번 효과 처리 시에 자신 필드에 「X」 몬스터가 존재할 경우, … (이 효과는 별도의 발동 처리를 필요로 하지 않는다.)」는 n번 효과의 처리에 딸린다
(follow — 조건은 처리 시작 때, 그 번호도 1턴 1번, n번이 무효화되면 처리되지 않는다 — 2026-10-08 텍스트 · 재정)."""
from blocks.dsl import *   # noqa: F401,F403

SIA_MON = S('own', 'field', 'monster', group='시아', faceup=True)
CIEL_MON = S('own', 'field', 'monster', group='시엘', faceup=True)
HAS_SIA, HAS_CIEL = cnt(SIA_MON), cnt(CIEL_MON)
SIA_OR_CIEL = ('시아', '시엘')
OPP_FIELD = S('opp', 'field')
BOTH_FIELD = S('both', 'field')
FOLLOW = '(이 효과는 별도의 발동 처리를 필요로 하지 않는다.)'


def follow(code, key, tmpl, cond, do, of='1'):
    fx(code, key, tmpl, follow=of, cond=cond, do=do)


# 솔루나 시아 · 시엘
fx('SLNA-001', '1', '[신속] 자신 필드에 「시엘」 몬스터가 존재할 때 발동. 이 카드를 패에서 특수소환한다.',
   zones=HAND, cond=[HAS_CIEL], do=[special(ref='SELF', src_zone=('hand',))])
fx('SLNA-001', '2', '[소환] 자신 필드에 「시엘」 몬스터가 존재할 때 발동. 필드의 카드 {n}장을 파괴한다.',
   cond=[HAS_CIEL], do=[destroy(scope=BOTH_FIELD, n='$n')])
# 3번: 「필드에 「시엘」이 있으면」은 처리 때 판정(양쪽 필드의 앞면 「시엘」 카드) — 없으면 아무 일도 없음(재정)
fx('SLNA-001', '3', '[트리거] 상대가 효과를 발동했을 때 발동. 필드에 「시엘」이 있으면 그 효과를 무효로 한다.',
   when=[when('activated', who='opp')],
   do=[branch(cnt(S('both', 'field', group='시엘', faceup=True)), [negate_link()])])
fx('SLNA-002', '1', '[신속] 자신 필드에 「시아」 몬스터가 존재할 때 발동. 이 카드를 패에서 특수소환한다.',
   zones=HAND, cond=[HAS_SIA], do=[special(ref='SELF', src_zone=('hand',))])
fx('SLNA-002', '2', '[소환] 자신 필드에 「시아」 몬스터가 존재할 때 발동. 필드의 카드 {n}장을 덱으로 되돌린다.',
   cond=[HAS_SIA], do=[to_deck(scope=BOTH_FIELD, n='$n')])
fx('SLNA-002', '3', '[전투] 턴 종료 시까지 이 카드의 공격력을 {amt} 올리고, 한 번 더 공격할 수 있다.',
   do=[stat('$amt', ref='SELF', harm=False), extra_attack(1)])

# 코로나 이그니스 · 블러드문 리퍼 — 1번 [제약](소환 조건 — 패 · 덱 · 묘지에서도), 2번 「덱으로 되돌아간다」(키워드 없음 — 어디서나)
for code in ('SLNA-003', 'SLNA-004'):
    fx(code, '1', '[제약] 이 카드는 카드의 효과로만 소환할 수 있다.', card=[effect_only()])
    fx(code, '2', '이 카드는 묘지로 보내질 경우 덱으로 되돌아간다.', no_effect=True, card=[grave_redirect()])
fx('SLNA-003', '3', '[트리거] 상대 필드의 카드가 효과로 필드를 벗어났을 때 발동. 상대에게 {amt} 대미지를 준다.',
   when=[when('left_field', ctrl='opp', cause='effect')], do=[damage('$amt')])
fx('SLNA-003', '4', '[트리거] 상대의 효과가 발동했을 때 발동. 그 효과를 무효로 하고 파괴한다.',
   when=[when('activated', who='opp')], do=[negate_link(destroy=True)])
# 3번 — 한 번 적용하면 그 턴 동안 상대 몬스터 전부에 공격(사용자 지시 2026-10-22), 무효면 적용 안 함(Game.cont_flag)
fx('SLNA-004', '3', '[지속] 이 카드는 상대 몬스터 전부에 공격 선언을 할 수 있다.', cont=[card_flag('attack_all', lasting=True)])
fx('SLNA-004', '4', '[전투] 상대 필드의 카드 {n}장을 제외한다. 자신의 HP를 {amt} 회복한다. (이 효과는 1턴에 3번까지 사용할 수 있다.)',
   do=[banish(scope=OPP_FIELD, n='$n'), heal('$amt')])

# 솔루나 인카운터 — 2번 「이미 존재할 경우」는 1번 처리 전(처리 시작 때) 판정
fx('SLNA-005', '1', '[신속] 메인 덱에서 「솔루나」 몬스터를 {n}장 특수소환한다. (이 카드는 패에서도 발동할 수 있다.)',
   do=[special(scope=S('own', 'main', 'monster', group='솔루나'), n='$n')])
follow('SLNA-005', '2', '1번 효과 처리 시에 자신 필드에 「솔루나」 몬스터가 이미 존재할 경우, 덱에서 「솔루나」 지속 마법을 앞면으로 놓거나 '
       f'「시아」 또는 「시엘」 카드를 {{n}}장 패에 넣는다. {FOLLOW}',
       [cnt(S('own', 'field', 'monster', group='솔루나', faceup=True))],
       [choice([place(S('own', 'deck', ('cont',), group='솔루나'))], [search(S('own', 'deck', group=SIA_OR_CIEL), '$n')])])

# 여명과 황혼의 궤적 (지속 마법)
fx('SLNA-006', '1', '[신속] 자신 필드의 「솔루나」 몬스터 {n}장을 패로 되돌리고 발동. 덱에서 「시아」 또는 「시엘」 카드를 {m}장 패에 넣는다.',
   cost=[to_hand(scope=S('own', 'field', 'monster', group='솔루나', faceup=True), n='$n')],
   do=[search(S('own', 'deck', group=SIA_OR_CIEL), '$m')])
fx('SLNA-006', '2', '[트리거] 자신 필드의 「솔루나」 몬스터가 묘지로 보내졌을 때 이하의 효과를 발동한다.\n'
   '- 시엘: 패 또는 묘지에서 「시아」 몬스터를 {n}장 특수소환한다.\n- 시아: 패 또는 묘지에서 「시엘」 몬스터를 {n}장 특수소환한다.',
   when=[when('sent_grave', prev=('m', 'shared'), ctrl='own', filter=S(kind='monster', group=SIA_OR_CIEL))],
   do=[branch(ev_card(group='시엘'),
              [special(scope=S('own', ('hand', 'grave'), 'monster', group='시아'), n='$n')],
              [special(scope=S('own', ('hand', 'grave'), 'monster', group='시엘'), n='$n')])])

# 듀얼 컴뱃 — 「각각 1장씩 존재할 경우」는 처리 때 판정(텍스트)
fx('SLNA-007', '1', '[신속] 메인 덱에서 「시아」 또는 「시엘」 카드를 {n}장 패에 넣는다. 자신 필드에 「시아」·「시엘」 몬스터가 각각 1장씩 존재할 경우, '
   '덱에서 「솔루나」 카드를 {m}장 패에 넣는다.',
   do=[search(S('own', 'main', group=SIA_OR_CIEL), '$n'),
       branch(B('cond_all', of=(HAS_SIA, HAS_CIEL)), [search(S('own', 'deck', group='솔루나'), '$m')])])

# 태양과 달의 가호 (지속 마법) — 「세트」는 마법 카드를 마법 존에 뒷면으로(재정 던전마스터 2)
fx('SLNA-008', '1', '[신속] 패를 {n}장 버린다. 덱에서 「시아」 또는 「시엘」 카드를 {m}장 세트한다. 이 효과로 세트한 카드는 이 턴에도 발동할 수 있다.',
   do=[discard('$n'), place(S('own', 'deck', 'spell', group=SIA_OR_CIEL), set=True, act_this_turn=True)])
fx('SLNA-008', '2', '[신속] 메인 덱에서 「솔루나」 몬스터 {n}장을 특수소환한다.',
   do=[special(scope=S('own', 'main', 'monster', group='솔루나'), n='$n')])

# 천체정렬 — 「2장까지」 = 1 · 2장(재정 Q19), 버리는 수는 놓을 수 있는 만큼(빈 마법 존 · 덱의 지속 마법)
CONT_SOL = S('own', 'deck', ('cont',), group='솔루나')
fx('SLNA-009', '1', '자신의 패를 {n}장까지 버린다. 덱에서 「솔루나」 지속 마법을 버린 수까지 앞면 표시로 놓는다. (이 카드는 패에서도 발동할 수 있다.)',
   do=[discard('$n', upto=True, count_as='N', cap_by=('free_s', CONT_SOL)), place(CONT_SOL, n=('ref', 'N'), upto=True)])
fx('SLNA-009', '2', '[신속] 자신의 패에서 동명의 카드를 묘지로 보내고, 묘지의 이 카드를 제외하고 발동. 묘지에서 「아츠」 카드를 {n}장 패에 넣는다.',
   zones=GRAVE,
   cost=[send_grave(scope=S('own', 'hand', pred='same_name'), n=1), banish(ref='SELF')],
   do=[to_hand(scope=S('own', 'grave', group='아츠', pickable=True, not_self=True), n='$n', harm=False)])

# 시엘 아츠 — 월영침식
fx('SLNA-010', '1', '[신속] 자신 필드의 「시엘」 몬스터 {n}장을 턴 종료 시까지 제외하고, 상대 필드의 카드를 {m}장을 대상으로 하고 발동. 그 카드를 덱으로 되돌린다.',
   cost=[banish(scope=CIEL_MON, n='$n', until='turn'), target('T', OPP_FIELD, n='$m')], do=[to_deck(ref='T')])
follow('SLNA-010', '2', f'1번 효과 처리 시에 자신 필드에 「시아」 몬스터가 존재할 경우, 상대 필드의 카드 {{n}}장을 턴 종료 시까지 무효로 한다. {FOLLOW}',
       [HAS_SIA], [negate_card(scope=S('opp', ('field', 'skill'), faceup=True, pred='not_negated'), n='$n')])
# 월영잠행 — 처리 문장은 「상대 필드의 카드 1장」이지만 발동 시 고른 대상을 덱으로(예전 구현과 같음)
fx('SLNA-011', '1', '[신속] 자신 필드의 「시엘」 몬스터 {n}장을 상대 몬스터 존으로 이동시키고, 상대 필드의 카드 {m}장을 대상으로 하고 발동. '
   '상대 필드의 카드 {k}장을 덱으로 되돌린다. (이 효과로 컨트롤이 변경된 카드는 턴 종료 시에 자신 필드로 돌아온다.)',
   cost=[control(scope=CIEL_MON, n='$n', to='opp', back='turn', harm=False), target('T', OPP_FIELD, n='$m')], do=[to_deck(ref='T')])
follow('SLNA-011', '2', '1번 효과 처리 시에 자신 필드에 「시아」 몬스터가 존재할 경우, 상대 몬스터 존의 「시엘」을 자신 몬스터 존으로 이동시키고 '
       f'필드의 몬스터를 {{n}}장 파괴한다. {FOLLOW}',
       [HAS_SIA], [control(scope=S('opp', 'mzone', 'monster', group='시엘', pred='own_owned'), n=1, to='self', harm=False),
                   destroy(scope=S('both', 'field', 'monster'), n='$n')])
fx('SLNA-012', '1', '[신속] 자신 필드의 「시엘」 몬스터 {n}장을 묘지로 보내고 발동. 「솔루나」 이외의 자신 묘지의 카드를 {m}장 패에 넣는다.',
   cost=[send_grave(scope=CIEL_MON, n='$n')],
   do=[to_hand(scope=S('own', 'grave', not_group='솔루나', pickable=True), n='$m', harm=False)])
follow('SLNA-012', '2', f'1번 효과 처리 시에 자신 필드에 「시아」 몬스터가 존재할 경우, 상대 필드의 마법 카드 {{n}}장을 파괴한다. {FOLLOW}',
       [HAS_SIA], [destroy(scope=S('opp', 'field', 'spell'), n='$n')])
fx('SLNA-013', '1', '[전투] 필드의 카드 {n}장을 덱으로 되돌린다.',
   when=[when('battle_win', any_own=True)], do=[to_deck(scope=BOTH_FIELD, n='$n')])
follow('SLNA-013', '2', f'1번 효과 처리 시에 자신 필드에 「시아」 몬스터가 존재할 경우, 상급 덱에서 「시엘」 몬스터를 {{n}}장 특수소환한다. {FOLLOW}',
       [HAS_SIA], [special(scope=S('own', 'upper', 'monster', group='시엘'), n='$n')])
# 월영암수 — 상대가 되돌릴 패를 고른다
fx('SLNA-014', '1', '[신속] 자신 필드의 「시엘」 몬스터 {n}장을 상대의 패에 넣고 발동. 상대는 패를 {m}장 덱으로 되돌린다.',
   cost=[B('move', dest='opp_hand', scope=CIEL_MON, n='$n')], do=[to_deck(scope=S('opp', 'hand'), n='$m', chooser='opp', shuffle='opp')])
follow('SLNA-014', '2', f'1번 효과 처리 시에 자신 필드에 「시아」 몬스터가 존재할 경우, 상대 묘지의 카드 {{n}}장을 제외한다. {FOLLOW}',
       [HAS_SIA], [banish(scope=S('opp', 'grave'), n='$n')])

# 시아 아츠
fx('SLNA-015', '1', '[신속] 자신 필드의 「시아」 카드를 덱으로 되돌리고, 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 턴 종료 시까지 무효로 하고 자신의 HP를 {amt} 회복한다.',
   cost=[to_deck(scope=S('own', 'field', group='시아', faceup=True, not_self=True), n=1),
         target('T', S('both', ('field', 'skill'), faceup=True, not_self=True, pred='not_negated'), n='$n')],
   do=[negate_card(ref='T'), heal('$amt')])
follow('SLNA-015', '2', f'1번 효과 처리 시에 자신 필드에 「시엘」 몬스터가 존재할 경우, 자신 묘지에서 카드 {{n}}장을 패에 넣는다. {FOLLOW}',
       [HAS_CIEL], [to_hand(scope=S('own', 'grave', pickable=True, not_self=True), n='$n', harm=False)])
# 성광난무 — 패의 「시아」 카드를 원하는 만큼 보여 줌: AI는 전부(대상 수 = 보여 준 수, 상대 카드가 모자라면 있는 만큼)
fx('SLNA-016', '1', '[신속] 자신 필드의 「시아」 몬스터를 패로 되돌리고, 패의 「시아」 카드를 원하는 만큼 보여주고 그 개수 만큼 상대 필드의 카드를 대상으로 하고 발동. 그 카드를 파괴한다.',
   cost=[to_hand(scope=SIA_MON, n=1), target('T', OPP_FIELD, n_count=(S('own', 'hand', group='시아'), 99))],
   do=[destroy(ref='T')])
follow('SLNA-016', '2', f'1번 효과 처리 시에 자신 필드에 「시엘」 몬스터가 존재할 경우, 상대 필드의 몬스터 {{n}}장을 덱으로 되돌린다. {FOLLOW}',
       [HAS_CIEL], [to_deck(scope=S('opp', 'field', 'monster'), n='$n')])
fx('SLNA-017', '1', '자신의 「시아」 몬스터를 덱으로 되돌리고 발동. 덱에서 「시아」 또는 「시엘」 카드를 {n}장 패에 넣는다.',
   cost=[to_deck(scope=SIA_MON, n=1)], do=[search(S('own', 'deck', group=SIA_OR_CIEL), '$n')])
follow('SLNA-017', '2', f'1번 효과 처리 시에 자신 필드에 「시엘」 몬스터가 존재할 경우, 상대 필드의 카드 {{n}}장을 덱으로 되돌린다. {FOLLOW}',
       [HAS_CIEL], [to_deck(scope=OPP_FIELD, n='$n')])
fx('SLNA-018', '1', '[트리거] 자신 필드의 「시아」 몬스터가 상대에 의해 필드를 벗어났을 때 발동. 상대 필드의 카드 {n}장을 파괴한다.',
   when=[when('left_field', ctrl='own', filter=S(kind='monster', group='시아'), by='opp')], do=[destroy(scope=OPP_FIELD, n='$n')])
follow('SLNA-018', '2', f'1번 효과 처리 시에 자신 필드에 「시엘」 몬스터가 존재할 경우, 상급 덱에서 「시아」 몬스터를 {{n}}장 특수소환한다. {FOLLOW}',
       [HAS_CIEL], [special(scope=S('own', 'upper', 'monster', group='시아'), n='$n')])
# 성광소각 — 코스트의 「필드」는 자신 필드(재정 Q41 · PDF Q8)
fx('SLNA-019', '1', '[신속] 필드의 「시아」 몬스터를 {n}장 묘지로 보내고 발동. 상대 묘지의 카드를 {m}장 제외한다.',
   cost=[send_grave(scope=SIA_MON, n='$n')], do=[banish(scope=S('opp', 'grave'), n='$m')])
follow('SLNA-019', '2', f'1번 효과 처리 시에 자신 필드에 「시엘」 몬스터가 존재할 경우, 상대 필드의 마법 카드를 {{n}}장 덱으로 되돌린다. {FOLLOW}',
       [HAS_CIEL], [to_deck(scope=S('opp', 'field', 'spell'), n='$n')])

# 이클립스
fx('SLNA-020', '1', '[트리거] 자신 필드의 「시아」·「시엘」 몬스터가 동시에 파괴되었을 때 발동. 필드의 카드를 전부 파괴한다. 다음 자신 턴 종료 시까지, 자신은 상대에게 대미지를 줄 수 없다.',
   when=[when('both_destroyed', groups=SIA_OR_CIEL)],
   do=[destroy(scope=S('both', 'field', not_self=True), all=True), no_damage(until='next_own')])
fx('SLNA-021', '1', '[트리거] 상대의 효과가 발동했을 때, 자신 필드에 「시아」·「시엘」 몬스터가 1장씩 존재하면 발동. 그 효과를 무효로 하고 파괴한다. '
   '(이 카드의 발동에 대하여, 상대는 효과를 발동할 수 없다.)',
   when=[when('activated', who='opp')], cond=[HAS_SIA, HAS_CIEL], do=[negate_link(destroy=True)])

# 필드 — 일광 · 월영
fx('SLNA-022', '1', '[트리거] 자신의 「시아」 효과의 발동에 이어 상대가 효과를 발동했을 때 발동. 그 효과를 무효로 하고 파괴한다.',
   when=[when('activated', who='opp', after_own_group='시아')], do=[negate_link(destroy=True)])
fx('SLNA-022', '2', '[신속] 필드의 이 카드를 덱으로 되돌린다. 덱에서 「시엘」 필드 카드를 {n}장 발동한다.',
   do=[to_deck(ref='SELF', harm=False), place(S('own', 'deck', 'field_spell', group='시엘'))])
fx('SLNA-023', '1', '[트리거] 자신의 「시엘」 효과의 발동에 이어 상대가 효과를 발동했을 때 발동. 자신 묘지에서 「아츠」 카드를 {n}장 패에 넣는다.',
   when=[when('activated', who='opp', after_own_group='시엘')],
   do=[to_hand(scope=S('own', 'grave', group='아츠', pickable=True), n='$n', harm=False)])
fx('SLNA-023', '2', '[신속] 필드의 이 카드를 덱으로 되돌린다. 덱에서 「시아」 필드 카드를 {n}장 발동한다.',
   do=[to_deck(ref='SELF', harm=False), place(S('own', 'deck', 'field_spell', group='시아'))])

# 솔루나 아츠 (스킬) — 1번은 주인에게 불리한 [지속](고르지 않고 늘 적용, 사용자 답변 2026-10-22)
fx('SLNA-024', '1', '[지속] 자신 필드에 「시아」·「시엘」 몬스터는 각각 1장밖에 존재할 수 없다.', forced=True, cont=[field_limit('시아', '시엘')])
fx('SLNA-024', '2', '[트리거] 턴 종료 시에 자신 필드에 「시아」·「시엘」 몬스터가 모두 존재하면 덱에서 「아츠」 카드를 {n}장 필드에 세트한다.',
   when=[when('phase', phase='end')], cond=[HAS_SIA, HAS_CIEL], do=[place(S('own', 'deck', 'spell', group='아츠'), set=True)])
# 3번 「묘지의」 — 자신 묘지(드로우하는 쪽, 예전 구현과 같은 해석)
fx('SLNA-024', '3', '묘지의 「아츠」 카드를 {n}장을 대상으로 하고 발동. 그 카드를 덱으로 되돌리고 카드를 {m}장 드로우한다.',
   cost=[target('T', S('own', 'grave', group='아츠'), n='$n', harm=False)], do=[to_deck(ref='T', shuffle=True), draw('$m')])
