"""시뮬레이션 종료 보고서 — 덱별 승리 요인 집계.

한 판의 로그에서 다음을 뽑아 덱별로 누적한다.
- 피니셔: 결착 대미지를 낸 카드 (전투 대미지는 공격한 몬스터, 효과 대미지는 그 카드). 덱아웃 등은 사유로 기록
- 결착 턴 콤보: 이긴 쪽이 결착 턴에 발동 · 소환한 카드의 조합
- 대미지 점유율: 이긴 판에서 상대에게 준 대미지의 카드별 비중
- 카드 영향도: 그 카드를 한 번 이상 발동 · 소환한 판의 승률 vs 그렇지 않은 판의 승률
"""
import re, collections

RE_ACT = re.compile(r'^(.+?) 「(.+?)」 \d번 효과 발동')
RE_SUM = re.compile(r'^(.+?) 「(.+?)」 (?:일반소환|특수소환)')
RE_DMG = re.compile(r'^(.+?) (\d+) 대미지 \((.+?)\)')
RE_ATK = re.compile(r'^(.+?) 「(.+?)」\(ATK \d+\) → ')


class Report:
    def __init__(self):
        self.d = collections.defaultdict(lambda: {
            'games': 0, 'wins': 0, 'fin': collections.Counter(), 'reason': collections.Counter(),
            'combo': collections.Counter(), 'dmg': collections.Counter(), 'dmg_total': 0,
            'used_w': collections.Counter(), 'used_n': collections.Counter(), 'win_turns': []})

    def add(self, log, names, winner, reason):
        """log: 한 라운드의 로그, names: [덱0 이름, 덱1 이름], winner: 0/1/None"""
        used = [set(), set()]; last_attacker = {}; dmg = [collections.Counter(), collections.Counter()]
        turn_cards = collections.defaultdict(set); fin = None; fin_turn = None
        idx = {n: i for i, n in enumerate(names)}
        for e in log:
            m = e['m']; t = e['t']
            r = RE_ACT.match(m) or RE_SUM.match(m)
            if r and r.group(1) in idx:
                i = idx[r.group(1)]; used[i].add(r.group(2)); turn_cards[(i, t)].add(r.group(2))
            r = RE_ATK.match(m)
            if r and r.group(1) in idx: last_attacker[idx[r.group(1)]] = r.group(2)
            r = RE_DMG.match(m)
            if r and r.group(1) in idx:
                victim = idx[r.group(1)]; src = r.group(3); amt = int(r.group(2)); dealer = 1 - victim
                if src.startswith('자해') or src == '공유 존 마커': card = src
                elif src.startswith('전투'): card = last_attacker.get(dealer, '전투')
                elif src.endswith('직접공격'): card = src[:-len(' 직접공격')]
                else: card = src
                dmg[dealer][card] += amt
                fin = card; fin_turn = t
        for i in (0, 1):
            s = self.d[names[i]]; s['games'] += 1; won = winner == i
            s['wins'] += won
            for c in used[i]:
                s['used_n'][c] += 1; s['used_w'][c] += won
            if won:
                if 'HP 0' in (reason or '') and fin:
                    s['fin'][fin] += 1
                    s['combo'][' + '.join(sorted(turn_cards[(i, fin_turn)])) or '(발동 없음 — 기존 필드로 결착)'] += 1
                    s['win_turns'].append(fin_turn)
                else:
                    s['reason'][reason] += 1
                for c, a in dmg[i].items(): s['dmg'][c] += a
                s['dmg_total'] += sum(dmg[i].values())

    def text(self, top=6):
        out = []
        for name, s in self.d.items():
            if not s['games']: continue
            w = s['wins']
            out.append(f'### {name} — {s["games"]}판 {w}승 ({w / s["games"] * 100:.1f}%)')
            if w:
                hp_w = sum(s['fin'].values())
                out.append(f'\n평균 결착 턴 {sum(s["win_turns"]) / max(1, len(s["win_turns"])):.1f}' +
                           (f' · HP 0 외 승리: ' + ', '.join(f'{k} {v}' for k, v in s['reason'].items()) if s['reason'] else ''))
                out.append('\n| 피니셔 (결착 대미지) | 비율 |\n| --- | --- |')
                for c, n in s['fin'].most_common(top): out.append(f'| {c} | {n / max(1, hp_w) * 100:.1f}% |')
                out.append('\n| 결착 턴 콤보 (그 턴에 발동 · 소환한 카드) | 비율 |\n| --- | --- |')
                for c, n in s['combo'].most_common(top): out.append(f'| {c} | {n / max(1, hp_w) * 100:.1f}% |')
                out.append('\n| 대미지 점유율 (이긴 판) | 비율 |\n| --- | --- |')
                for c, a in s['dmg'].most_common(top): out.append(f'| {c} | {a / max(1, s["dmg_total"]) * 100:.1f}% |')
            rows = []
            for c, n in s['used_n'].items():
                if n < max(10, s['games'] * 0.05) or s['games'] - n < 10: continue
                wu = s['used_w'][c] / n; wn = (w - s['used_w'][c]) / (s['games'] - n)
                rows.append((wu - wn, c, wu, wn, n / s['games']))
            rows.sort(reverse=True)
            if rows:
                out.append('\n| 카드 영향도 | 사용한 판 승률 | 안 쓴 판 승률 | 차이 | 사용률 |\n| --- | --- | --- | --- | --- |')
                for d, c, wu, wn, r in rows[:top] + (rows[-3:] if len(rows) > top else []):
                    out.append(f'| {c} | {wu * 100:.1f}% | {wn * 100:.1f}% | {d * 100:+.1f}%p | {r * 100:.0f}% |')
            out.append('')
        out.append('영향도는 연관이지 인과가 아니다 — 이기고 있을 때 쓰게 되는 카드도 높게 나온다.')
        return '\n'.join(out)
