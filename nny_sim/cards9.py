"""카드 구현 9차: 던전마스터 18종 (카드 자료 2026-10-08, DGMS-001~018)
던전의 주인이 함정과 몬스터를 배치하는 테마 — 「트랩」(뒷면 운용 · 함정 마법) · 「다크」(파괴 · 전투 압박) · 「던전마스터」(자색 보스 3종의 지속 락).
상급 보스들은 [유언] 「상대는 카드를 1장 드로우한다」(강제)를 안고 있고, 「암흑의 율법」 1번이 그것을 「덱으로 되돌리고 「던전마스터」 카드 서치」로 바꾼다.
스킬 「던전마스터 셔플!」은 뒷면 카드끼리 자리를 섞어(양쪽 필드 사이 맞바꾸기, 1번), 뒷면 몬스터를 앞면으로 뒤집고(2번),
패의 레벨 5 이상 몬스터를 특수소환한다(3번). 트랩퍼 2번 · 트랩: 깜짝상자가 「자신 카드 + 상대 카드」를 함께 뒷면으로 만들면 셔플! 1번으로
맞바꿔 상대 카드를 빼앗고(2번으로 앞면), 상대 필드로 간 자신의 깜짝상자는 원래 주인(자신)만 열 수 있다.

구현 방식:
- 「뒷면 표시로 한다」(트랩퍼 2번 · 트랩: 깜짝상자): 몬스터는 Game.set_face_down(표시 형식 유지), 마법 존의 마법 카드는 세트 상태로 되돌린다
  (그 턴에 세트한 것으로 본다 — 신속 마법은 이 턴에 발동할 수 없다). 뒷면 카드는 [지속]이 적용되지 않는다(엔진 continuous_sources).
- 「뒷면 몬스터를 앞면으로」(셔플! 2번 · 깜짝상자 1번 코스트): 표시 형식은 그대로(깜짝상자는 「앞면 수비 표시로」) — 소환이 아니다. 사건 'flip'.
- 셔플! 1번 재배치 모델(ASSUME — 「셔플」 = 야바위): 필드의 뒷면 카드(양쪽 몬스터 존 · 마법 존, 공유 존 · 필드 존 제외)가 차지한 자리는
  그대로 두고, 그 자리들 사이에서 카드를 섞는다 — 뒷면 몬스터끼리 · 세트된 마법끼리 자리를 바꿀 수 있고(양쪽 필드 사이 포함), 놓인 쪽의
  플레이어가 컨트롤한다. 각 필드의 뒷면 몬스터 · 뒷면 마법 매수는 변하지 않는다(빈 존으로 옮기는 것은 「재배치」가 아님 — 룰에 어긋나는
  배치는 할 수 없다). 필드를 벗어나지 않으므로 카운터 · 표시 형식 · 뒷면은 그대로.
  AI는 「자신 필드의 뒷면 카드 ↔ 상대 필드의 뒷면 카드」 맞바꾸기만 고른다: 얻는 가치(상대 카드)가 주는 가치(자신 카드)보다 클 때.
  자신 소유의 깜짝상자는 상대 필드에서도 원래 주인(자신)만 열 수 있으므로 주는 손해가 없고, 상대 소유의 깜짝상자는 받지 않는다.
- 깜짝상자 1번 「원래 주인인 플레이어만 선언할 수 있다」: 엔진 Effect.owner_only — 컨트롤러가 아니라 원래 주인이 (상대 필드에 있어도) 발동한다.
  「뒷면 표시일 때만」: Effect.facedown_ok + cond(뒷면). 「상대 필드의 카드」는 발동한 플레이어(=원래 주인) 기준.
- 깜짝상자 2번 「뒷면 표시의 이 카드가 묘지로 보내졌을 경우」: 엔진 to_grave 사건의 was_faceup(보내지기 직전 앞면 여부).
- 인페르노 드래곤 1 · 2번: [지속] state_check — 상대 필드의 앞면 몬스터 중 공격력 또는 수비력이 2000 이상인 몬스터를 이 카드의 효과로 파괴.
  효과를 받지 않는 몬스터 · 효과로 파괴되지 않는 몬스터는 건너뛴다(같은 몬스터를 거듭 파괴하려 하지 않음).
- 데스 칠 드래곤 1번: 엔진 [지속] 규칙 'no_battle_damage'(p, 공격 몬스터, 공격 대상) — 이 카드가 낀 몬스터끼리의 전투에서 상대가 받는 전투 대미지 0.
  2번: 기존 규칙 'no_deck_to_hand'(상대).
- 헬 1번 뒷문장(「망령」 몬스터가 존재하는 한 전투로 파괴되지 않고 효과를 받지 않는다): 1번 처리 시 이 카드에 붙는 보호(flags['hell_guard'],
  필드를 벗어나면 사라짐). 「효과를 받지 않는다」는 callable immune_except_group(어떤 카드도 갖지 않는 카드군)으로 — 다른 모든 카드의 효과.
- 암흑의 율법 1번: [지속] on_event('activate') — 자신의 [유언] 발동을 link.replaced로 바꾼다(퇴마의 부적과 같은 방식). AI 판단: 강제 [유언]
  (상대 드로우 계열) · 망령 · 다크나이트는 서치할 카드가 있으면 바꾸고, 깜짝상자는 뒷면으로 묘지에 간 경우(파괴 효과)가 아니면 바꾼다.
- 트랩: 깜짝상자: 상대 발동에 체인(resp)해 그 Link를 link.replaced로 바꾼다. 바뀐 효과는 상대 카드의 효과로 본다(원인 카드 = 그 카드).
- 트랩: 거짓 샘물: 턴 종료 시까지의 부유 효과(floating, until=그 턴) — 「상대는 전투로 몬스터를 파괴할 수 없다」 = 그 턴 동안 자신 필드의
  몬스터(나중에 나온 몬스터 포함)에 battle_indestr_until을 단다(몬스터끼리의 전투는 늘 서로 다른 플레이어의 몬스터이므로 같은 뜻),
  「상대가 카드를 효과로 제거할 때마다 300」 = 상대 카드의 효과(원인 'effect')로 필드의 카드가 필드를 벗어난 사건(leave_field)마다 300.

ASSUME:
- 효과 종류 표기가 없는 효과(새크리파이스 1~3 · 어새신 2 · 매지션 1 · 헬 1 · 컨트롤러 1 · 2 · 셔플! 1 · 3)는 기동 효과(자신 턴 진행/정비 단계 · 체인 없음).
- 지속 마법의 표기 없는 효과(트랩 리페어 시스템 1번 · 암흑의 율법 2번): 지속 마법은 「사용 후 필드에 남아 계속해서 사용할 수 있는 마법 카드」(정본 1-2)
  이므로, 카드의 발동 때 처리하고 그 뒤에도 앞면으로 있는 동안 1턴에 1번(같은 효과 번호 — 발동한 턴에는 다시 못 씀) 기동 효과로 쓴다
  (재정 정리 2026-10-17). 율법은 묘지에 대상이 없어도 발동(놓기)할 수 있고(재정 로그 19), 앞면 상태의 2번은 대상이 있을 때만 쓴다.
- 「묘지」 · 「덱」(새크리파이스 2 · 매지션 1 · 컨트롤러 1)은 자신의 묘지 · 덱(율법 2번의 「자신 묘지」와 같게). 율법이 바꾼 효과의
  「「던전마스터」 카드를 1장 패에 넣는다」는 덱(메인 · 상급)에서. 「이 카드」 = [유언]을 발동한 그 카드.
- [유언] 「상대는 1장 드로우」(강제)도 1턴 1번 제약(§6-4)을 받는다 — 같은 이름 카드가 한 턴에 여러 장 묘지로 가도 한 번.
- 깜짝상자 1번의 코스트로 앞면 수비 표시가 된다. 2번은 「이 카드를 덱으로 되돌린다」와 별개로, 뒷면이었으면 「필드의 카드 1장」(양쪽 —
  상대 카드 우선)을 파괴한다.
- 망령 1번 · 트랩: 깜짝상자 「상대(의 효과)가 발동했을 때」 = 체인 대응(resp). 다크나이트 1번 · 가시바늘 「상대가 몬스터를 소환했을 때」 = 소환 사건 트리거
  (일반 · 특수 모두). 가시바늘의 「그 카드」는 발동 시 고른 대상.
- 새크리파이스 2번은 버린 자기 자신(0/0)을 고르지 않는다(묘지에 다른 「던전마스터」 몬스터가 있을 때만 발동). 3번은 빈 마법 존 수만큼(최대 2장) 세트
  (1장 이상 세트할 수 있어야 발동).
- 트랩퍼 1번 「「트랩」 카드를 1장 세트」 = 「트랩」 마법 카드(몬스터 세트는 규칙에 없음 — §5-2). 2번 대상은 뒷면으로 할 수 있는 앞면 카드
  (몬스터 존의 몬스터, 마법 존의 마법 카드 — 장착 카드 · 필드 존 제외), 자신 쪽은 이 카드 자신도 고를 수 있다.
- 어새신 1번: 특수소환을 처리해야 파괴도 처리한다(사용자 답변 2026-10-17 — 앞 효과 → 뒤 효과). 「필드의 카드」는 양쪽(상대 카드 우선,
  없으면 자신의 가장 가치가 낮은 카드). AI는 상대 카드가 없으면 쓰지 않는다.
- 매지션 1번: 덱에 「다크」 마법이 없어도 묘지에 「던전마스터」 몬스터가 있으면 발동할 수 있다. 종료 단계 회수는 이 턴의 종료 단계 시작 시
  (임의 — AI는 대상이 있으면 회수).
- 헬 1번: 덱에 「망령」 몬스터가 있어야 발동. 「「망령」 몬스터가 존재하는 한」 = 필드(양쪽)에 앞면 「망령」 몬스터. 보호는 앞면일 때만.
- 헬 2번: 상대의 일반소환 · 특수소환마다 200 (뒷면으로 놓는 것은 소환이 아님).
- 인페르노 · 헬 · 데스 칠의 [지속]은 상대 필드의 「앞면」 몬스터만 본다(뒷면 몬스터의 공격력 · 수비력은 알 수 없다).
- 트랩: 깜짝상자: 바뀐 효과의 특수소환은 이 카드의 컨트롤러(바뀐 효과 기준 「상대」)가 자신의 덱에서 한다(표시 형식은 그 플레이어가 고름).
  특수소환하지 못하면 「그 후」 이하도 없다. 「그 2장」(재정) 중 상대 카드는 필드에 있을 때만 — 마법 존의 마법 카드는 세트 상태로 필드에 남는다
  (일반 · 신속 · 트리거 마법도 처리 후 묘지로 가지 않음). 패 · 묘지 · 스킬 존에서 발동한 효과면 깜짝상자만 뒷면이 된다.
  발동하려면 자신의 덱에 「던전마스터 깜짝상자」가 있고 특수소환할 자리가 있어야 한다.
- 트랩: 거짓 샘물 「카드를 패에 넣었을 때」 = 덱 · 묘지에서 효과로 패에 넣은 사건과 드로우(턴 시작 드로우 포함 — 사용자 답변 2026-10-28, cards.hand_add).
  「카드를 효과로 제거」 = 필드의 카드를 필드에서 벗어나게 함(파괴 · 묘지 · 제외 · 덱 · 패 · 효과에 의한 릴리스) — 코스트는 포함하지 않음.
  「필드」 = 몬스터 존(공유 존 포함) · 마법 존 · 필드 존, 패 · 묘지 · 스킬 존은 들지 않는다 (사용자 답변 2026-10-22 Q37 — 지금 구현과 같음).
- 트랩 리페어 시스템: 「3장까지」는 1 ~ 3장(최소 1장 — 사용자 답변 2026-10-22, 시골쥐 2번과 같은 규칙), AI가 최대한(덱으로 되돌릴 가치가 큰 순).
  묘지에 「트랩」 카드가 없으면 발동하지 않는다. 체인 처리 중 묘지에서 사라져 0장이 되어도 1장 드로우(별도 문장).
- 셔플! 2번은 처리 시 고른다(대상 지정 없음). 셔플! 3번은 레벨 5 이상의 몬스터 1장.

- (검토 2026-10-13) 인페르노 드래곤이 양쪽 필드에 있으면 두 장의 [지속]을 동시에 적용한다(파괴 대상을 모두 모은 뒤 한꺼번에 파괴).
재정 질문:
1. 셔플! 1번 「재배치」의 범위: (지금) 뒷면 카드가 차지한 자리끼리 섞기 — 양쪽 필드 사이 맞바꾸기 가능, 컨트롤도 바뀜, 각 필드의 뒷면 매수는
   그대로(빈 존으로 옮기기 · 일방적으로 가져오기 불가). 세트된 마법 카드도 섞을 수 있음. 깜짝상자 1번의 「원래 주인만」 · 트랩퍼 2번 · 깜짝상자
   「그 2장」과 맞물리는 해석이다. 빈 존으로 옮기거나(일방적으로 가져오기) 자신 필드 안에서만 섞는 해석이면 알려 주기 바람.
2. 트랩퍼 1번 「「트랩」 카드를 1장 세트」에 몬스터(깜짝상자 등 「트랩」 몬스터)를 뒷면으로 놓는 것도 포함되는가? (지금: 마법 카드만)
3. 헬 1번의 「이 카드는, 「망령」 몬스터가 존재하는 한 …」은 1번을 처리했을 때 붙는 보호인가, 늘 적용되는 [지속]인가? (지금: 1번 처리 시 부여 — 사용자 답변 2026-10-22 Q33 유지)
   「존재」는 필드(양쪽)의 앞면 「망령」 몬스터인가? 「효과를 받지 않는다」는 자신 카드의 효과도 포함하는가? (지금: 그렇다 / 그렇다)
4. 트랩: 깜짝상자로 바뀐 효과가 상대의 일반 · 신속 · 트리거 마법이면, 그 마법 카드는 뒷면(세트)으로 필드에 남는다 (사용자 답변 2026-10-22 Q34, 유지)
5. 「묘지에서」(새크리파이스 2 · 매지션 1 · 컨트롤러 1)는 자신 묘지만 (사용자 답변 2026-10-22 Q35, 유지)
6. 암흑의 율법이 바꾼 효과의 「「던전마스터」 카드를 1장 패에 넣는다」는 덱에서, 「이 카드」는 [유언] 카드 (사용자 답변 2026-10-22 Q36, 유지)
7. 트랩: 거짓 샘물 「카드를 효과로 제거」의 범위 → 필드(몬스터 · 마법 · 필드 존)의 카드를 필드에서 벗어나게 하는 효과, 패 · 묘지는 포함하지 않음 (사용자 답변 2026-10-22 Q37)
(해결 2026-10-17: 2 마법 카드만 · 8 앞면으로 있는 동안 1턴 1번 · 9 받는다. 헬 「망령」= 던전마스터 망령만 — 설계도 확정)

엔진 변경 (engine.py · ai.py, 모두 추가 · 표시/규칙이 없는 카드는 예전과 같음):
- Game.zone_ok: Effect.owner_only(원래 주인만 발동 — 컨트롤러 대신 주인) · Effect.facedown_ok(뒷면 몬스터의 효과 발동 허용).
- Game.options: 상대 필드에 있는 자신 소유 카드 중 owner_only 효과가 있는 카드도 후보로.
- Game.send_grave: to_grave · leave_field 사건에 was_faceup(보내지기 직전 앞면 여부).
- Game.battle_damage(pair=) + [지속] 규칙 'no_battle_damage'(p, 공격 몬스터, 공격 대상); attack()의 몬스터끼리 전투 대미지 3곳이 pair를 넘긴다.
- ai.DECK_POLICY['던전마스터 셔플!'] (시작 패 메인 3 / 상급 2, 패의 상급 1~3장, 서치 우선순위).
- 사건 'flip'(뒷면 → 앞면, 이 모듈이 낸다 — 엔진 변경 아님).
"""
from engine import Effect
from cards import card, grp, best, value, own_turn, main_ok, opp_cards, last_opp_link, threat, ev_is, VETO, field_pick, hand_add
from cards2 import targets

DM = '던전마스터'; TRAP = '트랩'; DARK = '다크'
BOX = '던전마스터 깜짝상자'; MOURNER = '던전마스터 망령'; KNIGHT = '던전마스터 다크나이트'; SACRIFICE = '던전마스터 새크리파이스'
TRAPPER = '던전마스터 트랩퍼'; ASSASSIN = '던전마스터 다크엘프 어새신'; MAGICIAN = '던전마스터 다크 매지션'; EMPEROR = '던전마스터 다크 엠퍼러'
INFERNO = '던전마스터 인페르노 드래곤'; HELL = '던전마스터 헬'; CONTROLLER = '던전마스터 컨트롤러'; DEATHCHILL = '던전마스터 데스 칠 드래곤'
NEEDLE = '트랩: 가시바늘'; BOX_TRAP = '트랩: 깜짝상자'; SPRING = '트랩: 거짓 샘물'; REPAIR = '트랩 리페어 시스템'; LAW = '암흑의 율법'
SKILL = '던전마스터 셔플!'
FIELD_M = ('m', 'shared')
HELL_GUARD = '__헬의 가호__'   # 어떤 카드도 갖지 않는 카드군 — 헬의 「효과를 받지 않는다」를 immune_except_group으로 표현


def DM_CARD(x): return grp(x, DM)
def DM_MON(x): return grp(x, DM) and x.is_monster()
def TRAP_SPELL(x): return grp(x, TRAP) and x.type == '마법'
def TD_SPELL(x): return (grp(x, TRAP) or grp(x, DARK)) and x.type == '마법'
def DARK_SPELL(x): return grp(x, DARK) and x.type == '마법'
def mourner(x): return x.name == MOURNER and x.is_monster()   # 설계도 확정(2026-10-10): 「망령」 몬스터 = 「던전마스터 망령」만
def pri(g, p, x): return g.p[p].ai.card_pri(g, p, x)


# ═══════════════════════ 공통: 뒷면 · 앞면 · 재배치 ═══════════════════════
def turnable(g, x):
    """「뒷면 표시로 한다」를 받을 수 있는 앞면 카드: 몬스터 존(공유 존 포함)의 몬스터, 마법 존의 마법 카드(장착 · 몬스터 취급 제외),
    필드 존의 카드(뒷면이 되면 자동으로 묘지로 — 사용자 지시 2026-10-23, engine.Game.set_spell_face_down)"""
    if not g.on_field(x) or not x.faceup: return False
    if x.zone in FIELD_M: return x.is_monster()
    if x.zone == 'fieldz': return True
    if x.zone == 's':
        return x.type == '마법' and x.equip_to is None and not x.equips and not x.flags.get('as_spell') and not x.flags.get('as_monster')
    return False


def turn_face_down(g, x, src):
    """「뒷면 표시로 한다」: 몬스터는 Game.set_face_down(표시 형식 유지), 마법 카드는 세트 상태로 (이 턴에 세트한 것으로 본다)"""
    if not turnable(g, x): return False
    cause = ('effect', src)
    if x.zone in FIELD_M: return g.set_face_down(x, cause)
    return g.set_spell_face_down(x, cause)   # 필드 존의 카드는 묘지로


def keep_set(g, x):
    """처리 중 뒷면(세트)이 된 일반 · 신속 · 트리거 마법이 처리 후 규칙에 따라 묘지로 가지 않게 한다 (Game.resolve_chain은 flags['stay']를 본다).
    stay는 다음 사건에서 바로 푼다 — 그 뒤 다시 발동하면 보통의 마법처럼 묘지로 간다"""
    if x.flags.get('stay'): return
    x.flags['stay'] = True
    def fl(g2, ev, x=x):
        if fl in g2.floating: g2.floating.remove(fl)
        x.flags.pop('stay', None)
    fl.until = None
    g.floating.append(fl)


def flip_up(g, x, src, pos=None):
    """뒷면 몬스터를 앞면으로 (소환이 아님). pos: 「앞면 수비 표시로」처럼 표시 형식을 정할 때"""
    if not g.on_field(x) or x.faceup or not x.is_monster(): return False
    if src is not x and g.blocked(x, ('effect', src)): return False
    x.faceup = True
    if pos: x.pos = pos
    g.L(f'{x} 앞면 {"공격" if x.pos == "atk" else "수비"} 표시로 뒤집힘')
    g.emit('flip', card=x, cause=('effect', src))
    return True


def swap_cards(g, x, y):
    """같은 종류 존(몬스터 존끼리 · 마법 존끼리)의 뒷면 카드 x · y의 자리를 맞바꾼다 — 필드를 벗어나지 않음
    (카운터 · 표시 형식 · 뒷면 유지), 놓인 쪽의 플레이어가 컨트롤한다"""
    if x.zone != y.zone or x.zone not in ('m', 's') or x.faceup or y.faceup: return False
    lx = getattr(g.p[x.controller], x.zone); ly = getattr(g.p[y.controller], y.zone)
    if x not in lx or y not in ly: return False
    ix, iy = lx.index(x), ly.index(y)
    lx[ix], ly[iy] = y, x
    x.controller, y.controller = y.controller, x.controller
    return True


def dm_rank(g, p, x):
    """특수소환할 몬스터의 우선순위 (AI): 공격력 · 레벨(value) + 나온 뒤 쓸 효과. 패에서만 쓰는 새크리파이스(0/0)는 고르지 않는다"""
    if x.name == SACRIFICE: return -5
    r = 10 * value(g, x)
    if x.name == CONTROLLER and any(DM_MON(y) and y is not x for y in g.deck_cards(p) + g.p[p].grave): r += 40   # 보스 특수소환 + 서치
    if x.name == HELL and any(mourner(y) for y in g.deck_cards(p)): r += 25        # 망령까지 2장 + 소환마다 200
    if x.name == INFERNO: r += 10 * sum(1 for m in g.monsters(1 - p) if m.faceup and (g.atk(m) >= 2000 or g.df(m) >= 2000))
    if x.name == ASSASSIN and x.zone == 'hand': r -= 15   # 1번으로 스스로 특수소환할 수 있다
    if x.name == MOURNER and any(m.name == HELL and m.faceup for m in g.monsters(p)): r += 8
    return r


def summon_best(g, p, cands, why):
    cands = [x for x in cands if g.can_special(x, p)]
    if not cands: g.L(f'{why}: 특수소환할 몬스터 없음', 'sys'); return None
    x = max(cands, key=lambda x: (dm_rank(g, p, x), pri(g, p, x)))
    from_deck = x.zone in ('main', 'upper')
    if g.special_summon(x, p) and from_deck: g.shuffle(p)
    return x


def best_rank(g, p, cands):
    cs = [dm_rank(g, p, x) for x in cands if g.can_special(x, p)]
    return max(cs) if cs else None


def opp_best(g, p, pool=None):
    ts = targets(g, p, opp_cards(g, p) if pool is None else pool)
    return max((value(g, x) for x in ts), default=0), ts


def strong_attackers(g, p):
    """상대의 공격 표시 앞면 몬스터 중 위협이 되는 몬스터 (상대 전투 단계의 대응 점수)"""
    return [m for m in g.monsters(1 - p) if m.faceup and m.pos == 'atk' and g.atk(m) >= 1500 and not g.attack_banned(m)]


def law_on(g, p): return any(x.name == LAW and x.faceup and not g.is_neg(x) for x in g.spells(p))


def lastwill(num, res, score=50, cond=None, mandatory=False, label='[유언]', threat=200):
    def cnd(g, c, p, ev):
        if not (ev_is(ev, 'to_grave') and ev['card'] is c and (c.zone == 'grave' or c.uid in getattr(g, 'lw_grace', ()))): return False   # 우선 선언(Game.triggers)
        return cond is None or cond(g, c, p, ev)
    sc = score if callable(score) else (lambda *a, s=score: s)
    return Effect(num, 'lastwill', ('grave',), cond=cnd, res=res, score=sc, mandatory=mandatory, threat=threat, label=label)


def back_to_deck(g, c, p):
    if c.zone == 'grave':
        g.to_deck(c, ('effect', c)); g.shuffle(p); g.L(f'{c} 덱으로')


def opp_draw_lastwill(num=3, back=False):
    """[유언] (이 카드를 덱으로 되돌린다.) 상대는 카드를 1장 드로우한다. (이 효과는 강제로 발동한다.)"""
    def res(g, c, p, l):
        if back: back_to_deck(g, c, p)
        g.L(f'{g.pname(1 - p)} 1장 드로우 ({c.name} [유언])'); g.draw(1 - p, 1)
    return lastwill(num, res, 0, mandatory=True, label='[유언] 상대 1장 드로우 (강제)' if not back else '[유언] 덱으로 · 상대 1장 드로우 (강제)', threat=100)


# ═══════════════════════ 메인 덱 몬스터 ═══════════════════════
@card(BOX)
def _(c):
    def cands1(g, c, p): return targets(g, p, [x for x in opp_cards(g, p) if x is not c])
    def cond1(g, c, p, ev):
        return g.on_field(c) and not c.faceup and c.owner == p and c.zone in FIELD_M and bool(cands1(g, c, p))
    def cost1(g, c, p, l):
        g.L(f'코스트: {c} 앞면 수비 표시로 변경'); flip_up(g, c, c, 'def')
    def res1(g, c, p, l):
        t = best(g, cands1(g, c, p), p)   # 「상대 필드의 카드를 1장」 — 대상 지정 없음, 처리 시 고른다
        if t: g.destroy(t, ('effect', c))
    def sc1(g, c, p, ev):
        v, ts = opp_best(g, p, [x for x in opp_cards(g, p) if x is not c])
        if not ts: return VETO
        if main_ok(g, p): return 40 + 15 * v
        l = last_opp_link(g, p)
        if l is not None and threat(g, p) >= 800 and l.card in ts: return 55
        if not own_turn(g, p) and g.phase == '전투' and not g.chain and strong_attackers(g, p): return 45
        return 0
    def res2(g, c, p, l):
        fd = not l.ctx['ev'].get('was_faceup', True)
        back_to_deck(g, c, p)
        if fd:   # 「뒷면 표시의 이 카드가 묘지로 보내졌을 경우, 카드를 1장 파괴한다」 — 필드의 카드(상대 카드 우선)
            t = field_pick(g, p, pool=targets(g, p, g.all_field()))
            if t: g.destroy(t, ('effect', c))
    e1 = Effect(1, 'quick', ('field',), cond=cond1, cost=cost1, res=res1, score=sc1, threat=900, label='뒷면 → 앞면 수비, 상대 카드 1장 파괴')
    e1.owner_only = True; e1.facedown_ok = True
    c.effects = [e1,
                 lastwill(2, res2, lambda g, c, p, ev: (85 if targets(g, p, opp_cards(g, p)) else VETO) if not ev.get('was_faceup', True) else 30,   # 뒷면이었고 상대 카드가 없으면 자신 카드를 파괴하게 됨
                          label='[유언] 덱으로 (뒷면이었으면 카드 1장 파괴)', threat=500)]


@card(MOURNER)
def _(c):
    def cost1(g, c, p, l):
        l.ctx['t'] = g.chain[-1]; g.L(f'코스트: {c} 릴리스'); g.tribute(c, ('cost', c))
    def sc1(g, c, p, ev):
        t = threat(g, p)
        hell = any(m.name == HELL and m.faceup and m.flags.get('hell_guard') for m in g.monsters(p))
        others = sum(1 for m in g.monsters(0) + g.monsters(1) if mourner(m) and m.faceup and m is not c)
        if hell and not others: return 60 if t >= 900 else 0   # 헬의 보호가 이 카드에 걸려 있다
        return 60 if t >= 600 else 35 if t >= 400 else 0
    c.effects = [
        Effect(1, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and g.releasable(c),
               cost=cost1, res=lambda g, c, p, l: g.negate(l.ctx['t'], by=c), score=sc1, threat=800, label='자신 릴리스 → 상대 효과 무효'),
        lastwill(2, lambda g, c, p, l: back_to_deck(g, c, p), 35, label='[유언] 덱으로')]


@card(KNIGHT)
def _(c):
    def cands(g, p): return targets(g, p, opp_cards(g, p))
    def cond1(g, c, p, ev):
        return ev_is(ev, 'summon') and ev['player'] == 1 - p and g.on_field(c) and g.releasable(c) and bool(cands(g, p))
    def cost1(g, c, p, l):
        l.ctx['t'] = best(g, cands(g, p), p); g.L(f'코스트: {c} 릴리스, 대상: {l.ctx["t"]}'); g.tribute(c, ('cost', c))
    def res1(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t) and t.controller == 1 - p: g.destroy(t, ('effect', c))
    def sc1(g, c, p, ev):
        v, ts = opp_best(g, p)
        return 30 + 20 * (v - 2.0) if ts else VETO
    def res2(g, c, p, l):
        back_to_deck(g, c, p)
        g.search(p, DM_CARD, which=('upper',), why=f'{c.name} [유언]', source=c)
    c.effects = [
        Effect(1, 'trigger', ('field',), cond=cond1, cost=cost1, res=res1, score=sc1, threat=900, label='상대 소환 → 자신 릴리스, 상대 카드 1장 파괴'),
        lastwill(2, res2, lambda g, c, p, ev: 80 if g.can_search(p, DM_CARD, which=('upper',), source=c) else 20,
                 label='[유언] 덱으로 · 상급 덱 「던전마스터」 서치', threat=300)]


# ═══════════════════════ 상급 덱 몬스터 ═══════════════════════
@card(SACRIFICE)
def _(c):
    def discard(g, c, p, l):
        g.L(f'코스트: 패의 {c} 버림'); g.send_grave(c, ('cost', c))
    def gy(g, c, p): return [x for x in g.p[p].grave if DM_MON(x) and x is not c and g.can_special(x, p)]
    def res2(g, c, p, l):
        cs = gy(g, c, p) or [x for x in g.p[p].grave if DM_MON(x) and g.can_special(x, p)]
        summon_best(g, p, cs, f'{c.name} 2번')
    def sc2(g, c, p, ev):
        r = best_rank(g, p, gy(g, c, p))
        return 25 + r if r is not None and r > 0 else VETO
    def res3(g, c, p, l):
        for _ in range(2):
            cs = [x for x in g.deck_cards(p, ('main',)) if TD_SPELL(x)]
            if not cs or not g.free_s(p): break
            x = g.p[p].ai.pick_search(g, p, cs, f'{c.name} 3번 세트'); g._remove(x); g.place_spell(x, p, False); g.L(f'덱에서 {x} 세트')
        g.shuffle(p)
    def sc3(g, c, p, ev):
        n = len({x.name for x in g.deck_cards(p, ('main',)) if TD_SPELL(x)})
        return 40 if n >= 2 and len(g.free_s(p)) >= 2 else 20
    c.effects = [
        Effect(1, 'ignition', ('hand',), cond=lambda g, c, p, ev: g.can_search(p, DM_CARD), cost=discard,
               res=lambda g, c, p, l: g.search(p, DM_CARD, why=f'{c.name} 1번', source=c), score=lambda *a: 45, threat=300, label='버림 → 「던전마스터」 서치'),
        Effect(2, 'ignition', ('hand',), cond=lambda g, c, p, ev: bool(gy(g, c, p)), cost=discard, res=res2, score=sc2, threat=500,
               label='버림 → 묘지의 「던전마스터」 몬스터 특수소환'),
        Effect(3, 'ignition', ('hand',), cond=lambda g, c, p, ev: bool(g.free_s(p)) and any(TD_SPELL(x) for x in g.deck_cards(p, ('main',))),
               cost=discard, res=res3, score=sc3, threat=300, label='버림 → 「트랩」 · 「다크」 마법 2장 세트')]


@card(TRAPPER)
def _(c):
    def res1(g, c, p, l):
        cs = [x for x in g.deck_cards(p) if TRAP_SPELL(x)]
        if not cs or not g.free_s(p): g.L('세트할 「트랩」 마법 · 빈 마법 존 없음', 'sys'); return
        x = g.p[p].ai.pick_search(g, p, cs, f'{c.name} 1번 세트'); g._remove(x); g.place_spell(x, p, False)
        x.flags['act_this_turn'] = g.turn; g.L(f'덱에서 {x} 세트 (이 턴에도 발동 가능)'); g.shuffle(p)
    def own_cands(g, c, p): return [x for x in g.field_cards(p) if turnable(g, x) and not g.immune(x, p, c)]
    def opp_cands(g, c, p): return targets(g, p, [x for x in opp_cards(g, p) if turnable(g, x)])
    def own_cost(g, p, x):
        """자신 쪽 대상의 손익 (낮을수록 좋다): 앞면 깜짝상자(뒷면이 되면 1번을 쓸 수 있다) · 다시 발동할 수 있는 지속 마법이 가장 좋다"""
        if x.name == BOX and x.zone in FIELD_M: return -1.5
        if x.name == REPAIR: return -1.0
        if x.name == LAW: return -1.0 if any(DM_MON(y) for y in g.p[p].grave) else 0.5
        return value(g, x)
    def cost2(g, c, p, l):
        a = min(own_cands(g, c, p), key=lambda x: (own_cost(g, p, x), x.uid))
        b = best(g, opp_cands(g, c, p), p, 'negate_monster')
        l.ctx['a'] = a; l.ctx['b'] = b; g.L(f'대상: 자신 {a} · 상대 {b}')
    def res2(g, c, p, l):
        for k in ('a', 'b'):
            t = l.ctx.get(k)
            if t is not None and g.on_field(t): turn_face_down(g, t, c)
    def sc2(g, c, p, ev):
        own = own_cands(g, c, p); v, ts = opp_best(g, p, [x for x in opp_cards(g, p) if turnable(g, x)])
        if not own or not ts: return VETO
        s = 25 + 15 * v - 12 * max(0, min(own_cost(g, p, x) for x in own))
        if main_ok(g, p): return s
        if not own_turn(g, p) and g.phase == '전투' and not g.chain and any(m in ts for m in strong_attackers(g, p)): return max(s, 45)
        return 0
    c.effects = [
        Effect(1, 'quick', ('field',), cond=lambda g, c, p, ev: bool(g.free_s(p)) and any(TRAP_SPELL(x) for x in g.deck_cards(p)), res=res1,
               score=lambda g, c, p, ev: 40 if main_ok(g, p) else 0, threat=300, label='덱에서 「트랩」 마법 세트'),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: bool(own_cands(g, c, p)) and bool(opp_cands(g, c, p)), cost=cost2, res=res2,
               score=sc2, threat=800, label='자신 카드 1장 · 상대 카드 1장 뒷면으로'),
        opp_draw_lastwill(3)]


@card(ASSASSIN)
def _(c):
    def res1(g, c, p, l):   # 앞 효과(특수소환)를 처리해야 뒤 효과(파괴)도 처리한다 — 마침표로 나뉜 문장도 같다 (사용자 답변 2026-10-17)
        if not (c.zone == 'hand' and g.special_summon(c, p)): g.L(f'{c} 특수소환 못 함 — 파괴도 하지 않음', 'sys'); return
        t = field_pick(g, p)   # 「필드의 카드 1장」: 서로의 필드 — 상대 카드 우선
        if t: g.destroy(t, ('effect', c))
    def sc1(g, c, p, ev):
        v, ts = opp_best(g, p)
        if not ts: return VETO
        if main_ok(g, p): return 50 + 15 * v
        l = last_opp_link(g, p)
        if l is not None and threat(g, p) >= 800 and l.card in ts: return 55
        if not own_turn(g, p) and g.phase == '전투' and not g.chain and strong_attackers(g, p): return 45
        return 0
    def cost2(g, c, p, l):
        l.ctx['t'] = best(g, targets(g, p, opp_cards(g, p)), p); g.L(f'코스트: {c} 릴리스, 대상: {l.ctx["t"]}'); g.tribute(c, ('cost', c))
    def res2(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t) and t.controller == 1 - p: g.destroy(t, ('effect', c))
    def sc2(g, c, p, ev):
        v, ts = opp_best(g, p)
        if not ts: return VETO
        return 10 + 15 * (v - value(g, c)) - (0 if law_on(g, p) else 15)
    c.effects = [
        # 같은 카드의 1번이 이미 체인에 있으면 다시 발동할 수 없다 — 원문 재정 「이 카드가 자체적으로 패로 돌아갈 수는 없다 …
        # 동명의 카드를 여러 장 패에 잡고 각자 사용해 1턴에 최대 3회」 = 패에 있는 동안 1장당 1회 (2026-10-15 수정, 보고서 로그 점검)
        Effect(1, 'quick', ('hand',), opt=3, cond=lambda g, c, p, ev: g.can_special(c, p) and not any(l.card is c and l.eff.num == 1 for l in g.chain),
               cost=lambda g, c, p, l: g.L(f'코스트: 패의 {c} 공개'), res=res1, score=sc1, threat=1000, label='패에서 특수소환 + 필드의 카드 1장 파괴'),
        Effect(2, 'ignition', ('field',), cond=lambda g, c, p, ev: g.releasable(c) and bool(targets(g, p, opp_cards(g, p))),
               cost=cost2, res=res2, score=sc2, threat=900, label='자신 릴리스 → 상대 카드 1장 파괴'),
        opp_draw_lastwill(3)]


@card(MAGICIAN)
def _(c):
    def gy(g, p): return [x for x in g.p[p].grave if DM_MON(x)]
    def res1(g, c, p, l):
        g.search(p, DARK_SPELL, why=f'{c.name} 1번', source=c)
        t0 = g.turn
        def fl(g2, ev):
            if ev['kind'] != 'phase' or ev.get('phase') != '종료' or g2.turn != t0: return
            if fl in g2.floating: g2.floating.remove(fl)
            cs = gy(g2, p)
            if cs: g2.L(f'판단[{g2.pname(p)}] {c.name} 1번: 종료 단계에 묘지의 「던전마스터」 몬스터 회수', 'decision'); g2.salvage(p, cs, f'{c.name} 1번 (종료 단계)', source=c)
        fl.until = g.turn; g.floating.append(fl)
    def res2(g, c, p, l):
        t = field_pick(g, p)
        if t: g.destroy(t, ('effect', c))
    def sc2(g, c, p, ev):
        v, ts = opp_best(g, p)
        if not ts: return VETO
        if main_ok(g, p): return 25 + 15 * v
        if threat(g, p) >= 900: return 45
        if not own_turn(g, p) and g.phase == '전투' and not g.chain and strong_attackers(g, p): return 40
        return 0
    c.effects = [
        Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: g.can_search(p, DARK_SPELL) or bool(gy(g, p)), res=res1,
               score=lambda g, c, p, ev: 45 if g.can_search(p, DARK_SPELL) else 20, threat=300, label='「다크」 마법 서치 + 종료 단계 회수'),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: bool(targets(g, p, g.all_field())), res=res2, score=sc2, threat=1000,
               label='필드의 카드 1장 파괴'),
        opp_draw_lastwill(3)]


@card(EMPEROR)
def _(c):
    def hand_dm(g, c, p): return [x for x in g.p[p].hand if DM_MON(x) and x is not c and g.can_special(x, p)]
    def sc1(g, c, p, ev):
        r = best_rank(g, p, hand_dm(g, c, p))
        if r is None or r <= 0: return VETO
        if main_ok(g, p): return 25 + r * 0.8
        hot = sum(1 for m in g.monsters(1 - p) if m.faceup and (g.atk(m) >= 2000 or g.df(m) >= 2000))
        if any(x.name == INFERNO for x in hand_dm(g, c, p)) and hot and not g.chain: return 60   # 상대 턴에 인페르노로 2000 이상 몬스터 일소
        return 0
    def knights(g, p): return [x for x in g.deck_cards(p) if x.name == KNIGHT and g.can_special(x, p)]
    def sc2(g, c, p, ev):
        if main_ok(g, p): return 45
        return 30 if not own_turn(g, p) and g.phase == '진행' and not g.chain else 0   # 상대 진행 단계 첫 우선권 — 상대가 소환하기 전에 다크나이트를 세운다
    c.effects = [
        Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: bool(hand_dm(g, c, p)), cost=lambda g, c, p, l: g.L(f'코스트: 패의 {c} 공개'),
               res=lambda g, c, p, l: summon_best(g, p, hand_dm(g, c, p), f'{c.name} 1번'), score=sc1, threat=700, label='패의 「던전마스터」 몬스터 특수소환'),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: bool(knights(g, p)),
               res=lambda g, c, p, l: summon_best(g, p, knights(g, p), f'{c.name} 2번'), score=sc2, threat=500, label='덱에서 다크나이트 특수소환'),
        opp_draw_lastwill(3)]


@card(INFERNO)
def _(c):
    def sc(g, src):
        """1 · 2번 [지속]: 공격력 또는 수비력 2000 이상인 상대 필드의 (앞면) 몬스터는 파괴된다.
        양쪽에 인페르노가 있으면 동시에 적용한다 — 모든 앞면 인페르노의 파괴 대상을 먼저 모은 뒤 한꺼번에 파괴"""
        if g.__dict__.get('_inferno_busy') or not g.on_field(src): return
        hits = []
        for s in [x for x in g.monsters(0) + g.monsters(1) if x.name == INFERNO and x.faceup and not g.is_neg(x)]:
            p = s.controller
            hits += [(s, m) for m in g.monsters(1 - p) if m.faceup and (g.atk(m) >= 2000 or g.df(m) >= 2000)
                     and not g.immune(m, p, s) and not g.rule('indestructible', m, False) and all(m is not h for _, h in hits)]
        if not hits: return
        g._inferno_busy = True
        try:
            for s, m in hits:
                if g.on_field(m) and m.controller == 1 - s.controller and m.faceup:
                    g.L(f'{s.name} [지속]: {m}(공 {g.atk(m)} / 수 {g.df(m)}) 파괴'); g.destroy(m, ('effect', s))
        finally:
            g._inferno_busy = False
    c.state_check = sc
    c.effects = [opp_draw_lastwill(3)]


@card(HELL)
def _(c):
    def guarded(g, x):
        return (x.faceup and g.on_field(x) and bool(x.flags.get('hell_guard'))
                and any(mourner(m) and m.faceup for m in g.monsters(0) + g.monsters(1)))
    c.flags['immune_except_group'] = lambda g, x: HELL_GUARD if guarded(g, x) else None   # 「효과를 받지 않는다」 (다른 모든 카드)
    c.rules = {'indestructible': lambda g, src, x, battle: battle and x is src and guarded(g, src)}
    def on_ev(g, src, ev):
        """2번 [지속]: 상대가 몬스터를 소환할 때마다 200 대미지"""
        if ev['kind'] == 'summon' and ev.get('player') == 1 - src.controller and g.cont_use(src, 2, '상대 소환 대미지'):   # 1턴 1번, 주인이 고른다
            g.damage(1 - src.controller, 200, f'{src.name} 2번')
    c.on_event = on_ev
    def ms(g, p): return [x for x in g.deck_cards(p) if mourner(x) and g.can_special(x, p)]
    def res1(g, c, p, l):
        cs = ms(g, p)
        if cs:
            x = g.p[p].ai.pick_search(g, p, cs, f'{c.name} 1번'); g.special_summon(x, p); g.shuffle(p)
        if g.on_field(c):
            c.flags['hell_guard'] = True
            col = c.flags.get('clear_on_leave') or {}; col.setdefault('hell_guard', None); c.flags['clear_on_leave'] = col
            g.L(f'{c}: 「망령」 몬스터가 존재하는 한 전투로 파괴되지 않고 효과를 받지 않음')
    c.effects = [
        Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: bool(ms(g, p)), res=res1, score=lambda *a: 65, threat=600,
               label='덱에서 「망령」 몬스터 특수소환 + 보호'),
        opp_draw_lastwill(3)]


@card(CONTROLLER)
def _(c):
    def cands(g, p): return [x for x in g.deck_cards(p) + g.p[p].grave if DM_MON(x) and g.can_special(x, p)]
    def sc1(g, c, p, ev):
        r = best_rank(g, p, cands(g, p))
        return 40 + 0.6 * r if r is not None and r > 0 else VETO
    c.effects = [
        Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: bool(cands(g, p)),
               res=lambda g, c, p, l: summon_best(g, p, cands(g, p), f'{c.name} 1번'), score=sc1, threat=700,
               label='덱 · 묘지의 「던전마스터」 몬스터 특수소환'),
        Effect(2, 'ignition', ('field',), cond=lambda g, c, p, ev: g.can_search(p, DM_CARD),
               res=lambda g, c, p, l: g.search(p, DM_CARD, why=f'{c.name} 2번', source=c), score=lambda *a: 40, threat=300, label='「던전마스터」 서치'),
        opp_draw_lastwill(3, back=True)]


@card(DEATHCHILL)
def _(c):
    c.rules = {
        # 1번 [지속]: 이 카드가 몬스터와 전투할 때, 상대 플레이어에게 가하는 대미지는 0 (엔진 battle_damage의 pair)
        'no_battle_damage': lambda g, src, p, a, t: p == 1 - src.controller and (a is src or t is src),
        # 2번 [지속]: 상대는 효과로 덱에서 카드를 패에 넣을 수 없다
        'no_deck_to_hand': lambda g, src, player: player == 1 - src.controller}
    c.effects = [opp_draw_lastwill(3)]


# ═══════════════════════ 마법 ═══════════════════════
@card(NEEDLE)
def _(c):
    def cond(g, c, p, ev):
        if not (ev_is(ev, 'summon') and ev['player'] == 1 - p): return False
        x = ev['card']
        return g.on_field(x) and x.controller == 1 - p and not g.immune(x, p, c)
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if t is not None and g.on_field(t): g.destroy(t, ('effect', c))
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True, cond=cond,
                        cost=lambda g, c, p, l: l.ctx.update(t=l.ctx['ev']['card']) or g.L(f'대상: {l.ctx["t"]}'), res=res,
                        score=lambda g, c, p, ev: 20 + 25 * value(g, ev['card']) if isinstance(ev, dict) and 'card' in ev else 40, threat=900,
                        label='상대가 소환한 몬스터 파괴')]


@card(BOX_TRAP)
def _(c):
    def boxes(g, p): return [x for x in g.deck_cards(p) if x.name == BOX and g.can_special(x, p)]
    def cond(g, c, p, ev):
        l = last_opp_link(g, p)
        return l is not None and l.replaced is None and bool(boxes(g, p))
    def res(g, c, p, l):
        tl = l.ctx['t']
        if tl not in g.chain or tl.negated: g.L('변경할 발동이 없음', 'sys'); return
        def rep(g2, tl2, p=p):
            bs = boxes(g2, p)
            if not bs: g2.L(f'{BOX_TRAP}: 덱에 「{BOX}」 없음 — 처리 없음', 'sys'); return
            b = bs[0]
            if not g2.special_summon(b, p, by=tl2.card): return
            g2.shuffle(p)
            turn_face_down(g2, b, tl2.card)   # 그 후, 그 2장(재정: 발동한 상대 카드 + 특수소환된 깜짝상자)을 뒷면 표시로
            x = tl2.card
            if x is not b and turnable(g2, x):
                was_spell = x.zone == 's'
                if turn_face_down(g2, x, tl2.card) and was_spell: keep_set(g2, x)
        if not g.replace(tl, rep, c): return   # 발동한 카드가 깜짝상자의 효과를 받지 않으면(봉인 카운터가 있는 티라누스 등) 바뀌지 않는다 (Q59)
        g.L(f'{tl.card}의 효과를 「상대는 덱에서 「{BOX}」를 특수소환한다. 그 후, 그 2장을 뒷면 표시로 한다.」로 변경')
    def sc(g, c, p, ev):
        t = threat(g, p); l = last_opp_link(g, p)
        bonus = 10 if l is not None and l.card.zone in FIELD_M and l.card.faceup else 0
        return (60 if t >= 600 else 35 if t >= 400 else 0) + (bonus if t >= 400 else 0)
    c.effects = [Effect(1, 'resp', ('hand', 'field'), spell_act=True, cond=cond, cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res,
                        score=sc, threat=800, label='상대 효과 변경 — 깜짝상자 특수소환 · 그 2장 뒷면')]


@card(SPRING)
def _(c):
    def cond(g, c, p, ev):
        h = hand_add(ev)   # 드로우 포함 (사용자 답변 2026-10-28)
        return h is not None and h[1] == 1 - p
    def res(g, c, p, l):
        q = 1 - p; t0 = g.turn; name = c.name
        def guard(g2):   # 「상대는 전투로 몬스터를 파괴할 수 없다」 = 이 턴 동안 자신 필드의 몬스터는 전투로 파괴되지 않는다
            for m in g2.monsters(p):
                if m.flags.get('battle_indestr_until', -1) < t0: m.flags['battle_indestr_until'] = t0
        def fl(g2, ev):
            if g2.turn != t0: return
            guard(g2)
            if ev['kind'] == 'leave_field':
                ca = ev.get('cause') or ('', None)
                src = ca[1] if ca[0] == 'effect' else None
                if src is not None and src.controller == q and ev.get('prev') in ('m', 's', 'shared', 'fieldz'):
                    g2.damage(q, 300, f'{name} — {ev["card"].name} 제거')
        fl.until = t0; g.floating.append(fl); guard(g)
        g.L(f'턴 종료 시까지 {g.pname(q)}: 전투로 몬스터를 파괴할 수 없음 · 효과로 카드를 제거할 때마다 300 대미지')
    def sc(g, c, p, ev):
        if own_turn(g, p): return 30
        return 55 if g.phase in ('준비', '진행') else 25
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True, cond=cond, res=res, score=sc, threat=500,
                        label='상대 패 추가 → 턴 종료 시까지 전투 파괴 불가 · 제거마다 300')]


@card(REPAIR)
def _(c):
    def res(g, c, p, l):
        xs = sorted([x for x in g.p[p].grave if grp(x, TRAP)], key=lambda x: -pri(g, p, x))[:3]
        for x in xs: g.to_deck(x, ('effect', c))
        if xs: g.shuffle(p); g.L(f'묘지의 「트랩」 카드 {len(xs)}장 덱으로: {", ".join(map(str, xs))}')
        g.draw(p, 1)
    cond = lambda g, c, p, ev: bool(g.p[p].main or g.p[p].upper) and any(grp(x, TRAP) for x in g.p[p].grave)   # 「3장까지」: 최소 1장
    sc = lambda g, c, p, ev: 30 + 8 * min(3, sum(1 for x in g.p[p].grave if grp(x, TRAP)))
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=cond, res=res, score=sc, threat=200,
                        label='묘지 「트랩」 3장까지 덱으로 · 1장 드로우'),
                 Effect(1, 'ignition', ('field',), cond=cond, res=res, score=sc, threat=200,   # 앞면으로 있는 동안 1턴에 1번 (정본 1-2 지속 마법)
                        label='(앞면) 묘지 「트랩」 3장까지 덱으로 · 1장 드로우')]


def law_wants(g, p, link):
    """암흑의 율법 1번 AI 판단: 이 [유언]을 「덱으로 되돌리고 「던전마스터」 카드 서치」로 바꿀까"""
    x = link.card
    can = bool(g.search_cands(p, DM_CARD, source=x))
    if link.eff.mandatory: return True                       # 「상대는 1장 드로우」(강제) — 바꾸면 손해가 이득으로
    if x.name == BOX:
        ev = link.ctx.get('ev') or {}
        return can and ev.get('was_faceup', True)            # 뒷면으로 묘지에 갔으면 원래 효과(파괴)를 쓴다
    if x.name in (MOURNER, KNIGHT): return can
    return False                                             # 그 밖의 카드는 원래 [유언]


@card(LAW)
def _(c):
    def on_ev(g, src, ev):
        """1번 [지속]: 자신의 [유언] 효과가 발동할 때, 그 효과를 「이 카드를 덱으로 되돌리고 「던전마스터」 카드를 1장 패에 넣는다」로 변경할 수 있다"""
        if ev['kind'] != 'activate' or ev.get('player') != src.controller: return
        link = ev['link']
        if link.eff.kind != 'lastwill' or link.replaced is not None or link.negated: return
        p = src.controller
        if not law_wants(g, p, link): return
        def rep(g2, tl, p=p):
            x = tl.card
            back_to_deck(g2, x, p)
            g2.search(p, DM_CARD, why=f'{LAW} (변경된 {x.name} [유언])', source=x)
        if g.replace(link, rep, src):
            g.L(f'판단[{g.pname(p)}] {LAW}: {link.card}의 [유언]을 「덱으로 되돌리고 「던전마스터」 카드 서치」로 변경', 'decision')
    c.on_event = on_ev
    def gy(g, p): return [x for x in g.p[p].grave if DM_MON(x) and g.can_special(x, p)]
    def sc(g, c, p, ev):
        r = best_rank(g, p, gy(g, p))
        if r is not None and r > 0: return 30 + 0.6 * r
        return 0 if law_on(g, p) else 15
    c.effects = [Effect(2, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: True,
                        res=lambda g, c, p, l: summon_best(g, p, gy(g, p), f'{c.name} 2번'), score=sc, threat=500,
                        label='카드의 발동: 자신 묘지의 「던전마스터」 몬스터 특수소환'),
                 Effect(2, 'ignition', ('field',), cond=lambda g, c, p, ev: bool(gy(g, p)),   # 앞면으로 있는 동안 1턴에 1번 (정본 1-2 지속 마법)
                        res=lambda g, c, p, l: summon_best(g, p, gy(g, p), f'{c.name} 2번'), score=lambda g, c, p, ev: sc(g, c, p, ev) if gy(g, p) else 0,
                        threat=500, label='(앞면) 자신 묘지의 「던전마스터」 몬스터 특수소환')]


# ═══════════════════════ 스킬 ═══════════════════════
def spell_val(x):
    """세트된 마법 카드의 가치 (AI): 효과의 위협도 — 상대 턴에 쓸 함정일수록 크다"""
    return max((e.threat for e in x.effects), default=0) / 500


def take_gain(g, p, y):
    """상대 필드의 뒷면 카드 y를 자신 필드로 받을 때 얻는 가치. 상대 소유 깜짝상자는 받지 않는다(상대가 열면 자신의 카드가 파괴된다)"""
    if y.zone == 'm':
        if y.name == BOX and y.owner != p: return None
        return value(g, y) + 0.5                       # 상대의 벽 · 제물이 사라지고, 셔플! 2번으로 앞면으로 할 수 있다
    return spell_val(y)


def give_cost(g, p, x):
    """자신 필드의 뒷면 카드 x를 상대 필드로 줄 때 잃는 가치. 자신 소유 깜짝상자는 상대 필드에서도 자신만 열 수 있다"""
    if x.zone == 'm':
        if x.name == BOX and x.owner == p: return -0.5
        return 0.6 * value(g, x) + (0.6 if x.pos == 'def' else 0)   # 뒷면 수비 표시는 상대의 벽이 된다
    return spell_val(x)


def shuffle_plan(g, p):
    """셔플! 1번 AI 계획: (자신 필드의 뒷면 카드, 상대 필드의 뒷면 카드) 맞바꾸기 목록 — 같은 종류 존끼리, 얻는 가치가 주는 가치보다 클 때만.
    공유 존 · 필드 존 제외, 내성(효과를 받지 않는 카드)은 움직이지 않는다"""
    o = 1 - p; out = []
    for z in ('m', 's'):
        mine = targets(g, p, [x for x in getattr(g.p[p], z) if x is not None and not x.faceup])
        theirs = targets(g, p, [y for y in getattr(g.p[o], z) if y is not None and not y.faceup])
        theirs = sorted([(take_gain(g, p, y), y.uid, y) for y in theirs if take_gain(g, p, y) is not None], key=lambda t: (-t[0], t[1]))
        mine = sorted([(give_cost(g, p, x), x.uid, x) for x in mine], key=lambda t: (t[0], t[1]))
        for (gain, _, y), (cost, _, x) in zip(theirs, mine):
            if gain - cost <= 0.3: break
            out.append((x, y, gain - cost))
    return out


def flip_rank(g, p, x):
    """셔플! 2번: 뒤집을 뒷면 몬스터의 가치 (AI)"""
    if x.controller == p:
        if x.name == BOX and x.owner == p: return VETO   # 1번은 뒷면일 때만 쓸 수 있다
        return 30 + g.atk(x) / 100 + (20 if x.owner != p else 0)   # 가져온 상대 몬스터 · 뒷면이 된 자신의 몬스터
    # 상대 필드: 앞면이 되면 공격 대상이 된다 — 이번 턴 전투로 이길 수 있고, [지속]이 없는 몬스터일 때만
    if not (g.can_declare_attack(p) and g.phase == '진행'): return VETO
    if getattr(x, 'state_check', None) or getattr(x, 'on_event', None) or x.rules or getattr(x, 'atk_mod', None): return VETO
    wall = g.df(x) if x.pos == 'def' else g.atk(x)
    if not any(m.faceup and m.pos == 'atk' and not g.attack_banned(m) and g.atk(m) > wall for m in g.monsters(p)): return VETO
    return 15


@card(SKILL)
def _(c):
    def any_fd(g): return any(x for i in (0, 1) for x in g.p[i].m + g.p[i].s if x and not x.faceup)
    def res1(g, c, p, l):
        plan = shuffle_plan(g, p)   # 처리 시 정한다 (대상 지정 없음)
        if not plan: g.L(f'{c.name} 1번: 뒷면 카드 그대로 (바꿀 자리 없음)', 'sys'); return
        for x, y, _ in plan:
            if swap_cards(g, x, y):
                g.L(f'{c.name} 1번: 뒷면 카드 맞바꿈 — {g.pname(p)} 필드 ← {y.name} / {g.pname(1 - p)} 필드 ← {x.name} (컨트롤 이동)')
    def sc1(g, c, p, ev):
        plan = shuffle_plan(g, p)
        if not plan: return VETO
        return 20 + 15 * sum(d for _, _, d in plan) if main_ok(g, p) else 0
    def fd_mons(g, p): return [x for x in g.monsters(0) + g.monsters(1) if not x.faceup and x.is_monster() and not g.immune(x, p, c)]
    def res2(g, c, p, l):
        cs = fd_mons(g, p)
        if not cs: return
        x = max(cs, key=lambda x: (flip_rank(g, p, x), x.uid))
        flip_up(g, x, c)
    def sc2(g, c, p, ev):
        r = max((flip_rank(g, p, x) for x in fd_mons(g, p)), default=VETO)
        if r <= 0: return VETO
        return r if main_ok(g, p) else 0
    def hand5(g, p): return [x for x in g.p[p].hand if x.is_monster() and x.level >= 5 and g.can_special(x, p)]
    def res3(g, c, p, l):
        summon_best(g, p, hand5(g, p), f'{c.name} 3번')
    def sc3(g, c, p, ev):
        r = best_rank(g, p, hand5(g, p))
        return 45 + r if r is not None and r > 0 else VETO
    c.effects = [
        Effect(1, 'ignition', ('skill',), cond=lambda g, c, p, ev: any_fd(g), res=res1, score=sc1, threat=700, label='뒷면 카드 재배치'),
        Effect(2, 'quick', ('skill',), cond=lambda g, c, p, ev: bool(fd_mons(g, p)), res=res2, score=sc2, threat=300, label='뒷면 몬스터 1장 앞면으로'),
        Effect(3, 'ignition', ('skill',), cond=lambda g, c, p, ev: bool(hand5(g, p)), res=res3, score=sc3, threat=600, label='패의 레벨 5 이상 몬스터 특수소환')]
