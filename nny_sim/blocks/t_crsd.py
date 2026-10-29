"""조립표 — 저주인형 18종 (CRSD). 문법: blocks/dsl.py, 텍스트대로 바뀐 곳: blocks/CHANGES.md
스킬 「희생제」가 라운드 시작 시 상대 마법 존에 「퇴마의 부적」을 놓고, 저주 카운터(희생제 위)로 싸우는 테마.
「자신 필드의 저주 카운터」는 희생제(스킬 존)와 자신 필드의 카드에 놓인 것(ASSUME — 저주 카운터를 놓을 곳이 희생제뿐, 예전 구현과 같음).
「종료 단계(페이즈)가 되었을 때」 = 종료 단계에 들어설 때(when phase='end_step' — [지속] 종료 처리보다 먼저, 양쪽 플레이어의 종료 단계마다).
퇴마의 부적 2번의 「이 카드의 주인」 = 부적이 놓인 마법 존의 플레이어(재정), 「상대는 자신 필드의 「저주인형」 카드를 1장 골라 파괴」는 상대가 고른다.
저주 - 의심: 처리를 기다리는 부적의 효과(부적의 발동 · 부적 2번으로 바뀐 발동)를 무효로 한다 — 그런 효과가 없으면 발동하지 않는다(설계도 확정 2026-10-10)."""
from blocks.dsl import *   # noqa: F401,F403

SAC_NAME, TAL_NAME, ACE = '희생제', '퇴마의 부적', '저주인형 - 저주인형'
CURSE, EXO = '저주', '퇴마'
SAC = S('own', 'skill', name=SAC_NAME)
CURSE_ZONES = S('own', ('skill', 'field'))
TALISMAN = S('both', 'field', name=TAL_NAME, faceup=True)
OPP_FIELD = S('opp', 'field')
DOLL_MAIN = S('own', 'main', 'monster', group='저주인형')
END_STEP = when('phase', phase='end_step')


def curse(n=1): return counter(CURSE, n, scope=SAC, all=True)
def exo(n=1, scope=TALISMAN): return counter(EXO, n, scope=scope)


def end_curse(code, word='단계'):
    fx(code, '2', f'[트리거] 종료 {word}가 되었을 때 발동. 「희생제」에 저주 카운터를 {{n}}개 놓는다.', when=[END_STEP], do=[curse('$n')])


# ── 몬스터 ──
# 마들렌 1번(키워드 없음 — 기동 효과): 「3개 이상일 경우, 상급 덱에서도」는 카운터를 놓은 뒤(처리 중) 판정
fx('CRSD-001', '1', '「희생제」에 저주 카운터를 {n}개 놓는다. 메인 덱에서 몬스터를 {m}장 특수소환한다. 자신 필드에 저주 카운터가 {k}개 이상일 경우, 상급 덱에서도 특수소환할 수 있다.',
   cond=[any_of(can(special(scope=S('own', 'main', 'monster'), n='$m')),
                B('cond_all', of=(counters_ge(CURSE_ZONES, CURSE, '$k', plus='$n'), can(special(scope=S('own', ('main', 'upper'), 'monster'), n='$m')))))],
   do=[curse('$n'), branch(counters_ge(CURSE_ZONES, CURSE, '$k'),
                           [special(scope=S('own', ('main', 'upper'), 'monster'), n='$m')], [special(scope=S('own', 'main', 'monster'), n='$m')])])
end_curse('CRSD-001', '페이즈')
fx('CRSD-002', '1', '[신속] 자신 필드의 저주 카운터를 {n}개 제거한다. 다음 턴, 상대가 발동할 수 있는 효과는 {m}회로 제한된다. (이 효과는 종료 단계에서만 사용할 수 있다.)',
   do=[counter(CURSE, '$n', op='remove', total=True, scope=CURSE_ZONES, all=True), act_limit('$m')])
end_curse('CRSD-002')
fx('CRSD-003', '1', '[트리거] 상대의 효과가 발동했을 때 발동. 「희생제」에 저주 카운터를 {n}개 놓는다. 그 효과를 무효로 한다.',
   when=[when('activated', who='opp')], do=[curse('$n'), negate_link()])
end_curse('CRSD-003')
fx('CRSD-004', '1', '[소환] 덱에서 「저주」 마법 카드를 {m}장 패에 넣는다. 「희생제」에 저주 카운터를 {n}개 놓는다.',
   do=[search(S('own', 'deck', 'spell', group='저주'), '$m'), curse('$n')])
end_curse('CRSD-004')
fx('CRSD-005', '1', '[신속] 저주 카운터를 {n}개 제거하고, 상대 필드의 카드 {m}장을 대상으로 하고 발동. 그 카드를 파괴하고 {amt} 대미지를 준다. '
   '(이 효과는 1턴에 1번 제약을 받지 않으며 종료 단계에서만 사용할 수 있다.)',
   cost=[counter(CURSE, '$n', op='remove', total=True, scope=CURSE_ZONES, all=True), target('T', OPP_FIELD, n='$m')],
   do=[destroy(ref='T'), damage('$amt')])
end_curse('CRSD-005')
fx('CRSD-006', '1', '[트리거] 상대가 효과를 발동했을 때 발동. 「희생제」에 저주 카운터를 {n}개 놓는다. 상대 필드의 카드 {m}장을 파괴한다. (이 효과는 1턴에 3번까지 사용할 수 있다.)',
   when=[when('activated', who='opp')], do=[curse('$n'), destroy(scope=OPP_FIELD, n='$m')])
fx('CRSD-006', '2', '[트리거] 종료 단계가 되었을 때 발동. 필드의 「퇴마의 부적」에 퇴마 카운터를 {n}개 놓는다.', when=[END_STEP], do=[exo('$n')])

# 저주인형 - 저주인형
fx('CRSD-007', '1', '[지속] 이 카드는 전투로는 파괴되지 않고, 릴리스되지 않으며, 「퇴마의 부적」 이외의 카드의 효과를 받지 않는다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[self_rule('indestructible', battle=True), card_flag('no_release'), card_flag('immune_except', value=TAL_NAME)])
fx('CRSD-007', '2', '이 카드를 제외한다. 이 효과로 제외 존에 「저주인형 - 저주인형」이 {n}장 모였을 경우, 자신은 게임에서 승리한다.',
   do=[banish(ref='SELF', ref_scope=S('own', 'field'), harm=False), branch(cnt(S('own', 'banish', name=ACE), '>=', '$n'), [win()])])
fx('CRSD-007', '3', '[유언] 이 카드를 덱으로 되돌린다. 덱에서 「저주인형」 몬스터를 {n}장 특수소환한다.',
   do=[to_deck(ref='SELF', ref_scope=S('own', 'grave'), harm=False), special(scope=S('own', 'deck', 'monster', group='저주인형'), n='$n')])

# ── 마법 · 필드 ──
# 퇴마의 부적 — 1번 「카운터를 쌓는 효과는 적용」은 엔진(Game.counter_text_ok), 2번은 주인에게 불리한 [지속](forced — 고르지 않고 늘 적용, 자신 필드에 놓지 않음)
fx('CRSD-008', '1', '[지속] 이 카드는 릴리스할 수 없고, 상대의 「저주 - 의심」 마법 이외의 카드의 효과를 받지 않는다. (카운터를 쌓는 효과는 적용되며, 이 효과는 1턴에 1번 제약을 받지 않는다.)',
   cont=[card_flag('no_release'), card_flag('immune_except', value='저주 - 의심'), card_flag('immune_except_opp')])
fx('CRSD-008', '2', '[지속] 이 카드의 퇴마 카운터가 {n}개 이상일 때, 이 카드의 주인이 다음에 발동하는 효과는 무효가 되고 '
   '「「퇴마의 부적」에 놓인 카운터를 {m}개 제거한다. 상대는 자신 필드의 「저주인형」 카드를 {k}장 골라 파괴한다.」로 변경된다. (이 효과는 1턴에 1번 제약을 받지 않는다.)',
   forced=True,
   cont=[next_act_replace(EXO, '$n', [counter(EXO, '$m', op='remove', ref='SELF'),
                                      destroy(scope=S('opp', 'field', group='저주인형'), n='$k', chooser='opp')],
                          label='퇴마 카운터 제거 · 상대가 고른 「저주인형」 카드 파괴')])
fx('CRSD-008', '3', '[트리거] 종료 단계가 되었을 때 발동. 이 카드에 퇴마 카운터 {n}개를 놓는다.', when=[END_STEP], do=[counter(EXO, '$n', ref='SELF')])

fx('CRSD-009', '1', '[신속] 메인 덱에서 「저주인형」 카드를 {m}장 특수소환한다. 필드의 「퇴마의 부적」에 퇴마 카운터를 {n}개 놓는다.',
   do=[special(scope=S('own', 'main', group='저주인형'), n='$m'), exo('$n')])
fx('CRSD-010', '1', '[신속] 필드의 「퇴마의 부적」의 효과를 무효로 한다. 이 카드가 묘지로 보내졌을 때, 필드의 「퇴마의 부적」의 효과를 다시 활성화한다.',
   do=[negate_chain(name=TAL_NAME)])
fx('CRSD-011', '1', '메인 덱에서 「저주」 카드를 {m}장 패에 넣는다. 필드의 「퇴마의 부적」에 퇴마 카운터를 {n}개 놓는다.',
   do=[search(S('own', 'main', group='저주'), '$m'), exo('$n')])
# 타락 — 「상대가 카드를 발동했을 때」는 카드의 발동만(사용자 답변 2026-10-20)
fx('CRSD-012', '1', '[트리거] 상대가 카드를 발동했을 때, 상대 필드의 카드 {m}장을 대상으로 하고 발동. 그 카드를 묘지로 보내고, 필드의 「퇴마의 부적」에 퇴마 카운터를 {n}개 놓는다.',
   when=[when('activated', who='opp', card_only=True)], cost=[target('T', OPP_FIELD, n='$m')], do=[send_grave(ref='T'), exo('$n')])
# 탐욕 — 상대가 고른다(상대가 처리하는 플레이어 — 「자신의 패」 = 상대의 패)
fx('CRSD-013', '1', '[지속] 상대는 자신의 턴 시작 시에 이하의 효과 중 하나를 선택하여 적용한다.\n- 자신의 패를 {m}장 묘지로 보낸다.\n'
   '- 필드의 「퇴마의 부적」에 퇴마 카운터를 {n}개 놓는다.',
   cont=[turn_start([choice([send_grave(scope=S('own', 'hand'), n='$m')], [exo('$n')])], whose='opp', actor='opp')])
fx('CRSD-014', '1', '[트리거] 자신 카드의 효과가 무효화되었을 때 발동. 메인 덱에서 「저주인형」 카드를 {m}장 특수소환한다. 필드의 「퇴마의 부적」에 퇴마 카운터를 {n}개 놓는다.',
   when=[when('negated', who='own')], do=[special(scope=S('own', 'main', group='저주인형'), n='$m'), exo('$n')])
fx('CRSD-015', '1', '[신속] 상대 필드의 카드 {m}장을 릴리스한다. 자신 묘지에서 「저주인형」 몬스터 {k}장을 특수소환한다. 필드의 「퇴마의 부적」에 퇴마 카운터를 {n}개 놓는다.',
   do=[release(scope=S('opp', 'field', pred='releasable'), n='$m'), special(scope=S('own', 'grave', 'monster', group='저주인형'), n='$k'), exo('$n')])
fx('CRSD-016', '1', '자신 묘지의 「저주」 및 「저주인형」 카드를 {n}장 덱으로 되돌린다. 자신은 {m}장 드로우한다.',
   do=[to_deck(scope=S('own', 'grave', group=('저주', '저주인형')), n='$n', harm=False, shuffle=True), draw('$m')])
# 위저보드 — 서로의 턴 시작 시마다 이 카드의 컨트롤러가 고른다
fx('CRSD-017', '1', '[지속] 서로의 턴 시작 시에 이하의 효과 중 하나를 선택하여 적용한다.\n- 덱에서 「저주인형」 카드를 {m}장 특수소환한다.\n'
   '- 상대 필드의 「퇴마의 부적」에 퇴마 카운터를 {n}개 놓는다.',
   cont=[turn_start([choice([special(scope=S('own', 'deck', group='저주인형'), n='$m')],
                            [exo('$n', S('opp', 'field', name=TAL_NAME, faceup=True))])])])

# ── 스킬 희생제 ──
fx('CRSD-018', '1', '라운드 시작 시에 자신의 덱에서 「퇴마의 부적」 {n}장을 상대의 마법 존에 놓는다.', no_effect=True,
   card=[round_start([place(S('own', 'deck', name=TAL_NAME), n='$n', to='opp')])])
fx('CRSD-018', '2', '자신의 메인 덱에서 몬스터를 {n}장 특수소환한다.', do=[special(scope=S('own', 'main', 'monster'), n='$n')])
fx('CRSD-018', '3', '[트리거] 이 카드에 저주 카운터가 {k}개 놓였을 때 발동. 상급 덱에서 몬스터를 {n}장 특수소환한다.',
   when=[when('counter', name=CURSE, n='$k')], do=[special(scope=S('own', 'upper', 'monster'), n='$n')])
fx('CRSD-018', '4', '[지속] 상대 턴의 종료 시에 자신은 이 카드의 저주 카운터를 전부 제거하고, 제거한 수 × {a} 대미지를 받는다. '
   '자신 필드에 「저주인형 - 저주인형」이 존재할 경우, 제거한 수 × {b} 대미지를 상대에게 준다. (이 효과는 강제로 발동한다.)',
   forced=True,
   cont=[end_process([counter(CURSE, op='remove_all', ref='SELF', count_as='N'), damage('$a', who='self', times=('ref', 'N')),
                      branch(cnt(S('own', 'field', 'monster', name=ACE, faceup=True)), [damage('$b', who='opp', times=('ref', 'N'))])], whose='opp')])
