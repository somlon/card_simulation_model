"""새 형식 카드 자료(.md, 2026-10-08~) → card_pool.json.

형식: 앞머리(--- theme/code ---) + 카드마다 `### CODE: 이름`, `- **항목**: 값` 목록,
`**효과**:` 번호 목록, `**플레이버**`, `**재정 (Rulings)**:` 목록.
사용법: python parse_pool_md.py <md 파일 ...> [--out card_pool.json]
"""
import json, re, sys

THEME = {'공용카드': '공용', '소원의 분수': '소원의분수'}


def _split(s):
    return [x.strip() for x in s.split(',') if x.strip()]


def parse_file(path):
    txt = open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n', txt, re.S)
    meta = dict(l.split(':', 1) for l in m.group(1).split('\n') if ':' in l)
    theme = meta['theme'].strip(); theme = THEME.get(theme, theme)
    cards = []
    for blk in re.split(r'\n### ', txt)[1:]:
        head, body = blk.split('\n', 1)
        code, name = [x.strip() for x in head.split(':', 1)]
        f = dict(re.findall(r'^- \*\*(.+?)\*\*: (.*)$', body, re.M))
        eff = re.search(r'\*\*효과\*\*:\n(.*?)(?=\n\*\*|\n---|\Z)', body, re.S)
        eff = '\n'.join(l.strip() for l in eff.group(1).split('\n') if l.strip()) if eff else ''
        rul = re.search(r'\*\*재정 \(Rulings\)\*\*:\n(.*?)(?=\n\*\*|\n---|\Z)', body, re.S)
        rul = [l.strip()[2:].strip() for l in rul.group(1).split('\n') if l.strip().startswith('-')] if rul else []
        kind = f['카드 종류']
        c = {'theme': theme, 'code': code, 'name': name, 'color': f.get('색'), 'text': eff}
        if kind.startswith('몬스터'):
            c.update(type='몬스터', level=int(f['레벨']), race=f.get('종족'), attr=f.get('속성'),
                     atk=f.get('공격력'), deck='상급' if '상급' in kind else '메인')
            c['def'] = f.get('수비력')
        elif kind.startswith('스킬'):
            c.update(type='스킬', deck='스킬')
        elif kind.startswith('필드'):
            c.update(type='필드', deck='메인')
        else:
            c.update(type='마법', deck='메인', subtype=f.get('마법 분류', ''))
        c['tags'] = _split(f.get('태그', theme))
        if f.get('카드군'): c['groups'] = _split(f['카드군'])
        if c['type'] == '스킬':
            # 덱 구성 허용 태그 = 스킬 카드의 「태그」(대응 카드군 ⊆ 태그).
            # 소원의 분수는 대응 카드군에 없는 「소원의 분수」 태그 카드(기적의 영웅 등)도 쓰므로 태그 쪽을 쓴다.
            c['skill_tags'] = c['tags']
            if f.get('대응 카드군'): c['skill_groups'] = _split(f['대응 카드군'])
        if rul: c['rulings'] = rul
        cards.append(c)
    assert len(cards) == int(meta['total_cards']), (path, len(cards), meta['total_cards'])
    return cards


if __name__ == '__main__':
    args = sys.argv[1:]; out = 'card_pool.json'
    if '--out' in args:
        i = args.index('--out'); out = args[i + 1]; del args[i:i + 2]
    pool = [c for p in args for c in parse_file(p)]
    names = [c['name'] for c in pool]
    assert len(names) == len(set(names)), '이름 중복'
    json.dump(pool, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    from collections import Counter
    print(len(pool), dict(Counter((c['theme'], c['type']) for c in pool)))
