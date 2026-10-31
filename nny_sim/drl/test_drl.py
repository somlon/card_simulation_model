"""DRL 모듈 테스트 (nny_sim 폴더에서):  python -m unittest drl.test_drl -v
PyTorch가 없으면 학습망 관련 테스트는 건너뛴다."""
import copy, os, random, tempfile, unittest
import numpy as np
import season as SE
import policy as P
import match as M
import deck as DK
from engine import Game
from cards import Impl, POOL
from drl import schema as S, features as F, model as MD, side as SD, rollout as R
from drl.agent import DRLAI, Recorder

try:
    import torch
    from drl import learner as L, nets as N
except ImportError:   # 대국 전용 환경
    torch = None

DECKS = SE.load_decks(); NAMES = sorted(DECKS)
ACTOR = MD.NumpyActor(MD.init_arrays(0))


def _game(a, b, ais, first=0, seed=1):
    g = Game([DECKS[a], DECKS[b]], ais, first, random.Random(seed), [], Impl)
    g.seed = seed; g.dlog = []
    return g


class SchemaTest(unittest.TestCase):
    def test_parse_decision(self):
        self.assertEqual(S.parse_decision('진행 행동')[0], S.DT_IX['진행 행동'])
        self.assertEqual(S.parse_decision('대응')[0], S.DT_IX['대응'])
        name = S.VOCAB[5]
        dt, _, card = S.parse_decision(f'트리거:{name}#2')
        self.assertEqual((dt, card), (S.DT_IX['트리거'], name))
        self.assertEqual(S.parse_decision(f'멀리건:{name}')[2], name)
        self.assertEqual(S.parse_decision('드로우 덱(패의 상급 1)')[0], S.DT_IX['드로우 덱'])
        self.assertEqual(S.parse_decision('무엇인가 새로운 판단')[0], S.DT_IX['기타'])

    def test_crc_is_process_stable(self):
        self.assertEqual(S.crc('서치:입장', 8), S.crc('서치:입장', 8))
        self.assertEqual(S.crc('abc', 1 << 30), 891568578 % (1 << 30))   # zlib.crc32 고정값

    def test_action_kind(self):
        dt = S.DT_IX['진행 행동']
        self.assertEqual(S.action_kind('종료', dt), S.AK_IX['종료'])
        self.assertEqual(S.action_kind('수비 소환:x', dt), S.AK_IX['수비 소환'])
        self.assertEqual(S.action_kind('소환:x', dt), S.AK_IX['소환'])
        self.assertEqual(S.action_kind('a→직접', S.DT_IX['공격']), S.AK_IX['직접 공격'])
        self.assertEqual(S.action_kind('a→b', S.DT_IX['공격']), S.AK_IX['몬스터 공격'])
        self.assertEqual(S.action_kind('발동', S.DT_IX['트리거']), S.AK_IX['예'])

    def test_meta_check_and_remap(self):
        meta = S.schema_meta()
        self.assertIsNone(S.check_meta(meta))
        bad = dict(meta, hash=meta['hash'] + 1)
        with self.assertRaises(S.SchemaMismatch):
            S.check_meta(bad)
        old = dict(meta, vocab=meta['vocab'][1:])          # 모델이 첫 카드를 모르던 시절
        remap = S.check_meta(old)
        self.assertEqual(remap[S.CARD_ID[S.VOCAB[0]]], S.UNK)
        self.assertEqual(remap[S.CARD_ID[S.VOCAB[1]]], 2)


class FeatureTest(unittest.TestCase):
    def test_dims_and_no_leak(self):
        checks = {'n': 0, 'leak_ok': 0, 'oracle_changed': 0}
        test = self

        class Probe(DRLAI):
            def choose(self_, g, p, decision, opts, scale=40.0, log=True):
                if len(opts) > 1 and g.turn >= 2:
                    obs, orc = F.encode_obs(g, p, decision, oracle=True)
                    test.assertEqual(obs[0].shape, (S.G_DIM,))
                    test.assertEqual(len(obs[1]), len(S.BAGS_ACTOR)); test.assertEqual(len(orc[0]), len(S.BAGS_ORACLE) - len(S.BAGS_ACTOR))
                    ids, num = F.encode_cands(g, p, decision, opts, scale)
                    test.assertEqual(num.shape, (len(opts), S.A_DIM))
                    for k, c in enumerate([c for c in g.p[1 - p].m if c]):
                        if not c.faceup:
                            test.assertEqual(obs[2][1, k], S.UNK)
                    # 상대 패 · 덱을 바꿔도 배우 관측은 같아야 한다(정보 누설 없음)
                    op = g.p[1 - p]
                    if op.hand and op.main:
                        hi = next((i for i, c in enumerate(op.hand) if c.deck_kind() == '메인'), None)
                        di = next((i for i, c in enumerate(op.main) if hi is not None and c.name != op.hand[hi].name), None)
                        if hi is not None and di is not None:
                            op.hand[hi], op.main[di] = op.main[di], op.hand[hi]
                            obs2, orc2 = F.encode_obs(g, p, decision, oracle=True)
                            op.hand[hi], op.main[di] = op.main[di], op.hand[hi]
                            same = all(np.array_equal(np.asarray(a), np.asarray(b)) for a, b in zip(obs[:1] + obs[2:], obs2[:1] + obs2[2:])) \
                                and [sorted(x) for x in obs[1]] == [sorted(x) for x in obs2[1]]
                            test.assertTrue(same, '상대 패를 바꿨더니 배우 관측이 달라짐 — 정보 누설')
                            checks['leak_ok'] += 1
                            checks['oracle_changed'] += int(sorted(orc[0][0]) != sorted(orc2[0][0]))
                    checks['n'] += 1
                return DRLAI.choose(self_, g, p, decision, opts, scale, log)

        for k in range(4):
            a, b = NAMES[k], NAMES[(k + 1) % len(NAMES)]
            g = _game(a, b, [Probe(DECKS[a]['스킬'], actor=ACTOR), Probe(DECKS[b]['스킬'], actor=ACTOR)], k % 2, 10 + k)
            g.run()
        self.assertGreater(checks['n'], 20); self.assertGreater(checks['leak_ok'], 5)
        self.assertGreater(checks['oracle_changed'], 0)   # 비평가는 상대 패 변화를 본다


    def test_facedown_target_is_hidden(self):
        """상대의 뒷면 카드가 후보(대상)일 때 후보 특징에 정체가 들어가지 않아야 한다"""
        seen = {'n': 0}
        test = self

        class Probe(DRLAI):
            def choose(self_, g, p, decision, opts, scale=40.0, log=True):
                cards = [c for c in g.field_cards(1 - p)]
                if cards and seen['n'] < 20:
                    c = cards[0]; old = (c.faceup, c.d, c.name)
                    other = next(n for n in S.VOCAB if n != c.name and POOL[n]['type'] == c.type)
                    try:
                        c.faceup = False
                        a = F.encode_cands(g, p, '대상:remove', [('상:?', 0, c), ('종료', 0, None)], 20)
                        c.d = POOL[other]; c.name = other
                        b = F.encode_cands(g, p, '대상:remove', [('상:?', 0, c), ('종료', 0, None)], 20)
                    finally:
                        c.faceup, c.d, c.name = old
                    test.assertEqual(a[0][0, 0], S.UNK)
                    np.testing.assert_array_equal(a[0], b[0]); np.testing.assert_array_equal(a[1], b[1])
                    seen['n'] += 1
                return DRLAI.choose(self_, g, p, decision, opts, scale, log)

        for k in range(3):
            a, b = NAMES[k], NAMES[(k + 3) % len(NAMES)]
            _game(a, b, [Probe(DECKS[a]['스킬'], actor=ACTOR), Probe(DECKS[b]['스킬'], actor=ACTOR)], k % 2, 90 + k).run()
        self.assertGreater(seen['n'], 5)

    def test_opponent_hand_card_is_hidden(self):
        """상대 패의 카드가 후보가 되어도(패 카드는 엔진에서 faceup=True) 정체가 들어가지 않아야 한다"""
        g = _game(NAMES[0], NAMES[1], [P.LearnedAI(DECKS[NAMES[0]]['스킬'], learn=False), P.LearnedAI(DECKS[NAMES[1]]['스킬'], learn=False)])
        g.setup()
        c = g.p[1].hand[0]; self.assertTrue(c.faceup); self.assertEqual(c.zone, 'hand')
        a = F.encode_cands(g, 0, '대상:discard', [('상:?', 0, c), ('종료', 0, None)], 20)
        other = next(n for n in S.VOCAB if n != c.name and POOL[n]['type'] == c.type)
        old = (c.d, c.name)
        try:
            c.d = POOL[other]; c.name = other
            b = F.encode_cands(g, 0, '대상:discard', [('상:?', 0, c), ('종료', 0, None)], 20)
        finally:
            c.d, c.name = old
        self.assertEqual(a[0][0, 0], S.UNK)
        np.testing.assert_array_equal(a[0], b[0]); np.testing.assert_array_equal(a[1], b[1])
        own = F.encode_cands(g, 1, '대상:discard', [('자:?', 0, c), ('종료', 0, None)], 20)   # 자기 패 카드는 보인다
        self.assertEqual(own[0][0, 0], S.cid(c.name))


class AgentTest(unittest.TestCase):
    def test_teacher_mode_reproduces_learnedai(self):
        """교사 모드(탐색 0)는 LearnedAI(학습 끔)와 판 전체가 똑같아야 한다 — 모방 학습 자료가 곧 학습표의 수.
        DRLAI는 종료 · 패스 보유 가치 평가를 끄므로(PASS_EVAL=False) 같은 설정의 LearnedAI와 비교한다"""
        def table_ai(name):
            ai = P.LearnedAI(DECKS[name]['스킬'], learn=False); ai.PASS_EVAL = DRLAI.PASS_EVAL
            return ai
        for k in range(4):
            a, b = NAMES[k], NAMES[(k + 2) % len(NAMES)]
            g1 = _game(a, b, [table_ai(a), table_ai(b)], k % 2, 50 + k)
            r1 = g1.run()
            g2 = _game(a, b, [DRLAI(DECKS[a]['스킬'], mode='teacher', teacher=P.POLICY), DRLAI(DECKS[b]['스킬'], mode='teacher', teacher=P.POLICY)], k % 2, 50 + k)
            r2 = g2.run()
            self.assertEqual(r1, r2); self.assertEqual(g1.turn, g2.turn); self.assertEqual(g1.dlog, g2.dlog)

    def test_replay_compatibility(self):
        """DRL 게임의 판단 기록(dlog)을 탐색 AI의 재현 절차(g.script)로 되감으면 같은 결과가 나와야 한다"""
        for k in range(3):
            a, b = NAMES[k + 1], NAMES[(k + 4) % len(NAMES)]
            g = _game(a, b, [DRLAI(DECKS[a]['스킬'], actor=ACTOR, mode='sample', rng=np.random.default_rng(k)),
                             DRLAI(DECKS[b]['스킬'], actor=ACTOR)], k % 2, 70 + k)
            w, _ = g.run()
            h = _game(a, b, [P.LearnedAI(DECKS[a]['스킬'], learn=False), P.LearnedAI(DECKS[b]['스킬'], learn=False)], k % 2, 70 + k)
            h.script = {'seq': list(g.dlog), 'pos': 0, 'force': 0, 'forced': True, 'player': 0, 'determinize': lambda *x: None}
            w2, _ = h.run()
            self.assertEqual((w, g.turn), (w2, h.turn))
            self.assertEqual(h.script['pos'], len(g.dlog))

    def test_recorder_rewards_and_abort(self):
        rec = Recorder(); nrng = np.random.default_rng(0)
        rec.begin_match()
        mw, rounds = R.play_one_match(DECKS[NAMES[0]], DECKS[NAMES[1]], 0, 5, ['cur', 'cur'], [ACTOR, ACTOR], rec, nrng)
        rec.end_match(mw)
        self.assertTrue(rec.samples)
        self.assertTrue(all(e[4] in (1.0, -1.0) for e in rec.samples))
        side = [e for e in rec.samples if e[0] == 'side']
        self.assertTrue(all(e[4] == (1.0 if e[1] == mw else -1.0) for e in side))
        n = len(rec.samples); rec.begin_match(); rec.add('game', 0, 999, None); rec.abort_match()
        self.assertEqual(len(rec.samples), n)


class SideTest(unittest.TestCase):
    def _check_deck(self, before, after):
        for sec in ('메인', '상급', '전략'):
            self.assertEqual(sum(n for n, _ in before[sec]), sum(n for n, _ in after[sec]), sec)
        act = M.counts_of(after)
        self.assertTrue(all(k <= 3 for k in act.values()))
        self.assertTrue(all(M.fits(n, after['스킬']) for n, k in act.items() if k > 0))
        errs, _ = DK.validate(after, policy=False)
        self.assertFalse(errs, errs)

    def test_drl_side_swap_keeps_rules(self):
        rs = np.random.default_rng(1)
        for a in NAMES:
            for b in NAMES[:3]:
                if a == b:
                    continue
                ctx = dict(round=1, wins_me=0, wins_op=1, lost_last=True)
                rec = Recorder(); rec.begin_match()
                nd = SD.drl_side_swap(DECKS[a], DECKS[b], ctx, ACTOR, mode='sample', rng=rs, recorder=rec, seat=0)
                self._check_deck(DECKS[a], nd)

    def test_teacher_side_matches_table(self):
        for a in NAMES:
            b = NAMES[(NAMES.index(a) + 1) % len(NAMES)]
            ctx = dict(round=1, wins_me=0, wins_op=1, lost_last=True)
            rec = Recorder(); rec.begin_match()
            d1 = SD.teacher_side_swap(DECKS[a], DECKS[b], ctx, random.Random(3), recorder=rec, seat=0)
            d2 = M.side_swap(DECKS[a], DECKS[b]['스킬'], random.Random(3), 0.0, None, '')
            self.assertEqual(d1, d2)
            # 기록된 교사 선택을 같은 절차(후보 1개면 자동 진행)로 다시 적용하면 학습표와 같은 덱이 된다
            picks = [e[3][3] for e in rec._pending]
            w = SD._Walker(DECKS[a], DECKS[b], ctx, False)
            for _ in range(SD.MAX_STEPS):
                cands = w.cands()
                if not cands:
                    break
                cand = cands[0] if len(cands) == 1 else cands[picks.pop(0)]
                if w.take(cand):
                    break
            self.assertEqual(picks, [])
            self.assertEqual(M.counts_of(w.deck(DECKS[a])), M.counts_of(d2))
            self.assertEqual(w.deck(DECKS[a])['스킬'], d2['스킬'])

    def test_mirror_match_with_one_drl_seat(self):
        """같은 덱끼리 한쪽만 DRL이어도 자리(deck['_seat'])로 구분된다"""
        from drl import play as PL
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'm.npz'); MD.save_model(p, MD.init_arrays(1))
            make_ai, side_fn = PL.players(p, None)
            kinds = []
            orig = make_ai
            mk = lambda deck: (kinds.append((deck['_seat'], type(orig(deck)).__name__)), orig(deck))[1]
            M.play_match(DECKS[NAMES[0]], DECKS[NAMES[0]], 0, random.Random(4), [], mk, learn_side=False, side_fn=side_fn)
        self.assertIn((0, 'DRLAI'), kinds); self.assertIn((1, 'LearnedAI'), kinds)
        self.assertFalse(any((s, n) in kinds for s, n in ((0, 'LearnedAI'), (1, 'DRLAI'))))

    def test_play_match_hook_default_unchanged(self):
        """side_fn을 주지 않으면 기존 경로와 같고, 기존 교체 함수를 side_fn으로 넘겨도 결과가 같다"""
        mk = lambda d: P.LearnedAI(d['스킬'], learn=False)
        r1 = M.play_match(DECKS[NAMES[2]], DECKS[NAMES[5]], 1, random.Random(9), [], mk, learn_side=False)
        fn = lambda i, decks, wins, rounds, rng, eps, log: M.side_swap(decks[i], decks[1 - i]['스킬'], rng, eps, log, decks[i]['이름'])
        r2 = M.play_match(DECKS[NAMES[2]], DECKS[NAMES[5]], 1, random.Random(9), [], mk, learn_side=False, side_fn=fn)
        strip = lambda r: (r[0], [(x['first'], x['winner'], x['turns']) for x in r[1]])
        self.assertEqual(strip(r1), strip(r2))


class TableIOTest(unittest.TestCase):
    def test_gzip_table_loads_same(self):
        """압축한 학습표(.json.gz)도 원본과 같은 값을 돌려준다"""
        import gzip, json as _json
        d = {'games': 3, 'L1': {'a|b': [2, 3]}, 'L2': {'a|b|c': [1, 2]}}
        with tempfile.TemporaryDirectory() as tmp:
            p1 = os.path.join(tmp, 't.json'); p2 = p1 + '.gz'
            with open(p1, 'w', encoding='utf-8') as f:
                _json.dump(d, f)
            with gzip.open(p2, 'wt', encoding='utf-8') as f:
                _json.dump(d, f)
            t1, t2 = R.load_table(p1), R.load_table(p2)
        self.assertEqual((t1.L1, t1.L2, t1.games), (t2.L1, t2.L2, t2.games))
        self.assertEqual(t1.value('a|b', 'a|b|c', 0.5), t2.value('a|b', 'a|b|c', 0.5))


class ModelIOTest(unittest.TestCase):
    def test_save_load_roundtrip(self):
        arr = MD.init_arrays(3)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'm.npz'); MD.save_model(p, arr, {'note': 't'})
            actor, meta = MD.load_actor(p)
            self.assertEqual(meta['note'], 't')
            for k in arr:
                np.testing.assert_array_equal(actor.w[k], arr[k])
            self.assertFalse(os.path.exists(p + '.tmp'))

    def test_old_model_with_smaller_card_pool_loads(self):
        """카드 풀에 카드가 추가된 뒤에도 옛 모델을 불러와 쓸 수 있다(새 카드는 UNK)"""
        import io, json as _json
        arr = MD.init_arrays(5); drop = S.VOCAB[-1]
        arr['emb'] = arr['emb'][:-1]; arr['s_emb'] = arr['s_emb'][:-1]      # 모델 어휘 = 현재 어휘 − 마지막 카드
        meta = {'schema': dict(S.schema_meta(), vocab=S.VOCAB[:-1])}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'old.npz')
            np.savez_compressed(p, __meta__=np.array(_json.dumps(meta, ensure_ascii=False)), **arr)
            actor, _ = MD.load_actor(p)
        self.assertEqual(int(actor.remap[S.CARD_ID[drop]]), S.UNK)
        g = _game(NAMES[0], NAMES[1], [DRLAI(DECKS[NAMES[0]]['스킬'], actor=actor), DRLAI(DECKS[NAMES[1]]['스킬'], actor=actor)])
        g.run()   # 추론 전 과정이 오류 없이 돈다

    def test_shape_guard(self):
        arr = MD.init_arrays(0); arr['t1_w'] = arr['t1_w'][:, :10]
        with self.assertRaises(ValueError):
            MD.NumpyActor(arr)


class BufferTest(unittest.TestCase):
    """묶음(열 단위 배열) 형식: 묶기 · 부분 선택 · 궤적 구분이 원본 표본과 맞는가"""

    @classmethod
    def setUpClass(cls):
        rec = Recorder(3); nrng = np.random.default_rng(0)
        for k in range(3):
            rec.begin_match()
            mw, _ = R.play_one_match(DECKS[NAMES[k]], DECKS[NAMES[k + 2]], k % 2, 60 + k, ['cur', 'cur'], [ACTOR, ACTOR], rec, nrng)
            rec.end_match(mw)
        cls.entries = list(rec.samples)
        from drl import buffer as B
        cls.B = B; cls.P = B.pack('game', [e for e in cls.entries if e[0] == 'game'], worker=3)

    def test_pack_select_roundtrip(self):
        B = self.B; games = [e for e in self.entries if e[0] == 'game']
        ix = np.array([0, 5, 17, len(games) - 1])
        Q = B.select(self.P, ix)
        st = B._starts(Q['bag_len']); cst = B._starts(Q['cand_len'])
        for j, i in enumerate(ix):
            obs, orc, cands, idx, logp, tp, dt = games[i][3]
            for z, bag in enumerate(obs[1]):
                got = Q['bag_ids'][st[j, z]:st[j, z] + Q['bag_len'][j, z]]
                np.testing.assert_array_equal(got, bag)
            np.testing.assert_array_equal(Q['cand_ids'][cst[j]:cst[j] + len(cands[0])], cands[0])
            np.testing.assert_allclose(Q['cand_num'][cst[j]:cst[j] + len(cands[0])].astype(np.float32), cands[1], atol=2e-3, rtol=2e-3)
            self.assertEqual((int(Q['idx'][j]), int(Q['dt'][j])), (idx, dt))
            self.assertAlmostEqual(float(Q['logp'][j]), logp, places=5)

    def test_trajectories_are_chronological(self):
        order, bounds = self.B.trajectories(self.P)
        self.assertEqual(sorted(order.tolist()), list(range(self.B.size(self.P))))
        for s, e in bounds:
            ix = order[s:e]
            self.assertTrue(np.all(np.diff(ix) > 0))                       # 궤적 안은 원래(시간) 순서
            self.assertEqual(len(set(zip(self.P['gid'][ix], self.P['seat'][ix]))), 1)
            self.assertEqual(len(set(self.P['reward'][ix].tolist())), 1)   # 궤적의 보상은 하나


@unittest.skipIf(torch is None, 'PyTorch 없음')
class TorchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from drl import buffer as B
        cls.B = B
        cls.cfg = dict(seed=0, lr_actor=3e-4, lr_critic=1e-3, epochs=1, minibatch=256, side_minibatch=64, clip=0.2, lam=0.95, max_grad_norm=0.5)
        cls.lr = L.Learner(cls.cfg); cls.actor = MD.NumpyActor(cls.lr.export())
        rec = Recorder(); nrng = np.random.default_rng(0)
        for k in range(4):
            roles = [['cur', 'cur'], ['teacher', 'teacher']][k % 2]
            rec.begin_match()
            mw, _ = R.play_one_match(DECKS[NAMES[k]], DECKS[NAMES[k + 1]], k % 2, 40 + k, roles,
                                     [cls.actor if r == 'cur' else None for r in roles], rec, nrng, use_teacher_kl=True)
            rec.end_match(mw)
        cls.entries = list(rec.samples); cls.data = rec.packed()

    def test_numpy_torch_parity(self):
        """학습망(PyTorch, 묶음 입력)과 대국용 numpy 추론의 로짓이 같다 (묶음의 float16 저장 오차 이내)"""
        B = self.B
        for kind, fn in (('game', self.actor.logits), ('side', self.actor.side_logits)):
            ents = [e for e in self.entries if e[0] == kind][:200]
            if not ents:
                continue
            P = B.pack(kind, ents)
            with torch.no_grad():
                lt = self.lr.nets(kind)[0](B.to_torch(P)).numpy()
            ln = np.concatenate([fn(e[3][0], e[3][2]) for e in ents])
            self.assertLess(float(np.abs(lt - ln).max()), 1e-2, kind)

    def test_gae(self):
        adv, ret = L.gae(np.array([0.0, 0.5]), 1.0, 1.0)
        np.testing.assert_allclose(adv, [1.0, 0.5]); np.testing.assert_allclose(ret, [1.0, 1.0])
        adv, ret = L.gae(np.array([0.0, 0.5]), -1.0, 0.0)
        np.testing.assert_allclose(adv, [0.5, -1.5])

    def test_updates_are_finite(self):
        lr = L.Learner(self.cfg); lr.load_state_dict(self.lr.state_dict())
        m1 = lr.update(self.data, 0.0, 0.0, bc=True, epochs=1)
        m2 = lr.update(self.data, 0.01, 0.5)
        self.assertIn('game', m1); self.assertIn('game', m2)
        for m in (m1, m2):
            for kind in m.values():
                for k, v in kind.items():
                    self.assertTrue(np.isfinite(v), (k, v))
        self.assertTrue(lr.bc_metrics(self.data))


if __name__ == '__main__':
    unittest.main()
