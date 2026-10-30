"""게임 프로그램의 신경망 표본(사람 대전 · AI끼리)을 모아 기본 신경망을 다시 학습한다 — 「신경망 내보내기」 zip · 「GitHub에 올리기」 폴더를 읽는다.

  python3 merge_nn.py --sim <실행 폴더> --inputs nny_sim/learned/drl/human_nn [다른 폴더 · zip ...] --list
  python3 merge_nn.py --sim <실행 폴더> --inputs nny_sim/learned/drl/human_nn --out <실행 폴더>/learned/drl/human_v1/model_best.npz [--epochs 4]

- 출처: 폴더(하위 폴더 포함 — <컴퓨터>/samples/*.npz, 올린 zip) · zip 파일. 같은 매치(표본 파일 이름)는 한 번만 쓴다(nn_samples.load_sources).
- 표본 가중치: samples/index.json 의 매치 출처로 사람 대전 HUMAN_WEIGHT · AI끼리 AI_WEIGHT(app/learndata.py — 프로그램과 같음, 출처 없는 예전 표본은 사람 대전).
- 학습: 프로그램 안 「신경망 학습」과 같은 학습기(nn_train.train — 교사 KL + 기본 모델 KL + 라운드 승패 가중, numpy)로
  --base(기본: <실행 폴더>/learned/drl/base_v2/model_best.npz)에서 시작해 모은 표본 전체로 학습한다.
- 결과 모델을 배포본의 기본 모델로 쓰려면 평가(학습표 · 휴리스틱 AI 상대) 뒤 data 계열 브랜치에 올리고 build_windows.py --nn-base 로 넣는다.
"""
import argparse, json, os, sys, time

APP = os.path.dirname(os.path.abspath(__file__))


def manifests(srcs):
    """출처별 manifest.json(내보내기 · 올리기 때 함께 들어감) — 누가 · 언제 · 매치 몇 개"""
    import zipfile
    out = []
    for src in srcs:
        if os.path.isdir(src):
            for root, _, files in sorted(os.walk(src)):
                for n in sorted(files):
                    f = os.path.join(root, n)
                    if n == 'manifest.json':
                        with open(f, encoding='utf-8') as fh: out.append((f, json.load(fh)))
                    elif n.endswith('.zip'):
                        out += manifests([f])
        elif zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as z:
                if 'manifest.json' in z.namelist(): out.append((src, json.loads(z.read('manifest.json'))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sim', required=True, help='실행 폴더(drl · 기본 모델)'); ap.add_argument('--inputs', nargs='+', required=True)
    ap.add_argument('--base', help='시작 모델(기본: <sim>/learned/drl/base_v2/model_best.npz)'); ap.add_argument('--out')
    ap.add_argument('--epochs', type=int); ap.add_argument('--list', action='store_true', help='표본 현황만 보기')
    a = ap.parse_args(argv)
    sim = os.path.abspath(a.sim); srcs = [os.path.abspath(x) for x in a.inputs]
    sys.path[:0] = [sim, APP]
    import nn_samples as NS, nn_train as NT, nnai as NA
    from drl import model as MD
    for f, m in manifests(srcs):
        print(f'  {os.path.relpath(f)} — {m.get("host")} · {m.get("created")} · 매치 {m.get("matches")} · 표본 {m.get("samples")}'
              + (' · 내 모델 있음' if m.get('local_model') else ''))
    P, matches, info = NS.load_sources(srcs)
    print(f'표본 파일(매치) {info["files"]}개 · 판단 {info["samples"]}개 · 겹쳐서 뺀 파일 {info["duplicates"]}개 — 출처별 '
          + ', '.join(f'{k} 매치 {v["files"]} · 판단 {v["samples"]}' for k, v in sorted(info['by_source'].items())))
    if P is None: return 1
    if a.list: return 0
    if info['samples'] < NA.MIN_SAMPLES:
        print(f'표본이 {NA.MIN_SAMPLES}개보다 적어 학습하지 않습니다.'); return 1
    if not a.out: ap.error('--out 이 필요합니다(학습 결과 모델 파일)')
    base = a.base or NA.base_path(sim)
    arrays, base_meta = MD.load_arrays(base)
    t0 = time.time(); epochs = a.epochs or NT.EPOCHS

    def prog(f, m): print(f'  에포크 {m["epoch"]}/{epochs} · 손실 {m["loss"]}', flush=True)
    w, log = NT.train(arrays, P, matches, epochs=epochs, progress=prog)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    MD.save_model(a.out, w, {'stage': 'human-merged', 'created': time.strftime('%Y-%m-%d %H:%M'), 'base': os.path.relpath(base, sim),
                             'base_it': base_meta.get('it'), 'sources': [os.path.basename(s) for s in srcs], 'train': log})
    print(f'저장: {a.out} ({time.time() - t0:.0f}초) — 학습 전 {log.get("before")} → 학습 후 {log.get("after")}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
