"""리그 표본 재생 집계 — 보고서 지침 2장 3항(주요 대미지 · 제외 출처) · 5항(선공 · 후공 1턴 운영).

리그 원자료에는 카드별 대미지 · 제외 출처와 턴별 행동이 없으므로, 순서쌍마다 앞쪽 매치 K개를 같은 시드 · 같은 표로
다시 돌려(match_sim.play_one과 같은 조건 — 재현 여부를 승자 · 턴 수로 확인) 로그에서 센다.
  - 대미지 출처: 「이름 N 대미지 (출처) → HP」 줄. 자해 · 공유 존 마커는 받은 쪽, 그 밖은 상대가 준 것.
  - 제외 출처: Game.banish를 감싸 실제로 제외 존에 간 카드마다 (주인, 원인 카드 · 그 컨트롤러)를 기록.
  - 첫 턴 운영: 선공 = 1턴, 후공 = 2턴(자기 첫 턴)에 그 플레이어가 한 행동(발동 · 소환 · 세트 · 공격) 순서.
    행동별 「그 라운드 승률 차이」는 상대 덱별로 나눈 뒤 표본 수로 가중 평균한 값만 낸다(덱 상성 착시 방지).

  python3 sample_stats.py --run <리그 폴더> --k 6 --out <집계.json> --md <표.md>   (nny_sim 폴더에서)"""
import argparse, collections, gzip, json, os, random, re, sys

RE_DMG = re.compile(r'^(.+?) (\d+) 대미지 \((.*)\) → HP (-?\d+)$')
RE_ACT = re.compile(r'^(.+?) 「(.+?)」 (\d)번 효과 발동')
RE_SUM = re.compile(r'^(.+?) 「(.+?)」 (일반소환|특수소환)')
RE_SET = re.compile(r'^(.+?) (?:마법|함정|카드) (\d+)장 세트$|^(.+?) 「(.+?)」 세트')
RE_ATK = re.compile(r'^(.+?) 「(.+?)」\(ATK \d+\) → (.+)$')
NAME_TAIL = re.compile(r' \(시제품용[^)]*\)')


def short_card(s):
    return s


def first_turn_actions(entries, name, turn):
    acts = []
    for e in entries:
        if e.get('t') != turn or e.get('k') != 'act': continue
        m = e['m']
        if not m.startswith(name): continue
        r = RE_ACT.match(m)
        if r: acts.append(f'발동 {r.group(2)}#{r.group(3)}'); continue
        r = RE_SUM.match(m)
        if r: acts.append(f'{r.group(3)} {r.group(2)}'); continue
        r = RE_ATK.match(m)
        if r: acts.append(f'공격 {r.group(2)}'); continue
        r = RE_SET.match(m)
        if r: acts.append('세트' if r.group(2) else f'세트 {r.group(4)}')
    return acts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True); ap.add_argument('--k', type=int, default=6)
    ap.add_argument('--out', required=True); ap.add_argument('--md', required=True)
    a = ap.parse_args(argv)
    sys.setrecursionlimit(10000); sys.path.insert(0, os.getcwd())
    import match_sim as MS, match as M, engine as E
    meta = json.load(open(os.path.join(a.run, 'meta.json'), encoding='utf-8'))
    MS._init(meta['ai'])
    # 리그 원자료에서 순서쌍마다 앞쪽 매치 K개(매치 번호순)와 그 1라운드 선공 · 결과
    want = collections.defaultdict(list); info = {}
    with gzip.open(os.path.join(a.run, 'rounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('type', 'round') != 'round': continue
            key = tuple(r['decks']); mid = r['match_id']
            if r['round'] == 1 and len(want[key]) < a.k and mid not in want[key]:
                want[key].append(mid); info[mid] = {'decks': r['decks'], 'first': r['first_seat'], 'seed': r['seed'], 'rounds': {}}
            if mid in info: info[mid]['rounds'][r['round']] = (r['winner_seat'], r['turns'])
    # 제외 기록용 감싸기
    ban = []
    orig_banish = E.Game.banish

    def banish(self, c, cause=None):
        before = c.zone
        orig_banish(self, c, cause)
        if c.zone == 'banish' and before != 'banish':
            cz = cause or ('effect', self.src)
            src = cz[1] if isinstance(cz, tuple) and len(cz) > 1 else None
            ban.append((c.owner, getattr(src, 'name', None) or (cz[0] if isinstance(cz, tuple) else str(cz)), getattr(src, 'controller', None), c.name))
    E.Game.banish = banish

    dmg = collections.defaultdict(collections.Counter)       # 덱 → 출처 → 상대에게 준 대미지
    ban_by = collections.defaultdict(collections.Counter)    # 덱 → 원인 카드 → 상대 카드를 제외한 수
    ban_self = collections.defaultdict(collections.Counter)  # 덱 → 원인 → 자기 카드가 제외된 수(자기 효과 · 코스트 포함)
    first = {'선공': collections.defaultdict(collections.Counter), '후공': collections.defaultdict(collections.Counter)}
    seqs = {'선공': collections.defaultdict(collections.Counter), '후공': collections.defaultdict(collections.Counter)}
    rows = []   # (덱, 선공/후공, 상대, 이김, 첫 턴 행동 집합) — 행동별 승률 차이는 모든 라운드를 모은 뒤 계산
    n_rounds = collections.Counter(); replay_bad = 0; n_match = 0
    for mid, x in sorted(info.items()):
        a_, b_ = x['decks']; decks = MS._W['decks']
        dA = dict(decks[a_], 이름=f"{decks[a_]['이름']} [자리0]"); dB = dict(decks[b_], 이름=f"{decks[b_]['이름']} [자리1]")
        names = [dA['이름'], dB['이름']]; kw = dict(side=True, side_eps=0.0, learn_side=False)
        log = []; ban.clear()
        try:
            mw, rounds = M.play_match(dA, dB, x['first'], random.Random(x['seed']), log, MS._W['make_ai'], **kw)
        except Exception as ex:
            replay_bad += 1; continue
        n_match += 1
        bans = list(ban)
        for i, rinfo in enumerate(rounds, 1):
            exp = x['rounds'].get(i)
            if exp and (exp[0] != rinfo['winner'] or exp[1] != rinfo['turns']): replay_bad += 1
            sl = log[rinfo['log'][0]:rinfo['log'][1]]
            for s in (0, 1):
                d = x['decks'][s]; n_rounds[d] += 1
                pos = '선공' if rinfo['first'] == s else '후공'
                acts = first_turn_actions(sl, names[s], 1 if pos == '선공' else 2)
                first[pos][d].update(set(acts)); seqs[pos][d][' → '.join(acts[:3]) + (' → …' if len(acts) > 3 else '') if acts else '(행동 없음)'] += 1   # 시작 수순 = 앞 3개 행동
                rows.append((d, pos, x['decks'][1 - s], rinfo['winner'] == s, frozenset(acts)))
            for e in sl:
                r = RE_DMG.match(e.get('m', ''))
                if not r: continue
                victim = names.index(r.group(1)) if r.group(1) in names else None
                if victim is None: continue
                src = NAME_TAIL.sub('', r.group(3)); amt = int(r.group(2))
                if src.startswith('자해') or src == '공유 존 마커': continue
                dealer = 1 - victim
                card = src[:-len(' 직접공격')] + ' (직접공격)' if src.endswith(' 직접공격') else src
                dmg[x['decks'][dealer]][card] += amt
        for owner, src, ctrl, cname in bans:
            if ctrl is None:
                ban_self[x['decks'][owner]]['규칙 · 출처 불명' if src in ('effect', 'rule', None) else f'{src} (규칙)'] += 1
            elif ctrl == owner:
                ban_self[x['decks'][owner]][src] += 1
            else:
                ban_by[x['decks'][ctrl]][src] += 1
    # 상대별로 나눈 승률 차이 (표본 수 가중 평균) — 행동한 판 · 안 한 판이 모두 있는 상대만
    strata = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0])))
    for d, pos, opp, won, acts in rows:
        for act in first[pos][d]:   # 상대별 [한 판 승, 한 판 수, 안 한 판 승, 안 한 판 수]
            c = strata[(d, pos)][act][opp]
            if act in acts: c[0] += won; c[1] += 1
            else: c[2] += won; c[3] += 1
    eff = {}
    for (d, pos), acts in strata.items():
        for act, by in acts.items():
            num = den = 0.0; nt = 0
            for opp, (w1, n1, w0, n0) in by.items():
                if n1 and n0:
                    wgt = n1 * n0 / (n1 + n0); num += wgt * (w1 / n1 - w0 / n0); den += wgt; nt += n1
            if den: eff[(d, pos, act)] = (100 * num / den, nt)
    out = {'matches': n_match, 'replay_mismatch_rounds': replay_bad, 'k_per_pair': a.k, 'rounds_per_deck': dict(n_rounds),
           'damage': {d: dict(c.most_common(15)) for d, c in dmg.items()},
           'banish_opp': {d: dict(c.most_common(15)) for d, c in ban_by.items()},
           'banish_self': {d: dict(c.most_common(10)) for d, c in ban_self.items()},
           'first_turn': {pos: {d: dict(c.most_common(12)) for d, c in v.items()} for pos, v in first.items()},
           'first_seq': {pos: {d: c.most_common(5) for d, c in v.items()} for pos, v in seqs.items()},
           'first_effect': {f'{d}|{pos}|{act}': [round(v[0], 1), v[1]] for (d, pos, act), v in sorted(eff.items())}}
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 마크다운
    names = sorted(n_rounds)
    md = [f'표본: 순서쌍마다 앞쪽 {a.k}매치 = {n_match}매치 재생 (원자료와 승자 · 턴 수가 다른 라운드 {replay_bad}개).', '']
    md += ['### 주요 대미지 출처 (상대에게 준 대미지 비중, 상위 6)', '']
    for d in names:
        c = dmg[d]; t = sum(c.values()) or 1
        md.append(f'- **{d}** — ' + ' · '.join(f'{k} {100 * v / t:.0f}%' for k, v in c.most_common(6)))
    md += ['', '### 제외 출처 (상대 카드를 제외 존으로 보낸 원인 카드, 표본 매치당 횟수)', '']
    for d in names:
        c = ban_by[d]; per_m = 2 * a.k * len(names)   # 이 덱이 앉은 매치-자리 수 ≈ 2 · K · 덱 수
        md.append(f'- **{d}** — ' + (' · '.join(f'{k} {v / per_m:.2f}' for k, v in c.most_common(5)) or '없음')
                  + ' / 자기 카드가 제외된 원인: ' + (' · '.join(f'{k} {v / per_m:.2f}' for k, v in ban_self[d].most_common(3)) or '없음'))
    md += ['', '### 선공 · 후공 첫 턴 운영 (그 첫 턴에 한 번 이상 한 행동의 비율, 상위 6)', '']
    for d in names:
        for pos in ('선공', '후공'):
            n = sum(seqs[pos][d].values()) or 1
            md.append(f'- **{d} · {pos}** ({n}라운드) — ' + ' · '.join(f'{k} {100 * v / n:.0f}%' for k, v in first[pos][d].most_common(6)))
            md.append(f'  - 가장 흔한 시작 수순(앞 3개 행동): ' + ' / '.join(f'「{s}」 {100 * v / n:.0f}%' for s, v in seqs[pos][d].most_common(3)))
            top = [(act, eff.get((d, pos, act))) for act, _ in first[pos][d].most_common(4)]
            top = [f'{act} {v[0]:+.0f}%p' for act, v in top if v and v[1] >= 20]
            if top: md.append('  - 그 행동을 한 라운드의 승률 차이(상대 덱별로 나눈 가중 평균): ' + ' · '.join(top))
    open(a.md, 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print('재생', n_match, '매치 · 불일치 라운드', replay_bad, flush=True)


if __name__ == '__main__':
    main()
