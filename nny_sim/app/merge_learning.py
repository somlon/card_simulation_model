"""게임 프로그램의 학습 기록을 저장소의 학습표에 합친다 — 프로그램이 쌓은 jsonl(한 줄 = 한 매치)을 policy 표에 더한다.

  python3 merge_learning.py --policy <실행 폴더>/learned/policy.json.xz --logs <폴더 또는 jsonl ...> [--dry-run]

- 같은 매치(기록의 id)는 한 번만 합친다: 합친 id 목록을 표 옆의 human_games_merged.json 에 남긴다.
- 갱신은 프로그램 안 학습과 같다(policy.Table.update — L1 · L2 · L0). 표의 games 에 합친 매치 수를 더한다.
- 출처별 가중치(app/learndata.py — 프로그램과 같은 값): 줄의 source 가 'human'(사람 대전)이면 HUMAN_WEIGHT, 'ai'(AI끼리)면 AI_WEIGHT,
  source 가 없는 예전 기록은 사람 대전. 프로그램에서 「학습 데이터 정리」로 뺀 매치는 내보내기 · 올리기 파일에 들어 있지 않다.
- 합친 표로 이어서 학습(train_table.py) · 리그 · 프로그램 빌드(build_windows.py — 대전별 표를 다시 나눔)를 하면 된다.
"""
import argparse, glob, json, lzma, os, sys, time


def iter_logs(paths):
    for p in paths:
        files = sorted(glob.glob(os.path.join(p, '*.jsonl'))) if os.path.isdir(p) else [p]
        for f in files:
            with open(f, encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if not line: continue
                    try: yield f, json.loads(line)
                    except ValueError: print(f'건너뜀(깨진 줄): {f}', file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--policy', required=True); ap.add_argument('--logs', nargs='+', required=True)
    ap.add_argument('--out', help='저장할 표(기본: --policy 덮어쓰기)'); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    sim = os.path.dirname(os.path.dirname(os.path.abspath(a.policy)))
    sys.path.insert(0, sim)
    from policy import Table   # noqa: E402 — 시뮬레이터 폴더의 policy.py (같은 갱신 규칙)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import learndata as LD   # noqa: E402 — 출처별 가중치
    merged_path = os.path.join(os.path.dirname(os.path.abspath(a.policy)), 'human_games_merged.json')
    try: merged = set(json.load(open(merged_path, encoding='utf-8')))
    except (OSError, ValueError): merged = set()
    t0 = time.time(); t = Table.load(a.policy); print(f'표 읽음 {time.time() - t0:.0f}초 — L2 {len(t.L2)}개')
    n_rec = n_upd = 0; new_ids = []; by = {}
    for f, rec in iter_logs(a.logs):
        rid = rec.get('id')
        if not rid or rid in merged or rid in new_ids: continue
        src = LD.record_source(rec); w = LD.weight_of(src)
        for k1, k2, won in rec.get('updates', ()): t.update(k1, k2, won, w); n_upd += 1
        n_rec += 1; new_ids.append(rid); by[src] = by.get(src, 0) + 1
    print(f'새 매치 {n_rec}개 · 갱신 {n_upd}개 (이미 합친 매치 {len(merged)}개는 건너뜀) — 출처별 매치 '
          + ', '.join(f'{LD.SOURCE_LABEL.get(k, k)} {v}개(가중치 {LD.weight_of(k)})' for k, v in sorted(by.items())))
    if a.dry_run or not n_rec: return
    t.games += n_rec
    r = lambda x: round(x, 3) if isinstance(x, float) else x
    rd = lambda D: {k: [r(v[0]), r(v[1])] for k, v in D.items()}
    d = {'games': t.games, 'L1': rd(t.L1), 'L2': rd(t.L2)}
    if t.L0: d['L0'] = rd(t.L0)
    out = a.out or a.policy; tmp = out + '.tmp'
    with (lzma.open(tmp, 'wt', encoding='utf-8', preset=6) if out.endswith('.xz') else open(tmp, 'w', encoding='utf-8')) as fh:
        json.dump(d, fh, ensure_ascii=False)
    os.replace(tmp, out)
    with open(merged_path, 'w', encoding='utf-8') as fh: json.dump(sorted(merged | set(new_ids)), fh, ensure_ascii=False, indent=0)
    print(f'저장: {out} · 합친 id 목록 {merged_path}')


if __name__ == '__main__':
    main()
