"""화면 필드 갱신 시험(화면 없이, 사용자 지시 2026-10-30 「효과가 처리된 상황에서 화면에는 효과 처리 이전 화면의 필드 상황만 보이는 현상」):
나 vs AI(가짜 사람 — 무작위 답)에서 사람에게 묻는 순간마다, 화면이 받는 마지막 프레임의 상태가 엔진의 지금 상태와 같은지(viewer/record.Recorder.sync).
python3 board_sync_test.py <sim> <split> <cards> <library> <시험용 사용자 폴더>"""
import sys, os, time, random, shutil, json
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM, SPLIT, CARDS, LIB, USER = (os.path.abspath(x) for x in sys.argv[1:6]); sys.argv = ['x']
sys.path[:0] = [SIM, os.path.join(os.path.dirname(APP), 'viewer'), APP]
os.chdir(SIM)
import server
shutil.rmtree(USER, ignore_errors=True)
app = server.App({'sim': SIM, 'split': SPLIT, 'cards': CARDS, 'library': LIB, 'user': USER, 'static': APP + '/static',
                  'viewer': os.path.join(os.path.dirname(APP), 'viewer')})
rng = random.Random(9); asked = stale = syncs = 0
key = lambda st: json.dumps(st, sort_keys=True, ensure_ascii=False)
for da, db, seed in [('데이터버그 패키지 프로그램', '던전마스터 셔플!', 3), ('소원의 분수', '세제', 4)]:
    r = app.start_match({'mode': 'human', 'deck': 'o:' + da, 'ai_deck': 'o:' + db, 'first': 'me', 'seed': seed, 'learn': False}); lid = r['id']
    f = s = c = 0; t0 = time.time(); S = []
    while time.time() - t0 < 400:
        res = app.route('GET', '/api/match/poll', {'id': [lid], 'f': [str(f)], 's': [str(s)], 'c': [str(c)]}, {})
        S += res['states']; fr = res['frames']; f += len(fr); s += len(res['states']); c += len(res['cards'])
        syncs += sum(1 for x in fr if x['k'] == 'sync')
        pd = res['pending']
        if pd:
            rec = app.live.rec
            if pd['kind'] == 'choose' and rec.game is not None and f:
                last = next((x['s'] for x in reversed(rec.export_frames(0)[:f]) if x['s'] >= 0), -1)
                asked += 1; stale += int(last < 0 or key(S[last]) != key(rec.state(rec.game)))
            app.route('POST', '/api/match/answer', {}, {'rid': pd['id'], 'idx': 0 if pd['kind'] == 'side' else rng.randrange(len(pd['opts']))})
        elif res['status'] not in ('starting', 'running'): break
        time.sleep(0.003)
print(f'질문 {asked}번 · 화면이 엔진보다 뒤처진 질문 {stale}번 · sync 프레임 {syncs}개')
ok = asked > 0 and stale == 0
print('결과:', '통과' if ok else '실패'); sys.exit(0 if ok else 1)
