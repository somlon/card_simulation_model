"""카드 구현 10차: 데이터버그 23종 (카드 자료 2026-10-08, DTBG-001~023)
몬스터의 소환 그 자체를 트리거로 삼는 전개 테마. 15종 중 11종이 「필드에 「데이터버그」 몬스터가 소환되었을 때 패에서 특수소환」
(손패 트리거)을 가지고, [소환] · 서치 · 덱/묘지 특수소환이 다음 소환을 부른다. 스킬 「데이터버그 패키지 프로그램」은 필드를
「데이터버그」 몬스터 6장(몬스터 존 5 + 공유 존)으로 채웠을 때 일반소환을 1회 더 준다.

구현 방식:
- 손패 트리거(hand_ss): 'trigger' 효과 (zones=('hand',)), 소환 사건마다 패의 카드가 조건을 본다. 같은 이름은 1턴에 1번(카드명 × 효과 번호)이라
  한 턴의 연쇄는 이름 수만큼으로 끝난다. AI 점수는 빈 몬스터 존보다 더 가치 있는 후보가 많으면 0 (자리를 약한 몬스터가 먼저 차지하지 않게).
- 덱 · 묘지에서 고르는 카드는 pick(): 학습형 AI는 학습표(판단 「서치:<이유>」, 사전값 = 상황별 휴리스틱), 휴리스틱 AI는 사전값 최대.
- 더 바이러스 · 더 딜리트의 패에서의 특수소환(소환 절차)은 진행/정비 단계의 행동인 기동 효과로 모델링하되 Effect.procedure 표시로
  발동 사건 · 발동 횟수에 들어가지 않고, 대응(no_resp) · 무효(unnegatable)가 없다.
- 콜로니로 특수소환한 몬스터의 「이 턴에 효과를 발동할 수 없다」: flags['no_act_until'] = 그 턴 (필드를 벗어나면 clear_on_leave로 지움).
  모든 「데이터버그」 몬스터 효과의 발동 조건이 이 플래그를 본다(db_mon) — 엔진 변경 없음.

ASSUME:
- 효과 종류 표기가 없는 효과(캐터필러 1 · 코쿤 1 · 에볼루션 마스터 1 · 앤트 1 · 퀸 비 2 · 유니온 마스터 1 · 로딩 2 · 콜로니 1 · 스킬 1)는
  기동 효과(자신 턴 진행/정비 단계 · 체인 없음).
- 「필드에 「데이터버그」 몬스터가 소환되었을 때」 = 서로의 필드, 일반 · 특수소환 모두, 사건 기준 — 소환된 몬스터가 그 뒤 필드를 벗어나도
  (다운로드) 발동한다. 「자신 필드에」(퀸 비 · 유니온 마스터 3번)는 자신이 자신 필드에 소환한 것만. 리틀버그 2번 「「데이터버그」 몬스터가
  소환되었을 때」는 리틀버그 자신의 소환도 포함 (필드의 리틀버그가 발동).
- 「덱에서」(덱 미지정) = 메인 · 상급 덱 모두, 「메인 덱에서」 · 「상급 덱에서」는 그 덱만. 서치 · 덱 특수소환은 효과 주체와 같은 이름의 카드를
  고를 수 없다(사용자 재정 · 정본 3-6 f) — 앤트 2번은 자기 이름이 적혀 있어 예외(cards.Impl.attach 자동 판정). 「「데이터버그」 몬스터를 패에
  넣는다」처럼 장수가 없으면 1장.
- 플라이 1번 「이 카드가 패에 넣어졌을 때」: 서치 · 회수 · 필드에서 패로 · 드로우(라운드 시작 패 · 멀리건 제외) 모두. 「특수소환하고, … 서치」는
  각각 처리 — 특수소환할 수 없어도(자리 없음) 마법 서치는 한다.
- 코쿤 · 에볼루션 마스터 2번 「패의 이 카드를 덱으로 되돌리고, … 패에 넣는다」: 처리 시 이 카드가 패에 없으면 서치도 하지 않는다.
- 「자신 필드의 「데이터버그」 몬스터를 2장 릴리스하고 발동」(에볼루션 1 · 퀸 비 2 · 유니온 1)은 이 카드 자신도 포함할 수 있다 (AI는 아직 쓸
  효과가 남은 카드 · 가치가 높은 카드를 뒤로). 로딩 2번 「필드에서」 · 습격 「필드의」는 자신 필드의 「데이터버그」 몬스터만 (사용자 답변 2026-10-22 Q41 —
  코스트 문장의 「필드」는 「서로」 · 「상대」가 적혀 있을 때만 상대 필드를 포함한다, cards.cost_opp). 릴리스는 releasable.
- 에볼루션 마스터 1번 「(이 효과는 계속해서 사용할 수 있다.)」 = 1턴 사용 횟수 제한 없음.
- 헤라클레스 1번 [전투]: 「자신은 이어서 공격할 수 있다」 = 이 카드가 한 번 더 공격할 수 있다(추가 공격 1회). 파괴할 상대 카드가 없어도
  1000 대미지 · 추가 공격은 처리.
- 웜 1번: 대상 「필드의 「데이터버그」 몬스터」는 서로의 필드. 처리 시 대상이 필드에 없어도 메인 덱 특수소환은 한다.
- 유니온 마스터 2번 「「데이터버그」 카드의 수」는 앞면 카드만 센다.
- 버터플라이 2번(2026-10-22 텍스트 변경 — 사용자 지시) 「[지속] 상대는 덱에서 패에 카드를 넣을 수 없다」: 엔진 규칙 'no_deck_to_hand'.
  이 카드가 무효화되지 않는 한 상대는 덱에서 패에 넣는 효과를 발동할 수 없다(서치 후보 없음 — Game.search_cands). 상대 플레이어에게 거는 금지라
  1턴 1번이어도 상대의 모든 행동에 작용해 사실상 횟수 제한이 없다(Game.cont_limit — 사용자 지시 2026-10-22). 효과로 하는 드로우도 막는다
  (같은 규칙 'no_deck_to_hand' — 사용자 답변 2026-10-22 Q46, Game.draw). 드로우가 든 효과의 발동은 막지 않고 드로우만 하지 않는다(PDF 2026-10-23 Q7). 턴 시작 드로우 등 규칙 드로우는 막지 않는다.
  예전 텍스트(자신은 상대의 효과를 받지 않는다)의 해석:
  상대 더 딜리트 3번(덱→패 금지)을 받지 않는다. 자신 필드 · 패의 카드에 대한 내성은 아니다.
- 디지털 웜 2번 「자신 필드에서 「데이터버그」 카드 1장을 묘지로 보낸다」는 처리 문장(「하고 발동」 문구 없음 — 코스트 아님). 이 카드 자신도
  보낼 수 있다(AI는 가치가 낮은 카드부터). 1 · 2번 모두 「고르고」 없는 파괴라 처리 시 고른다(대상 지정 없음).
- 더 바이러스 · 더 딜리트 1번 [제약](소환 조건 — 2026-10-22 텍스트, 패에서도 판정): 「다른 카드의 효과로 소환할 수 없다」 = 이 모듈의 모든 특수소환 후보에서 뺀다(flags['ss_self_only'] —
  지금 카드 풀에 상대 · 다른 테마 카드를 특수소환하는 효과는 없다), 일반소환 불가(flags['no_normal']). 「자신 필드의 몬스터 3장」은
  「데이터버그」가 아니어도 된다 · 뒷면 몬스터 포함. 소환 절차는 효과의 발동이 아니다(Effect.procedure — 발동 사건 · 비비안 발동 횟수 ·
  퇴마의 부적 변경 · 세제 제외 대상이 아님, 체인에 대응할 수 없고 무효화되지 않음). 소환 자체는 소환이므로 상대의 더 바이러스 2번 ·
  「소환되었을 때」 트리거의 대상이다.
- 더 바이러스 2번 「그 소환을 무효로 하고 파괴한다」 (설계도 확정 2026-10-10): 소환 무효를 그 소환의 [소환] 효과보다 먼저 묻고(Effect.summon_negate —
  Game.triggers의 앞 단계에서 발동 · 처리), 무효로 했으면 그 소환 사건에 negated를 달아 [소환] 효과를 묻지 않는다. 소환된 몬스터는 파괴한다.
- 쌍살벌 2번 「그 발동을 무효로 한다」: 지속 · 필드 마법 카드의 발동이 무효가 되면 그 카드를 묘지로 보낸다. 버터플라이 1번 「그 효과를 무효로
  한다」는 엔진 기본(지속 마법은 필드에 남음).
- 더 딜리트 2번 「필드의 몬스터가 파괴되었을 때」 = 서로의 몬스터. 「필드의 카드를 1장 파괴」에서 더 딜리트 자신은 고르지 않는다.
- 로딩 1번(「발동 선언을 필요로 하지 않는다」)은 마법 카드 발동의 처리에 딸린다 — 1턴에 1번(같은 턴 두 번째 로딩 발동은 서치 없음).
  카드의 발동 자체(효과 0)는 1턴 1번 제약이 없다(opt=None, 2026-10-13 검토 반영).
- 「효과로 덱에서 카드를 패에 넣을 수 없다」(더 딜리트 3번 · 던전마스터 데스 칠 드래곤 2번)는 효과로 하는 드로우도 막는다(사용자 답변 2026-10-22 Q46):
  드로우가 든 효과도 발동할 수 있고 나머지는 처리하되 드로우만 하지 않는다(Game.draw — 사용자 답변 2026-10-23 PDF Q7: 영웅의 조건은 덱으로만 돌아감, 조커는 묘지로만 보냄).
- (예전 텍스트) 버터플라이 2번 「자신은 상대의 효과를 받지 않는다」: 효과 대미지와 플레이어 대상 [지속]만 — 2026-10-22 텍스트 변경으로 없앰.
  거짓 샘물의 전투 파괴 금지 · 강제 「상대는 1장 드로우」 등 다른 플레이어 대상 효과는 받는다.
- 콜로니 1번은 카드의 발동과 별개인 기동 효과(앞면으로 놓인 뒤 1턴에 1번). 「이 효과로 특수소환한 몬스터는 이 턴에 효과를 발동할 수
  없다」 = 그 몬스터가 필드에 있는 동안 이 턴에는 그 카드의 효과([소환] 포함)를 발동할 수 없다. [지속]은 적용된다. 필드를 벗어나면 풀린다.
- 백업: 대상이 처리 시 자신 필드에 없거나 묘지로 가지 않으면 이후 처리 없음. 같은 이름 카드가 덱에 없어도 특수소환은 한다.
- 아로마: 버릴 패가 1장 이상 있어야 발동한다. 버린 카드도 특수소환 후보 — AI는 「데이터버그」 상급 몬스터를 버리고 되살리는 것도 고려한다.
- 습격 「그 후」: 상대 카드를 파괴했을 때만 묘지에서 「데이터버그」 몬스터를 2장(까지) 특수소환한다.
- 리벤지 「상대의 효과에 의해」 = 상대 카드의 효과 또는 코스트(사건 cause의 주체 카드를 상대가 컨트롤). 「필드의 카드를 전부 파괴」에서
  리벤지 자신은 뺀다. 「그 후」 특수소환은 파괴 처리 뒤 묘지에 「데이터버그」 몬스터가 있으면 한다.
- 패키지 프로그램: 「6장」 = 몬스터 존 5 + 공유 존 1을 모두 「데이터버그」 몬스터로 채운 상태(자신 필드 최대 6장). 추가 일반소환 권리는 엔진의
  extra_normal(그 턴 1회). 공유 존은 사용자 지침상 필요할 때만 쓰므로, AI는 「이 몬스터로 6장이 되고 스킬을 아직 쓰지 않았고 패에 일반소환할
  몬스터가 있을 때」 공유 존 사용을 허용한다(ai.HeuristicAI.use_shared의 스킬 훅 wants_shared).

재정 질문:
1. 플라이 1번 「패에 넣어졌을 때」에 드로우도 포함되는가 → 포함 (사용자 답변 2026-10-22 Q38, 유지).
2. 헤라클레스 1번 「자신은 이어서 공격할 수 있다」 — 이 카드의 추가 공격 1회 (사용자 답변 2026-10-22 Q39, 유지).
3. (해결 2026-10-22) 버터플라이 2번은 「상대는 덱에서 패에 카드를 넣을 수 없다」로 텍스트가 바뀌어 질문이 없어졌다.
4. 더 바이러스 · 더 딜리트의 패에서의 특수소환은 체인에 올리는 효과의 발동인가, 발동이 아닌 소환 절차인가 (지금: 소환 절차)?
5. 더 바이러스 2번으로 소환이 무효가 된 몬스터의 [소환] 효과는 발동하지 않은 것으로 보는가 (지금: 근사 처리 — 체인 위의 [소환] 무효)?
6. 로딩 2번 「필드에서」 · 습격 「필드의」에 상대 필드의 「데이터버그」 몬스터도 포함되는가 → 자신 필드만 (사용자 답변 2026-10-22 Q41).
7. 콜로니 1번은 카드 발동 시 1번만 처리되는가, 필드에 있는 동안 매 턴 쓸 수 있는 효과인가 (지금: 매 턴 1번 기동)?
8. 웜 1번 · 백업 · 습격처럼 「A하고, B」 · 「그 후」 앞부분을 처리할 수 없으면 뒷부분도 처리하지 않는가 (지금: 웜 1번은 처리, 백업 · 습격은 안 함)?
9. 디지털 웜 2번의 「자신 필드에서 「데이터버그」 카드 1장을 묘지로 보낸다」는 처리 (사용자 답변 2026-10-22 Q42, 유지).
10. 유니온 마스터 2번에서 세트(뒷면) 「데이터버그」 카드는 세지 않는다 (사용자 답변 2026-10-22 Q43, 유지).
11. 패키지 프로그램 「6장 존재」는 공유 존까지 채워야만 가능한가 (지금: 그렇다)?
12. 에볼루션 마스터 · 퀸 비 · 유니온 마스터의 「자신 필드의 「데이터버그」 몬스터를 2장 릴리스」에 이 카드 자신을 포함할 수 있다 (사용자 답변 2026-10-22 Q44, 유지).
13. 더 바이러스 · 더 딜리트 1번 「자신 필드의 몬스터를 3장」은 「데이터버그」 이외 · 뒷면 몬스터도 된다 (사용자 답변 2026-10-22 Q45, 유지 — 뒷면 일반 규칙은 engine.Game.immune · clear_applied).
14. 더 딜리트 3번(· 던전마스터 데스 칠 드래곤 2번) 「효과로 덱에서 카드를 패에 넣을 수 없다」는 효과로 하는 드로우도 막는다 (사용자 답변 2026-10-22 Q46, 변경).

엔진 변경 (engine.py · ai.py, 추가 · 표시가 없는 카드의 동작은 그대로):
- engine.Effect 속성 procedure(getattr 기본 False — Effect 인스턴스에 붙인다): Game.activate가 발동 사건('activate') · 발동 횟수(act_count)를
  남기지 않고, Game.legal이 발동 횟수 제한(act_limit, 비비안)을 보지 않는다 — 소환 절차(더 바이러스 · 더 딜리트 1번).
- engine.Game.damage: [지속] 규칙 'no_effect_damage'(p, src) — 「자신은 상대의 효과를 받지 않는다」(버터플라이 2번). 출처 판정은 규칙 함수가 한다
  (처리 중인 효과의 주체 Game.src가 상대 카드 / 출처 이름이 상대 카드). 공유 존 마커 · 「자해」 대미지는 묻지 않는다.
- ai.HeuristicAI.use_shared: 스킬 카드의 훅 wants_shared(g, p, c) — 스킬 조건을 위해 공유 존을 쓸 이유(패키지 프로그램). LearnedAI도 이것을 거친다.
- ai.DECK_POLICY['데이터버그 패키지 프로그램'].
- 그 밖(엔진 변경 없음): 콜로니의 발동 제한은 이 모듈의 db_mon(발동 조건 감싸기) + flags['clear_on_leave'], 추가 일반소환은 엔진의 extra_normal,
  덱→패 금지는 엔진 규칙 'no_deck_to_hand', 「다른 카드의 효과로 소환할 수 없다」는 이 모듈의 ss_ok.
"""
from engine import Effect, link_targets
from cards import card, grp, best, value, own_turn, main_ok, opp_cards, last_opp_link, threat, cause_card, ev_is, VETO, field_pick, cost_opp
from cards2 import targets

DB = '데이터버그'
SKILL = '데이터버그 패키지 프로그램'
CATER, FLY, LITTLE, COCOON, EVO = ('데이터버그 캐터필러', '데이터버그 플라이', '데이터버그 리틀버그', '데이터버그 코쿤', '데이터버그 에볼루션 마스터')
ANT, HERC, WORM, QUEEN, UNION = ('데이터버그 앤트', '데이터버그 헤라클레스', '데이터버그 웜', '데이터버그 퀸 비', '데이터버그 유니온 마스터')
BUTTER, DWORM, VIRUS, DELETE, WASP = ('데이터버그 버터플라이', '데이터버그 디지털 웜', '데이터버그 더 바이러스', '데이터버그 더 딜리트', '데이터버그 쌍살벌')
LOADING, BACKUP, DOWNLOAD, AROMA = '데이터버그 로딩', '데이터버그 백업', '데이터버그 다운로드', '데이터버그 아로마'
RAID, REVENGE, COLONY = '데이터버그 습격', '데이터버그 리벤지', '데이터버그 콜로니'
FIELD_M = ('m', 'shared')

# 패에서 특수소환 트리거(손패 트리거)의 효과 번호
HT = {CATER: 2, FLY: 2, LITTLE: 3, ANT: 3, HERC: 2, WORM: 3, QUEEN: 3, UNION: 3, BUTTER: 3, DWORM: 3, WASP: 3}
# 패에 넣을 카드의 기본 사전값 (AI)
HAND_PRI = {FLY: 30, DWORM: 50, ANT: 46, BUTTER: 44, HERC: 42, QUEEN: 40, WASP: 38, WORM: 36, UNION: 34, LITTLE: 35, CATER: 30,
            VIRUS: 28, DELETE: 28, COCOON: 22, EVO: 18,
            COLONY: 50, RAID: 45, LOADING: 38, BACKUP: 36, DOWNLOAD: 32, AROMA: 30, REVENGE: 26}
# 다운로드(특수소환 후 곧바로 묘지로)로 고를 카드: 묘지에서 되살릴 가치
GRAVE_PRI = {LITTLE: 40, CATER: 36, COCOON: 34, EVO: 15, FLY: 10}


def DBC(x): return grp(x, DB)
def DBM(x): return grp(x, DB) and x.is_monster()
def DBS(x): return grp(x, DB) and x.type == '마법'


def opt_free(g, p, name, num): return g.p[p].opt.get((name, num), 0) < 1
def use_opt(g, p, name, num): g.p[p].opt[(name, num)] = g.p[p].opt.get((name, num), 0) + 1


def ss_ok(g, x, p):
    """x를 이 모듈의 효과로 특수소환할 수 있는가: 「다른 카드의 효과로 소환할 수 없다」(더 바이러스 · 더 딜리트) 제외 + 엔진 판정"""
    return not x.flags.get('ss_self_only') and g.can_special(x, p)


def leaves_ok(g, x):
    """코스트로 필드를 벗어나게 할 수 있는가 (「파괴 이외의 방법으로 필드를 벗어나지 않는다」 — Game.stays와 같은 판정, 로그 없음)"""
    return not (g.on_field(x) and not g.is_neg(x) and g.flag(x, 'leave_only_destroy'))


def summoned_db(ev, p=None):
    """「데이터버그」 몬스터의 소환 사건 (p가 있으면 p가 자신 필드에 소환한 것만)"""
    return ev_is(ev, 'summon') and DBM(ev['card']) and (p is None or ev['player'] == p)


def summoned_self(g, c, ev): return ev_is(ev, 'summon') and ev['card'] is c and g.on_field(c)


def has_db_spell(g, p): return any(y.faceup and DBS(y) for y in g.spells(p))


def threatened(g, p):
    """체인 맨 위의 상대 발동이 발동 시 고른 자신 필드의 카드"""
    l = last_opp_link(g, p)
    if l is None: return []
    return [x for x in link_targets(l) if g.on_field(x) and x.controller == p]


# ═══════════════════════ AI 사전값 ═══════════════════════
def unused_field_eff(g, p, m):
    return any(e.kind in ('ignition', 'quick') and 'field' in e.zones and g.opt_ok(p, m, e) for e in m.effects)


def base_value(m):
    """원래 공격력 기준 가치 (cards.value와 같은 식 — 유니온 마스터 등 [지속] 증감은 남는 몬스터에도 붙으므로 빼고 비교)"""
    if not m.is_monster(): return 1.5
    return 1 + m.base_atk() / 1000 + (1.5 if m.level >= 8 else 0)


def fod_val(g, p, m):
    """코스트로 보낼 때 잃는 가치 (낮을수록 먼저): 원래 가치 + 아직 쓰지 않은 필드 기동 · 신속 효과 + 소환 절차가 필요한 보스. 상대 카드는 이득(음수)"""
    if m.controller != p: return -2 * value(g, m)
    v = base_value(m)
    if unused_field_eff(g, p, m): v += 0.8
    if m.flags.get('ss_self_only'): v += 2
    return v


def hand_prior(g, p, x):
    """패에 넣을 카드: 바로 나오는 플라이 · 이번 턴 패에서 특수소환할 수 있는 상급 · 아직 없는 지속 마법"""
    s = HAND_PRI.get(x.name, 10)
    if x.name == FLY and opt_free(g, p, FLY, 1): s += 30
    n = HT.get(x.name)
    if n is not None:
        if any(y.name == x.name for y in g.p[p].hand): s -= 20     # 같은 이름은 1턴에 1장만 패에서 특수소환
        elif not opt_free(g, p, x.name, n): s -= 10
    if x.name in (COLONY, LOADING) and any(y.name == x.name and y.faceup for y in g.spells(p)): s -= 30
    return s


def has_live_summon(g, p, x):
    return any(e.kind == 'summon' and g.opt_ok(p, x, e) for e in x.effects)


def stay_prior(g, p, x):
    """덱에서 특수소환해 필드에 둘 몬스터: 스스로 릴리스해 서치하는 캐터필러 · 코쿤, [소환]이 남은 리틀버그"""
    if x.name in (CATER, COCOON): return 50 if opt_free(g, p, x.name, 1) else 12
    if x.name == LITTLE: return 45 if (opt_free(g, p, LITTLE, 1) or opt_free(g, p, LITTLE, 2)) else 18
    return 10 * value(g, x) + (12 if has_live_summon(g, p, x) else 0)


def revive_prior(g, p, x):
    """묘지에서 특수소환할 몬스터: 가치 + 아직 쓰지 않은 [소환]"""
    s = 10 * value(g, x)
    if has_live_summon(g, p, x): s += 22
    if x.name in (CATER, COCOON) and opt_free(g, p, x.name, 1): s += 15
    return s


def colony_prior(g, p, x):
    """콜로니로 특수소환할 몬스터: 이 턴 효과를 쓸 수 없으므로 몸체 · 다음 턴의 [신속] · 대응"""
    return 10 * value(g, x) + (8 if any(e.kind in ('quick', 'resp') for e in x.effects) else 0)


def ready_hand(g, p, exclude=None):
    """이번 턴 패에서 특수소환 트리거를 아직 쓸 수 있는 카드 이름 수"""
    return len({x.name for x in g.p[p].hand if x is not exclude and x.name in HT and opt_free(g, p, x.name, HT[x.name])})


def pick(g, p, cands, why, prior):
    """후보 카드 중 하나를 고른다 (같은 이름은 하나로). 학습형 AI는 학습표(판단 「서치:why」, 사전값 = prior), 휴리스틱 AI는 prior 최대"""
    uniq = {}
    for x in cands: uniq.setdefault(x.name, x)
    xs = list(uniq.values())
    if not xs: return None
    if len(xs) == 1: return xs[0]
    ai = g.p[p].ai
    opts = [(x.name, float(prior(x)), x) for x in xs]
    if hasattr(ai, 'T') and hasattr(ai, 'choose'):
        return ai.choose(g, p, f'서치:{why}', opts, scale=30)
    opts.sort(key=lambda o: -o[1])
    note = getattr(ai, 'note', None)
    if note: note(g, p, why, [(n, s) for n, s, _ in opts], opts[0][0])
    return opts[0][2]


def fetch(g, p, pred, which=('main', 'upper'), why='서치', prior=None):
    """덱에서 패에 넣기 (Game.search와 같은 규칙 — 효과 주체와 같은 이름 제외 · 덱→패 금지), 고르기는 pick"""
    cs = g.search_cands(p, pred, which)
    if not cs: g.L(f'{why}: 대상 없음', 'sys'); return None
    x = pick(g, p, cs, why, prior or (lambda x: hand_prior(g, p, x)))
    g.L(f'{g.pname(p)} {why}: {x} 패에 넣음'); g.to_hand(x); g.shuffle(p)
    return x


def summon_pick(g, p, cands, why, prior, pos=None):
    x = pick(g, p, cands, why, prior)
    if x is None: g.L(f'{why}: 특수소환할 몬스터 없음', 'sys'); return None
    from_deck = x.zone in ('main', 'upper')
    ok = g.special_summon(x, p, pos)
    if from_deck: g.shuffle(p)
    return x if ok else None


def gy_mons(g, p): return [x for x in g.p[p].grave if DBM(x) and ss_ok(g, x, p)]


def revive(g, p, why):
    return summon_pick(g, p, gy_mons(g, p), why, lambda x: revive_prior(g, p, x))


def rel_pool(g, p, both=False):
    """코스트로 릴리스할 수 있는 「데이터버그」 몬스터 (자신 필드, both면 서로의 필드 — 상대 카드는 앞면만)"""
    out = [m for m in g.monsters(p) if DBM(m) and g.releasable(m) and leaves_ok(g, m)]
    if both: out += [m for m in g.monsters(1 - p) if DBM(m) and m.faceup and g.releasable(m) and leaves_ok(g, m)]
    return out


def cheapest(g, p, pool, n):
    return sorted(pool, key=lambda m: (fod_val(g, p, m), m.uid))[:n]


def pay_release(g, c, p, n, pool):
    xs = cheapest(g, p, pool, n)
    g.L(f'코스트: {", ".join(map(str, xs))} 릴리스')
    for m in xs: g.tribute(m, ('cost', c))
    return xs


def rel2_score(g, c, p, pool, gain):
    """「데이터버그」 몬스터 2장 릴리스 기동 효과의 점수: 얻는 것 − 12 × 잃는 가치. 몬스터 존이 가득 차 있으면 자리가 비는 이득"""
    if not main_ok(g, p): return 0
    xs = cheapest(g, p, pool, 2)
    if len(xs) < 2: return VETO
    s = gain - 12 * sum(fod_val(g, p, m) for m in xs)
    if not g.free_m(p) and ready_hand(g, p): s += 8
    return s


def ns_val(fn):
    """상급 몬스터의 제물 일반소환 가치 (ai.extra_summon_options 훅): 20 + 15 × [소환] 가치 − 12 × 제물 가치"""
    def f(g, p, ts, cost):
        v = fn(g, p, ts)
        return 20 + 15 * v - 12 * cost if v > 0 else VETO
    return f


# ═══════════════════════ 공통 효과 ═══════════════════════
def db_mon(c, effects, ns=None):
    """「데이터버그」 몬스터 공통: 콜로니로 특수소환된 그 턴에는 효과를 발동할 수 없다 (flags['no_act_until'], 필드를 벗어나면 지움)"""
    for e in effects:
        f = e.cond
        e.cond = (lambda g, x, p, ev, f=f: x.flags.get('no_act_until', -1) < g.turn and (f is None or f(g, x, p, ev)))
    c.effects = effects
    if ns is not None: c.ns_value = ns


def hand_ss_score(g, c, p, ev):
    """손패 트리거 점수. 「지금은 아님」은 음수(학습형 AI의 트리거 판단은 0점이 「발동」과 「안 함」의 동점)"""
    free = len(g.free_m(p))
    if free <= 0: return 40   # 공유 존에 놓을 수 있을 때만 발동 조건이 선다 (AI가 공유 존 사용을 허용 — 결착 · 패키지 프로그램 6장)
    v = value(g, c)
    better = {x.name for x in g.p[p].hand if x is not c and x.name != c.name and x.name in HT and opt_free(g, p, x.name, HT[x.name])
              and value(g, x) > v}
    if len(better) >= free: return -15   # 빈 자리는 더 강한 패의 데이터버그에게
    return 55 + 5 * v


def hand_ss(num, own=False):
    """[트리거] (자신) 필드에 「데이터버그」 몬스터가 소환되었을 때 발동. 패에서 이 카드를 특수소환한다"""
    def cond(g, c, p, ev): return c.zone == 'hand' and summoned_db(ev, p if own else None) and ss_ok(g, c, p)
    def res(g, c, p, l):
        if c.zone == 'hand' and ss_ok(g, c, p): g.special_summon(c, p)
        else: g.L(f'{c}: 패에서 특수소환할 수 없음', 'sys')
    return Effect(num, 'trigger', ('hand',), cond=cond, res=res, score=hand_ss_score, threat=300,
                  label=f'[트리거] {"자신 " if own else ""}필드에 데이터버그 소환 → 패에서 특수소환')


def summon_revive(num):
    """[소환] 묘지에서 「데이터버그」 몬스터 1장을 특수소환한다 (웜 2 · 쌍살벌 1)"""
    return Effect(num, 'summon', ('field',), cond=lambda g, c, p, ev: summoned_self(g, c, ev) and bool(gy_mons(g, p)),
                  res=lambda g, c, p, l: revive(g, p, f'{c.name} {num}번'), score=lambda *a: 75, threat=600,
                  label='[소환] 묘지의 「데이터버그」 몬스터 특수소환')


def negate_resp(num, destroy=False, activation=False, gate=600):
    """[트리거] 상대가 (카드의) 효과를 발동했을 때 발동. 그 효과/발동을 무효로 한다 (destroy: 무효로 하고 파괴)"""
    def res(g, c, p, l):
        t = l.ctx['t']; g.negate(t, destroy=destroy, by=c)
        x = t.card
        if activation and t.negated and t.eff.spell_act and g.on_field(x) and x.is_spell_like() and x.d.get('subtype') not in ('일반', '신속', '트리거'):
            g.L(f'{x}의 발동 무효 → 묘지로', 'sys'); g.send_grave(x, ('rule', None))
    return Effect(num, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None,
                  cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res,
                  score=lambda g, c, p, ev: (65 if destroy else 60) if threat(g, p) >= gate else 0, threat=900 if destroy else 800,
                  label='상대 발동 무효' + (' + 파괴' if destroy else ''))


def nomi(c, num=1):
    """[제약] 「이 카드는 다른 카드의 효과로 소환할 수 없다. 자신 필드의 몬스터를 3장 묘지로 보내야만 패에서 특수소환할 수 있다」 — 소환 절차"""
    c.flags.update(ss_self_only=True, no_normal=True)
    def pool(g, p): return [m for m in g.monsters(p) if leaves_ok(g, m) and not m.flags.get('immune_others')]
    def cond(g, c, p, ev): return c.zone == 'hand' and len(pool(g, p)) >= 3 and not g.rule('no_special', c, p)
    def cost(g, c, p, l):
        xs = cheapest(g, p, pool(g, p), 3)
        g.L(f'코스트: {", ".join(map(str, xs))} 묘지로')
        for m in xs: g.send_grave(m, ('cost', c))
    def res(g, c, p, l):
        if c.zone == 'hand' and g.can_special(c, p): g.special_summon(c, p)
        else: g.L(f'{c}: 특수소환할 수 없음', 'sys')
    def sc(g, c, p, ev):
        if not main_ok(g, p): return 0
        xs = cheapest(g, p, pool(g, p), 3)
        return 25 + 15 * value(g, c) - 12 * sum(fod_val(g, p, m) for m in xs)
    e = Effect(num, 'ignition', ('hand',), opt=None, cond=cond, cost=cost, res=res, score=sc, threat=0,
               label='자신 필드의 몬스터 3장 묘지로 → 패에서 특수소환 (소환 절차)')
    e.no_resp = True; e.unnegatable = True; e.procedure = True
    return e


# ═══════════════════════ 메인 덱 몬스터 ═══════════════════════
def self_release(c):
    def cond(g, c, p, ev): return g.releasable(c) and leaves_ok(g, c)
    def cost(g, c, p, l): g.L(f'코스트: {c} 릴리스'); g.tribute(c, ('cost', c))
    return cond, cost


@card(CATER)
def _(c):
    rc, cost1 = self_release(c)
    def res1(g, c, p, l):
        for _ in range(2): fetch(g, p, DBC, why=f'{c.name} 1번')
    db_mon(c, [
        Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: rc(g, c, p, ev) and g.can_search(p, DBC), cost=cost1, res=res1,
               score=lambda g, c, p, ev: 65, threat=500, label='자신 릴리스 → 「데이터버그」 카드 2장 서치'),
        hand_ss(2)])


@card(FLY)
def _(c):
    def added(g, c, p, ev):
        if not isinstance(ev, dict) or ev.get('card') is not c: return False
        k = ev.get('kind')
        if k == 'added_to_hand': return ev['player'] == p
        if k == 'draw': return ev['player'] == p and ev.get('turn', 0) >= 1   # 라운드 시작 패 · 멀리건은 제외
        if k == 'leave_field': return ev.get('dest') == 'hand'
        return False
    def cond1(g, c, p, ev):
        return c.zone == 'hand' and c in g.p[p].hand and added(g, c, p, ev) and (ss_ok(g, c, p) or g.can_search(p, DBS))
    def res1(g, c, p, l):
        if c.zone == 'hand' and ss_ok(g, c, p): g.special_summon(c, p)
        else: g.L(f'{c}: 특수소환할 수 없음 — 서치만 처리', 'sys')
        fetch(g, p, DBS, why=f'{c.name} 1번')
    e2 = hand_ss(2)
    def sc2(g, c, p, ev):
        # 같은 사건 묶음에 「패에 넣어짐」이 있고 1번을 아직 쓸 수 있으면 특수소환은 1번(+ 마법 서치)에 맡긴다
        if opt_free(g, p, FLY, 1) and any(added(g, c, p, x) for x in getattr(g, 'cur_evs', [])): return -15
        return hand_ss_score(g, c, p, ev)
    e2.score = sc2
    db_mon(c, [
        Effect(1, 'trigger', ('hand',), cond=cond1, res=res1, score=lambda *a: 85, threat=500,
               label='[트리거] 패에 넣어짐 → 자신 특수소환 + 「데이터버그」 마법 서치'),
        e2])


@card(LITTLE)
def _(c):
    def mains(g, p): return [x for x in g.p[p].main if DBM(x) and ss_ok(g, x, p)]
    db_mon(c, [
        Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: summoned_self(g, c, ev) and bool(mains(g, p)),
               res=lambda g, c, p, l: summon_pick(g, p, mains(g, p), f'{c.name} 1번', lambda x: stay_prior(g, p, x)),
               score=lambda *a: 80, threat=600, label='[소환] 메인 덱 「데이터버그」 몬스터 특수소환'),
        Effect(2, 'trigger', ('field',), cond=lambda g, c, p, ev: summoned_db(ev) and g.can_search(p, DBM),
               res=lambda g, c, p, l: fetch(g, p, DBM, why=f'{c.name} 2번'), score=lambda *a: 70, threat=400,
               label='[트리거] 데이터버그 소환 → 「데이터버그」 몬스터 서치'),
        hand_ss(3)])


def return_and_fetch(num, which, pred, label, sc):
    """[트리거] 「데이터버그」 몬스터가 필드에 소환되었을 때 발동. 패의 이 카드를 덱으로 되돌리고, … 1장을 패에 넣는다 (코쿤 · 에볼루션 2번)"""
    def cond(g, c, p, ev): return c.zone == 'hand' and summoned_db(ev) and g.can_search(p, pred, which)
    def res(g, c, p, l):
        if c.zone != 'hand': g.L(f'{c}이(가) 패에 없음 — 처리 없음', 'sys'); return
        g.to_deck(c); g.L(f'패의 {c} 덱으로')
        fetch(g, p, pred, which, why=f'{c.name} {num}번')
    return Effect(num, 'trigger', ('hand',), cond=cond, res=res, score=sc, threat=200, label=label)


def swap_score(g, c, p, ev):
    """코쿤 · 에볼루션 2번: 이번 턴 이 카드를 일반소환할 수 있으면 남겨 둔다"""
    if own_turn(g, p) and g.phase in ('준비', '진행') and g.can_normal(p, c): return 12
    return 30


@card(COCOON)
def _(c):
    rc, cost1 = self_release(c)
    UP = lambda x: DBC(x)
    def res1(g, c, p, l):
        for _ in range(2): fetch(g, p, UP, ('upper',), why=f'{c.name} 1번')
    db_mon(c, [
        Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: rc(g, c, p, ev) and g.can_search(p, UP, ('upper',)), cost=cost1, res=res1,
               score=lambda g, c, p, ev: 65, threat=500, label='자신 릴리스 → 상급 덱 「데이터버그」 카드 2장 서치'),
        return_and_fetch(2, ('upper',), UP, '[트리거] 데이터버그 소환 → 패의 이 카드를 덱으로, 상급 덱 「데이터버그」 카드 서치', swap_score)])


@card(EVO)
def _(c):
    def pool(g, p): return rel_pool(g, p)
    db_mon(c, [
        Effect(1, 'ignition', ('field',), opt=None, cond=lambda g, c, p, ev: len(pool(g, p)) >= 2 and g.can_search(p, DBM),
               cost=lambda g, c, p, l: pay_release(g, c, p, 2, pool(g, p)) and None,
               res=lambda g, c, p, l: fetch(g, p, DBM, why=f'{c.name} 1번'),
               score=lambda g, c, p, ev: rel2_score(g, c, p, pool(g, p), 40), threat=400,
               label='데이터버그 2장 릴리스 → 「데이터버그」 몬스터 서치 (횟수 제한 없음)'),
        return_and_fetch(2, ('main', 'upper'), DBM, '[트리거] 데이터버그 소환 → 패의 이 카드를 덱으로, 「데이터버그」 몬스터 서치', swap_score)])


# ═══════════════════════ 상급 덱 몬스터 ═══════════════════════
@card(ANT)
def _(c):
    def ants(g, p): return [x for x in g.deck_cards(p) if x.name == ANT and ss_ok(g, x, p)]
    def res2(g, c, p, l):
        n = 0
        for _ in range(3):   # 「가능한 만큼」 (같은 이름 최대 3장)
            cs = ants(g, p)
            if not cs or not g.special_summon(cs[0], p): break
            n += 1
        g.shuffle(p); g.L(f'덱에서 「{ANT}」 {n}장 특수소환')
    def sc1(g, c, p, ev):
        if not main_ok(g, p): return 0
        return 25 if not opt_free(g, p, ANT, 3) else 10   # 이번 턴 패에서 나올 수 없으면 서치로 바꾼다
    db_mon(c, [
        Effect(1, 'ignition', ('hand',), cond=lambda g, c, p, ev: g.can_search(p, DBM, ('upper',)),
               cost=lambda g, c, p, l: (g.L(f'코스트: 패의 {c} 버림'), g.send_grave(c, ('cost', c))) and None,
               res=lambda g, c, p, l: fetch(g, p, DBM, ('upper',), why=f'{c.name} 1번'), score=sc1, threat=300,
               label='패에서 버림 → 상급 덱 「데이터버그」 몬스터 서치'),
        Effect(2, 'summon', ('field',), cond=lambda g, c, p, ev: summoned_self(g, c, ev) and bool(ants(g, p)), res=res2,
               score=lambda *a: 80, threat=700, label='[소환] 덱에서 「데이터버그 앤트」를 가능한 만큼 특수소환'),
        hand_ss(3)],
        ns=ns_val(lambda g, p, ts: 1.2 * min(2, len(ants(g, p))) if opt_free(g, p, ANT, 2) else 0))


@card(HERC)
def _(c):
    def res1(g, c, p, l):
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.destroy(t)
        else: g.L('파괴할 상대 카드 없음', 'sys')
        g.damage(1 - p, 1000, c.name)
        if g.on_field(c): c.extra_attacks += 1; g.L(f'{c} 이어서 공격할 수 있음')
    db_mon(c, [
        Effect(1, 'battle', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['card'] is c, res=res1,
               score=lambda *a: 90, threat=1000, label='[전투] 상대 카드 1장 파괴 + 1000 대미지 + 이어서 공격'),
        hand_ss(2)])


@card(WORM)
def _(c):
    def tcands(g, p): return targets(g, p, [m for m in g.monsters(p) + g.monsters(1 - p) if DBM(m) and m.faceup])
    def mains(g, p): return [x for x in g.p[p].main if DBM(x) and not x.flags.get('ss_self_only') and not g.rule('no_special', x, p)]
    def cond1(g, c, p, ev):
        ts = tcands(g, p)
        return c.zone == 'hand' and bool(ts) and bool(mains(g, p)) and (bool(g.free_m(p)) or any(m.controller == p and m.zone == 'm' for m in ts))
    def tpick(g, p):
        ts = tcands(g, p)
        th = [m for m in ts if m in threatened(g, p)]
        if th: return max(th, key=lambda m: value(g, m))                    # 상대 효과의 대상이 된 자신 몬스터 (어차피 잃는 카드)
        opp = [m for m in ts if m.controller != p]
        if opp and max(value(g, m) for m in opp) >= 1.8: return best(g, opp, p)
        own = [m for m in ts if m.controller == p]
        if own: return min(own, key=lambda m: fod_val(g, p, m))
        return best(g, opp, p)
    def cost1(g, c, p, l):
        t = tpick(g, p); l.ctx['t'] = t
        g.L(f'코스트: 패의 {c} 버림 · 대상 {t}'); g.send_grave(c, ('cost', c))
    def res1(g, c, p, l):   # 앞 효과(묘지로)를 처리해야 뒤 효과(특수소환)도 처리한다 (사용자 답변 2026-10-17 — 재정 데이터버그 8)
        t = l.ctx.get('t')
        if t is None or not g.on_field(t): g.L(f'{c.name} 1번: 대상 없음 — 특수소환도 하지 않음', 'sys'); return
        g.L(f'{t} 묘지로'); g.send_grave(t)
        if g.on_field(t): return
        summon_pick(g, p, [x for x in g.p[p].main if DBM(x) and ss_ok(g, x, p)], f'{c.name} 1번', lambda x: stay_prior(g, p, x))
    def sc1(g, c, p, ev):
        ts = tcands(g, p)
        if any(lk.card is c for lk in g.chain): return 0   # 이 카드의 패에서 특수소환이 처리 대기 중
        if any(m in threatened(g, p) for m in ts): return 50
        opp = [m for m in ts if m.controller != p]
        if opp:
            v = max(value(g, m) for m in opp)
            if v >= 1.8 and (main_ok(g, p) or threat(g, p) >= 700): return 25 + 15 * v
        if main_ok(g, p):
            own = [m for m in ts if m.controller == p]
            if own:   # 덱에서의 특수소환도 「데이터버그」 소환 — 패의 트리거 몬스터가 연쇄로 나온다
                v = 28 + 15 * ready_hand(g, p, c) - 12 * max(0.0, min(fod_val(g, p, m) for m in own) - 1.4)
                return v if v > 0 else 0
        return 0
    db_mon(c, [
        Effect(1, 'quick', ('hand',), cond=cond1, cost=cost1, res=res1, score=sc1, threat=600,
               label='패에서 버리고 데이터버그 1장 대상 → 그 몬스터 묘지로 + 메인 덱 「데이터버그」 몬스터 특수소환'),
        summon_revive(2), hand_ss(3)],
        ns=ns_val(lambda g, p, ts: 1.0 + 0.04 * max([revive_prior(g, p, x) for x in gy_mons(g, p) + [t for t in ts if DBM(t)]] or [0])
                  if gy_mons(g, p) or any(DBM(t) for t in ts) else 0))


@card(QUEEN)
def _(c):
    def pool(g, p): return rel_pool(g, p)
    db_mon(c, [
        Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: summoned_self(g, c, ev) and g.can_search(p, DBM),
               res=lambda g, c, p, l: fetch(g, p, DBM, why=f'{c.name} 1번'), score=lambda *a: 80, threat=400,
               label='[소환] 「데이터버그」 몬스터 서치'),
        Effect(2, 'ignition', ('field',), cond=lambda g, c, p, ev: len(pool(g, p)) >= 2 and g.can_search(p, DBS),
               cost=lambda g, c, p, l: pay_release(g, c, p, 2, pool(g, p)) and None,
               res=lambda g, c, p, l: fetch(g, p, DBS, why=f'{c.name} 2번'),
               score=lambda g, c, p, ev: rel2_score(g, c, p, pool(g, p), 35), threat=300,
               label='데이터버그 2장 릴리스 → 「데이터버그」 마법 서치'),
        hand_ss(3, own=True)],
        ns=ns_val(lambda g, p, ts: 1.5 if g.can_search(p, DBM, source=c) and opt_free(g, p, QUEEN, 1) else 0))


@card(UNION)
def _(c):
    def pool(g, p): return rel_pool(g, p)
    def am(g, src, x):   # 2번 [지속]: 자신 필드의 몬스터 공격력 +100 × 자신 필드의 (앞면) 「데이터버그」 카드 수
        q = src.controller
        if x.controller != q or not x.is_monster() or not g.on_field(x) or not x.faceup: return 0
        return 100 * sum(1 for y in g.field_cards(q) if y.faceup and DBC(y))
    c.atk_mod = am
    c.cont_nums = {'atk_mod': 2}   # 2번 [지속] 공격력 증감 — 텍스트에 턴 제한이 없어 횟수 없이 늘 적용 (Game.cont_num, 사용자 지시 2026-10-22)
    def sc1(g, c, p, ev):
        ps = pool(g, p)
        xs = cheapest(g, p, ps, 2)
        cand = [x for x in gy_mons(g, p)] + [x for x in xs if not x.flags.get('ss_self_only')]
        if not cand: return VETO
        return rel2_score(g, c, p, ps, 0.7 * max(revive_prior(g, p, x) for x in cand) + 15 * ready_hand(g, p))   # 소생도 「데이터버그」 소환 → 패 트리거
    db_mon(c, [
        Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: len(pool(g, p)) >= 2,
               cost=lambda g, c, p, l: pay_release(g, c, p, 2, pool(g, p)) and None,
               res=lambda g, c, p, l: revive(g, p, f'{c.name} 1번'), score=sc1, threat=500,
               label='데이터버그 2장 릴리스 → 묘지의 「데이터버그」 몬스터 특수소환'),
        hand_ss(3, own=True)])


@card(BUTTER)
def _(c):
    # 2번 [지속] 「상대는 덱에서 패에 카드를 넣을 수 없다」(2026-10-22 텍스트) — 상대 플레이어에게 거는 금지라 횟수 제한 없이,
    # 상대는 덱에서 패에 넣는 효과를 발동할 수 없다(Game.search_cands · to_hand)
    c.rules = {'no_deck_to_hand': lambda g, src, pl: pl == 1 - src.controller}
    c.cont_nums = {'rule:no_deck_to_hand': 2}
    db_mon(c, [negate_resp(1), hand_ss(3)])


@card(DWORM)
def _(c):
    def opp_t(g, p): return targets(g, p, opp_cards(g, p))
    def res1(g, c, p, l):
        t = best(g, opp_t(g, p), p)
        if t: g.destroy(t)
    def sc1(g, c, p, ev):
        ts = opp_t(g, p)
        if not ts: return VETO
        v = max(value(g, x) for x in ts)
        if main_ok(g, p): return 30 + 15 * v
        if threat(g, p) >= 700: return 55
        if not own_turn(g, p) and not g.chain and g.phase in ('전투', '종료'): return 25 + 10 * v   # 1턴 1번 — 상대 턴에 쓰고 자신 턴에 다시
        return 0
    def fod2(g, c, p): return [x for x in g.field_cards(p) if DBC(x) and x.faceup and leaves_ok(g, x)]
    def fpick(g, c, p):
        xs = fod2(g, c, p)
        return min(xs, key=lambda x: (x is c, fod_val(g, p, x) if x.is_monster() else value(g, x) + 1.0))
    def res2(g, c, p, l):
        xs = fod2(g, c, p)
        if xs:
            x = fpick(g, c, p); g.L(f'{x} 묘지로'); g.send_grave(x)
        t = field_pick(g, p, 'remove', targets(g, p, [y for y in g.all_field() if g.on_field(y)]))
        if t: g.destroy(t)
    def sc2(g, c, p, ev):
        ts = opp_t(g, p)
        if not ts or not fod2(g, c, p): return VETO
        x = fpick(g, c, p)
        loss = fod_val(g, p, x) if x.is_monster() else value(g, x) + 1.0
        base = 20 + 15 * max(value(g, y) for y in ts) - 12 * loss
        if main_ok(g, p): return base
        return base if threat(g, p) >= 900 else 0
    db_mon(c, [
        Effect(1, 'quick', ('field',), cond=lambda g, c, p, ev: bool(opp_t(g, p)), res=res1, score=sc1, threat=1000, label='상대 카드 1장 파괴'),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: bool(fod2(g, c, p)) and bool(targets(g, p, g.all_field())), res=res2, score=sc2,
               threat=900, label='자신의 데이터버그 1장 묘지로 → 필드의 카드 1장 파괴'),
        hand_ss(3)])


def summon_negater(e):
    """소환 무효 효과 표시: Game.triggers가 그 소환의 [소환] 효과보다 먼저 묻고, 무효로 했으면 [소환]은 묻지 않는다 (설계도 확정 2026-10-10)"""
    e.summon_negate = True
    return e


@card(VIRUS)
def _(c):
    def cond2(g, c, p, ev):
        if not (ev_is(ev, 'summon') and ev['player'] == 1 - p): return False
        x = ev['card']
        return g.on_field(x) and x.controller == 1 - p
    def res2(g, c, p, l):
        x = l.ctx['ev']['card']
        l.ctx['ev']['negated'] = True   # 소환 무효 — 그 소환의 [소환] 효과는 묻지 않는다 (Game.triggers)
        g.L(f'{x}의 소환 무효')
        for lk in g.chain:   # 그 소환으로 체인에 올라 아직 처리되지 않은 그 몬스터의 [소환] 효과는 처리하지 않는다 (소환 무효 근사, 사용 횟수 반환)
            e2 = lk.ctx.get('ev')
            if lk.card is x and lk.eff.kind == 'summon' and not lk.negated and isinstance(e2, dict) and e2.get('kind') == 'summon' and e2.get('card') is x:
                lk.negated = True
                for k in lk.ctx.get('opt_keys', []):
                    if g.p[lk.player].opt.get(k): g.p[lk.player].opt[k] -= 1
                g.L(f'  소환이 무효 — {x}의 {lk.eff.num}번 [소환] 효과는 처리되지 않음', 'sys')
        if g.on_field(x) and x.controller == 1 - p: g.destroy(x)
    def sc2(g, c, p, ev):
        x = ev.get('card') if isinstance(ev, dict) else None
        if x is None: return 0
        v = value(g, x)
        live = any(lk.card is x and lk.eff.kind == 'summon' for lk in g.chain) or has_live_summon(g, 1 - p, x)
        if v < 1.4 and not live: return 10
        return 15 + 20 * v + (20 if live else 0)
    db_mon(c, [
        nomi(c),
        summon_negater(Effect(2, 'trigger', ('field',), cond=cond2, res=res2, score=sc2, threat=1000, label='[트리거] 상대 소환 무효 + 파괴')),
        negate_resp(3, destroy=True, gate=500)])


@card(DELETE)
def _(c):
    c.rules = {'no_deck_to_hand': lambda g, src, pl: pl == 1 - src.controller}   # 3번 [지속] (단서 있음 — 횟수 제한 없음)
    def pool(g, c): return targets(g, c.controller, [x for x in g.all_field() if x is not c])
    def cond2(g, c, p, ev):
        return ev_is(ev, 'destroyed') and ev['card'].type == '몬스터' and bool(pool(g, c))
    def res2(g, c, p, l):
        t = field_pick(g, p, 'remove', [x for x in pool(g, c) if g.on_field(x)])
        if t: g.destroy(t)
    db_mon(c, [
        nomi(c),
        Effect(2, 'trigger', ('field',), cond=cond2, res=res2,
               score=lambda g, c, p, ev: (60 + 10 * max(value(g, x) for x in targets(g, p, opp_cards(g, p)))) if targets(g, p, opp_cards(g, p)) else VETO,
               threat=900, label='[트리거] 몬스터 파괴 → 필드의 카드 1장 파괴')])


@card(WASP)
def _(c):
    db_mon(c, [summon_revive(1), negate_resp(2, activation=True), hand_ss(3)],
           ns=ns_val(lambda g, p, ts: 0.04 * max([revive_prior(g, p, x) for x in gy_mons(g, p) + [t for t in ts if DBM(t)]] or [0])))


# ═══════════════════════ 마법 ═══════════════════════
@card(LOADING)
def _(c):
    UPM = lambda x: DBM(x)
    def res0(g, c, p, l):
        if opt_free(g, p, LOADING, 1):   # 1번: 발동했을 때 처리 (발동 선언 불필요, 1턴에 1번)
            use_opt(g, p, LOADING, 1); fetch(g, p, UPM, ('upper',), why=f'{c.name} 1번')
        else: g.L(f'{c.name} 1번: 이 턴에 이미 처리함', 'sys')
    def sc0(g, c, p, ev):
        can = opt_free(g, p, LOADING, 1) and g.can_search(p, UPM, ('upper',), source=c)
        if any(y.name == c.name and y.faceup for y in g.spells(p)): return 30 if can else VETO   # 2장째: 1번 서치만 (2번은 이름당 1턴 1번)
        return 50 if can else 30
    def pool(g, p): return rel_pool(g, p, both=cost_opp(c, 2))   # 2번 코스트 「필드에서」 = 자신 필드 (Q41)
    c.effects = [
        Effect(0, 'ignition', ('hand', 'field'), spell_act=True, res=res0, score=sc0, threat=300, opt=None,   # 카드의 발동 자체는 1턴 1번이 아니다 (1번 서치만)
               label='발동 + 상급 덱 「데이터버그」 몬스터 서치'),
        Effect(2, 'ignition', ('field',), cond=lambda g, c, p, ev: len(pool(g, p)) >= 2 and g.can_search(p, DBM),
               cost=lambda g, c, p, l: pay_release(g, c, p, 2, pool(g, p)) and None,
               res=lambda g, c, p, l: fetch(g, p, DBM, why=f'{c.name} 2번'),
               score=lambda g, c, p, ev: rel2_score(g, c, p, pool(g, p), 40), threat=300,
               label='필드의 데이터버그 2장 릴리스 → 「데이터버그」 몬스터 서치')]


@card(BACKUP)
def _(c):
    def tg(g, p): return targets(g, p, [m for m in g.monsters(p) if DBM(m) and m.faceup])
    def gain(g, p, m):
        s = 0
        if not g.rule('no_deck_to_hand', p) and any(x.name == m.name for x in g.deck_cards(p)): s += 30
        if m.flags.get('ss_self_only'): return s - 10 * value(g, m)   # 다시 특수소환할 수 없다 — 잃는다
        if has_live_summon(g, p, m): s += 22
        return s + 5 * ready_hand(g, p)
    def cost(g, c, p, l):
        l.ctx['t'] = max(tg(g, p), key=lambda m: (gain(g, p, m), -value(g, m))); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if not (t and g.on_field(t) and t.controller == p): g.L('대상이 자신 필드에 없음 — 처리 없음', 'sys'); return
        g.L(f'{t} 묘지로'); g.send_grave(t)
        if t.zone != 'grave': g.L(f'{t}이(가) 묘지로 가지 않음 — 이후 처리 없음', 'sys'); return
        name = t.name
        fetch(g, p, lambda x: x.name == name, why=f'{c.name} 동일한 이름')
        if ss_ok(g, t, p): g.special_summon(t, p)
        else: g.L(f'{t}: 특수소환할 수 없음', 'sys')
    def sc(g, c, p, ev):
        if not main_ok(g, p): return 0
        ts = tg(g, p)
        return 15 + max(gain(g, p, m) for m in ts) if ts else VETO
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(tg(g, p)), cost=cost, res=res,
                        score=sc, threat=500, label='데이터버그 1장 대상 → 묘지로 · 같은 이름 서치 · 다시 특수소환')]


@card(DOWNLOAD)
def _(c):
    def mains(g, p): return [x for x in g.p[p].main if DBM(x) and ss_ok(g, x, p)]
    def res(g, c, p, l):
        x = summon_pick(g, p, mains(g, p), f'{c.name}', lambda x: GRAVE_PRI.get(x.name, 10), pos='def')
        if x is not None and g.on_field(x): g.L(f'그 후, {x} 묘지로'); g.send_grave(x)
    def sc(g, c, p, ev):
        if not main_ok(g, p): return 0
        return 14 + 10 * ready_hand(g, p)
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(mains(g, p)), res=res,
                        score=sc, threat=400, label='메인 덱 「데이터버그」 몬스터 특수소환 → 그 후 묘지로')]


@card(AROMA)
def _(c):
    def plan(g, c, p):
        """(점수, 버릴 카드): 이번 턴 패에서 나올 수 없는 「데이터버그」 상급을 버리고 되살리는 것까지 고려"""
        gb = max([revive_prior(g, p, x) for x in gy_mons(g, p)] or [0])
        out = None
        for h in g.p[p].hand:
            if h is c: continue
            keep = g.p[p].ai.card_pri(g, p, h) + (8 if h.name in HT and opt_free(g, p, h.name, HT[h.name]) else 0)
            rv = gb
            if DBM(h) and not h.flags.get('ss_self_only') and not g.rule('no_special', h, p): rv = max(rv, revive_prior(g, p, h))
            if out is None or rv - keep > out[0]: out = (rv - keep, rv, h)
        return out
    def cond(g, c, p, ev):
        pl = plan(g, c, p)
        return pl is not None and pl[1] > 0
    def res(g, c, p, l):
        pl = plan(g, c, p)
        if pl is not None:
            h = pl[2]; g.L(f'패의 {h} 버림'); g.send_grave(h)
        revive(g, p, f'{c.name}')
    def sc(g, c, p, ev):
        if not main_ok(g, p): return 0
        pl = plan(g, c, p)
        return 10 + 0.5 * pl[0] if pl else VETO   # 되살릴 가치 − 버리는 카드의 가치
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=cond, res=res, score=sc, threat=500,
                        label='패 1장 버림 → 묘지의 「데이터버그」 몬스터 특수소환')]


@card(RAID)
def _(c):
    def pool(g, p):   # 코스트 「필드의 「데이터버그」 몬스터」 = 자신 필드 (Q41 — 문장에 「서로」 · 「상대」가 있을 때만 상대 필드, cards.cost_opp)
        # 자신의 뒷면 몬스터도 쓸 수 있다(대상 지정이 아닌 효과 — 사용자 답변 2026-10-22 Q45, rel_pool과 같음), 상대 카드는 앞면만
        return [m for m in g.monsters(p) + (g.monsters(1 - p, faceup_only=True) if cost_opp(c, 1) else []) if DBM(m) and leaves_ok(g, m)]
    def opp_t(g, p): return targets(g, p, opp_cards(g, p))
    def plan(g, p):
        """코스트 2장: 잃는 가치 합이 가장 작은 2장 — 단 파괴할 상대 카드가 1장 이상 남도록"""
        ts = opp_t(g, p); ps = pool(g, p); out = None
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                pr = (ps[i], ps[j])
                if not any(t not in pr for t in ts): continue
                k = fod_val(g, p, ps[i]) + fod_val(g, p, ps[j])
                if out is None or k < out[0]: out = (k, pr)
        return list(out[1]) if out else None
    def cost(g, c, p, l):
        xs = plan(g, p)
        g.L(f'코스트: {", ".join(map(str, xs))} 묘지로')
        for m in xs: g.send_grave(m, ('cost', c))
    def res(g, c, p, l):
        t = best(g, opp_t(g, p), p)   # 「고르고」: 처리 시 고른다
        if t is None or not g.destroy(t): g.L('상대 카드를 파괴하지 못함 — 특수소환 없음', 'sys'); return
        for _ in range(2):
            if not revive(g, p, f'{c.name}'): break
    def sc(g, c, p, ev):
        xs = plan(g, p)
        ts = [t for t in opp_t(g, p) if xs is None or t not in xs]
        if not ts or not xs: return VETO
        base = 40 + 15 * max(value(g, x) for x in ts) - 8 * sum(fod_val(g, p, m) for m in xs)
        if main_ok(g, p): return base
        if any(m in threatened(g, p) for m in pool(g, p)): return base + 15
        return base if threat(g, p) >= 800 else 0
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: plan(g, p) is not None,
                        cost=cost, res=res, score=sc, threat=1000, label='데이터버그 2장 묘지로 → 상대 카드 파괴 → 묘지에서 2장 특수소환')]


@card(REVENGE)
def _(c):
    def cond(g, c, p, ev):
        if not (ev_is(ev, 'leave_field') and ev['ctrl'] == p and ev['prev'] in FIELD_M and DBM(ev['card'])): return False
        ca = ev.get('cause') or ('', None)
        return ca[0] in ('effect', 'cost') and ca[1] is not None and ca[1].controller != p
    def res(g, c, p, l):
        for t in [x for x in g.all_field() if x is not c]:
            if g.on_field(t): g.destroy(t)
        revive(g, p, f'{c.name}')
    def sc(g, c, p, ev):
        d = sum(value(g, x) for x in g.field_cards(1 - p)) - sum(value(g, x) for x in g.field_cards(p) if x is not c)
        rv = max([revive_prior(g, p, x) for x in gy_mons(g, p)] + [0])
        s = 20 + 15 * d + 0.3 * rv
        return s if d > -1 and s > 0 else VETO
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True, cond=cond, res=res, score=sc, threat=1200,
                        label='데이터버그가 상대 효과로 필드를 벗어남 → 필드 전부 파괴 + 묘지에서 1장 특수소환')]


@card(COLONY)
def _(c):
    def own_db(g, p): return any(DBM(m) and m.faceup for m in g.monsters(p))
    def cands(g, p): return [x for x in g.deck_cards(p) if DBM(x) and ss_ok(g, x, p)]
    def res1(g, c, p, l):
        if not own_db(g, p): g.L('자신 필드에 「데이터버그」 몬스터 없음 — 처리 없음', 'sys'); return
        x = summon_pick(g, p, cands(g, p), f'{c.name}', lambda x: colony_prior(g, p, x))
        if x is not None and g.on_field(x):
            col = x.flags.get('clear_on_leave') or {}
            col.setdefault('no_act_until', x.flags.get('no_act_until'))
            x.flags['clear_on_leave'] = col; x.flags['no_act_until'] = g.turn
            g.L(f'{x}은(는) 이 턴에 효과를 발동할 수 없음')
    def sc0(g, c, p, ev):
        if any(y.name == c.name and y.faceup for y in g.spells(p)): return VETO   # 1번은 이름당 1턴 1번 — 2장째로 얻는 것 없음
        return 55 if own_db(g, p) else 35
    c.effects = [
        Effect(0, 'ignition', ('hand', 'field'), spell_act=True, score=sc0, threat=400, label='발동'),
        Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: own_db(g, p) and bool(cands(g, p)), res=res1,
               score=lambda g, c, p, ev: 70 if main_ok(g, p) else 0, threat=600,
               label='덱에서 「데이터버그」 몬스터 특수소환 (그 몬스터는 이 턴 효과 발동 불가)')]


# ═══════════════════════ 스킬 ═══════════════════════
@card(SKILL)
def _(c):
    def n_db(g, p): return sum(1 for m in g.monsters(p) if DBM(m))
    c.extra_normal = lambda g, src, p, x: 1 if p == src.controller and src.flags.get('pkg_turn') == g.turn else 0
    def res(g, c, p, l):
        c.flags['pkg_turn'] = g.turn; g.L(f'이 턴 {g.pname(p)}은(는) 한 번 더 일반소환할 수 있음')
    def summonable(g, p):
        """6장이면 자리가 없어 추가 일반소환은 제물 소환뿐 — 패의 레벨 5 이상 일반소환 가능 몬스터"""
        return [x for x in g.p[p].hand if x.type == '몬스터' and not x.flags.get('no_normal') and not x.flags.get('effect_only') and x.level >= 5]
    def sc(g, c, p, ev):
        if not main_ok(g, p): return 0
        return 75 if g.phase == '진행' and summonable(g, p) else 5
    def wants_shared(g, p, x):
        """ai.use_shared 훅: 이 몬스터로 「데이터버그」 몬스터 6장이 되고, 스킬을 아직 쓰지 않았고, 일반소환할 몬스터가 패에 있을 때"""
        sk = g.p[p].skill
        if sk is None or sk.name != SKILL or sk.negated or not DBM(x): return None
        if not (own_turn(g, p) and g.phase == '진행') or not g.opt_ok(p, sk, sk.effects[0]): return None
        if n_db(g, p) != 5 or not any(y is not x for y in summonable(g, p)): return None
        return f'{SKILL} 조건(「데이터버그」 몬스터 6장)'
    c.wants_shared = wants_shared
    c.effects = [Effect(1, 'ignition', ('skill',), cond=lambda g, c, p, ev: n_db(g, p) >= 6, res=res, score=sc, threat=200,
                        label='「데이터버그」 몬스터 6장 → 이 턴 일반소환 1회 추가')]
