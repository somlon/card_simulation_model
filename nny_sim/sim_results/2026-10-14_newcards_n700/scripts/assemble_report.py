"""보고서 원고(report_src.md)의 자리표시자를 자료로 채워 재학습_결과_보고서.md를 만든다.

  python3 assemble_report.py <원고> <표.md(make_tables)> <sample_stats.md> <rep_logs.json> <해설 md 폴더> <빈 표 비교 md> <출력>

자리표시자
  {{A}} {{B}} {{C-1}} {{C-2}} {{D}} {{E}} {{F}} {{G}} {{H-1}}  — make_tables.py 의 같은 이름 절 본문
  {{H-2:<덱>}}   — 표 ② 중 그 덱의 표       {{SS:<덱>}} — 표본 재생의 그 덱 줄(대미지 · 제외 · 첫 턴)
  {{REP:<덱>}}   — 대표 로그 두 개의 머리 정보   {{COM:<덱>}} — 해설 파일의 그 덱 절   {{EMPTY}} — 빈 표 리그 비교
"""
import glob, json, os, re, sys

src, tables, ss, rep, comdir, empty, out = sys.argv[1:8]
T = open(tables, encoding='utf-8').read()
SS = open(ss, encoding='utf-8').read().split('\n')
R = json.load(open(rep, encoding='utf-8'))
COM = '\n'.join(open(f, encoding='utf-8').read() for f in sorted(glob.glob(os.path.join(comdir, 'commentary_*.md'))))
EMP = open(empty, encoding='utf-8').read() if os.path.exists(empty) else '(빈 표 리그 결과 없음)'


def section(key):
    m = re.search(r'^## ' + re.escape(key) + r'\.[^\n]*\n(.*?)(?=^## |\Z)', T, re.S | re.M)
    if not m: raise KeyError(key)
    return m.group(1).strip()


def h2(deck):
    body = section('H-2')
    m = re.search(r'^\*\*' + re.escape(deck) + r'\*\*\n\n(.*?)(?=^\*\*|\Z)', body, re.S | re.M)
    return (body.split('\n')[0] + '\n\n' + m.group(1).strip()) if m else '(표 없음)'


def ss2(deck):
    out = []; head = None; mine = False
    for line in SS:
        if line.startswith('### '): head = line[4:].split(' (')[0]; mine = False; continue
        if line.startswith('- **'):
            mine = line.startswith(f'- **{deck}** ') or line.startswith(f'- **{deck} · ')
            if mine:
                out.append(line.replace(f'- **{deck}** — ', f'- **{head}** — ').replace(f'- **{deck} · ', '- **첫 턴 · '))
            continue
        if mine and line.startswith('  - '): out.append('  ' + line)
    return '\n'.join(out)


def rep_head(deck):
    x = R[deck]; p = x['pattern']; r = x['rep']; L = x.get('last') or {}
    s = (f"- ① 최빈 구도: **{p[0]} · {p[1]} · {p[2]} · {p[3]}턴** — 그 덱 라운드 {x['rounds']:,}개 중 {x['count']:,}개({100 * x['count'] / x['rounds']:.1f}%). "
         f"대표 = 매치 {r['match_id']} {r['round']}라운드, 상대 {r['opp']}, 시드 {r['seed']}, 같은 시드 재생 {'일치' if r['replay_ok'] else '불일치'}.\n"
         f"  - 상위 5개 조합: " + ' · '.join(f"{'/'.join(map(str, k))}턴 {n:,}" for k, n in x['top5']) + '\n')
    if L:
        s += (f"- ② 수렴 직전 학습 매치: 반복 {L.get('iter')} · {L['decks'][0]} [자리0] vs {L['decks'][1]} [자리1] · 1라운드 선공 자리 {L['first']} · "
              f"시드 {L['seed']} · 탐색률 ε {L['eps']} · {L['rounds']}라운드 · 매치 승자 자리 {L['winner_seat']}")
    return s


def com(deck):
    blocks = re.findall(r'^### ' + re.escape(deck) + r' — (.*?)\n(.*?)(?=^### |^## |\Z)', COM, re.S | re.M)
    if not blocks: return '(해설 없음)'
    out = '\n\n'.join(f'#### {t.strip()}\n\n{b.strip()}' for t, b in blocks)
    rc = re.search(r'^## 요약 — 의심 규칙 위반 \(' + re.escape(deck) + r'\)\n(.*?)(?=^## |^### |\Z)', COM, re.S | re.M)
    if rc:
        out += ('\n\n#### 규칙 점검 — 해설에서 나온 의심 항목\n\n'
                '해설 에이전트가 적은 그대로다. 검증 결과(확정 · 재정 질문 · 기각)는 7-3에 모았다.\n\n' + rc.group(1).strip())
    return out


S = open(src, encoding='utf-8').read()
decks_src = os.path.join(os.path.dirname(src), 'deck_chapters.md')
if '{{DECKS}}' in S: S = S.replace('{{DECKS}}', open(decks_src, encoding='utf-8').read().strip())


def rulecheck():
    parts = re.findall(r'^## 요약 — 의심 규칙 위반[^\n]*\n(.*?)(?=^## |\Z)', COM, re.S | re.M)
    return '\n'.join(p.strip() for p in parts) or '(점검 결과 없음)'


S = S.replace('{{RULECHECK}}', rulecheck())
RCP = open(os.path.join(os.path.dirname(src), 'recipes.md'), encoding='utf-8').read()


def recipe(deck):
    m = re.search(r'^\*\*' + re.escape(deck) + r'\*\*\n\n(.*?)(?=^\*\*|\Z)', RCP, re.S | re.M)
    return m.group(1).strip() if m else '(레시피 없음)'


S = re.sub(r'\{\{RECIPE:(.+?)\}\}', lambda m: recipe(m.group(1)), S)
S = re.sub(r'\{\{H-2:(.+?)\}\}', lambda m: h2(m.group(1)), S)
S = re.sub(r'\{\{SS:(.+?)\}\}', lambda m: ss2(m.group(1)), S)
S = re.sub(r'\{\{REP:(.+?)\}\}', lambda m: rep_head(m.group(1)), S)
S = re.sub(r'\{\{COM:(.+?)\}\}', lambda m: com(m.group(1)), S)
S = S.replace('{{EMPTY}}', EMP.strip())
SWD = os.path.join(os.path.dirname(empty), 'swing')


def swing_one(i):
    a = open(os.path.join(SWD, f'analysis_{i}.md'), encoding='utf-8').read().strip()
    head, _, body = a.partition('\n')
    sp = os.path.join(SWD, f'summary_{i}.md')
    summ = open(sp, encoding='utf-8').read().strip() if os.path.exists(sp) else ''
    return '#' + head.strip() + '\n\n' + summ + '\n\n' + body.strip()


SWING = '\n\n'.join(swing_one(i) for i in (1, 2, 3) if os.path.exists(os.path.join(SWD, f'analysis_{i}.md')))
S = S.replace('{{SWING}}', SWING or '(분석 없음)')
D0 = os.path.dirname(src)


def rd(name, default='(자료 없음)'):
    p = os.path.join(D0, name)
    return open(p, encoding='utf-8').read().strip() if os.path.exists(p) else default


PC = rd('probe_compare.md', '')


def probe_sec(title):
    m = re.search(r'^### ' + re.escape(title) + r'[^\n]*\n(.*?)(?=^### |\Z)', PC, re.S | re.M)
    return ('**' + m.group(0).split('\n')[0][4:].strip() + '**\n\n' + m.group(1).strip()) if m else '(측정 없음)'


S = S.replace('{{R1CMP}}', rd('r1_vs_match.md')).replace('{{ASSASSIN}}', rd('assassin_compare.md'))
S = S.replace('{{NOSWAP}}', probe_sec('전략 덱 교체 끔')).replace('{{FIXED}}', probe_sec('구현 오류 4건 수정'))
S = re.sub(r'\{\{([A-H](?:-\d)?)\}\}', lambda m: section(m.group(1)), S)
left = re.findall(r'\{\{.*?\}\}', S)
if left: print('남은 자리표시자:', left)
open(out, 'w', encoding='utf-8').write(S)
print('보고서:', out, len(S.split('\n')), '줄')
