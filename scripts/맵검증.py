"""두 맵(호박옥·던전마스터)이 실제로 돌아갈 수 있는 상태인지 한 번에 확인한다.

    python scripts/맵검증.py

`engine.mapfilter.맵_검증()` 을 맵마다 돌려 노드 id 집합과 검증 결과를 찍는다.
완성 기준 3번("두 맵 모두 검증 깨끗") 의 통과 조건은 `검증.깨끗한가 == True` 뿐 아니라
`서술형불변식`·`자원미선언` 도 0건이어야 한다 — `깨끗한가` 프로퍼티는 이 둘을 안 보므로
이 스크립트가 따로 검사해 종료 코드에 반영한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

뿌리 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(뿌리))

from engine.mapfilter import 맵_검증, 맵_읽기

맵경로들 = [
    뿌리 / "maps" / "호박옥_봉인의_계약.yaml",
    뿌리 / "maps" / "던전마스터_셔플.yaml",
]


def 메인() -> int:
    전부통과 = True
    for 경로 in 맵경로들:
        맵 = 맵_읽기(경로)
        검증 = 맵_검증(맵)
        통과 = 검증.깨끗한가 and not 검증.서술형불변식 and not 검증.자원미선언

        print(f"=== {경로.name} ===")
        print(f"노드 id 집합: {[n.id for n in 맵.노드들]}")
        print(f"검증.깨끗한가: {검증.깨끗한가}")
        print(f"서술형불변식: {검증.서술형불변식}")
        print(f"자원미선언: {검증.자원미선언}")
        print(f"검증.글로():\n{검증.글로()}")
        print(f"→ 완성 기준 3번 통과: {통과}")
        print()

        전부통과 = 전부통과 and 통과

    print(f"전체 결과: {'통과' if 전부통과 else '불통과'}")
    return 0 if 전부통과 else 1


if __name__ == "__main__":
    raise SystemExit(메인())
