"""4차원 주머니 — NNY 프로젝트 비서 디스코드 봇 (슬래시 커맨드, discord.py).

- 슬래시 커맨드는 응답이 **자기한테만 보임(ephemeral)** — 채널을 더럽히지 않는 안내문.
- 게이트웨이 연결이라 **메시지/명령에 실시간 반응**(폴링 아님).
- 메뉴/조회(진행·업데이트·접속·재정)는 리포를 읽어 봇이 즉답.
- `?...` 또는 /질문 은 자유 질문 — 기본은 접수(online/data-games 에 쌓고 Claude 루틴이 처리).
  환경변수 ANTHROPIC_API_KEY 가 있으면 그 자리에서 Claude 로 즉답한다(선택, 별도 과금).

토큰·설정: %LOCALAPPDATA%/NNY_Simulator/discord.json  (token, 암호[미사용], guild_id 선택)
실행: py -3.12 tools/discord_bot.py
"""
import json, os, time, urllib.request
import discord
from discord import app_commands

CFG = os.path.join(os.environ.get('LOCALAPPDATA', '.'), 'NNY_Simulator', 'discord.json')
cfg = json.load(open(CFG, encoding='utf-8-sig'))
TOKEN = cfg['token']
GUILD_ID = int(cfg.get('guild_id') or 1514441529257623662)
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip()
RAW = 'https://raw.githubusercontent.com/somlon/card_simulation_model/online/main/'
GH = 'https://api.github.com/repos/somlon/card_simulation_model/'


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'nny-bot'}), timeout=15).read().decode('utf-8')


def 진행():
    try:
        t = fetch(RAW + 'NNY%EC%98%A8%EB%9D%BC%EC%9D%B8_%EC%A7%84%ED%96%89.md')
        return '📋 **진행 상황** (NNY온라인_진행.md 머리)\n' + '\n'.join(t.splitlines()[:28])
    except Exception as e:
        return f'(진행 문서를 못 읽었어요: {e})'


def 커밋():
    try:
        cs = json.loads(fetch(GH + 'commits?sha=online/main&per_page=6'))
        return '🔄 **최근 업데이트**\n' + '\n'.join(f"- {c['commit']['message'].splitlines()[0]} ({c['commit']['committer']['date'][:10]})" for c in cs)
    except Exception as e:
        return f'(커밋을 못 읽었어요: {e})'


def 접속():
    return ('🎮 **접속 방법**\n'
            '1) 하마치 설치 → 네트워크 참가: 이름 `new_card_game` / 비번 `17225`\n'
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


MENU = ('🗂 **4차원 주머니** — 명령은 전부 나한테만 보여요\n'
        '`/진행` 진행 상황 · `/업데이트` 최근 커밋 · `/접속` 게임 접속법 · `/재정` 재정질문\n'
        '`/질문 <내용>` 또는 채널에 `?내용` — 프로젝트 관련 자유 질문')


def ask_claude(q):
    """ANTHROPIC_API_KEY 가 있을 때만. 프로젝트 비서 역할로 즉답."""
    if not API_KEY:
        return None
    sys_p = ('너는 「뉴네오 유희왕」 온라인판 프로젝트의 디스코드 비서야. 세창의 NNY 시뮬레이터 기반으로 '
             '하마치 접속 온라인 대전·관전·룰미스 메모·AI를 만드는 중. 리포는 somlon/card_simulation_model '
             'online/main. 프로젝트 관련 질문에만 한국어로 짧고 정확히 답하고, 모르면 모른다고 해. '
             '프로젝트 밖 질문은 정중히 거절.')
    body = json.dumps({'model': 'claude-sonnet-5', 'max_tokens': 500, 'system': sys_p,
                       'messages': [{'role': 'user', 'content': q}]}).encode()
    r = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body,
                               headers={'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    try:
        d = json.load(urllib.request.urlopen(r, timeout=40))
        return ''.join(b.get('text', '') for b in d.get('content', []))
    except Exception as e:
        return f'(Claude 호출 실패: {e})'


def 질문접수(author, text):
    """자유 질문 — 즉답 가능하면 Claude, 아니면 접수 + 다음 루틴까지 남은 시간 안내."""
    ans = ask_claude(text)
    if ans:
        return '💬 ' + ans
    now = time.localtime()
    mins = (7 - now.tm_min) % 60  # 다음 :07(매시 7분 루틴)까지 남은 분
    if mins == 0:
        mins = 60
    eta = time.strftime('%H:%M', time.localtime(time.time() + mins * 60))
    return (f'📨 질문 접수! Claude 루틴이 **매시 7분**에 디스코드를 확인하고 이 채널에 답을 달아줘요.\n'
            f'→ 다음 확인까지 약 **{mins}분** (대략 {eta}경). 루틴이 다른 작업 중이면 그다음 회차(최대 1시간)로 밀릴 수 있어요.\n'
            f'(즉답을 켜려면 인준이 봇에 Claude API 키를 넣으면 돼요.)')


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
GUILD = discord.Object(id=GUILD_ID)


@client.event
async def on_ready():
    try:
        tree.copy_global_to(guild=GUILD)
        await tree.sync(guild=GUILD)
        print('로그인:', client.user, '| 슬래시 커맨드 동기화 완료 (guild', GUILD_ID, ')')
    except Exception as e:
        print('커맨드 동기화 실패:', e)


def reg(name, desc, fn):
    async def _cmd(interaction: discord.Interaction):
        await interaction.response.send_message(fn(), ephemeral=True)
    _cmd.__name__ = 'cmd_' + name
    tree.command(name=name, description=desc, guild=GUILD)(_cmd)


reg('메뉴', '사용법 안내 (나만 보임)', lambda: MENU)
reg('진행', '프로젝트 진행 상황 (나만 보임)', 진행)
reg('업데이트', '최근 커밋 내역 (나만 보임)', 커밋)
reg('접속', '게임 접속 방법 (나만 보임)', 접속)
reg('재정', '재정질문 목록 (나만 보임)', 재정)


@tree.command(name='질문', description='프로젝트 관련 자유 질문 (나만 보임)', guild=GUILD)
@app_commands.describe(내용='물어볼 내용')
async def 질문_cmd(interaction: discord.Interaction, 내용: str):
    await interaction.response.defer(ephemeral=True, thinking=True)
    await interaction.followup.send(질문접수(interaction.user.display_name, 내용), ephemeral=True)


@client.event
async def on_message(m):
    if m.author.bot:
        return
    c = (m.content or '').strip()
    if c.startswith('?') and len(c) > 1:
        # 채널에 ?로 올린 자유 질문 — 작성자에게만 보이게 할 수 없으니(일반 메시지) 짧게 채널 답.
        try:
            await m.channel.send(f'{m.author.mention} ' + 질문접수(m.author.display_name, c[1:].strip()))
        except Exception:
            pass


if __name__ == '__main__':
    client.run(TOKEN)
