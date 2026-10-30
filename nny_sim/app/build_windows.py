"""Windows 배포본 만들기(리눅스에서) — NNY_Simulator 폴더 + zip.

  python3 build_windows.py --sim <실행 폴더(model/main 코드 + data/main 데이터, 전체 policy.json.xz 포함)>
                           --nupkg python.3.13.17.nupkg --numpy-wheel numpy-2.4.6-cp313-cp313-win_amd64.whl --out <출력 폴더>
                           [--split <분할 표>] [--library <재생 기록>] [--nn-base <기본 신경망 모델.npz>]

준비물(우분투): gcc-mingw-w64-x86-64 (실행기 .exe), Pillow (이미지 · 아이콘).
Windows 파이썬: NuGet의 파이썬 재단 공식 패키지 `python`(https://www.nuget.org/packages/python) — 개발 환경과 같은 3.13.17.
numpy(신경망 AI 추론 · 로컬 학습): PyPI 공식 휠 numpy 2.4.6 cp313 win_amd64 — 개발 환경과 같은 판. PyTorch는 넣지 않는다(학습은 app/nn_train.py 가 numpy로).
구성: NNY_Simulator.exe(실행기) · runtime(파이썬) · app(이 코드) · viewer(record.py) · sim(엔진 · 카드 풀 · 덱) · data(split · cards · library)
"""
import argparse, compileall, glob, json, os, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
NNY = os.path.dirname(HERE)
APP_FILES = ['main.py', 'server.py', 'session.py', 'human.py', 'tables.py', 'learndata.py', 'nnai.py', 'nn_samples.py', 'nn_train.py']
DRL_FILES = ['__init__.py', 'agent.py', 'buffer.py', 'features.py', 'model.py', 'schema.py', 'side.py']   # drl/ 중 numpy만 쓰는 것(nets · learner · train 은 PyTorch)
NN_BASE_REL = ('learned', 'drl', 'base_v2', 'model_best.npz')   # nnai.BASE_REL 과 같은 자리
# 런타임에서 뺄 것(파이썬 표준 배포본 중 이 프로그램이 쓰지 않는 것)
PRUNE_DIRS = ['Lib/test', 'Lib/idlelib', 'Lib/tkinter', 'Lib/turtledemo', 'Lib/ensurepip', 'Lib/lib2to3', 'Lib/site-packages', 'Lib/venv',
              'Lib/pydoc_data', 'Lib/unittest/test', 'tcl', 'Tools', 'Doc', 'include', 'libs', 'Scripts']
PRUNE_FILES = ['DLLs/_tkinter.pyd', 'DLLs/tcl86t.dll', 'DLLs/tk86t.dll', 'Lib/turtle.py']
SIM_DATA = ['card_pool.json', 'learned/side.json']


def sh(*cmd, **kw):
    print('$', ' '.join(cmd)); subprocess.run(cmd, check=True, **kw)


def runtime(nupkg, dst):
    with zipfile.ZipFile(nupkg) as z:
        for m in z.namelist():
            if not m.startswith('tools/') or m.endswith('/'): continue
            rel = m[len('tools/'):]; out = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(m) as src, open(out, 'wb') as f: shutil.copyfileobj(src, f)
    for d in PRUNE_DIRS: shutil.rmtree(os.path.join(dst, d), ignore_errors=True)
    for f in PRUNE_FILES:
        try: os.remove(os.path.join(dst, f))
        except OSError: pass
    for p in glob.glob(os.path.join(dst, '**', '__pycache__'), recursive=True): shutil.rmtree(p, ignore_errors=True)


def sim_copy(sim, dst):
    os.makedirs(dst, exist_ok=True)
    for f in glob.glob(os.path.join(sim, '*.py')):
        b = os.path.basename(f)
        if b.startswith('test_'): continue
        shutil.copy2(f, dst)
    shutil.copytree(os.path.join(sim, 'blocks'), os.path.join(dst, 'blocks'), ignore=shutil.ignore_patterns('__pycache__', 'test*', 'tools'))
    for f in SIM_DATA:
        os.makedirs(os.path.dirname(os.path.join(dst, f)) or dst, exist_ok=True); shutil.copy2(os.path.join(sim, f), os.path.join(dst, f))
    os.makedirs(os.path.join(dst, 'decks'), exist_ok=True)
    for f in glob.glob(os.path.join(sim, 'decks', '*.deck')): shutil.copy2(f, os.path.join(dst, 'decks'))
    shutil.copytree(os.path.join(sim, 'learned', 'decks'), os.path.join(dst, 'learned', 'decks'))
    os.makedirs(os.path.join(dst, 'drl'))
    for f in DRL_FILES: shutil.copy2(os.path.join(sim, 'drl', f), os.path.join(dst, 'drl', f))


def numpy_install(wheel, runtime_dir):
    """numpy 휠을 런타임 site-packages 에 푼다(시험 폴더는 뺌)"""
    sp = os.path.join(runtime_dir, 'Lib', 'site-packages'); os.makedirs(sp, exist_ok=True)
    with zipfile.ZipFile(wheel) as z:
        for m in z.namelist():
            if m.endswith('/') or '/tests/' in m: continue
            out = os.path.join(sp, m); os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(m) as src, open(out, 'wb') as f: shutil.copyfileobj(src, f)


def icon(out):
    sys.path.insert(0, os.path.join(NNY, 'viewer')); import assets as AS
    im = AS.card_back(AS.face_ratio()); w, h = im.size; s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    im.save(out, sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])


def launcher(stage, version):
    win = os.path.join(HERE, 'win'); tmp = os.path.join(stage, '_build'); os.makedirs(tmp, exist_ok=True)
    icon(os.path.join(tmp, 'app.ico'))
    rc = open(os.path.join(win, 'resource.rc'), encoding='utf-8').read()
    nums = (version.split('.') + ['0'] * 4)[:4]
    rc = rc.replace('__VER_COMMA__', ','.join(nums)).replace('__VER__', version)
    open(os.path.join(tmp, 'resource.rc'), 'w', encoding='utf-8').write(rc)
    sh('x86_64-w64-mingw32-windres', 'resource.rc', '-O', 'coff', '-o', 'resource.o', cwd=tmp)
    sh('x86_64-w64-mingw32-gcc', '-municode', '-mwindows', '-O2', '-s', os.path.join(win, 'launcher.c'), 'resource.o',
       '-o', os.path.join(stage, 'NNY_Simulator.exe'), cwd=tmp)
    shutil.rmtree(tmp)


README = """뉴 네오 유희왕 시뮬레이터 (Windows) — v{ver}

실행: 이 폴더의 NNY_Simulator.exe 를 두 번 누르세요. Microsoft Edge 앱 창(없으면 기본 브라우저)으로 게임 화면이 열립니다.
      인터넷은 필요 없습니다. 창을 닫으면 몇 분 안에 프로그램도 저절로 꺼집니다(화면의 「종료」로 바로 끌 수도 있음).
처음 실행 때 Windows가 「알 수 없는 게시자」 경고(SmartScreen)를 보이면 「추가 정보 → 실행」을 누르세요(서명하지 않은 프로그램).

기능
- 관전 · 재생 목록: 기본 제공 AI 대전 녹화를 골라 재생 목록을 만들고 이어서 재생. 새 AI 대전을 녹화할 수도 있음(학습표 AI끼리 · 휴리스틱 AI끼리).
- AI 대전: 나 vs AI(학습표 AI · 신경망 AI · 휴리스틱 AI 중 고름) Bo3. 판단 패널에서 행동 · 대상 · 서치와 카드 효과 처리 중의 선택(선택지 · 소환할 몬스터 · 카운터 등)을 고릅니다.
  라운드 사이에는 전략 덱 교체 패널에서 넣을 카드 → 뺄 카드를 골라 바꾸고 「교체 끝」을 누릅니다. AI vs AI 실시간 관전도 가능.
  시작 패는 메인 · 상급 덱에서 몇 장씩 뽑을지 직접 고르고, 멀리건 때도 처음과 다른 비율로 다시 뽑을 수 있습니다(AI도 같음).
  몬스터 · 마법 카드를 놓을 존과 소환 표시 형식(앞면 공격 · 앞면 수비)도 직접 고릅니다.
  제물 소환의 제물, 포커짐승들 족보 재료, 「원하는 레벨과 원하는 속성」 부여 · 짐승조커 선언, 번식지로 패에 넣을 카드도 직접 고릅니다(1.2.1).
  대전 중에는 상대 AI가 전략 덱에서 무엇을 바꿨는지 보이지 않고, 대전이 끝난 뒤 재생 기록에서 뺀 카드 · 넣은 카드 이미지로 볼 수 있습니다.
- 덱 편집: 카드 풀에서 덱을 짜고 규칙 검사 후 저장 → AI 대전 · 녹화에 사용.
- 학습: 「AI 학습」을 켜고 대전하면 매치가 끝날 때 AI가 그 판단 기록으로 학습(프로그램 안에서 바로 반영).
  기록은 사용자 폴더에 쌓이고, 「학습」 화면에서 내보내거나(인터넷 없이) GitHub에 올릴 수 있습니다(인터넷 · git 필요).
- 🧠 신경망 학습(화면 위쪽 막대): 「AI 학습」을 켠 나 vs AI 대전에서 쌓인 신경망 표본으로, 원할 때 신경망 AI를 내 컴퓨터에서 학습합니다(인터넷 불필요).
  AI 대전에서 AI 종류를 「신경망 AI」로 고르면 학습한 내 모델(없으면 기본 모델)과 대전합니다. 「기본 모델로 되돌리기」로 언제든 처음 상태로.
  같은 창의 「신경망 내보내기」(zip — GitHub 웹에서 저장소 nny_sim/learned/drl/human_nn/ 에 올림) · 「GitHub에 올리기」(인터넷 · git 필요)로 표본과 내 모델을 저장소에 모을 수 있습니다.

사용자 폴더(덱 · 재생 기록 · 학습 기록 · 설정): %LOCALAPPDATA%\\NNY_Simulator
  (이 폴더 안에 userdata 폴더를 만들어 두면 그곳을 씁니다 — USB 등 휴대용으로 쓸 때)
문제가 생기면: NNY_Simulator_콘솔.bat 로 실행하면 오류 내용이 창에 보입니다. 사용자 폴더의 app.log 에도 남습니다.

구성: runtime(파이썬 {py} — 파이썬 재단 NuGet 공식 패키지, numpy {np} — PyPI 공식 휠), app(프로그램),
      sim(시뮬레이션 엔진 · 카드 풀 · 덱 · 신경망 코드 drl · 기본 신경망 모델 learned/drl/base_v2),
      data/split(대전별 학습표 — data/main 의 policy.json.xz 를 나눈 것), data/cards(카드 이미지), data/library(기본 재생 기록)
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sim', required=True); ap.add_argument('--nupkg', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--split'); ap.add_argument('--library'); ap.add_argument('--version')
    ap.add_argument('--numpy-wheel', required=True); ap.add_argument('--nn-base', help='기본 신경망 모델(기본: <sim>/learned/drl/base_v2/model_best.npz)')
    a = ap.parse_args(argv)
    sys.path.insert(0, HERE)
    import re
    version = a.version or re.search(r"^VERSION = '([^']+)'", open(os.path.join(HERE, 'server.py'), encoding='utf-8').read(), re.M).group(1)
    stage = os.path.join(os.path.abspath(a.out), 'NNY_Simulator')
    shutil.rmtree(stage, ignore_errors=True); os.makedirs(stage)
    runtime(a.nupkg, os.path.join(stage, 'runtime'))
    numpy_install(a.numpy_wheel, os.path.join(stage, 'runtime'))
    os.makedirs(os.path.join(stage, 'app'))
    for f in APP_FILES: shutil.copy2(os.path.join(HERE, f), os.path.join(stage, 'app', f))
    shutil.copytree(os.path.join(HERE, 'static'), os.path.join(stage, 'app', 'static'))
    os.makedirs(os.path.join(stage, 'viewer')); shutil.copy2(os.path.join(NNY, 'viewer', 'record.py'), os.path.join(stage, 'viewer'))
    sim = os.path.abspath(a.sim); sim_copy(sim, os.path.join(stage, 'sim'))
    nn_dst = os.path.join(stage, 'sim', *NN_BASE_REL); os.makedirs(os.path.dirname(nn_dst), exist_ok=True)
    shutil.copy2(a.nn_base or os.path.join(sim, *NN_BASE_REL), nn_dst)
    data = os.path.join(stage, 'data')
    import tables as T
    if a.split: shutil.copytree(a.split, os.path.join(data, 'split'))
    else:
        import lzma
        T.split(os.path.join(sim, 'learned', 'policy.json.xz'), os.path.join(data, 'split'),
                read=lambda p: json.load(lzma.open(p, 'rt', encoding='utf-8')))
    import build_assets
    build_assets.build(os.path.join(data, 'cards'))
    if a.library: shutil.copytree(a.library, os.path.join(data, 'library'))
    else: os.makedirs(os.path.join(data, 'library'))
    launcher(stage, version)
    with open(os.path.join(stage, 'NNY_Simulator_콘솔.bat'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('@echo off\r\nchcp 65001 > nul\r\ncd /d "%~dp0"\r\n"runtime\\python.exe" -I -X utf8 "app\\main.py" %*\r\npause\r\n')
    pyver = os.path.basename(a.nupkg).replace('python.', '').replace('.nupkg', '')
    npver = os.path.basename(a.numpy_wheel).split('-')[1]
    with open(os.path.join(stage, '읽어보기.txt'), 'w', encoding='utf-8-sig', newline='\r\n') as f: f.write(README.format(ver=version, py=pyver, np=npver))
    # 바이트코드 미리 만들기(같은 3.13 — 첫 실행을 빠르게, 쓰기 금지 폴더에서도)
    for d in ('app', 'viewer', 'sim'): compileall.compile_dir(os.path.join(stage, d), quiet=1, workers=0)
    z = os.path.join(os.path.abspath(a.out), f'NNY_Simulator_v{version}_win64.zip')
    if os.path.exists(z): os.remove(z)
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, _, files in os.walk(stage):
            for fn in files:
                p = os.path.join(root, fn); zf.write(p, os.path.relpath(p, os.path.dirname(stage)))
    print(z, f'{os.path.getsize(z) / 1e6:.1f}MB')


if __name__ == '__main__':
    main()
