"""보고서 대표 게임 로그 — 덱마다 2개 (보고서 작성 지침 2장 4항, 사용자 지시 2026-10-13).

① 가장 많이 반복되는 구도: 리그 원자료(rounds.jsonl.gz)에서 그 덱 시점의 라운드를
   (승패 · 선후공 · 결착 방식 · 결착 턴)으로 묶어 최빈 조합을 고르고, 그 조합의 첫 라운드(매치 번호순)를
   같은 시드 · 같은 표로 다시 돌려 전체 로그를 얻는다. 다시 돌린 결과(승자 · 턴 수)가 원자료와 같은지 확인한다.
② 학습이 수렴한 마지막 시뮬레이션 로그: train_table.py가 반복마다 덮어쓰는 <출력 폴더>/last_logs.json.gz.

사용 (nny_sim 폴더에서):
  python3 <이 파일> --run <리그 폴더> --last learned/train_v2/last_logs.json.gz --out <대표_로그.md> [--json <요약.json>]
리그 폴더의 meta.json 에 적힌 AI · 학습표 · 교체표를 그대로 쓴다.
"""
import argparse, collections, gzip, json, os, random, re, sys

NAME_TAIL = re.compile(r' \(시제품용[^)]*\)')
RE_DEC = re.compile(r'^판단\[(.+?)\] (.+?): \{(.*)\} → (.+?) \(([^()]*)\)$')
RE_OPT = re.compile(r'(.+?)=([\d.]+)%\(n[^)]*\)(?:, |$)')
SKIP_DEC = ('멀리건', '서치', '대상', '버릴 카드', '드로우 덱', '인카운터 분기', '시작 패')


def clean(m):
    return NAME_TAIL.sub('', m)


def blow_kind(rec):
    if rec.get('final_blow'): return rec['final_blow']['kind']
    return rec.get('reason') or '무승부'


def pattern(rec, s):
    w = rec['winner_seat']
    res = '승' if w == s else '무' if w is None else '패'
    pos = '선공' if rec['first_seat'] == s else '후공'
    return (res, pos, blow_kind(rec), rec['turns'])


def load_rounds(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return [r for r in map(json.loads, f) if r.get('type', 'round') == 'round']


def most_frequent(rounds, names):
    """덱 → (최빈 조합, 횟수, 그 덱의 라운드 수, 대표 (기록, 자리), 상위 5개 조합)"""
    cnt = collections.defaultdict(collections.Counter); rep = {}; tot = collections.Counter()
    for r in sorted(rounds, key=lambda r: (r['match_id'], r['round'])):
        for s in (0, 1):
            d = r['decks'][s]; k = pattern(r, s)
            cnt[d][k] += 1; tot[d] += 1
            rep.setdefault((d, k), (r, s))
    out = {}
    for d in names:
        (k, n), = cnt[d].most_common(1)
        out[d] = {'pattern': k, 'count': n, 'rounds': tot[d], 'rep': rep[(d, k)], 'top5': cnt[d].most_common(5)}
    return out


def replay(a, b, first, seed, rnd):
    """match_sim.play_one과 같은 조건으로 매치를 다시 돌려 rnd 라운드의 로그(앞 라운드 뒤 교체 포함)를 돌려준다"""
    import match as M, match_sim as MS
    decks = MS._W['decks']
    dA = dict(decks[a], 이름=f"{decks[a]['이름']} [자리0]"); dB = dict(decks[b], 이름=f"{decks[b]['이름']} [자리1]")
    kw = dict(side=True, side_eps=0.0, learn_side=False)
    if MS._W['side_fn'] is not None: kw['side_fn'] = MS._W['side_fn']
    log = []
    mw, rounds = M.play_match(dA, dB, first, random.Random(seed), log, MS._W['make_ai'], **kw)
    i0, i1 = rounds[rnd - 1]['log']
    if rnd > 1: i0 = rounds[rnd - 2]['log'][1]
    return log[i0:i1], rounds[rnd - 1], mw


def render(entries, explore=False):
    """로그 → 마크다운 줄. 판단은 고른 수 · 대안 2개만, 사소한 판단(멀리건 · 서치 · 대상 …)은 생략 —
    단 explore=True(학습 매치)면 탐색으로 고른 판단은 종류와 관계없이 남기고 〔탐색〕으로 표시한다"""
    out = []; phase = None
    for e in entries:
        k = e.get('k', ''); m = clean(e.get('m', '')); t = e.get('t', '')
        if k == 'round':
            out += ['', f'**{m.strip("█ ").strip()}**', '']; phase = None; continue
        if k == 'turn':
            out += ['', f'*{m.strip("━ ").strip()}*', '']; phase = None; continue
        if k == 'snap':
            d = e.get('data')
            if d:
                out.append(f'  - 형세: HP {d["hp"][0]} / {d["hp"][1]} · 패 {d["hand"][0]} / {d["hand"][1]} · '
                           f'필드 [{", ".join(d["mons"][0] + d["spells"][0]) or "-"}] / [{", ".join(d["mons"][1] + d["spells"][1]) or "-"}]')
            continue
        if k == 'end':
            out += ['', f'**{m.strip("■ ").strip()}**', '']; continue
        ph = e.get('ph')
        if ph and ph != phase and t not in ('', 0, '0'):
            phase = ph; out.append(f'- [{ph}]')
        if k == 'decision':
            r = RE_DEC.match(m)
            if not r:
                out.append(f'  - {m}'); continue
            who, kind, opts, pick, why = r.groups()
            ex = '탐색' in why
            if (kind.startswith(SKIP_DEC) or opts.count('%(') < 2) and not (explore and ex):
                continue
            alts = [f'{lab} {v}%' for lab, v in RE_OPT.findall(opts) if lab != pick][:2]
            mark = ' 〔탐색〕' if ex else ''
            out.append(f'  - · 판단 ({kind}): {pick}{mark} — 대안 ' + (', '.join(alts) if alts else '없음'))
            continue
        pre = {'res': '    - ↳ ', 'act': '  - ▶ ' if re.search(r'효과 발동|일반소환|특수소환|→ |직접공격|세트$', m) else '    - ✦ '}.get(k, '  - ')
        out.append(pre + m)
    return out


def text_entries(lines):
    out = []
    for l in lines:
        p = l.split('\t', 3)
        if len(p) < 4: continue
        t, ph, k, m = p
        out.append({'t': int(t) if t.isdigit() else t, 'ph': ph, 'k': k, 'm': m})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True); ap.add_argument('--last', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--json')
    a = ap.parse_args(argv)
    sys.setrecursionlimit(10000); sys.path.insert(0, os.getcwd())   # nny_sim 폴더에서 실행
    import match_sim as MS
    meta = json.load(open(os.path.join(a.run, 'meta.json'), encoding='utf-8'))
    spec = meta['ai']
    MS._init(spec)
    rounds = load_rounds(os.path.join(a.run, 'rounds.jsonl.gz'))
    names = sorted({d for r in rounds for d in r['decks']})
    mf = most_frequent(rounds, names)
    last = json.load(gzip.open(a.last, 'rt', encoding='utf-8'))
    md = ['# 덱별 대표 게임 로그', '',
          f'- ① 최빈 구도: 리그 `{a.run}` 원자료에서 (승패 · 선후공 · 결착 방식 · 결착 턴) 최빈 조합의 첫 라운드를 같은 시드로 다시 돌린 전체 로그',
          f'- ② 수렴 직전 마지막 학습 매치: `{a.last}` (학습 매치 — ε 탐색 판단은 〔탐색〕 표시)',
          '- 기호: ▶ 행동 · ↳ 체인 처리 · ✦ 결과 · 판단은 고른 수와 대안(학습 승률). 사소한 판단(멀리건 · 서치 · 대상 선택)은 생략.', '']
    summ = {}
    for d in names:
        x = mf[d]; r, s = x['rep']
        ents, rinfo, mw = replay(r['decks'][0], r['decks'][1], r['match_first'] if 'match_first' in r else _match_first(rounds, r), r['seed'], r['round'])
        ok = rinfo['winner'] == r['winner_seat'] and rinfo['turns'] == r['turns']
        res, pos, how, turn = x['pattern']
        opp = r['decks'][1 - s]
        md += ['', '---', '', f'## {d}', '',
               f'### ① 최빈 구도 — {res} · {pos} · {how} · {turn}턴 ({x["count"]}/{x["rounds"]}라운드, {100 * x["count"] / x["rounds"]:.1f}%)', '',
               f'- 대표: 매치 {r["match_id"]} {r["round"]}라운드 · 상대 {opp} · 이 덱 자리 {s} · 시드 {r["seed"]} · 재현 {"일치" if ok else "불일치(!)"}',
               '- 상위 5개 조합: ' + ' · '.join(f'{"/".join(map(str, k))}턴 {n}' for k, n in x['top5']), '']
        md += render(ents)
        L = last.get(d)
        if L:
            ws = L['winner_seat']; me = L['decks'].index(d)
            md += ['', f'### ② 학습이 수렴한 마지막 시뮬레이션 로그 — 반복 {L["iter"]}', '',
                   f'- {L["decks"][0]} [자리0] vs {L["decks"][1]} [자리1] · 1라운드 선공 자리 {L["first"]} · 시드 {L["seed"]} · '
                   f'ε {L["eps"]} · 교체 ε {L.get("side_eps")} · {L["rounds"]}라운드 · 매치 승자 자리 {ws}', '']
            md += render(text_entries(L['log']), explore=True)
        summ[d] = {'pattern': x['pattern'], 'count': x['count'], 'rounds': x['rounds'], 'top5': x['top5'],
                   'rep': {'match_id': r['match_id'], 'round': r['round'], 'seat': s, 'seed': r['seed'], 'opp': opp, 'replay_ok': ok},
                   'last': {k: L[k] for k in L if k != 'log'} if L else None}
        print(d, x['pattern'], x['count'], '/', x['rounds'], '재현', ok, flush=True)
    open(a.out, 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    if a.json: json.dump(summ, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def _match_first(rounds, r):
    """매치 1라운드 선공 자리 (원자료는 라운드마다 그 라운드의 선공만 적으므로 1라운드 기록에서 찾는다)"""
    for x in rounds:
        if x['match_id'] == r['match_id'] and x['round'] == 1: return x['first_seat']
    raise KeyError(r['match_id'])


if __name__ == '__main__':
    main()
