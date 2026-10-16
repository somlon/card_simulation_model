"""리그의 한 순서쌍 앞쪽 매치 N개를 같은 시드로 다시 돌려 읽기 쉬운 로그로 저장 (rep_logs.render 사용)"""
import gzip, json, os, random, sys
sys.setrecursionlimit(10000); sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_sim as MS, match as M, rep_logs as RL
run, a, b, n, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
MS._init(json.load(open(os.path.join(run, 'meta.json'), encoding='utf-8'))['ai'])
want = []
with gzip.open(os.path.join(run, 'rounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        if r.get('type', 'round') == 'round' and r['decks'] == [a, b] and r['round'] == 1:
            want.append((r['match_id'], r['first_seat'], r['seed']))
            if len(want) >= n: break
decks = MS._W['decks']; md = []
for mid, first, seed in want:
    dA = dict(decks[a], 이름=f"{decks[a]['이름']} [자리0]"); dB = dict(decks[b], 이름=f"{decks[b]['이름']} [자리1]")
    log = []
    mw, rounds = M.play_match(dA, dB, first, random.Random(seed), log, MS._W['make_ai'], side=True, side_eps=0.0, learn_side=False)
    md += ['', f'## 매치 {mid} — 승자 자리 {mw} · {len(rounds)}라운드 · 시드 {seed}', ''] + RL.render(log)
open(out, 'w', encoding='utf-8').write('\n'.join(md))
print('저장', out, len(md))
