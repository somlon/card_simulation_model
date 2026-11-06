"""시험 전용 — 데이터버그 테마는 카드 풀에서 빠져 있다(사용자 지시 2026-10-30 「데이터버그는 이후에 수정할게 일단은 카드풀에서 해당 테마 카드들을 모두 제외」).
그 카드를 쓰는 엔진 시험(일반 규칙 시험 포함)은 보류 자료 — 카드자료/보류/데이터버그.md(parse_pool_md 형식, 예전 풀과 같음) ·
decks/보관/2026-10-30_데이터버그제외/시제_데이터버그_패키지_프로그램.deck — 로 그 카드 · 덱을 시험 모듈이 도는 동안만 넣는다.
  def setUpModule(): databug_fixture.install()      # 자료가 없으면 unittest.SkipTest
  def tearDownModule(): databug_fixture.uninstall()
풀에 데이터버그가 다시 들어오면(카드를 고친 뒤) 아무것도 하지 않는다."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
THEME = '데이터버그'
MD = os.path.join(HERE, '카드자료', '보류', '데이터버그.md')
DECK = os.path.join(HERE, 'decks', '보관', '2026-10-30_데이터버그제외', '시제_데이터버그_패키지_프로그램.deck')
_added = {'cards': [], 'decks': []}


def _deck_dicts():
    """불러온 시험 모듈들의 덱 목록(DECKS — season.load_decks 결과)"""
    return [m.DECKS for n, m in list(sys.modules.items()) if n.startswith('test_') and isinstance(getattr(m, 'DECKS', None), dict)]


def install():
    import cards, deck as D
    if any(c.get('theme') == THEME for c in cards.POOL.values()): return   # 풀에 다시 들어왔다
    if not (os.path.exists(MD) and os.path.exists(DECK)): raise unittest.SkipTest('데이터버그 보류 자료가 없음 — 데이터버그 시험 건너뜀')
    import parse_pool_md as PP
    for c in PP.parse_file(MD):
        cards.POOL[c['name']] = c; D.POOL.append(c); D.BY_NAME[c['name']] = c
        if c.get('code'): D.BY_CODE[c['code']] = c
        _added['cards'].append(c)
    dk = D.load(DECK)[0]
    for dd in _deck_dicts():
        if dk['스킬'] not in dd: dd[dk['스킬']] = dk; _added['decks'].append((dd, dk['스킬']))


def uninstall():
    import cards, deck as D
    for c in _added['cards']:
        cards.POOL.pop(c['name'], None); D.BY_NAME.pop(c['name'], None); D.BY_CODE.pop(c.get('code'), None)
        if c in D.POOL: D.POOL.remove(c)
    for dd, sk in _added['decks']: dd.pop(sk, None)
    _added['cards'].clear(); _added['decks'].clear()
