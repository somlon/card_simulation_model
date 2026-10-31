"""조립표 — 포커짐승들 20종 (PKBS). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
몬스터의 레벨을 숫자로, 속성(스페이드 · 다이아 · 하트 · 클로버)을 문양으로 족보를 완성하는 테마. 족보 코스트(combo)의 재료 고르기 ·
레벨/속성 부여 계획은 조합 탐색 공용 함수(cards8 — 재료 풀 · 족보 찾기 · 부여 계획)를 쓰고, 재료 매수 · 상대 카드 사용 여부는 효과 문장에서 읽는다.
「상급 덱에서 「X」를 소환한다」 = 특수소환(ASSUME, 예전과 같음). 올인 2번 [지속]의 부여 효과(「-」 항목)는 포커짐승들 카드마다 붙고 부여가 적용될 때만 쓴다
(build.cont_granted_effect — 번호 21 · 22, 카드마다 1턴 1번)."""
from blocks.dsl import *   # noqa: F401,F403

PK = '포커짐승들'
OPP_FIELD = S('opp', 'field')
NOT_ONCE = '(이 효과는 1턴에 1번 제약을 받지 않는다.)'
BATTLE_IND = f'[지속] 이 카드는 전투로는 파괴되지 않는다. {NOT_ONCE}'
ALL_SUITS = f'[지속] 이 카드의 속성은 스페이드·다이아·하트·클로버 모두로 취급한다. {NOT_ONCE}'
RAT_REVIVE = '[트리거] 이 카드가 묘지에 존재하는 상태에서 자신 필드의 「포커짐승들」 몬스터가 파괴되었을 경우 발동. 이 카드를 묘지에서 특수소환한다.'
REL_DRAW = '[트리거] 이 카드가 릴리스되었을 때 발동. 이 카드를 덱으로 되돌리고 {n}장 드로우한다.'


def upper(name_has): return special(scope=S('own', 'upper', 'monster', name_has=name_has), n=1)
def reveal(code, key, group, own='자신 '):
    fx(code, key, f'이 카드를 패에서 상대에게 보여주고 발동. 이 카드를 덱으로 되돌리고 {own}덱에서 「{group}」 몬스터 {{n}}장을 패에 넣는다.',
       zones=HAND, do=[to_deck(ref='SELF', ref_scope=S('own', 'hand'), shuffle=True, harm=False), search(S('own', 'deck', 'monster', group=group), '$n')])


def rel_draw(code, key):
    fx(code, key, REL_DRAW, zones=GRAVE, when=[when('to_grave', released=True)],
       do=[to_deck(ref='SELF', ref_scope=S('own', 'grave'), shuffle=True, harm=False), draw('$n')])


# ── 메인 덱 몬스터 ──
fx('PKBS-001', '1', BATTLE_IND, cont=[self_rule('indestructible', battle=True)])
fx('PKBS-001', '2', '[신속] 이 카드를 포함하는 패와 필드의 연속되는 레벨의 몬스터 {n}장을 릴리스하고 발동. 상급 덱에서 「스트레이트 토끼」를 소환한다.',
   zones=HAND_FIELD, pk_kind='straight', cost=[combo('straight')], do=[upper('스트레이트 토끼')])
fx('PKBS-001-1', '1', '[유언] 자신 묘지의 카드 {n}장을 덱으로 되돌린다. 그 후 {m}장을 드로우한다.',
   do=[to_deck(scope=S('own', 'grave'), n='$n', harm=False, shuffle=True), draw('$m')])
fx('PKBS-001-1', '2', f'[지속] 이 카드는 공격 선언을 할 수 없다. {NOT_ONCE}', cont=[card_flag('no_attack', live=True)])
fx('PKBS-002', '1', f'[지속] 자신의 「포커짐승들」 몬스터의 공격력은 같은 속성의 카드 1장당 {{amt}} 올린다. {NOT_ONCE}',
   cont=[stat_per('$amt', ('same', 'attr'), to=S('own', 'field', 'monster', group=PK))])
fx('PKBS-002', '2', '[신속] 이 카드를 포함하는 자신의 패와 서로의 필드의 같은 속성의 몬스터 {n}장을 릴리스하고 발동. 상급 덱에서 「플러쉬 늑대」를 소환한다.',
   zones=HAND_FIELD, pk_kind='flush', cost=[combo('flush')], do=[upper('플러쉬 늑대')])
fx('PKBS-002-1', '1', '[유언] 필드의 몬스터 {n}장을 대상으로 하고 발동. 그 몬스터의 효과를 턴 종료 시까지 무효로 한다.',
   cost=[target('T', S('both', 'field', 'monster', faceup=True), n='$n', purpose='negate')], do=[negate_card(ref='T')])
fx('PKBS-003', '1', '자신은 「포커짐승들」 몬스터를 추가로 일반소환한다.', no_effect=True, card=[B('extra_normal', n=1, to=S(kind='monster', group=PK))])
fx('PKBS-003', '2', '[신속] 이 카드를 포함하는 서로의 필드와 묘지에서 같은 레벨의 몬스터 {a}장, 같은 레벨의 몬스터 {b}장을 덱으로 되돌리고 발동. 상급 덱에서 「풀 하우스 강아지」를 소환한다. '
   '(5장이 전부 같은 레벨일 수는 없으며 이 효과는 패에서도 발동할 수 있다.)',
   pk_kind='full', cost=[combo('full', hand_ok=True)], do=[upper('풀 하우스 강아지')])
fx('PKBS-003-1', '1', '[유언] 덱에서 「포커짐승들」 마법 카드 {n}장을 패에 넣는다.', do=[search(S('own', 'deck', 'spell', group=PK), '$n')])
fx('PKBS-003-1', '2', f'[지속] 자신이 「포커짐승들」 효과를 발동할 때마다 상대에게 {{amt}} 대미지를 준다. {NOT_ONCE}',
   cont=[B('whenever', when=when('activated_ev', who='own', group=PK), steps=(damage('$amt'),))])
fx('PKBS-004', '1', f'[지속] 자신의 「포커짐승들」 몬스터의 수비력은, 필드에 존재하는 그 몬스터와 같은 레벨의 몬스터 1장당 {{amt}} 올린다. {NOT_ONCE}',
   cont=[stat_per('$amt', ('same', 'level'), to=S('own', 'field', 'monster', group=PK), stat='def')])
fx('PKBS-004', '2', '[신속] 이 카드를 포함하는 자신과 상대의 필드, 묘지에서 같은 레벨의 몬스터 {n}장을 덱으로 되돌리고 발동. 상급 덱에서 「포카드 고양이」를 소환한다. (이 효과는 패에서도 발동할 수 있다.)',
   pk_kind='four', cost=[combo('four', hand_ok=True)], do=[upper('포카드 고양이')])
fx('PKBS-004-1', '1', '[유언] 덱에서 「포커짐승들」 몬스터 {n}장을 패에 넣는다.', do=[search(S('own', 'deck', 'monster', group=PK), '$n')])
GY_PK = (S('own', 'grave', 'monster', group=PK),)
fx('PKBS-004-1', '2', f'[지속] 상대 몬스터의 공격력과 수비력은 자신 묘지에 존재하는 「포커짐승들」 몬스터 1장당 {{amt}}씩 내린다. {NOT_ONCE}',
   cont=[stat_mod(S('opp', 'field', 'monster'), '-$amt', per=GY_PK), stat_mod(S('opp', 'field', 'monster'), '-$amt', per=GY_PK, stat='def')])

# ── 상급 덱 몬스터 ──
for code in ('PKBS-005', 'PKBS-006'):
    fx(code, '1', ALL_SUITS, cont=[card_flag('all_suits')])
    fx(code, '3', RAT_REVIVE, zones=GRAVE, when=[when('destroyed', who='own', zone=('m', 'shared'), filter=S(kind='monster', group=PK))],
       do=[special(ref='SELF', src_zone=('grave',))])
fx('PKBS-005', '2', '[소환] 자신 묘지에서 카드를 {n}장까지 덱으로 되돌리고 {m}장 드로우한다.',
   do=[to_deck(scope=S('own', 'grave'), n='$n', upto=True, harm=False, shuffle=True), draw('$m')])
fx('PKBS-006', '2', '[소환] 자신 묘지에서 {lv}레벨 이하의 「포커짐승들」 몬스터를 {n}장까지 자신 필드에 특수소환한다.',
   do=[special(scope=S('own', 'grave', 'monster', group=PK, level=('<=', '$lv')), n='$n', upto=True)])
fx('PKBS-007', '1', BATTLE_IND, cont=[self_rule('indestructible', battle=True)])
fx('PKBS-007', '2', '[소환] 이 카드가 소환되었을 경우 발동. 자신은 {n}장을 드로우한다.', do=[draw('$n')])
fx('PKBS-007', '3', '[트리거] 상대가 효과를 발동했을 경우 발동. 그 효과를 무효로 한다.', when=[when('activated', who='opp')], do=[negate_link()])
fx('PKBS-008', '1', f'[지속] 이 카드가 필드에 존재할 경우, 이 카드의 공격력은 필드에 존재하는 다이아 속성의 카드 1장당 {{amt}} 올린다. {NOT_ONCE}',
   cont=[stat_per('$amt', ('attr', '다이아'), self_only=True)])
fx('PKBS-008', '2', '[소환] 자신 묘지에서 「포커짐승들」 몬스터를 {n}장까지 대상으로 하고 발동한다. 그 카드를 특수소환한다.',
   cost=[target('T', S('own', 'grave', 'monster', group=PK), n='$n', upto=True, harm=False)], do=[special(ref='T', ref_scope=S('own', 'grave'))])
reveal('PKBS-008', '3', '늑대')
fx('PKBS-009', '1', '[지속] 이 카드가 필드에 존재할 경우, 자신은 1턴에 {n}번까지 「포커짐승들」 몬스터를 추가로 일반소환할 수 있다.',
   cont=[B('extra_normal', n='$n', to=S(kind='monster', group=PK))])
reveal('PKBS-009', '2', '강아지')
fx('PKBS-009', '3', '[소환] 상대 플레이어에게 {amt}의 대미지를 준다.', do=[damage('$amt')])
fx('PKBS-010', '1', '[소환] 자신 묘지의 카드를 {n}장까지 덱으로 되돌리고 상대 필드의 카드를 그 수만큼 고르고 파괴한다.',
   cond=[cnt(OPP_FIELD)],
   do=[to_deck(scope=S('own', 'grave'), n='$n', upto=True, harm=False, shuffle=True, count_as='N', cap_by=(OPP_FIELD,)),
       destroy(scope=OPP_FIELD, n=('ref', 'N'), upto=True)])
reveal('PKBS-010', '2', '고양이', own='')

# ── 마법 · 필드 ──
# 표시목 1번(키워드 없음) — 카드의 발동(예전 구현과 같음). 놓기만 하는 발동은 두지 않는다
fx('PKBS-011', '1', '필드의 카드 {n}장을 대상으로 하고 발동. 그 카드에 원하는 레벨과 원하는 속성을 부여한다. (마법 카드와 필드 카드는 몬스터로 취급하여 부여한다.)',
   spell_act=True, zones=HAND_FIELD, no_place=True,
   cost=[target('T', S('both', 'field', faceup=True), n='$n', picker='mark', harm=False)], do=[B('grant_la', ref='T')])
rel_draw('PKBS-011', '2')
fx('PKBS-012', '1', '덱에서 「포커짐승들」 몬스터 {n}장을 패에 넣는다.', do=[search(S('own', 'deck', 'monster', group=PK), '$n')])
FROM_DG = ('main', 'upper', 'grave')
fx('PKBS-013', '1', '[트리거] 상대가 덱 또는 묘지에서 카드를 패에 넣었을 경우, 또는 상대가 덱 또는 묘지에서 몬스터를 필드에 특수소환했을 경우에 발동. 그 카드를 제외한다.',
   when=[when_any(when('hand_added', who='opp', src=FROM_DG), when('summoned', who='opp', how='special', prev=FROM_DG))],
   do=[banish(ref='EV', ref_scope=S('opp', ('hand', 'field')))])
fx('PKBS-014', '1', '[신속] 레벨과 속성을 선언한다. 이 카드는 해당 레벨과 속성을 가진 몬스터로 취급되어 원하는 자신 필드에 특수소환한다. (이 효과는 패에서도 발동할 수 있다.)',
   do=[B('joker')])
rel_draw('PKBS-014', '2')
fx('PKBS-015', '1', '[지속] 자신 「포커짐승들」 몬스터의 [신속] 효과를 패에서도 발동할 수 있다. (이 효과는 1턴에 2번까지 사용할 수 있다.)', cont=[B('hand_quick')])

# ── 스킬 올인 ──
fx('PKBS-016', '1', '자신은 라운드 시작 시의 패를 {n}장 구성한다.', no_effect=True, card=[player_rule('hand7')])
fx('PKBS-016', '2', '[지속] 자신 필드의 「포커짐승들」 몬스터는 다음의 효과를 얻는다.', no_effect=True)
fx('PKBS-016', '2-a', '[신속] 자신을 포함하는 패, 필드의 레벨이 같은 몬스터 {n}장을 릴리스하고 발동. 상대 필드의 카드 {m}장을 골라 속성과 레벨을 부여하여 컨트롤을 옮긴다.',
   granted=True, zones=FIELD, pk_kind='pair', pk_granted=0, cost=[combo('pair')], do=[B('take_grant')])
fx('PKBS-016', '2-b', '[신속] 자신의 몬스터를 포함하는 자신 패, 필드, 상대 필드의 같은 레벨의 몬스터 {n}장을 릴리스하고 발동. 덱에서 {lv}레벨 이하의 「포커짐승들」 몬스터 {m}장을 소환한다.',
   granted=True, zones=FIELD, pk_kind='triple', pk_granted=1, cost=[combo('triple')],
   do=[special(scope=S('own', 'deck', 'monster', group=PK, level=('<=', '$lv')), n='$m')])
cont_grant('PKBS-016', '2-a', PK, 21)
cont_grant('PKBS-016', '2-b', PK, 22)
