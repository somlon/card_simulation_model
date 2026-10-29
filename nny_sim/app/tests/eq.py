"""사람 자리 감싸기(human.install_block_hooks)가 AI끼리의 대전을 바꾸지 않는지 — 같은 시드 기록 문장 비교.
python3 eq.py split <sim> <split> <out>      # 감싸기 없이
python3 eq.py splithook <sim> <split> <out>  # 감싸기 설치 뒤 → 두 out 파일이 같아야 한다(cmp)
python3 eq.py full <sim> <split> <out>       # 전체 학습표(sim/learned/policy.json.xz, 메모리 약 4GB) — split 과 같아야 한다"""
import sys, os, json, random
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = [('투기장의 규칙', '던전마스터 셔플!', 7), ('올인', '희생제', 3), ('세제', '세제', 5)]   # (P1 덱, P2 덱, 시드)
mode, sim, split, out = sys.argv[1:5]
sim = os.path.abspath(sim); split = os.path.abspath(split); out = os.path.abspath(out)
sys.path.insert(0, sim); os.chdir(sim); sys.path.insert(0, APP)
import season as SE, match as M, policy as P
decks = SE.load_decks()
if mode == 'splithook':
    import human; human.install_block_hooks()
res = {}
for a, b, seed in CASES:
    if mode == 'full': tab = P.POLICY
    else:
        import tables as T; tab = T.matchup_table(split, [a, b])
    mk = lambda d: P.LearnedAI(d['스킬'], learn=False, table=tab)
    log = []
    dA = dict(decks[a], 이름='A'); dB = dict(decks[b], 이름='B')
    M.play_match(dA, dB, 0, random.Random(seed), log, mk, side=True, side_eps=0.0, learn_side=False)
    res[f'{a}|{b}|{seed}'] = [e['m'] for e in log]
with open(out, 'w', encoding='utf-8') as f: json.dump(res, f, ensure_ascii=False)
print(mode, {k: len(v) for k, v in res.items()})
