"""서버 — 게임 화면(static/)과 API. 하마치 어댑터 IP(25.x)에만 열고, 실행마다 새로 만드는 토큰을 요구한다(다른 웹사이트의 호출 차단).
온라인판: 사람vs사람 대전은 좌석(0·1)마다 Bridge 가 따로 있고, 참가 키로 poll · answer 를 그 좌석에만 묶는다(session.LiveMatch 참고)."""
import json, mimetypes, os, re, secrets, socket, subprocess, sys, threading, time, traceback
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import deck as D
from cards import POOL

import session as SS
import tables as T

VERSION = '1.1.0'
IDLE_EXIT = 180          # 화면이 이만큼(초) 신호를 보내지 않으면 서버를 끈다(창을 닫은 경우) — 녹화 작업 중에는 끄지 않음
CLIENT_TTL = 45          # 접속중 명단: 이만큼(초) heartbeat 가 없으면 끊긴 것으로 본다(heartbeat 주기 20초의 2배 이상)
ROOM_GRACE = 90          # 로비(방) 재접속 유예: 이만큼(초) heartbeat 가 없어야 자리를 비운다(CLIENT_TTL 보다 넉넉히 — 잠깐 끊겨도 자리 유지)
CHAT_MAX = 200           # 인게임 메신저: 메시지 1개 최대 글자 수(room_join 의 name[:40] 과 같은 식의 사람 입력 캡)
CHAT_BUFFER = 200        # 인게임 메신저: 메모리 링버퍼에 유지하는 최근 메시지 수(프로세스 수명 동안만 — 그 이상은 push_game 으로 넘어가야 남음)
POOL_KEYS = ('code', 'name', 'type', 'subtype', 'level', 'race', 'attr', 'atk', 'def', 'deck', 'color', 'text', 'tags', 'theme', 'skill_tags', 'no_common')
mimetypes.add_type('image/webp', '.webp'); mimetypes.add_type('text/javascript', '.js')


class HamachiNotFound(RuntimeError):
    """하마치 가상 어댑터(25.x.x.x) 를 찾지 못함 — main.py 가 안내 문구를 찍고 조용히 끝낸다"""


def hamachi_ip():
    """이 PC의 하마치 가상 어댑터 IP(25.0.0.0/8). 없으면 None — 하마치가 안 깔렸거나 네트워크(new_card_game)에 아직 참가하지 않음.
    표준 라이브러리만 쓴다(배포본은 외부 패키지를 내려받지 않음): 먼저 hostname 의 주소들에서 찾고, 안 되면 OS 네트워크 명령 출력을 훑는다"""
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip.startswith('25.'): return ip
    except socket.gaierror: pass
    try:
        if sys.platform == 'win32': out = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='cp437', errors='replace', timeout=5).stdout
        else: out = subprocess.run(['ip', 'addr'], capture_output=True, text=True, timeout=5).stdout
        m = re.search(r'\b25\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', out)
        if m: return m.group(0)
    except (OSError, subprocess.SubprocessError): pass
    return None


def commit_rev():
    """업데이트 패널 — 지금 돌고 있는 코드의 git 짧은 커밋 해시. .bat 의 `git pull --ff-only` 가
    받아오는 그 값과 같아서, 화면에서 버전 옆에 보여주면 최신인지 눈으로 바로 비교할 수 있다.
    git 이 없거나(.git 없는 배포본) 실패하면 None — 배지가 버전만 보여주고 조용히 끝난다."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        out = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, timeout=5, cwd=here)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


class App:
    def __init__(self, paths):
        self.p = paths
        import human
        human.install_block_hooks()   # 첫 게임(카드 효과 코드 생성 · 캐시) 전에 — 사람 자리의 서치 · 카드 고르기를 화면에서 묻는다
        self.store = SS.Store(paths['user'], paths.get('library'))
        self.users_path = os.path.join(paths['user'], 'online_users.json')  # tools/discord_bot.py 의 /유저등록 이 쓰는 그 파일(같은 경로)
        self.token = secrets.token_hex(16)
        self.commit = commit_rev()  # 업데이트 패널(⑧) — 서버 켤 때 한 번만 읽음(git 호출 반복 안 함)
        self.live = None; self.jobs = {}; self.last_beat = time.time(); self.server = None
        self.clients = {}  # ip -> 마지막 heartbeat 시각(접속중 명단, allowed_ips 와 같은 파일을 이름 표시에 재사용)
        self.room = {}     # 로비(방) 참가자: ip -> {'name','role'('player'|'spectator'),'joined','last_seen'} — 방 1개 · 자리(player) 최대 2
        self.live_ips = {}  # 로비에서 시작한 사람vs사람 매치의 ip -> 좌석(0|1) — 상대 화면이 매치 ID·참가 키를 수동으로 받지 않고 스스로 찾아 들어가게 함
        self.chat = deque(maxlen=CHAT_BUFFER)  # 인게임 메신저: 방 전체 공용 채팅 1개(매치별 구분 없음) — 최근 CHAT_BUFFER개만 메모리에(프로세스 수명 동안만)
        self.chat_seq = 0   # 끊기지 않고 늘어나는 메시지 id — 링버퍼에서 오래된 메시지가 밀려나도 커서(마지막으로 받은 id) 비교는 계속 올바름
        self.chat_owner = {}  # msg id -> 보낸 ip(별도 dict, 응답 직렬화에 절대 안 실림) — 삭제 권한(자기 글만) 확인용
        with open(os.path.join(paths['cards'], 'index.json'), encoding='utf-8') as f: self.cards = json.load(f)
        self.pool = {n: {k: c[k] for k in POOL_KEYS if c.get(k) not in (None, '', [])} for n, c in POOL.items()}

    def _users(self):
        """online_users.json(이름 → 하마치 IP, discord_bot.py 의 /유저등록 이 쓰는 그 파일) — 없거나 깨졌으면 {}."""
        try:
            with open(self.users_path, encoding='utf-8-sig') as f: u = json.load(f)
        except (OSError, ValueError): return {}
        return {k: v.strip() for k, v in u.items() if not k.startswith('_') and isinstance(v, str) and v.strip()}

    def allowed_ips(self):
        """등록된 하마치 IP 집합. 파일이 없거나 등록이 비어 있으면 None(게이트 비활성 — 첫 실행 때 호스트가
        자기 접속까지 막아버리는 걸 피한다; discord_bot.py 의 /유저등록 으로 한 명이라도 등록되면 그때부터 게이트가 선다)."""
        ips = set(self._users().values())
        return ips or None

    def live_info(self):
        """관전(④) 진입용 — 지금 매치가 떠 있다면 누구나(관전자) 알 수 있는 기본 정보만. pending · seat · key 는 절대 안 준다
        (좌석별 비공개 정보는 /api/match/poll 에 spectate=1 로만 접근 — 그쪽이 늘 pending=None)."""
        if not self.live or self.live.status not in ('starting', 'running'): return None
        return {'id': self.live.id, 'names': self.live.names, 'title': self.live.title}

    def heartbeat(self, ip, chat_from=0):
        self.last_beat = time.time()
        if ip:
            self.clients[ip] = time.time()
            if ip in self.room: self.room[ip]['last_seen'] = time.time()  # 재접속 유예: 방에 있던 자리는 heartbeat 가 계속 오면 안 비워진다
        return {'ok': True, 'online': self.connected(), 'room': self.room_status(), 'my_match': self.my_match(ip),
                'live_info': self.live_info(), 'commit': self.commit, 'chat': self.chat_since(chat_from)}

    def _ip_names(self):
        """online_users.json 을 ip → 등록 이름으로 거꾸로 뒤집은 것(이름 → ip 인 _users() 를 접속중 명단 ·
        로비 · 채팅이 전부 같은 식으로 표시에 쓴다 — 한곳에 모아 중복을 없앤다, R6)."""
        return {ip: name for name, ip in self._users().items()}

    def connected(self):
        """접속중 명단 — 마지막 CLIENT_TTL 초 안에 heartbeat 를 보낸 IP들, 등록 이름이 있으면 이름으로 표시."""
        names = self._ip_names()
        now = time.time()
        rows = [{'ip': ip, 'name': names.get(ip, ip)} for ip, last in self.clients.items() if now - last <= CLIENT_TTL]
        return sorted(rows, key=lambda r: r['name'])

    # ── 로비(방): 참가/관전/나가기, 재접속 유예, 방 1·자리(player) 최대 2 ──
    def room_gc(self):
        """ROOM_GRACE 를 넘겨 heartbeat 가 끊긴 자리를 비운다(재접속 유예 — 끝나야 남의 차례가 됨)"""
        now = time.time()
        for ip in [ip for ip, m in self.room.items() if now - m['last_seen'] > ROOM_GRACE]: del self.room[ip]

    def room_status(self):
        self.room_gc()
        names = self._ip_names()
        rows = [{'ip': ip, 'name': names.get(ip, m['name']), 'role': m['role']} for ip, m in self.room.items()]
        players = [r for r in rows if r['role'] == 'player']
        return {'members': sorted(rows, key=lambda r: (r['role'] != 'player', r['name'])),
                'players': len(players), 'open_seat': len(players) < 2}

    def room_join(self, ip, name, role):
        """방 참가(참가=player 자리 요청, 관전=spectator) — 이미 있던 사람의 재접속·역할 변경도 같은 호출로 처리한다.
        등록된 하마치 유저(online_users.json)면 로비에서 직접 타이핑한 이름을 무시하고 등록 이름을 그대로 쓴다
        (「다음 회차 지시」 2번 — 이러면 room_status() 뿐 아니라 채팅 발신자 이름(chat_post 의 m['name'])도
        자동으로 등록 이름과 맞는다, 새 네트워크 호출·새 필드 없음). 미등록 IP는 기존 그대로 직접 타이핑한
        이름을 쓴다(등록 게이트가 비활성일 때도 로비는 그대로 동작해야 하므로)."""
        self.room_gc()
        role = role if role in ('player', 'spectator') else 'spectator'
        cur = self.room.get(ip)
        if role == 'player' and (not cur or cur['role'] != 'player'):
            if sum(1 for pip, m in self.room.items() if m['role'] == 'player' and pip != ip) >= 2:
                raise ValueError('방 자리가 이미 가득 찼습니다(2명) — 관전으로 들어가 주세요')
        now = time.time()
        reg = self._ip_names().get(ip)
        self.room[ip] = {'name': reg or (name or '').strip()[:40] or (cur['name'] if cur else ip), 'role': role,
                          'joined': cur['joined'] if cur else now, 'last_seen': now}
        return self.room_status()

    def room_leave(self, ip):
        self.room.pop(ip, None)
        return self.room_status()

    # ── 인게임 메신저(수다): 방 전체 공용 채팅 1개 — "방 1·듀얼 1"이라 매치별로 나눌 이유가 없다(room 참가자끼리) ──
    def _chat_evict_owner(self):
        """새 메시지를 append 하기 전에, 링버퍼가 이미 가득 차 있으면 밀려날 가장 오래된 항목의 소유자 기록도
        같이 지운다(chat_owner 가 deque 와 별도 dict 라서 저절로 안 줄어듦 — 오래 켜 둔 서버에서 무한히
        커지는 걸 막음, '삭제' 이벤트 자체는 chat_owner 에 안 들어가므로 지울 것이 없어도 안전)."""
        if len(self.chat) >= self.chat.maxlen: self.chat_owner.pop(self.chat[0]['id'], None)

    def chat_post(self, ip, text):
        """방(room)에 있는 사람만(참가·관전 모두) 쓸 수 있다 — room_join 으로 먼저 들어와야 함.
        읽기는 따로 안 막는다(heartbeat/boot 로 누구나 받음 — 화면이 어차피 로비 패널 옆에 두므로 room 참가가 자연스러운 전제)."""
        m = self.room.get(ip)
        if not m: raise ValueError('방에 참가해야 채팅할 수 있습니다.')
        text = (text or '').strip()
        if not text: raise ValueError('빈 메시지는 보낼 수 없습니다.')
        if len(text) > CHAT_MAX: raise ValueError(f'메시지가 너무 깁니다({CHAT_MAX}자 이하로 적어 주세요).')
        self._chat_evict_owner()
        self.chat_seq += 1
        msg = {'id': self.chat_seq, 'who': m['name'] or ip, 'text': text, 't': int(time.time() * 1000), 'kind': 'msg'}
        self.chat.append(msg)
        self.chat_owner[msg['id']] = ip   # 응답에는 절대 안 실림(별도 dict) — 삭제 권한 확인에만 서버 내부에서 씀
        return msg

    def chat_delete(self, ip, msg_id):
        """자신이 보낸 메시지만 삭제(수정은 이번 범위 밖 — 「다음 과제」 메모의 절반). 원본은 그 자리에서
        text 를 비우고 deleted 로 표시해 두어 처음부터 다시 받는 화면(chat_from=0)도 바로 '(삭제됨)'을 보고,
        그와 별도로 kind='delete' 이벤트를 새 id 로 하나 더 올려서 이미 원문을 받아 그려둔 화면도 다음
        증분 커서 조회에서 그 사실을 알고 지울 수 있게 한다(기존 f_from/chat_from 커서 패턴 그대로 재사용,
        새 네트워크 호출 없음)."""
        try: msg_id = int(msg_id)
        except (TypeError, ValueError): raise ValueError('메시지를 찾을 수 없습니다.')
        if not self.room.get(ip): raise ValueError('방에 참가해야 메시지를 삭제할 수 있습니다.')
        owner = self.chat_owner.get(msg_id)
        if owner is None: raise ValueError('메시지를 찾을 수 없습니다(이미 밀려났거나 없는 메시지입니다).')
        if owner != ip: raise ValueError('자신이 보낸 메시지만 삭제할 수 있습니다.')
        target = next((x for x in self.chat if x['id'] == msg_id), None)
        if target is None or target.get('deleted'): raise ValueError('메시지를 찾을 수 없습니다(이미 삭제됐습니다).')
        target['text'] = ''; target['deleted'] = True
        self._chat_evict_owner()
        self.chat_seq += 1
        event = {'id': self.chat_seq, 'who': target['who'], 'text': '', 't': int(time.time() * 1000),
                 'kind': 'delete', 'target': msg_id}
        self.chat.append(event)
        return event

    def chat_since(self, from_id=0):
        """heartbeat/boot 응답에 끼워 보낼 새 메시지만(기존 f_from/s_from/c_from 커서 패턴과 같음) — 매 호출마다 전체를 다시 보내지 않음."""
        from_id = from_id or 0
        return [m for m in self.chat if m['id'] > from_id]

    def chat_between(self, start_ts, end_ts):
        """기능 v1⑥ 기보 수집 경로 재사용 — 그 매치가 돌고 있던 시간(초, time.time()) 사이에 온 채팅만 묶어 같이 올린다."""
        lo, hi = int(start_ts * 1000), int(end_ts * 1000)
        return [m for m in self.chat if lo <= m['t'] <= hi]

    def my_match(self, ip):
        """로비(방)에서 짝지어 시작한 매치라면, 이 ip 가 매치 ID·참가 키를 묻지 않고도 자기 좌석을 그대로 받는다.
        로비를 거치지 않고(수동으로) 시작한 사람vs사람 매치는 live_ips 가 비어 있으므로 여기서 항상 None(기존 수동 키
        공유 방식 그대로) — 호환."""
        if not self.live or self.live.status not in ('starting', 'running'): return None
        seat = self.live_ips.get(ip)
        if seat is None: return None
        return {'id': self.live.id, 'seat': seat, 'key': self.live.keys[seat], 'names': self.live.names, 'title': self.live.title}

    # ── 덱 이름 · 대전 시작 ──
    def deck_label(self, did, d):
        return d['스킬'] if did.startswith('o:') else d['이름']

    def start_match(self, j, ip=None):
        if self.live and self.live.status in ('starting', 'running'): self.live.abort()
        # humans: [좌석0이 사람인가, 좌석1이 사람인가]. 새 클라이언트가 이걸 보내고, 옛 클라이언트의 mode(human/ai)도 그대로 받는다
        humans = tuple(bool(x) for x in j['humans']) if j.get('humans') else (j.get('mode', 'human') == 'human', False)
        da, db = self.store.deck(j['deck']), self.store.deck(j['ai_deck'])
        if not da or not db: raise ValueError('덱을 찾을 수 없습니다')
        for d in (da, db):
            errs, _ = D.validate(d, policy=False)
            if errs: raise ValueError(f'덱 규칙 오류 「{d["이름"]}」: ' + '; '.join(errs[:3]))
        first = {'me': 0, 'ai': 1}.get(j.get('first'), None)
        if first is None: first = secrets.randbelow(2)
        s = self.store.settings()
        a, b = self.deck_label(j['deck'], da), self.deck_label(j['ai_deck'], db)
        if humans[0] and humans[1]:
            names = [a, b] if a != b else [f'{a} (P1)', f'{b} (P2)']; title = f'{names[0]} vs {names[1]} (사람 대 사람)'
        elif humans[0]:
            names = ['나', 'AI']; title = f'나({a}) vs AI({b})'
        else:
            names = [a, b] if a != b else [f'{a} (P1)', f'{b} (P2)']; title = f'{names[0]} vs {names[1]}'
        seed = j.get('seed'); seed = int(seed) if seed not in (None, '') else None
        self.live = SS.LiveMatch(self.store, self.p['split'], [da, db], names, human=humans, seed=seed, first=first,
                                 learn=bool(j.get('learn', s['learn'])), hints=bool(j.get('hints', s['hints'])), title=title,
                                 chat_fn=self.chat_between).start()
        seats = {i: self.live.keys[i] for i in (0, 1) if self.live.humans[i]}
        # 로비(방)에서 짝지어 시작했으면(둘 다 사람 · 방에 player 가 정확히 둘 · 시작한 ip 가 그 둘 중 하나) 상대 ip 를
        # 자동으로 좌석1에 묶어 둔다 — 수동으로 시작했으면(방에 없는 ip 거나 player 가 둘이 아니면) 비워 둬서 기존
        # 매치 ID·참가 키 수동 공유 방식이 그대로 동작한다(호환).
        self.live_ips = {}
        if humans[0] and humans[1]:
            players = [pip for pip, m in self.room.items() if m['role'] == 'player']
            if ip in players and len(players) == 2:
                other = next(p for p in players if p != ip)
                self.live_ips = {ip: 0, other: 1}
        return {'id': self.live.id, 'names': names, 'title': title, 'seats': seats}

    def join_match(self, j):
        """사람vs사람 대전에 참가 키로 들어간다 — 좌석 번호를 몰라도 키만으로 자기 좌석을 찾는다"""
        if not self.live or self.live.id != j.get('id'): raise ValueError('매치를 찾을 수 없습니다')
        key = j.get('key')
        for seat, k in enumerate(self.live.keys):
            if k and k == key: return {'ok': True, 'seat': seat, 'key': key, 'names': self.live.names, 'title': self.live.title}
        raise ValueError('참가 키가 올바르지 않습니다')

    def start_record(self, j):
        pairs = []
        for a, b in j.get('pairs', []):
            da, db = self.store.deck(a), self.store.deck(b)
            if not da or not db: continue
            x, y = self.deck_label(a, da), self.deck_label(b, db)
            pairs.append(((da, db), [x, y] if x != y else [f'{x} (P1)', f'{y} (P2)']))
        if not pairs: raise ValueError('대진이 없습니다')
        job = SS.RecordJob(self.store, self.p['split'], pairs, matches=max(1, min(20, int(j.get('matches', 1)))),
                           seed=int(j['seed']) if j.get('seed') not in (None, '') else None)
        self.jobs[job.id] = job
        return job.info()

    def boot(self, ip=None, chat_from=0):
        return {'version': VERSION, 'token_ok': True, 'decks': self.store.deck_list(),
                'skills': sorted(n for n, c in POOL.items() if c['type'] == '스킬'), 'settings': self.store.settings(),
                'assets': {'ratio': self.cards['ratio'], 'mat_size': self.cards['mat_size'], 'faces': self.cards['faces'],
                           'mat': self.cards.get('mat', 'mat.webp'), 'back': self.cards.get('back', 'back.webp')},
                'replays': self.store.replays(), 'playlists': self.store.playlists(), 'learning': self.learning(),
                'live': self.live.id if self.live and self.live.status in ('starting', 'running') else None,
                'limits': {k: list(v) for k, v in D.LIMITS.items()}, 'max_copies': D.MAX_COPIES, 'online': self.connected(),
                'room': self.room_status(), 'my_match': self.my_match(ip), 'live_info': self.live_info(), 'commit': self.commit,
                'chat': self.chat_since(chat_from)}

    def learning(self):
        st = T.log_stats(self.store.log_path)
        return dict(st, path=self.store.log_path, export_dir=os.path.join(self.store.dir, 'export'),
                    last_push=self.store.last_push(), last_game_push=self.store.last_game_push())

    # ── 요청 처리 ──
    def route(self, method, path, q, body, ip=None):
        g = lambda k, d=None: (q.get(k) or [d])[0]
        if path == '/api/boot': return self.boot(ip, int(g('chat_from', 0) or 0))
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
        if path == '/api/replay/memo': return self.store.add_memo(body.get('id', ''), body.get('memos', []))
        if path == '/api/replay/push': return self.store.push_game_now(body.get('id', ''))
        if path == '/api/playlists':
            return self.store.save_playlists(body.get('playlists', [])) if method == 'POST' else self.store.playlists()
        if path == '/api/match/start': return self.start_match(body, ip)
        if path == '/api/match/join': return self.join_match(body)
        if path == '/api/match/poll':
            if not self.live or self.live.id != g('id'): return {'status': 'none'}
            seat = g('seat'); seat = int(seat) if seat not in (None, '') else None
            return self.live.poll(seat, g('key'), int(g('f', 0)), int(g('s', 0)), int(g('c', 0)), spectate=bool(g('spectate')))
        if path == '/api/match/answer':
            ok = bool(self.live) and self.live.answer(int(body.get('rid', -1)), int(body.get('idx', -1)), body.get('seat'), body.get('key'))
            return {'ok': ok}
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
        if path == '/api/learning/export':
            out = self.store.export_learning(); return {'ok': bool(out), 'path': out}
        if path == '/api/learning/git': return self.store.git_push()
        if path == '/api/settings': return self.store.save_settings(body)
        if path == '/api/open':
            target = {'export': os.path.join(self.store.dir, 'export'), 'user': self.store.dir,
                      'learning': os.path.dirname(self.store.log_path)}.get(body.get('what'))
            if target and hasattr(os, 'startfile'): os.startfile(target)
            return {'ok': bool(target), 'path': target}
        if path == '/api/heartbeat': return self.heartbeat(ip, int(body.get('chat_from', 0) or 0))
        if path == '/api/room/status': return self.room_status()
        if path == '/api/room/join': return self.room_join(ip, body.get('name'), body.get('role'))
        if path == '/api/room/leave': return self.room_leave(ip)
        if path == '/api/room/chat': return self.chat_post(ip, body.get('text'))
        if path == '/api/room/chat/delete': return self.chat_delete(ip, body.get('id'))
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
            busy = any(j.status == 'running' for j in self.jobs.values())
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

        def _registered(self):
            ips = app.allowed_ips()
            return ips is None or self.client_address[0] in ips

        def _api(self, method):
            u = urlparse(self.path)
            if u.path == '/api/ping': return self._send(200, {'ok': True, 'app': 'nny-sim', 'version': VERSION})
            if not self._registered(): return self._send(403, {'error': '등록되지 않은 접속입니다. 하마치 IP를 호스트에게 알려 등록을 요청하세요.'})
            if self.headers.get('X-NNY-Token') != app.token: return self._send(403, {'error': 'token'})
            body = {}
            if method == 'POST':
                n = int(self.headers.get('Content-Length') or 0)
                if n: body = json.loads(self.rfile.read(n).decode('utf-8'))
            try: self._send(200, app.route(method, u.path, parse_qs(u.query), body, self.client_address[0]))
            except KeyError as ex: self._send(404, {'error': str(ex)})
            except ValueError as ex: self._send(400, {'error': str(ex)})
            except Exception: self._send(500, {'error': traceback.format_exc()[-1500:]})

        def do_GET(self):
            u = urlparse(self.path)
            if u.path.startswith('/api/'): return self._api('GET')
            if not self._registered(): return self._send(403, {'error': '등록되지 않은 접속입니다. 하마치 IP를 호스트에게 알려 등록을 요청하세요.'})
            if u.path in ('/', '/index.html'): return self._file(static, 'index.html', token=True)
            if u.path.startswith('/cards/'): return self._file(cards, u.path[len('/cards/'):], cache=True)
            return self._file(static, u.path.lstrip('/'))

        def do_POST(self):
            if self.path.startswith('/api/'): return self._api('POST')
            self._send(404, {'error': 'not found'})
    return H


def serve(paths, port=0, host=None):
    """host=None 이면 하마치 어댑터 IP 에만 연다(온라인판 기본) — 없으면 HamachiNotFound.
    host 를 직접 주면 그 주소에 연다(개발 · 자동 스모크 전용 — 배포 bat 은 넘기지 않는다)"""
    if host is None:
        host = hamachi_ip()
        if host is None: raise HamachiNotFound('하마치 가상 어댑터(25.x.x.x)를 찾지 못했습니다')
    app = App(paths)
    srv = ThreadingHTTPServer((host, port), make_handler(app)); srv.daemon_threads = True
    app.server = srv
    threading.Thread(target=app.watchdog, daemon=True).start()
    return app, srv
