"""규칙 자료(YAML)의 `.json` 사본을 다시 만든다 — 개발자 PC 에서만 돌린다.

pyyaml 이 없는 테스터 PC 에서도 프로그램이 돌게 하려는 장치다. 자세한 사정은
`engine/자료읽기.py` 머리글 참조. YAML 을 고쳤으면 이걸 돌리고 사본까지 같이 커밋한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.자료읽기 import 사본쓰기, 자료파일들, yaml있나


def 주문() -> int:
    if not yaml있나:
        print("pyyaml 이 없다 — 사본은 pyyaml 이 있는 PC 에서 만들어야 한다.")
        return 1
    for 하나 in 자료파일들():
        낸곳 = 사본쓰기(하나)
        print(f"{하나.relative_to(Path.cwd()) if 하나.is_relative_to(Path.cwd()) else 하나}"
              f"  →  {낸곳.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(주문())
