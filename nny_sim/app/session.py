"""대전 세션 · 저장소(덱 · 재생 기록 · 재생 목록 · 학습 기록).

LiveMatch: 엔진 스레드에서 Bo3 매치 1개를 돌리며 기록기(viewer/record.py Recorder)로 기록 줄마다 보드 상태를 남긴다.
  - 사람 vs AI: 사람 자리는 HumanAI(판단을 화면에서 받음). 학습을 켜면 AI · 사람의 판단 기록이 라운드마다 대전 표에 반영되고,
    매치가 끝나면 그 갱신을 학습 기록(jsonl)에 덧붙인다 — 다음 대전부터 그대로 쓰인다(프로그램 안에서는 즉시 반영).
  - AI vs AI: 관전 · 녹화용. 학습하지 않는다(match_sim 과 같음).
  매치가 끝나면(그만둔 경우도) 재생 기록으로 저장한다.
Store: 사용자 폴더의 파일들.
"""
import gzip, json, os, random, re, secrets, shutil, subprocess, threading, time, traceback, uuid

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

    DEFAULTS = {'speed': 1, 'reveal': True, 'learn': True, 'hints': False, 'auto_push': False, 'push_games': False,
                'git_url': 'https://github.com/somlon/card_simulation_model.git', 'git_base': 'data/main', 'git_branch': ''}

    def __init__(self, user_dir, library_dir=None):
        self.dir = user_dir; self.lib = library_dir
        for sub in ('decks', 'replays', 'learning', 'export'): os.makedirs(os.path.join(user_dir, sub), exist_ok=True)
        self.lock = threading.Lock(); self.push_lock = threading.Lock(); self.game_push_lock = threading.Lock()

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
                'rounds': [[r['winner'], r['reason']] for r in m.get('rounds', [])], 'status': m.get('status', 'done'),
                'memos': len(rec.get('memos') or []), 'chat': len(rec.get('chat') or [])}

    def save_replay(self, rec, base=None, rid=None):
        base = base or os.path.join(self.dir, 'replays')
        rid = rid or time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
        with gzip.open(os.path.join(base, rid + '.json.gz'), 'wt', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, separators=(',', ':'))
        with self.lock:
            idx = self._index(base); idx[rid] = self.replay_meta(rec); self._write_json(self._index_path(base), idx)
        return rid

    def add_memo(self, rid, memos):
        """기능 v1⑤ 룰미스 메모 — 체인·효과 발동 로그 줄(프레임 번호 i)에 매치가 끝난 뒤 묶어 붙인다(관전자도 가능).
        새 저장소를 만들지 않고 기존 재생 기록(.json.gz)의 `memos` 필드에 끼워 넣는다 — 내 기록(u:)에만, 겹치는 메모는 건너뜀."""
        src, _, key = rid.partition(':')
        if src != 'u': return {'ok': False, 'msg': '내 기록에만 메모를 달 수 있습니다.'}
        key = safe_name(key, '')
        base = os.path.join(self.dir, 'replays'); path = os.path.join(base, key + '.json.gz')
        if not key or not os.path.isfile(path): return {'ok': False, 'msg': '기록을 찾을 수 없습니다.'}
        with self.lock:
            with gzip.open(path, 'rt', encoding='utf-8') as f: rec = json.load(f)
            have = rec.setdefault('memos', [])
            seen = {(m.get('i'), m.get('text'), m.get('who')) for m in have}
            added = 0
            for m in (memos or [])[:50]:
                try: i = int(m.get('i'))
                except (TypeError, ValueError): continue
                text = str(m.get('text') or '').strip()[:300]
                if not text: continue
                who = str(m.get('who') or '').strip()[:40]
                sig = (i, text, who)
                if sig in seen: continue
                seen.add(sig)
                try: t = int(m.get('t'))
                except (TypeError, ValueError): t = int(time.time() * 1000)
                have.append({'i': i, 'text': text, 'who': who, 't': t}); added += 1
            if added:
                with gzip.open(path, 'wt', encoding='utf-8') as f: json.dump(rec, f, ensure_ascii=False, separators=(',', ':'))
                idx = self._index(base); meta = idx.get(key)
                if meta is not None: meta['memos'] = len(have); self._write_json(self._index_path(base), idx)
                if self.settings().get('push_games'): threading.Thread(target=self.push_game, args=(rid,), daemon=True).start()
        return {'ok': True, 'added': added, 'total': len(have)}

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

    def last_game_push(self):
        try: return json.load(open(os.path.join(self.dir, 'learning', 'last_game_push.json'), encoding='utf-8'))
        except (OSError, ValueError): return None

    def push_game(self, rid):
        """기능 v1⑥ 기보 수집 — 매치가 끝날 때(메모 없이도)와 메모가 새로 붙을 때마다 online/data-games 에 올린다.
        git_push와 같은 모양(얕은 clone · 실패는 조용히 기록만, 다음 기회에 다시 통째로 시도) — 하마치만 있고 인터넷이
        끊긴 경우에도 매치 자체가 막히면 안 되므로 호출하는 쪽에서 항상 스레드로 띄운다."""
        if not self.game_push_lock.acquire(blocking=False): return
        try:
            r = self._push_game(rid); r = {k: v for k, v in r.items() if k != 'log'}; r['time'] = now(); r['rid'] = rid
            self._write_json(os.path.join(self.dir, 'learning', 'last_game_push.json'), r)
        finally: self.game_push_lock.release()

    def _push_game(self, rid):
        git = shutil.which('git')
        if not git: return {'ok': False, 'msg': 'git 이 설치되어 있지 않습니다.'}
        src, _, key = rid.partition(':')
        if src != 'u': return {'ok': False, 'msg': '내 기록만 올릴 수 있습니다.'}
        key = safe_name(key, '')
        path = os.path.join(self.dir, 'replays', key + '.json.gz')
        if not key or not os.path.isfile(path): return {'ok': False, 'msg': '기록을 찾을 수 없습니다.'}
        with gzip.open(path, 'rt', encoding='utf-8') as f: rec = json.load(f)
        s = self.settings(); branch = 'online/data-games'
        repo = os.path.join(self.dir, 'git', 'games'); host = safe_name(os.environ.get('COMPUTERNAME') or os.environ.get('HOSTNAME') or 'pc', 'pc')
        log = []

        def run(*args, cwd=None):
            r = subprocess.run([git, *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
            log.append(f'$ git {" ".join(args)}\n{r.stdout}{r.stderr}'.strip())
            return r.returncode == 0, r.stdout.strip()

        try:
            if not os.path.isdir(os.path.join(repo, '.git')):
                os.makedirs(os.path.dirname(repo), exist_ok=True)
                ok, _ = run('clone', '--depth', '1', '--filter=blob:none', '--no-checkout', '-b', branch, s['git_url'], repo)
                if not ok: return {'ok': False, 'msg': 'clone 실패 — 인터넷 연결 · 저장소 주소 · 권한을 확인하세요.', 'log': log}
                run('sparse-checkout', 'set', 'games', 'index.json', cwd=repo)
            ok, _ = run('fetch', '--depth', '1', 'origin', branch, cwd=repo)
            if ok: run('checkout', '-B', branch, 'FETCH_HEAD', cwd=repo)
            else: run('checkout', '-B', branch, cwd=repo)
            os.makedirs(os.path.join(repo, 'games'), exist_ok=True)
            shutil.copyfile(path, os.path.join(repo, 'games', key + '.json.gz'))
            idx_path = os.path.join(repo, 'index.json')
            try: idx = json.load(open(idx_path, encoding='utf-8'))
            except (OSError, ValueError): idx = {}
            meta = self.replay_meta(rec); meta['host'] = host
            prev = idx.get(key) or {}
            meta['commit'] = prev.get('commit'); meta['processed'] = prev.get('processed', False)
            if idx.get(key) == meta: return {'ok': True, 'msg': '이미 최신입니다.', 'branch': branch, 'log': log}
            idx[key] = meta
            self._write_json(idx_path, idx)
            run('add', '-A', 'games', 'index.json', cwd=repo)
            ok, _ = run('-c', 'user.name=NNY Simulator', '-c', 'user.email=nny-simulator@localhost', 'commit', '-m',
                        f'기보 수집: {host} — {meta["title"]} (메모 {meta["memos"]}개)', cwd=repo)
            if not ok: return {'ok': True, 'msg': '올릴 내용 없음(이미 최신)', 'branch': branch, 'log': log}
            if not run('push', '-u', 'origin', f'HEAD:{branch}', cwd=repo)[0]:
                return {'ok': False, 'msg': 'push 실패 — 인터넷 연결 · GitHub 로그인(권한)을 확인하세요.', 'log': log}
            # 1순위(수정 고리)가 기보 메타의 커밋 해시로 재현하므로, 방금 올라간 실제 해시를 다시 적어 둔다(두 번째 커밋 — 자기 자신을
            # 가리키는 해시는 같은 커밋에 미리 넣을 수 없어 한 번 올린 뒤 알아낸 해시를 뒤따르는 커밋에 적는다).
            ok, h = run('rev-parse', 'HEAD', cwd=repo)
            if ok and h and idx[key].get('commit') != h:
                idx[key]['commit'] = h; self._write_json(idx_path, idx)
                run('add', '-A', 'index.json', cwd=repo)
                if run('-c', 'user.name=NNY Simulator', '-c', 'user.email=nny-simulator@localhost', 'commit', '-m',
                       f'기보 수집 — 커밋 해시 기록: {key} ({h[:8]})', cwd=repo)[0]:
                    run('push', '-u', 'origin', f'HEAD:{branch}', cwd=repo)
            return {'ok': True, 'msg': f'GitHub 브랜치 {branch} 에 올렸습니다.', 'branch': branch, 'log': log}
        except (OSError, subprocess.SubprocessError) as ex:
            return {'ok': False, 'msg': f'git 실행 오류: {ex}', 'log': log}


class LiveMatch:
    """Bo3 매치 1개 — 엔진 스레드 + 기록기. human: 사람 자리 여부 — bool(좌석0만) 또는 (좌석0, 좌석1) 튜플(사람vs사람).
    사람 자리마다 Bridge 가 따로 있다(self.bridges) — 사람vs사람이면 좌석마다 참가 키(self.keys)로 poll · answer 를 묶는다"""

    def __init__(self, store, split_dir, decks, names, human=False, seed=None, first=0, learn=True, hints=False, title='', chat_fn=None):
        self.store = store; self.split = split_dir; self.decks = decks; self.names = names
        self.humans = tuple(bool(x) for x in human) if isinstance(human, (tuple, list)) else (bool(human), False)
        self.human = any(self.humans)   # 사람 자리가 하나 이상 있는가(기존 코드 호환)
        self.seed = random.randrange(2 ** 31) if seed is None else seed; self.first = first
        self.learn = learn and self.human; self.hints = hints; self.title = title
        self.bridges = [Bridge(), Bridge()]; self.keys = [secrets.token_hex(8) if h else None for h in self.humans]
        self.rec = REC.Recorder(); self.status = 'starting'; self.error = None
        self.result = None; self.replay_id = None; self.learned = 0; self.id = uuid.uuid4().hex[:8]
        # 인게임 메신저(수다+로그 수집) — 방 전체 채팅 중 이 매치가 떠 있던 구간(start_ts~end_ts)만 기보에 묶어 올린다.
        # chat_fn(start_ts, end_ts) 는 App.chat_between 재사용(새 저장소 없음) — 안 주어지면(RecordJob 등) 그냥 안 붙는다.
        self.chat_fn = chat_fn; self.start_ts = time.time(); self.end_ts = None
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
                seat = d['_seat']
                if self.humans[seat]: return HumanAI(d['스킬'], self.bridges[seat], table, learn=self.learn, hints=self.hints)
                return P.LearnedAI(d['스킬'], learn=self.learn, table=table)

            def side_fn(i, decks, wins, rnds, rng, eps, log):   # 사람 덱은 화면에서 교체, AI는 학습표 교체 규칙대로
                if self.humans[i]: return human_side(self.bridges[i], decks, i, wins, len(rnds) + 1, log)
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
                if self.rec.frames:
                    self.end_ts = time.time()
                    rec = self.replay_dict()
                    if self.chat_fn:   # 매치가 떠 있던 구간(start_ts~end_ts)에 온 채팅만 — chat_between 이 그 필터를 함
                        try: rec['chat'] = self.chat_fn(self.start_ts, self.end_ts)
                        except Exception: pass
                    self.replay_id = 'u:' + self.store.save_replay(rec)
                    if self.store.settings().get('push_games'):
                        threading.Thread(target=self.store.push_game, args=(self.replay_id,), daemon=True).start()
            except Exception:
                self.error = (self.error or '') + '\n저장 오류:\n' + traceback.format_exc()[-2000:]

    def replay_dict(self):
        pool = {}
        for name, _ in self.rec.cards.values():
            d = POOL[name]; pool[name] = {k: d[k] for k in REC.POOL_KEYS if d.get(k) not in (None, '', [])}
        return {'schema': 1, 'meta': self.result or {'names': self.names, 'decks': [d['스킬'] for d in self.decks]},
                'cards': {str(u): v for u, v in self.rec.cards.items()}, 'pool': pool,
                'states': list(self.rec.states), 'frames': self.rec.export_frames()}

    def poll(self, seat=None, key=None, f_from=0, s_from=0, c_from=0, spectate=False):
        rec = self.rec
        frames = rec.export_frames(f_from); states = rec.states[s_from:]
        cards = list(rec.cards.items())[c_from:]
        pending = None
        if not spectate:   # spectate=True: 관전 화면의 명시적 요청 — 사람 자리가 하나뿐인 매치(기존 사람vsAI)라도 자동 귀속하지 않는다
            human_seats = [i for i, h in enumerate(self.humans) if h]
            if seat is None and len(human_seats) == 1: seat = human_seats[0]   # 사람 자리가 하나뿐이면(기존 사람vsAI) 키 없이도 그 자리
            if seat is not None and self.humans[seat] and (len(human_seats) == 1 or key == self.keys[seat]):
                pending = self.bridges[seat].pending
        else:
            seat = None
        return {'id': self.id, 'status': self.status, 'frames': frames, 'f_from': f_from, 'states': states, 's_from': s_from,
                'cards': {str(u): v for u, v in cards}, 'c_from': c_from, 'pending': pending, 'seat': seat,
                'result': self.result if self.status not in ('starting', 'running') else None, 'error': self.error,
                'replay_id': self.replay_id, 'learned': self.learned, 'names': self.names, 'human': self.human, 'humans': list(self.humans)}

    def answer(self, rid, idx, seat=None, key=None):
        human_seats = [i for i, h in enumerate(self.humans) if h]
        if seat is None and len(human_seats) == 1: seat = human_seats[0]
        if seat is None or not self.humans[seat]: return False
        if len(human_seats) > 1 and key != self.keys[seat]: return False   # 사람vs사람: 자기 참가 키 없이는 상대 자리에 답할 수 없다
        return self.bridges[seat].reply(rid, idx)

    def abort(self):
        for b in self.bridges: b.abort()


def side_options(act, st, skill):
    """지금 덱에서 할 수 있는 교체 하나하나 — match.py 교체 규칙 그대로(전략 덱 카드 1:1 · 같은 덱 종류 · 동명 3장 · 스킬 태그 · 고정 카드 제외,
    스킬 카드는 새 스킬로 활성 덱 전부를 쓸 수 있을 때만)"""
    out = []
    for i in M.swap_ins(act, st, skill):
        for o in M.swap_outs(act, i):
            out.append({'label': f'「{o}」 → 「{i}」', 'kind': 'card', 'out': o, 'in': i})
    for n in M.skill_swaps(act, st, skill):
        out.append({'label': f'스킬 「{skill}」 → 「{n}」', 'kind': 'skill', 'out': skill, 'in': n})
    return out


def human_side(bridge, decks, i, wins, rnd, log):
    """라운드 사이 사람의 전략 덱 교체 — 할 수 있는 교체 목록을 서버가 만들어 보내고(Bridge 요청 kind 'side'), 하나씩 받아 적용한다.
    「교체 끝」이면 덱 규칙(deck.validate)을 다시 확인해 새 덱을 돌려주고, 기록에 side_swap 과 같은 'side' 줄을 남긴다"""
    deck = decks[i]; base = (M.counts_of(deck), M.counts_of(deck, ('전략',)), deck['스킬'])
    act, st, skill = dict(base[0]), dict(base[1]), base[2]; swaps = []; err = None
    while True:
        opts = [{'label': '교체 끝', 'kind': 'done'}] + ([{'label': '처음으로 (교체 모두 취소)', 'kind': 'reset'}] if swaps else [])
        opts += side_options(act, st, skill)
        o = opts[bridge.ask({'kind': 'side', 'p': i, 'decision': f'{rnd}라운드 전 전략 덱 교체', 'opts': opts, 'turn': 0, 'phase': '',
                             'skill': skill, 'opp_skill': decks[1 - i]['스킬'], 'wins': list(wins), 'error': err,
                             'active': sorted(act.items()), 'strategy': sorted((n, k) for n, k in st.items() if k > 0),
                             'swaps': [[a, b] for a, b, _ in swaps]})]
        err = None
        if o['kind'] == 'reset':
            act, st, skill = dict(base[0]), dict(base[1]), base[2]; swaps = []
        elif o['kind'] == 'card':
            M.apply_card_swap(act, st, o['out'], o['in']); swaps.append((o['out'], o['in'], '사람'))
        elif o['kind'] == 'skill':
            st[o['in']] -= 1; st[skill] = st.get(skill, 0) + 1; swaps.append((skill, o['in'], '스킬 교체')); skill = o['in']
        else:
            d = M.deck_from(deck, act, st); d['스킬'] = skill
            errs, _ = D.validate(d, policy=False)
            if errs: err = '덱 규칙 오류: ' + '; '.join(errs[:3]); continue
            break
    pname = deck['이름']
    log.append({'t': 0, 'ph': '', 'tp': 0, 'k': 'side', 'data': {'player': pname, 'swaps': swaps},
                'm': f'{pname} 전략 덱 교체: ' + ', '.join(f'「{a}」 → 「{b}」 ({why})' for a, b, why in swaps) if swaps else f'{pname} 전략 덱 교체 없음'})
    return d


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
