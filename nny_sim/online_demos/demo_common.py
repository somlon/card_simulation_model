"""AI 방식 데모 공용 — sim 폴더 연결 · 덱 로드 · 기록형 AI.

사용: 각 데모를 `runtime/python.exe <데모.py> --sim <sim폴더>` 로 실행.
sim 폴더 = v1.1.0 빌드의 sim/ (엔진 + 카드 풀 + 덱). 룰 엔진은 전혀 수정하지 않는다.
"""
import argparse, os, sys


def attach_sim(default=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sim', default=default or os.path.join(os.path.expanduser('~'), 'Desktop', 'NNY_Simulator', 'sim'))
    ap.add_argument('--out', default=os.path.join(os.path.expanduser('~'), 'Desktop', 'NNY_AI분석'))
    ap.add_argument('--n', type=int, default=0)   # 데모별 규모(0이면 데모 기본값)
    a = ap.parse_args()
    sim = os.path.abspath(a.sim)
    if not os.path.exists(os.path.join(sim, 'engine.py')):
        sys.exit(f'engine.py 가 없음: {sim} — --sim 으로 sim 폴더를 지정하세요')
    sys.path.insert(0, sim); os.chdir(sim)
    os.makedirs(a.out, exist_ok=True)
    return a


def load_decks(*names):
    import deck as D
    out = []
    for n in names:
        d, errs, _ = D.load(os.path.join('decks', n))
        if errs: sys.exit(f'덱 오류 {n}: {errs[:2]}')
        out.append(d)
    return out


def recording_ai(skill, sink):
    """LearnedAI 서브클래스 인스턴스 — 판단(결정 이름 · 후보 라벨 · 고른 번호)을 sink 에 기록.
    엔진이 부르는 상위 메서드(main_phase 등)가 내부에서 self.choose 를 쓰므로 서브클래스가 정답."""
    from policy import LearnedAI

    class RecordingAI(LearnedAI):
        def choose(self, g, p, decision, opts, scale=40.0, log=True, **kw):
            pay = super().choose(g, p, decision, opts, scale, log, **kw)
            if getattr(g, 'script', None) is None and len(opts) > 1:
                try:
                    idx = next(i for i, o in enumerate(opts) if o[2] is pay)
                except StopIteration:
                    idx = next((i for i, o in enumerate(opts) if o[2] == pay), 0)
                self._sink.append({'p': p, 'decision': decision, 'labels': [o[0] for o in opts],
                                   'pick': idx, 'turn': getattr(g, 'turn', 0), 'dlog_len': len(g.dlog) - 1})
            return pay

    ai = RecordingAI(skill, learn=False)
    ai._sink = sink
    return ai
