"""조립기 (blocks/README.md) — 조립 명세 → engine.Effect · [지속] 훅.

문장마다 한 번 효과 함수의 소스를 만들어 컴파일하고(코드 생성 — 블록 통합 결정 2026-10-27 ②), (카드 코드, 효과 키, 문장)으로 캐시한다.
캐시는 프로세스 단위(카드 객체 단위로 두면 판마다 쌓여 누수)이고, 같은 카드의 모든 인스턴스가 같은 Effect 객체를 함께 쓴다.

효과 함수의 동작:
  cond  — 발동 시점(E) · 발동 조건(C1) · 단계 제한 · 재정 G2(코스트를 낼 수 있고 모든 처리를 할 수 있어야 발동 선언)
  cost  — 응답할 발동 기록(E2) · 코스트 · 발동 시 고르는 대상(텍스트 순서). 하나라도 안 되면 발동 취소
  res   — 처리 블록을 텍스트 순서대로. 재정 G2: 앞 처리를 하지 못하면 뒤 처리는 하지 않는다(「…할 수 있다」 처리는 건너뛰어도 이어 감)
  score — B안: 시점 보정 × (처리 블록 가치의 합 − 코스트 블록 가치의 합)
"""
from engine import Effect
from blocks import text as T, lib as L, dsl as D, status as ST

KIND = {'신속': 'quick', '트리거': 'trigger', '유언': 'lastwill', '소환': 'summon', '전투': 'battle', '지속': 'cont', '제약': 'restrict', '': 'ignition'}
SPELL_ACT_SUB = ('일반', '신속', '트리거')
DISRUPT = {'destroy', 'move', 'release', 'negate_link', 'negate_card', 'equip', 'equip_card'}
# 가치 함수가 그때 상황을 직접 보는 블록(쓸 때가 아니면 가치가 0 이하) — 점수의 시점 보정을 하지 않는다
AWARE = {'no_attack', 'floating', 'replace', 'status', 'negate_link', 'negate_chain', 'no_damage'}


class TemplateMismatch(Exception):
    """조립표의 문장 틀이 카드 텍스트와 맞지 않는다 — 텍스트가 바뀌었으면 조립표를 고친다"""


_CACHE = {}


def attach(c):
    """카드 c에 조립표의 효과 · [지속] 훅을 붙인다. 조립표가 없는 카드면 False(옛 함수를 쓴다)"""
    code = c.d.get('code')
    specs = D.TABLE.get(code)
    if specs is None: return False
    sents = T.sentences(c.d)
    effects = []
    for key, spec in specs.items():
        if spec.kw.get('granted'): continue   # 부여 효과는 받는 카드에 붙는다(A22 — do_grant · 부여 [지속])
        if spec.kw.get('follow'): continue    # 「n번 효과 처리 시에 …」 — n번 효과의 처리에 딸린다(make_effect)
        sent = sents.get(key)
        ck = (code, key, sent)
        proto = _CACHE.get(ck)
        if proto is None:
            proto = _CACHE[ck] = compile_spec(spec, sent, c.d)
        if proto.effect is not None: effects.append(proto.effect)
        for inst in proto.installs: inst(c)
    from cards import grp
    for group, lst in D.CONT_GRANTS.items():   # 「자신 필드의 「X」 몬스터는 다음의 효과를 얻는다」 [지속] — 그 카드군 카드마다 붙이고, 발동은 부여가 적용될 때만
        if grp(c, group):
            effects += [cont_granted_effect(code, key, num) for code, key, num in lst]
    if c.type == '몬스터' and (c.d.get('level') or 0) >= 5 and any(e.kind == 'summon' for e in effects):
        c.ns_value = ns_value_of(c)   # 제물 일반소환의 가치(ai.extra_summon_options): [소환] 효과 가치를 더한다(B안)
    import cards
    tax = cards.action_taxes(c.d)            # [지속] 행동 세금 (engine.Game.taxes)
    if tax: c.action_tax = tax
    effects += [e for e in c.effects if e.num == 0]     # 카드를 놓기만 하는 발동(지속 · 필드 마법 — status.place_effect)
    c.effects = sorted(effects, key=lambda e: e.num)
    if (c.type in ('필드',) or (c.type == '마법' and c.d.get('subtype') == '지속')) and not any(sp.kw.get('no_place') for sp in specs.values()):
        if not any(e.num == 0 for e in c.effects): c.effects.insert(0, ST.place_effect(c))
    return True


class Proto:
    __slots__ = ('effect', 'installs')

    def __init__(self, effect=None, installs=()):
        self.effect = effect; self.installs = list(installs)


# ═══════════════════════ 명세 해석 ═══════════════════════
def _sub(v, holes):
    """명세 값의 '$이름'을 문장에서 읽은 수로 바꾼다 (중첩 dict · 튜플 · 리스트 · Blk 포함)"""
    if isinstance(v, str) and v.startswith('$'):
        return holes[v[1:]]
    if isinstance(v, str) and v.startswith('-$'):   # 「…가 n 내려간다」 → −n
        return -holes[v[2:]]
    if isinstance(v, D.Blk): return D.Blk(v.name, _sub(v.k, holes))
    if isinstance(v, dict): return {a: _sub(b, holes) for a, b in v.items()}
    if isinstance(v, list): return [_sub(x, holes) for x in v]
    if isinstance(v, tuple) and not (v and v[0] == 'ref'): return tuple(_sub(x, holes) for x in v)
    return v


def compile_spec(spec, sent, d):
    if sent is None:
        raise TemplateMismatch(f'{spec.code} {spec.key}: 카드 텍스트에 이 효과 문장이 없다')
    holes = T.match(spec.tmpl, sent)
    if holes is None:
        raise TemplateMismatch(f'{spec.code} {spec.key}: 문장 틀이 텍스트와 맞지 않는다\n  틀:   {T.norm(spec.tmpl)}\n  문장: {sent}')
    kw = _sub(dict(spec.kw), holes)
    notes = T.notes(sent)
    kind = kw.get('kind') or KIND.get(T.keyword(sent), 'ignition')
    if not kw.get('kind') and not T.keyword(sent) and d.get('type') == '마법' and spec.key == '1':   # 키워드 없는 카드의 발동은 마법 종류대로
        kind = {'신속': 'quick', '트리거': 'trigger'}.get(d.get('subtype'), kind)
    num = kw.get('num') or int(spec.key.split('-')[0])
    installs = []
    if kw.get('cont'):
        installs += [ST.installer(b, num, notes, kw, d) for b in kw['cont']]
    if kw.get('card'):
        installs += [ST.installer(b, num, notes, kw, d) for b in kw['card']]
    if kind in ('cont', 'restrict') or kw.get('no_effect'):
        return Proto(None, installs)
    e = make_effect(spec, sent, d, kw, notes, kind, num)
    return Proto(e, installs)


def frame(d, kw, notes, kind, num, key):
    """효과 틀(F): 발동 위치 · 1턴 횟수 · 강제 · 카드 발동 여부 …"""
    typ, sub = d.get('type'), d.get('subtype')
    spell_act = kw.get('spell_act')
    if spell_act is None:
        spell_act = typ == '마법' and sub in SPELL_ACT_SUB and num == 1 and '-' not in key
    zones = kw.get('zones')
    if zones is None:
        if spell_act: zones = ('hand', 'field')
        elif kind == 'lastwill': zones = ('grave',)
        elif typ == '스킬': zones = ('skill',)
        else: zones = ('field',)
    if notes.get('hand_ok') and 'hand' not in zones: zones = tuple(zones) + ('hand',)
    opt = kw['opt'] if 'opt' in kw else notes.get('opt', 1)
    return dict(spell_act=spell_act, zones=tuple(zones), opt=opt, mandatory=kw.get('mandatory', notes.get('mandatory', False)))


def implicit_when(kind, notes, kw):
    """키워드가 정하는 발동 시점 — [소환] 이 카드가 소환되었을 때 · [유언] 묘지로 보내졌을 때 · [전투] 전투로 파괴했을 때"""
    if kw.get('when') is not None: return list(kw['when'])
    if kind == 'summon': return [D.when('summoned', self=True)]
    if kind == 'lastwill':
        return [D.when('to_grave', **{k: True for k in ('not_from_field', 'not_from_deck', 'not_cost') if notes.get(k)})]
    if kind == 'battle': return [D.when('battle_win')]
    return []


def make_effect(spec, sent, d, kw, notes, kind, num):
    import cards
    f = frame(d, kw, notes, kind, num, spec.key)
    whens = implicit_when(kind, notes, kw)
    if kind == 'trigger' and any(b.name == 'when_activated' for b in whens): kind = 'resp'
    costs = list(kw.get('cost', ()))
    if kind == 'resp':
        wa = next(b for b in whens if b.name == 'when_activated')
        costs.insert(0, D.B('keep_link', **wa.k))
    dos = scoped(costs, list(kw.get('do', ())))
    conds = list(kw.get('cond', ()))
    fns = codegen(spec, whens, conds, costs, dos, kind, f, notes, kw, follows_of(spec, d), num)
    e = Effect(num, kind, f['zones'], cond=fns['cond'], cost=fns['cost'] if costs or notes.get('cooldown') else None, res=fns['res'], score=fns['score'],
               opt=f['opt'], mandatory=f['mandatory'], threat=kw.get('threat', threat_of(dos + [b for b in costs if b.name != 'pick'])),
               label=kw.get('label', ''), spell_act=f['spell_act'])
    for a in ('no_resp', 'unnegatable', 'hand_ok', 'facedown_ok'):
        if notes.get(a) or kw.get(a): setattr(e, a, True)
    for a in ('owner_only', 'procedure', 'opt_per_card', 'summon_negate', 'exclusive'):
        if kw.get(a): setattr(e, a, kw[a])
    if kw.get('grant_of'): e.grant_of = kw['grant_of']
    if kw.get('pk_kind'): e.pk_kind = kw['pk_kind']; e.pk_hand = bool(notes.get('hand_ok'))   # 족보 효과(cards8.best_play · combo_text)
    if kw.get('pk_granted') is not None: e.pk_granted = kw['pk_granted']
    e.counter_keep = next(((b.k['name'], b.k['n']) for b in conds if b.name == 'cond_counters' and b.k['scope'].get('pred') == 'is_self'), None)   # lib.counter_keep
    e.counter_need = next(((w.k['name'], w.k['n']) for w in whens if w.name == 'when_counter'), None)   # lib.counter_effects
    e.kinds_costs = tuple(b.k for b in costs if b.name == 'kinds')   # 「각각 n장씩」 모으는 코스트(lib.v_kinds — 다른 효과가 쓰면 손해)
    pay = [b for b in costs if b.name not in ('pick', 'keep_link', 'oath')]
    if pay and all(b.k.get('transfer') or b.name == 'mill' for b in pay):
        # 델레가토르 1번: 상대가 대신 낼 수 있는 코스트만으로 된 효과 — 상대(q)가 낼 수 있는가(engine.Game.transfer_ok)
        def cost_payable(g, c, p, q, _bs=tuple(pay)):
            return all(L.BLOCKS[b.name].can(g, c, p, None, dict(b.k, cost=True)) for b in _bs)
        e.cost_payable = cost_payable
    line = sent if '-' in spec.key else f'{num}. {sent}'
    cards.text_attrs(e, line, d['name'] if '-' not in spec.key else kw.get('grant_name', d['name']))
    e.spec = spec
    return e


def follows_of(spec, d):
    """「n번 효과 처리 시에 … 경우, …한다 (별도의 발동 처리를 필요로 하지 않는다)」 — n번 처리에 딸린 효과들: [(번호, 1턴 횟수, 조건, 처리)]"""
    out = []
    sents = None
    for k2, s2 in D.TABLE.get(spec.code, {}).items():
        if s2.kw.get('follow') != spec.key: continue
        sents = sents or T.sentences(d)
        holes = T.match(s2.tmpl, sents.get(k2, ''))
        if holes is None: raise TemplateMismatch(f'{s2.code} {k2}: 문장 틀이 텍스트와 맞지 않는다\n  틀:   {T.norm(s2.tmpl)}\n  문장: {sents.get(k2)}')
        kw2 = _sub(dict(s2.kw), holes); n2 = T.notes(sents[k2])
        out.append((int(k2.split('-')[0]), kw2['opt'] if 'opt' in kw2 else n2.get('opt', 1), list(kw2.get('cond', ())), list(kw2.get('do', ()))))
    return out


def threat_of(dos):
    t = 100
    for b in _flat(dos):
        bd = L.BLOCKS.get(b.name)
        if bd is not None: t = max(t, bd.threat(b.k))
    return t


def _flat(steps):
    for b in steps:
        if b.name == 'branch':
            yield from _flat(b.k['then']); yield from _flat(b.k['other'])
        elif b.name == 'choice':
            for o in b.k['options']: yield from _flat(o)
        else:
            yield b


# ═══════════════════════ 코드 생성 ═══════════════════════
class _Gen:
    def __init__(self):
        self.ns = {'L': L}; self.n = 0

    def const(self, v):
        name = f'K{self.n}'; self.n += 1; self.ns[name] = v; return name

    def fn(self, f):
        name = f'F{self.n}'; self.n += 1; self.ns[name] = f; return name


def codegen(spec, whens, conds, costs, dos, kind, f, notes, kw, follows=(), num=1):
    G = _Gen()
    # cond: 시점 · 조건 · 단계 제한 · 재정 G2(코스트 · 처리 가능)
    tests = []
    for b in whens + conds:
        tests.append(f'{G.fn(L.TESTS[b.name])}(g, c, p, ev, {G.const(b.k)})')
    if notes.get('phase_only'):
        tests.append(f'g.phase == {notes["phase_only"]!r}')
    if notes.get('cooldown'):   # 「이 효과의 사용 후, 다음 턴까지 자신은 이 효과를 사용할 수 없다」(F05 — 발동하면 사용한 것)
        tests.append(f'L.cool_ok(g, c, p, {num})')
    made = False   # 앞 처리가 자신 필드에 카드를 낸다(특수소환 · 놓기) — 뒤 처리의 「자신 필드의 …」는 그 카드로 할 수 있다
    for b in [x for x in costs if not x.k.get('may')] + [x for x in dos if not x.k.get('may') and not x.k.get('soft')]:
        if b in dos and any(x.name == 'combo' for x in costs): continue   # 족보 코스트: 재료를 낸 뒤의 처리 가능 여부는 조합 탐색이 본다(cards8.plan — 비는 자리 · 같은 이름)
        if made and b in dos and (b.k.get('scope') or {}).get('side') == 'own' and (b.k.get('scope') or {}).get('zone') in ('field', 'mzone'): continue
        if b in dos and b.name in ('special', 'place'): made = True
        if b.name == 'choice':
            tests.append(f'{G.fn(L.TESTS["cond_any_option"])}(g, c, p, ev, {G.const(b.k)})'); continue
        if b.name in ('branch',) or b.name not in L.BLOCKS: continue
        bd = L.BLOCKS[b.name]
        if bd.can is L._always: continue
        k = dict(b.k, cost=True) if b in costs and b.name != 'pick' else b.k
        tests.append(f'{G.fn(bd.can)}(g, c, p, ev, {G.const(k)})')
        if b.name != 'pick' and 'ref' in b.k: continue
    src = ['def cond(g, c, p, ev):', '    return ' + (' and '.join(tests) if tests else 'True')]
    # cost
    src += ['def cost(g, c, p, l):']
    if notes.get('cooldown'): src.append(f'    L.cool_set(g, c, p, {num})')
    for b in costs:
        k = dict(b.k); k['cost'] = b.name != 'pick'
        call = f'{G.fn(L.BLOCKS[b.name].run)}(g, c, p, l, {G.const(k)})'
        if b.k.get('may'):   # 「…하고 발동할 수도 있다」 — 낼지는 AI(코스트 가치 + 더 얻는 처리), 내지 않아도 발동
            src.append(f'    if L.wants_cost(g, c, p, l, {G.const(dict(k, blk=b.name))}): {call}')
        else:
            src.append(f'    if not {call}: return False')
    src.append('    return True')
    # res — 딸린 효과(follows)는 조건을 처리 시작 때 보고(「n번 효과 처리 시에 … 경우」), 본 처리 뒤에 처리한다(1턴 횟수는 그 번호로)
    if follows:
        src += ['def _main(g, c, p, l):'] + (_steps(G, dos, 1) or ['    pass'])
        src += ['def res(g, c, p, l):', '    if L.swapped(g, c, p, l): return']
        for i, (n2, opt2, c2, d2) in enumerate(follows):
            ok = [f'L.follow_ok(g, c, p, {n2}, {opt2!r})'] + [f'{G.fn(L.TESTS[b.name])}(g, c, p, l, {G.const(b.k)})' for b in c2]
            src.append(f'    _f{i} = ' + ' and '.join(ok))
        src.append('    _main(g, c, p, l)')
        for i, (n2, opt2, c2, d2) in enumerate(follows):
            src.append(f'    if _f{i}:')
            src.append(f'        L.follow_use(g, c, p, {n2}); g.L(f"  {n2}번 처리 (1번 처리 시 조건 충족 — 별도 발동 없음)")')
            src += _steps(G, d2, 2) or ['        pass']
    else:
        src += ['def res(g, c, p, l):', '    if L.swapped(g, c, p, l): return'] + (_steps(G, dos, 1) or ['    pass'])
    # score (B안)
    vals = [_val_expr(G, dos)]
    for n2, opt2, c2, d2 in follows:   # 딸린 효과: 지금 조건이 맞고 이 턴 아직 쓰지 않았으면 그 가치도
        ok = ' and '.join([f'L.follow_ok(g, c, p, {n2}, {opt2!r})'] + [f'{G.fn(L.TESTS[b.name])}(g, c, p, ev, {G.const(b.k)})' for b in c2])
        vals.append(f'(({_val_expr(G, d2)}) if ({ok}) else 0.0)')
    cvals = [(f'max(0.0, {G.fn(L.BLOCKS[b.name].val)}(g, c, p, ev, {G.const(b.k)}) + {_val_expr(G, list(b.k.get("gain", ())))})' if b.k.get('may') else
              f'{G.fn(L.BLOCKS[b.name].val)}(g, c, p, ev, {G.const(b.k)})') for b in costs if b.name not in ('pick', 'keep_link')]
    info = dict(num=num, phase_only=bool(notes.get('phase_only')), kind=kind, disrupt=any(b.name in DISRUPT and (b.k.get('ref') not in (None, 'SELF') or b.k.get('scope', {}).get('side') == 'opp')
                                         for b in list(_flat(dos)) + costs), spell_act=f['spell_act'], mandatory=f['mandatory'],
                aware=any(b.name in AWARE for b in _flat(dos)))
    v = ' + '.join(vals) or '0.0'
    cv = (' + ' + ' + '.join(cvals)) if cvals else ''   # 코스트 블록의 가치는 「그 코스트로 바뀌는 형세」 — 자신 자원이면 음수, 상대 카드를 쓰면 양수
    src += ['def score(g, c, p, ev):', f'    return L.timing(g, c, p, ev, {G.const(info)}, {v}{cv})']
    code = '\n'.join(src)
    exec(compile(code, f'<blocks {spec.code} {spec.key}>', 'exec'), G.ns)
    return {k: G.ns[k] for k in ('cond', 'cost', 'res', 'score')}


def _val_expr(G, steps):
    """처리 블록 가치의 합 — 분기(J2)는 확률(prob)이 있으면 기댓값, 없으면 큰 쪽 · 선택지는 가장 큰 것.
    「이 카드를 X로 옮긴다. 이 효과로 X에 …이 n장 모였을 경우, 승리한다」는 이 카드를 센 수로 판정하고, 모이기 전에는 모은 비율만큼(lib.WIN_PROGRESS)"""
    parts = []; moved = set()
    for b in steps:
        if b.name == 'move' and b.k.get('ref') == 'SELF': moved.add(b.k['dest'])
        if b.name == 'branch':
            a, o = _val_expr(G, b.k['then']), _val_expr(G, b.k['other'])
            pr = b.k.get('prob'); cb = b.k['cond']
            if cb.name == 'cnt' and cb.k['scope'].get('zone') in moved:
                ck = dict(cb.k, plus=1)
                if any(x.name == 'win' for x in b.k['then']):
                    parts.append(f'(({a}) if L.TESTS["cnt"](g, c, p, ev, {G.const(ck)}) else L.WIN_PROGRESS * (len(L.cards_in(g, c, p, {G.const(ck["scope"])})) + 1) / {ck["n"]})')
                    continue
                cb = D.Blk(cb.name, ck)
            if pr is not None: parts.append(f'({pr} * ({a}) + {1 - pr} * ({o}))')
            elif cb.name == 'cond_ref_in': parts.append(f'max({a}, {o})')   # 처리 때 정해지는 값(주사위 등)
            else: parts.append(f'(({a}) if {G.fn(L.TESTS[cb.name])}(g, c, p, ev, {G.const(cb.k)}) else ({o}))')
        elif b.name == 'choice':
            parts.append('max(' + ', '.join(_val_expr(G, o) for o in b.k['options']) + ')')
        elif b.name in L.BLOCKS:
            e = f'{G.fn(L.BLOCKS[b.name].val)}(g, c, p, ev, {G.const(b.k)})'
            parts.append(f'max(0.0, {e})' if b.k.get('may') else e)
    return ' + '.join(parts) or '0.0'


def scoped(costs, steps):
    """발동 시 고른 대상을 쓰는 처리 블록에 그 대상의 조건(ref_scope)을 달아, 처리 때 대상이 조건을 벗어났으면 처리하지 않게 한다"""
    sc = {b.k['ref']: b.k['scope'] for b in costs if b.name == 'pick'}
    def fix(b):
        if b.name == 'branch': return D.Blk(b.name, dict(b.k, then=tuple(map(fix, b.k['then'])), other=tuple(map(fix, b.k['other']))))
        if b.name == 'choice': return D.Blk(b.name, dict(b.k, options=tuple(tuple(map(fix, o)) for o in b.k['options'])))
        r = b.k.get('ref')
        if r in sc and 'ref_scope' not in b.k: return D.Blk(b.name, dict(b.k, ref_scope=sc[r]))
        return b
    return [fix(b) for b in steps]


def _steps(G, steps, depth):
    pad = '    ' * depth; out = []
    for b in steps:
        if b.name == 'choice':
            v = f'_o{depth}'
            out.append(f'{pad}{v} = L.best_option(g, c, p, l, {G.const(b.k)})')
            for i, o in enumerate(b.k['options']):
                out.append(f'{pad}{"if" if i == 0 else "elif"} {v} == {i}:')
                out += _steps(G, o, depth + 1) or [pad + '    pass']
            out.append(f'{pad}else: return')
            continue
        if b.name == 'branch':
            out.append(f'{pad}if {G.fn(L.TESTS[b.k["cond"].name])}(g, c, p, l, {G.const(b.k["cond"].k)}):')
            out += _steps(G, b.k['then'], depth + 1) or [pad + '    pass']
            if b.k['other']:
                out.append(f'{pad}else:')
                out += _steps(G, b.k['other'], depth + 1)
            continue
        call = f'{G.fn(L.BLOCKS[b.name].run)}(g, c, p, l, {G.const(b.k)})'
        if b.k.get('soft'):   # 고를 것이 없으면 건너뛰고 다음 처리로(숨은 정보를 확인한 뒤 고르기 · 정리 처리)
            out.append(f'{pad}{call}')
        elif b.k.get('may'):
            out.append(f'{pad}if L.wants(g, c, p, l, {G.const(b)}): {call}')
        else:
            out.append(f'{pad}if not {call}: return')
    return out


# ═══════════════════════ A22 효과 부여 ═══════════════════════
_GRANTS = {}


def granted_effect(code, key, n, num):
    """조립표 (code, key)의 부여 효과를 효과 번호 num으로 — 받는 카드가 그 부여를 n번째 이상 받아 두었을 때만 발동(필드를 벗어나면 부여가 사라짐)"""
    ck = (code, key, n, num)
    e = _GRANTS.get(ck)
    if e is None:
        import copy
        from cards import POOL
        d = next(x for x in POOL.values() if x.get('code') == code)
        spec = D.TABLE[code][key]
        base = compile_spec(spec, T.sentences(d)[key], d).effect
        e = copy.copy(base); e.num = num
        flag = f'grant:{code}:{key}'
        def cond(g, c, p, ev, _b=base.cond, _f=flag, _n=n): return c.flags.get(_f, 0) >= _n and _b(g, c, p, ev)
        e.cond = cond; e.opt_per_card = True     # 부여받은 효과 — 부여마다 별개의 1턴 1번 (재정 G3)
        _GRANTS[ck] = e
    return e


def do_grant(g, c, p, l, k):
    """A22 효과 부여 — ref의 카드가 조립표 (이 카드 코드, k['key'])의 효과를 얻는다. stack: 다시 받으면 효과가 하나 더(번호 base + n).
    필드를 벗어나면 부여가 사라진다(flags['clear_on_leave'])"""
    xs = L.subjects(g, c, p, l, k)
    done = False
    for m in xs:
        if not g.on_field(m) or g.blocked(m, ('effect', c)): continue
        flag = f'grant:{c.d["code"]}:{k["key"]}'
        n = m.flags.get(flag, 0) + 1
        col = dict(m.flags.get('clear_on_leave') or {}); col.setdefault(flag, None); m.flags['clear_on_leave'] = col
        m.flags[flag] = n
        num = k.get('base', 20) + (n if k.get('stack') else 1)
        if not any(e.num == num for e in m.effects):
            m.effects = list(m.effects) + [granted_effect(c.d['code'], k['key'], n if k.get('stack') else 1, num)]
        g.L(f'{m}: {c.name}의 효과를 얻음' + (f' ({n}중첩)' if k.get('stack') else ''))
        done = True
    return done


L.block('grant', can=L.can_subjects, val=lambda g, c, p, ev, k: 2.0 * L.UNIT, threat=600)(do_grant)


# ═══════════════════════ 체인 밖 처리 (지연 효과 · [지속] 처리 · 장착 해제) ═══════════════════════
_STEPS = {}


def steps_fn(steps):
    """처리 블록 목록 → 함수 f(g, c, p, l) (코드 생성 · 블록 목록마다 한 번)"""
    key = id(steps)
    hit = _STEPS.get(key)
    if hit is not None and hit[0] is steps: return hit[1]
    G = _Gen()
    src = ['def run(g, c, p, l):'] + (_steps(G, list(steps), 1) or ['    pass'])
    exec(compile('\n'.join(src), '<blocks steps>', 'exec'), G.ns)
    _STEPS[key] = (steps, G.ns['run'])
    return G.ns['run']


def ns_value_of(c):
    """제물 일반소환의 가치(ai.extra_summon_options 훅): [소환] 효과 가치(B안)와 공격력 기준 중 큰 쪽 — 결착이면 최우선"""
    from cards import VETO
    def nv(g, p, ts, cost, c=c):
        v = sum(max(0.0, e.score(g, c, p, {'kind': 'summon', 'card': c, 'player': p, 'how': 'normal'})) for e in c.effects if e.kind == 'summon')
        if v >= L.LETHAL / 2: return 500
        by_eff = 20 + 15 * v / L.UNIT - 12 * cost if v > 0 else VETO
        gain = g.atk(c) - sum(g.atk(t) for t in ts if t.is_monster())
        by_atk = 20 + g.atk(c) / 100 - 12 * cost if gain > 0 else VETO
        return max(by_eff, by_atk)
    return nv


_CG = {}


def cont_granted_effect(code, key, num):
    """[지속] 효과 부여: 조립표 (code, key)의 효과를 번호 num으로 — 받는 카드가 자신 필드의 앞면 몬스터이고, 부여하는 카드(code)가 그 플레이어의
    스킬 존 · 필드에서 적용 중이고, 받는 카드가 그 효과를 받을 때만 발동(무효면 쓸 수 없음 — 엔진 zone_ok). 부여받은 효과는 카드마다 1턴 1번(재정 G3)"""
    ck = (code, key, num)
    e = _CG.get(ck)
    if e is None:
        import copy
        from cards import POOL
        d = next(x for x in POOL.values() if x.get('code') == code)
        spec = D.TABLE[code][key]
        base = compile_spec(spec, T.sentences(d)[key], d).effect
        e = copy.copy(base); e.num = num; e.opt_per_card = True
        def src_of(g, p, _code=code):
            for x in ([g.p[p].skill] if g.p[p].skill else []) + g.field_cards(p):
                if x.d.get('code') == _code and g.cont_active(x): return x
            return None
        def cond(g, c, p, ev, _b=base.cond):
            s = src_of(g, p)
            return (s is not None and c.is_monster() and g.on_field(c) and c.controller == p and c.faceup and g.receives(c, s) and _b(g, c, p, ev))
        e.cond = cond
        for a in ('pk_kind',):
            if spec.kw.get(a): setattr(e, a, spec.kw[a])
        if spec.kw.get('pk_granted') is not None: e.pk_granted = spec.kw['pk_granted']
        _CG[ck] = e
    return e
