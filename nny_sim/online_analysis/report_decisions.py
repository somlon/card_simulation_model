"""aggregate_decisions.py의 출력(by_choice/common_points)을 사람이 읽기 좋은 한국어 문장
리포트로 추린다. `docs/AI_방식_선택지.md`가 정한 "표본이 적을 때는 판수를 함께 표기해 과신하지
않는다" 원칙을 지켜, 모든 줄에 판수(n)를 같이 적고 표본이 적은 조합은 "(표본 적음)" 딱지를 붙인다.
"""
import json

DEFAULT_MIN_N = 5


def _pct(x):
    return f'{round(x * 100)}%' if x is not None else '-'


def _flag(n, min_n):
    return ' (표본 적음)' if n < min_n else ''


def render_by_choice(rows, min_n=DEFAULT_MIN_N, top=None):
    """② 상황별 카드 선택-승률 — 판수 많은 순으로 "{decision} → {pick}: N판 중 W승 (승률 P%)" 문장."""
    lines = []
    for row in rows[:top] if top else rows:
        lines.append(
            f"- {row['decision']} → {row['pick']}: {row['n']}판 중 {row['wins']}승 "
            f"(승률 {_pct(row['win_rate'])}){_flag(row['n'], min_n)}"
        )
    return lines


def render_common_points(rows, min_n=DEFAULT_MIN_N, top=None):
    """① 이긴 판 공통 요점 — 이긴 판에 나온 횟수(won_n) 많은 순으로
    "{decision} → {pick}: 이긴 판 W회 / 진 판 L회 (이긴 비율 S%)" 문장."""
    lines = []
    for row in rows[:top] if top else rows:
        lines.append(
            f"- {row['decision']} → {row['pick']}: 이긴 판 {row['won_n']}회 / 진 판 {row['lost_n']}회 "
            f"(이긴 비율 {_pct(row['won_share'])}){_flag(row['n'], min_n)}"
        )
    return lines


def render_report(result, min_n=DEFAULT_MIN_N, top=None):
    """result: aggregate()의 출력 {'by_choice': [...], 'common_points': [...]}.
    반환: 전체 리포트 텍스트(제목 + 두 섹션). 둘 다 빈 리스트면 그 사실을 적은 한 줄짜리 리포트."""
    by_choice = result.get('by_choice') or []
    common_points = result.get('common_points') or []
    if not by_choice and not common_points:
        return '집계할 판단 레코드가 없다(승패가 확정된 기보가 아직 없거나 판단이 없음).'

    parts = ['# AI 실력 트랙 — 판단 리포트', '']
    parts.append('## ① 이긴 판에 자주 나온 선택 (공통 요점 후보)')
    parts.extend(render_common_points(common_points, min_n=min_n, top=top) or ['(집계 없음)'])
    parts.append('')
    parts.append('## ② 상황별 카드 선택과 승률 (판수 많은 순)')
    parts.extend(render_by_choice(by_choice, min_n=min_n, top=top) or ['(집계 없음)'])
    parts.append('')
    parts.append(f'표본 n < {min_n}인 조합은 "(표본 적음)"으로 표시 — 과신하지 않는다.')
    return '\n'.join(parts)


def main(argv):
    import sys
    if len(argv) < 2:
        sys.exit('usage: report_decisions.py <aggregate_decisions.py 출력.json> [-o 출력.md] [--top N] [--min-n N]')
    args = list(argv[1:])
    out_path = None
    top = None
    min_n = DEFAULT_MIN_N
    if '-o' in args:
        i = args.index('-o')
        out_path = args[i + 1]
        args = args[:i] + args[i + 2:]
    if '--top' in args:
        i = args.index('--top')
        top = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    if '--min-n' in args:
        i = args.index('--min-n')
        min_n = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    with open(args[0], encoding='utf-8') as f:
        result = json.load(f)
    text = render_report(result, min_n=min_n, top=top)
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        print(text)


if __name__ == '__main__':
    import sys
    main(sys.argv)
