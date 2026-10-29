"""재생 기록 폴더(library · 사용자 replays)의 체인 표시 점검: res 프레임 중 res 연출 없는 수, 처리 번호(높은 번호부터) 위반 수, 발동 프레임에 그 고리가 보이는지 — python3 chain_check.py <폴더>"""
import sys, json, gzip, glob, re
tot = miss = acts = act_vis = viol = 0
for f in sorted(glob.glob(sys.argv[1] + '/*.json.gz')):
    d = json.load(gzip.open(f, 'rt', encoding='utf-8')); S = d['states']
    for fr in d['frames']:
        m = fr.get('m', '')
        if fr.get('k') == 'res':
            tot += 1
            if not any(x.get('t') == 'res' for x in fr.get('fx', [])): miss += 1
            r = re.match(r'^체인 (\d+) ', m)
            if r and fr['s'] >= 0 and int(r.group(1)) != len(S[fr['s']]['ch']) + 1: viol += 1
        r = re.search(r'발동(?: \[.*\])? — 체인 (\d+)$', m)
        if r and fr['s'] >= 0:
            acts += 1; act_vis += len(S[fr['s']]['ch']) == int(r.group(1))
print(f'res 프레임 {tot} · res 연출 없음 {miss} · 처리 번호 ≠ 남은 체인+1 {viol} · 발동 프레임 {acts} 중 그 고리가 보임 {act_vis}')
