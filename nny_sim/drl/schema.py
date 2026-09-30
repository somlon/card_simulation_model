"""특징 스키마: 카드 어휘 · 판단 종류 · 행동 종류 · 특징 크기.

모델 파일에는 schema_meta()를 함께 저장하고, 불러올 때 check_meta()로 현재 코드와 같은지 검사한다.
(R1 버그 교훈: 학습 당시와 다른 특징으로 판정하면 조용히 틀린다 → 다르면 바로 오류.)
해시는 파이썬 hash()가 아니라 zlib.crc32로 계산한다 — 프로세스마다 값이 바뀌지 않게.
"""
import json, zlib
from cards import POOL

SCHEMA_VERSION = 1

# ── 카드 어휘 ── 0 = 빈칸(PAD), 1 = 알 수 없음(UNK: 상대의 뒷면 카드 등), 2~ = 카드 풀 이름순
PAD, UNK = 0, 1
VOCAB = sorted(POOL)
CARD_ID = {n: i + 2 for i, n in enumerate(VOCAB)}
N_CARDS = len(VOCAB) + 2
SKILLS = sorted(n for n, c in POOL.items() if c['type'] == '스킬')
SKILL_IX = {n: i for i, n in enumerate(SKILLS)}


def cid(name):
    return CARD_ID.get(name, UNK)


# ── 판단 종류 ── LearnedAI.choose(decision=...)의 문자열 앞부분으로 구분한다
DECISION_TYPES = ('드로우 덱', '멀리건', '서치', '인카운터 분기', '대상', '버릴 카드', '번식지', '트리거',
                  '대응', '우선권', '진행 행동', '정비 행동', '공격', '기타')
DT_IX = {d: i for i, d in enumerate(DECISION_TYPES)}
N_DSUB = 8   # 판단 세부(서치 이유 · 대상 목적 · 효과 번호 등)의 해시 칸 수


def crc(s, n):
    return zlib.crc32(s.encode('utf-8')) % n


def parse_decision(decision):
    """판단 문자열 → (종류 번호, 세부 해시 칸, 판단 대상 카드 이름 또는 None)"""
    for d in DECISION_TYPES[:-1]:
        if decision.startswith(d):
            rest = decision[len(d):].lstrip(':(')
            card = None
            if d in ('멀리건', '트리거'):
                card = rest.split('#')[0]
                card = card if card in CARD_ID else None
            return DT_IX[d], crc(rest, N_DSUB), card
    return DT_IX['기타'], crc(decision, N_DSUB), None


# ── 행동 종류 ── 후보 라벨(LearnedAI가 만든 문자열)과 판단 종류로 구분한다
ACTION_KINDS = ('종료', '소환', '수비 소환', '특수 일반소환', '발동', '세트', '수비 표시로', '공격 표시로',
                '직접 공격', '몬스터 공격', '유지', '되돌림', '메인', '상급', '지속 마법', '시아·시엘 서치',
                '견제', '엔진', '예', '아니오', '자신 카드', '상대 카드', '카드', '대응 카드',
                '교체 멈춤', '카드 교체', '스킬 교체', '기타')
AK_IX = {a: i for i, a in enumerate(ACTION_KINDS)}
_PREFIX = (('수비 소환:', '수비 소환'), ('특수 일반소환:', '특수 일반소환'), ('소환:', '소환'), ('발동:', '발동'),
           ('세트:', '세트'), ('수비 표시로:', '수비 표시로'), ('공격 표시로:', '공격 표시로'),
           ('자:', '자신 카드'), ('상:', '상대 카드'))
_EXACT = {'종료': '종료', '패스': '종료', '공격 종료': '종료', '안 함': '아니오', '유지': '유지', '되돌림': '되돌림',
          '메인': '메인', '상급': '상급', '지속 마법': '지속 마법', '시아·시엘 서치': '시아·시엘 서치',
          '견제': '견제', '엔진': '엔진'}


def action_kind(label, dtype):
    """후보 라벨 → 행동 종류 번호"""
    if label in _EXACT:
        return AK_IX[_EXACT[label]]
    if label == '발동' and dtype == DT_IX['트리거']:
        return AK_IX['예']
    for pre, k in _PREFIX:
        if label.startswith(pre):
            return AK_IX[k]
    if '→' in label:
        return AK_IX['직접 공격'] if label.endswith('→직접') else AK_IX['몬스터 공격']
    if dtype in (DT_IX['대응'], DT_IX['우선권']):
        return AK_IX['대응 카드']
    if label in CARD_ID:
        return AK_IX['카드']
    return AK_IX['기타']


# ── 게임 관측 특징 크기 ──
PHASES = ('준비', '진행', '전투', '정비', '종료')
ZONES = ('hand', 'm', 's', 'shared', 'fieldz', 'grave', 'banish', 'main', 'upper', 'skill')
N_SLOT = 6            # 한쪽의 몬스터 칸(5 + 공유 존) · 마법 칸(5 + 필드 존)
F_MON = 12            # 몬스터 칸 수치 특징
F_SPL = 4             # 마법 칸 수치 특징
BAGS_ACTOR = ('내 패', '내 묘지', '상대 묘지', '내 제외', '상대 제외', '내 남은 덱', '내 체인', '상대 체인')
BAGS_ORACLE = BAGS_ACTOR + ('상대 패', '상대 남은 덱', '상대 뒷면 카드')   # 비평가 전용(학습 시에만)
G_DIM = 104           # 전역 수치 특징 (features.global_feats가 이 길이를 만든다 — 테스트로 검사)
A_DIM = len(ACTION_KINDS) + 32   # 행동 수치 특징: 종류 원핫 + 수치 32

# ── 전략 덱 교체 관측 ──
SIDE_BAGS_ACTOR = ('내 활성 덱', '내 전략 덱')
SIDE_BAGS_ORACLE = SIDE_BAGS_ACTOR + ('상대 활성 덱',)
SIDE_G_DIM = 2 * len(SKILLS) + 7    # 스킬 원핫 ×2 + 라운드 · 승수 · 직전 패배 · 단계 · 스킬 교체 여부 · 빼기 단계
SIDE_A_DIM = 9                      # 종류 원핫 4(멈춤 · 넣기 · 스킬 · 빼기) + 수치 5


def schema_meta():
    """해시는 카드 어휘를 뺀 나머지로 계산한다. 카드 어휘는 따로 저장해 두고, 카드 풀이 바뀌면 번호를 다시 매핑한다(card_remap)."""
    meta = dict(version=SCHEMA_VERSION, skills=SKILLS, decision_types=DECISION_TYPES, action_kinds=ACTION_KINDS,
                n_dsub=N_DSUB, n_slot=N_SLOT, f_mon=F_MON, f_spl=F_SPL, bags_actor=BAGS_ACTOR, bags_oracle=BAGS_ORACLE,
                g_dim=G_DIM, a_dim=A_DIM, side_bags_actor=SIDE_BAGS_ACTOR, side_bags_oracle=SIDE_BAGS_ORACLE,
                side_g_dim=SIDE_G_DIM, side_a_dim=SIDE_A_DIM)
    meta = json.loads(json.dumps(meta, ensure_ascii=False))   # 튜플 → 목록 (저장본과 같은 모양으로)
    meta['hash'] = zlib.crc32(json.dumps(meta, ensure_ascii=False, sort_keys=True).encode('utf-8'))
    meta['vocab'] = list(VOCAB)
    return meta


class SchemaMismatch(ValueError):
    pass


def check_meta(saved):
    """저장된 스키마가 현재 코드와 같은지 검사한다. 다르면 어느 항목이 다른지 알려 주는 오류.
    반환: 카드 번호 매핑 배열(현재 번호 → 모델 번호) 또는 None(어휘가 같음).
    모델이 모르는 새 카드는 UNK로 보인다 — 동작은 하지만 그 카드에 대해서는 다시 학습하는 편이 좋다."""
    cur = schema_meta()
    if saved.get('hash') != cur['hash']:
        diff = [k for k in cur if k not in ('hash', 'vocab') and json.dumps(saved.get(k), ensure_ascii=False) != json.dumps(cur[k], ensure_ascii=False)]
        raise SchemaMismatch(f'DRL 모델의 특징 스키마가 현재 코드와 다름: {diff} — 이 코드로 다시 학습해야 함')
    if list(saved.get('vocab', [])) == cur['vocab']:
        return None
    mid = {n: i + 2 for i, n in enumerate(saved['vocab'])}
    import numpy as np
    remap = np.full(N_CARDS, UNK, dtype=np.int64); remap[PAD] = PAD
    for n, i in CARD_ID.items():
        remap[i] = mid.get(n, UNK)
    return remap
