"""라운드 사이 사람의 스킬 교체 시험(화면 없이): 전략 덱의 스킬 카드로 바꾸면 새 스킬 태그에 맞지 않는 메인 · 상급 카드를 표시하고,
그 카드를 모두 전략 덱으로 보내기 전에는 「교체 끝」을 받지 않는다.
python3 side_skill_test.py <sim>"""
import os, sys
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sim = os.path.abspath(sys.argv[1]); sys.path[:0] = [sim, os.path.join(os.path.dirname(APP), 'viewer'), APP]; os.chdir(sim)
import deck as D, match as M, season as SE
from cards import POOL
import session as SS

decks = SE.load_decks(); base = decks['투기장의 규칙']; me = base['스킬']
# 시험 덱: 두 스킬에 모두 맞는 메인 카드(공용 등)로 채우고, 지금 스킬에만 맞는 카드 2종 · 전략 덱에 다른 스킬 카드 + 그 스킬에만 맞는 카드 2종
s2 = next(n for n, c in sorted(POOL.items()) if c['type'] == '스킬' and n != me)
mains = lambda f: [n for n, c in sorted(POOL.items()) if c['type'] != '스킬' and c.get('deck') == '메인' and 1 <= (c.get('level') or 1) <= 10 and f(n)]
both = mains(lambda n: M.fits(n, me) and M.fits(n, s2)); only_me = mains(lambda n: M.fits(n, me) and not M.fits(n, s2))[:2]
fit2 = mains(lambda n: M.fits(n, s2) and not M.fits(n, me))[:2]
main = [[3, n] for n in only_me] + [[3, n] for n in both[:6]]
deck = {'이름': '시험', '스킬': me, '메인': main, '상급': [], '전략': [[1, s2]] + [[3, n] for n in fit2]}
act = M.counts_of(deck)
errs, _ = D.validate(deck, policy=False)
print('deck valid (전략 덱에 다른 스킬 태그 카드):', not errs, errs[:3])
mis_main = [n for n, k in act.items() if not M.fits(n, s2)]
print('스킬', me, '→', s2, '| 새 스킬에 안 맞는 활성 카드', mis_main, '· 전략 덱 후보', fit2)


class Bot:
    """화면 대역: 스킬 교체 → 「교체 끝」 시도(거절 확인) → 안 맞는 카드를 빼는 교체 → 「교체 끝」"""
    def __init__(self): self.step = 0; self.log = []; self.pending = None

    def ask(self, req):
        o = req['opts']; self.step += 1
        kinds = [x['kind'] for x in o]
        if self.step == 1:
            return next(i for i, x in enumerate(o) if x['kind'] == 'skill' and x['in'] == s2)
        if self.step == 2:
            self.log.append(('after skill swap misfit', len(req['misfit']))); return 0   # 「교체 끝」 — 거절돼야 함
        if self.step == 3:
            self.log.append(('error shown', bool(req['error']) and '전략 덱으로 보내야' in req['error']))
        if req['misfit']:
            i = next((i for i, x in enumerate(o) if x['kind'] == 'card' and x.get('misfit')), None)
            if i is None: self.log.append(('stuck', req['misfit'])); return kinds.index('reset') if 'reset' in kinds else 0
            return i
        self.log.append(('misfit cleared at step', self.step)); return 0


bot = Bot(); log = []
d = SS.human_side(bot, [dict(deck), dict(decks['세제'])], 0, [0, 1], 2, log)
for x in bot.log: print(' ', x)
print('최종 스킬', d['스킬'], '| 메인 · 상급 전부 새 스킬 태그:', all(M.fits(n, d['스킬']) for n, k in M.counts_of(d).items() if k > 0),
      '| 덱 규칙 오류', D.validate(d, policy=False)[0][:2])
print('기록:', log[-1]['m'][:160])
ok = d['스킬'] == s2 and all(M.fits(n, s2) for n in M.counts_of(d)) and not D.validate(d, policy=False)[0] and ('error shown', True) in bot.log
print('결과:', '통과' if ok else '실패'); sys.exit(0 if ok else 1)
