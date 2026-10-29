"""신경망 학습 표본 — 사람 대전(나 vs AI, 「AI 학습」 켬)에서 두 자리의 판단을 drl 표본 형식으로 기록 · 저장 · 불러온다.

판단 하나 = (게임 상태 관측 · 후보 행동 특징 · 고른 후보 · 그 라운드 승패 · 교사 분포).
교사 분포는 대전에 쓰는 로컬 학습표(사람 대전 기록 human_games.jsonl 이 다시 적용된 표)의 후보 값 → softmax(값 / TEACHER_TEMP)
— drl.agent.DRLAI.teacher_values 와 같은 키 · 사전값. 후보가 하나뿐인 판단 · AI의 가치 계산(가정) 안의 판단은 기록하지 않는다.
저장: 사용자 폴더 learning/nn/samples/<시각>_<번호>.npz (drl.buffer 묶음, 매치 1개) + index.json(매치별 표본 수 · 덱).
"""
import json, os, time, uuid
import numpy as np

TEACHER_TEMP = 0.03   # 교사 분포 온도 (drl.train 기본값 teacher_temp 와 같음)
DIR = ('learning', 'nn', 'samples')


def samples_dir(user_dir):
    return os.path.join(user_dir, *DIR)


def teacher_probs(ai, table, g, p, decision, opts, scale):
    from policy import prior_of
    me = g.p[p].skill.name; op = g.p[1 - p].skill.name
    base = f'{me} vs {op}|{decision}|'; b = ai.bucket(g, p)
    v = np.array([table.value(base + lab, base + lab + '|' + b, prior_of(h, scale))[0] for lab, h, _ in opts], np.float64)
    z = np.exp((v - v.max()) / TEACHER_TEMP)
    return (z / z.sum()).astype(np.float32)


class Tap:
    """매치 하나의 표본 기록기. attach(ai, seat, table)로 AI 객체의 choose · end_game 을 감싼다(원래 동작은 그대로)"""

    def __init__(self):
        from drl.agent import Recorder
        self.rec = Recorder(); self.rec.begin_match(); self.decisions = 0

    def attach(self, ai, seat, table):
        from drl import features as F, schema as S
        from drl.agent import DRLAI
        from human import evaluating
        orig_choose, orig_end = ai.choose, ai.end_game

        def choose(g, p, decision, opts, *a, **kw):
            want = bool(opts) and len(opts) > 1 and getattr(g, 'script', None) is None and not evaluating()
            if not want:
                return orig_choose(g, p, decision, opts, *a, **kw)
            scale = a[0] if a else kw.get('scale', 40.0)
            obs, _ = F.encode_obs(g, p, decision, oracle=False)
            cands = F.encode_cands(g, p, decision, opts, scale)
            tp = teacher_probs(ai, table, g, p, decision, opts, scale)
            n0 = len(g.dlog)
            out = orig_choose(g, p, decision, opts, *a, **kw)
            if len(g.dlog) > n0:   # LearnedAI._rec 가 (자리, 후보 번호)를 남긴다
                idx = g.dlog[-1][1]
                self.rec.add('game', seat, DRLAI.game_id(g), (obs, None, cands, idx, 0.0, tp, S.parse_decision(decision)[0]))
                self.decisions += 1
            return out

        def end_game(g, p, winner):
            orig_end(g, p, winner)
            if getattr(g, '_drl_gid', None) is not None:
                self.rec.end_game(g._drl_gid, seat, 0.0 if winner is None else (1.0 if winner == p else -1.0))

        ai.choose = choose; ai.end_game = end_game
        return ai

    def save(self, user_dir, winner, meta):
        """매치 끝: 승패가 난 라운드의 표본만 저장 → (파일 이름, 표본 수). 표본이 없으면 (None, 0)"""
        self.rec.end_match(winner)
        P = self.rec.packed().get('game')
        n = 0 if P is None else len(P['idx'])
        if not n:
            return None, 0
        d = samples_dir(user_dir); os.makedirs(d, exist_ok=True)
        name = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6] + '.npz'
        arrays = {k: v for k, v in P.items() if k != 'kind' and not k.startswith('o')}   # 비평가(완전 정보) 칸은 쓰지 않는다
        tmp = os.path.join(d, name + '.tmp')
        with open(tmp, 'wb') as f: np.savez_compressed(f, **arrays)
        os.replace(tmp, os.path.join(d, name))
        idx = read_index(user_dir); idx[name] = dict(meta, samples=n, time=time.strftime('%Y-%m-%d %H:%M'))
        _write_index(user_dir, idx)
        return name, n


def read_index(user_dir):
    p = os.path.join(samples_dir(user_dir), 'index.json')
    try:
        with open(p, encoding='utf-8') as f: return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_index(user_dir, idx):
    p = os.path.join(samples_dir(user_dir), 'index.json'); tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(idx, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def stats(user_dir):
    idx = read_index(user_dir); d = samples_dir(user_dir)
    files = [k for k in idx if os.path.exists(os.path.join(d, k))]
    by = {}
    for k in files:
        key = ' vs '.join(idx[k].get('decks', []))
        e = by.setdefault(key, [0, 0]); e[0] += 1; e[1] += idx[k].get('samples', 0)
    return {'matches': len(files), 'samples': sum(idx[k].get('samples', 0) for k in files),
            'by_matchup': {k: {'matches': a, 'samples': b} for k, (a, b) in sorted(by.items())}, 'dir': d}


def load_all(path):
    """표본 폴더(또는 사용자 폴더의 표본 폴더) → (묶음, 표본별 매치 번호, 정보)"""
    from drl import buffer as B
    d = path if os.path.basename(path) == DIR[-1] else samples_dir(path)
    names = sorted(n for n in os.listdir(d) if n.endswith('.npz')) if os.path.isdir(d) else []
    packs = []; matches = []
    for k, n in enumerate(names):
        with np.load(os.path.join(d, n), allow_pickle=False) as z:
            P = {'kind': 'game', **{key: z[key] for key in z.files}}
        packs.append(P); matches.append(np.full(len(P['idx']), k, np.int32))
    if not packs:
        return None, np.zeros(0, np.int32), {'files': 0, 'samples': 0}
    P = B.concat(packs)
    return P, np.concatenate(matches), {'files': len(names), 'samples': len(P['idx'])}
