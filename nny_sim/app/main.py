"""뉴 네오 유희왕 시뮬레이터 — 실행 진입점.

배포 폴더 구성(build_windows.py): <root>/app(이 코드) · viewer · sim(엔진 · 카드 풀 · 덱) · data/split(대전별 학습표) · data/library(재생 기록) ·
data/cards(카드 이미지) · userdata(덱 · 재생 기록 · 학습 기록 · 설정 — 프로그램이 만든다).
개발: python3 nny_sim/app/main.py --sim <실행 폴더> --split <분할 표> --cards <이미지> --user <사용자 폴더>
"""
import argparse, json, os, subprocess, sys, threading, time, urllib.request, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def default_user_dir():
    """사용자 폴더(덱 · 재생 기록 · 학습 기록 · 설정). 프로그램 폴더에 userdata 가 있으면 그곳(휴대용),
    없으면 Windows 는 %LOCALAPPDATA%\\NNY_Simulator — 새 버전을 받아도 학습 기록 · 덱이 남는다"""
    portable = os.path.join(ROOT, 'userdata')
    if os.path.isdir(portable) or sys.platform != 'win32' or not os.environ.get('LOCALAPPDATA'): return portable
    return os.path.join(os.environ['LOCALAPPDATA'], 'NNY_Simulator')


def paths_from(a):
    p = {'sim': a.sim or os.path.join(ROOT, 'sim'), 'split': a.split or os.path.join(ROOT, 'data', 'split'),
         'cards': a.cards or os.path.join(ROOT, 'data', 'cards'), 'library': a.library or os.path.join(ROOT, 'data', 'library'),
         'user': a.user or default_user_dir(), 'static': os.path.join(HERE, 'static'),
         'viewer': a.viewer or os.path.join(ROOT, 'viewer')}
    return {k: os.path.abspath(v) for k, v in p.items()}


def running_port(user):
    """이미 떠 있는 서버(같은 사용자 폴더)가 있으면 그 포트"""
    try:
        info = json.load(open(os.path.join(user, 'server.json'), encoding='utf-8'))
        with urllib.request.urlopen(f'http://127.0.0.1:{info["port"]}/api/ping', timeout=1.5) as r:
            if json.load(r).get('app') == 'nny-sim': return info['port']
    except Exception: pass
    return None


def open_window(url, user):
    """Edge 앱 창(주소창 없는 창)으로 연다. Edge가 없으면 기본 브라우저"""
    if sys.platform == 'win32':
        for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LOCALAPPDATA')):
            exe = base and os.path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe')
            if exe and os.path.exists(exe):
                try:
                    subprocess.Popen([exe, f'--app={url}', '--no-first-run', '--window-size=1600,1000',
                                      f'--user-data-dir={os.path.join(user, "edge")}']); return
                except OSError: pass
    webbrowser.open(url)


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ('sim', 'split', 'cards', 'library', 'user', 'viewer'): ap.add_argument('--' + k)
    ap.add_argument('--port', type=int, default=0); ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args(argv)
    P = paths_from(a)
    os.makedirs(P['user'], exist_ok=True)
    if sys.stderr is None or sys.stdout is None:   # 창 없는 실행(pythonw): 출력 · 오류를 사용자 폴더의 app.log 로
        log = open(os.path.join(P['user'], 'app.log'), 'a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stdout or log; sys.stderr = sys.stderr or log
    port = running_port(P['user'])
    if port:
        if not a.no_browser: open_window(f'http://127.0.0.1:{port}/', P['user'])
        return
    sys.path[:0] = [P['sim'], P['viewer'], HERE]
    os.chdir(P['sim'])   # 엔진은 상대 경로(card_pool.json · decks · learned)를 쓴다
    import server
    app, srv = server.serve(P, a.port)
    port = srv.server_address[1]
    with open(os.path.join(P['user'], 'server.json'), 'w', encoding='utf-8') as f:
        json.dump({'port': port, 'pid': os.getpid()}, f)
    url = f'http://127.0.0.1:{port}/'
    print(f'NNY 시뮬레이터 {server.VERSION} — {url}', flush=True)
    if not a.no_browser: threading.Timer(0.5, open_window, (url, P['user'])).start()
    try: srv.serve_forever()
    finally:
        try: os.remove(os.path.join(P['user'], 'server.json'))
        except OSError: pass


if __name__ == '__main__':
    main()
