"""로컬 서버 — 게임 화면(static/)과 API. 127.0.0.1 에만 열고, 실행마다 새로 만드는 토큰을 요구한다(다른 웹사이트의 호출 차단)."""
import json, mimetypes, os, secrets, sys, threading, time, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import deck as D
from cards import POOL

import session as SS
import nnai as NA

VERSION = '1.3.1'
IDLE_EXIT = 180          # 화면이 이만큼(초) 신호를 보내지 않으면 서버를 끈다(창을 닫은 경우) — 녹화 작업 중에는 끄지 않음
POOL_KEYS = ('code', 'name', 'type', 'subtype', 'level', 'race', 'attr', 'atk', 'def', 'deck', 'color', 'text', 'tags', 'theme', 'skill_tags', 'no_common')
mimetypes.add_type('image/webp', '.webp'); mimetypes.add_type('text/javascript', '.js')


class App:
    def __init__(self, paths):
        self.p = paths
        import human
        human.install_block_hooks()   # 첫 게임(카드 효과 코드 생성 · 캐시) 전에 — 사람 자리의 서치 · 카드 고르기를 화면에서 묻는다
        self.store = SS.Store(paths['user'], paths.get('library'))
        self.nn = NA.Manager(paths['sim'], paths['user'], paths.get('nn_base'))   # 신경망 AI 모델 · 로컬 학습 작업
        self.token = secrets.token_hex(16)
        self.live = None; self.jobs = {}; self.last_beat = time.time(); self.server = None
        with open(os.path.join(paths['cards'], 'index.json'), encoding='utf-8') as f: self.cards = json.load(f)
        self.pool = {n: {k: c[k] for k in POOL_KEYS if c.get(k) not in (None, '', [])} for n, c in POOL.items()}

    # ── 덱 이름 · 대전 시작 ──
    def deck_label(self, did, d):
        return d['스킬'] if did.startswith('o:') else d['이름']

    def start_match(self, j):
        if self.live and self.live.status in ('starting', 'running'): self.live.abort()
        mode = j.get('mode', 'human')
        da, db = self.store.deck(j['deck']), self.store.deck(j['ai_deck'])
        if not da or not db: raise ValueError('덱을 찾을 수 없습니다')
        for d in (da, db):
            errs, _ = D.validate(d, policy=False)
            if errs: raise ValueError(f'덱 규칙 오류 「{d["이름"]}」: ' + '; '.join(errs[:3]))
        first = {'me': 0, 'ai': 1}.get(j.get('first'), None)
        if first is None: first = secrets.randbelow(2)
        s = self.store.settings()
        if mode == 'human':
            names = ['나', 'AI']; title = f'나({self.deck_label(j["deck"], da)}) vs AI({self.deck_label(j["ai_deck"], db)})'
        else:
            a, b = self.deck_label(j['deck'], da), self.deck_label(j['ai_deck'], db)
            names = [a, b] if a != b else [f'{a} (P1)', f'{b} (P2)']; title = f'{names[0]} vs {names[1]}'
        seed = j.get('seed'); seed = int(seed) if seed not in (None, '') else None
        ai_kind = j.get('ai_kind', 'table'); ai0_kind = j.get('ai0_kind', 'table') if mode != 'human' else 'table'
        nn_model, nn_label = self.nn_choice(ai_kind, ai0_kind)
        self.live = SS.LiveMatch(self.store, self.p['split'], [da, db], names, human=(mode == 'human'), seed=seed, first=first,
                                 learn=bool(j.get('learn', s['learn'])), hints=bool(j.get('hints', s['hints'])), title=title,
                                 ai_kind=ai_kind, ai0_kind=ai0_kind, nn_model=nn_model, nn_label=nn_label,
                                 nn_record=self.nn_record(bool(j.get('learn', s['learn'])))).start()
        return {'id': self.live.id, 'names': names, 'title': title}

    def nn_record(self, learn):
        """학습을 켠 대전(나 vs AI · AI끼리)에서 신경망 표본도 남길 수 있는가 — numpy · 기본 모델이 있을 때"""
        return learn and self.nn.ready()

    def nn_choice(self, *kinds):
        """자리별 AI 종류 확인 → (신경망 모델 파일, 'local' · 'base') — 신경망 AI 자리가 없으면 (None, '')"""
        for k in kinds:
            if k not in SS.AI_KINDS: raise ValueError(f'알 수 없는 AI 종류: {k}')
        if 'nn' not in kinds: return None, ''
        if not self.nn.ready(): raise ValueError('신경망 AI를 쓸 수 없습니다: ' + self.nn.np_msg)
        m = self.nn.current_path()
        return m, 'local' if m == NA.local_path(self.store.dir) else 'base'

    def start_record(self, j):
        pairs = []
        for a, b in j.get('pairs', []):
            da, db = self.store.deck(a), self.store.deck(b)
            if not da or not db: continue
            x, y = self.deck_label(a, da), self.deck_label(b, db)
            pairs.append(((da, db), [x, y] if x != y else [f'{x} (P1)', f'{y} (P2)']))
        if not pairs: raise ValueError('대진이 없습니다')
        ai_kind = j.get('ai_kind', 'table'); ai0_kind = j.get('ai0_kind', ai_kind)
        nn_model, nn_label = self.nn_choice(ai_kind, ai0_kind)
        learn = bool(j.get('learn', False))
        job = SS.RecordJob(self.store, self.p['split'], pairs, matches=max(1, min(20, int(j.get('matches', 1)))),
                           seed=int(j['seed']) if j.get('seed') not in (None, '') else None, ai_kind=ai_kind, ai0_kind=ai0_kind,
                           nn_model=nn_model, nn_label=nn_label, learn=learn, nn_record=self.nn_record(learn))
        self.jobs[job.id] = job
        return job.info()

    def boot(self):
        return {'version': VERSION, 'token_ok': True, 'decks': self.store.deck_list(),
                'skills': sorted(n for n, c in POOL.items() if c['type'] == '스킬'), 'settings': self.store.settings(),
                'assets': {'ratio': self.cards['ratio'], 'mat_size': self.cards['mat_size'], 'faces': self.cards['faces'],
                           'mat': self.cards.get('mat', 'mat.webp'), 'back': self.cards.get('back', 'back.webp')},
                'replays': self.store.replays(), 'playlists': self.store.playlists(), 'learning': self.learning(),
                'live': self.live.id if self.live and self.live.status in ('starting', 'running') else None, 'nn': self.nn.status(),
                'limits': {k: list(v) for k, v in D.LIMITS.items()}, 'max_copies': D.MAX_COPIES}

    def learning(self):
        import learndata as LD
        return dict(self.store.learning_stats(), path=self.store.log_path, ai_path=self.store.ai_log_path, export_dir=os.path.join(self.store.dir, 'export'),
                    last_push=self.store.last_push(), weights={'human': LD.HUMAN_WEIGHT, 'ai': LD.AI_WEIGHT})

    # ── 요청 처리 ──
    def route(self, method, path, q, body):
        g = lambda k, d=None: (q.get(k) or [d])[0]
        if path == '/api/boot': return self.boot()
        if path == '/api/pool': return self.pool
        if path == '/api/decks': return self.store.deck_list()
        if path == '/api/deck':
            d = self.store.deck(g('id', ''))
            if not d: raise KeyError('덱 없음')
            return {'id': g('id'), 'deck': {**d, '메인': d['메인'], '상급': d['상급'], '전략': d['전략']}, 'text': self.store.deck_text(d)}
        if path == '/api/deck/validate':
            errs, warns = D.validate(self.store.deck_from_json(body), policy=False); return {'errs': errs, 'warns': warns}
        if path == '/api/deck/save': return self.store.save_deck(body.get('deck', {}), body.get('id'))
        if path == '/api/deck/delete': return {'ok': self.store.delete_deck(body.get('id', ''))}
        if path == '/api/replays': return self.store.replays()
        if path == '/api/replay': return self.store.replay(g('id', ''))
        if path == '/api/replay/delete': return {'ok': self.store.delete_replay(body.get('id', ''))}
        if path == '/api/playlists':
            return self.store.save_playlists(body.get('playlists', [])) if method == 'POST' else self.store.playlists()
        if path == '/api/match/start': return self.start_match(body)
        if path == '/api/match/poll':
            if not self.live or self.live.id != g('id'): return {'status': 'none'}
            return self.live.poll(int(g('f', 0)), int(g('s', 0)), int(g('c', 0)))
        if path == '/api/match/answer':
            ok = bool(self.live) and self.live.bridge.reply(int(body.get('rid', -1)), int(body.get('idx', -1))); return {'ok': ok}
        if path == '/api/match/abort':
            if self.live: self.live.abort()
            return {'ok': True}
        if path == '/api/record': return self.start_record(body)
        if path == '/api/jobs': return [j.info() for j in self.jobs.values()]
        if path == '/api/jobs/stop':
            j = self.jobs.get(body.get('id'));
            if j: j.stop = True
            return {'ok': bool(j)}
        if path == '/api/learning': return self.learning()
        if path == '/api/learning/items': return self.store.learning_items()
        if path == '/api/learning/exclude':
            if self.nn.busy(): raise ValueError('신경망 학습 중에는 학습 데이터를 바꿀 수 없습니다')
            return {'ok': True, 'excluded': self.store.set_excluded(body.get('keys', []), bool(body.get('excluded', True)))}
        if path == '/api/nn/status': return self.nn.status()
        if path == '/api/nn/train': return self.nn.start(body.get('epochs'))
        if path == '/api/nn/stop': return self.nn.stop()
        if path == '/api/nn/reset': return self.nn.reset()
        if path == '/api/nn/export':
            out = self.nn.export(os.path.join(self.store.dir, 'export'), self.store.host()); return {'ok': bool(out), 'path': out}
        if path == '/api/nn/git': return self.store.git_push_nn(self.nn)
        if path == '/api/learning/export':
            out = self.store.export_learning(); return {'ok': bool(out), 'path': out}
        if path == '/api/learning/git': return self.store.git_push()
        if path == '/api/settings': return self.store.save_settings(body)
        if path == '/api/open':
            target = {'export': os.path.join(self.store.dir, 'export'), 'user': self.store.dir, 'nn': NA.nn_dir(self.store.dir),
                      'learning': os.path.dirname(self.store.log_path)}.get(body.get('what'))
            if target and hasattr(os, 'startfile'): os.startfile(target)
            return {'ok': bool(target), 'path': target}
        if path == '/api/heartbeat': self.last_beat = time.time(); return {'ok': True}
        if path == '/api/quit':
            threading.Thread(target=self.shutdown, daemon=True).start(); return {'ok': True}
        raise KeyError(path)

    def shutdown(self):
        time.sleep(0.3)
        if self.live: self.live.abort()
        if self.server: self.server.shutdown()

    def watchdog(self):
        while True:
            time.sleep(15)
            busy = any(j.status == 'running' for j in self.jobs.values()) or self.nn.busy()
            if not busy and time.time() - self.last_beat > IDLE_EXIT:
                self.shutdown(); return


def make_handler(app):
    static = app.p['static']; cards = app.p['cards']

    class H(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *a): pass

        def _send(self, code, data, ctype='application/json; charset=utf-8', cache=False):
            if isinstance(data, (dict, list)): data = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            elif isinstance(data, str): data = data.encode('utf-8')
            self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'max-age=86400' if cache else 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers(); self.wfile.write(data)

        def _file(self, base, rel, cache=False, token=False):
            path = os.path.normpath(os.path.join(base, rel))
            if not path.startswith(os.path.normpath(base) + os.sep) or not os.path.isfile(path): return self._send(404, {'error': 'not found'})
            with open(path, 'rb') as f: data = f.read()
            if token: data = data.replace(b'__TOKEN__', app.token.encode())
            self._send(200, data, mimetypes.guess_type(path)[0] or 'application/octet-stream', cache)

        def _api(self, method):
            u = urlparse(self.path)
            if u.path == '/api/ping': return self._send(200, {'ok': True, 'app': 'nny-sim', 'version': VERSION})
            if self.headers.get('X-NNY-Token') != app.token: return self._send(403, {'error': 'token'})
            body = {}
            if method == 'POST':
                n = int(self.headers.get('Content-Length') or 0)
                if n: body = json.loads(self.rfile.read(n).decode('utf-8'))
            try: self._send(200, app.route(method, u.path, parse_qs(u.query), body))
            except KeyError as ex: self._send(404, {'error': str(ex)})
            except ValueError as ex: self._send(400, {'error': str(ex)})
            except Exception: self._send(500, {'error': traceback.format_exc()[-1500:]})

        def do_GET(self):
            u = urlparse(self.path)
            if u.path.startswith('/api/'): return self._api('GET')
            if u.path in ('/', '/index.html'): return self._file(static, 'index.html', token=True)
            if u.path.startswith('/cards/'): return self._file(cards, u.path[len('/cards/'):], cache=True)
            return self._file(static, u.path.lstrip('/'))

        def do_POST(self):
            if self.path.startswith('/api/'): return self._api('POST')
            self._send(404, {'error': 'not found'})
    return H


def serve(paths, port=0):
    app = App(paths)
    srv = ThreadingHTTPServer(('127.0.0.1', port), make_handler(app)); srv.daemon_threads = True
    app.server = srv
    threading.Thread(target=app.watchdog, daemon=True).start()
    return app, srv
