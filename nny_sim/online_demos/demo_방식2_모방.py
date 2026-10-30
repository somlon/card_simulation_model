"""방식 2 데모 — 「사람 로그 모방」.

기보(replay)에서 (상황, 고른 수) 쌍을 모아 "같은 상황에서 플레이어가 고른 수"를
따라하는 모방 정책을 만들고, 떼어 둔 시험 기보에서 **수 일치율**(top-1)을 잰다.
지금은 사람 기보가 없어 기본 제공 AI 기보(data/library)로 메커니즘을 시연한다 —
온라인판 기보 수집(⑥)이 쌓이면 같은 코드가 사람 기보로 돈다. 신경망 없이 빈도표로
시연하며, 본구현에서 이 (상황→수) 데이터가 그대로 신경망 학습 데이터가 된다.

출력: <out>/방식2_모방_<시각>.md — 판단 종류별 일치율 표.
"""
import collections, glob, gzip, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from demo_common import attach_sim

A = attach_sim()


def decisions(path):
    d = json.load(gzip.open(path, 'rt', encoding='utf-8'))
    out = []
    for f in d['frames']:
        if isinstance(f, dict) and f.get('k') == 'decision' and isinstance(f.get('d'), dict):
            dd = f['d']
            q, pick = dd.get('q'), dd.get('pick')
            opts = [o[0] for o in (dd.get('opts') or [])]
            if q and pick and opts and pick in opts and len(opts) >= 2:
                out.append((q, tuple(sorted(opts)), pick))
    return out


files = sorted(glob.glob(os.path.join('..', 'data', 'library', 'lib*.json.gz')))
if not files: sys.exit('기보가 없습니다 (data/library)')
cut = max(1, int(len(files) * 0.7))
train_f, test_f = files[:cut], files[cut:]
train = [d for p in train_f for d in decisions(p)]
test = [d for p in test_f for d in decisions(p)]

# 모방 정책: (판단 종류, 후보 집합) → 최빈 선택. 못 보면 (판단 종류) → 후보 중 최빈 선택.
exact = collections.defaultdict(collections.Counter)
loose = collections.defaultdict(collections.Counter)
for q, opts, pick in train:
    exact[(q, opts)][pick] += 1
    loose[q][pick] += 1

hit = tot = 0
per = collections.defaultdict(lambda: [0, 0])
for q, opts, pick in test:
    if (q, opts) in exact:
        guess = exact[(q, opts)].most_common(1)[0][0]
    else:
        cand = [(n, c) for n, c in loose[q].most_common() if n in opts]
        guess = cand[0][0] if cand else opts[0]
    kind = q.split(':')[0].split('(')[0]
    per[kind][1] += 1; tot += 1
    if guess == pick:
        per[kind][0] += 1; hit += 1

lines = [f'# 방식2 「사람 로그 모방」 데모 — {time.strftime("%Y-%m-%d %H:%M")}', '',
         f'학습 기보 {len(train_f)}개({len(train)}판단) → 시험 기보 {len(test_f)}개({len(test)}판단)',
         f'**전체 수 일치율(top-1): {hit}/{tot} = {100 * hit / max(tot, 1):.1f}%**  (무작위 기준선보다 높으면 모방이 작동한다는 뜻)', '',
         '| 판단 종류 | 일치 | 표본 | 일치율 |', '|---|---|---|---|']
for kind, (h, n) in sorted(per.items(), key=lambda x: -x[1][1])[:14]:
    lines.append(f'| {kind} | {h} | {n} | {100 * h / n:.0f}% |')
lines += ['', '※ 지금은 AI 기보로 시연. 사람 기보가 쌓이면 같은 파이프라인이 「사람다움」 측정과',
          '   신경망(상황→사람의 수 예측) 학습 데이터 공급을 겸한다.']
out = os.path.join(A.out, f'방식2_모방_{time.strftime("%m%d_%H%M")}.md')
open(out, 'w', encoding='utf-8').write('\n'.join(lines))
print('저장:', out)
print(f'전체 일치율 {100 * hit / max(tot, 1):.1f}% ({hit}/{tot})')
