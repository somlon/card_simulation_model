"""신경망 학습 표본 — 사람 대전(나 vs AI, 「AI 학습」 켬)에서 두 자리의 판단을 drl 표본 형식으로 기록 · 저장 · 불러온다.

판단 하나 = (게임 상태 관측 · 후보 행동 특징 · 고른 후보 · 그 라운드 승패 · 교사 분포).
교사 분포는 대전에 쓰는 로컬 학습표(사람 대전 기록 human_games.jsonl 이 다시 적용된 표)의 후보 값 → softmax(값 / TEACHER_TEMP)
— drl.agent.DRLAI.teacher_values 와 같은 키 · 사전값. 후보가 하나뿐인 판단 · AI의 가치 계산(가정) 안의 판단은 기록하지 않는다.
저장: 사용자 폴더 learning/nn/samples/<시각>_<번호>.npz (drl.buffer 묶음, 매치 1개) + index.json(매치별 표본 수 · 덱).
나누기: 표본 파일 이름은 컴퓨터마다 겹치지 않으므로(시각 + 무작위 번호) 여러 사람의 표본을 모아도 같은 매치는 이름으로 한 번만 센다
(load_sources — 표본 폴더 · 내보낸 zip(nnai.Manager.export) · 저장소의 human_nn 폴더를 함께 읽음).
"""
import io, json, os, time, uuid, zipfile
# numpy 는 쓸 때 불러온다 — numpy 를 못 불러오는 컴퓨터에서도 프로그램의 나머지는 돌아가게(nnai.Manager 가 따로 확인)

TEACHER_TEMP = 0.03   # 교사 분포 온도 (drl.train 기본값 teacher_temp 와 같음)
NOT_NN = ('소환 표시 형식', '시작 패 배분', '시작 패 재배분')
# 신경망 AI(DRLAI)가 신경망으로 고르지 않는 판단 — 표본에 넣지 않는다:
#   소환 표시 형식(학습표 경로 — policy.LearnedAI.choose_summon_pos),
#   시작 패 배분 · 재배분(policy.LearnedAI.choose_split · mulligan_split 이 LearnedAI.choose 직접 — 사람 자리는 HumanAI 가 self.choose 로 물어 감싸개에 걸리므로 빼야 두 자리가 같다)
DIR = ('learning', 'nn', 'samples')


def samples_dir(user_dir):
    return os.path.join(user_dir, *DIR)


def teacher_probs(ai, table, g, p, decision, opts, scale):
    import numpy as np
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
            want = bool(opts) and len(opts) > 1 and getattr(g, 'script', None) is None and not decision.startswith(NOT_NN) and not evaluating()
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
        import numpy as np
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
    d = path if os.path.basename(path) == DIR[-1] else samples_dir(path)
    return load_sources([d])


def iter_sample_files(src):
    """표본 출처 하나 → (파일 이름, 내용 bytes) — 폴더(하위 폴더 포함)의 *.npz · 내보낸 zip 안의 *.npz.
    폴더 안의 zip도 읽는다(GitHub 웹으로 올린 내보내기 파일)"""
    if os.path.isdir(src):
        for root, _, files in sorted(os.walk(src)):
            for n in sorted(files):
                f = os.path.join(root, n)
                if n.endswith('.npz') and os.path.basename(root) == DIR[-1]:
                    with open(f, 'rb') as fh: yield n, fh.read()
                elif n.endswith('.zip'):
                    yield from iter_sample_files(f)
    elif zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            for n in sorted(z.namelist()):
                if n.endswith('.npz') and n.split('/')[-2:-1] == [DIR[-1]]:
                    yield n.split('/')[-1], z.read(n)


def load_sources(srcs):
    """표본 출처 여러 개(폴더 · zip) → (묶음, 표본별 매치 번호, 정보). 같은 이름의 표본 파일(같은 매치)은 한 번만"""
    import numpy as np
    from drl import buffer as B
    packs = []; matches = []; seen = set(); dup = 0
    for src in srcs:
        for n, data in iter_sample_files(src):
            if n in seen:
                dup += 1; continue
            seen.add(n)
            with np.load(io.BytesIO(data), allow_pickle=False) as z:
                P = {'kind': 'game', **{key: z[key] for key in z.files}}
            matches.append(np.full(len(P['idx']), len(packs), np.int32)); packs.append(P)
    if not packs:
        return None, np.zeros(0, np.int32), {'files': 0, 'samples': 0, 'duplicates': dup}
    P = B.concat(packs)
    return P, np.concatenate(matches), {'files': len(packs), 'samples': len(P['idx']), 'duplicates': dup}
