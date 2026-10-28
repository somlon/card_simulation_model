"""배포본 부트스트랩 — 바탕화면 bat 이 부르는 유일한 진입점 (사용자 설계 2026-10-29).

bat 은 세 가지만 한다 — ① 파이썬 찾기 ② 저장소 받기(git clone 또는 zip) ③ 이 파일 실행.
나머지 전부(저장소 갱신 · 의존성 · 안내 · 서버 띄우기)는 여기 있다. **여기는 깃허브에
고치면 테스터가 다음 실행 때 바로 받지만, bat 은 재배포해야 하기 때문이다.**

bat 을 다시 만들 일이 생기면 **CP949 + CRLF** 를 반드시 지킬 것 — 2026-10-28 에 LF 로
저장했다가 cmd 가 명령을 줄 중간에서 잘라 먹는 사고가 있었다.

    python scripts/부트.py            # 갱신 → 점검 → 서버(기본 포트 8777) → 브라우저
    python scripts/부트.py --포트 9000 --공개   # 나머지 인수는 웹듀얼.py 로 그대로 간다
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

뿌리 = Path(__file__).resolve().parent.parent


def _깃(*인수: str, 시간: int = 90) -> tuple[int, str]:
    try:
        난것 = subprocess.run(["git", *인수], cwd=뿌리, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=시간)
        return 난것.returncode, (난것.stdout or "") + (난것.stderr or "")
    except (OSError, subprocess.SubprocessError) as 오류:
        return 1, str(오류)


def 갱신() -> None:
    """git 체크아웃이면 최신으로. zip 으로 받은 사람은 bat 쪽 받기가 이미 갱신이다."""
    if not (뿌리 / ".git").exists():
        return
    print(" [1/3] 최신 버전을 받는 중...")
    낌, 글 = _깃("pull", "--rebase", "--quiet")
    if 낌 != 0:
        # 로컬이 더러워졌어도 판은 둘 수 있어야 한다 — 멈추지 않고 알리기만 한다.
        print("      (갱신 실패 — 지금 버전으로 계속 간다: " + 글.strip().splitlines()[-1][:80] + ")")


def 준비물() -> None:
    """pyyaml 은 있으면 좋고 없어도 된다(.json 사본, engine/자료읽기.py). 소스 빌드로
    넘어가 컴파일러 없는 PC 에서 멈추는 일이 없게 휠만 허용한다."""
    print(" [2/3] 준비물 확인 중...")
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
             "--only-binary", ":all:", "pyyaml"],
            capture_output=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        import yaml  # noqa: F401
    except ImportError:
        print("      pyyaml 없이 간다 — 규칙 자료는 .json 사본으로 읽는다(동작 동일).")


def 안내() -> None:
    print(" [3/3] 브라우저 창이 열립니다.")
    print()
    print("   * 이 검은 창이 게임 서버입니다. 닫으면 게임도 꺼집니다.")
    print("   * 혼자 두기 : 상대를 AI(헤아림)로 두고 만들기")
    print("   * 구경만 하기: 내 쪽도 AI로 두면 AI끼리 두는 것을 배속으로 볼 수 있습니다")
    print("   * 이상한 점은 화면 오른쪽 [메모] 탭에 남겨 주세요 (턴/단계가 자동으로 붙습니다)")
    print("   * 룰 해석이 궁금하면 메인 화면의 [재정 질문] 페이지에 의견을 남길 수 있습니다")
    print()


def 주문() -> int:
    os.chdir(뿌리)
    print("=" * 46)
    print("   뉴 네오 듀얼  -  테스트용 실행기")
    print("=" * 46)
    print()
    갱신()
    준비물()
    안내()
    명령 = [sys.executable, str(뿌리 / "scripts" / "웹듀얼.py")]
    꼬리 = sys.argv[1:]
    if "--포트" not in 꼬리:
        꼬리 = ["--포트", "8777", *꼬리]
    try:
        return subprocess.call(명령 + 꼬리)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(주문())
