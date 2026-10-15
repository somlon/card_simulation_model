"""새 카드 재학습 보고서의 표 생성 (보고서 작성 지침 2 · 3장) — 판단표를 읽지 않고 원자료(JSON)만 쓴다.

  python3 make_tables.py --run <리그 폴더> --v1 <train_new/state.json> --v2 <train_v2/state.json> --out <표.md> [--json <집계.json>]

만드는 표
  A 입력 · 재현 정보(meta.json)   B 덱별 종합 매치 승률   C 학습 경과(1차 · 2차 재학습 평가)
  D 상성표   E 라운드 · 선후공   F 승리 · 패배 방식(종료 원인 · 결정타 · 결착 턴 · 역전 · 결정타 출처 · 준 대미지 종류)
  G 판단 데이터 보유율 · 처리 실패 · 안전장치 중단   H 시즌별 레시피 표 ① · ② (1차 시즌 0~3 + 2차 시즌 0~N)
원자료(rounds.jsonl.gz)는 한 줄씩 읽어 집계한다(메모리 절약)."""
import argparse, collections, gzip, json, math, os, statistics

IDEAL = (49.0, 51.0)


def ci(w, n):
    if not n: return None
    p = w / n
    return 196 * math.sqrt(p * (1 - p) / n)


def pct(w, n, digits=1):
    return f'{100 * w / n:.{digits}f}' if n else '—'


def short(d):
    return {'던전마스터 셔플!': '던전', '데이터버그 패키지 프로그램': '데이터버그', '번성충-대발생': '대발생', '세제': '세제',
            '소원의 분수': '분수', '솔루나 아츠': '솔루나', '올인': '올인', '투기장의 규칙': '투기장',
            '호박옥 - 몽식의 계약': '몽식', '호박옥 - 봉인의 계약': '봉인', '희생제': '희생제', '번성충-기생': '기생'}.get(d, d)


# ─────────────── 리그 원자료 집계 ───────────────
def stream_rounds(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('type', 'round') == 'round': yield r


def aggregate(run):
    per = collections.defaultdict(lambda: {
        'rounds': 0, 'wins': 0,
        'pos': collections.Counter(), 'pos_w': collections.Counter(),
        'reason_w': collections.Counter(), 'reason_l': collections.Counter(),
        'blow_w': collections.Counter(), 'blow_l': collections.Counter(),
        'src_w': collections.Counter(), 'src_l': collections.Counter(),
        'turns_w': [], 'turns_l': [], 'rev_w': 0, 'dealt': collections.Counter(), 'taken': collections.Counter(),
        'swap_rounds': 0})
    for r in stream_rounds(os.path.join(run, 'rounds.jsonl.gz')):
        w = r['winner_seat']
        for s in (0, 1):
            d = r['decks'][s]; x = per[d]; won = w == s; x['rounds'] += 1; x['wins'] += won
            pos = '선공' if r['first_seat'] == s else '후공'
            x['pos'][pos] += 1; x['pos_w'][pos] += won
            reason = 'HP 0' if 'HP 0' in r['reason'] else '덱아웃' if '덱아웃' in r['reason'] else '특수 승리' if '특수 승리' in r['reason'] else (r['reason'] or '무승부')
            fb = r.get('final_blow')
            if w is None:
                continue
            if won:
                x['reason_w'][reason] += 1; x['turns_w'].append(r['turns'])
                if fb: x['blow_w'][fb['kind']] += 1; x['src_w'][fb['source']] += 1
                if r.get('winner_min_hp_lead', 0) <= -1000: x['rev_w'] += 1
            else:
                x['reason_l'][reason] += 1; x['turns_l'].append(r['turns'])
                if fb: x['blow_l'][fb['kind']] += 1; x['src_l'][fb['source']] += 1
            pl = r['players'][s]
            x['dealt'].update(pl.get('damage_dealt', {})); x['taken'].update(pl.get('damage_taken', {}))
            if any(r.get('side_swaps_before', [[], []])[s]): x['swap_rounds'] += 1
    return per


# ─────────────── 표 ───────────────
def t_meta(meta, summ):
    i = meta.get('inputs', {}); c = meta.get('code', {})
    rows = ['| 항목 | 값 |', '|---|---|',
            f"| AI | {meta['ai']['ai']} (양쪽 자리 같은 AI · 같은 설정) |",
            f"| 판단표 | `{i.get('policy', {}).get('path')}` · {i.get('policy', {}).get('bytes')} B · SHA-1 `{i.get('policy', {}).get('sha1')}` |",
            f"| 교체표 | `{i.get('side', {}).get('path')}` · {i.get('side', {}).get('bytes')} B · SHA-1 `{i.get('side', {}).get('sha1')}` |",
            f"| 코드 커밋 | `{c.get('commit')}` ({c.get('branch', '')}{' · 수정 있음' if c.get('dirty') else ''}) |",
            f"| 시드 | {meta['seed']} |", f"| 순서쌍당 매치 수 | {meta['matches_per_pair']} (덱 {len(meta['decks_list'])}개 × {len(meta['decks_list'])} = {len(meta['decks_list']) ** 2} 순서쌍, 미러전 포함) |",
            f"| 매치 · 라운드 | {summ['matches']:,}매치 · {summ['rounds']:,}라운드 · 안전장치 중단 {summ['stalled_matches']} · 오류 {summ['error_matches']} |",
            f"| 실행 | {meta.get('started')} 시작 · {meta.get('sec')}초 · 작업자 {meta.get('workers')} |"]
    return rows


def t_decks(summ):
    D = summ['decks']; names = sorted(D, key=lambda d: -D[d]['match']['rate'])
    rows = ['| 순위 | 덱 | 매치 승률 | 95% CI | 매치 수 | 라운드 승률 | 이상 범위(49~51%) |', '|---|---|---|---|---|---|---|']
    for k, d in enumerate(names, 1):
        m = D[d]['match']; r = D[d]['round_overall']
        lo, hi = m['rate'] - m['ci95'], m['rate'] + m['ci95']
        judge = '안' if D[d]['in_ideal_range'] else ('높음' if m['rate'] > IDEAL[1] else '낮음')
        rows.append(f"| {k} | {d} | **{m['rate']:.1f}%** | ±{m['ci95']:.1f} ({lo:.1f}~{hi:.1f}) | {m['games']:,} | {r['rate']:.1f}% | {judge} |")
    return rows


def t_progress(v1, v2):
    rows = ['| 재학습 · 평가 | 반복 | 덱 승률 변동 χ² p | 최대 변동 %p | 직전 표 대비 | 빈 표 대비 | 안정 |', '|---|---|---|---|---|---|---|']
    calm = 0
    for tag, st in (('1차', v1), ('2차', v2)):
        calm = 0
        for ev in st['evals']:
            c = ev.get('chi2') or {}; h = ev.get('h2h'); he = ev.get('h2h_empty')
            calm = calm + 1 if ev.get('calm') else 0
            rows.append(f"| {tag} 평가 {ev['iter']} | {ev['iter']} | {c.get('p', float('nan')):.3f} | {c.get('max_delta_pp', '—')} | "
                        f"{(str(h['rate']) + '% ± ' + str(h['ci95'])) if h else '—'} | {(str(he['rate']) + '% ± ' + str(he['ci95'])) if he else '—'} | "
                        f"{'✔' if ev.get('calm') else ''} {calm}/2 |".replace('nan', '—'))
    return rows


def t_progress_decks(v1, v2):
    names = sorted(v2['evals'][-1]['league']['decks'])
    cols = [('1차', ev) for ev in v1['evals']] + [('2차', ev) for ev in v2['evals']]
    rows = ['| 덱 | ' + ' | '.join(f'{t}{ev["iter"]}' for t, ev in cols) + ' |', '|---|' + '---|' * len(cols)]
    for d in names:
        cells = []
        for t, ev in cols:
            x = ev['league']['decks'].get(d)
            cells.append(f"{x['rate']:.1f}" if x else '—')
        rows.append(f'| {d} | ' + ' | '.join(cells) + ' |')
    return rows


def t_vs(summ):
    names = sorted(summ['decks'], key=lambda d: -summ['decks'][d]['match']['rate'])
    rows = ['| 덱 \\ 상대 | ' + ' | '.join(short(o) for o in names) + ' |', '|---|' + '---|' * len(names)]
    for d in names:
        cells = []
        for o in names:
            v = summ['vs'].get(f'{d} vs {o}')
            cells.append(f"{v['rate']:.0f}" if v else '—')
        rows.append(f'| {d} | ' + ' | '.join(cells) + ' |')
    return rows


def t_rounds(summ, per):
    names = sorted(summ['decks'], key=lambda d: -summ['decks'][d]['match']['rate'])
    keys = [f'{r}R {p}' for r in (1, 2, 3) for p in ('선공', '후공')]
    rows = ['| 덱 | ' + ' | '.join(keys) + ' | 선공 전체 | 후공 전체 | 선후공 차 |', '|---|' + '---|' * (len(keys) + 3)]
    for d in names:
        R = summ['decks'][d]['rounds']; x = per[d]
        cells = [f"{R[k]['rate']:.1f} ({R[k]['games']:,})" if R.get(k) else '—' for k in keys]
        f_, s_ = 100 * x['pos_w']['선공'] / max(1, x['pos']['선공']), 100 * x['pos_w']['후공'] / max(1, x['pos']['후공'])
        rows.append(f'| {d} | ' + ' | '.join(cells) + f' | {f_:.1f} | {s_:.1f} | {f_ - s_:+.1f} |')
    return rows


def t_ways(summ, per):
    names = sorted(summ['decks'], key=lambda d: -summ['decks'][d]['match']['rate'])
    out = ['| 덱 | 이긴 라운드 | 종료: HP 0 / 덱아웃 / 특수 승리 | 결정타 (이긴 라운드 전체 대비): 직접공격 · 전투 · 효과 · 자해 · 마커 | 결착 턴 평균 (중앙값) | 4턴 이하 · 5~9 · 10턴 이상 | 역전승 |',
           '|---|---|---|---|---|---|---|']
    kinds = ('직접공격', '전투', '효과', '자해', '공유 존 마커')
    for d in names:
        x = per[d]; n = sum(x['reason_w'].values()); t = x['turns_w']
        bl = ' · '.join(pct(x['blow_w'][k], n, 0) for k in kinds)
        bins = (sum(1 for v in t if v <= 4), sum(1 for v in t if 5 <= v <= 9), sum(1 for v in t if v >= 10))
        out.append(f"| {d} | {n:,} | {pct(x['reason_w']['HP 0'], n, 0)}% / {pct(x['reason_w']['덱아웃'], n, 0)}% / {pct(x['reason_w']['특수 승리'], n, 0)}% | {bl} (%) | "
                   f"{statistics.mean(t):.1f} ({statistics.median(t):.0f}) | " + ' · '.join(pct(b, n, 0) for b in bins) + f" (%) | {pct(x['rev_w'], n, 1)}% |")
    out += ['', '패배 쪽', '', '| 덱 | 진 라운드 | 종료: HP 0 / 덱아웃 / 상대 특수 승리 | 받은 결정타: 직접공격 · 전투 · 효과 · 자해 · 마커 | 결착 턴 평균 (중앙값) |', '|---|---|---|---|---|']
    for d in names:
        x = per[d]; n = sum(x['reason_l'].values()); t = x['turns_l']
        bl = ' · '.join(pct(x['blow_l'][k], n, 0) for k in kinds)
        out.append(f"| {d} | {n:,} | {pct(x['reason_l']['HP 0'], n, 0)}% / {pct(x['reason_l']['덱아웃'], n, 0)}% / {pct(x['reason_l']['특수 승리'], n, 0)}% | {bl} (%) | {statistics.mean(t):.1f} ({statistics.median(t):.0f}) |")
    out += ['', '결정타 출처 상위 5 (이긴 라운드 기준, 출처 문자열 그대로 — 「~ 직접공격」은 공격한 몬스터, 「전투」는 전투 대미지, 그 밖은 효과 카드)', '']
    for d in names:
        x = per[d]; n = sum(x['src_w'].values())
        out.append(f"- **{d}** — " + ' · '.join(f'{s} {100 * c / n:.0f}%' for s, c in x['src_w'].most_common(5)))
    out += ['', '준 대미지 종류 (이긴 · 진 라운드 합계, 덱이 상대에게 준 대미지의 비중)', '', '| 덱 | 직접공격 | 전투 | 효과 | 받은 대미지 중 자해 |', '|---|---|---|---|---|']
    for d in names:
        x = per[d]; tot = sum(x['dealt'].values()) or 1; tk = sum(x['taken'].values()) or 1
        out.append(f"| {d} | {100 * x['dealt']['직접공격'] / tot:.0f}% | {100 * x['dealt']['전투'] / tot:.0f}% | {100 * x['dealt']['효과'] / tot:.0f}% | {100 * x['taken']['자해'] / tk:.0f}% |")
    return out


def t_quality(summ):
    names = sorted(summ['decks'])
    rows = ['| 덱 | 학습표 판단 수 | 그 매치업 데이터(L1)가 있던 비율 | 안전장치 중단 자리 수 |', '|---|---|---|---|']
    for d in names:
        c = summ['decks'][d].get('decision_coverage', {})
        rows.append(f"| {d} | {c.get('decisions', 0):,} | {('%.1f%%' % c['rate']) if c.get('rate') is not None else '—'} | {summ['decks'][d].get('stalled_match_seats', 0)} |")
    rows += ['', '처리 실패 (로그 패턴, 매치당 횟수): ' + (' · '.join(f"{k} {v['count']:,}회 ({v['per_match']}/매치)" for k, v in summ.get('failures', {}).items()) or '없음')]
    return rows


# ─────────────── 시즌별 레시피 ───────────────
def sz(x):
    return f"{x['메인']}/{x['상급']}/{x['전략']}" if x else '—'


def seasons_all(v1, v2):
    out = [(f'1차 {s["season"]}', s) for s in v1['seasons']] + [(f'2차 {s["season"]}', s) for s in v2['seasons']]
    return out


def t_season1(v1, v2):
    rows = ['| 시즌 | 학습 반복 | 덱 | 결정 | 변경 내용 | 메인/상급/전략 (전 → 후) | 근거: 현재 → 후보 승률, 차이, z (확인 z) |', '|---|---|---|---|---|---|---|']
    for lab, s in seasons_all(v1, v2):
        if s['season'] == 0: continue
        for d, c in sorted(s['changes'].items()):
            if not c: continue
            acc = c.get('accepted'); cf = c.get('confirm')
            diff = c.get('diff')
            why = f"{c.get('base')}% → {c.get('best_rate')}%" + (f", {diff:+}%p" if isinstance(diff, (int, float)) else '') + f", z = {c.get('z')}" + (f" (확인 z = {cf['z']})" if cf else '')
            what = c.get('best') if acc else f"(최선 후보: {c.get('best')})"
            rows.append(f"| {lab} | {s['iter']} | {d} | {'**채택**' if acc else '유지'} | {what} | {sz(c.get('sizes_before'))} → {sz(c.get('sizes_after'))} | {why} |")
    return rows


def t_season2(v1, v2):
    alls = seasons_all(v1, v2)
    keep = []
    for i, (lab, s) in enumerate(alls):
        if s['season'] == 0 or s.get('accepted') or i == len(alls) - 1: keep.append((lab, s))
    names = sorted(v2['seasons'][-1]['recipes'])
    out = [f"열 = 시즌 (전체 {len(alls)}개 중 각 재학습의 시즌 0 · 레시피가 바뀐 시즌 · 마지막 시즌). 칸 = 매수, 바로 앞 열과 달라진 칸은 굵게. "
           "1차 재학습에는 「투기장의 규칙」이 없었다(격투가 추가 전). 2차 시즌 0 = 1차 시즌 3 레시피 + 기생 축 삭제 반영."]
    for d in names:
        cols = [(lab, s) for lab, s in keep if d in s['recipes']]
        out += ['', f'**{d}**', '', '| 구역 | 카드 | ' + ' | '.join(lab for lab, _ in cols) + ' |', '|---|---|' + '---|' * len(cols)]
        tot = [{} for _ in cols]
        for sec in ('메인', '상급', '전략'):
            cards = sorted({n for _, s in cols for k, n in s['recipes'][d][sec]})
            for n in cards:
                row, prev = [], None
                for j, (_, s) in enumerate(cols):
                    k = dict((nm, kk) for kk, nm in s['recipes'][d][sec]).get(n, 0)
                    tot[j][sec] = tot[j].get(sec, 0) + k
                    row.append(f'**{k}**' if prev is not None and k != prev else str(k)); prev = k
                out.append(f'| {sec} | {n} | ' + ' | '.join(row) + ' |')
        out.append('| 합계 | 메인 / 상급 / 전략 | ' + ' | '.join(f"{t.get('메인', 0)} / {t.get('상급', 0)} / {t.get('전략', 0)}" for t in tot) + ' |')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True); ap.add_argument('--v1', required=True); ap.add_argument('--v2', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--json')
    a = ap.parse_args(argv)
    meta = json.load(open(os.path.join(a.run, 'meta.json'), encoding='utf-8'))
    summ = json.load(open(os.path.join(a.run, 'summary.json'), encoding='utf-8'))
    v1 = json.load(open(a.v1, encoding='utf-8')); v2 = json.load(open(a.v2, encoding='utf-8'))
    per = aggregate(a.run)
    md = []
    for title, rows in (('A. 입력 · 재현 정보', t_meta(meta, summ)), ('B. 덱별 종합 매치 승률', t_decks(summ)),
                        ('C-1. 학습 경과 — 평가별 수렴 지표', t_progress(v1, v2)), ('C-2. 학습 경과 — 평가별 덱 승률 (고정 시드 리그, 순서쌍당 100매치)', t_progress_decks(v1, v2)),
                        ('D. 상성표 (행 덱의 매치 승률 %, 열은 종합 승률 순)', t_vs(summ)), ('E. 라운드 · 선후공별 라운드 승률 % (라운드 수)', t_rounds(summ, per)),
                        ('F. 승리 · 패배 방식 (라운드 기준)', t_ways(summ, per)), ('G. 판단 데이터 보유율 · 처리 실패 · 안전장치', t_quality(summ)),
                        ('H-1. 표 ① 시즌별 레시피 변동', t_season1(v1, v2)), ('H-2. 표 ② 각 시즌의 덱별 레시피', t_season2(v1, v2))):
        md += ['', f'## {title}', ''] + rows
    open(a.out, 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    if a.json:
        js = {d: {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in x.items() if k not in ('turns_w', 'turns_l')} |
              {'turns_w_mean': statistics.mean(x['turns_w']) if x['turns_w'] else None, 'turns_l_mean': statistics.mean(x['turns_l']) if x['turns_l'] else None}
              for d, x in per.items()}
        json.dump(js, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('표 작성:', a.out)


if __name__ == '__main__':
    main()
