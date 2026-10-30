"""기능 v1⑥ 기보 수집 자동 스모크: python -m unittest test_push_games -v
매치가 끝나거나(메모 없이도) 메모가 새로 붙을 때마다 Store.push_game 이 online/data-games 에 기보(재생+메모)를
올리고, 1순위(수정 고리)가 쓸 실제 커밋 해시를 기보 메타에 되돌려 적는지 확인한다. 가짜 origin(로컬 bare repo)만
쓰고 실제 GitHub 에는 전혀 닿지 않음 — 엔진·룰 레이어는 건드리지 않음(저장소 쪼가리만).
"""
import json, os, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import session as SESS


def git(*args, cwd):
    r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout.strip()


def dummy_rec(title='A vs B'):
    return {'schema': 1, 'meta': {'names': ['A', 'B'], 'decks': ['스킬1', '스킬2'], 'winner': 0, 'status': 'done',
                                   'created': SESS.now(), 'rounds': [], 'title': title},
            'cards': {}, 'pool': {}, 'states': [], 'frames': [{'k': 'act', 'm': '발동: 더미'}]}


class ImmediateThread:
    """threading.Thread 대신 끼워 넣어 백그라운드 push_game 호출을 그 자리에서 바로(동기로) 실행시킨다."""
    def __init__(self, target=None, args=(), daemon=None): self.target, self.args = target, args
    def start(self): self.target(*self.args)


class PushGameTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_push_')
        self.origin = os.path.join(self.tmp, 'origin.git')
        git('init', '--bare', '-b', 'online/data-games', self.origin, cwd=self.tmp)
        seed = os.path.join(self.tmp, 'seed')   # 실제 online/data-games 모양(README.md 만 있는 빈 브랜치) 재현
        git('clone', self.origin, seed, cwd=self.tmp)
        with open(os.path.join(seed, 'README.md'), 'w', encoding='utf-8') as f: f.write('기보\n')
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'add', 'README.md', cwd=seed)
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-m', 'seed', cwd=seed)
        git('push', 'origin', 'HEAD:online/data-games', cwd=seed)
        self.store = SESS.Store(os.path.join(self.tmp, 'user'))
        self.store.save_settings({'git_url': self.origin, 'push_games': True})   # 기본값은 False(auto_push와 같은 이유 — 꺼짐이 기본)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _clone_data_games(self, name='verify'):
        dst = os.path.join(self.tmp, name)
        git('clone', '-b', 'online/data-games', self.origin, dst, cwd=self.tmp)
        return dst

    def test_match_end_pushes_record_and_stamps_real_commit_hash(self):
        rid = 'u:' + self.store.save_replay(dummy_rec())
        self.store.push_game(rid)
        status = self.store.last_game_push()
        self.assertTrue(status and status['ok'], status)
        verify = self._clone_data_games()
        key = rid.split(':', 1)[1]
        idx = json.load(open(os.path.join(verify, 'index.json'), encoding='utf-8'))
        self.assertIn(key, idx)
        self.assertEqual(idx[key]['memos'], 0)
        self.assertTrue(os.path.isfile(os.path.join(verify, 'games', key + '.json.gz')))
        self.assertTrue(idx[key]['commit'])   # 1순위가 재현에 쓸 해시
        # 기록된 해시가 실제로 존재하는, 그 기보 파일을 담고 있는 커밋이어야 한다(두 번째 커밋이 적는 해시는 그
        # 바로 앞 — 실제로 파일을 올린 — 커밋을 가리킨다; 자기 자신의 해시는 같은 커밋에 미리 넣을 수 없음)
        git('cat-file', '-e', f"{idx[key]['commit']}:games/{key}.json.gz", cwd=verify)
        self.assertNotEqual(idx[key]['commit'], git('log', '-1', '--format=%H', cwd=verify))

    def test_memo_added_later_triggers_repush_with_updated_memo_count(self):
        orig_thread = SESS.threading.Thread
        SESS.threading.Thread = ImmediateThread
        try:
            rid = 'u:' + self.store.save_replay(dummy_rec())
            self.store.push_game(rid)   # 1차: 메모 0개로 끝난 매치
            self.store.add_memo(rid, [{'i': 0, 'text': '체인 처리 순서 확인 필요', 'who': 'A'}])   # push_games 기본값(True) → 즉시 재수집
        finally:
            SESS.threading.Thread = orig_thread
        verify = self._clone_data_games('verify2')
        key = rid.split(':', 1)[1]
        idx = json.load(open(os.path.join(verify, 'index.json'), encoding='utf-8'))
        self.assertEqual(idx[key]['memos'], 1)
        self.assertTrue(idx[key]['commit'])

    def test_push_games_off_means_add_memo_does_not_schedule_push(self):
        self.store.save_settings({'push_games': False})
        started = []

        class SpyThread:
            def __init__(self, target=None, args=(), daemon=None): started.append((target, args))
            def start(self): pass

        orig_thread = SESS.threading.Thread
        SESS.threading.Thread = SpyThread
        try:
            rid = 'u:' + self.store.save_replay(dummy_rec())
            self.store.add_memo(rid, [{'i': 0, 'text': '확인 필요', 'who': 'A'}])
        finally:
            SESS.threading.Thread = orig_thread
        self.assertEqual(started, [])

    def test_bad_git_url_fails_gracefully_without_raising(self):
        self.store.save_settings({'git_url': os.path.join(self.tmp, '없는-저장소.git')})
        rid = 'u:' + self.store.save_replay(dummy_rec())
        self.store.push_game(rid)   # 예외 없이 끝나야 함
        status = self.store.last_game_push()
        self.assertFalse(status['ok'])

    def test_push_now_works_even_when_push_games_setting_is_off(self):
        """push_games 수동 '지금 올리기' 버튼 — 자동 수집 설정(push_games)이 꺼져 있어도 그 자리에서 바로 올라가야 한다."""
        self.store.save_settings({'push_games': False})
        rid = 'u:' + self.store.save_replay(dummy_rec())
        r = self.store.push_game_now(rid)
        self.assertTrue(r['ok'], r)
        self.assertIn('log', r)   # 버튼은 즉시 보여줄 로그까지 그대로 받아야 함(자동 push_game 과 다른 점)
        status = self.store.last_game_push()
        self.assertTrue(status and status['ok'], status)   # last_game_push.json 도 같이 갱신됨
        verify = self._clone_data_games('verify3')
        key = rid.split(':', 1)[1]
        idx = json.load(open(os.path.join(verify, 'index.json'), encoding='utf-8'))
        self.assertIn(key, idx)

    def test_push_now_rejects_library_replay(self):
        r = self.store.push_game_now('l:없음')
        self.assertFalse(r['ok'])


if __name__ == '__main__':
    unittest.main()
