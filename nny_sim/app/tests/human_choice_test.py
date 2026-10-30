"""사람 자리가 직접 고르는 선택 시험(화면 없이, 사용자 지시 2026-10-29 「사람은 자신이 할 모든 행동을 자신이 고를 수 있게」):
일반소환 제물 · 포커짐승들 족보 재료 · 「원하는 레벨과 원하는 속성」 부여 · 짐승조커 선언 · 번식지 카드.
python3 human_choice_test.py <sim>"""
import os, sys, random
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sim = os.path.abspath(sys.argv[1]); sys.path[:0] = [sim, os.path.join(os.path.dirname(APP), 'viewer'), APP]; os.chdir(sim)
import policy as P
import human as H
from cards import Impl
from engine import Game, Card
import season as SE
import cards8
import blocks.lib as L

H.install_block_hooks()
DECKS = SE.load_decks()


class Script:
    """화면 대역: 묻는 순서대로 정해 둔 답(후보 이름표에 들어 있는 글자 또는 번호)을 고른다"""
    def __init__(self, answers): self.answers = list(answers); self.asked = []   # asked: (질문, 후보 이름표들)

    def ask(self, req):
        labs = [o['label'] for o in req['opts']]; self.asked.append((req['decision'], labs))
        if not self.answers: return 0   # 정해 둔 답이 없는 질문(우선권 · 대응 등)은 첫 후보(패스 · 안 함)
        a = self.answers.pop(0)
        if isinstance(a, int): return a
        hit = [i for i, l in enumerate(labs) if a in l]
        if not hit: raise AssertionError(f'답 「{a}」이(가) 후보에 없음 — 질문 {req["decision"]} · 후보 {labs}')
        return hit[0]


def game(deck_a, deck_b, answers):
    bot = Script(answers)
    hu = H.HumanAI(DECKS[deck_a]['스킬'], bot, P.Table('none'), learn=False)
    from ai import HeuristicAI
    g = Game([dict(DECKS[deck_a], 이름='나'), dict(DECKS[deck_b], 이름='AI')], [hu, HeuristicAI(DECKS[deck_b]['스킬'])], 0, random.Random(3), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'; g.events = []
    return g, hu, bot


def put(g, name, owner, zone, slot=None):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone; c.controller = owner
    if zone in ('hand', 'grave', 'main', 'upper'): getattr(g.p[owner], zone).append(c)
    if zone == 'm': g.p[owner].m[slot] = c; c.faceup = True
    return c


ok = True


def check(name, cond, extra=''):
    global ok
    ok = ok and bool(cond); print(('통과 ' if cond else '실패 ') + name, extra)


# ① 일반소환 제물 — AI가 미리 고른 제물(가치가 낮은 쪽) 대신 사람이 고른 몬스터를 릴리스
g, hu, bot = game('투기장의 규칙', '세제', [])
mons = [n for n, d in sorted(Impl.pool.items()) if d['type'] == '몬스터' and int(d.get('level') or 0) in (5, 6)
        and not any(k in d.get('text', '') for k in ('[제약]', '특수소환할 수 없'))]
big = put(g, mons[0], 0, 'hand')
low = [n for n, d in sorted(Impl.pool.items()) if d['type'] == '몬스터' and 1 <= int(d.get('level') or 0) <= 4 and d.get('deck') == '메인']
a = put(g, low[0], 0, 'm', 0); b = put(g, low[1], 0, 'm', 1)
pre = hu.pick_tributes(g, 0, big)
want = b if pre[0] is a else a
n0 = len(bot.asked); bot.answers = [f'몬스터 존 {g.p[0].m.index(want) + 1}: {want.name}', 0, 0]   # 제물 · 놓을 존 · 표시 형식
hu.do_extra(g, 0, ('summon', big, pre, None))
check('제물: 사람이 고른 몬스터를 릴리스', want.zone == 'grave' and (pre[0].zone == 'm') and g.on_field(big),
      f'(AI 제물 {pre[0].name} · 고른 것 {want.name} · 질문 {bot.asked[n0][0]})')

# ② 포커짐승들 족보 재료 — 지금 낼 수 있는 조합 중에서 고른다
g, hu, bot = game('올인', '세제', [])
up = put(g, cards8.RABBIT_UP, 0, 'upper')
RAB, WOLF_F, WOLF, DOG = '♠ 스트레이트를 부르는 토끼', '◆ 메이드에 실패한 늑대', '◆ 플러쉬를 노리는 늑대', '♥ 풀 하우스를 찾는 강아지'
r = put(g, RAB, 0, 'm', 0); wf = put(g, WOLF_F, 0, 'm', 1); w = put(g, WOLF, 0, 'm', 2); d = put(g, DOG, 0, 'hand')
opts = cards8.plan_options(g, r, 0, 'straight')
labs = [' + '.join(H.card_label(g, 0, m.card) for m in sel) for _, sel in opts]
pick = next(i for i, (_, sel) in enumerate(opts) if w in [m.card for m in sel])   # AI 최선(실패한 늑대)이 아닌 쪽
n0 = len(bot.asked); bot.answers = [pick]
e = next(x for x in r.effects if getattr(x, 'pk_kind', None) == 'straight')
link = g.activate(0, r, e)
check('족보 재료: 고른 조합을 릴리스', link is not None and w.zone == 'grave' and wf.zone == 'm' and d.zone == 'grave',
      f'(후보 {len(opts)}개 · 질문 {bot.asked[n0][0]} · {bot.asked[n0][1]})')

# ③ 부여 · ④ 선언 — 레벨 · 속성을 차례로
g, hu, bot = game('올인', '세제', [])
n0 = len(bot.asked); bot.answers = ['레벨 7', '하트', '레벨 3', '클로버']   # 시작 패 · 멀리건 질문이 끝난 뒤
t = put(g, DOG, 0, 'm', 0)
check('부여: 레벨 · 속성', L.grant_pick(g, 0, t) == (7, '하트'), str([q for q, _ in bot.asked[n0:n0 + 2]]))
jk = put(g, '짐승조커', 0, 'm', 1)
check('선언: 레벨 · 속성', L.joker_pick(g, 0, jk) == (3, '클로버'), str([q for q, _ in bot.asked[n0 + 2:n0 + 4]]))

# ⑤ 번식지 — 패에 넣을 카드를 직접
g, hu, bot = game('번성충-대발생', '세제', [])
cands = [put(g, n, 0, 'main') for n in ('번성충-노린재', '번성충-메뚜기여왕', '번성충-주기매미')]
n0 = len(bot.asked); bot.answers = ['번성충-주기매미']
x = hu.breeding_pick(g, 0, cands)
check('번식지: 고른 카드', x.name == '번성충-주기매미', str(bot.asked[n0:]))

# ⑥ 공격 — 상대 필드에 같은 이름 몬스터가 여러 장이면 어느 카드를 공격할지 고른다(사용자 지시 2026-10-30)
g, hu, bot = game('투기장의 규칙', '세제', [])
weak = sorted((n for n, d in Impl.pool.items() if d['type'] == '몬스터' and 1 <= int(d.get('level') or 0) <= 4), key=lambda n: int(Impl.pool[n].get('atk') or 0))[0]
strong = max((n for n, d in Impl.pool.items() if d['type'] == '몬스터' and int(d.get('level') or 0) <= 4), key=lambda n: int(Impl.pool[n].get('atk') or 0))
att = put(g, strong, 0, 'm', 0); att.summon_turn = 1; att.pos = 'atk'
t1 = put(g, weak, 1, 'm', 0); t2 = put(g, weak, 1, 'm', 2)
for t in (t1, t2): t.pos = 'atk'; t.summon_turn = 1
g.phase = '전투'
labs_seen = {}   # 첫 「공격」 질문의 후보 — 상대 몬스터 존 3 쪽을 고른다(뒤 질문은 「공격 종료」)

class Pick(Script):
    def ask(self, req):
        if req['decision'] == '공격' and not labs_seen:
            labs_seen['opts'] = req['opts']
            return next(i for i, o in enumerate(req['opts']) if '상대 몬스터 존 3' in o.get('sub', ''))
        return 0
hu.bridge = Pick([])
hu.battle_phase(g, 0)
subs = [o.get('sub', '') for o in labs_seen.get('opts', [])]
check('공격: 같은 이름 대상이 따로 나온다', sum(1 for x in subs if '상대 몬스터 존' in x) == 2, str(subs))   # 빛낼 카드(u)는 기록기가 있는 실제 대전에서만
check('공격: 고른 칸의 카드를 공격', t2.zone == 'grave' and t1.zone == 'm', f'({weak} 존1 {t1.zone} · 존3 {t2.zone})')

# ⑦ 행동 — 자신 필드의 같은 이름 몬스터는 표시 형식 변경 후보도 따로
g, hu, bot = game('투기장의 규칙', '세제', [])
a1 = put(g, weak, 0, 'm', 0); a2 = put(g, weak, 0, 'm', 1)
for a in (a1, a2): a.pos = 'atk'; a.summon_turn = 1
seen = {}

class First(Script):
    def ask(self, req):
        if req['decision'].endswith('행동') and not seen: seen['opts'] = req['opts']
        return 0
hu.bridge = First([])
hu.main_phase(g, 0, '정비')
pos = [o for o in seen.get('opts', []) if o['label'].startswith('수비 표시로:')]
check('행동: 같은 이름 몬스터의 표시 형식 변경이 따로 나온다', len(pos) == 2 and pos[0].get('sub') != pos[1].get('sub'), str([(o['label'], o.get('sub')) for o in pos]))

print('결과:', '통과' if ok else '실패'); sys.exit(0 if ok else 1)
