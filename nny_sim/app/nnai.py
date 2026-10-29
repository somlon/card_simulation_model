"""신경망 AI — 모델 파일 관리 · 대국용 불러오기 · 로컬 학습 작업(백그라운드 스레드).

모델
  기본 모델: 실행 폴더 learned/drl/base_v2/model_best.npz (저장소 data 계열, 배포본에 포함 — 학습표를 교사로 모방 학습 + 자기 대국 PPO)
  내 모델  : 사용자 폴더 learning/nn/model.npz — 「신경망 학습」 버튼으로 만든다. 학습할 때마다 기본 모델에서 시작해
             지금까지 쌓인 사람 대전 표본 전체로 다시 학습한다(학습을 거듭해도 기본 모델에서 멀리 떠내려가지 않게). 이전 내 모델은 backups/ 에 보관.
대국: AI 종류 「신경망 AI」 = drl.agent.DRLAI(학습표 AI의 후보 생성 · 하드 제약은 그대로, 고르기만 신경망). 내 모델이 있으면 내 모델, 없으면 기본 모델.
"""
import json, os, shutil, threading, time, traceback

BASE_REL = ('learned', 'drl', 'base_v2', 'model_best.npz')
NN_DIR = ('learning', 'nn')
KEEP_BACKUPS = 3
MIN_SAMPLES = 50      # 이보다 적으면 학습하지 않는다(한 판도 안 되는 자료로 모델을 바꾸지 않게)


def base_path(sim, override=None):
    return override or os.path.join(sim, *BASE_REL)


def nn_dir(user_dir):
    return os.path.join(user_dir, *NN_DIR)


def local_path(user_dir):
    return os.path.join(nn_dir(user_dir), 'model.npz')


def model_info(path):
    if not os.path.exists(path):
        return None
    from drl import model as MD
    try:
        _, meta = MD.load_arrays(path)
    except Exception as ex:
        return {'path': path, 'error': str(ex)}
    t = meta.get('train') or {}; ev = meta.get('eval')
    brief = {k: {kk: v[kk] for kk in ('win', 'ci95', 'games') if kk in v} for k, v in ev.items() if isinstance(v, dict)} if isinstance(ev, dict) else None
    return {'path': path, 'stage': meta.get('stage'), 'created': meta.get('created'), 'samples': t.get('samples'), 'matches': t.get('matches'),
            'before': t.get('before'), 'after': t.get('after'), 'eval': brief, 'it': meta.get('it')}


def load_actor(path):
    from drl import model as MD
    return MD.load_actor(path)[0]


def make_ai(skill, actor, table):
    """신경망 AI — 학습표 AI(LearnedAI)의 후보 생성 · 지침은 그대로, 판단 고르기만 신경망. 시작 패 배분 · 표시 형식 등 DRL 판단 종류가 아닌 것은 학습표로"""
    from drl.agent import DRLAI
    ai = DRLAI(skill, actor=actor, mode='greedy')
    ai.table = table
    return ai


class Manager:
    def __init__(self, sim, user_dir, base=None):
        self.sim = sim; self.user = user_dir; self.base = base_path(sim, base)
        self.job = None; self.lock = threading.Lock()

    def current_path(self):
        p = local_path(self.user)
        return p if os.path.exists(p) else self.base

    def status(self):
        import nn_samples as NS
        base = self.base
        return {'available': os.path.exists(base), 'base': model_info(base), 'local': model_info(local_path(self.user)),
                'using': 'local' if os.path.exists(local_path(self.user)) else 'base', 'samples': NS.stats(self.user),
                'job': self.job_info(), 'min_samples': MIN_SAMPLES}

    def job_info(self):
        j = self.job
        if not j: return None
        return {k: j[k] for k in ('status', 'progress', 'msg', 'started', 'log', 'error', 'epochs') if k in j}

    def busy(self):
        return bool(self.job and self.job['status'] == 'running')

    def start(self, epochs=None):
        import nn_train as NT
        with self.lock:
            if self.busy(): raise ValueError('이미 학습 중입니다')
            if not os.path.exists(self.base): raise ValueError('기본 신경망 모델이 없습니다')
            self.job = {'status': 'running', 'progress': 0.0, 'msg': '표본 불러오는 중…', 'started': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'epochs': int(epochs or NT.EPOCHS), 'stop': threading.Event()}
        threading.Thread(target=self._run, daemon=True).start()
        return self.job_info()

    def stop(self):
        if self.busy(): self.job['stop'].set()
        return self.job_info()

    def _run(self):
        import nn_samples as NS, nn_train as NT
        from drl import model as MD
        j = self.job
        try:
            P, matches, info = NS.load_all(self.user)
            n = 0 if P is None else len(P['idx'])
            if n < MIN_SAMPLES:
                raise ValueError(f'표본이 {n}개뿐입니다 — 「AI 학습」을 켜고 나 vs AI 대전을 해서 표본을 더 모아 주세요(최소 {MIN_SAMPLES}개).')
            arrays, _ = MD.load_arrays(self.base)
            j['msg'] = f'학습 중 — 매치 {info["files"]}개 · 판단 {n}개'

            def prog(f, m):
                j['progress'] = round(f, 4); j['msg'] = f'학습 중 — 에포크 {m["epoch"]}/{j["epochs"]} · 손실 {m["loss"]}'
            w, log = NT.train(arrays, P, matches, epochs=j['epochs'], progress=prog, stop=j['stop'].is_set)
            d = nn_dir(self.user); os.makedirs(d, exist_ok=True); cur = local_path(self.user)
            if os.path.exists(cur):
                bk = os.path.join(d, 'backups'); os.makedirs(bk, exist_ok=True)
                shutil.copy2(cur, os.path.join(bk, 'model_' + time.strftime('%Y%m%d_%H%M%S') + '.npz'))
                for old in sorted(os.listdir(bk))[:-KEEP_BACKUPS]: os.remove(os.path.join(bk, old))
            MD.save_model(cur, w, {'stage': 'local', 'created': time.strftime('%Y-%m-%d %H:%M'), 'base': '/'.join(BASE_REL), 'train': log})
            j['log'] = log; j['progress'] = 1.0
            j['status'] = 'stopped' if log.get('stopped') else 'done'
            j['msg'] = ('멈춤 — 그때까지 가장 좋았던 가중치를 저장했습니다' if log.get('stopped') else '학습 완료 — 다음 「신경망 AI」 대전부터 내 모델을 씁니다')
        except Exception as ex:
            j['status'] = 'error'; j['msg'] = str(ex) if isinstance(ex, ValueError) else '학습 오류'
            j['error'] = traceback.format_exc()[-2000:]

    def reset(self):
        """내 모델을 지우고 기본 모델로 — 지운 모델은 backups/ 에 남긴다"""
        if self.busy(): raise ValueError('학습 중에는 되돌릴 수 없습니다')
        cur = local_path(self.user)
        if os.path.exists(cur):
            bk = os.path.join(nn_dir(self.user), 'backups'); os.makedirs(bk, exist_ok=True)
            shutil.move(cur, os.path.join(bk, 'model_' + time.strftime('%Y%m%d_%H%M%S') + '_reset.npz'))
        return self.status()
