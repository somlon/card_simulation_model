"""매치 재생 화면 만들기 — AI끼리 둔 Bo3 매치를 기록해 브라우저에서 보는 단일 HTML 파일로.

  python3 viewer/replay.py --a "투기장의 규칙" --b "던전마스터 셔플!" --seed 7 --out 재생.html
  python3 viewer/replay.py --a ... --b ... --seed 7 --matches 5 --out 재생.html   # 시드 7~11 매치 5개를 한 파일에(화면에서 골라 봄)
  python3 viewer/replay.py --pair 세제 "소원의 분수" --pair "솔루나 아츠" "투기장의 규칙" --out 재생.html   # 대진 여러 개
  python3 viewer/replay.py --list                       # 덱 목록과 카드 이미지 보유 현황
  python3 viewer/replay.py --from-json 기록.json --out 재생.html   # 저장해 둔 기록으로 다시 만들기

--sim: 시뮬레이터 폴더(engine.py · card_pool.json · decks · learned). 기본은 이 파일의 상위 폴더(nny_sim).
--ai: table(학습표 AI — match_sim 기본값과 같음, 판단표를 불러오는 데 약 3GB 메모리) | heuristic.
화면은 외부 파일 · 네트워크 없이 열린다(이미지 · 기록을 파일 안에 넣는다).
"""
import argparse, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(os.path.dirname(HERE), 'app', 'static')   # board.js · app.css (게임 프로그램 화면과 공용)
sys.path.insert(0, HERE)
import record as REC   # noqa: E402
import assets as AS    # noqa: E402


def build_html(recs, out):
    names = {n for rec in recs for n in rec['pool']}
    # 라운드 사이 전략 덱 교체 화면이 보여 줄 카드(게임에 나오지 않은 전략 덱 카드 포함)
    names |= {x for rec in recs for fr in rec['frames'] if fr['k'] == 'side' for sw in (fr.get('d') or {}).get('swaps', []) for x in sw[:2]}
    bundle = AS.bundle(names)
    today = datetime.date.today().isoformat()
    recs = [dict(rec, built=today) for rec in recs]
    m = recs[0]['meta']
    pairs = {tuple(r['meta']['decks']) for r in recs}
    title = f"매치 재생 — {m['names'][0]} vs {m['names'][1]}" if len(pairs) == 1 else f"매치 재생 — 대진 {len(pairs)}개 · {len(recs)}매치"
    def js(o): return json.dumps(o, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    def read(*p):
        with open(os.path.join(*p), encoding='utf-8') as f: return f.read()
    html = read(HERE, 'template.html')
    board, css = read(STATIC, 'board.js').replace('</script', '<\\/script'), read(STATIC, 'app.css')   # 게임 프로그램과 같은 보드 · 재생 부품
    html = (html.replace('__TITLE__', title).replace('/*__CSS__*/', css, 1).replace('/*__BOARD__*/', board, 1)
            .replace('/*__DATA__*/', f'const REPLAYS={js(recs)};\nconst ASSETS={js(bundle)};', 1))
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    have = sum(1 for n in names if n in bundle['faces'])
    return have, len(names)


def list_decks():
    import season as SE, cards as C
    extra, missing = AS.check(set(C.POOL))
    have = set(C.POOL) - set(missing)
    for name, d in sorted(SE.load_decks().items()):
        cards = {n for sec in ('메인', '상급', '전략') for _, n in d[sec]} | {d['스킬']}
        print(f'{name}: 카드 {len(cards)}종 중 이미지 {len(cards & have)}종')
    if extra: print('시트에 있지만 카드 풀에 없는 이름(쓰지 않음):', ', '.join(extra))
    if missing: print(f'이미지가 없는 풀 카드 {len(missing)}장:', ', '.join(missing))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--a', help='P1 덱(스킬 이름)'); ap.add_argument('--b', help='P2 덱(스킬 이름)')
    ap.add_argument('--pair', nargs=2, action='append', metavar=('P1', 'P2'), help='대진(여러 번 줄 수 있음) — --a/--b 대신')
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--first', type=int, default=0, help='1라운드 선공 자리 (0 = P1)')
    ap.add_argument('--matches', type=int, default=1, help='매치 수 — 시드를 1씩 늘리고 1라운드 선공을 번갈아 정한다')
    ap.add_argument('--ai', default='table'); ap.add_argument('--sim', default=REC.DEFAULT_SIM)
    ap.add_argument('--out', help='출력 HTML'); ap.add_argument('--save-json', help='기록을 JSON으로도 저장')
    ap.add_argument('--from-json', help='저장해 둔 기록으로 만들기'); ap.add_argument('--list', action='store_true')
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out) if a.out else None
    save = os.path.abspath(a.save_json) if a.save_json else None
    if a.from_json:
        with open(a.from_json, encoding='utf-8') as f: recs = json.load(f)
        if isinstance(recs, dict): recs = [recs]
    else:
        REC.use_sim(a.sim)
        if a.list: list_decks(); return
        pairs = a.pair or ([(a.a, a.b)] if a.a and a.b else [])
        if not (pairs and out): ap.error('--a · --b(또는 --pair)와 --out 이 필요함 (덱 목록은 --list)')
        recs = [REC.record_match(x, y, seed=a.seed + k, first=(a.first + k) % 2, ai=a.ai) for x, y in pairs for k in range(a.matches)]
        if save:
            with open(save, 'w', encoding='utf-8') as f: json.dump(recs, f, ensure_ascii=False, separators=(',', ':'))
    if not out: ap.error('--out 이 필요함')
    have, n = build_html(recs, out)
    print(f'{out}  (카드 이미지 {have}/{n}종)')
    for rec in recs:
        m = rec['meta']
        print(f"  {m['names'][0]} vs {m['names'][1]} · 시드 {m['seed']} · 기록 {len(rec['frames'])}줄"
              f" · 승자 {m['names'][m['winner']] if m['winner'] is not None else '없음'}" + (f" · 중단: {m['stalled']}" if m.get('stalled') else ''))


if __name__ == '__main__':
    main()
