"""4차원 주머니 — NNY 프로젝트 비서 디스코드 봇 (표준 라이브러리만, REST 폴링).

- 아무 채널에서 암호 번호를 치면 1시간 동안 메뉴 사용 가능.
- 메뉴: 1 진행 상황 / 2 최근 업데이트 / 3 접속 방법 / 4 재정질문 목록
  (전부 공개 리포(online/main)를 읽어서 답함 — Claude 호출 없음, 즉답)
- `?` 로 시작하는 글 = 자유 질문 접수 → 매시간 클라우드 루틴이 답변을 닮.
- 토큰·암호는 리포가 아니라 로컬 파일(%LOCALAPPDATA%/NNY_Simulator/discord.json)에 둔다.

실행: python tools/discord_bot.py   (바탕화면 NNY디코봇.bat 참조)
"""
import json, os, time, urllib.request, urllib.error

CFG = os.path.join(os.environ.get('LOCALAPPDATA', '.'), 'NNY_Simulator', 'discord.json')
cfg = json.load(open(CFG, encoding='utf-8-sig'))
TOK, PW = cfg['token'], str(cfg.get('암호', '17225'))
API = 'https://discord.com/api/v10'
RAW = 'https://raw.githubusercontent.com/somlon/card_simulation_model/online/main/'
GH = 'https://api.github.com/repos/somlon/card_simulation_model/'
HDR = {'Authorization': 'Bot ' + TOK, 'User-Agent': 'DiscordBot (nny, 1.0)', 'Content-Type': 'application/json'}


def req(url, body=None, hdr=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                               headers=hdr or HDR, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(r, timeout=15) as f:
            return json.load(f)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(float(json.load(e).get('retry_after', 2))); return req(url, body, hdr)
        raise


def say(ch, text):
    for part in [text[i:i + 1900] for i in range(0, len(text), 1900)] or ['']:
        req(f'{API}/channels/{ch}/messages', {'content': part})


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'nny-bot'}), timeout=15).read().decode('utf-8')


def 진행():
    t = fetch(RAW + 'NNY%EC%98%A8%EB%9D%BC%EC%9D%B8_%EC%A7%84%ED%96%89.md')
    return '📋 **진행 상황** (NNY온라인_진행.md 머리)\n' + '\n'.join(t.splitlines()[:30])


def 커밋():
    cs = json.loads(fetch(GH + 'commits?sha=online/main&per_page=5'))
    return '🔄 **최근 업데이트**\n' + '\n'.join(f"- {c['commit']['message'].splitlines()[0]} ({c['commit']['committer']['date'][:10]})" for c in cs)


def 접속():
    return ('🎮 **접속 방법**\n1) 하마치 설치 → 네트워크 참가: `new_card_game` / 비번 `17225`\n'
            '2) 인준이 서버 켠 상태에서 브라우저로 http://25.0.242.63:8899/\n'
            '3) 미등록이면 인준에게 자기 하마치 IP(25.x) 알려주고 등록 요청')


def 재정():
    try:
        fs = json.loads(fetch(GH + 'contents/%EC%9E%AC%EC%A0%95%EC%A7%88%EB%AC%B8?ref=online/main'))
        names = [f['name'] for f in fs if f['name'] != 'README.md']
    except Exception:
        names = []
    return ('⚖️ **재정질문** ' + (f'{len(names)}건\n' + '\n'.join('- ' + n for n in names[:15]) if names else '— 지금 열린 질문 없음') +
            '\n(답변은 깃허브 재정질문/ 파일에 직접 적으면 루틴이 반영)')


MENU = (f'🗂 **4차원 주머니 메뉴** (1시간 유효)\n`1` 진행 상황 · `2` 최근 업데이트 · `3` 접속 방법 · `4` 재정질문\n'
        f'자유 질문은 `?질문내용` — 매시간 Claude 루틴이 답을 달아줘요')


def handle(content, author_id, authed):
    c = content.strip()
    if c == PW:
        authed[author_id] = time.time(); return MENU
    ok = time.time() - authed.get(author_id, 0) < 3600
    if c.startswith('?'):
        return '📨 질문 접수! 매시간 루틴이 확인하고 이 채널에 답을 달아줘요.'
    if not ok:
        return None if c not in '1234' else '🔒 먼저 암호 번호를 입력해 주세요.'
    try:
        return {'1': 진행, '2': 커밋, '3': 접속, '4': 재정}.get(c, lambda: None)()
    except Exception as e:
        return f'(조회 실패: {e})'




from discord_intro import INTRO


def setup_once():
    """봇이 서버에 처음 들어온 뒤 1회: 서버 이름 변경 + 소개글 게시·고정."""
    mark = os.path.join(os.path.dirname(CFG), 'discord_setup_done.txt')
    if os.path.exists(mark):
        return
    gs = req(f'{API}/users/@me/guilds')
    if not gs:
        return
    g = gs[0]
    try:
        r = urllib.request.Request(f"{API}/guilds/{g['id']}", data=json.dumps({'name': '뉴네오 유희왕'}).encode(),
                                   headers=HDR, method='PATCH')
        urllib.request.urlopen(r, timeout=15).read()
        print('서버 이름 → 뉴네오 유희왕')
    except Exception as e:
        print('(서버 이름 변경 불가 — 권한 부족일 수 있음)', e)
    chs = [c for c in req(f"{API}/guilds/{g['id']}/channels") if c['type'] == 0]
    if chs:
        m = req(f'{API}/channels/{chs[0]["id"]}/messages', {'content': INTRO})
        try:
            r = urllib.request.Request(f'{API}/channels/{chs[0]["id"]}/pins/{m["id"]}', headers=HDR, method='PUT')
            urllib.request.urlopen(r, timeout=15).read()
            print('소개글 게시 + 고정 완료')
        except Exception as e:
            print('소개글 게시 완료 (고정 실패 — 권한 부족)', e)
    open(mark, 'w').write('done')


def main():
    me = req(f'{API}/users/@me'); my_id = me['id']
    print('봇 로그인:', me['username'])
    last = {}; authed = {}; chans = []; tick = 0

    def rescan():
        nonlocal chans
        setup_once()
        found = []
        for g in req(f'{API}/users/@me/guilds'):
            found += [c['id'] for c in req(f"{API}/guilds/{g['id']}/channels") if c['type'] == 0]
        for ch in found:
            if ch not in last:
                ms = req(f'{API}/channels/{ch}/messages?limit=1')
                last[ch] = ms[0]['id'] if ms else '0'
        if len(found) != len(chans):
            print('감시 채널', len(found), '개')
        chans = found

    rescan()
    print('폴링 시작 (서버 초대가 아직이면 60초마다 재탐색, Ctrl+C 종료)')
    while True:
        tick += 1
        if not chans or tick % 20 == 0:
            try:
                rescan()
            except Exception:
                pass
        for ch in chans:
            try:
                ms = req(f'{API}/channels/{ch}/messages?after={last[ch]}&limit=10')
            except Exception:
                continue
            for m in reversed(ms):
                last[ch] = max(last[ch], m['id'], key=int)
                if m['author'].get('id') == my_id or m['author'].get('bot'): continue
                out = handle(m.get('content', ''), m['author']['id'], authed)
                if out: say(ch, out)
        time.sleep(3)


if __name__ == '__main__':
    main()
