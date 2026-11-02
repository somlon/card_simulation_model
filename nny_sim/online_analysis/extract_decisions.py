"""기보(.json.gz, schema 1) → 판단 로그 추출기.

온라인판 기보는 app/session.Match.replay_dict()가 만드는 스키마 1 dict를 gzip해 저장한다
(viewer/record.Recorder가 만든 frames + states). online_demos/demo_방식2_모방.py는 이미 그 frames에서
(판단 종류, 후보, 고른 수)만 뽑아 쓰지만, 2026-11-02 확정된 AI 방식(「docs/AI_방식_선택지.md」 2안+3안
조합, 사람 기보 기반)의 목표 산출물 — ① 이긴 판의 공통 요점 ② 상황별 카드 선택과 승률 — 에는 그
판단이 속한 라운드·매치를 결국 누가 이겼는지가 함께 있어야 한다. 이 모듈은 그 승패 레이블과 턴·단계
요약을 붙여 판단 레코드를 뽑는다. 아직 사람 기보가 없어(online/data-games 기보 0건) 진짜 온라인
기보로는 못 돌려 봤다 — test_extract_decisions.py가 AI끼리 돌린 기보(viewer.record.record_match)로
파이프라인만 확인한다. 기보가 쌓이면 그 파일을 그대로 넘기면 된다.
"""
import gzip, json


def load_replay(path):
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def _round_result(meta, round_no):
    """round_no: frame['r'](1부터). meta['rounds']는 0부터 — 없으면 None."""
    rounds = meta.get('rounds') or []
    i = round_no - 1
    return rounds[i] if 0 <= i < len(rounds) else None


def _state_summary(states, s):
    if s is None or s < 0 or s >= len(states):
        return None
    st = states[s]
    P = st.get('P') or []
    return {'t': st.get('t'), 'ph': st.get('ph'), 'tp': st.get('tp'),
            'hp': [p.get('hp') for p in P], 'hand_n': [len(p.get('hand') or []) for p in P],
            'grave_n': [len(p.get('grave') or []) for p in P], 'ban_n': [len(p.get('ban') or []) for p in P]}


def extract_decisions(rec):
    """rec: load_replay()가 낸 dict. 판단 레코드(dict) 목록을 낸다 — 라운드·매치 승패 레이블 포함.

    각 레코드: decision(판단 종류) · player · pick · why · opts([label, 학습값%])
    · round · state(그 시점 턴·단계·HP·패/묘지/제외 수) · round_result(그 라운드 승자·사유)
    · match_winner · won_round · won_match(해당 player 기준, 모르면 None)."""
    meta = rec.get('meta') or {}
    states = rec.get('states') or []
    match_winner = meta.get('winner')
    out = []
    for fr in rec.get('frames') or []:
        if not isinstance(fr, dict) or fr.get('k') != 'decision':
            continue
        d = fr.get('d')
        if not isinstance(d, dict) or d.get('p') is None or not d.get('q'):
            continue
        p = d['p']; round_no = fr.get('r') or 0
        rr = _round_result(meta, round_no)
        round_winner = rr.get('winner') if rr else None
        out.append({
            'decision': d.get('q'), 'player': p, 'pick': d.get('pick'), 'why': d.get('why'),
            'opts': d.get('opts') or [], 'round': round_no, 'state': _state_summary(states, fr.get('s')),
            'round_result': rr, 'match_winner': match_winner,
            'won_round': (round_winner == p) if round_winner is not None else None,
            'won_match': (match_winner == p) if match_winner is not None else None,
        })
    return out


def extract_file(path):
    return extract_decisions(load_replay(path))


def main(argv):
    import sys
    if len(argv) < 2:
        sys.exit('usage: extract_decisions.py <기보.json[.gz]> [출력.jsonl]')
    rows = extract_file(argv[1])
    out = open(argv[2], 'w', encoding='utf-8') if len(argv) > 2 else sys.stdout
    try:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
    finally:
        if out is not sys.stdout:
            out.close()
    print(f'{len(rows)}개 판단 추출' + (f' → {argv[2]}' if len(argv) > 2 else ''), file=sys.stderr)
    return len(rows)


if __name__ == '__main__':
    import sys
    main(sys.argv)
