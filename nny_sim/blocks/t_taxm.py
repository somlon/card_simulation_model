"""조립표 — 세리 11종 (TAXM). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
세금 = 덱 위에서 카드 제외. 덱 위 제외의 덱 고르기(§6-7): 「메인 · 상급 덱의 위에서부터」는 그 덱만(부족분 문구가 있으면 다른 덱에서),
덱 미지정은 주어가 고른다(「상대의 덱의 위에서부터 … 제외한다」는 효과를 쓴 플레이어 — chooser='self').
「서로가 …할 때마다, 그 플레이어는 … 제외한다」 [지속](세제 · 아이라리움 · 취득세 1번)은 엔진 공통 규칙 행동 세금(카드 텍스트에서 읽음 — Game.pay_tax)."""
from blocks.dsl import *   # noqa: F401,F403

SERI_MAIN_MON = S('own', 'main', 'monster', group='세리')
SERI3_GRAVE = S('own', 'grave', 'monster', group='세리', level=('==', 3))
SHORT_UPPER = '제외할 카드가 부족할 경우, 부족한 매수만큼을 자신의 상급 덱의 위에서부터 대신 제외한다.'

# 세리 몬스터 공통 [유언] — 코스트: 자신의 제외 존 → 덱(델레가토르면 상대가 자신의 제외 존에서 대신, 아이라리움 2번이면 1장)
def seri_lastwill(code, key='2'):
    fx(code, key, '[유언] 자신의 제외 존에서 카드를 {n}장 골라 자신의 덱으로 되돌리고 발동. 자신의 메인 덱에서 「세리」 몬스터를 {m}장 특수소환한다.',
       cost=[to_deck(scope=S('own', 'banish'), n='$n', transfer=True, shuffle=True, n_rule=('seri_lw_one', 1), harm=False)],
       do=[special(scope=SERI_MAIN_MON, n='$m')])

# 마법 공통 [유언] — 상대에 의해 묘지로: 자신 메인 덱 위 3장 제외(코스트)하고 이 카드를 패로
def spell_lastwill(code, key):
    fx(code, key, f'[유언] 이 카드가 상대에 의해 자신의 묘지로 보내진 경우, 자신의 메인 덱의 위에서부터 카드를 {{n}}장 제외하고 발동. 이 카드를 자신의 패에 넣는다. {SHORT_UPPER}',
       when=[when('to_grave', by_opp=True)], cost=[mill('$n', deck='main')], do=[to_hand(ref='SELF', ref_scope=S('own', 'grave'), harm=False)])


fx('TAXM-001', '1', '[지속] 이 카드가 필드에 앞면 표시로 존재하는 한, 자신이 카드의 발동을 위해 지불해야 하는 코스트는 상대가 대신 지불한다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[player_rule('cost_transfer', who='own')])
fx('TAXM-002', '1', '[지속] 이 카드가 필드에 앞면 표시로 존재하는 한, 서로가 카드의 발동을 위해 코스트로 지불해야 하는 카드의 매수는 {n}배가 된다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[player_rule('cost_double', who='both')])
fx('TAXM-003', '1', '[소환] 서로 자신의 덱의 위에서부터 카드를 {n}장 제외한다.', do=[mill('$n', who='both')])
fx('TAXM-004', '1', '[지속] 이 카드가 필드에 앞면 표시로 존재하는 한, 자신 필드의 다른 카드들은 상대의 효과를 받지 않는다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[rule_immune(S('own', 'field', not_self=True), frm='opp')])
for code in ('TAXM-001', 'TAXM-002', 'TAXM-003', 'TAXM-004'): seri_lastwill(code)

# 치프 세리 - 프로쿠라토르
fx('TAXM-005', '1', '[제약] 이 카드는 자신의 묘지에서 {lv}레벨 「세리」 몬스터를 {n}장 제외하는 것으로 일반소환할 수 있다.',
   card=[alt_normal(S('own', 'grave', 'monster', group='세리', level=('==', '$lv')), '$n')])
fx('TAXM-005', '2', '[소환] 자신의 제외 존의 카드를 전부 자신의 덱으로 되돌리고 발동. 되돌린 매수만큼 상대의 덱의 위에서부터 카드를 제외한다.',
   cost=[to_deck(scope=S('own', 'banish'), all=True, transfer=True, count_as='N', shuffle=True, harm=False)],
   do=[mill(('ref', 'N'), who='opp', chooser='self')])
fx('TAXM-005', '3', '[유언] 자신의 묘지에서 {lv}레벨 「세리」 몬스터를 {n}장 특수소환한다.',
   do=[special(scope=S('own', 'grave', 'monster', group='세리', level=('==', '$lv')), n='$n')])

# 소환세
fx('TAXM-006', '1', '자신의 메인 덱에서 「세리」 몬스터를 {n}장 골라 자신의 패에 넣는다.', do=[search(SERI_MAIN_MON, '$n')])
spell_lastwill('TAXM-006', '2')

# 인지세 — 「카드의 발동」만(재정 10-20 Q13), 상대가 고른다(제외 · 무효)
fx('TAXM-007', '1', '[신속] 상대가 카드의 발동을 선언했을 때 발동. 상대는 자신의 메인 덱의 위에서부터 카드를 {n}장 제외하거나 그 카드를 무효로 한다. '
   '제외할 카드가 부족할 경우, 부족한 매수만큼을 상대의 상급 덱의 위에서부터 대신 제외한다.',
   kind='resp', when=[when('activated', who='opp', card_only=True)],
   do=[choice([mill('$n', who='opp', deck='main', fallback=True)], [negate_link()], chooser='opp')])
spell_lastwill('TAXM-007', '2')

# 이탈세
fx('TAXM-008', '1', '이 카드의 {a}·{b}번 효과는 동시에 발동할 수 없다.', no_effect=True, card=[exclusive('$a', '$b')])
fx('TAXM-008', '2', '[트리거] 상대가 자신 필드의 카드를 필드에서 벗어나게 하는 효과의 발동을 선언했을 때 발동. '
   '그 효과를 「자신의 상급 덱의 위에서부터 카드를 {n}장 제외한다. 제외할 카드가 부족할 경우, 부족한 매수만큼을 자신의 메인 덱의 위에서부터 대신 제외한다.」로 변경한다.',
   spell_act=True, when=[when('activated', who='opp', moves_off=True)],   # 1번은 규칙 문장 — 카드의 발동은 2번
   do=[replace([mill('$n', who='self', deck='upper', fallback=True)], label='상급 덱 위 5장 제외')])
spell_lastwill('TAXM-008', '3')
fx('TAXM-008', '4', '[유언] 상대의 덱의 위에서부터 카드를 {n}장 제외한다. 이 효과에 상대는 체인할 수 없다.',
   no_resp=True, do=[mill('$n', who='opp', chooser='self')])

# 취득세 · 세 - 아이라리움 · 세제 1번 — 행동 세금(엔진)
fx('TAXM-009', '1', '[지속] 서로가 몬스터를 특수소환할 때마다, 그 플레이어는 자신의 덱의 위에서부터 카드를 {n}장 제외한다. (이 효과는 1턴에 1번 제약을 받지 않는다.)')
spell_lastwill('TAXM-009', '2')
fx('TAXM-010', '1', '[지속] 서로가 카드를 드로우하거나 덱에서 패에 카드를 넣을 때마다, 그 플레이어는 자신의 덱의 위에서부터 카드를 {n}장 제외한다. (이 효과는 1턴에 1번 제약을 받지 않는다.)')
fx('TAXM-010', '2', '[지속] 자신 필드의 「세리」 몬스터의 [유언] 효과의 코스트로 자신의 제외 존에서 자신의 덱으로 되돌리는 매수는 {n}장이 된다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[player_rule('seri_lw_one', who='own')])
fx('TAXM-011', '1', '[지속] 서로가 효과를 발동할 때마다, 그 플레이어는 자신의 덱의 위에서부터 카드를 {n}장 제외한다. (이 효과는 1턴에 1번 제약을 받지 않는다.)')
# 세제 2 · 3번 — 「서로가 … 발동」: 상대도 발동할 수 있다(재정 10-20 Q4 — Effect.either_player, 텍스트로 표시)
fx('TAXM-011', '2', '서로가 자신의 메인 덱에서 카드를 {n}장 제외하고 발동. 자신의 메인 덱에서 {m}장 드로우한다. '
   '제외할 카드가 부족할 경우, 부족한 매수만큼을 자신의 상급 덱의 위에서부터 대신 제외한다.',
   cond=[B('cond_tax_draw', n='$n', deck='main', draws='$m')], cost=[mill('$n', deck='main')], do=[draw('$m', deck='main')])
fx('TAXM-011', '3', '서로가 자신의 상급 덱에서 카드를 {n}장 제외하고 발동. 자신의 상급 덱에서 {m}장 드로우한다. '
   '제외할 카드가 부족할 경우, 부족한 매수만큼을 자신의 메인 덱의 위에서부터 대신 제외한다.',
   cond=[B('cond_tax_draw', n='$n', deck='upper', draws='$m')], cost=[mill('$n', deck='upper')], do=[draw('$m', deck='upper')])
