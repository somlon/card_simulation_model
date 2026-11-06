"""좌석별 기록 거르기 — 실시간 대전 poll 이 보는 사람(좌석0 · 좌석1 · 관전자)마다 비공개 정보를 서버에서 걸러 보낸다(2026-11-06, 온라인 O2).

예전에는 모든 좌석 · 관전자에게 같은 기록(frames · states · cards 등록표)을 통째로 보내고 화면(board.js)에서만 가렸다 —
사람 대 사람에서는 브라우저 개발자 도구로 상대 패 · 뒷면 카드 이름이 보였다. 여기서는 보는 사람마다 따로 걸러 쌓은 흐름을 둔다.

숨기는 좌석(hidden)의 비공개 카드 = 그 좌석의 패 · 그 좌석이 조종하는 뒷면 카드(몬스터 존 · 마법 존 · 공유 존 · 필드 존).
- 아직 공개된 적 없는 비공개 카드는 가짜 번호(음수 별칭)로 바꾸고, 등록표에는 이름 없이 주인만 보낸다(카드 번호 순서로 덱을 짐작하지 못하게).
  공개 자리(앞면 필드 · 묘지 · 제외 · 체인)에서 곧바로 비공개 자리로 간 카드(예: 묘지 → 패)는 모두가 본 정보라 진짜 번호 그대로.
  어느 자리에도 없게 되면(덱으로 들어감) 아는 카드에서 뺀다 — 다시 뽑히면 모르는 카드.
- 기록 줄: 숨기는 좌석의 드로우 · 시작 패 · 멀리건 · 세트 · 전략 덱 교체 줄은 카드 이름을 모두 「?」로(화면 board.js maskMsg 와 같은 규칙).
  다른 줄은 그 줄의 앞 · 뒤 상태에서 비공개인 카드 이름(공개 자리에 같은 이름이 있으면 제외)을 「?」로 — 서치(「X」 패에 넣음) · 대상 등.
  「공개」 줄(덱에서 공개 → …)은 규칙상 모두가 본 것이라 그대로. 그래서 마지막 줄은 다음 줄(처리 뒤 상태)이 올 때까지 보내지 않는다(sync · 대전 끝은 바로).
- 숨기는 좌석의 판단 줄(판단[이름] …)은 내용(후보 · 고른 것)을 빼고, 전략 덱 교체 프레임의 교체 목록은 카드 이름을 뺀다.
기록 원본(rec)과 대전이 끝난 뒤 저장하는 재생 기록은 그대로다 — 끝난 대전은 재생 목록에서 전부 볼 수 있다.
"""
import re, threading

PRIVATE_LINE = re.compile(r'드로우|시작 패|멀리건|세트$|전략 덱 교체')   # 숨기는 좌석의 이 줄은 카드 이름을 모두 가린다(board.js maskMsg 와 같음)
NAME_RE = re.compile(r'「([^」]+)」')
HIDDEN = '「?」'
UID_KEYS = ('u', 'a', 'd')   # fx(연출)의 카드 번호 칸 — 'to' 는 목록


def hidden_seats(humans, viewer):
    """보는 사람이 볼 수 없는 좌석. viewer: 좌석 번호(그 좌석의 사람) · None(관전자). 사람이 없는 대전(AI끼리)은 모두 공개(화면 규칙과 같음)"""
    if not any(humans): return frozenset()
    if viewer is None: return frozenset((0, 1))
    return frozenset({1 - viewer})


class SeatView:
    """한 매치 · 한 종류의 보는 사람(숨기는 좌석 집합)에 대한 걸러 쌓은 기록. poll 마다 새로 붙은 원본만 이어서 거른다"""

    def __init__(self, rec, names, hidden):
        self.rec = rec; self.names = list(names); self.hidden = frozenset(hidden)
        self.states = []; self.frames = []; self.cards = []    # 걸러 쌓은 것 — 번호는 원본과 같다(states[i] ↔ rec.states[i], frames[j] ↔ rec.frames[j])
        self.sent = set()                                      # 등록표에 이미 보낸 번호
        self.alias = {}; self.next_alias = -1                  # 모르는 비공개 카드: 진짜 번호 → 별칭(음수)
        self.known = set()                                     # 보는 사람이 정체를 아는 카드(공개된 뒤 계속 어느 자리에 있음)
        self.info = []                                         # 상태마다 (번호 바꾸기 표, 모르는 비공개 카드 이름, 공개 자리의 카드 이름)
        self.lock = threading.Lock()

    # ── 상태 ──
    def _cells(self, st):
        """(칸, 그 칸을 조종하는 좌석) — 몬스터 존 · 마법 존 · 스킬 · 공유 존 · 필드 존"""
        for p, P in enumerate(st['P']):
            for c in P['m'] + P['s'] + [P['sk']]: yield c, p
        sc = st.get('sc') or []
        for i, c in enumerate(st.get('sh') or []): yield c, (sc[i] if i < len(sc) else None)
        yield st.get('fz'), st.get('fc')

    def _name(self, u): return (self.rec.cards.get(u) or ['', None])[0]

    def _scan(self, st):
        """상태의 (있는 카드 번호, 숨기는 비공개 카드 번호)"""
        present = set(); private = set()
        for p, P in enumerate(st['P']):
            present.update(P['hand'] + P['grave'] + P['ban'])
            if p in self.hidden: private.update(P['hand'])
        for c, ctl in self._cells(st):
            if not c: continue
            present.add(c['u'])
            if c.get('e') is not None: present.add(c['e'])
            if c.get('f') == 0 and ctl in self.hidden: private.add(c['u'])
        chained = set()
        for lk in st.get('ch') or []:
            present.add(lk[0]); chained.add(lk[0])
            if len(lk) > 4: present.update(lk[4])
        return present, private - chained   # 체인에 오른(효과를 발동한) 카드는 패에서 발동했어도 모두가 본 카드

    def _alias(self, u):
        if u not in self.alias: self.alias[u] = self.next_alias; self.next_alias -= 1
        return self.alias[u]

    def _register(self, x, real=None):
        if x in self.sent: return
        self.sent.add(x)
        if x >= 0: self.cards.append((x, self.rec.cards.get(x)))
        else: self.cards.append((x, ['', (self.rec.cards.get(real) or [None, None])[1]]))   # 별칭: 이름 없이 주인만

    def _state(self, i):
        st = self.rec.states[i]
        present, private = self._scan(st)
        unknown = {u for u in private if u not in self.known}
        tr = {u: self._alias(u) for u in unknown}
        public = present - private
        names = {self._name(u) for u in unknown}; pub = {self._name(u) for u in public}
        f = lambda u: tr.get(u, u)

        def cell(c):
            if not c: return c
            d = dict(c); d['u'] = f(c['u'])
            if d.get('e') is not None: d['e'] = f(d['e'])
            return d
        out = {k: v for k, v in st.items() if k not in ('P', 'sh', 'fz', 'ch')}
        out['P'] = [dict(P, hand=[f(u) for u in P['hand']], m=[cell(c) for c in P['m']], s=[cell(c) for c in P['s']], sk=cell(P['sk']))
                    for P in st['P']]
        out['sh'] = [cell(c) for c in st.get('sh') or []]; out['fz'] = cell(st.get('fz'))
        out['ch'] = [lk[:4] + ([[f(x) for x in lk[4]]] if len(lk) > 4 else []) for lk in st.get('ch') or []]
        for u in present: self._register(f(u), u)
        # 다음 상태를 위해: 아는 카드 = (계속 어느 자리에 있는 아는 카드) + 지금 공개 자리의 카드. 자리에서 사라진(덱으로 간) 카드는 별칭도 버린다
        self.known = (self.known & present) | public
        for u in [u for u in self.alias if u not in present or u in public]: del self.alias[u]
        self.info.append((tr, names, pub))
        self.states.append(out)

    def _upto_state(self, i):
        while len(self.states) <= i and len(self.states) < len(self.rec.states): self._state(len(self.states))

    # ── 기록 줄 ──
    def _owner(self, m):
        """줄을 남긴 좌석(「이름 …」 · 「판단[이름] …」) — 이름이 겹치면 긴 이름부터"""
        for s in sorted(range(len(self.names)), key=lambda s: -len(self.names[s])):
            n = self.names[s]
            if m.startswith(f'판단[{n}]') or m == n or m.startswith(n + ' ') or m.startswith(n + ':'): return s
        return None

    def _frame(self, j):
        rec = self.rec; fr = rec.export_frame(rec.frames[j])
        s = fr.get('s', -1)
        nxt = rec.frames[j + 1].get('s', -1) if j + 1 < len(rec.frames) else -1
        prev = next((rec.frames[i].get('s', -1) for i in range(j - 1, -1, -1) if rec.frames[i].get('s', -1) != s), -1)
        self._upto_state(max(s, nxt))
        # 비공개 이름 = 앞(직전 줄) · 이 줄 · 다음 줄 상태에서 모르는 비공개 카드의 이름 − 이 줄 · 다음 줄 상태에서 공개 자리에 있는 이름
        # (직전 상태: 패에서 덱으로 돌아간 카드처럼 줄이 남을 때는 이미 자리를 떠난 카드 · 다음 상태: 서치처럼 처리 뒤에야 패에 들어온 카드)
        get = lambda x: self.info[x] if 0 <= x < len(self.info) else None
        near = [get(x) for x in (prev, s, nxt)]
        names = set().union(*(i[1] for i in near if i)) - set().union(*(i[2] for i in near[1:] if i))
        tr = {}
        for i in near[1:]:
            if i: tr.update(i[0])   # 뒤 상태의 별칭이 앞 상태의 것을 덮는다(처리 뒤 자리 기준)
        m = fr.get('m') or ''; owner = self._owner(m)
        if owner in self.hidden and fr['k'] == 'decision' and m.startswith(f'판단[{self.names[owner]}]'):
            return {'k': 'decision', 'm': f'판단[{self.names[owner]}]', 'r': fr.get('r'), 's': s, 'd': {'p': owner}}   # 판단 내용은 뺀다
        if owner in self.hidden and PRIVATE_LINE.search(m): m = NAME_RE.sub(HIDDEN, m)
        elif ' 공개' not in m: m = NAME_RE.sub(lambda x: HIDDEN if x.group(1) in names else x.group(0), m)
        fr['m'] = m
        if fr['k'] == 'side' and owner in self.hidden and fr.get('d'):
            fr['d'] = {'swaps': [['?', '?'] + list(x[2:]) for x in fr['d'].get('swaps', [])]}
        if fr['k'] == 'decision' and fr.get('d') and owner in self.hidden: fr.pop('d')
        if fr.get('fx'):
            fx = []
            for e in fr['fx']:
                e = dict(e)
                for k in UID_KEYS:
                    if e.get(k) is not None: e[k] = tr.get(e[k], e[k])
                if e.get('to'): e['to'] = [tr.get(x, x) for x in e['to']]
                fx.append(e)
                for k in UID_KEYS:   # 앞 · 뒤 상태 어디에도 없는 숨기는 좌석의 모르는 카드(덱 안 등)도 진짜 번호를 내지 않는다
                    if isinstance(e.get(k), int): e[k] = self._fx_uid(e[k])
                if e.get('to'): e['to'] = [self._fx_uid(x) for x in e['to']]
                for x in [e.get(k) for k in UID_KEYS] + list(e.get('to') or []):
                    if isinstance(x, int): self._register(x, x)
            fr['fx'] = fx
        return fr

    def _fx_uid(self, x):
        if x < 0 or x in self.sent or x in self.known: return x
        owner = (self.rec.cards.get(x) or [None, None])[1]
        return self._alias(x) if owner in self.hidden else x

    def sync(self, final=False, settled=False):
        """원본에 새로 붙은 것을 걸러 쌓는다. 마지막 줄은 다음 줄이 올 때까지 둔다 — sync 프레임 · final(대전 끝) ·
        settled(엔진이 사람의 답을 기다리며 멈춤 — 그 줄 뒤로 바뀔 상태가 아직 없다)이면 바로"""
        rec = self.rec
        with self.lock:
            n = len(rec.frames)
            limit = n if final or settled or (n and rec.frames[n - 1].get('k') == 'sync') else n - 1
            while len(self.frames) < limit: self.frames.append(self._frame(len(self.frames)))
            self._upto_state(len(rec.states) - 1)

    def view(self, f_from, s_from, c_from, final=False, settled=False):
        self.sync(final, settled)
        return self.frames[f_from:], self.states[s_from:], self.cards[c_from:]

    def map_uids(self, us):
        """질문 후보의 빛낼 카드(진짜 번호) → 이 보는 사람의 번호(모르는 비공개 카드는 별칭)"""
        return [self.alias.get(u, u) for u in us]
