"""기능 v1 — 인게임 메신저(수다+로그수집) 자동 스모크: python -m unittest test_online_chat -v
방(room) 전체 공용 채팅 1개(매치별 구분 없음 — "방 1·듀얼 1"이라 나눌 의미가 없음): 보내기(App.chat_post/
/api/room/chat) · 커서 기반 증분 읽기(App.chat_since, heartbeat/boot 의 chat_from) · 빈 글·너무 긴 글·
방 밖에서 보내기 거부 · 매치가 끝날 때 그 구간의 채팅이 기보(push_game 경로)에 같이 묶여 올라가고
index.json 에 chat 개수가 반영되는지를 확인한다. 엔진·룰 레이어는 건드리지 않음(app 레이어 쪼가리만).
"""
import json, os, shutil, subprocess, sys, tempfile, threading, time, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import server as S
import session as SESS


def req(base, token, method, path, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                                headers={'X-NNY-Token': token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp: return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as ex: return ex.code, json.loads(ex.read())


def git(*args, cwd):
    r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout.strip()


class ChatBufferTest(unittest.TestCase):
    """App 레벨 — 서버를 안 띄우고 App 객체만으로 링버퍼·커서·검증 규칙을 확인."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_chat_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': os.path.join(self.tmp, 'user'), 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}
        self.app = S.App(self.paths)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_post_requires_room_membership(self):
        with self.assertRaises(ValueError):
            self.app.chat_post('25.0.0.11', '방에 안 들어가고 보내기')

    def test_empty_and_too_long_rejected(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        with self.assertRaises(ValueError):
            self.app.chat_post('25.0.0.11', '   ')   # 빈 글(공백만)
        with self.assertRaises(ValueError):
            self.app.chat_post('25.0.0.11', 'ㅁ' * (S.CHAT_MAX + 1))   # 너무 긴 글
        ok = self.app.chat_post('25.0.0.11', 'ㅁ' * S.CHAT_MAX)   # 정확히 한도까지는 통과
        self.assertEqual(len(ok['text']), S.CHAT_MAX)

    def test_post_and_incremental_cursor(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        self.app.room_join('25.0.0.12', '관전자', 'spectator')
        m1 = self.app.chat_post('25.0.0.11', '안녕')
        m2 = self.app.chat_post('25.0.0.12', '어 왔네')   # 관전자도 쓸 수 있음
        self.assertEqual(m1['who'], '성창'); self.assertEqual(m2['who'], '관전자')
        self.assertLess(m1['id'], m2['id'])
        all_msgs = self.app.chat_since(0)
        self.assertEqual([m['text'] for m in all_msgs], ['안녕', '어 왔네'])
        after1 = self.app.chat_since(m1['id'])
        self.assertEqual([m['id'] for m in after1], [m2['id']], '커서 이전 메시지가 다시 와서는 안 된다')
        after2 = self.app.chat_since(m2['id'])
        self.assertEqual(after2, [], '마지막까지 받은 뒤에는 새 메시지가 없어야 한다')

    def test_ring_buffer_bounded_but_ids_keep_increasing(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        for i in range(S.CHAT_BUFFER + 20):
            self.app.chat_post('25.0.0.11', f'메시지 {i}')
        self.assertEqual(len(self.app.chat), S.CHAT_BUFFER)   # 링버퍼 한도
        self.assertEqual(self.app.chat_seq, S.CHAT_BUFFER + 20)   # id 자체는 끊기지 않고 계속 늘어남
        self.assertEqual(self.app.chat[0]['text'], '메시지 20')   # 앞의 20개는 밀려남

    def test_chat_between_filters_by_timestamp_window(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        t0 = time.time()
        m1 = self.app.chat_post('25.0.0.11', '매치 중 채팅')
        t1 = time.time()
        self.assertEqual(self.app.chat_between(t0, t1), [m1])
        self.assertEqual(self.app.chat_between(t1 + 1, t1 + 2), [], '구간 밖의 메시지는 걸러져야 한다')


class ChatHttpTest(unittest.TestCase):
    """실제 HTTP(서버 기동) — boot/heartbeat 의 chat_from 커서, /api/room/chat 엔드포인트."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_chat_http_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': os.path.join(self.tmp, 'user'), 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}
        self.app, self.srv = S.serve(self.paths, port=0, host='127.0.0.1')
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        self.token = self.app.token
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        if self.app.live: self.app.live.abort()
        self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_chat_endpoint_rejects_outside_room(self):
        st, body = req(self.base, self.token, 'POST', '/api/room/chat', {'text': '방에 안 들어감'})
        self.assertEqual(st, 400, body)

    def test_boot_and_heartbeat_carry_new_chat_only_since_cursor(self):
        self.app.room_join('127.0.0.1', '테스터', 'player')   # 테스트 클라이언트는 항상 127.0.0.1 로 옴
        st, m1 = req(self.base, self.token, 'POST', '/api/room/chat', {'text': '첫 메시지'})
        self.assertEqual(st, 200, m1)
        st, boot = req(self.base, self.token, 'GET', '/api/boot')
        self.assertEqual(st, 200)
        self.assertEqual([x['text'] for x in boot['chat']], ['첫 메시지'])
        st, hb = req(self.base, self.token, 'POST', '/api/heartbeat', {'chat_from': m1['id']})
        self.assertEqual(st, 200, hb)
        self.assertEqual(hb['chat'], [], '커서를 넘긴 뒤에는 같은 메시지가 다시 오면 안 된다')
        st, m2 = req(self.base, self.token, 'POST', '/api/room/chat', {'text': '두 번째'})
        st, hb2 = req(self.base, self.token, 'POST', '/api/heartbeat', {'chat_from': m1['id']})
        self.assertEqual([x['text'] for x in hb2['chat']], ['두 번째'], '커서 이후에 온 것만 와야 한다')
        st, hb3 = req(self.base, self.token, 'POST', '/api/heartbeat', {'chat_from': 0})
        self.assertEqual([x['text'] for x in hb3['chat']], ['첫 메시지', '두 번째'], 'chat_from=0 이면 처음부터 다시 받을 수 있다')

    def test_empty_and_too_long_rejected_over_http(self):
        self.app.room_join('127.0.0.1', '테스터', 'player')
        st, body = req(self.base, self.token, 'POST', '/api/room/chat', {'text': '   '})
        self.assertEqual(st, 400, body)
        st, body = req(self.base, self.token, 'POST', '/api/room/chat', {'text': 'ㅁ' * (S.CHAT_MAX + 1)})
        self.assertEqual(st, 400, body)


class ChatPushGameTest(unittest.TestCase):
    """기보 수집(⑥) 경로 재사용 — 매치가 끝날 때 그 구간의 채팅이 기보(replay)에 chat 필드로 묶여
    online/data-games 에 같이 올라가고, index.json 의 chat 개수에도 반영되는지. 로컬 bare repo 를
    가짜 origin 으로 써서 실제 GitHub 에는 전혀 닿지 않는다(test_push_games.py 와 같은 방식)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_chatpush_')
        self.origin = os.path.join(self.tmp, 'origin.git')
        git('init', '--bare', '-b', 'online/data-games', self.origin, cwd=self.tmp)
        seed = os.path.join(self.tmp, 'seed')
        git('clone', self.origin, seed, cwd=self.tmp)
        with open(os.path.join(seed, 'README.md'), 'w', encoding='utf-8') as f: f.write('기보\n')
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'add', 'README.md', cwd=seed)
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-m', 'seed', cwd=seed)
        git('push', 'origin', 'HEAD:online/data-games', cwd=seed)
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': os.path.join(self.tmp, 'user'), 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}
        self.app, self.srv = S.serve(self.paths, port=0, host='127.0.0.1')
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        self.token = self.app.token
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.app.store.save_settings({'git_url': self.origin})   # push_games 는 기본 꺼짐 — 테스트에선 push_game 을 직접 부름

    def tearDown(self):
        if self.app.live: self.app.live.abort()
        self.srv.shutdown(); self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _clone_data_games(self, name='verify'):
        dst = os.path.join(self.tmp, name)
        git('clone', '-b', 'online/data-games', self.origin, dst, cwd=self.tmp)
        return dst

    def decks(self):
        st, d = req(self.base, self.token, 'GET', '/api/decks')
        self.assertEqual(st, 200)
        ids = [x['id'] for x in d if x['kind'] == 'official' and x['valid']]
        self.assertGreaterEqual(len(ids), 2)
        return ids[0], ids[1]

    def _run_human_vs_ai_to_done(self, mid):
        """idx=0(가장 앞 선택지)로만 응답해 사람vsAI 매치를 자연스럽게 끝까지 돌린다(test_online_pvp.py 와 같은 방식).
        status 가 끝남으로 바뀌는 순간과 replay_id 가 채워지는 순간 사이에는 틈이 있다(_run() 의 finally 블록이
        save_replay 를 아직 못 돌렸을 수 있음 — 엔진 스레드와 poll 호출 사이의 원래 있던 레이스, 이번에 새로 만든
        문제 아님) — status 가 끝난 뒤에도 replay_id 가 비어 있으면 몇 번 더 poll 해 기다린다."""
        p = None
        for _ in range(600):
            st, p = req(self.base, self.token, 'GET', f'/api/match/poll?id={mid}')
            if p['pending']:
                req(self.base, self.token, 'POST', '/api/match/answer', {'rid': p['pending']['id'], 'idx': 0})
            elif p['status'] not in ('starting', 'running'):
                break
            else:
                time.sleep(0.02)
        else:
            self.fail('매치가 끝나지 않았다(idx=0 반복 응답으로도 600번 안에 안 끝남)')
        for _ in range(100):
            if p['replay_id']: return p
            time.sleep(0.05)
            st, p = req(self.base, self.token, 'GET', f'/api/match/poll?id={mid}')
        self.fail('매치는 끝났지만 replay_id 가 끝내 채워지지 않았다(저장이 실패했거나 너무 오래 걸림)')

    def test_chat_during_match_is_attached_to_replay_and_pushed(self):
        self.app.room_join('127.0.0.1', '성창', 'player')
        d1, d2 = self.decks()
        st, start = req(self.base, self.token, 'POST', '/api/match/start',
                        {'deck': d1, 'ai_deck': d2, 'mode': 'human', 'learn': False})
        self.assertEqual(st, 200, start)
        mid = start['id']
        # 매치가 떠 있는 동안 채팅 2개
        req(self.base, self.token, 'POST', '/api/room/chat', {'text': '이거 체인 순서 이상한데'})
        req(self.base, self.token, 'POST', '/api/room/chat', {'text': '어 그러네'})
        result = self._run_human_vs_ai_to_done(mid)
        self.assertIsNotNone(result['replay_id'])
        rec = self.app.store.replay(result['replay_id'])
        self.assertEqual(len(rec.get('chat') or []), 2, '매치가 떠 있던 동안의 채팅 2개가 기보에 묶여야 한다')
        self.assertEqual([m['text'] for m in rec['chat']], ['이거 체인 순서 이상한데', '어 그러네'])
        reps = self.app.store.replays()
        self.assertEqual(next(x for x in reps if x['id'] == result['replay_id'])['chat'], 2,
                          'index.json 류 메타(여기선 사용자 폴더 index) 에도 memos 와 같은 식으로 chat 개수가 반영돼야 한다')
        # push_game(⑥) 경로로 online/data-games 에 올리면 거기 index.json 에도 chat 개수가 그대로 실린다
        self.app.store.push_game(result['replay_id'])
        status = self.app.store.last_game_push()
        self.assertTrue(status and status['ok'], status)
        verify = self._clone_data_games()
        key = result['replay_id'].split(':', 1)[1]
        idx = json.load(open(os.path.join(verify, 'index.json'), encoding='utf-8'))
        self.assertIn(key, idx)
        self.assertEqual(idx[key]['chat'], 2)
        self.assertEqual(idx[key]['memos'], 0)

    def test_match_without_chat_has_zero_chat_count(self):
        d1, d2 = self.decks()
        st, start = req(self.base, self.token, 'POST', '/api/match/start',
                        {'deck': d1, 'ai_deck': d2, 'mode': 'human', 'learn': False})
        self.assertEqual(st, 200, start)
        result = self._run_human_vs_ai_to_done(start['id'])
        rec = self.app.store.replay(result['replay_id'])
        self.assertEqual(rec.get('chat') or [], [])
        reps = self.app.store.replays()
        self.assertEqual(next(x for x in reps if x['id'] == result['replay_id'])['chat'], 0)


class ChatDeleteTest(unittest.TestCase):
    """기능 v1 — 인게임 메신저 「메시지 삭제」(「다음 회차 지시」 2번 후보의 절반, 수정은 이번 범위 밖).
    자신이 보낸 메시지만 삭제할 수 있고, 삭제하면 원본은 그 자리에서 (삭제됨)으로 바뀌면서 이미 그
    원문을 받아 그려둔 화면에도 알릴 수 있도록 kind='delete' 이벤트가 새 id로 하나 더 올라간다."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_chatdel_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards, exist_ok=True)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.paths = {'sim': os.path.abspath('.'), 'split': os.path.join(self.tmp, 'split'),
                      'cards': cards, 'library': os.path.join(self.tmp, 'library'),
                      'user': os.path.join(self.tmp, 'user'), 'static': os.path.abspath('app/static'),
                      'viewer': os.path.abspath('viewer')}
        self.app = S.App(self.paths)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_delete_requires_room_membership(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        m = self.app.chat_post('25.0.0.11', '안녕')
        with self.assertRaises(ValueError):
            self.app.chat_delete('25.0.0.99', m['id'])   # 방에 없는 ip

    def test_delete_rejects_unknown_message_id(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        with self.assertRaises(ValueError):
            self.app.chat_delete('25.0.0.11', 999999)

    def test_delete_rejects_other_users_message(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        self.app.room_join('25.0.0.12', '관전자', 'spectator')
        m = self.app.chat_post('25.0.0.11', '성창이 보낸 글')
        with self.assertRaises(ValueError):
            self.app.chat_delete('25.0.0.12', m['id'])   # 남의 글은 못 지운다
        after = self.app.chat_since(0)
        self.assertFalse(after[-1].get('deleted'), '거부됐으면 원본이 그대로 남아야 한다')

    def test_delete_marks_original_and_emits_event_once(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        m = self.app.chat_post('25.0.0.11', '지울 메시지')
        ev = self.app.chat_delete('25.0.0.11', m['id'])
        self.assertEqual(ev['kind'], 'delete'); self.assertEqual(ev['target'], m['id'])
        self.assertGreater(ev['id'], m['id'], '삭제 이벤트는 새 id를 받아야 한다(기존 메시지 id 재사용 금지)')
        all_msgs = self.app.chat_since(0)
        orig = next(x for x in all_msgs if x['id'] == m['id'])
        self.assertTrue(orig['deleted']); self.assertEqual(orig['text'], '', '원본 텍스트는 그 자리에서 비워야 한다')
        self.assertEqual([x['kind'] for x in all_msgs], ['msg', 'delete'])
        with self.assertRaises(ValueError):
            self.app.chat_delete('25.0.0.11', m['id'])   # 두 번 지우기는 거부

    def test_chat_owner_pruned_when_ring_buffer_evicts(self):
        self.app.room_join('25.0.0.11', '성창', 'player')
        first = self.app.chat_post('25.0.0.11', '첫 메시지')
        for i in range(S.CHAT_BUFFER):   # 버퍼를 꽉 채워 first 를 밀어낸다
            self.app.chat_post('25.0.0.11', f'메시지 {i}')
        self.assertNotIn(first['id'], self.app.chat_owner, '링버퍼에서 밀려난 메시지의 소유자 기록도 같이 지워져야 한다')
        self.assertLessEqual(len(self.app.chat_owner), S.CHAT_BUFFER, '소유자 dict 가 버퍼 크기보다 무한정 커지면 안 된다')
        with self.assertRaises(ValueError):
            self.app.chat_delete('25.0.0.11', first['id'])   # 밀려난 메시지는 더 이상 삭제 대상이 아님

    def test_delete_endpoint_over_http(self):
        tmp = tempfile.mkdtemp(prefix='nny_chatdel_http_')
        try:
            cards = os.path.join(tmp, 'cards'); os.makedirs(cards, exist_ok=True)
            with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
                json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
            paths = {'sim': os.path.abspath('.'), 'split': os.path.join(tmp, 'split'),
                     'cards': cards, 'library': os.path.join(tmp, 'library'),
                     'user': os.path.join(tmp, 'user'), 'static': os.path.abspath('app/static'),
                     'viewer': os.path.abspath('viewer')}
            app, srv = S.serve(paths, port=0, host='127.0.0.1')
            base = f'http://127.0.0.1:{srv.server_address[1]}'
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                app.room_join('127.0.0.1', '테스터', 'player')   # 테스트 클라이언트는 항상 127.0.0.1 로 옴
                st, m = req(base, app.token, 'POST', '/api/room/chat', {'text': '지울 글'})
                self.assertEqual(st, 200, m)
                st, ev = req(base, app.token, 'POST', '/api/room/chat/delete', {'id': m['id']})
                self.assertEqual(st, 200, ev); self.assertEqual(ev['kind'], 'delete')
                st, again = req(base, app.token, 'POST', '/api/room/chat/delete', {'id': m['id']})
                self.assertEqual(st, 400, again)   # 이미 지운 것을 또 지우면 400(ValueError)
            finally:
                if app.live: app.live.abort()
                srv.shutdown(); srv.server_close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
