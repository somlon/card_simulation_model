"""매치 기록기 — 재생 화면(viewer)용.

엔진은 고치지 않는다. match.play_match 의 log 자리에 Recorder를 넣으면 기록 줄이 붙을 때마다 그 시점의 보드 상태
(HP · 패 · 덱 매수 · 묘지 · 제외 · 몬스터/마법 존 · 스킬 · 필드 존 · 공유 존 · 체인 · 턴 · 단계)를 찍어 둔다.
발동 · 공격 · 파괴는 Game 메서드를 감싼 관찰 훅이 연출 정보(fx)로 다음 기록 줄에 붙인다 — 훅은 원래 메서드를 그대로 부르고
게임 상태 · 난수를 건드리지 않는다(같은 시드에서 기록기 유무로 기록 문장이 같은지 check_same 으로 확인).

AI · 덱 · 전략 덱 교체는 match_sim 과 같은 설정(학습표 AI, 학습 끔, 교체 학습 끔)을 쓴다.
"""
import json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SIM = os.path.dirname(HERE)          # viewer/ 의 상위 폴더 = nny_sim (engine.py 가 있는 곳)
POOL_KEYS = ('code', 'name', 'type', 'subtype', 'level', 'race', 'attr', 'atk', 'def', 'deck', 'color', 'text', 'tags')
RES_RE = re.compile(r'^체인 (\d+) ')         # 체인 처리 줄 (engine.Game.resolve_chain)


def use_sim(sim):
    """시뮬레이터 폴더(engine.py · card_pool.json · decks · learned)를 불러올 수 있게 한다 — 상대 경로를 쓰므로 그 폴더로 이동"""
    sim = os.path.abspath(sim)
    if not os.path.exists(os.path.join(sim, 'engine.py')):
        sys.exit(f'engine.py 가 없음: {sim} — --sim 으로 시뮬레이터 폴더(nny_sim)를 지정')
    if sim not in sys.path: sys.path.insert(0, sim)
    os.chdir(sim)
    return sim


class Recorder(list):
    """기록 목록 + 기록 줄마다의 상태 스냅숏. frames[i] = {'k', 'm', 'r', 's'(상태 번호, 라운드 밖이면 -1), 'fx'?}"""

    def __init__(self):
        super().__init__()
        self.game = None; self.round = 0
        self.frames = []; self.states = []; self._last = None
        self.cards = {}                       # uid → [카드 이름, 주인 자리]
        self.pending = []                     # 다음 기록 줄에 붙일 연출
        self.chain_prev = []

    def append(self, e):
        super().append(e)
        k = e.get('k')
        if k == 'snap': return                # 턴 시작 형세 요약 — 상태 스냅숏과 같은 정보
        if k == 'round':
            self.round = e['data']['round']; self.game = None
        fx = self.pending; self.pending = []
        if k == 'res' and self.game is not None:   # 처리 중인 발동은 이미 체인에서 빠졌다 → 직전 체인에서 찾는다
            m = RES_RE.match(e['m']); n = int(m.group(1)) if m else 0
            if 0 < n <= len(self.chain_prev):
                u, num, p, _ = self.chain_prev[n - 1]; fx = fx + [{'t': 'res', 'u': u, 'n': num, 'p': p}]
        fr = {'k': k, 'm': e['m'], 'r': self.round, 's': self.snapshot(), '_e': e}
        if fx: fr['fx'] = fx
        self.frames.append(fr)
        if k == 'end': self.game = None

    # ── 상태 ──
    def reg(self, c):
        self.cards.setdefault(c.uid, [c.name, c.owner])
        return c.uid

    def cell(self, g, c):
        if c is None: return None
        d = {'u': self.reg(c)}
        if not c.faceup: d['f'] = 0
        if c.is_monster() and g.on_field(c):
            d['a'] = g.atk(c); d['d'] = g.df(c)
            if c.pos == 'def': d['p'] = 1
        cnt = {k: v for k, v in c.counters.items() if v}
        if cnt: d['c'] = cnt
        if c.equip_to is not None: d['e'] = self.reg(c.equip_to)
        if g.is_neg(c): d['n'] = 1
        return d

    def state(self, g):
        P = []
        for pl in g.p:
            P.append({'hp': pl.hp, 'hand': [self.reg(c) for c in pl.hand], 'main': len(pl.main), 'upper': len(pl.upper),
                      'grave': [self.reg(c) for c in pl.grave], 'ban': [self.reg(c) for c in pl.banish],
                      'm': [self.cell(g, c) for c in pl.m], 's': [self.cell(g, c) for c in pl.s], 'sk': self.cell(g, pl.skill)})
        ch = [[self.reg(l.card), l.eff.num, l.player, int(bool(l.negated))] for l in g.chain]
        st = {'P': P, 't': g.turn, 'tp': g.turn_player, 'ph': g.phase, 'ch': ch,
              'sh': self.cell(g, g.shared), 'so': g.shared_owner, 'fz': self.cell(g, g.fieldz)}
        if g.shared is not None: st['sc'] = g.shared.controller
        if g.fieldz is not None: st['fc'] = g.fieldz.controller
        return st

    def snapshot(self):
        g = self.game
        if g is None: return -1
        st = self.state(g); self.chain_prev = st['ch']
        key = json.dumps(st, separators=(',', ':'), ensure_ascii=False)
        if key != self._last:
            self.states.append(st); self._last = key
        return len(self.states) - 1

    def export_frames(self):
        """판단 줄의 data는 줄이 붙은 뒤에 채워진다(policy.LearnedAI.choose) → 내보낼 때 읽는다"""
        out = []
        for fr in self.frames:
            e = fr['_e']; fr = {k: v for k, v in fr.items() if k != '_e'}
            d = e.get('data')
            if fr['k'] == 'decision' and d:
                fr['d'] = {'p': d.get('p'), 'q': d.get('decision'), 'pick': d.get('pick'), 'why': d.get('why'),
                           'opts': [list(o[:2]) for o in d.get('opts', [])][:6]}
            if fr['k'] == 'side' and d: fr['d'] = {'swaps': [list(x) for x in d.get('swaps', [])]}
            out.append(fr)
        return out


_HOOKED = False


def install_hooks():
    """Game에 관찰 훅을 단다(한 번만). 기록 대상(log가 Recorder)인 게임에서만 연출을 남긴다"""
    global _HOOKED
    if _HOOKED: return
    import engine
    G = engine.Game
    o_init, o_act, o_atk, o_des = G.__init__, G.activate, G.attack, G.destroy

    def __init__(self, decks, ais, first, rng, log, card_impl):
        o_init(self, decks, ais, first, rng, log, card_impl)
        if isinstance(log, Recorder): log.game = self

    def activate(self, p, c, e, ev=None):
        if isinstance(self.log, Recorder): self.log.pending.append({'t': 'act', 'u': self.log.reg(c), 'n': e.num, 'p': p})
        return o_act(self, p, c, e, ev)

    def attack(self, a, target):
        if isinstance(self.log, Recorder):
            self.log.pending.append({'t': 'atk', 'a': self.log.reg(a), 'd': self.log.reg(target) if target is not None else None, 'p': a.controller})
        return o_atk(self, a, target)

    def destroy(self, c, cause=None, battle=False):
        if isinstance(self.log, Recorder): self.log.pending.append({'t': 'des', 'u': self.log.reg(c)})
        return o_des(self, c, cause, battle)

    G.__init__, G.activate, G.attack, G.destroy = __init__, activate, attack, destroy
    _HOOKED = True


def player_names(a, b):
    """기록 문장의 플레이어 이름 = 스킬(덱) 이름. 미러전이면 자리를 붙인다"""
    return [a, b] if a != b else [f'{a} (P1)', f'{b} (P2)']


def _play(deck_a, deck_b, seed, first, ai, log, policy=None, side=None):
    import season as SE, match as M, match_sim as MS
    decks = SE.load_decks()
    for d in (deck_a, deck_b):
        if d not in decks: sys.exit(f'덱 없음: {d} — 있는 덱: {", ".join(sorted(decks))}')
    make_ai, side_fn = MS._ai_factory({'ai': ai, 'policy': policy, 'side': side})
    names = player_names(deck_a, deck_b)
    dA = dict(decks[deck_a], 이름=names[0]); dB = dict(decks[deck_b], 이름=names[1])
    kw = dict(side=True, side_eps=0.0, learn_side=False)
    if side_fn is not None: kw['side_fn'] = side_fn
    return names, M.play_match(dA, dB, first, random.Random(seed), log, make_ai, **kw)


def record_match(deck_a, deck_b, seed=1, first=0, ai='table', policy=None, side=None):
    """Bo3 매치 1회를 기록 → 재생 화면용 dict"""
    from engine import StalledGame
    import cards as C
    install_hooks()
    rec = Recorder(); stalled = None
    try:
        names, (mw, rounds) = _play(deck_a, deck_b, seed, first, ai, rec, policy, side)
    except StalledGame as ex:   # 1000턴 안전장치 — 판정 없음. 거기까지의 기록은 남긴다
        names, mw, rounds, stalled = player_names(deck_a, deck_b), None, [], str(ex)
    pool = {}
    for name, _ in rec.cards.values():
        d = C.POOL[name]; pool[name] = {k: d[k] for k in POOL_KEYS if d.get(k) not in (None, '', [])}
    return {'schema': 1,
            'meta': {'decks': [deck_a, deck_b], 'names': names, 'seed': seed, 'first': first, 'ai': ai,
                     'winner': mw, 'stalled': stalled,
                     'rounds': [{'first': r['first'], 'winner': r['winner'], 'reason': r['reason'], 'turns': r['turns']} for r in rounds]},
            'cards': {str(u): v for u, v in rec.cards.items()}, 'pool': pool,
            'states': rec.states, 'frames': rec.export_frames()}


def check_same(deck_a, deck_b, seed=1, first=0, ai='heuristic'):
    """같은 시드에서 기록기 없이 돌린 기록 문장과 기록기로 돌린 문장이 같은지 (훅이 게임을 바꾸지 않는다는 확인)"""
    plain = []; _play(deck_a, deck_b, seed, first, ai, plain)
    install_hooks(); rec = Recorder(); _play(deck_a, deck_b, seed, first, ai, rec)
    a = [e['m'] for e in plain]; b = [e['m'] for e in rec]
    return a == b, len(a), len(b)
