"""학습형 판단 정책 (LearnedAI).
모든 판단 지점을 「후보 → 학습 승률표로 선택」으로 바꾼다. 휴리스틱 점수는 데이터가 없을 때의 사전값(prior)으로만 쓰이고,
판이 쌓일수록 실제 승률이 사전값을 대체한다.

승률표는 세 단계로 추정한다(계층 축소 추정).
  L0: (덱 · 판단 종류 · 후보)                    — 상대를 묶은 평균. 처음 보는 상대 · 드문 판단의 공백을 채운다
  L1: (덱 · 상대 · 판단 종류 · 후보)           — 상황과 무관한 평균
  L2: L1 + 상황 구간(턴 · 차례 · HP 차 · 상대 필드 · 내 몬스터 · 패 수)
  값 = (L2 승수 + a·L1추정) / (L2 판수 + a),  L1추정 = (L1 승수 + a·L0추정) / (L1 판수 + a),
  L0추정 = (L0 승수 + a·사전값) / (L0 판수 + a).  L0이 없는 예전 표는 L1추정이 곧바로 사전값으로 줄어든다(예전과 같음).
판이 끝나면 그 판에서 내린 모든 판단에 승패를 반영한다(몬테카를로 학습).

사용자 지침(하드 제약)은 학습 대상이 아니다: 번성충 일반소환은 결착 시에만, 공유 존 사용 조건,
결착 공격 우선(이번 공격으로 상대 HP가 0이 되면 반드시 공격).
시작 패 배분 · 멀리건 재배분은 판단 대상이다(사용자 지시 2026-10-06) — 예전 고정표는 사전값으로만 쓴다.
"""
import json, os, math
from ai import HeuristicAI, INTERFERE, LEARN_DIR, p_skill
from cards import value, VETO

A = 20.0   # 축소 강도 (가상 판수)


class ReplayDesync(Exception):
    pass


def k0_of(k1):
    """L1 키 「덱 vs 상대|판단|후보」 → L0 키 「덱 vs *|판단|후보」"""
    i = k1.find(' vs ')
    j = k1.find('|', i) if i >= 0 else -1
    return k1[:i] + ' vs *' + k1[j:] if j > 0 else None


class Table:
    def __init__(self, name):
        self.path = os.path.join(LEARN_DIR, name + '.json')
        d = {}; self.source = None                    # source: 실제로 읽은 파일 (결과 메타의 해시용)
        for path in (self.path, self.path + '.gz'):   # 큰 표는 압축본(.json.gz)으로 보관할 수 있다
            if os.path.exists(path):
                try: d = self.read(path); self.source = path; break
                except Exception: d = {}
        self.L0 = d.get('L0', {}); self.L1 = d.get('L1', {}); self.L2 = d.get('L2', {}); self.games = d.get('games', 0)

    @staticmethod
    def read(path):
        import gzip
        with (gzip.open(path, 'rt', encoding='utf-8') if path.endswith('.gz') else open(path, encoding='utf-8')) as f:
            return json.load(f)

    @classmethod
    def load(cls, path):
        """파일 경로(.json · .json.gz) → Table"""
        t = cls.__new__(cls); d = cls.read(path)
        t.path = path; t.source = path; t.L0 = d.get('L0', {}); t.L1 = d.get('L1', {}); t.L2 = d.get('L2', {}); t.games = d.get('games', 0)
        return t

    def value(self, k1, k2, prior):
        k0 = k0_of(k1)
        if k0 is not None and self.L0:
            w0, n0 = self.L0.get(k0, (0, 0)); prior = (w0 + A * prior) / (n0 + A)
        w1, n1 = self.L1.get(k1, (0, 0)); m1 = (w1 + A * prior) / (n1 + A)
        w2, n2 = self.L2.get(k2, (0, 0)); return (w2 + A * m1) / (n2 + A), n1, n2

    def update(self, k1, k2, won):
        a = self.L1.setdefault(k1, [0, 0]); a[0] += won; a[1] += 1
        b = self.L2.setdefault(k2, [0, 0]); b[0] += won; b[1] += 1
        k0 = k0_of(k1)
        if k0 is not None:
            c = self.L0.setdefault(k0, [0, 0]); c[0] += won; c[1] += 1

    def rebuild_L0(self):
        """L1을 상대에 걸쳐 합해 L0을 다시 만든다 (L0이 없던 예전 표에 붙일 때)"""
        self.L0 = {}
        for k1, (w, n) in self.L1.items():
            k0 = k0_of(k1)
            if k0 is None: continue
            c = self.L0.setdefault(k0, [0, 0]); c[0] += w; c[1] += n

    def save(self, path=None):
        import gzip
        path = path or self.path
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        r = lambda x: round(x, 3) if isinstance(x, float) else x     # 망각(γ)으로 생긴 실수 판수는 소수 3자리로
        rd = lambda D: {k: [r(v[0]), r(v[1])] for k, v in D.items()}
        d = {'games': self.games, 'L1': rd(self.L1), 'L2': rd(self.L2)}
        if self.L0: d['L0'] = rd(self.L0)
        with (gzip.open(path, 'wt', encoding='utf-8', compresslevel=6) if path.endswith('.gz') else open(path, 'w', encoding='utf-8')) as f:
            json.dump(d, f, ensure_ascii=False)


POLICY = Table('policy')


def prior_of(h, scale):
    return 0.5 + 0.15 * math.tanh(h / scale)


class LearnedAI(HeuristicAI):
    def __init__(self, skill, split_override=None, learn=True, eps=0.0, table=None):
        super().__init__(skill, split_override)
        self.learn = learn; self.eps = eps; self.trace = []
        self.table = table          # 이 AI만 쓰는 학습표(표끼리 맞대결 평가용). None이면 전역 POLICY

    @property
    def T(self):
        return self.table if self.table is not None else POLICY

    # ── 공통 선택기 ──
    def bucket(self, g, p):
        d = g.p[p].hp - g.p[1 - p].hp
        hp = 'A' if d >= 1000 else 'B' if d <= -1000 else 'E'
        return (f't{min(g.turn, 5)}{"M" if g.turn_player == p else "O"}|{hp}|of{min(len(g.field_cards(1 - p)), 3)}'
                f'|mm{min(len(g.monsters(p)), 2)}|h{min(len(g.p[p].hand), 4)}')

    def choose(self, g, p, decision, opts, scale=40.0, log=True, explore='eps'):
        """opts: [(label, heuristic_score, payload)] → payload
        explore: 학습 중(learn · eps>0) 탐색 방식. 'eps' = ε 확률로 균등 선택,
        'thompson' = 후보마다 사후분포 Beta(v·(n+A), (1−v)·(n+A))에서 뽑은 값이 가장 큰 후보 — 판 시작에 한 번 내리는 결정용"""
        if not opts: return None
        sc = getattr(g, 'script', None)
        if sc is not None:                                   # 탐색용 재현 게임
            if sc['pos'] < len(sc['seq']):
                pl, idx = sc['seq'][sc['pos']]; sc['pos'] += 1
                if pl != p or idx >= len(opts): raise ReplayDesync()
                return self._rec(g, p, idx, opts)
            if not sc['forced']:
                sc['forced'] = True
                if p != sc['player'] or sc['force'] >= len(opts): raise ReplayDesync()
                sc['determinize'](g, p)
                return self._rec(g, p, sc['force'], opts)
        me = g.p[p].skill.name; op = g.p[1 - p].skill.name
        base = f'{me} vs {op}|{decision}|'; b = self.bucket(g, p)
        scored = []
        for lab, h, pay in opts:
            k1 = base + lab; k2 = k1 + '|' + b
            v, n1, n2 = self.T.value(k1, k2, prior_of(h, scale))
            scored.append((v, lab, pay, k1, k2, n1, n2))
        scored.sort(key=lambda x: -x[0])
        if explore == 'thompson' and self.learn and self.eps:
            pick = max(scored, key=lambda x: g.rng.betavariate(max(x[0] * (x[6] + A), 1e-3), max((1 - x[0]) * (x[6] + A), 1e-3)))
            why = '톰슨 탐색' if pick is not scored[0] else '학습값'
        elif self.eps and g.rng.random() < self.eps:
            pick = g.rng.choice(scored); why = '탐색'
        else:
            pick = scored[0]; why = '학습값'
        if self.learn: self.trace.append((pick[3], pick[4]))
        if log and len(scored) > 1 and getattr(g, 'script', None) is None:
            cs = ', '.join(f'{lab}={v*100:.1f}%(n{n2}/{n1})' for v, lab, _, _, _, n1, n2 in scored[:8])
            g.L(f'판단[{g.pname(p)}] {decision}: {{{cs}}} → {pick[1]} ({why})', 'decision')
            g.log[-1]['data'] = {'p': p, 'decision': decision, 'pick': pick[1], 'why': why, 'pick_n1': pick[5], 'pick_n2': pick[6],
                                 'opts': [(lab, round(v * 100, 1), n2) for v, lab, _, _, _, n1, n2 in scored[:4]]}
        idx = next(i for i, o in enumerate(opts) if o[0] == pick[1])
        return self._rec(g, p, idx, opts)

    @staticmethod
    def _rec(g, p, idx, opts):
        if hasattr(g, 'dlog'): g.dlog.append((p, idx))
        return opts[idx][2]

    def end_game(self, g, p, winner):
        if winner is not None and self.learn:
            for k1, k2 in self.trace: self.T.update(k1, k2, int(winner == p))
        self.trace = []

    # ── 드로우 · 멀리건 ──
    def choose_draw_deck(self, g, p):
        lo, hi = self.pol['upper_in_hand']
        ups = sum(1 for c in g.p[p].hand if c.deck_kind() == '상급')
        heur = 'upper' if ups < lo and g.p[p].upper else 'main'
        return self.choose(g, p, f'드로우 덱(패의 상급 {min(ups,2)})', [('메인', 5 if heur == 'main' else 0, 'main'), ('상급', 5 if heur == 'upper' else 0, 'upper')])

    # ── 시작 패 배분 · 멀리건 재배분 ──
    # 후보 = 규칙상 가능한 모든 배분(메인 k장 / 상급 n−k장). 키 = 덱 · 상대 · 선후공이라 덱과 매치업마다 따로 배운다.
    # 사전값은 지침 · 측정표의 배분(재배분은 되돌린 카드와 같은 배분)에 가까울수록 높다.
    LEARN_SPLIT = True

    @staticmethod
    def split_opts(k0, lo, hi):
        return [(f'메인 {k}', 5.0 - 3.0 * abs(k - k0), k) for k in range(lo, hi + 1)]

    def choose_split(self, g, p, n):
        if not self.LEARN_SPLIT or self.split_override:
            return HeuristicAI.choose_split(self, g, p, n)
        pl = g.p[p]
        lo, hi = max(0, n - len(pl.upper)), min(n, len(pl.main))
        k0 = max(lo, min(hi, self.split_default(g, p, n)[0]))
        pos = '선공' if g.first == p else '후공'
        # DRLAI도 학습표로 고른다(DRL 판단 종류에 없음)
        return LearnedAI.choose(self, g, p, f'시작 패 배분({pos})', self.split_opts(k0, lo, hi), scale=10, explore='thompson')

    def mulligan_split(self, g, p, back):
        """멀리건으로 다시 뽑을 매수 중 메인 덱 몫 (§4 STEP 6: 배분을 바꿀 수 있다). 되돌린 카드는 이미 덱에 있다"""
        n0 = HeuristicAI.mulligan_split(self, g, p, back)
        if not self.LEARN_SPLIT or self.split_override:
            return n0
        pl = g.p[p]; n = len(back)
        lo, hi = max(0, n - len(pl.upper)), min(n, len(pl.main))
        if lo >= hi: return lo
        ups = sum(1 for c in pl.hand if c.deck_kind() == '상급')
        pos = '선공' if g.first == p else '후공'
        return LearnedAI.choose(self, g, p, f'시작 패 재배분({pos}·{n}장·남은 상급 {min(ups, 3)})',
                                self.split_opts(max(lo, min(hi, n0)), lo, hi), scale=10, explore='thompson')

    # ── 2 · 3라운드 선후공 ──
    # 이전 라운드 패자가 정한다(정본 4, §11-2). 키 = 덱 · 상대 · 라운드, 결과 = 그 선택으로 시작한 라운드의 승패.
    # (2라운드 패배 = 매치 패배, 2라운드 승리 후 3라운드 선후공은 상대가 정하므로 라운드 승률 최대화가 곧 매치 승률 최대화)
    LEARN_FIRST = True

    def choose_first(self, me_skill, opp_skill, rnd, rng, log=None, pname=''):
        h = self.wants_first(opp_skill)
        self._first_key = None
        if not self.LEARN_FIRST:
            return h
        base = f'{me_skill} vs {opp_skill}|선후공 선택({rnd}라운드)|'
        scored = []
        for lab, go in (('선공', True), ('후공', False)):
            k1 = base + lab; k2 = k1 + '|-'
            v, n1, n2 = self.T.value(k1, k2, prior_of(5 if go == h else 0, 10))
            scored.append((v, lab, go, k1, k2, n1, n2))
        scored.sort(key=lambda x: -x[0]); pick = scored[0]; why = '학습값'
        if self.learn and self.eps:   # 매치마다 한 번뿐인 결정 → 톰슨 표본으로 탐색
            pick = max(scored, key=lambda x: rng.betavariate(max(x[0] * (x[6] + A), 1e-3), max((1 - x[0]) * (x[6] + A), 1e-3)))
            why = '톰슨 탐색' if pick is not scored[0] else why
        if self.learn: self._first_key = (pick[3], pick[4])
        if log is not None:
            cs = ', '.join(f'{lab}={v*100:.1f}%(n{n2})' for v, lab, _, _, _, _, n2 in scored)
            log.append({'t': 0, 'ph': '', 'tp': 0, 'k': 'decision', 'm': f'판단[{pname}] {rnd}라운드 선후공: {{{cs}}} → {pick[1]} ({why})',
                        'data': {'decision': f'선후공 선택({rnd}라운드)', 'pick': pick[1], 'why': why,
                                 'opts': [(lab, round(v * 100, 1), n2) for v, lab, _, _, _, _, n2 in scored]}})
        return pick[2]

    def first_result(self, won):
        k = getattr(self, '_first_key', None)
        if k and self.learn: self.T.update(k[0], k[1], int(won))
        self._first_key = None

    def mulligan(self, g, p, hand):
        heur = set(id(c) for c in super().mulligan(g, p, hand))
        back = []
        for c in hand:
            r = self.choose(g, p, f'멀리건:{c.name}', [('유지', 0 if id(c) in heur else 5, False), ('되돌림', 5 if id(c) in heur else 0, True)])
            if r: back.append(c)
        return back

    # ── 선택 ──
    def pick_search(self, g, p, cands, why):
        uniq = {}
        for c in cands: uniq.setdefault(c.name, c)
        return self.choose(g, p, f'서치:{why}', [(n, self.card_pri(g, p, c) * 3, c) for n, c in uniq.items()], scale=30, log=len(uniq) > 1)

    def prefers_place(self, g, p, conts):
        return self.choose(g, p, '인카운터 분기', [('지속 마법', 5 if len(g.spells(p)) < 2 else 0, True), ('시아·시엘 서치', 0 if len(g.spells(p)) < 2 else 5, False)])

    def pick_target(self, g, p, cands, purpose='remove', any_side=False):
        if not cands: return None
        pool = cands
        if any_side:
            opp = [c for c in cands if c.controller != p]; pool = opp or cands
        heur = HeuristicAI.pick_target(self, g, p, cands, purpose, any_side)
        uniq = {}
        for c in pool: uniq.setdefault((c.name, c.controller == p, c.zone), c)
        opts = [(f'{"자" if own else "상"}:{n}@{z}', (10 if c is heur else 0) + value(g, c) * 3, c) for (n, own, z), c in uniq.items()]
        return self.choose(g, p, f'대상:{purpose}', opts, scale=20, log=len(opts) > 1)

    def pick_discard(self, g, p, hand):
        uniq = {}
        for c in hand: uniq.setdefault(c.name, c)
        return self.choose(g, p, '버릴 카드', [(n, -self.card_pri(g, p, c) * 3 - value(g, c), c) for n, c in uniq.items()], scale=30, log=len(uniq) > 1)

    def choose_summon_pos(self, g, p, c, how):
        """소환 표시 형식 (모든 일반소환 · 특수소환, Game.summon_pos가 묻는다). 학습 대상 —
        키: 「소환 표시 형식:일반|특수」 × 후보(공격 표시:카드 / 수비 표시:카드). 데이터가 없으면 휴리스틱 판단이 사전값으로 이긴다.
        LearnedAI.choose를 직접 부른다: DRL 에이전트(DRLAI)도 이 판단은 학습표 경로로 고른다 — DRL 특징 스키마에 아직 이 판단 종류가 없음"""
        heur, _ = self.summon_pos_heuristic(g, p, c, how)
        opts = [(f'공격 표시:{c.name}', 5 if heur == 'atk' else 0, 'atk'), (f'수비 표시:{c.name}', 5 if heur == 'def' else 0, 'def')]
        return LearnedAI.choose(self, g, p, f'소환 표시 형식:{"일반" if how == "normal" else "특수"}', opts)

    def use_shared(self, g, p, c, full=True):
        ok = HeuristicAI.use_shared(self, g, p, c, full)
        return ok   # 사용자 지침(하드 제약) — 학습 대상 아님

    def breeding_pick(self, g, p, cands):
        k = sum(1 for x in g.p[p].hand if x.name in INTERFERE)
        inter = [x for x in cands if x.name in INTERFERE]; eng = [x for x in cands if x.name not in INTERFERE]
        opts = []
        if inter: opts.append(('견제', 5, max(inter, key=lambda c: self.card_pri(g, p, c))))
        if eng: opts.append(('엔진', 0, max(eng, key=lambda c: self.card_pri(g, p, c))))
        when = '자신턴' if g.turn_player == p else '상대턴'
        return self.choose(g, p, f'번식지({when}·견제패{min(k,3)})', opts)

    # ── 트리거 · 대응 ──
    def choose_triggers(self, g, p, cands):
        out = []
        for c, e, ev in cands:
            s = e.score(g, c, p, ev) if e.score else 1
            if e.mandatory: out.append((1.0, c, e, ev)); continue
            if s <= VETO: continue   # 규칙상 발동할 수 있으나 AI는 쓰지 않는 경우
            go = self.choose(g, p, f'트리거:{c.name}#{e.num}', [('발동', s, True), ('안 함', 0, False)])
            if go: out.append((s, c, e, ev))
        out.sort(key=lambda x: -x[0])
        return [(c, e, ev) for _, c, e, ev in out]

    def respond(self, g, p, opts):
        cand = [('패스', 0, None)]
        seen = set()
        for c, e in opts:
            lab = f'{c.name}#{e.num}'
            if lab in seen: continue
            s = e.score(g, c, p, g.chain) if e.score else 0
            if s <= VETO: continue
            seen.add(lab)
            cand.append((lab, s, (c, e)))
        if len(cand) == 1: return None
        if self.PASS_EVAL:   # 패스 = 남겨 둔 선택지의 가치, 발동 = 즉시 이득 + 남은 가치 − 쓰는 카드의 보유 가치(위협도만큼 할인)
            R = self.reserve(g, p)
            cand = [(lab, R if pay is None else s + R - self.spend_cost(g, p, pay[0], respond=True), pay) for lab, s, pay in cand]
        return self.choose(g, p, '대응' if g.chain else '우선권', cand)

    # ── 진행 / 정비 ──
    def main_phase(self, g, p, ph):
        for _ in range(40):
            acts = [('종료', 0, None)]; seen = set()
            if ph == '진행' and g.p[p].normal_summons > 0:
                for c in g.p[p].hand:
                    if c.type != '몬스터' or c.flags.get('effect_only') or c.flags.get('no_normal') or g.tributes_needed(c.level) > 0: continue
                    if g.rule('no_special', c, p) or not g.can_place(c, p): continue
                    if c.has('솔루나') and any(x.has('솔루나') and x.is_monster() for x in g.monsters(p)): continue
                    s = 20 + g.atk(c) / 100 + (40 if c.has('솔루나') else 0)
                    if c.has('번성충'):
                        if self.lethal_damage(g, p, c) < g.p[1 - p].hp: continue   # 사용자 지침: 결착 시에만
                        s = 95
                    lab = f'소환:{c.name}'
                    if lab not in seen: seen.add(lab); acts.append((lab, s, ('summon', c, None)))
                for c in g.p[p].hand:   # 대체 일반소환 (치프 세리 등 「…하는 것으로 일반소환할 수 있다」)
                    alt = getattr(c, 'alt_normal', None)
                    if alt and alt[0](g, p) and g.can_place(c, p):
                        lab = f'특수 일반소환:{c.name}'
                        if lab not in seen: seen.add(lab); acts.append((lab, 70, ('alt', c, None)))
            for lab, s, pay in self.extra_summon_options(g, p) + self.position_options(g, p, ph):   # 제물 · 수비 소환, 표시 형식 변경
                if s <= VETO or lab in seen: continue
                seen.add(lab); acts.append((lab, s, ('extra', pay[1], pay)))
            for c, e in g.options(p, ('ignition', 'quick')):
                lab = f'발동:{c.name}#{e.num}'
                if lab in seen: continue
                s = e.score(g, c, p, None) if e.score else 0
                if s <= VETO: continue
                seen.add(lab); acts.append((lab, s, ('act', c, e)))
            if g.free_s(p):
                for c in g.p[p].hand:
                    if c.type == '마법' and c.d.get('subtype') in ('트리거', '신속') and not getattr(c.effects[0], 'hand_ok', False) \
                       and any(e.kind in ('resp', 'trigger', 'quick') for e in c.effects):
                        lab = f'세트:{c.name}'
                        if lab not in seen: seen.add(lab); acts.append((lab, 8, ('set', c, None)))
            if len(acts) == 1: return
            if self.PASS_EVAL:   # 종료 = 남겨 둔 선택지의 가치, 행동 = 즉시 이득 + 남은 가치 − 패에서 쓰는 카드의 보유 가치
                R = self.reserve(g, p)
                acts = [(lab, R if pay is None else s + R - (self.spend_cost(g, p, pay[1]) if pay[0] in ('summon', 'alt', 'act', 'extra') else 0), pay)
                        for lab, s, pay in acts]
            pick = self.choose(g, p, f'{ph} 행동', acts)
            if pick is None: return
            kind, c, e = pick
            if kind == 'summon': g.normal_summon(c, p); g.after_action(p)
            elif kind == 'alt':
                c.alt_normal[1](g, p); g.L(f'{g.pname(p)} {c} 조건 충족 — 제물 없이 일반소환'); g.normal_summon(c, p); g.after_action(p)
            elif kind == 'act': g.act(p, c, e)
            elif kind == 'extra': self.do_extra(g, p, e)
            else: g._remove(c); g.place_spell(c, p, False); g.L(f'{g.pname(p)} 마법 1장 세트')

    # ── 전투 ──
    def battle_phase(self, g, p):
        for _ in range(20):
            if g.no_attack.get(p) == g.turn: g.L('공격 봉인 상태', 'sys'); return
            attackers = [m for m in g.monsters(p) if m.faceup and m.pos == 'atk' and m.summon_turn <= g.turn
                         and m.attacks_made < self.max_attacks(g, m)]
            if not attackers: return
            if self.take_lethal(g, p, attackers): continue   # 결착 우선 지침 — 학습 대상 아님
            opts = [('공격 종료', 0, None)]; seen = set()
            for a in attackers:
                av = g.atk(a)
                if g.can_direct(a) and not (a.flags.get('attack_all') and g.monsters(1 - p)):
                    lab = f'{a.name}→직접'
                    if lab not in seen: seen.add(lab); opts.append((lab, av + 500, (a, None)))
                for t in g.attack_targets(a):
                    tv = g.atk(t) if t.pos == 'atk' else g.df(t)
                    h = (200 + value(g, t) * 400 + (av - tv if t.pos == 'atk' else 0)) if av > tv else (50 if av == tv else -300)
                    lab = f'{a.name}→{t.name}'
                    if lab not in seen: seen.add(lab); opts.append((lab, h, (a, t)))
            if g.rule('must_attack', p) and len(opts) > 1:
                opts = opts[1:]   # 격투가의 투기장: 공격 가능한 몬스터가 있으면 반드시 공격
            pick = self.choose(g, p, '공격', opts, scale=400)
            if pick is None: return
            g.attack(*pick)
