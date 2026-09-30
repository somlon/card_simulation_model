"""DRL 모델 평가 — 고정 시드 단판, 학습 끔, 선후공 · 덱 조합을 모두 돌린다(덱 유불리 상쇄).

  python -m drl.evaluate --model learned/drl/run1/model_best.npz --vs heuristic --vs table:learned/policy.json [--k 12]
  --vs drl:<다른 모델.npz> 로 모델끼리도 비교한다.
  --matches: 단판 대신 Bo3 매치(전략 덱 교체 포함) — 상대 table:<policy.json>,<side.json> 또는 heuristic
결과: 승률 · 95% 신뢰구간 · 판수 · 안전장치 중단 수 · 평균 턴(매치 모드는 평균 라운드 수) · 덱별 승률(모델 쪽 덱 기준)
"""
import os
for _k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_k, '1')
import argparse, concurrent.futures as cf, json, multiprocessing as mp, time
from . import model as MD
from . import rollout as R


def drl_spec(path):
    """모델 파일 → 평가 작업자용 명세(스키마 검사 · 카드 번호 매핑 포함)"""
    actor, _ = MD.load_actor(path)
    return {'kind': 'drl', 'arrays': actor.w, 'remap': actor.remap}


def parse_vs(s):
    if s == 'heuristic':
        return 'heuristic', {'kind': 'heuristic'}
    kind, _, path = s.partition(':')
    if kind == 'table' and path:
        pol, _, side = path.partition(',')          # table:<policy.json>[,<side.json>] — 교체표는 매치 평가에서 쓴다
        return f'table:{os.path.basename(pol)}', {'kind': 'table', 'path': pol, 'side': side or None}
    if kind == 'drl' and path:
        return f'drl:{os.path.basename(path)}', drl_spec(path)
    raise SystemExit(f'--vs 형식: heuristic | table:<policy.json>[,<side.json>] | drl:<model.npz> (받은 값: {s})')


def main(argv=None):
    ap = argparse.ArgumentParser(description='DRL 모델 평가')
    ap.add_argument('--model', required=True); ap.add_argument('--vs', action='append', required=True)
    ap.add_argument('--k', type=int, default=6, help='덱 순서쌍 · 선후공마다 판 수 (총 판수 = 42 × 2 × k)')
    ap.add_argument('--workers', type=int, default=4); ap.add_argument('--base', type=int, default=2 * 10 ** 7, help='시드 시작값')
    ap.add_argument('--out', help='결과 JSON 저장 경로')
    ap.add_argument('--matches', action='store_true', help='단판 대신 Bo3 매치(전략 덱 교체 포함)로 평가 — 상대는 heuristic 또는 table만')
    a = ap.parse_args(argv)
    x = drl_spec(a.model)                            # 스키마 검사 (다르면 여기서 오류)
    import season as SE
    names = sorted(SE.load_decks()); gl = R.games_list(names, a.k, a.base)
    res = {'model': a.model, 'k': a.k, 'mode': 'match' if a.matches else 'game', 'results': {}}
    job_fn = R.eval_match_job if a.matches else R.eval_job
    with cf.ProcessPoolExecutor(a.workers, mp_context=mp.get_context('spawn'), initializer=R.init_worker, initargs=({},)) as pool:
        for s in a.vs:
            name, spec = parse_vs(s); t0 = time.time()
            if a.matches and spec['kind'] == 'drl':
                raise SystemExit('매치 평가 상대는 heuristic 또는 table만 지원')
            parts = list(pool.map(job_fn, [dict(x=x, y=spec, games=gl[i::a.workers]) for i in range(a.workers)]))
            r = R.merge_eval(parts); r['sec'] = round(time.time() - t0, 1)
            res['results'][name] = r
            print(json.dumps({name: r}, ensure_ascii=False), flush=True)
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
