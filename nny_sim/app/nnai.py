"""신경망 AI — 모델 파일 관리 · 대국용 불러오기 · 로컬 학습 작업(백그라운드 스레드).

모델
  기본 모델: 실행 폴더 learned/drl/base_v2/model_best.npz (저장소 data 계열, 배포본에 포함 — 학습표를 교사로 모방 학습 + 자기 대국 PPO)
  내 모델  : 사용자 폴더 learning/nn/model.npz — 「신경망 학습」 버튼으로 만든다. 학습할 때마다 기본 모델에서 시작해
             지금까지 쌓인 표본 전체(사람 대전 · AI끼리 — 출처별 가중치, 사용자가 뺀 매치 제외)로 다시 학습한다
             (학습을 거듭해도 기본 모델에서 멀리 떠내려가지 않게). 이전 내 모델은 backups/ 에 보관.
대국: AI 종류 「신경망 AI」 = drl.agent.DRLAI(학습표 AI의 후보 생성 · 하드 제약은 그대로, 고르기만 신경망). 내 모델이 있으면 내 모델, 없으면 기본 모델.
나누기(학습 기록과 같은 방식): 「신경망 내보내기」 = 표본(사용자가 뺀 매치 제외) · 내 모델 · manifest.json 을 zip 하나로(사용자 폴더 export/) →
  GitHub 웹에서 저장소의 nny_sim/learned/drl/human_nn/ 에 올림, 또는 「GitHub에 올리기」(session.Store.git_upload — data/human-nn-<컴퓨터> 브랜치의
  같은 폴더 아래 <컴퓨터>/). 저장소에서는 merge_nn.py 가 여러 사람의 표본을 모아(같은 매치는 한 번) 기본 모델을 다시 학습한다.
"""
import json, os, shutil, subprocess, sys, threading, time, traceback, zipfile

BASE_REL = ('learned', 'drl', 'base_v2', 'model_best.npz')
NN_DIR = ('learning', 'nn')
KEEP_BACKUPS = 3
MIN_SAMPLES = 50      # 이보다 적으면 학습하지 않는다(한 판도 안 되는 자료로 모델을 바꾸지 않게)
NUMPY_CHECK_TIMEOUT = 120   # numpy 확인(별도 프로세스) 제한 시간(초)
SHARE_REL = ('nny_sim', 'learned', 'drl', 'human_nn')   # 저장소에서 사람 대전 신경망 표본을 모으는 폴더


def numpy_check():
    """numpy 를 이 컴퓨터에서 불러올 수 있는가 — 별도 프로세스로 확인한다(불러오다 프로세스가 통째로 죽는 환경이 있어서: 예 wine 9.0 의 ucrtbase crealf 없음).
    반환: (가능 여부, 안내 문구)"""
    code = 'import numpy as np; print(np.__version__); x = np.ones((8, 8), np.float32); print(float((x @ x).sum()))'
    try:
        r = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=NUMPY_CHECK_TIMEOUT,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError) as ex:
        return False, f'numpy 확인 실패: {ex}'
    if r.returncode != 0 or not r.stdout.strip():
        return False, 'numpy 를 불러올 수 없음' + (f' — {(r.stderr or "").strip()[-300:]}' if r.stderr else f' (종료 코드 {r.returncode})')
    return True, 'numpy ' + r.stdout.split()[0]


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
        self.np_ok = None; self.np_msg = 'numpy 확인 중…'   # None = 확인 중
        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        self.np_ok, self.np_msg = numpy_check()

    def ready(self):
        """신경망 기능(표본 기록 · 신경망 AI · 학습)을 쓸 수 있는가 — 확인이 끝나기 전이면 기다린다"""
        for _ in range(NUMPY_CHECK_TIMEOUT * 10):
            if self.np_ok is not None: break
            time.sleep(0.1)
        return bool(self.np_ok) and os.path.exists(self.base)

    def current_path(self):
        p = local_path(self.user)
        return p if os.path.exists(p) else self.base

    def status(self):
        import nn_samples as NS
        base = self.base
        ok = bool(self.np_ok) and os.path.exists(base)
        return {'available': ok, 'numpy': {'ok': self.np_ok, 'msg': self.np_msg}, 'base_exists': os.path.exists(base),
                'base': model_info(base) if ok else None, 'local': model_info(local_path(self.user)) if ok else None,
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
            if not self.ready(): raise ValueError('신경망 기능을 쓸 수 없습니다: ' + (self.np_msg if not self.np_ok else '기본 신경망 모델이 없습니다'))
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
                raise ValueError(f'표본이 {n}개뿐입니다 — 「AI 학습」을 켜고 대전(나 vs AI · AI끼리)을 해서 표본을 더 모으거나, 「학습 데이터 정리」에서 뺀 매치를 다시 넣어 주세요(최소 {MIN_SAMPLES}개).')
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

    # ── 나누기(내보내기 · GitHub) ──
    def manifest(self, host):
        import nn_samples as NS
        st = NS.stats(self.user); loc = model_info(local_path(self.user)) if self.np_ok else None
        return {'kind': 'nny-sim-nn-share', 'host': host, 'created': time.strftime('%Y-%m-%d %H:%M:%S'),
                'matches': st['matches'], 'samples': st['samples'], 'by_matchup': st['by_matchup'], 'by_source': st['by_source'], 'base': '/'.join(BASE_REL),
                'base_info': {k: v for k, v in (model_info(self.base) or {}).items() if k in ('it', 'eval', 'created', 'stage')} if self.np_ok else None,
                'local_model': {k: v for k, v in (loc or {}).items() if k != 'path'} or None}

    def share_files(self, host):
        """나눌 파일 → [(묶음 안 경로, 원본 경로 또는 내용 bytes)] — 표본 · 표본 목록(사용자가 뺀 매치 제외) · 내 모델(있으면)"""
        import nn_samples as NS
        import learndata as LD
        d = NS.samples_dir(self.user); names, idx = NS.kept_files(self.user); ex = LD.read_excluded(self.user)
        out = []
        for n in sorted(names):
            drop = ex.dropped(LD.sample_key(n, idx[n]), 'n')
            if not drop: out.append((f'{NS.DIR[-1]}/{n}', os.path.join(d, n))); continue
            out.append((f'{NS.DIR[-1]}/{n}', NS.filtered_npz(os.path.join(d, n), drop)))   # 사용자가 뺀 판단은 나누지 않는다
            if idx[n].get('decs'): idx[n] = dict(idx[n], decs=[x for i, x in enumerate(idx[n]['decs']) if i not in drop])
        if names:
            out.append((f'{NS.DIR[-1]}/index.json', json.dumps({n: idx[n] for n in sorted(names)}, ensure_ascii=False, indent=1).encode('utf-8')))
        if os.path.exists(local_path(self.user)): out.append(('model.npz', local_path(self.user)))
        return out

    def export(self, export_dir, host):
        """표본 · 내 모델 · manifest.json → export_dir/신경망표본_<컴퓨터>_<시각>.zip. 표본이 없으면 None"""
        files = self.share_files(host)
        if not any(a.endswith('.npz') and a.startswith('samples/') for a, _ in files): return None
        os.makedirs(export_dir, exist_ok=True)
        out = os.path.join(export_dir, time.strftime(f'신경망표본_{host}_%Y%m%d-%H%M%S.zip'))
        with zipfile.ZipFile(out + '.tmp', 'w', zipfile.ZIP_STORED) as z:   # npz 는 이미 압축됨
            z.writestr('manifest.json', json.dumps(self.manifest(host), ensure_ascii=False, indent=1))
            for arc, src in files:
                if isinstance(src, bytes): z.writestr(arc, src)
                else: z.write(src, arc)
        os.replace(out + '.tmp', out)
        return out

    def place_share(self, dst, host):
        """GitHub에 올리기: 앱의 clone 폴더 dst(= human_nn/<컴퓨터>/)를 지금 표본 · 내 모델 · manifest 로 맞춘다"""
        if os.path.isdir(dst): shutil.rmtree(dst)
        os.makedirs(dst)
        for arc, src in self.share_files(host):
            out = os.path.join(dst, arc); os.makedirs(os.path.dirname(out), exist_ok=True)
            if isinstance(src, bytes):
                with open(out, 'wb') as f: f.write(src)
            else: shutil.copyfile(src, out)
        with open(os.path.join(dst, 'manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(self.manifest(host), f, ensure_ascii=False, indent=1)

    def reset(self):
        """내 모델을 지우고 기본 모델로 — 지운 모델은 backups/ 에 남긴다"""
        if self.busy(): raise ValueError('학습 중에는 되돌릴 수 없습니다')
        cur = local_path(self.user)
        if os.path.exists(cur):
            bk = os.path.join(nn_dir(self.user), 'backups'); os.makedirs(bk, exist_ok=True)
            shutil.move(cur, os.path.join(bk, 'model_' + time.strftime('%Y%m%d_%H%M%S') + '_reset.npz'))
        return self.status()
