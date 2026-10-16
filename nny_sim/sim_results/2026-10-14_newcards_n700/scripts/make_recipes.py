"""덱별 최종 레시피 표 (리그에 쓴 덱 = learned/decks/*.json, 재학습 시즌 8 수렴 상태) — nny_sim 폴더에서 실행
  python3 make_recipes.py <출력.md> <출력.json>
덱마다 메인 · 상급 · 전략 덱의 모든 카드: 매수 · 종류 · 레벨 · 공격력/수비력 · 시작 덱(decks/시제_*.deck) 대비 증감.
"""
import collections, glob, json, os, sys
sys.path.insert(0, os.getcwd())
import deck as D

POOL = {c['name']: c for c in json.load(open('card_pool.json', encoding='utf-8'))}
start = {}
for f in sorted(glob.glob('decks/시제_*.deck')):
    d = D.load(f, policy=False)[0]; start[d['스킬']] = d
SECS = ('메인', '상급', '전략')


def kind(c):
    if c['type'] == '몬스터': return '몬스터'
    return f"{c['type']} ({c['subtype']})" if c.get('subtype') else c['type']


def stats(c):
    if c['type'] != '몬스터': return '', ''
    return str(c.get('level', '')), f"{c.get('atk', '?')} / {c.get('def', '?')}"


out_md, out_js = [], {}
for f in sorted(glob.glob('learned/decks/*.json')):
    d = json.load(open(f, encoding='utf-8')); sk = d['스킬']; s0 = start.get(sk)
    sc = POOL[sk]
    out_md += [f'**{sk}**', '',
               f"스킬 「{sk}」 · 덱 이름 「{d['이름']}」 · 메인 {sum(n for n, _ in d['메인'])}장 · 상급 {sum(n for n, _ in d['상급'])}장 · 전략 {sum(n for n, _ in d['전략'])}장", '',
               '| 구분 | 카드 | 매수 | 종류 | 레벨 | 공격력 / 수비력 | 시작 덱 대비 |', '|---|---|---|---|---|---|---|']
    js = {'이름': d['이름'], '스킬': sk}
    for sec in SECS:
        now = collections.Counter({n: k for k, n in d[sec]})
        was = collections.Counter({n: k for k, n in s0[sec]}) if s0 else collections.Counter()
        js[sec] = [[k, n] for k, n in d[sec]]
        for k, n in d[sec]:
            c = POOL.get(n, {'type': '?'}); lv, ad = stats(c); dd = k - was.get(n, 0)
            out_md.append(f"| {sec} | {n} | {k} | {kind(c)} | {lv} | {ad} | {'—' if dd == 0 else (f'+{dd}' if dd > 0 else f'−{-dd}')} |")
        gone = [(n, was[n]) for n in was if n not in now]
        for n, k in gone:
            c = POOL.get(n, {'type': '?'})
            out_md.append(f'| {sec} | ~~{n}~~ (빠짐) | 0 | {kind(c)} | {stats(c)[0]} | {stats(c)[1]} | −{k} |')
        js[sec + '_빠짐'] = gone
    out_md.append('')
    out_js[sk] = js
open(sys.argv[1], 'w', encoding='utf-8').write('\n'.join(out_md) + '\n')
json.dump(out_js, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('덱', len(out_js), '→', sys.argv[1])
