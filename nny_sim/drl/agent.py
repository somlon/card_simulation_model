"""DRLAI — LearnedAI의 공통 선택기 choose()만 신경망으로 바꾼 판단 AI, 그리고 학습용 표본 기록기.

LearnedAI의 나머지(하드 제약, 후보 생성, 휴리스틱 점수)는 그대로 쓴다 → 학습 요소 · 지침이 학습표 버전과 같다.
탐색 AI의 재현 게임(g.script)에서는 LearnedAI.choose로 넘겨 기존 재현 · 결정화 절차를 그대로 따른다.
모든 판단은 g.dlog에 (플레이어, 후보 번호)로 남는다(탐색 AI 재현 호환).

mode
  greedy   가장 높은 점수의 후보 (평가 · 실전 기본값)
  sample   확률 표본 추출 (학습용 자기 대국)
  teacher  학습표(teacher Table)로 LearnedAI와 똑같이 고르고, 신경망 입력과 교사 분포를 기록 (모방 학습 자료)
"""
import itertools, math
import numpy as np
from policy import LearnedAI, prior_of
from . import features as F
from . import schema as S

_GID = itertools.count(1)


def softmax(x):
    z = np.exp(x - x.max()); return z / z.sum()


class Recorder:
    """매치 단위로 표본을 모았다가, 결과가 나면 보상을 붙여 확정한다(중단 · 오류 매치는 버린다).
    표본 = [종류('game'|'side'), 자리, 게임 번호, 내용, 보상, 매치 번호]
      game 내용: (obs, oracle, cands, idx, logp, 교사 분포 또는 None, 판단 종류 번호)
      side 내용: (obs, oracle, cands, idx, logp, 교사 분포 또는 None)"""

    PACK_EVERY = 20000   # 확정 표본이 이만큼 쌓이면 열 단위 배열로 묶어 메모리를 줄인다(buffer.pack)

    def __init__(self, worker=0):
        self.samples = []; self._pending = []; self.matches = 0; self.worker = worker; self._packs = {'game': [], 'side': []}

    def begin_match(self):
        self._pending = []

    def add(self, kind, seat, gid, content):
        if kind == 'side':
            gid = ('side', self.matches)   # 전략 덱 교체 궤적 = 매치 하나 · 자리 하나
        self._pending.append([kind, seat, gid, content, None, self.matches])

    def end_game(self, gid, seat, reward):
        for e in self._pending:
            if e[0] == 'game' and e[2] == gid and e[1] == seat:
                e[4] = reward

    def end_match(self, winner):
        for e in self._pending:
            if e[0] == 'side':
                e[4] = 0.0 if winner is None else (1.0 if winner == e[1] else -1.0)
        self.samples.extend(e for e in self._pending if e[4] is not None)
        self._pending = []; self.matches += 1
        if len(self.samples) >= self.PACK_EVERY:
            self._flush()

    def _flush(self):
        from . import buffer as B
        for kind in ('game', 'side'):
            self._packs[kind].append(B.pack(kind, [e for e in self.samples if e[0] == kind], self.worker))
        self.samples = []

    def packed(self):
        """지금까지 확정된 표본 → {'game': 묶음 또는 None, 'side': 묶음 또는 None}"""
        from . import buffer as B
        self._flush()
        return {k: B.concat(v) for k, v in self._packs.items()}

    def abort_match(self):
        self._pending = []


class DRLAI(LearnedAI):
    PASS_EVAL = False   # 종료 · 패스 보유 가치 평가는 끈다 — 후보 점수 h가 DRL 입력 특징이라 학습 당시 분포를 유지 (재학습 때 켠다)
    def __init__(self, skill, actor=None, mode='greedy', temperature=1.0, rng=None, recorder=None, seat=0,
                 teacher=None, teacher_eps=0.0, teacher_temp=0.03, split_override=None, log_decisions=True):
        super().__init__(skill, split_override, learn=False, eps=teacher_eps if mode == 'teacher' else 0.0)
        if mode not in ('greedy', 'sample', 'teacher'):
            raise ValueError(mode)
        if mode == 'teacher' and teacher is None:
            raise ValueError('teacher 모드에는 교사 학습표(teacher)가 필요함')
        if mode != 'teacher' and actor is None:
            raise ValueError('greedy · sample 모드에는 actor(NumpyActor)가 필요함')
        self.actor = actor; self.mode = mode; self.temperature = temperature
        self.rng = rng if rng is not None else np.random.default_rng(0)
        self.recorder = recorder; self.seat = seat
        self.teacher = teacher; self.teacher_temp = teacher_temp; self.log_decisions = log_decisions

    # ── 교사(학습표) 값: LearnedAI.choose와 같은 키 · 사전값 ──
    def teacher_values(self, g, p, decision, opts, scale):
        me = g.p[p].skill.name; op = g.p[1 - p].skill.name
        base = f'{me} vs {op}|{decision}|'; b = self.bucket(g, p)
        return np.array([self.teacher.value(base + lab, base + lab + '|' + b, prior_of(h, scale))[0] for lab, h, _ in opts], np.float64)

    @staticmethod
    def game_id(g):
        gid = getattr(g, '_drl_gid', None)
        if gid is None:
            gid = g._drl_gid = next(_GID)
        return gid

    def choose(self, g, p, decision, opts, scale=40.0, log=True):
        if not opts:
            return None
        if getattr(g, 'script', None) is not None:          # 탐색 AI의 재현 게임 — 기존 절차 그대로
            return LearnedAI.choose(self, g, p, decision, opts, scale, log)
        if len(opts) == 1:
            return self._rec(g, p, 0, opts)
        rec = self.recorder is not None
        tv = self.teacher_values(g, p, decision, opts, scale) if self.teacher is not None else None
        if self.mode == 'teacher':
            # LearnedAI.choose와 같은 선택: 값 내림차순 안정 정렬의 첫째(동점이면 앞 후보), 탐색은 g.rng로 같은 방식
            order = sorted(range(len(opts)), key=lambda i: -tv[i])
            if self.eps and g.rng.random() < self.eps:
                pick = g.rng.choice(order); why = '탐색'
            else:
                pick = order[0]; why = '학습표'
            idx = next(i for i, o in enumerate(opts) if o[0] == opts[pick][0])
            probs = None; logp = 0.0
        else:
            obs, orc = F.encode_obs(g, p, decision, oracle=rec)
            cands = F.encode_cands(g, p, decision, opts, scale)
            lg = self.actor.logits(obs, cands) / self.temperature
            probs = softmax(lg)
            if self.mode == 'sample':
                idx = int(min(np.searchsorted(np.cumsum(probs), self.rng.random()), len(opts) - 1)); why = 'DRL 표본'
            else:
                idx = int(np.argmax(lg)); why = 'DRL'
            logp = float(math.log(max(probs[idx], 1e-12)))
        if rec:
            if self.mode == 'teacher':
                obs, orc = F.encode_obs(g, p, decision, oracle=True)
                cands = F.encode_cands(g, p, decision, opts, scale)
            tp = softmax(tv / self.teacher_temp).astype(np.float32) if tv is not None else None
            self.recorder.add('game', self.seat, self.game_id(g), (obs, orc, cands, idx, logp, tp, S.parse_decision(decision)[0]))
        if log and self.log_decisions:
            if probs is not None:
                cs = ', '.join(f'{lab}={pr * 100:.1f}%' for (lab, _, _), pr in sorted(zip(opts, probs), key=lambda x: -x[1])[:8])
                shown = [(lab, round(float(pr) * 100, 1), 0) for (lab, _, _), pr in sorted(zip(opts, probs), key=lambda x: -x[1])[:4]]
            else:
                cs = ', '.join(f'{opts[i][0]}={tv[i] * 100:.1f}%' for i in sorted(range(len(opts)), key=lambda i: -tv[i])[:8])
                shown = [(opts[i][0], round(float(tv[i]) * 100, 1), 0) for i in sorted(range(len(opts)), key=lambda i: -tv[i])[:4]]
            g.L(f'판단[{g.pname(p)}] {decision}: {{{cs}}} → {opts[idx][0]} ({why})', 'decision')
            g.log[-1]['data'] = {'p': p, 'decision': decision, 'pick': opts[idx][0], 'why': why, 'opts': shown}
        return self._rec(g, p, idx, opts)

    def end_game(self, g, p, winner):
        super().end_game(g, p, winner)
        if self.recorder is not None and getattr(g, '_drl_gid', None) is not None:
            self.recorder.end_game(g._drl_gid, self.seat, 0.0 if winner is None else (1.0 if winner == p else -1.0))
