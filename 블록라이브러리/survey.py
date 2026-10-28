"""전수 조사: 카드 텍스트의 모든 효과 문장 ↔ 블록 대응 검사 · 사용 횟수 · 구현 대응 · 이름 참조 점검.
사용: python3 -I survey.py <실행 폴더(nny_sim)> <blocks.html> <out.json>"""
import sys, os, re, json, collections
RUN, BLOCKS_HTML, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ann import ANN, NEED_PARAM

# ── 블록 목록 (앞서 보낸 목록 PDF의 원본) ──
h = open(BLOCKS_HTML, encoding='utf-8').read()
CAT = {}
for bid, name, en in re.findall(r'<td class="id">([A-Z]\d\d)</td><td class="b">([^<]+)<span class="en">([a-z_]+)</span>', h):
    CAT[bid] = (name.strip(), en)
GROUP = {'F': '0 효과 틀', 'W': '1 발동 시점', 'C': '2 조건', 'V': '3 수량', 'K': '4 코스트', 'T': '5 대상 · 고르기',
         'D': '6 처리', 'P': '7 [지속]', 'R': '8 [제약] · 제약', 'J': '9 연결'}

# ── 카드 텍스트 → 효과 항목 ──
pool = json.load(open(os.path.join(RUN, 'card_pool.json'), encoding='utf-8'))
items = []          # (code, num, name, theme, text, subs)
for c in pool:
    cur = None
    for raw in c['text'].split('\n'):
        l = raw.strip()
        if not l: continue
        m = re.match(r'^(\d+)\.\s*', l)
        if m:
            cur = {'code': c['code'], 'num': m.group(1), 'name': c['name'], 'theme': c['theme'], 'type': c['type'] + ('/' + c['subtype'] if c.get('subtype') else ''),
                   'text': l, 'subs': []}
            items.append(cur)
        elif l.startswith('-') and cur is not None:
            cur['subs'].append(l)
        else:
            cur['text'] += ' ' + l if cur else ''
# 부여되는 하위 효과(세레모니 · 올인)는 따로 행으로
GRANTED = {('FGTR-007', '1'): ['1-a'], ('PKBS-016', '2'): ['2-a', '2-b']}
rows = []
for it in items:
    rows.append(dict(it, key=it['num'], granted=False))
    for i, k in enumerate(GRANTED.get((it['code'], it['num']), [])):
        rows.append(dict(it, key=k, text=it['subs'][i], subs=[], granted=True))

# ── 효과 틀 속성 자동 판정 (문장의 단서 문구) ──
def frame(text):
    f = []
    kw = re.search(r'\[([^\]]+)\]', text)
    f.append(('F01', kw.group(1) if kw else '표기 없음'))
    if re.search(r'패에서도 발동할 수 있다', text): f.append(('F02', '패에서도'))
    m = re.search(r'1턴에 (\d+)번까지', text)
    if m: f.append(('F03', f'{m.group(1)}번까지'))
    if re.search(r'계속해서 사용할 수 있다', text): f.append(('F03', '제한 없음(계속)'))
    if re.search(r'1턴에 1번 제약을 받지 않', text): f.append(('F03' if '[지속]' not in text else 'F04', '제약 받지 않음'))
    if '[지속]' in text and not re.search(r'1턴에 1번 제약을 받지 않|1턴에 \d+번까지|상대는 [^.]*수 없다|때마다', text): f.append(('F04', '1턴 1번(단서 없음)'))
    if re.search(r'다음 턴까지 자신은 이 효과를 사용할 수 없다', text): f.append(('F05', '다음 턴까지'))
    if re.search(r'강제로 발동한다', text): f.append(('F06', '강제'))
    if re.search(r'상대는 효과를 발동할 수 없다|상대는 체인할 수 없다', text): f.append(('F07', '체인 금지'))
    if re.search(r'무효화되지 않으며', text): f.append(('F08', '무효화 불가'))
    if re.search(r'종료 단계에서만 사용할 수 있다', text): f.append(('F09', '종료 단계에서만'))
    if re.search(r'뒷면 표시일 때만 발동', text): f.append(('F09', '뒷면일 때만'))
    if re.search(r'원래 주인인 플레이어만', text): f.append(('F10', '원래 주인만'))
    if re.search(r'동시에 발동할 수 없다', text): f.append(('F11', '동시 발동 금지'))
    if re.search(r'별도의 발동 처리를 필요로 하지 않|발동 선언을 필요로 하지 않', text): f.append(('F12', '부속'))
    return f

# ── 대응 검사 ──
errors, unknown = [], []
for r in rows:
    a = ANN.get(r['code'], {}).get(r['key'])
    if a is None: errors.append(f"대응 없음: {r['code']} #{r['key']} {r['name']}")
    r['blocks'] = a.split() if a else []
    r['frame'] = frame(r['text'] + ' ' + ' '.join(r['subs']))
    for b in r['blocks']:
        if b not in CAT and not b.startswith('F'): unknown.append((r['code'], r['key'], b))
for code, d in ANN.items():
    for k in d:
        if not any(r['code'] == code and r['key'] == k for r in rows): errors.append(f'텍스트에 없는 대응: {code} #{k}')

# ── 사용 횟수 ──
use = collections.defaultdict(list)
for r in rows:
    for b in dict.fromkeys(r['blocks']):     # 한 효과에서 같은 블록은 한 번
        if b.startswith('F'): continue
        use[b].append(f"{r['code']} #{r['key']}")
fuse = collections.defaultdict(list)
for r in rows:
    for fid, v in r['frame']:
        fuse[(fid, v)].append(f"{r['code']} #{r['key']}")
    for b in r['blocks']:
        if b.startswith('F'): fuse[(b, '(대응표)')].append(f"{r['code']} #{r['key']}")
num_effects = sum(1 for r in rows)
v01 = [f"{r['code']} #{r['key']}" for r in rows if re.search(r'\d', re.sub(r'^\d+\.\s*', '', r['text'] + ' '.join(r['subs'])))]
block_stats = []
for bid, (name, en) in CAT.items():
    if bid.startswith('F'): continue
    us = use.get(bid, [])
    cards = sorted({u.split(' #')[0] for u in us})
    block_stats.append({'id': bid, 'name': name, 'en': en, 'effects': len(us), 'cards': len(cards), 'uses': us,
                        'star': len(cards) == 1})
if 'V01' in CAT:
    for s in block_stats:
        if s['id'] == 'V01':
            s['uses'] = v01; s['effects'] = len(v01); s['cards'] = len({u.split(' #')[0] for u in v01}); s['star'] = False; s['auto'] = True

# ── 구현 대응 (지금 코드) ──
sys.path.insert(0, RUN); os.chdir(RUN)
from cards import Impl
from engine import Card
impl = {}
HOOKS = ('rules', 'atk_mod', 'def_mod', 'on_event', 'end_process', 'grave_redirect', 'state_check', 'extra_normal', 'grant', 'alt_normal', 'end_return')
for c in pool:
    x = Card(Impl.pool[c['name']], 0); Impl.attach(x)
    effs = [(e.num, e.kind) for e in x.effects]
    cont = sorted(set((getattr(x, 'cont_nums', None) or {}).values()))
    hooks = [h_ for h_ in HOOKS if getattr(x, h_, None)]
    flags = sorted(k for k in x.flags if k not in ('unimplemented',))
    impl[c['code']] = {'effs': effs, 'cont': cont, 'hooks': hooks, 'flags': flags, 'unimpl': bool(x.flags.get('unimplemented'))}
corr = []
for r in rows:
    if r['granted']: continue
    im = impl[r['code']]; n = int(r['num'])
    kinds = [k for num, k in im['effs'] if num == n]
    how = ('Effect(' + ','.join(kinds) + ')') if kinds else ('[지속] 훅 번호 있음' if n in im['cont'] else ('번호 없는 훅 · 플래그' if (im['hooks'] or im['flags']) else '구현 흔적 없음'))
    r['impl'] = how
    corr.append((r['code'], r['num'], how))
extra_nums = []
for c in pool:
    tn = {int(it['num']) for it in items if it['code'] == c['code']}
    for num, k in impl[c['code']]['effs']:
        if num and num not in tn: extra_nums.append((c['code'], c['name'], num, k))
impl_count = collections.Counter(r['impl'].split('(')[0] if r['impl'].startswith('Effect') else r['impl'] for r in rows if not r['granted'])

# ── 「」 이름 참조 점검 ──
names = {c['name'] for c in pool}
groups = {g for c in pool for g in (c.get('groups') or [])}
refs = collections.Counter()
for r in rows:
    for q in re.findall(r'「([^「」]+)」', r['text'] + ' '.join(r['subs'])):
        if len(q) > 24 or '.' in q or q.endswith('다'): continue   # 「…」로 인용한 효과 · 규칙 문장은 이름이 아님
        refs[q] += 1
ref_tab = []
for q, n in sorted(refs.items(), key=lambda x: -x[1]):
    if q in groups and q in names: kind = '카드군 · 카드명'
    elif q in groups: kind = '카드군'
    elif q in names: kind = '카드명'
    elif any(q in nm for nm in names): kind = '이름 일부(카드군 필드에는 없음)'
    else: kind = '없음 — 카드 풀에 그런 카드군 · 이름이 없음'
    holders = [c['name'] for c in pool if q in (c.get('groups') or [])] if kind.startswith('카드군') else ([nm for nm in names if q in nm] if kind.startswith('이름 일부') else [])
    ref_tab.append({'ref': q, 'count': n, 'kind': kind, 'holders': len(holders), 'ex': holders[:4]})

# ── 단서 문구(괄호) ──
paren = collections.Counter()
for r in rows:
    for q in re.findall(r'\(([^()]*)\)', r['text'] + ' '.join(r['subs'])): paren[q.strip()] += 1

# ── 키워드 없는 문장 ──
nokw = [{'code': r['code'], 'num': r['key'], 'name': r['name'], 'type': r['type'], 'text': r['text'], 'has_act': bool(re.search(r'발동', r['text'])), 'impl': r.get('impl', '')}
        for r in rows if not re.search(r'\[[^\]]+\]', r['text']) and not r['granted']]

# ── 테마별 ──
theme = collections.defaultdict(lambda: {'cards': set(), 'effects': 0, 'blocks': set()})
for r in rows:
    t = theme[r['theme']]; t['cards'].add(r['code']); t['effects'] += 1; t['blocks'].update(b for b in r['blocks'] if not b.startswith('F'))
theme_tab = [{'theme': k, 'cards': len(v['cards']), 'effects': v['effects'], 'blocks': len(v['blocks'])} for k, v in sorted(theme.items())]

# ── 재정 · 가정 근거 주석 (조립표 basis로 옮길 분량) ──
import inspect
from cards import IMPL
basis = {}
for c in pool:
    fn = IMPL.get(c['name'])
    src = inspect.getsource(fn) if fn else ''
    basis[c['code']] = {'user': len(re.findall(r'사용자 (답변|지시|재정)', src)), 'ruling': len(re.findall(r'재정|정본|룰지|설계도', src)), 'assume': len(re.findall(r'ASSUME', src))}
mods = {}
for f in sorted(os.listdir(RUN)):
    if re.match(r'cards\d*\.py$', f):
        doc = open(os.path.join(RUN, f), encoding='utf-8').read().split('"""')[1] if '"""' in open(os.path.join(RUN, f), encoding='utf-8').read() else ''
        mods[f] = {'lines': len(doc.splitlines()), 'assume': len(re.findall(r'ASSUME|^- ', doc, re.M)), 'user': len(re.findall(r'사용자 (답변|지시|재정)', doc))}
out = {'errors': errors, 'unknown': unknown, 'n_rows': num_effects, 'n_items': len(items), 'n_subs': sum(len(i['subs']) for i in items),
       'n_cards': len(pool), 'block_stats': block_stats, 'cat': CAT, 'groups': GROUP,
       'frame_use': [{'id': k[0], 'val': k[1], 'n': len(v), 'uses': v} for k, v in sorted(fuse.items())],
       'need_param': NEED_PARAM, 'rows': [{k: r[k] for k in ('code', 'key', 'name', 'theme', 'type', 'text', 'subs', 'blocks', 'frame', 'granted')} | {'impl': r.get('impl', '')} for r in rows],
       'impl_count': dict(impl_count), 'extra_nums': extra_nums, 'refs': ref_tab, 'paren': paren.most_common(), 'nokw': nokw, 'themes': theme_tab, 'basis': basis, 'mods': mods}
json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('rows', num_effects, 'items', len(items), 'subs', out['n_subs'], 'errors', len(errors), 'unknown', unknown[:10])
for e in errors[:20]: print(' ', e)
z = [s['id'] for s in block_stats if s['effects'] == 0]
print('unused', z); print('stars', sum(s['star'] for s in block_stats), [s['id'] for s in block_stats if s['star']])
print('impl', dict(impl_count)); print('extra code nums', extra_nums)
print('refs unknown', [r for r in ref_tab if r['kind'].startswith('없음') or r['kind'].startswith('이름 일부')])
