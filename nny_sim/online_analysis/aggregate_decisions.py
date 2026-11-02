"""판단 레코드(extract_decisions.py 출력) 다수를 모아 집계 — ①이긴 판 공통 요점 ②상황별 카드
선택-승률. `docs/AI_방식_선택지.md` 확정(2안+3안 조합)의 목표 산출물 두 가지를 낸다.

extract_decisions.py가 기보 1개에서 뽑은 판단 레코드들을 여러 기보에 걸쳐 모아
(decision, pick) 조합별로 승률·판수를 센다. 사람 기보가 아직 없어(online/data-games 기보 0건)
지금은 AI끼리 돌린 기보로 파이프라인만 검증한다 — 사람 판이 쌓이면 그 파일들을 그대로 넘기면 된다.
확정 문서의 "표본이 적을 때는 판수를 함께 표기해 과신하지 않는다" 원칙대로, 모든 집계 행에 표본
수(n)를 함께 낸다 — win_rate만 보고 판단하지 않도록.
"""
import json
from collections import defaultdict


def aggregate(rows):
    """rows: extract_decisions()가 낸 판단 레코드들(여러 기보를 이어붙인 것도 됨).

    반환: {'by_choice': [...], 'common_points': [...]}
    - by_choice (②): (decision, pick)별 {n, wins, win_rate} — 표본 수 내림차순.
    - common_points (①): (decision, pick)별로 이긴 판/진 판에서 몇 번 나왔는지 — 이긴 판에
      더 많이 나온(won_n 내림차순) 조합이 "그 판의 공통 요점"에 가까운 후보다.
    won_match가 None(승패 미확정)이거나 pick이 없는 레코드는 집계에서 뺀다.
    """
    by_choice = defaultdict(lambda: {'n': 0, 'wins': 0})
    won_counts = defaultdict(int)
    lost_counts = defaultdict(int)
    for r in rows:
        if r.get('won_match') is None or r.get('pick') is None:
            continue
        key = (r['decision'], r['pick'])
        c = by_choice[key]
        c['n'] += 1
        if r['won_match']:
            c['wins'] += 1
            won_counts[key] += 1
        else:
            lost_counts[key] += 1

    choice_rows = []
    for (decision, pick), c in by_choice.items():
        choice_rows.append({
            'decision': decision, 'pick': pick, 'n': c['n'], 'wins': c['wins'],
            'win_rate': c['wins'] / c['n'] if c['n'] else None,
        })
    choice_rows.sort(key=lambda x: (-x['n'], -(x['win_rate'] or 0)))

    all_keys = set(won_counts) | set(lost_counts)
    point_rows = []
    for decision, pick in all_keys:
        w = won_counts.get((decision, pick), 0)
        l = lost_counts.get((decision, pick), 0)
        total = w + l
        point_rows.append({
            'decision': decision, 'pick': pick, 'n': total, 'won_n': w, 'lost_n': l,
            'won_share': w / total if total else None,
        })
    point_rows.sort(key=lambda x: (-x['won_n'], -(x['won_share'] or 0)))

    return {'by_choice': choice_rows, 'common_points': point_rows}


def aggregate_files(paths):
    from extract_decisions import extract_file
    rows = []
    for p in paths:
        rows.extend(extract_file(p))
    return aggregate(rows)


def main(argv):
    import sys
    if len(argv) < 2:
        sys.exit('usage: aggregate_decisions.py <기보1.json[.gz]> [기보2 ...] [-o 출력.json]')
    paths = list(argv[1:])
    out_path = None
    if '-o' in paths:
        i = paths.index('-o')
        out_path = paths[i + 1]
        paths = paths[:i] + paths[i + 2:]
    result = aggregate_files(paths)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
    else:
        print(text)
    print(f'{len(paths)}개 기보, {len(result["by_choice"])}개 (판단,선택) 조합 집계', file=sys.stderr)


if __name__ == '__main__':
    import sys
    main(sys.argv)
