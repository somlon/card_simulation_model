"""시즌별 덱 레시피 표 생성 (보고서 작성 지침 3장): python recipe_tables.py <recipe_seasons.json 또는 state.json> [출력.md]
표 ① 시즌별 레시피 변동 — 시즌 · 학습 반복 · 덱 · 결정 · 변경 · 매수(전 → 후) · 근거
표 ② 각 시즌의 덱별 레시피 — 카드 × 시즌 매수(구역별), 바뀐 칸은 굵게. 시즌이 많으면 시즌 0 · 바뀐 시즌 · 마지막 시즌만"""
import json, sys

src = json.load(open(sys.argv[1], encoding='utf-8'))
seasons = src['seasons'] if isinstance(src, dict) else src
out = []


def sz(x):
    return f"{x['메인']}/{x['상급']}/{x['전략']}" if x else '—'


out += ['### 표 ① 시즌별 레시피 변동', '',
        '| 시즌 | 학습 반복 | 덱 | 결정 | 변경 내용 | 메인/상급/전략 (전 → 후) | 근거: 현재 → 후보 승률, 차이, z (확인 z) |',
        '|---|---|---|---|---|---|---|']
for s in seasons[1:]:
    for d, c in sorted(s['changes'].items()):
        if not c: continue
        acc = c.get('accepted')
        cf = c.get('confirm')
        why = f"{c.get('base')}% → {c.get('best_rate')}%, {c.get('diff'):+}%p, z = {c.get('z')}" + (f" (확인 z = {cf['z']})" if cf else '')
        lab = c.get('best') if acc else f"(최선 후보: {c.get('best')})"
        out.append(f"| {s['season']} | {s['iter']} | {d} | {'**채택**' if acc else '유지'} | {lab} | {sz(c.get('sizes_before'))} → {sz(c.get('sizes_after'))} | {why} |")
changed = [s['season'] for s in seasons[1:] if s.get('accepted')]
size_changes = [(s['season'], d, sz(c.get('sizes_before')), sz(c.get('sizes_after'))) for s in seasons[1:]
                for d, c in sorted(s['changes'].items()) if c and c.get('accepted') and c.get('sizes_before') != c.get('sizes_after')]
out += ['', f"- 레시피가 바뀐 시즌: {', '.join(map(str, changed)) or '없음'}"]
if size_changes:
    out.append('- 덱 매수 증감: ' + '; '.join(f'시즌 {a} {d} {b} → {c}' for a, d, b, c in size_changes))
out += ['', '### 표 ② 각 시즌의 덱별 레시피', '']
cols = [0] + changed + ([seasons[-1]['season']] if seasons[-1]['season'] not in changed and seasons[-1]['season'] != 0 else [])
cols = sorted(set(cols))
by = {s['season']: s for s in seasons}
decks = sorted(seasons[0]['recipes'])
note = '' if len(cols) == len(seasons) else f" (시즌 {len(seasons) - 1}개 중 시즌 0 · 레시피가 바뀐 시즌 · 마지막 시즌만)"
out.append(f'열 = 시즌{note}, 칸 = 매수. 바로 앞 열과 달라진 칸은 굵게.')
for d in decks:
    out += ['', f'**{d}**', '', '| 구역 | 카드 | ' + ' | '.join(f'시즌 {c}' for c in cols) + ' |', '|---|---|' + '---|' * len(cols)]
    tot = {c: {} for c in cols}
    for sec in ('메인', '상급', '전략'):
        names = sorted({n for c in cols for k, n in by[c]['recipes'][d][sec]})
        for n in names:
            row, prev = [], None
            for c in cols:
                k = dict((nm, kk) for kk, nm in by[c]['recipes'][d][sec]).get(n, 0)
                tot[c][sec] = tot[c].get(sec, 0) + k
                row.append(f'**{k}**' if prev is not None and k != prev else str(k)); prev = k
            out.append(f'| {sec} | {n} | ' + ' | '.join(row) + ' |')
    out.append('| 합계 | 메인 / 상급 / 전략 | ' + ' | '.join(f"{tot[c].get('메인', 0)} / {tot[c].get('상급', 0)} / {tot[c].get('전략', 0)}" for c in cols) + ' |')
text = '\n'.join(out) + '\n'
if len(sys.argv) > 2:
    open(sys.argv[2], 'w', encoding='utf-8').write(text)
print(text)
