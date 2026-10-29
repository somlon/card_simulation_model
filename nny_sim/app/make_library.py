"""기본 제공 재생 기록(library) 만들기 — AI vs AI 매치를 녹화하거나 viewer/replay.py --save-json 기록을 넣는다.

  python3 make_library.py --sim <실행 폴더> --split <분할 표> --out <library> --all-pairs --matches 1 --seed 1 [--workers 4]
  python3 make_library.py --out <library> --from-json 기록.json [...]
"""
import argparse, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def _setup(sim):
    sys.path[:0] = [sim, os.path.join(os.path.dirname(HERE), 'viewer'), HERE]
    os.chdir(sim)


def _record(args):
    sim, split, a, b, seed, first, tmp = args
    _setup(sim)
    import season as SE, session as SS
    decks = SE.load_decks()
    names = [a, b] if a != b else [f'{a} (P1)', f'{b} (P2)']
    store = SS.Store(tmp)
    m = SS.LiveMatch(store, split, [decks[a], decks[b]], names, human=False, seed=seed, first=first, title=f'{names[0]} vs {names[1]}')
    m._run()
    rec = m.replay_dict(); rec['meta']['created'] = time.strftime('%Y-%m-%d')
    return rec, m.status, m.error


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sim'); ap.add_argument('--split'); ap.add_argument('--out', required=True)
    ap.add_argument('--all-pairs', action='store_true', help='11개 덱의 모든 대진(미러전 제외, 순서 없는 쌍) — 선공은 번갈아')
    ap.add_argument('--mirror', action='store_true', help='미러전도 넣기'); ap.add_argument('--matches', type=int, default=1)
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--from-json', nargs='*', default=[])
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    sys.path.insert(0, HERE)
    recs = []
    for path in a.from_json:
        with open(path, encoding='utf-8') as f: x = json.load(f)
        recs += x if isinstance(x, list) else [x]
    if a.all_pairs:
        sim, split = os.path.abspath(a.sim), os.path.abspath(a.split)
        _setup(sim)
        import season as SE
        names = sorted(SE.load_decks())
        jobs = []; k = 0
        for i, x in enumerate(names):
            for y in names[i if a.mirror else i + 1:]:
                for _ in range(a.matches):
                    jobs.append((sim, split, x, y, a.seed + k, k % 2, os.path.join(out, '_tmp'))); k += 1
        with ProcessPoolExecutor(a.workers) as ex:
            for n, (rec, status, err) in enumerate(ex.map(_record, jobs), 1):
                print(f'{n}/{len(jobs)} {rec["meta"]["title"]} — {status}' + (f' {err[-200:]}' if err else ''), flush=True)
                if status == 'done': recs.append(rec)
    _setup(os.path.abspath(a.sim)) if a.sim else None
    import session as SS
    store = SS.Store(os.path.join(out, '_tmp'))
    for i, rec in enumerate(recs):
        m = rec['meta']; m.setdefault('kind', 'ai'); m.setdefault('created', time.strftime('%Y-%m-%d')); m.setdefault('status', 'done')
        m.setdefault('title', ' vs '.join(m['names']))
        store.save_replay(rec, base=out, rid=f'lib{i:03d}')
    import shutil; shutil.rmtree(os.path.join(out, '_tmp'), ignore_errors=True)
    print(out, len(recs), '매치')


if __name__ == '__main__':
    main()
