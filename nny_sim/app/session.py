"""대전 세션 · 저장소(덱 · 재생 기록 · 재생 목록 · 학습 기록).

LiveMatch: 엔진 스레드에서 Bo3 매치 1개를 돌리며 기록기(viewer/record.py Recorder)로 기록 줄마다 보드 상태를 남긴다.
  - 사람 vs AI: 사람 자리는 HumanAI(판단을 화면에서 받음). 학습을 켜면 AI · 사람의 판단 기록이 라운드마다 대전 표에 반영되고,
    매치가 끝나면 그 갱신을 학습 기록(jsonl)에 덧붙인다 — 다음 대전부터 그대로 쓰인다(프로그램 안에서는 즉시 반영).
  - AI vs AI: 관전 · 녹화용. 학습하지 않는다(match_sim 과 같음).
  매치가 끝나면(그만둔 경우도) 재생 기록으로 저장한다.
Store: 사용자 폴더의 파일들.
"""
import gzip, json, os, random, re, shutil, subprocess, threading, time, traceback, uuid

import deck as D
import match as M
import policy as P
import season as SE
from cards import POOL
from engine import StalledGame

import record as REC
import tables as T
from human import Abort, Bridge, HumanAI

SAFE = re.compile(r'[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ _\-().!]+')


def now(): return time.strftime('%Y-%m-%d %H:%M:%S')


def safe_name(s, default='덱'):
    s = SAFE.sub('', s or '').strip()[:60]
    return s or default


class Store:
    """사용자 폴더: decks/*.deck · replays/<id>.json.gz + index.json · playlists.json · learning/human_games.jsonl · settings.json"""

    DEFAULTS = {'speed': 1, 'reveal': True, 'learn': True, 'hints': False, 'auto_push': False,
                'git_url': 'https://github.com/somlon/card_simulation_model.git', 'git_base': 'data/main', 'git_branch': ''}

    def __init__(self, user_dir, library_dir=None):
        self.dir = user_dir; self.lib = library_dir
        for sub in ('decks', 'replays', 'learning', 'export'): os.makedirs(os.path.join(user_dir, sub), exist_ok=True)
        self.lock = threading.Lock(); self.push_lock = threading.Lock()

    # ── 설정 ──
    def settings(self):
        s = dict(self.DEFAULTS)
        try: s.update(json.load(open(os.path.join(self.dir, 'settings.json'), encoding='utf-8')))
        except (OSError, ValueError): pass
        return s

    def save_settings(self, upd):
        s = self.settings(); s.update({k: v for k, v in upd.items() if k in self.DEFAULTS})
        self._write_json(os.path.join(self.dir, 'settings.json'), s); return s

    @staticmethod
    def _write_json(path, obj):
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    # ── 덱 ──
    def official_decks(self):
        return {f'o:{sk}': dict(d, 이름=d.get('이름') or sk) for sk, d in SE.load_decks().items()}

    def user_decks(self):
        out = {}
        for fn in sorted(os.listdir(os.path.join(self.dir, 'decks'))):
            if not fn.endswith('.deck'): continue
            try:
                d, errs = D.parse(open(os.path.join(self.dir, 'decks', fn), encoding='utf-8').read())
                if not errs and d['스킬']: out['u:' + fn[:-5]] = d
            except OSError: pass
        return out

    def deck(self, did):
        return (self.official_decks() if did.startswith('o:') else self.user_decks()).get(did)

    def deck_list(self):
        out = []
        for kind, ds in (('official', self.official_decks()), ('user', self.user_decks())):
            for did, d in ds.items():
                errs, _ = D.validate(d, policy=False)
                out.append({'id': did, 'kind': kind, 'name': d['이름'], 'skill': d['스킬'], 'valid': not errs,
                            'counts': {s: sum(n for n, _ in d[s]) for s in ('메인', '상급', '전략')}})
        return out

    @staticmethod
    def deck_text(d):
        lines = [f"이름: {d['이름']}", f"스킬: {d['스킬']}"]
        for sec in ('메인', '상급', '전략'):
            lines.append(f'[{sec}]'); lines += [f'{n} {name}' for n, name in d[sec] if n > 0]
        return '\n'.join(lines) + '\n'

    @staticmethod
    def deck_from_json(j):
        d = {'이름': (j.get('이름') or '').strip(), '스킬': j.get('스킬'), '메인': [], '상급': [], '전략': []}
        for sec in ('메인', '상급', '전략'):
            for n, name in j.get(sec, []):
                if int(n) > 0 and name in D.BY_NAME: d[sec].append((int(n), name))
        return d

    def save_deck(self, j, old_id=None):
        d = self.deck_from_json(j)
        errs, warns = D.validate(d, policy=False)
        if errs: return {'ok': False, 'errs': errs, 'warns': warns}
        name = safe_name(d['이름']); d['이름'] = d['이름'] or name
        path = os.path.join(self.dir, 'decks', name + '.deck')
        with open(path, 'w', encoding='utf-8') as f: f.write(self.deck_text(d))
        if old_id and old_id.startswith('u:') and old_id[2:] != name:
            try: os.remove(os.path.join(self.dir, 'decks', old_id[2:] + '.deck'))
            except OSError: pass
        return {'ok': True, 'id': 'u:' + name, 'warns': warns}

    def delete_deck(self, did):
        if not did.startswith('u:'): return False
        try: os.remove(os.path.join(self.dir, 'decks', safe_name(did[2:]) + '.deck')); return True
        except OSError: return False

    # ── 재생 기록 ──
    def _index_path(self, base): return os.path.join(base, 'index.json')

    def _index(self, base):
        try: return json.load(open(self._index_path(base), encoding='utf-8'))
        except (OSError, ValueError): return {}

    def replays(self):
        out = []
        for src, base in (('library', self.lib), ('user', os.path.join(self.dir, 'replays'))):
            if not base or not os.path.isdir(base): continue
            for rid, meta in self._index(base).items(): out.append(dict(meta, id=f'{src[0]}:{rid}', source=src))
        out.sort(key=lambda m: (m['source'] != 'library', m.get('created', '')), reverse=False)
        return out

    def replay(self, rid):
        src, _, key = rid.partition(':')
        base = self.lib if src == 'l' else os.path.join(self.dir, 'replays')
        path = os.path.join(base, safe_name(key, '') + '.json.gz')
        with gzip.open(path, 'rt', encoding='utf-8') as f: return json.load(f)

    @staticmethod
    def replay_meta(rec):
        m = rec['meta']
        return {'title': m.get('title') or ' vs '.join(m['names']), 'names': m['names'], 'decks': m['decks'], 'winner': m.get('winner'),
                'kind': m.get('kind', 'ai'), 'created': m.get('created', ''), 'seed': m.get('seed'), 'frames': len(rec['frames']),
                'rounds': [[r['winner'], r['reason']] for r in m.get('rounds', [])], 'status': m.get('status', 'done')}

    def save_replay(self, rec, base=None, rid=None):
        base = base or os.path.join(self.dir, 'replays')
        rid = rid or time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
        with gzip.open(os.path.join(base, rid + '.json.gz'), 'wt', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, separators=(',', ':'))
        with self.lock:
            idx = self._index(base); idx[rid] = self.replay_meta(rec); self._write_json(self._index_path(base), idx)
        return rid

    def delete_replay(self, rid):
        src, _, key = rid.partition(':')
        if src != 'u': return False
        base = os.path.join(self.dir, 'replays'); key = safe_name(key, '')
        with self.lock:
            idx = self._index(base); idx.pop(key, None); self._write_json(self._index_path(base), idx)
        try: os.remove(os.path.join(base, key + '.json.gz'))
        except OSError: pass
        return True

    # ── 재생 목록 ──
    def playlists(self):
        try: return json.load(open(os.path.join(self.dir, 'playlists.json'), encoding='utf-8'))
        except (OSError, ValueError): return []

    def save_playlists(self, pls):
        clean = [{'name': str(p.get('name') or '재생 목록')[:60], 'items': [str(x) for x in p.get('items', [])][:500]} for p in pls][:100]
        self._write_json(os.path.join(self.dir, 'playlists.json'), clean); return clean

    # ── 학습 기록 ──
    @property
    def log_path(self): return os.path.join(self.dir, 'learning', 'human_games.jsonl')

    def export_learning(self):
        if not os.path.exists(self.log_path): return None
        out = os.path.join(self.dir, 'export', time.strftime('학습데이터_%Y%m%d-%H%M%S.jsonl'))
        shutil.copyfile(self.log_path, out); return out

    def auto_push(self):
        """대전이 끝날 때 자동으로 올리기(설정) — 인터넷 · git 이 없으면 실패를 기록만 하고, 다음 대전 때 쌓인 기록을 통째로 다시 올린다"""
        if not self.push_lock.acquire(blocking=False): return
        try:
            r = self.git_push(); r = {k: v for k, v in r.items() if k != 'log'}; r['time'] = now()
            self._write_json(os.path.join(self.dir, 'learning', 'last_push.json'), r)
        finally: self.push_lock.release()

    def last_push(self):
        try: return json.load(open(os.path.join(self.dir, 'learning', 'last_push.json'), encoding='utf-8'))
        except (OSError, ValueError): return None

    def git_push(self):
        """앱이 관리하는 얕은 clone(사용자 폴더/git)에 학습 기록을 넣고 커밋 · 푸시한다 — 인터넷과 git, GitHub 로그인이 필요"""
        s = self.settings()
        git = shutil.which('git')
        if not git: return {'ok': False, 'msg': 'git 이 설치되어 있지 않습니다. 「내보내기」한 파일을 GitHub 웹에서 올려 주세요.'}
        if not os.path.exists(self.log_path): return {'ok': False, 'msg': '아직 학습 기록이 없습니다.'}
        repo = os.path.join(self.dir, 'git', 'repo'); host = safe_name(os.environ.get('COMPUTERNAME') or os.environ.get('HOSTNAME') or 'pc', 'pc')
        branch = s['git_branch'] or f'data/human-games-{host.lower().replace(" ", "-")}'
        log = []

        def run(*args, cwd=None):
            r = subprocess.run([git, *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
            log.append(f'$ git {" ".join(args)}\n{r.stdout}{r.stderr}'.strip())
            return r.returncode == 0
        try:
            if not os.path.isdir(os.path.join(repo, '.git')):
                os.makedirs(os.path.dirname(repo), exist_ok=True)
                if not run('clone', '--depth', '1', '--filter=blob:none', '--no-checkout', '-b', s['git_base'], s['git_url'], repo):
                    return {'ok': False, 'msg': 'clone 실패 — 인터넷 연결 · 저장소 주소 · 권한을 확인하세요.', 'log': log}
                run('sparse-checkout', 'set', 'nny_sim/learned/human_games', cwd=repo)
            if run('fetch', '--depth', '1', 'origin', branch, cwd=repo):
                run('checkout', '-B', branch, 'FETCH_HEAD', cwd=repo)
            else:
                run('checkout', '-B', branch, cwd=repo)
            dst = os.path.join(repo, 'nny_sim', 'learned', 'human_games'); os.makedirs(dst, exist_ok=True)
            shutil.copyfile(self.log_path, os.path.join(dst, f'{host}.jsonl'))
            run('add', '-A', 'nny_sim/learned/human_games', cwd=repo)
            st = T.log_stats(self.log_path)
            run('-c', 'user.name=NNY Simulator', '-c', 'user.email=nny-simulator@localhost', 'commit', '-m',
                f'사람 대전 학습 기록: {host} — 매치 {st["matches"]}개 · 갱신 {st["updates"]}개', cwd=repo)
            if not run('push', '-u', 'origin', f'HEAD:{branch}', cwd=repo):
                return {'ok': False, 'msg': 'push 실패 — 인터넷 연결 · GitHub 로그인(권한)을 확인하세요.', 'log': log}
            return {'ok': True, 'msg': f'GitHub 브랜치 {branch} 에 올렸습니다.', 'branch': branch, 'log': log}
        except (OSError, subprocess.SubprocessError) as ex:
            return {'ok': False, 'msg': f'git 실행 오류: {ex}', 'log': log}


class LiveMatch:
    """Bo3 매치 1개 — 엔진 스레드 + 기록기. human: 사람 자리(0) 여부"""

    def __init__(self, store, split_dir, decks, names, human=False, seed=None, first=0, learn=True, hints=False, title=''):
        self.store = store; self.split = split_dir; self.decks = decks; self.names = names; self.human = human
        self.seed = random.randrange(2 ** 31) if seed is None else seed; self.first = first
        self.learn = learn and human; self.hints = hints; self.title = title
        self.bridge = Bridge(); self.rec = REC.Recorder(); self.status = 'starting'; self.error = None
        self.result = None; self.replay_id = None; self.learned = 0; self.id = uuid.uuid4().hex[:8]
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self): self.thread.start(); return self

    def skills(self):
        """대전 중 나올 수 있는 스킬(전략 덱의 스킬 카드로 바꿀 수 있음) — 그 몫의 학습표를 불러온다"""
        out = set()
        for d in self.decks:
            out.add(d['스킬']); out.update(n for _, n in d['전략'] if POOL[n]['type'] == '스킬')
        return out

    def _run(self):
        REC.install_hooks()
        meta = {'decks': [d['스킬'] for d in self.decks], 'names': self.names, 'seed': self.seed, 'first': self.first,
                'ai': 'table', 'kind': 'human' if self.human else 'ai', 'created': now(), 'title': self.title}
        rounds = []; mw = None
        try:
            table = T.matchup_table(self.split, self.skills(), logs=[self.store.log_path])
            self.table = table; self.status = 'running'

            def make_ai(d):
                if self.human and d['_seat'] == 0: return HumanAI(d['스킬'], self.bridge, table, learn=self.learn, hints=self.hints)
                return P.LearnedAI(d['스킬'], learn=self.learn, table=table)

            def side_fn(i, decks, wins, rnds, rng, eps, log):   # 사람 덱은 그대로, AI는 학습표 교체 규칙대로
                if self.human and i == 0: return decks[i]
                return M.side_swap(decks[i], decks[1 - i]['스킬'], rng, eps, log, decks[i]['이름'])
            dA = dict(self.decks[0], 이름=self.names[0]); dB = dict(self.decks[1], 이름=self.names[1])
            mw, rounds = M.play_match(dA, dB, self.first, random.Random(self.seed), self.rec, make_ai,
                                      side=True, side_eps=0.0, learn_side=False, side_fn=side_fn)
            self.status = 'done'
        except Abort: self.status = 'aborted'
        except StalledGame as ex: self.status = 'stalled'; self.error = str(ex)
        except Exception:   # 카드 구현 오류 등 — 거기까지 기록은 남긴다
            self.status = 'error'; self.error = traceback.format_exc()[-3000:]
        finally:
            meta.update(winner=mw, status=self.status, rounds=[{'first': r['first'], 'winner': r['winner'], 'reason': r['reason'], 'turns': r['turns']} for r in rounds])
            self.result = meta
            try:
                if self.learn and getattr(self, 'table', None) is not None and self.table.deltas:
                    T.append_log(self.store.log_path, {'decks': meta['decks'], 'human_seat': 0, 'seed': self.seed, 'status': self.status,
                                                       'human_won': (mw == 0) if mw is not None else None,
                                                       'rounds': [[r['winner'], r['reason']] for r in meta['rounds']]}, self.table.deltas)
                    self.learned = len(self.table.deltas)
                    if self.store.settings().get('auto_push'): threading.Thread(target=self.store.auto_push, daemon=True).start()
                if self.rec.frames: self.replay_id = 'u:' + self.store.save_replay(self.replay_dict())
            except Exception:
                self.error = (self.error or '') + '\n저장 오류:\n' + traceback.format_exc()[-2000:]

    def replay_dict(self):
        pool = {}
        for name, _ in self.rec.cards.values():
            d = POOL[name]; pool[name] = {k: d[k] for k in REC.POOL_KEYS if d.get(k) not in (None, '', [])}
        return {'schema': 1, 'meta': self.result or {'names': self.names, 'decks': [d['스킬'] for d in self.decks]},
                'cards': {str(u): v for u, v in self.rec.cards.items()}, 'pool': pool,
                'states': list(self.rec.states), 'frames': self.rec.export_frames()}

    def poll(self, f_from=0, s_from=0, c_from=0):
        rec = self.rec
        frames = rec.export_frames(f_from); states = rec.states[s_from:]
        cards = list(rec.cards.items())[c_from:]
        return {'id': self.id, 'status': self.status, 'frames': frames, 'f_from': f_from, 'states': states, 's_from': s_from,
                'cards': {str(u): v for u, v in cards}, 'c_from': c_from, 'pending': self.bridge.pending if self.human else None,
                'result': self.result if self.status not in ('starting', 'running') else None, 'error': self.error,
                'replay_id': self.replay_id, 'learned': self.learned, 'names': self.names, 'human': self.human}

    def abort(self):
        self.bridge.abort()


class RecordJob:
    """AI vs AI 매치 여러 개를 차례로 녹화(사용자 재생 기록에 저장)"""

    def __init__(self, store, split_dir, pairs, matches=1, seed=None):
        self.store = store; self.split = split_dir; self.pairs = pairs; self.n = matches
        self.seed = random.randrange(2 ** 31) if seed is None else seed
        self.done = []; self.total = len(pairs) * matches; self.status = 'running'; self.current = None; self.stop = False
        self.id = uuid.uuid4().hex[:8]
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        k = 0
        for (da, db), names in self.pairs:
            for j in range(self.n):
                if self.stop: break
                m = LiveMatch(self.store, self.split, [da, db], names, human=False, seed=self.seed + k, first=k % 2,
                              title=f'{names[0]} vs {names[1]}')
                self.current = m; m._run(); k += 1
                self.done.append({'replay_id': m.replay_id, 'status': m.status, 'winner': m.result and m.result.get('winner')})
        self.status = 'stopped' if self.stop else 'done'; self.current = None

    def info(self):
        return {'id': self.id, 'status': self.status, 'done': len(self.done), 'total': self.total, 'items': self.done,
                'current': self.current.id if self.current else None}
