"""대국 연결: 매치(match.play_match)에서 자리별로 DRL 정책 또는 학습표 정책을 쓰게 하는 도우미.

  make_ai, side_fn = players(dA, dB, 'learned/drl/run1/model_best.npz', None)   # A = DRL, B = 학습표
  M.play_match(dA, dB, first, rng, log, make_ai, side_fn=side_fn)
자리 구분은 덱 이름으로 한다(같은 덱끼리의 대전이면 둘 다 같은 정책이어야 한다).
"""
import match as M
import policy as P
from .agent import DRLAI
from .model import load_actor
from .side import drl_side_swap


def players(dA, dB, model_a=None, model_b=None, learn=False):
    """model_a · model_b: DRL 모델 경로 또는 None(학습표 LearnedAI). 반환: (make_ai, side_fn)"""
    actors = [load_actor(m)[0] if m else None for m in (model_a, model_b)]
    names = [dA['이름'], dB['이름']]
    if names[0] == names[1] and (model_a or None) != (model_b or None):
        raise ValueError('같은 이름의 덱끼리는 자리를 구분할 수 없음 — 두 자리 모두 같은 정책을 쓰거나 덱 이름을 바꿀 것')

    def seat(deck):
        return names.index(deck['이름'])

    def make_ai(deck):
        a = actors[seat(deck)]
        return DRLAI(deck['스킬'], actor=a, mode='greedy') if a is not None else P.LearnedAI(deck['스킬'], learn=learn)

    def side_fn(i, decks, wins, rounds, rng, side_eps, log):
        a = actors[seat(decks[i])]
        if a is None:
            return M.side_swap(decks[i], decks[1 - i]['스킬'], rng, side_eps, log, decks[i]['이름'])
        ctx = dict(round=len(rounds), wins_me=wins[i], wins_op=wins[1 - i], lost_last=rounds[-1]['winner'] != i)
        return drl_side_swap(decks[i], decks[1 - i], ctx, a, mode='greedy', log=log, pname=decks[i]['이름'])

    return make_ai, side_fn
