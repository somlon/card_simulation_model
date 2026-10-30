"""학습 데이터 공통 규칙 — 출처별 가중치 · 사용자 정리(제외 목록) · 매치 목록. 학습표 기록(jsonl) · 신경망 표본(npz) · 휴리스틱 학습(학습표 기록과 같음) 모두 이 규칙을 쓴다.

출처: 'human'(나 vs AI) · 'ai'(AI끼리 — 관전 · 녹화). 가중치(사용자 지시 2026-10-30): 사람 대전 HUMAN_WEIGHT · AI끼리 AI_WEIGHT.
  학습표 기록을 다시 적용할 때(tables.matchup_table — policy.Table.update 의 w) · 신경망 학습(nn_train — 표본 가중치 sw) ·
  저장소에서 합칠 때(merge_learning.py · merge_nn.py) 모두 같은 값을 쓴다. 출처가 없는 예전 기록은 사람 대전(예전에는 사람 대전만 기록했다).
매치 키: 기록 · 표본 정보의 'match'(같은 매치의 학습표 기록과 신경망 표본이 같은 키), 없으면(예전 것) 학습표 기록 id · 표본 파일 이름.
제외 목록: 사용자 폴더 learning/excluded.json — 사용자가 「학습 데이터 정리」에서 뺀 매치 키. 뺀 매치는 학습 · 내보내기 · GitHub 올리기에서 모두 빠진다.
"""
import json, os

HUMAN_WEIGHT = 3.0   # 사람 vs AI 대전 데이터의 가중치
AI_WEIGHT = 1.0      # AI끼리 대전 데이터의 가중치
SOURCE_LABEL = {'human': '사람 대전', 'ai': 'AI끼리'}
EXCLUDED = ('learning', 'excluded.json')


def record_source(rec):
    """학습표 기록의 출처 — 'source' 가 없는 예전 기록은 사람 대전"""
    return rec.get('source') or 'human'


def sample_source(meta):
    """신경망 표본(index.json 의 매치 정보)의 출처 — 없으면 사람 대전"""
    return (meta or {}).get('source') or 'human'


def weight_of(source):
    return HUMAN_WEIGHT if source == 'human' else AI_WEIGHT


def record_key(rec):
    return rec.get('match') or rec.get('id')


def sample_key(name, meta):
    return (meta or {}).get('match') or name


def excluded_path(user_dir):
    return os.path.join(user_dir, *EXCLUDED)


def read_excluded(user_dir):
    try:
        with open(excluded_path(user_dir), encoding='utf-8') as f: return set(json.load(f).get('keys', []))
    except (OSError, ValueError, AttributeError):
        return set()


def write_excluded(user_dir, keys):
    p = excluded_path(user_dir); os.makedirs(os.path.dirname(p), exist_ok=True); tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump({'keys': sorted(keys)}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
