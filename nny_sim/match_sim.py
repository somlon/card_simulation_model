"""매치 시뮬레이션 · 라운드 통계 기록기 (덱 밸런스 판단용).

원칙(사용자 지시 2026-10-01 — workflow.md 「목표 기준」)
  · 시뮬레이션은 매치(Bo3)로만 한다. 참여하는 모든 덱의 모든 순서쌍(미러전 포함)을 같은 수만큼 돌린다.
  · 양쪽 자리는 같은 AI · 같은 설정(사용자 수준이 같다는 전제). 학습표는 갱신하지 않는다.
  · 덱마다 1 · 2 · 3라운드 승률을 선공 · 후공으로 나눠 기록하고, 종합 승률(모든 덱 상대 · 선후공 무관 · 미러전 포함)이
    이상 범위 49~51%에 드는지 표시한다. 미러전은 양쪽 자리를 모두 그 덱의 판으로 센다.
  · 라운드마다 승리 · 패배 요인을 rounds.jsonl에 한 줄씩 저장한다 — 나중에 따로 통계 분석할 수 있게 원자료를 남긴다.

실행 (nny_sim 폴더)
  python match_sim.py run --matches 50 --out sim_results/run1 [--ai table|heuristic|drl:<모델.npz>] [--policy P --side S]
  python match_sim.py summarize sim_results/run1/rounds.jsonl.gz       # 저장된 원자료로 요약 다시 계산
결과 (--out 폴더)
  rounds.jsonl.gz  라운드 1개 = 1줄(gzip 압축 JSON Lines, round_record 참고). 안전장치로 중단된 매치도
                   {"type": "stalled_match", ...} 줄로 남긴다 — 원자료만으로 요약을 그대로 다시 만들 수 있다
  meta.json      실행 설정(AI · 시드 · 순서쌍당 매치 수 · 완료 여부)
  summary.json   덱별 · 라운드별 · 선후공별 집계, 상성표, 요인 분포 (+ 실행 설정)
  summary.md     사람이 읽는 요약
"""
import os
for _k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_k, '1')
import argparse, collections, concurrent.futures as cf, itertools, json, math, multiprocessing as mp, random, re, sys, time

IDEAL = (49.0, 51.0)            # 덱 종합 승률 이상 범위(%) — workflow.md 「목표 기준」
SCHEMA = 1                      # rounds.jsonl 형식 판 — 필드를 바꾸면 올린다
_RE_DMG = re.compile(r'^(.+?) (\d+) 대미지 \((.*)\) → HP (-?\d+)$')
_RE_USE = re.compile(r'^(.+?) 「(.+?)」 (\d번 효과 발동|일반소환|특수소환)')
_RE_MULL = re.compile(r'^(.+?) 멀리건 (\d+)장')


# ─────────────── 요인 추출 ───────────────
def damage_kind(src):
    """대미지 출처 문자열 → 종류"""
    if src.endswith('직접공격'):
        return '직접공격'
    if src.startswith('전투'):
        return '전투'
    if src == '공유 존 마커':
        return '공유 존 마커'
    if src.startswith('자해'):
        return '자해'
    return '효과'


def _player_block(g, i, name, log_slice):
    pl = g.p[i]
    dealt = collections.Counter(); taken = collections.Counter(); used = collections.Counter(); mull = 0
    for e in log_slice:
        m = e.get('m', '')
        d = _RE_DMG.match(m)
        if d:
            kind = damage_kind(d.group(3)); amt = int(d.group(2))
            if d.group(1) == name:
                taken[kind] += amt
            elif kind not in ('자해', '공유 존 마커'):   # 상대의 자해 · 마커 페널티는 이 플레이어가 준 대미지가 아니다
                dealt[kind] += amt
            continue
        u = _RE_USE.match(m)
        if u and u.group(1) == name:
            used[u.group(2)] += 1; continue
        mm = _RE_MULL.match(m)
        if mm and mm.group(1) == name:
            mull = int(mm.group(2))
    return {
        'hp': pl.hp, 'hand': len(pl.hand), 'monsters': len(g.monsters(i)), 'spells': len(g.spells(i)),
        'deck_main': len(pl.main), 'deck_upper': len(pl.upper), 'grave': len(pl.grave), 'banish': len(pl.banish),
        'damage_dealt': dict(dealt), 'damage_taken': dict(taken), 'cards_used': dict(used),
        'activations': sum(v for k, v in used.items()), 'mulligan': mull,
        'opening_hand': list(getattr(g, 'opening', [[], []])[i]),
    }


def _hp_trend(g, w):
    """턴 시작 스냅샷 기준 승자 시점 HP 차(승자 − 패자)의 최솟값 · 최댓값 · 주도권 변화 수"""
    diffs = [s['hp'][w] - s['hp'][1 - w] for s in getattr(g, 'snaps', [])]
    if not diffs:
        return 0, 0, 0
    lead = [1 if d > 0 else -1 if d < 0 else 0 for d in diffs]
    nz = [x for x in lead if x]
    changes = sum(1 for a, b in zip(nz, nz[1:]) if a != b)
    return min(diffs), max(diffs), changes


def factor_tags(rec):
    """라운드 기록 → 승리 · 패배 요인 태그(집계용). 원자료는 rec에 그대로 남는다"""
    w = rec['winner_seat']; l = 1 - w; tags = []
    reason = rec['reason']
    tags.append('HP 0' if 'HP 0' in reason else '덱아웃' if '덱아웃' in reason else '기타 종료')
    if rec.get('final_blow'):
        tags.append('결정타:' + rec['final_blow']['kind'])
    tags.append('선공 승리' if rec['first_seat'] == w else '후공 승리')
    if rec['winner_min_hp_lead'] <= -1000:
        tags.append('역전승(HP 1000 이상 열세 극복)')
    if rec['winner_min_hp_lead'] >= 0:
        tags.append('한 번도 HP 열세 없음')
    t = rec['turns']
    tags.append('단기전(4턴 이하)' if t <= 4 else '장기전(10턴 이상)' if t >= 10 else '중간 길이(5~9턴)')
    pw, pl_ = rec['players'][w], rec['players'][l]
    if pw['hand'] + pw['monsters'] + pw['spells'] > pl_['hand'] + pl_['monsters'] + pl_['spells']:
        tags.append('종료 시 카드 우위(패+필드)')
    if pl_['mulligan'] > pw['mulligan']:
        tags.append('패자가 멀리건 더 많음')
    return tags


def round_record(g, rnd, rinfo, decks, names, log, match_meta, swaps_before):
    """라운드 하나의 원자료 + 요인 태그"""
    i0, i1 = rinfo['log']; sl = log[i0:i1]
    w = rinfo['winner']; first = rinfo['first']
    players = [_player_block(g, i, names[i], sl) for i in (0, 1)]
    for i in (0, 1):
        players[i].update(seat=i, skill=decks[i]['스킬'], deck=match_meta['decks'][i], first=(first == i))
    blow = None
    for e in reversed(sl):
        d = _RE_DMG.match(e.get('m', ''))
        if d:
            blow = {'kind': damage_kind(d.group(3)), 'source': d.group(3), 'amount': int(d.group(2)), 'turn': e.get('t')}
            break
    rec = {
        'type': 'round', 'schema': SCHEMA, 'match_id': match_meta['match_id'], 'seed': match_meta['seed'], 'round': rnd,
        'ai': match_meta['ai'], 'decks': match_meta['decks'], 'mirror': match_meta['decks'][0] == match_meta['decks'][1],
        'first_seat': first, 'winner_seat': w, 'reason': rinfo['reason'], 'turns': rinfo['turns'],
        'end_turn_player': g.turn_player, 'final_blow': blow if 'HP 0' in rinfo['reason'] else None,
        'side_swaps_before': swaps_before, 'players': players,
    }
    rec['winner_min_hp_lead'], rec['winner_max_hp_lead'], rec['lead_changes'] = _hp_trend(g, w) if w is not None else (0, 0, 0)
    rec['tags'] = factor_tags(rec) if w is not None else ['무승부']
    return rec


def _swaps_between(log, start, end, names):
    """두 라운드 사이 로그의 전략 덱 교체 → 자리별 [(뺀 카드, 넣은 카드, 이유)]"""
    out = [[], []]
    for e in log[start:end]:
        if e.get('k') == 'side':
            who = e.get('data', {}).get('player')
            if who in names:
                out[names.index(who)] = [list(x) for x in e['data'].get('swaps', [])]
    return out


# ─────────────── AI ───────────────
def _ai_factory(spec):
    """(make_ai(deck), side_fn 또는 None). 양쪽 자리에 같은 AI · 같은 설정"""
    import policy as P
    import match as M
    from ai import HeuristicAI
    kind = spec['ai']
    if kind == 'heuristic':
        class _Fixed(HeuristicAI):
            def end_game(self, g, p, winner):   # 번식지 학습표(BREEDING)를 갱신하지 않는다 — 시뮬레이션 중 학습 금지
                self.decisions = []
        return (lambda d: _Fixed(d['스킬'])), None
    if kind == 'table':
        if spec.get('policy'):
            P.POLICY = _load_table(spec['policy'])
        if spec.get('side'):
            M.SIDE = _load_table(spec['side'])
        return (lambda d: P.LearnedAI(d['스킬'], learn=False)), None
    if kind.startswith('drl:'):
        try:
            from drl.play import players
        except ImportError:
            sys.exit('DRL AI에는 drl 패키지(PR #9)가 필요함')
        make_ai, side_fn = players(kind[4:], kind[4:])
        return make_ai, side_fn
    raise ValueError(kind)


def _load_table(path):
    import gzip
    import policy as P
    t = P.Table.__new__(P.Table)
    with (gzip.open(path, 'rt', encoding='utf-8') if path.endswith('.gz') else open(path, encoding='utf-8')) as f:
        d = json.load(f)
    t.path = path; t.L1 = d.get('L1', {}); t.L2 = d.get('L2', {}); t.games = d.get('games', 0)
    return t


# ─────────────── 매치 실행 ───────────────
_W = {}


def _init(spec):
    import season as SE
    _W['decks'] = SE.load_decks(); _W['spec'] = spec
    _W['make_ai'], _W['side_fn'] = _ai_factory(spec)


def play_one(a, b, first, seed, match_id):
    """매치 1회 → 라운드 기록 목록 (안전장치 중단이면 None)"""
    import match as M
    from engine import StalledGame
    decks = _W['decks']; base_make = _W['make_ai']
    # 로그의 플레이어 이름을 자리별로 구분(미러전에서도 사용 카드 · 대미지를 자리별로 셀 수 있게)
    dA = dict(decks[a], 이름=f"{decks[a]['이름']} [자리0]"); dB = dict(decks[b], 이름=f"{decks[b]['이름']} [자리1]")
    names = [dA['이름'], dB['이름']]
    games = []

    def make_ai(deck):
        ai = base_make(deck)
        orig = ai.end_game

        def end_game(g, p, winner, _o=orig):
            if p == 0:
                games.append(g)         # 라운드가 끝난 게임 상태(자리 0의 호출에서 한 번만)
            return _o(g, p, winner)
        ai.end_game = end_game
        return ai

    log = []
    kw = dict(side=True, side_eps=0.0, learn_side=False)
    if _W['side_fn'] is not None:
        kw['side_fn'] = _W['side_fn']
    base = {'schema': SCHEMA, 'match_id': match_id, 'seed': seed, 'ai': _W['spec']['ai'], 'decks': [a, b], 'first_seat': first}
    try:
        mw, rounds = M.play_match(dA, dB, first, random.Random(seed), log, make_ai, **kw)
    except StalledGame:
        return [dict(base, type='stalled_match', rounds_done=len(games))]
    except Exception:   # 카드 구현 오류 등 — 이 매치만 오류로 기록하고 실행은 계속한다(같은 시드로 재현 가능)
        import traceback
        return [dict(base, type='error_match', rounds_done=len(games), error=traceback.format_exc()[-2000:])]
    meta = {'match_id': match_id, 'seed': seed, 'ai': _W['spec']['ai'], 'decks': [a, b]}
    out = []
    for r, (rinfo, g) in enumerate(zip(rounds, games), 1):
        swaps = _swaps_between(log, rounds[r - 2]['log'][1], rinfo['log'][0], names) if r > 1 else [[], []]
        decks_now = [dict(dA, 스킬=g.p[0].skill.name), dict(dB, 스킬=g.p[1].skill.name)]   # 스킬 교체 반영
        rec = round_record(g, r, rinfo, decks_now, names, log, meta, swaps)
        rec['match_winner_seat'] = mw; rec['match_rounds'] = len(rounds)
        out.append(rec)
    return out


def _job(batch):
    out = []
    for a, b, first, seed, mid in batch:
        out += play_one(a, b, first, seed, mid)
    return out


def schedule(names, n, seed):
    """모든 순서쌍(미러전 포함) × n매치. 1라운드 선공은 매치마다 번갈아 정한다"""
    rng = random.Random(seed); out = []; mid = 0
    for a, b in itertools.product(names, repeat=2):
        for k in range(n):
            out.append((a, b, k % 2, rng.randrange(2 ** 31), mid)); mid += 1
    return out


# ─────────────── 집계 ───────────────
def _rate(w, n):
    p = w / n if n else 0.0
    return {'win': w, 'games': n, 'rate': round(100 * p, 2), 'ci95': round(196 * math.sqrt(p * (1 - p) / n), 2) if n else None}


def summarize(records):
    """원자료(라운드 · 중단 매치 기록) → 덱별 집계. 덱 시점: 그 덱이 앉은 자리마다 한 번씩 센다(미러전은 양쪽 모두).
    안전장치로 중단된 매치는 승패가 없으므로 승률에서 빼고 따로 센다"""
    rounds = [r for r in records if r.get('type', 'round') == 'round']
    stalled_recs = [r for r in records if r.get('type') == 'stalled_match']
    stalled = len(stalled_recs); errors = [r for r in records if r.get('type') == 'error_match']
    per = collections.defaultdict(lambda: {'match': [0, 0], 'round_all': [0, 0], 'round': collections.defaultdict(lambda: [0, 0]),
                                           'win_tags': collections.Counter(), 'loss_tags': collections.Counter()})
    vs = collections.defaultdict(lambda: [0, 0]); matches = {}
    for r in rounds:
        matches.setdefault(r['match_id'], r)
        for s in (0, 1):
            d = r['decks'][s]; won = r['winner_seat'] == s; st = per[d]
            pos = '선공' if r['first_seat'] == s else '후공'
            st['round_all'][0] += won; st['round_all'][1] += 1
            e = st['round'][(r['round'], pos)]; e[0] += won; e[1] += 1
            (st['win_tags'] if won else st['loss_tags']).update(r['tags'])
    for r in matches.values():
        for s in (0, 1):
            d = r['decks'][s]; won = r['match_winner_seat'] == s
            per[d]['match'][0] += won; per[d]['match'][1] += 1
            v = vs[(d, r['decks'][1 - s])]; v[0] += won; v[1] += 1
    st_by = collections.Counter(d for r in stalled_recs for d in r['decks'])
    out = {'ideal_range': list(IDEAL), 'matches': len(matches), 'rounds': len(rounds), 'stalled_matches': stalled,
           'error_matches': len(errors), 'error_samples': [e['error'][-500:] for e in errors[:3]], 'decks': {}}
    for d, st in sorted(per.items()):
        m = _rate(*st['match'])
        out['decks'][d] = {
            'match': m, 'in_ideal_range': IDEAL[0] <= m['rate'] <= IDEAL[1],
            'round_overall': _rate(*st['round_all']),
            'rounds': {f'{rn}R {pos}': _rate(*st['round'][(rn, pos)]) for rn in (1, 2, 3) for pos in ('선공', '후공')},
            'win_factors': dict(st['win_tags'].most_common()), 'loss_factors': dict(st['loss_tags'].most_common()),
            'stalled_match_seats': st_by.get(d, 0),
        }
    out['vs'] = {f'{a} vs {b}': _rate(*v) for (a, b), v in sorted(vs.items())}
    return out


def to_markdown(s):
    lo, hi = s['ideal_range']
    L = [f"# 매치 시뮬레이션 요약", '', f"- 매치 {s['matches']} · 라운드 {s['rounds']} · 안전장치 중단 매치 {s['stalled_matches']} · 오류 매치 {s.get('error_matches', 0)}",
         f"- 이상 범위: 덱 종합 매치 승률 {lo:g}~{hi:g}% (모든 덱 상대 · 미러전 포함 · 선후공 무관)", '',
         '## 덱별 종합 승률', '', '| 덱 | 매치 승률 | 95% CI | 판정 | 라운드 승률 |', '|---|---|---|---|---|']
    for d, v in s['decks'].items():
        m = v['match']; ok = '이상 범위' if v['in_ideal_range'] else ('높음' if m['rate'] > hi else '낮음')
        L.append(f"| {d} | {m['rate']}% ({m['win']}/{m['games']}) | ±{m['ci95']} | {ok} | {v['round_overall']['rate']}% |")
    L += ['', '## 라운드 · 선후공별 승률', '', '| 덱 | 1R 선공 | 1R 후공 | 2R 선공 | 2R 후공 | 3R 선공 | 3R 후공 |', '|---|---|---|---|---|---|---|']
    for d, v in s['decks'].items():
        cells = [f"{x['rate']}% ({x['games']})" if x['games'] else '—' for x in v['rounds'].values()]
        L.append(f"| {d} | " + ' | '.join(cells) + ' |')
    L += ['', '## 승리 · 패배 요인 (상위 5개, 라운드 수)', '']
    for d, v in s['decks'].items():
        top = lambda c: ', '.join(f'{k} {n}' for k, n in list(c.items())[:5])
        L.append(f"- **{d}** — 승리: {top(v['win_factors'])} / 패배: {top(v['loss_factors'])}")
    return '\n'.join(L) + '\n'


# ─────────────── 명령행 ───────────────
def cmd_run(a):
    import season as SE
    names = sorted(SE.load_decks())
    spec = {'ai': a.ai, 'policy': a.policy, 'side': a.side}
    sched = schedule(names, a.matches, a.seed)
    batches = [sched[i::a.workers * 4] for i in range(a.workers * 4)]
    os.makedirs(a.out, exist_ok=True); t0 = time.time(); records = []
    meta = {'ai': spec, 'matches_per_pair': a.matches, 'seed': a.seed, 'workers': a.workers, 'decks_list': names,
            'planned_matches': len(sched), 'started': time.strftime('%Y-%m-%d %H:%M:%S')}
    complete = False
    try:
        with cf.ProcessPoolExecutor(a.workers, mp_context=mp.get_context('spawn'), initializer=_init, initargs=(spec,)) as ex:
            for res in ex.map(_job, batches):
                records += res
        complete = True
    finally:   # 작업자가 비정상 종료돼도 그때까지 끝난 결과는 남긴다
        records.sort(key=lambda r: (r['match_id'], r.get('round', 0)))
        write_records(os.path.join(a.out, 'rounds.jsonl.gz'), records)
        meta.update(complete=complete, sec=round(time.time() - t0, 1))
        with open(os.path.join(a.out, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
    s = summarize(records); s['run'] = meta
    _write_summary(a.out, s)
    print(to_markdown(s))


def write_records(path, records):
    """원자료를 gzip JSON Lines로 원자적 저장"""
    import gzip
    tmp = path + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, path)


def read_records(path):
    import gzip
    with (gzip.open(path, 'rt', encoding='utf-8') if path.endswith('.gz') else open(path, encoding='utf-8')) as f:
        return [json.loads(l) for l in f if l.strip()]


def _write_summary(out, s):
    with open(os.path.join(out, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write(to_markdown(s))


def cmd_summarize(a):
    s = summarize(read_records(a.rounds))
    mp_ = os.path.join(os.path.dirname(os.path.abspath(a.rounds)), 'meta.json')
    if os.path.exists(mp_):   # 실행 설정(AI · 시드 · 매치 수 등)을 그대로 붙인다
        with open(mp_, encoding='utf-8') as f:
            s['run'] = json.load(f)
    _write_summary(os.path.dirname(os.path.abspath(a.rounds)), s)
    print(to_markdown(s))


def main(argv=None):
    ap = argparse.ArgumentParser(description='매치 시뮬레이션 · 라운드 통계')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--matches', type=int, default=20, help='덱 순서쌍(미러전 포함)마다 매치 수')
    r.add_argument('--out', required=True); r.add_argument('--ai', default='table', help='table | heuristic | drl:<모델.npz>')
    r.add_argument('--policy', help='table AI의 판단 학습표(기본: learned/policy.json)'); r.add_argument('--side', help='table AI의 교체표(기본: learned/side.json)')
    r.add_argument('--workers', type=int, default=4); r.add_argument('--seed', type=int, default=1)
    s = sub.add_parser('summarize'); s.add_argument('rounds')
    a = ap.parse_args(argv)
    {'run': cmd_run, 'summarize': cmd_summarize}[a.cmd](a)


if __name__ == '__main__':
    main()
