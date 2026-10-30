"""4차원 주머니 — NNY 프로젝트 비서 디스코드 봇 (슬래시 커맨드, discord.py).

- 슬래시 커맨드 응답은 기본 **자기한테만 보임(ephemeral)** — 채널을 안 더럽히는 안내문.
- 게이트웨이 연결이라 **명령·메시지에 실시간 반응**.
- 조회(진행·업데이트·접속·재정·상태·덱)는 리포/게임서버를 읽어 봇이 즉답.
- `/질문`·`?...` 자유 질문: ANTHROPIC_API_KEY 있으면 즉답, 없으면 접수(루틴이 매시 :07 처리).

설정 파일: %LOCALAPPDATA%/NNY_Simulator/discord.json
  {token, guild_id(선택), server_url(게임서버 http 주소), admin_ids[관리자 디스코드 id]}
실행: py -3.12 tools/discord_bot.py   (바탕화면 NNY디코봇.bat)
"""
import json, os, time, urllib.request, urllib.error
import discord
from discord import app_commands

CFG = os.path.join(os.environ.get('LOCALAPPDATA', '.'), 'NNY_Simulator', 'discord.json')
cfg = json.load(open(CFG, encoding='utf-8-sig'))
TOKEN = cfg['token']
GUILD_ID = int(cfg.get('guild_id') or 1514441529257623662)
SERVER_URL = cfg.get('server_url', 'http://25.0.242.63:8899')
ADMIN_IDS = set(str(x) for x in (cfg.get('admin_ids') or []))
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip()
REPO = 'somlon/card_simulation_model'
RAW = f'https://raw.githubusercontent.com/{REPO}/online/main/'
GH = f'https://api.github.com/repos/{REPO}/'
USERS_PATH = os.path.join(os.path.dirname(CFG), 'online_users.json')  # 유저 등록 로컬 저장

CONNECT_BAT = (
    '@echo off\r\nchcp 65001 > nul\r\ntitle 뉴네오 유희왕 접속\r\n'
    'echo.\r\necho  [뉴네오 유희왕 온라인] 접속\r\necho.\r\n'
    'echo  1) 하마치 켜고 네트워크(new_card_game / 17225)에 들어와 있어야 해요.\r\n'
    'echo  2) 인준이 서버를 켜둬야 접속됩니다.\r\necho.\r\n'
    'echo  브라우저로 게임 화면을 엽니다...\r\ntimeout /t 2 > nul\r\n'
    f'start "" {SERVER_URL}/\r\n'
    'echo  안 열리면 하마치 연결/서버 상태를 확인하세요.\r\npause\r\n')


def fetch(url, timeout=15):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'nny-bot'}), timeout=timeout).read().decode('utf-8')


# ───────── 조회 기능 ─────────
def 진행():
    try:
        t = fetch(RAW + 'NNY%EC%98%A8%EB%9D%BC%EC%9D%B8_%EC%A7%84%ED%96%89.md')
        return '📋 **진행 상황** (최신 기록 머리)\n' + '\n'.join(t.splitlines()[:28])
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
            '1) 하마치 설치(https://vpn.net) → 네트워크 참가: 이름 `new_card_game` / 비번 `17225`\n'
            f'2) 인준이 서버 켠 상태에서 브라우저로 {SERVER_URL}/\n'
            '3) 미등록이면 `/유저등록` 하거나 인준에게 하마치 IP(25.x) 알려주고 등록 요청\n'
            '• 매번 주소 치기 귀찮으면 `/접속파일` 로 더블클릭 bat 받기')


def 재정():
    try:
        fs = json.loads(fetch(GH + 'contents/%EC%9E%AC%EC%A0%95%EC%A7%88%EB%AC%B8?ref=online/main'))
        names = [f['name'] for f in fs if f['name'] != 'README.md']
    except Exception:
        names = []
    return ('⚖️ **재정질문** ' + (f'{len(names)}건\n' + '\n'.join('- ' + n for n in names[:15]) if names else '— 지금 열린 질문 없음') +
            '\n(답변은 깃허브 재정질문/ 파일에 직접 적으면 루틴이 반영)')


def 상태():
    try:
        r = fetch(SERVER_URL + '/api/ping', timeout=4)
        j = json.loads(r)
        return f'🟢 **게임 서버 켜짐** (v{j.get("version", "?")}) — 바로 접속할 수 있어요: {SERVER_URL}/'
    except Exception:
        return f'🔴 **게임 서버 꺼짐** — 인준이 서버를 켜야 접속돼요. ({SERVER_URL})'


def 덱():
    try:
        pool = json.loads(fetch(RAW + 'nny_sim/card_pool.json'))
        skills = sorted({c.get('skill') or c.get('스킬') for c in pool if (c.get('type') == '스킬' or c.get('deck') == '스킬')} - {None})
        if skills:
            return '🃏 **덱(스킬) 목록**\n' + '\n'.join('- ' + s for s in skills)
    except Exception:
        pass
    return '🃏 덱 목록은 게임 화면의 「덱 편집」에서 볼 수 있어요.'


MENU = ('🗂 **4차원 주머니** — 명령은 전부 나한테만 보여요 (채널 안 더러워짐)\n'
        '`/상태` 서버 켜짐? · `/접속` 접속법 · `/접속파일` 더블클릭 bat\n'
        '`/진행` 진행 상황 · `/업데이트` 최근 커밋 · `/재정` 재정질문 · `/덱` 덱 목록\n'
        '`/유저등록 <하마치IP>` 내 접속 등록 · `/질문 <내용>` 자유 질문\n'
        '채널에 `?내용` 으로도 질문할 수 있어요.')


# ───────── 유저 등록 ─────────
def load_users():
    try:
        return json.load(open(USERS_PATH, encoding='utf-8-sig'))
    except Exception:
        return {'_설명': '이름:하마치IP (최대 5)'}


def save_users(u):
    json.dump(u, open(USERS_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def 유저등록(name, ip):
    ip = ip.strip()
    import re
    if not re.match(r'^25\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
        return '❌ 하마치 IP 형식이 아니에요. 하마치 창에 보이는 `25.x.x.x` 를 적어주세요.'
    u = load_users()
    real = {k: v for k, v in u.items() if not k.startswith('_')}
    if name not in real and len(real) >= 5:
        return '❌ 정원(5명)이 찼어요. 인준에게 말해주세요.'
    u[name] = ip
    save_users(u)
    return f'✅ 등록 완료: **{name}** → `{ip}` (총 {len([k for k in u if not k.startswith("_")])}/5명)\n이제 서버가 켜져 있으면 접속할 수 있어요.'


# ───────── 자유 질문 ─────────
def ask_claude(q):
    if not API_KEY:
        return None
    sys_p = ('너는 「뉴네오 유희왕」 온라인판 프로젝트의 디스코드 비서야. 세창의 NNY 시뮬레이터 기반 '
             '하마치 접속 온라인 대전·관전·룰미스 메모·AI 프로젝트. 리포 somlon/card_simulation_model online/main. '
             '프로젝트 관련 질문에만 한국어로 짧고 정확히, 모르면 모른다고. 프로젝트 밖은 정중히 거절.')
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
    ans = ask_claude(text)
    if ans:
        return '💬 ' + ans
    now = time.localtime()
    mins = (7 - now.tm_min) % 60 or 60
    eta = time.strftime('%H:%M', time.localtime(time.time() + mins * 60))
    return (f'📨 질문 접수! Claude 루틴이 **매시 7분**에 확인하고 이 채널에 답을 달아줘요.\n'
            f'→ 다음 확인까지 약 **{mins}분** (대략 {eta}경). 다른 작업 중이면 그다음 회차(최대 1시간)로 밀릴 수 있어요.')


# ───────── 봇 본체 ─────────
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
        print('로그인:', client.user, '| 커맨드 동기화 완료', flush=True)
    except Exception as e:
        print('동기화 실패:', e, flush=True)


def reg(name, desc, fn):
    async def _cmd(interaction: discord.Interaction):
        await interaction.response.send_message(fn(), ephemeral=True)
    _cmd.__name__ = 'cmd_' + name
    tree.command(name=name, description=desc, guild=GUILD)(_cmd)


reg('메뉴', '사용법 안내 (나만 보임)', lambda: MENU)
reg('도움', '사용법 안내 (나만 보임)', lambda: MENU)
reg('상태', '게임 서버 켜졌는지 확인 (나만 보임)', 상태)
reg('진행', '프로젝트 진행 상황 (나만 보임)', 진행)
reg('업데이트', '최근 커밋 내역 (나만 보임)', 커밋)
reg('접속', '게임 접속 방법 (나만 보임)', 접속)
reg('재정', '재정질문 목록 (나만 보임)', 재정)
reg('덱', '덱(스킬) 목록 (나만 보임)', 덱)


@tree.command(name='유저등록', description='내 하마치 IP를 등록해 접속 허용 (나만 보임)', guild=GUILD)
@app_commands.describe(하마치ip='하마치 창에 보이는 25.x.x.x 주소')
async def 유저등록_cmd(interaction: discord.Interaction, 하마치ip: str):
    name = interaction.user.display_name
    await interaction.response.send_message(유저등록(name, 하마치ip), ephemeral=True)


@tree.command(name='접속파일', description='더블클릭 접속 bat 받기 (나만 보임)', guild=GUILD)
async def 접속파일_cmd(interaction: discord.Interaction):
    import io
    f = discord.File(io.BytesIO(CONNECT_BAT.encode('utf-8')), filename='newneo_connect.bat')
    await interaction.response.send_message(
        '📎 더블클릭하면 게임 화면이 열려요. (하마치 먼저 연결 필수!)\n'
        '⚠ 디스코드가 .bat 경고를 띄우는데, 브라우저로 주소만 여는 안전한 파일이에요(메모장으로 열면 내용 보임).',
        file=f, ephemeral=True)


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
        try:
            await m.channel.send(f'{m.author.mention} ' + 질문접수(m.author.display_name, c[1:].strip()))
        except Exception:
            pass


if __name__ == '__main__':
    client.run(TOKEN)
