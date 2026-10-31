"""효과 문장 · 문장 틀 (blocks/README.md).

- 효과 문장: 카드 텍스트의 「n. …」 줄(바로 아래의 「- …」 하위 항목 포함). 「- [키워드] …」 항목은 부여 효과로 따로 둔다(키 「n-a」 · 「n-b」 …).
- 문장 틀: 문장에서 수치 자리를 {이름}으로 비운 글. 틀과 문장을 맞춰 수치를 읽는다 — 틀이 맞지 않으면(문장이 바뀌었으면) None.
- 효과 틀 속성(F): 키워드와 단서 괄호(「(이 효과는 …)」)에서 읽는다.
"""
import re

_NUM_LINE = re.compile(r'^(\d+)\.\s*')
_SPACES = re.compile(r'\s+')


def norm(s):
    """공백 정리 — 줄바꿈은 남기고 줄마다 앞뒤 공백 · 겹친 공백을 하나로"""
    return '\n'.join(_SPACES.sub(' ', l).strip() for l in (s or '').split('\n') if l.strip())


def sentences(d):
    """카드 자료 d → {키: 효과 문장(번호 뗀 것)}. 키는 '1' · '2' …, 부여 효과는 '1-a' · '2-b' …"""
    out, cur, sub = {}, None, 0
    for raw in (d.get('text') or '').split('\n'):
        l = raw.strip()
        if not l: continue
        m = _NUM_LINE.match(l)
        if m:
            cur = m.group(1); sub = 0; out[cur] = l[m.end():]
        elif l.startswith('-') and cur is not None:
            body = l[1:].strip()
            if body.startswith('['):                       # 부여 효과 「- [신속] …」
                out[f'{cur}-{chr(ord("a") + sub)}'] = body; sub += 1
            else:                                          # 하위 항목(주사위 눈 · 고르는 효과 …)은 그 번호 문장에 붙인다
                out[cur] += '\n- ' + body
        elif cur is not None:
            out[cur] += ' ' + l
    return {k: norm(v) for k, v in out.items()}


# ── 문장 틀 ──
_HOLE = re.compile(r'\{([a-z_][a-z0-9_]*)\}')
_COMPILED = {}


def compile_template(t):
    """틀 → (정규식, 구멍 이름 목록). 같은 이름이 두 번 나오면 같은 수여야 한다"""
    r = _COMPILED.get(t)
    if r is None:
        t = norm(t); parts, names, pos = [], [], 0
        for m in _HOLE.finditer(t):
            parts.append(re.escape(t[pos:m.start()]))
            n = m.group(1)
            parts.append(f'(?P={n})' if n in names else rf'(?P<{n}>\d+)')
            if n not in names: names.append(n)
            pos = m.end()
        parts.append(re.escape(t[pos:]))
        r = _COMPILED[t] = (re.compile('^' + ''.join(parts) + '$'), tuple(names))
    return r


def match(template, text):
    """문장 text가 틀에 맞으면 {구멍: 정수}, 아니면 None"""
    rx, names = compile_template(template)
    m = rx.match(norm(text))
    return None if m is None else {n: int(m.group(n)) for n in names}


# ── 키워드 · 단서 괄호 → 효과 틀 속성 ──
KEYWORDS = ('신속', '트리거', '지속', '유언', '소환', '전투', '제약')


def keyword(text):
    """문장 앞머리의 [키워드] (없으면 '')"""
    m = re.match(r'^\[([^\]]+)\]', text or '')
    return m.group(1) if m else ''


_NOTE_RULES = (
    # (단서 정규식, 속성, 값) — 값이 함수면 일치 결과로 계산
    (r'1턴에 1번 제약을 받지 않', 'opt', None),
    (r'계속해서 사용할 수 있다', 'opt', None),
    (r'1턴에 (\d+)번까지 사용할 수 있다', 'opt', lambda m: int(m.group(1))),
    (r'강제로 발동한다', 'mandatory', True),
    (r'(이 카드의 발동|이 효과)에 대하여,? 상대는 효과를 발동할 수 없다', 'no_resp', True),
    (r'이 카드는 무효화되지 않', 'unnegatable', True),
    (r'패에서도 발동할 수 있다', 'hand_ok', True),
    (r'뒷면 표시일 때만 발동할 수 있다', 'facedown_ok', True),
    (r'종료 단계에서만 사용할 수 있다', 'phase_only', '종료'),
    (r'사용 후, 다음 턴까지 자신은 이 효과를 사용할 수 없다', 'cooldown', True),
    (r'(별도의 발동 처리|발동 선언)를 필요로 하지 않는다', 'auto', True),
    (r'필드에서 묘지로 보내졌을 경우,? 발동하지 않는다', 'not_from_field', True),
    (r'덱에서 묘지로 보내졌을 경우 이 효과는 발동하지 않는다', 'not_from_deck', True),
    (r'자신의 효과를 발동하기 위해 묘지로 보내졌을 경우,? 이 효과는 발동하지 않는다', 'not_cost', True),
)


def notes(text):
    """문장의 단서 괄호에서 읽은 효과 틀 속성 {속성: 값}"""
    out = {}
    for body in re.findall(r'\(([^()]*)\)', text or ''):
        for rx, key, val in _NOTE_RULES:
            m = re.search(rx, body)
            if m: out[key] = val(m) if callable(val) else val
    return out
