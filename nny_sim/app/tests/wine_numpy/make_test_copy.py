"""시험 전용 — 배포본에는 절대 넣지 않는다. wine 9.0 의 ucrtbase 에는 C99 복소수 함수(crealf 등)가 없어 numpy 를 불러오다 프로세스가 죽는다
(실제 Windows 10/11 의 UCRT 에는 있음). 빌드한 NNY_Simulator 폴더의 「시험용 사본」에서만 numpy 의 세 모듈이 수학 함수를 가져오는 DLL 이름을
같은 길이의 시험용 shim 으로 바꾸고, shim(shim.c — 복소수 함수 구현 + 나머지는 ucrtbase 로 넘김)을 그 옆에 둔다.
  python3 make_test_copy.py <빌드한 NNY_Simulator 폴더> <시험용 사본 폴더>
준비물: gcc-mingw-w64-x86-64 (x86_64-w64-mingw32-gcc · objdump)"""
import os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = b'api-ms-win-crt-math-l1-1-0.dll'
NEW = b'nnytest-crt-math-shim-0001.dll'   # 같은 길이(가져오기 표의 이름만 바꿈)
PYDS = ('numpy/_core/_multiarray_umath.cp313-win_amd64.pyd', 'numpy/_core/_multiarray_tests.cp313-win_amd64.pyd',
        'numpy/linalg/_umath_linalg.cp313-win_amd64.pyd')


def imports(pyd):
    out = subprocess.run(['x86_64-w64-mingw32-objdump', '-p', pyd], capture_output=True, text=True, check=True).stdout
    names, cur = set(), None
    for ln in out.splitlines():
        m = re.match(r'\s*DLL Name: (\S+)', ln)
        if m: cur = m.group(1); continue
        if not ln.strip(): cur = None; continue
        m = re.match(r'\s+[0-9a-f]+\s+\d+\s+(\S+)', ln)
        if cur == OLD.decode() and m: names.add(m.group(1))
    return names


def main(src, dst):
    assert len(OLD) == len(NEW)
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(src, dst)
    sp = os.path.join(dst, 'runtime', 'Lib', 'site-packages')
    names = set().union(*(imports(os.path.join(sp, p)) for p in PYDS))
    impl = set(re.findall(r'F\([a-z]+ ([a-z]+)\)', open(os.path.join(HERE, 'shim.c'), encoding='utf-8').read()))
    work = os.path.join(dst, '_shim'); os.makedirs(work)
    with open(os.path.join(work, 'shim.def'), 'w') as f:
        f.write(f'LIBRARY {NEW.decode()}\nEXPORTS\n' + ''.join(f'  {n}\n' for n in sorted(impl))
                + ''.join(f'  {n} = ucrtbase.{n}\n' for n in sorted(names - impl)))
    dll = os.path.join(work, NEW.decode())
    subprocess.run(['x86_64-w64-mingw32-gcc', '-shared', '-O2', '-fno-builtin', '-w', '-o', dll, os.path.join(HERE, 'shim.c'), os.path.join(work, 'shim.def'), '-lm'], check=True)
    for p in PYDS:
        f = os.path.join(sp, p); d = open(f, 'rb').read(); assert d.count(OLD) == 1, p
        open(f, 'wb').write(d.replace(OLD, NEW)); shutil.copy2(dll, os.path.dirname(f))
    print(dst, f'— shim 함수 {len(impl)}개 구현 · {len(names - impl)}개 ucrtbase 로')


if __name__ == '__main__':
    main(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]))
