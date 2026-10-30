"""학습표(policy) 대전별 분할 · 불러오기 · 사람 대전 학습 기록.

학습표의 키는 모두 「내 덱 vs 상대 덱|판단|후보…」(L1 · L2)와 「내 덱 vs *|…」(L0, 상대를 합친 단계)이다.
덱 A와 B의 대전에서 AI가 찾는 키는 「A vs B|」 · 「B vs A|」 · 「A vs *|」 · 「B vs *|」뿐이므로,
전체 표(키 700만 개, 메모리 약 4GB)를 덱 쌍별 파일로 나눠 두고 그 대전 몫만 불러온다 — 판단은 전체 표와 같다(check_same).

사람 대전 학습: 대전 표(MatchupTable)의 update 를 모두 기록해 두었다가 매치가 끝나면 learning 기록(jsonl, 한 줄 = 한 매치)에 덧붙인다.
불러올 때 기록을 다시 적용하므로, 프로그램 안에서는 학습이 그 자리에서 반영된다. 기록 파일은 저장소의 표에 합칠 수 있다(merge_learning.py).
"""
import gzip, json, os, time, uuid

SPLIT_FORMAT = 1
LOG_FORMAT = 1


def key_owner(k):
    """키 → (내 덱, 상대 덱 또는 '*'). 형식이 다르면 None"""
    i = k.find(' vs ')
    j = k.find('|', i + 4) if i >= 0 else -1
    if i < 0 or j < 0: return None
    return k[:i], k[i + 4:j]


def _write(path, obj):
    with gzip.open(path, 'wt', encoding='utf-8', compresslevel=9) as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))


def _read(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def split(policy_path, out_dir, read=None):
    """전체 표 → out_dir/manifest.json + pair_<i>_<j>.json.gz(L1 · L2) + l0_<i>.json.gz(L0). 덱 이름은 manifest 의 번호로"""
    import hashlib
    if read is None:
        from policy import Table
        read = Table.read
    d = read(policy_path)
    decks = set(); pairs = {}; l0 = {}
    for L in ('L1', 'L2'):
        for k, v in d.get(L, {}).items():
            o = key_owner(k)
            if o is None or o[1] == '*': continue
            decks.update(o); pairs.setdefault(o, {'L1': {}, 'L2': {}})[L][k] = v
    for k, v in d.get('L0', {}).items():
        o = key_owner(k)
        if o is None: continue
        decks.add(o[0]); l0.setdefault(o[0], {})[k] = v
    decks = sorted(decks); ix = {n: i for i, n in enumerate(decks)}
    os.makedirs(out_dir, exist_ok=True)
    for (a, b), t in pairs.items(): _write(os.path.join(out_dir, f'pair_{ix[a]}_{ix[b]}.json.gz'), t)
    for a, t in l0.items(): _write(os.path.join(out_dir, f'l0_{ix[a]}.json.gz'), {'L0': t})
    h = hashlib.sha256()
    with open(policy_path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    man = {'format': SPLIT_FORMAT, 'decks': decks, 'games': d.get('games', 0), 'source': os.path.basename(policy_path),
           'source_sha256': h.hexdigest(), 'keys': {L: len(d.get(L, {})) for L in ('L0', 'L1', 'L2')}}
    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    return man


def matchup_table(split_dir, decks, logs=()):
    """대전에 나오는 덱(스킬 이름)들의 몫만 담은 학습표. logs: 사람 대전 학습 기록 파일들 — 그 덱이 「내 덱」인 갱신을 다시 적용"""
    from policy import Table

    class MatchupTable(Table):
        """policy.Table 과 같은 값 계산(value) · 갱신(update). 갱신을 deltas 에 남긴다"""
        def __init__(self):   # Table.__init__ 은 learned/policy.json 을 읽으므로 부르지 않는다
            self.path = None; self.source = split_dir; self.L0 = {}; self.L1 = {}; self.L2 = {}; self.games = 0
            self.deltas = []; self.recording = True

        def update(self, k1, k2, won):
            Table.update(self, k1, k2, won)
            if self.recording: self.deltas.append([k1, k2, won])

    t = MatchupTable()
    try:
        with open(os.path.join(split_dir, 'manifest.json'), encoding='utf-8') as f: man = json.load(f)
    except FileNotFoundError:   # 아직 나눠 둔 학습표가 없음(새 설치 · 온라인판 첫 가동) — 전부 휴리스틱 기본값으로
        man = {'decks': []}
    ix = {n: i for i, n in enumerate(man['decks'])}
    want = sorted(set(decks))
    for a in want:
        if a not in ix: continue
        p = os.path.join(split_dir, f'l0_{ix[a]}.json.gz')
        if os.path.exists(p): t.L0.update(_read(p)['L0'])
        for b in want:
            p = os.path.join(split_dir, f'pair_{ix[a]}_{ix.get(b, -1)}.json.gz')
            if os.path.exists(p):
                x = _read(p); t.L1.update(x['L1']); t.L2.update(x['L2'])
    t.recording = False   # 기록 다시 적용은 새 갱신이 아니다
    applied = 0
    for path in logs:
        for rec in read_log(path):
            for k1, k2, won in rec.get('updates', ()):
                o = key_owner(k1)
                if o and o[0] in want: t.update(k1, k2, won); applied += 1
    t.recording = True; t.applied = applied
    return t


# ── 사람 대전 학습 기록 (jsonl, 한 줄 = 한 매치) ──
def read_log(path):
    if not os.path.exists(path): return []
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except ValueError: pass   # 쓰다 끊긴 줄은 건너뛴다
    return out


def append_log(path, meta, updates):
    """매치 1개의 학습 기록을 덧붙인다(원자적으로: 한 줄을 한 번에 쓴다)"""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    rec = dict(meta, v=LOG_FORMAT, id=uuid.uuid4().hex, time=time.strftime('%Y-%m-%dT%H:%M:%S'), updates=updates)   # id: 저장소에 합칠 때 중복 방지
    line = json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line); f.flush(); os.fsync(f.fileno())
    return rec


def log_stats(path):
    recs = read_log(path)
    by = {}
    for r in recs:
        k = ' vs '.join(r.get('decks', ['?', '?'])); s = by.setdefault(k, {'matches': 0, 'wins': 0, 'updates': 0})
        s['matches'] += 1; s['wins'] += int(r.get('human_won') is True); s['updates'] += len(r.get('updates', ()))
    return {'matches': len(recs), 'updates': sum(len(r.get('updates', ())) for r in recs), 'by_matchup': by,
            'size': os.path.getsize(path) if os.path.exists(path) else 0}
