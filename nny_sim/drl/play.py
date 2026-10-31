"""대국 연결: 매치(match.play_match)에서 자리별로 DRL 정책 또는 학습표 정책을 쓰게 하는 도우미.

  make_ai, side_fn = players('learned/drl/run1/model_best.npz', None)   # 자리 0 = DRL, 자리 1 = 학습표
  M.play_match(dA, dB, first, rng, log, make_ai, side_fn=side_fn, learn_side=False)
자리는 play_match가 덱에 붙이는 deck['_seat']로 구분한다(같은 덱끼리의 대전도 된다).
"""
import os
import match as M
import policy as P
from .agent import DRLAI
from .model import load_actor
from .side import drl_side_swap

_CACHE = {}


def cached_actor(path):
    """모델 파일 → NumpyActor. 같은 파일(경로 · 수정 시각)은 한 번만 읽는다"""
    key = (os.path.abspath(path), os.path.getmtime(path))
    if key not in _CACHE:
        _CACHE[key] = load_actor(path)[0]
    return _CACHE[key]


def players(model_a=None, model_b=None, learn=False):
    """model_a · model_b: 자리 0 · 1의 DRL 모델 경로 또는 None(학습표 LearnedAI). 반환: (make_ai, side_fn)"""
    actors = [cached_actor(m) if m else None for m in (model_a, model_b)]

    def make_ai(deck):
        a = actors[deck['_seat']]
        return DRLAI(deck['스킬'], actor=a, mode='greedy') if a is not None else P.LearnedAI(deck['스킬'], learn=learn)

    def side_fn(i, decks, wins, rounds, rng, side_eps, log):
        a = actors[i]
        if a is None:
            return M.side_swap(decks[i], decks[1 - i]['스킬'], rng, side_eps, log, decks[i]['이름'])
        ctx = dict(round=len(rounds), wins_me=wins[i], wins_op=wins[1 - i], lost_last=rounds[-1]['winner'] != i)
        return drl_side_swap(decks[i], decks[1 - i], ctx, a, mode='greedy', log=log, pname=decks[i]['이름'])

    return make_ai, side_fn
