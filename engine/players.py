"""수를 고르는 역할 — 완성_기준_듀얼.md 6번.

둘 다 **고르기만** 한다. 어떤 수가 합법인지는 `engine/legalmoves.py`, 그 수를 적용하는 것은
`engine/turn.py` 의 일이다.

- `무작위플레이어` — 합법수 중에서 균등 추출. 기준선이고, 100판 완주 시험의 상대다.
- `필터플레이어` — 합법수를 1층 맵으로 거른 뒤 **남은 것 중에서** 무작위. 맵이 전부 떨어뜨리면
  (공집합 — 맵_형식.md 7-1 대로 버그가 아니다) 거르기 전 합법수로 되돌아간다.

**1층은 순위를 매기지 않는다.** `필터결과.후보` 의 순서는 맵에 적힌 순서일 뿐 좋음/나쁨이
아니므로(맵_형식.md 7장) 첫 번째를 고르지 않고 무작위로 뽑는다 — 순서를 선호로 오해하면
아직 없는 상위 층(심리 · 덱 성향)의 일을 1층이 몰래 하는 것이 된다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from .mapfilter import 거르기, 맵, 맵_읽기
from .state import 게임상태


@dataclass
class 무작위플레이어:
    이름: str
    난수: random.Random

    def 고르기(self, 질문: str, 후보: list[str]) -> str:
        return self.난수.choice(후보)

    def 수_고르기(self, 상태: 게임상태, 합법수: list[str], 누구: str) -> str | None:
        """None 을 돌려주면 「더 안 둠」(단계를 넘긴다)."""
        if not 합법수:
            return None
        # 턴을 끝낼 선택지도 똑같이 하나의 선택지로 둔다 — 그래야 무한 루프가 안 생긴다.
        return self.난수.choice([*합법수, None])  # type: ignore[list-item]


@dataclass
class 필터플레이어:
    이름: str
    난수: random.Random
    맵경로: Path
    _맵: 맵 | None = None

    def __post_init__(self) -> None:
        self._맵 = 맵_읽기(self.맵경로)

    def 고르기(self, 질문: str, 후보: list[str]) -> str:
        return self.난수.choice(후보)

    def 수_고르기(self, 상태: 게임상태, 합법수: list[str], 누구: str) -> str | None:
        if not 합법수:
            return None
        원래 = set(상태.가용수단)
        상태.가용수단 = set(합법수)
        try:
            결과 = 거르기(self._맵, 상태, {}, 나는=누구)
        finally:
            상태.가용수단 = 원래
        남은 = [하나 for 하나 in 합법수 if 하나 in set(결과.후보)]
        고를것 = 남은 or 합법수
        return self.난수.choice([*고를것, None])  # type: ignore[list-item]
