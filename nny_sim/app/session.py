"""대전 세션 · 저장소(덱 · 재생 기록 · 재생 목록 · 학습 기록).

LiveMatch: 엔진 스레드에서 Bo3 매치 1개를 돌리며 기록기(viewer/record.py Recorder)로 기록 줄마다 보드 상태를 남긴다.
  - 사람 vs AI: 사람 자리는 HumanAI(판단을 화면에서 받음). 학습을 켜면 AI · 사람의 판단 기록이 라운드마다 대전 표에 반영되고,
    매치가 끝나면 그 갱신을 학습 기록(jsonl)에 덧붙인다 — 다음 대전부터 그대로 쓰인다(프로그램 안에서는 즉시 반영).
  - AI vs AI: 관전 · 녹화. 학습을 켜면 사람 대전과 같이 학습표 AI 자리의 판단이 대전 표에 반영되고 학습 기록(ai_games.jsonl) · 신경망 표본에 남는다
    (출처 'ai' — 사람 대전보다 낮은 가중치, learndata).
  매치가 끝나면(그만둔 경우도) 재생 기록으로 저장한다.
Store: 사용자 폴더의 파일들. 학습 데이터(학습표 기록 · 신경망 표본)는 매치 단위로 사용자가 빼거나 다시 넣을 수 있다(learndata 제외 목록).
"""
import gzip, json, os, random, re, shutil, subprocess, threading, time, traceback, uuid

import deck as D
import match as M
import policy as P
import season as SE
from ai import HeuristicAI
from cards import POOL
from engine import StalledGame

import record as REC
import tables as T
import learndata as LD
import nnai as NA
import nn_samples as NS
from human import Abort, Bridge, HumanAI

SAFE = re.compile(r'[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ _\-().!]+')


def now(): return time.strftime('%Y-%m-%d %H:%M:%S')


GIT_LEARN_DIR = 'nny_sim/learned/human_games'          # 학습 기록을 올리는 저장소 폴더(merge_learning.py 가 읽음 — 사람 대전 · AI끼리 합친 기록, 줄마다 출처)
GIT_LEARN_BRANCH = 'data/human-games-{host}'
GIT_NN_BRANCH = 'data/human-nn-{host}'                  # 신경망 표본(nnai.SHARE_REL 폴더 — merge_nn.py 가 읽음)


def safe_name(s, default='덱'):
    s = SAFE.sub('', s or '').strip()[:60]
    return s or default


class Store:
    """사용자 폴더: decks/*.deck · replays/<id>.json.gz + index.json · playlists.json · settings.json ·
    learning/human_games.jsonl(사람 대전) · learning/ai_games.jsonl(AI끼리) · learning/excluded.json(사용자가 뺀 매치)"""

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
                'rounds': [[r['winner'], r['reason']] for r in m.get('rounds', [])], 'status': m.get('status', 'done'),
                'ai': m.get('ai', 'table'), **({'ai2': m['ai2']} if m.get('ai2') else {})}

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

    # ── 학습 기록 ── (출처 · 가중치 · 제외: learndata)
    @property
    def log_path(self): return os.path.join(self.dir, 'learning', 'human_games.jsonl')

    @property
    def ai_log_path(self): return os.path.join(self.dir, 'learning', 'ai_games.jsonl')

    @property
    def log_paths(self): return [self.log_path, self.ai_log_path]

    def excluded(self): return LD.read_excluded(self.dir)

    def learning_records(self, include_excluded=False):
        """두 학습 기록 파일의 매치 기록(줄마다 출처 'source') — 사용자가 뺀 매치는 빼고, 뺀 판단은 그 줄의 갱신에서 뺀다"""
        ex = LD.Exclusion() if include_excluded else self.excluded()
        return [dict(r, source=LD.record_source(r), updates=LD.kept_updates(r, ex))
                for path in self.log_paths for r in T.read_log(path) if LD.record_key(r) not in ex]

    @staticmethod
    def write_records(path, recs):
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            for r in recs: f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
        os.replace(tmp, path)

    def learning_stats(self):
        """학습표 기록 통계 — 전체 · 출처별(사용자가 뺀 매치 제외)"""
        ex = self.excluded()
        by = {src: T.log_stats(path, ex) for src, path in (('human', self.log_path), ('ai', self.ai_log_path))}
        tot = {'matches': sum(v['matches'] for v in by.values()), 'updates': sum(v['updates'] for v in by.values()),
               'size': sum(v['size'] for v in by.values())}
        return dict(tot, by_source=by, by_matchup=by['human']['by_matchup'], excluded=len(ex),
                    excluded_parts=sum(len(v.get('t', ())) + len(v.get('n', ())) for v in ex.parts.values()))

    def export_learning(self):
        """사람 대전 · AI끼리 학습 기록을 합친 파일 하나(줄마다 출처) — 사용자가 뺀 매치는 넣지 않는다"""
        recs = self.learning_records()
        if not recs: return None
        out = os.path.join(self.dir, 'export', time.strftime('학습데이터_%Y%m%d-%H%M%S.jsonl'))
        self.write_records(out, recs); return out

    def learning_items(self):
        """학습 데이터 정리 목록 — 매치마다 학습표 기록 · 신경망 표본을 매치 키(learndata)로 묶는다. 최근 것이 앞"""
        ex = self.excluded(); items = {}

        def item(key, src, meta):
            it = items.get(key)
            if it is None:
                it = items[key] = {'key': key, 'source': src, 'label': LD.SOURCE_LABEL.get(src, src), 'weight': LD.weight_of(src),
                                   'time': '', 'decks': meta.get('decks', []), 'ai_kinds': meta.get('ai_kinds'), 'winner': meta.get('winner'),
                                   'human_won': meta.get('human_won'), 'status': meta.get('status'), 'updates': 0, 'samples': 0, 'excluded': key in ex,
                                   'dropped': len(ex.dropped(key, 't')) + len(ex.dropped(key, 'n'))}
            return it
        for path in self.log_paths:
            for r in T.read_log(path):
                src = LD.record_source(r); it = item(LD.record_key(r), src, r)
                it['updates'] += len(r.get('updates', ())); it['time'] = max(it['time'], (r.get('time') or '').replace('T', ' ')[:16])
        for name, meta in NS.read_index(self.dir).items():
            if not os.path.exists(os.path.join(NS.samples_dir(self.dir), name)): continue
            it = item(LD.sample_key(name, meta), LD.sample_source(meta), meta)
            it['samples'] += meta.get('samples', 0); it['time'] = max(it['time'], meta.get('time') or '')
        return sorted(items.values(), key=lambda it: it['time'], reverse=True)

    def decisions(self, key):
        """매치 하나의 판단 목록(판단 단위 정리) — 학습표 기록의 갱신마다 {i, 판단, 후보, 승패, 뺌} · 신경망 표본마다 {i, 판단, 후보, 자리, 뺌}.
        예전 신경망 표본(판단 글이 없는 것)은 판단 종류만(drl.schema)"""
        ex = self.excluded(); dt, dn = ex.dropped(key, 't'), ex.dropped(key, 'n')
        table = []
        for path in self.log_paths:
            for r in T.read_log(path):
                if LD.record_key(r) != key: continue
                for i, (k1, _, won) in enumerate(r.get('updates', ())):
                    d, lab = LD.split_key(k1); table.append({'i': i, 'decision': d, 'label': lab, 'won': won, 'excluded': i in dt})
        nn = []
        for name, meta in NS.read_index(self.dir).items():
            if LD.sample_key(name, meta) != key: continue
            decs = meta.get('decs') or NS.decision_types(self.dir, name)
            for i, d in enumerate(decs):
                nn.append({'i': i, 'decision': d[0], 'label': d[1] if len(d) > 1 else '', 'seat': d[2] if len(d) > 2 else None, 'excluded': i in dn})
        return {'key': key, 'match_excluded': key in ex, 'table': table, 'nn': nn}

    def set_parts(self, key, table=(), nn=(), excluded=True):
        """매치 key 안의 판단(학습표 갱신 번호 table · 신경망 표본 번호 nn)을 빼거나 다시 넣는다 → 그 매치의 뺀 판단 수"""
        with self.lock:
            ex = self.excluded(); part = ex.parts.setdefault(str(key), {'t': set(), 'n': set()})
            for kind, idx in (('t', table), ('n', nn)):
                cur = part.setdefault(kind, set()); idx = {int(i) for i in idx}
                part[kind] = (cur | idx) if excluded else (cur - idx)
            LD.write_excluded(self.dir, ex, ex.parts)
            return sum(len(v) for v in part.values())

    def set_decision_text(self, keys, text, excluded=True):
        """여러 매치에서 판단 · 후보 글에 text 가 들어 있는 판단을 한꺼번에 빼거나 넣는다 → 바뀐 판단 수"""
        n = 0
        for key in keys:
            d = self.decisions(key)
            t = [x['i'] for x in d['table'] if text in x['decision'] or text in x['label']]
            m = [x['i'] for x in d['nn'] if text in x['decision'] or text in x['label']]
            if t or m: self.set_parts(key, t, m, excluded); n += len(t) + len(m)
        return n

    def set_excluded(self, keys, excluded):
        """매치 키들을 학습 데이터에서 빼거나(excluded=True) 다시 넣는다 → 제외 매치 수"""
        with self.lock:
            ex = self.excluded(); keys = {str(k) for k in keys}
            new = (ex | keys) if excluded else (ex - keys)
            LD.write_excluded(self.dir, new, ex.parts)
        return len(new)

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

    def host(self):
        return safe_name(os.environ.get('COMPUTERNAME') or os.environ.get('HOSTNAME') or 'pc', 'pc')

    def git_push(self):
        """학습 기록(사람 대전 · AI끼리 합친 것, 줄마다 출처 — 사용자가 뺀 매치 제외)을 저장소 nny_sim/learned/human_games/<컴퓨터>.jsonl 로
        — 브랜치는 설정 또는 data/human-games-<컴퓨터>"""
        recs = self.learning_records()
        if not recs: return {'ok': False, 'msg': '아직 학습 기록이 없습니다(또는 모두 학습 데이터에서 뺐습니다).'}
        n = {src: sum(1 for r in recs if r['source'] == src) for src in LD.SOURCE_LABEL}
        return self.git_upload(GIT_LEARN_DIR, self.settings()['git_branch'] or GIT_LEARN_BRANCH,
                               lambda dst, host: self.write_records(os.path.join(dst, f'{host}.jsonl'), recs),
                               lambda host: f'학습 기록: {host} — 사람 대전 {n["human"]}매치 · AI끼리 {n["ai"]}매치 · 갱신 {sum(len(r.get("updates", ())) for r in recs)}개')

    def git_push_nn(self, nn):
        """신경망 표본 · 내 모델(nnai.Manager.place_share)을 저장소 nny_sim/learned/drl/human_nn/<컴퓨터>/ 로 — 브랜치 data/human-nn-<컴퓨터>"""
        import nn_samples as NS
        st = NS.stats(self.dir)
        if not st['matches']: return {'ok': False, 'msg': '아직 신경망 표본이 없습니다 — 「AI 학습」을 켜고 대전(나 vs AI · AI끼리)을 해 주세요.'}
        return self.git_upload('/'.join(NA.SHARE_REL), GIT_NN_BRANCH, lambda dst, host: nn.place_share(os.path.join(dst, host), host),
                               lambda host: f'신경망 표본: {host} — 매치 {st["matches"]}개 · 표본 {st["samples"]}개')

    def git_upload(self, sub, branch, place, message):
        """앱이 관리하는 얕은 clone(사용자 폴더/git/repo, sparse)의 sub 폴더에 place(폴더, 컴퓨터 이름)로 파일을 넣고 커밋 · 푸시한다
        — 인터넷과 git, GitHub 로그인이 필요. branch 의 {host} 는 컴퓨터 이름. 브랜치가 아직 없으면 설정의 기준 브랜치에서 만든다"""
        s = self.settings()
        git = shutil.which('git')
        if not git: return {'ok': False, 'msg': 'git 이 설치되어 있지 않습니다. 「내보내기」한 파일을 GitHub 웹에서 올려 주세요.'}
        repo = os.path.join(self.dir, 'git', 'repo'); host = self.host()
        branch = branch.replace('{host}', host.lower().replace(' ', '-'))
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
                run('sparse-checkout', 'set', sub, cwd=repo)
            else:
                run('sparse-checkout', 'add', sub, cwd=repo)
            if not run('fetch', '--depth', '1', 'origin', branch, cwd=repo) and not run('fetch', '--depth', '1', 'origin', s['git_base'], cwd=repo):
                return {'ok': False, 'msg': 'fetch 실패 — 인터넷 연결 · 저장소 주소를 확인하세요.', 'log': log}
            run('checkout', '-B', branch, 'FETCH_HEAD', cwd=repo)
            dst = os.path.join(repo, *sub.split('/')); os.makedirs(dst, exist_ok=True)
            place(dst, host)
            run('add', '-A', sub, cwd=repo)
            run('-c', 'user.name=NNY Simulator', '-c', 'user.email=nny-simulator@localhost', 'commit', '-m', message(host), cwd=repo)
            if not run('push', '-u', 'origin', f'HEAD:{branch}', cwd=repo):
                return {'ok': False, 'msg': 'push 실패 — 인터넷 연결 · GitHub 로그인(권한)을 확인하세요.', 'log': log}
            return {'ok': True, 'msg': f'GitHub 브랜치 {branch} 에 올렸습니다.', 'branch': branch, 'log': log}
        except (OSError, subprocess.SubprocessError) as ex:
            return {'ok': False, 'msg': f'git 실행 오류: {ex}', 'log': log}


AI_KINDS = ('table', 'nn', 'heuristic')   # AI 대전 · 녹화에서 고를 수 있는 AI 종류


class LearningHeuristicAI(P.LearnedAI):
    """학습하는 휴리스틱 AI. 전술(발동 · 대응 · 트리거 · 공격 · 대상 · 서치 · 버릴 카드 · 소환 표시 형식 등)은 ai.HeuristicAI 규칙 그대로(덱 지침 · 카드 우선순위),
    전략(STRATEGY — 시작 패 배분 · 멀리건 재배분 · 멀리건 · 드로우 덱 · 2 · 3라운드 선후공 · 번식지)은 학습표 AI와 같은 키 · 사전값으로 학습표 값을 보고 고르고,
    학습을 켜면 그 결과를 학습표에 더한다 — 학습 기록 · 출처 · 가중치 · 제외는 다른 AI와 같다(learndata). 학습표에 기록이 없으면 사전값(휴리스틱 판단)이 이긴다.
    ai.BREEDING(전역 번식지 표)은 쓰지 않는다(번식지도 학습표 키). 전략 덱 교체는 다른 AI와 같은 규칙(match.side_swap)"""
    STRATEGY = ('choose_split', 'mulligan_split', 'mulligan', 'choose_draw_deck', 'choose_first', 'first_result', 'breeding_pick')
    LEARNER = ('choose', 'end_game', 'bucket', 'split_opts')   # 학습표 판단 · 학습 장치(LearnedAI 그대로)


# 학습표 AI가 다시 정의한 판단 중 STRATEGY · LEARNER 가 아닌 것(전술)은 휴리스틱 규칙으로 되돌린다
LearningHeuristicAI.TACTICS = tuple(n for n, f in vars(P.LearnedAI).items() if not n.startswith('_') and callable(f) and hasattr(HeuristicAI, n)
                                    and n not in LearningHeuristicAI.STRATEGY + LearningHeuristicAI.LEARNER)
for _n in LearningHeuristicAI.TACTICS: setattr(LearningHeuristicAI, _n, getattr(HeuristicAI, _n))


class LiveMatch:
    """Bo3 매치 1개 — 엔진 스레드 + 기록기. human: 사람 자리(0) 여부"""

    def __init__(self, store, split_dir, decks, names, human=False, seed=None, first=0, learn=False, hints=False, title='',
                 ai_kind='table', nn_model=None, nn_label='', nn_record=False, ai0_kind='table'):
        self.store = store; self.split = split_dir; self.decks = decks; self.names = names; self.human = human
        # AI 종류(AI_KINDS): ai_kind = P2(AI) 자리 — 'table' 학습표 AI | 'nn' 신경망 AI(nn_model 파일, nn_label 'local' · 'base') | 'heuristic' 휴리스틱 AI,
        # ai0_kind = 사람이 없을 때 P1 자리(녹화 · 관전 — AI_KINDS 중 하나, 신경망이면 P2와 같은 모델)
        self.ai_kind = ai_kind; self.ai0_kind = ai0_kind; self.nn_model = nn_model; self.nn_label = nn_label; self.nn_record = nn_record; self.nn_saved = 0
        self.seed = random.randrange(2 ** 31) if seed is None else seed; self.first = first
        self.learn = learn; self.hints = hints; self.title = title   # 학습: 사람 대전 · AI끼리 모두(출처별 가중치 — learndata)
        self.match_uid = uuid.uuid4().hex   # 매치 키 — 이 매치의 학습표 기록과 신경망 표본이 같은 키(학습 데이터 정리에서 함께 빼고 넣음)
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
                'ai': 'table' if self.human else self.ai0_kind, 'kind': 'human' if self.human else 'ai', 'created': now(), 'title': self.title}
        tag = lambda k: 'nn:' + (self.nn_label or 'model') if k == 'nn' else k   # 재생 기록 정보: 신경망은 어느 모델인지까지
        if not self.human: meta['ai'] = tag(self.ai0_kind)
        if tag(self.ai_kind) != meta['ai']: meta['ai2'] = tag(self.ai_kind)
        rounds = []; mw = None; tap = None
        try:
            table = T.matchup_table(self.split, self.skills(), logs=self.store.log_paths, exclude=self.store.excluded())
            table.live_w = LD.weight_of('human' if self.human else 'ai')   # 이 대전에서 바로 배우는 갱신도 기록을 다시 적용할 때와 같은 가중치
            self.table = table; self.status = 'running'
            kinds = [None if self.human else self.ai0_kind, self.ai_kind]   # 자리별 AI 종류(사람 자리는 None)
            actor = NA.load_actor(self.nn_model) if 'nn' in kinds else None
            if self.learn and self.nn_record: tap = NS.Tap()   # 신경망 학습 표본(학습표 판단이 있는 자리의 판단 · 라운드 승패 · 로컬 학습표 교사 분포) — numpy 를 쓸 수 있을 때만

            def make_ai(d):
                seat = d['_seat']; kind = kinds[seat]
                if self.human and seat == 0: ai = HumanAI(d['스킬'], self.bridge, table, learn=self.learn, hints=self.hints)
                elif kind == 'nn': ai = NA.make_ai(d['스킬'], actor, table)
                elif kind == 'heuristic': ai = LearningHeuristicAI(d['스킬'], learn=self.learn, table=table)
                else: ai = P.LearnedAI(d['스킬'], learn=self.learn, table=table)
                return tap.attach(ai, seat, table) if tap and hasattr(ai, 'choose') else ai   # 학습표 판단(choose)이 있는 자리 — 휴리스틱 AI는 전략 판단만

            def side_fn(i, decks, wins, rnds, rng, eps, log):   # 사람 덱은 화면에서 교체, AI는 학습표 교체 규칙대로
                if self.human and i == 0: return human_side(self.bridge, decks, i, wins, len(rnds) + 1, log)
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
                info = self.learn_info(meta, mw)
                if self.learn and getattr(self, 'table', None) is not None and self.table.deltas:
                    T.append_log(self.store.log_path if self.human else self.store.ai_log_path,
                                 dict(info, rounds=[[r['winner'], r['reason']] for r in meta['rounds']]), self.table.deltas)
                    self.learned = len(self.table.deltas)
                    if self.store.settings().get('auto_push'): threading.Thread(target=self.store.auto_push, daemon=True).start()
                if tap is not None:
                    _, self.nn_saved = tap.save(self.store.dir, mw, info)
                if self.rec.frames: self.replay_id = 'u:' + self.store.save_replay(self.replay_dict())
            except Exception:
                self.error = (self.error or '') + '\n저장 오류:\n' + traceback.format_exc()[-2000:]

    def learn_info(self, meta, mw):
        """학습표 기록 · 신경망 표본에 같이 남기는 매치 정보 — 출처(learndata) · 매치 키 · 자리별 AI 종류 · 덱 · 승자"""
        info = {'source': 'human' if self.human else 'ai', 'match': self.match_uid, 'decks': meta['decks'], 'seed': self.seed, 'status': self.status,
                'winner': mw, 'ai_kinds': ['human' if self.human else meta['ai'], meta.get('ai2', meta['ai'])]}
        if self.human: info.update(human_seat=0, human_won=(mw == 0) if mw is not None else None)
        return info

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
                'replay_id': self.replay_id, 'learned': self.learned, 'nn_saved': self.nn_saved, 'names': self.names, 'human': self.human}

    def abort(self):
        self.bridge.abort()


def misfits(act, skill):
    """활성 덱(메인 · 상급) 카드 중 지금 스킬의 태그에 맞지 않는 것 — 스킬을 바꾼 뒤 전략 덱으로 보내야 하는 카드"""
    return sorted(n for n, k in act.items() if k > 0 and not M.fits(n, skill))


def side_options(act, st, skill):
    """지금 덱에서 할 수 있는 교체 하나하나 — 카드는 match.py 교체 규칙 그대로(전략 덱 카드 1:1 · 같은 덱 종류 · 동명 3장 · 지금 스킬 태그 · 고정 카드 제외).
    스킬 카드는 전략 덱에 있으면 언제든 고를 수 있고(사람), 바꾼 뒤 새 스킬 태그에 맞지 않는 활성 덱 카드(misfits)를 전략 덱으로 보내야 「교체 끝」이 된다.
    태그에 맞지 않는 카드를 빼는 교체를 앞에 둔다"""
    out = []; bad = set(misfits(act, skill))
    for i in M.swap_ins(act, st, skill):
        for o in sorted(M.swap_outs(act, i), key=lambda o: o not in bad):
            out.append({'label': f'「{o}」 → 「{i}」', 'kind': 'card', 'out': o, 'in': i, 'misfit': o in bad})
    for n in sorted(n for n, k in st.items() if k > 0 and M.is_skill(n) and n != skill):
        out.append({'label': f'스킬 「{skill}」 → 「{n}」', 'kind': 'skill', 'out': skill, 'in': n})
    return out


def human_side(bridge, decks, i, wins, rnd, log):
    """라운드 사이 사람의 전략 덱 교체 — 할 수 있는 교체 목록을 서버가 만들어 보내고(Bridge 요청 kind 'side'), 하나씩 받아 적용한다.
    「교체 끝」이면 덱 규칙(deck.validate)을 다시 확인해 새 덱을 돌려주고, 기록에 side_swap 과 같은 'side' 줄을 남긴다"""
    deck = decks[i]; base = (M.counts_of(deck), M.counts_of(deck, ('전략',)), deck['스킬'])
    act, st, skill = dict(base[0]), dict(base[1]), base[2]; swaps = []; err = None
    while True:
        opts = [{'label': '교체 끝', 'kind': 'done'}] + ([{'label': '처음으로 (교체 모두 취소)', 'kind': 'reset'}] if swaps else [])
        opts += side_options(act, st, skill); bad = misfits(act, skill)
        o = opts[bridge.ask({'kind': 'side', 'p': i, 'decision': f'{rnd}라운드 전 전략 덱 교체', 'opts': opts, 'turn': 0, 'phase': '',
                             'skill': skill, 'opp_skill': decks[1 - i]['스킬'], 'wins': list(wins), 'error': err,
                             'misfit': [(n, act[n]) for n in bad],
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
            if bad:   # 스킬을 바꿨으면 새 스킬 태그에 맞지 않는 메인 · 상급 카드를 모두 전략 덱으로 보내야 진행할 수 있다
                err = (f'스킬 「{skill}」의 태그에 맞지 않는 카드 {sum(act[n] for n in bad)}장을 모두 전략 덱으로 보내야 진행할 수 있습니다: '
                       + ', '.join(f'「{n}」×{act[n]}' for n in bad) + ' — 맞는 카드로 바꿀 수 없으면 「처음으로」')
                continue
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

    def __init__(self, store, split_dir, pairs, matches=1, seed=None, ai_kind='table', ai0_kind=None, nn_model=None, nn_label='',
                 learn=False, nn_record=False):
        self.store = store; self.split = split_dir; self.pairs = pairs; self.n = matches
        self.learn = learn; self.nn_record = nn_record   # 녹화한 매치를 학습 데이터로 남기기(출처 'ai')
        self.ai_kind = ai_kind; self.ai0_kind = ai0_kind or ai_kind; self.nn_model = nn_model; self.nn_label = nn_label   # P2 · P1 자리 AI 종류(AI_KINDS)
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
                              title=f'{names[0]} vs {names[1]}', ai_kind=self.ai_kind, ai0_kind=self.ai0_kind, nn_model=self.nn_model, nn_label=self.nn_label,
                              learn=self.learn, nn_record=self.nn_record)
                self.current = m; m._run(); k += 1
                self.done.append({'replay_id': m.replay_id, 'status': m.status, 'winner': m.result and m.result.get('winner'), 'learned': m.learned, 'nn_saved': m.nn_saved})
        self.status = 'stopped' if self.stop else 'done'; self.current = None

    def info(self):
        return {'id': self.id, 'status': self.status, 'done': len(self.done), 'total': self.total, 'items': self.done,
                'current': self.current.id if self.current else None}
