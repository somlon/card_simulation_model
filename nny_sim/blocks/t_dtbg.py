"""조립표 — 데이터버그 23종 (DTBG). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
몬스터의 소환 그 자체를 트리거로 삼는 전개 테마 — 「필드에 「데이터버그」 몬스터가 소환되었을 때 패에서 특수소환」(손패 트리거)이 연쇄한다.
효과 종류 표기가 없는 효과는 기동 효과(ASSUME, 예전과 같음). 「덱에서」 = 메인 · 상급, 「메인 덱에서」 · 「상급 덱에서」는 그 덱만.
코스트 문장의 「필드」는 「서로」 · 「상대」가 적혀 있을 때만 상대 필드를 포함한다(사용자 답변 2026-10-22 Q41) — 로딩 2번 · 습격은 자신 필드.
더 바이러스 · 더 딜리트 1번 [제약]의 패에서의 특수소환은 소환 절차(발동이 아님 — Effect.procedure, 대응 · 무효 없음)."""
from blocks.dsl import *   # noqa: F401,F403

DB = '데이터버그'
OPP_FIELD = S('opp', 'field')
BOTH_FIELD = S('both', 'field')
DB_MON = S(kind='monster', group=DB)
OWN_DB_MON = S('own', 'mzone', 'monster', group=DB)
REL2 = release(scope=S('own', 'mzone', 'monster', group=DB, pred='releasable'), n='$n')
HAND_SS = '[트리거] 필드에 「데이터버그」 몬스터가 소환되었을 때 발동. 패에서 이 카드를 특수소환한다.'
SELF_HAND = special(ref='SELF', src_zone=('hand',))


def hand_ss(code, key):
    fx(code, key, HAND_SS, zones=HAND, when=[when('summoned', filter=DB_MON)], do=[SELF_HAND])


def own_hand_ss(code, key, tmpl):
    fx(code, key, tmpl, zones=HAND, when=[when('summoned', who='own', filter=DB_MON)], do=[SELF_HAND])


def back_fetch(code, key, tmpl, scope):
    fx(code, key, tmpl, zones=HAND, when=[when('summoned', filter=DB_MON)],
       do=[to_deck(ref='SELF', ref_scope=S('own', 'hand'), shuffle=True, harm=False), search(scope, '$n')])


def nomi(code):
    fx(code, '1', '[제약] 이 카드는 다른 카드의 효과로 소환할 수 없다. 자신 필드의 몬스터를 {n}장 묘지로 보내야만 패에서 특수소환할 수 있다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
       kind='ignition', zones=HAND, procedure=True, no_resp=True, unnegatable=True,
       card=[card_flag('ss_self_only'), card_flag('no_normal')],
       cost=[send_grave(scope=S('own', 'mzone', 'monster'), n='$n')], do=[special(ref='SELF', src_zone=('hand',))])


# ── 메인 덱 몬스터 ──
fx('DTBG-001', '1', '이 카드를 릴리스하고 발동. 덱에서 「데이터버그」 카드를 {n}장 패에 넣는다.', cost=[release(ref='SELF')], do=[search(S('own', 'deck', group=DB), '$n')])
hand_ss('DTBG-001', '2')
# 플라이 1번 「패에 넣어졌을 때」 — 덱 · 묘지에서 패에 넣기 · 드로우(cards.hand_add) · 필드에서 패로
fx('DTBG-002', '1', '[트리거] 이 카드가 패에 넣어졌을 때 발동. 이 카드를 특수소환하고, 덱에서 「데이터버그」 마법 카드 {n}장을 패에 넣는다.',
   zones=HAND, when=[when_any(when('hand_added', self=True, who='own'), when('left_field', self=True, dest='hand'))],
   do=[SELF_HAND, search(S('own', 'deck', 'spell', group=DB), '$n')])
hand_ss('DTBG-002', '2')
fx('DTBG-003', '1', '[소환] 메인 덱에서 「데이터버그」 몬스터 {n}장을 특수소환한다.', do=[special(scope=S('own', 'main', 'monster', group=DB), n='$n')])
fx('DTBG-003', '2', '[트리거] 「데이터버그」 몬스터가 소환되었을 때 발동. 덱에서 「데이터버그」 몬스터를 패에 넣는다.',
   when=[when('summoned', filter=DB_MON)], do=[search(S('own', 'deck', 'monster', group=DB), 1)])
hand_ss('DTBG-003', '3')
fx('DTBG-004', '1', '이 카드를 릴리스하고 발동. 상급 덱에서 「데이터버그」 카드를 {n}장 패에 넣는다.', cost=[release(ref='SELF')], do=[search(S('own', 'upper', group=DB), '$n')])
back_fetch('DTBG-004', '2', '[트리거] 「데이터버그」 몬스터가 필드에 소환되었을 때 발동. 패의 이 카드를 덱으로 되돌리고, 상급 덱에서 「데이터버그」 카드 {n}장을 패에 넣는다.',
           S('own', 'upper', group=DB))
fx('DTBG-005', '1', '자신 필드의 「데이터버그」 몬스터를 {n}장 릴리스하고 발동. 덱에서 「데이터버그」 몬스터 {m}장을 패에 넣는다. (이 효과는 계속해서 사용할 수 있다.)',
   cost=[REL2], do=[search(S('own', 'deck', 'monster', group=DB), '$m')])
back_fetch('DTBG-005', '2', '[트리거] 「데이터버그」 몬스터가 필드에 소환되었을 때 발동. 패의 이 카드를 덱으로 되돌리고, 덱에서 「데이터버그」 몬스터 {n}장을 패에 넣는다.',
           S('own', 'deck', 'monster', group=DB))

# ── 상급 덱 몬스터 ──
fx('DTBG-006', '1', '이 카드를 패에서 버리고 발동. 상급 덱에서 「데이터버그」 몬스터 {n}장을 패에 넣는다.',
   zones=HAND, cost=[send_grave(ref='SELF', ref_scope=S('own', 'hand'))], do=[search(S('own', 'upper', 'monster', group=DB), '$n')])
fx('DTBG-006', '2', '[소환] 덱에서 「데이터버그 앤트」를 가능한 만큼 특수소환한다.', do=[special(scope=S('own', 'deck', 'monster', name='데이터버그 앤트'), all=True)])
hand_ss('DTBG-006', '3')
fx('DTBG-007', '1', '[전투] 상대 필드의 카드 {n}장을 파괴하고 {amt} 대미지를 준다. 자신은 이어서 공격할 수 있다.',
   do=[destroy(scope=OPP_FIELD, n='$n'), damage('$amt'), extra_attack(1)])
hand_ss('DTBG-007', '2')
fx('DTBG-008', '1', '[신속] 패에서 이 카드를 버리고, 필드의 「데이터버그」 몬스터 {n}장을 대상으로 하고 발동. 그 몬스터를 묘지로 보내고, 메인 덱에서 「데이터버그」 몬스터를 {m}장 특수소환한다.',
   zones=HAND, cost=[send_grave(ref='SELF', ref_scope=S('own', 'hand')), target('T', S('both', 'field', 'monster', group=DB, faceup=True), n='$n')],
   do=[send_grave(ref='T'), special(scope=S('own', 'main', 'monster', group=DB), n='$m')])
fx('DTBG-008', '2', '[소환] 묘지에서 「데이터버그」 몬스터 {n}장을 특수소환한다.', do=[special(scope=S('own', 'grave', 'monster', group=DB), n='$n')])
hand_ss('DTBG-008', '3')
fx('DTBG-009', '1', '[소환] 덱에서 「데이터버그」 몬스터 {n}장을 패에 넣는다.', do=[search(S('own', 'deck', 'monster', group=DB), '$n')])
fx('DTBG-009', '2', '자신 필드의 「데이터버그」 몬스터를 {n}장 릴리스하고 발동. 덱에서 「데이터버그」 마법 {m}장을 패에 넣는다.',
   cost=[REL2], do=[search(S('own', 'deck', 'spell', group=DB), '$m')])
own_hand_ss('DTBG-009', '3', '[트리거] 자신 필드에 「데이터버그」 몬스터가 소환되었을 때 발동. 이 카드를 패에서 특수소환한다.')
fx('DTBG-010', '1', '자신 필드의 「데이터버그」 몬스터를 {n}장 릴리스하고 발동. 묘지에서 「데이터버그」 몬스터를 {m}장 특수소환한다.',
   cost=[REL2], do=[special(scope=S('own', 'grave', 'monster', group=DB), n='$m')])
fx('DTBG-010', '2', '[지속] 자신 필드의 몬스터의 공격력은 자신 필드의 「데이터버그」 카드의 수 × {amt} 올라간다.',
   cont=[stat_mod(S('own', 'field', 'monster'), '$amt', per=(S('own', 'field', group=DB, faceup=True),))])
own_hand_ss('DTBG-010', '3', '[트리거] 자신 필드에 「데이터버그」 몬스터가 소환되었을 경우에 발동. 이 카드를 패에서 특수소환한다.')
fx('DTBG-011', '1', '[트리거] 상대가 효과를 발동했을 때 발동. 그 효과를 무효로 한다.', when=[when('activated', who='opp')], do=[negate_link()])
# 버터플라이 2번 — 「자신」 = 이 카드(사용자 답변 2026-10-25), 「데이터버그」 마법은 앞면만(Q43)
fx('DTBG-011', '2', '[지속] 자신 필드에 「데이터버그」 마법 카드가 존재하는 한, 자신은 상대의 효과를 받지 않는다.',
   cont=[card_flag('immune_opp', **{'while': cnt(S('own', 'szone', 'spell', group=DB, faceup=True))})])
hand_ss('DTBG-011', '3')
fx('DTBG-012', '1', '[신속] 상대 필드의 카드 {n}장을 파괴한다.', do=[destroy(scope=OPP_FIELD, n='$n')])
fx('DTBG-012', '2', '[신속] 자신 필드에서 「데이터버그」 카드 {n}장을 묘지로 보낸다. 필드의 카드 {m}장을 파괴한다.',
   do=[send_grave(scope=S('own', 'field', group=DB, faceup=True), n='$n'), destroy(scope=BOTH_FIELD, n='$m')])
hand_ss('DTBG-012', '3')
nomi('DTBG-013')
fx('DTBG-013', '2', '[트리거] 상대가 몬스터를 소환했을 때 발동. 그 소환을 무효로 하고 파괴한다.',
   summon_negate=True, when=[when('summoned', who='opp')], do=[B('negate_summon', destroy=True)])
fx('DTBG-013', '3', '[트리거] 상대가 효과를 발동했을 때 발동. 그 효과를 무효로 하고 파괴한다.', when=[when('activated', who='opp')], do=[negate_link(destroy=True)])
nomi('DTBG-014')
fx('DTBG-014', '2', '[트리거] 필드의 몬스터가 파괴되었을 때 발동. 필드의 카드를 {n}장 파괴한다.',
   when=[when('destroyed', filter=S(kind='monster'))], do=[destroy(scope=S('both', 'field', not_self=True), n='$n')])
fx('DTBG-014', '3', '[지속] 상대는 효과로 카드를 덱에서 패에 넣을 수 없다. (이 효과는 1턴에 1번 제약을 받지 않는다.)', cont=[forbid('no_deck_to_hand', who='opp')])
fx('DTBG-015', '1', '[소환] 묘지에서 「데이터버그」 몬스터 {n}장을 특수소환한다.', do=[special(scope=S('own', 'grave', 'monster', group=DB), n='$n')])
fx('DTBG-015', '2', '[트리거] 상대가 카드의 효과를 발동했을 때 발동. 그 발동을 무효로 한다.', when=[when('activated', who='opp')], do=[negate_link(act_grave=True)])
hand_ss('DTBG-015', '3')

# ── 마법 ──
# 로딩 1번(「발동 선언을 필요로 하지 않는다」) — 카드의 발동에 딸린 처리(1턴 1번), 놓기만 하는 발동도 있음
# 카드의 발동(번호 0 — 1턴 횟수 없음)이 1번을 처리한다(1턴 1번, 이미 했으면 놓기만)
fx('DTBG-016', '1', '이 카드를 발동했을 때, 상급 덱에서 「데이터버그」 몬스터를 {n}장 패에 넣는다. (이 효과는 발동 선언을 필요로 하지 않는다.)',
   num=0, spell_act=True, zones=HAND_FIELD, opt=None,
   do=[B('once', num=1, steps=(search(S('own', 'upper', 'monster', group=DB), '$n', soft=True),))])
fx('DTBG-016', '2', '필드에서 「데이터버그」 몬스터를 {n}장 릴리스하고 발동. 덱에서 「데이터버그」 몬스터를 {m}장 패에 넣는다.',
   cost=[REL2], do=[search(S('own', 'deck', 'monster', group=DB), '$m')])
fx('DTBG-017', '1', '자신 필드의 「데이터버그」 몬스터 {n}장을 대상으로 하고 발동. 그 카드를 묘지로 보내고, 덱에서 동일한 이름의 카드를 패에 넣는다. 묘지로 보낸 카드를 특수소환한다.',
   cost=[target('T', S('own', 'field', 'monster', group=DB, faceup=True), n='$n', harm=False)],
   do=[send_grave(ref='T'), search(S('own', 'deck'), 1, name_ref='T'), special(ref='T', ref_scope=S('own', 'grave'))])
fx('DTBG-018', '1', '메인 덱에서 「데이터버그」 몬스터 {n}장을 특수소환한다. 그 후, 그 카드를 묘지로 보낸다.',
   do=[special(scope=S('own', 'main', 'monster', group=DB), n='$n', pos='def', brief=True, **{'as': 'X'}), send_grave(ref='X', ref_scope=S('own', 'field'))])
fx('DTBG-019', '1', '자신의 패를 {n}장 버린다. 묘지에서 「데이터버그」 몬스터를 {m}장 특수소환한다.',
   do=[discard('$n', feeds=S(kind='monster', group=DB)), special(scope=S('own', 'grave', 'monster', group=DB), n='$m')])
fx('DTBG-020', '1', '[신속] 필드의 「데이터버그」 몬스터를 {n}장 묘지로 보내고 발동. 상대 필드의 카드 {m}장을 고르고 파괴한다. 그 후, 묘지에서 「데이터버그」 몬스터를 {k}장 특수소환한다.',
   cost=[send_grave(scope=OWN_DB_MON, n='$n')], do=[destroy(scope=OPP_FIELD, n='$m'), special(scope=S('own', 'grave', 'monster', group=DB), n='$k', upto=True)])
fx('DTBG-021', '1', '[트리거] 자신의 「데이터버그」 몬스터가 상대의 효과에 의해 필드를 벗어났을 때 발동. 필드의 카드를 전부 파괴한다. 그 후, 묘지에서 「데이터버그」 몬스터 {n}장을 특수소환한다.',
   when=[when('left_field', ctrl='own', filter=DB_MON, by='opp', cause='effect')],
   do=[destroy(scope=S('both', 'field', not_self=True), all=True, zero_ok=True), special(scope=S('own', 'grave', 'monster', group=DB), n='$n')])
fx('DTBG-022', '1', '자신 필드에 「데이터버그」 몬스터가 존재할 경우, 덱에서 「데이터버그」 몬스터를 {n}장 특수소환한다. 이 효과로 특수소환한 몬스터는 이 턴에 효과를 발동할 수 없다.',
   cond=[cnt(S('own', 'mzone', 'monster', group=DB, faceup=True))],
   do=[special(scope=S('own', 'deck', 'monster', group=DB), n='$n', **{'as': 'X'}), status('no_act', ref='X', label='이 턴에 효과를 발동할 수 없음')])

# ── 스킬 ──
fx('DTBG-023', '1', '자신 필드에 「데이터버그」 몬스터가 {n}장 존재할 경우 발동할 수 있다. 이 턴에, 자신은 한 번 더 일반소환할 수 있다.',
   cond=[cnt(OWN_DB_MON, '>=', '$n')],
   card=[B('extra_normal_turn', flag='xns_turn'), B('shared_hint', to=OWN_DB_MON, n='$n')],
   do=[B('mark_turn', key='xns_turn', what='extra_ns', label='이 턴 일반소환 1회 추가')])
