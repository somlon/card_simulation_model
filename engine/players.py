"""수를 고르는 역할 — 완성_기준_듀얼.md 6번.

둘 다 **고르기만** 한다. 어떤 수가 합법인지는 `engine/legalmoves.py`, 그 수를 적용하는 것은
`engine/turn.py` 의 일이다.

- `무작위플레이어` — 합법수 중에서 균등 추출. 기준선이고, 100판 완주 시험의 상대다.
- `필터플레이어` — 합법수를 1층 맵으로 거른 뒤 **남은 것 중에서** 무작위. 맵이 전부 떨어뜨리면
  (공집합 — 맵_형식.md 7-1 대로 버그가 아니다) 거르기 전 합법수로 되돌아간다.
- `헤아림플레이어` — 2026-10-29 신설(사용자 지시 "덱이 돌아가는 논리가 부실해").
  합법수마다 엔진 시뮬레이션으로 결과를 재어 가장 좋은 수를 고른다. 파일 끝 절 참조.

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

# 헤아림플레이어의 수입은 파일 끝 절에 몰아 둔다 — turn/effects 는 이 모듈을 수입하지
# 않아 순환이 없다(2026-10-29 확인).


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


# ---------------------------------------------------------------------------
# 헤아림 — 수의 결과를 엔진 시뮬레이션으로 재어 보고 고르는 플레이어
#
# 사용자 지시(2026-10-29): "덱이 돌아가는 논리가 부실해 … 룰지를 기본으로 깔고 가되,
# 재정에 벗어나지 않게." 설계 전문은 docs/대전논리_설계.md.
#
# 규칙을 지키는 방법이 이 플레이어의 핵심 설계다 — **규칙을 다시 적지 않는다.**
#   1. 고르는 것은 legalmoves 가 내놓은 합법수뿐이다. 규칙 위반 수는 애초에 후보에 없다.
#   2. 수의 결과는 엔진 자신(turn.수_적용 + 강제트리거_처리)의 시뮬레이션으로만 안다.
#      규칙 해석을 여기서 두 번째로 적으면 정본이 둘이 된다 — 그래서 안 적는다.
#   3. 평가 함수는 공개 정보만 읽는다 — 상대 패·덱의 내용은 장수만 세고, 뒷면 유닛은
#      정체 불명의 몸값으로만 친다.
#
# 알고 있는 한계(적당한 정도의 선):
#   - 1수 앞만 본다. 상대 턴의 응수는 "위협" 항으로만 어림한다.
#   - 시뮬레이션은 전체 상태의 깊은 복사 위에서 돈다. 내 덱 순서가 복사에 실려 있어
#     "덱 위에서 N장" 류 효과의 결과를 실제보다 정확히 알게 되는 작은 엿보기가 있다 —
#     평가 함수가 장수만 세므로 영향은 미미하지만, 없는 척하지 않고 여기 적어 둔다.
# ---------------------------------------------------------------------------

import copy
import pickle

from .effects import 효과적용기
from .predicates import 덱상수
from .state import 앞뒤, 표시
from .static import 카드표
from .turn import _능력치, 강제트리거_처리, 기보, 수_적용, 승패_확인, 적용오류

_큰수 = 10 ** 9


def _판전투력(쪽, 표: 카드표) -> tuple[int, int]:
    """유닛 존의 (전투력 합, 유닛 수). 룰지 3-3 — 공격 표시는 공격력, 수비 표시는 수비력.

    뒷면 유닛은 정체를 모르므로(평가는 공개 정보만) 고정 몸값 300 으로 친다.
    """
    합 = 0
    수 = 0
    for 하나 in 쪽.유닛존:
        if 하나 is None:
            continue
        수 += 1
        if 하나.앞뒤 is 앞뒤.뒷면:
            합 += 300
            continue
        합 += _능력치(하나, 표, "ATK" if 하나.표시 is 표시.공격 else "DF")
    return 합, 수


def _직접위협(쪽, 표: 카드표) -> int:
    """상대가 다음 턴 직접공격으로 넣을 수 있는 대미지 어림 — 앞면 공격 표시 ATK 합."""
    return sum(
        _능력치(하나, 표, "ATK")
        for 하나 in 쪽.유닛존
        if 하나 is not None and 하나.앞뒤 is 앞뒤.앞면 and 하나.표시 is 표시.공격
    )


def 상태값(상태, 누구: str, 표: 카드표) -> float:
    """덱 중립 평가 — 클수록 `누구` 에게 좋다. 근거는 전부 룰지의 승리 조건과 자원 구조다.

    - HP 차 (룰지 4-a: HP 0 이 패배) — 1 LP = 1점, 다른 모든 항의 기준 단위.
    - 판 위 전투력·유닛 수 (룰지 3-3: 전투는 이 수치로 갈린다. 상대 쪽에 조금 더 무게 —
      내 것을 쌓는 것보다 상대 것을 치우는 쪽이 전투·직접공격 양쪽을 연다).
    - 패·이펙트 존 (카드 어드밴티지 — 쓸 수 있는 선택지의 수).
    - 덱 잔량 (룰지 4-b: 덱이 다 떨어지면 패배 — 바닥이 보이면 가파르게 벌점).
    - 카운터 (룰지 6장: 효과의 연료 — 덱 중립으로는 가볍게만 센다).
    - 공유 존 마커 (룰지 0-5: 뒤집히면 페널티 셋 중 하나).
    - 직접 위협 (내 필드가 비었는데 상대 공격 표시 ATK 합이 내 HP 이상이면 다음 턴에
      직접공격으로 끝날 수 있다 — 룰지 3-3 직접공격).
    """
    나쪽 = 상태.플레이어(누구)
    적쪽 = 상태.플레이어("상대" if 누구 == "나" else "나")

    값 = float(나쪽.hp - 적쪽.hp)

    내힘, 내수 = _판전투력(나쪽, 표)
    적힘, 적수 = _판전투력(적쪽, 표)
    값 += 내힘 * 0.45 - 적힘 * 0.55
    값 += 내수 * 150 - 적수 * 170

    값 += (len(나쪽.패) - len(적쪽.패)) * 90
    값 += (sum(1 for 칸 in 나쪽.이펙트존 if 칸 is not None)
           - sum(1 for 칸 in 적쪽.이펙트존 if 칸 is not None)) * 60

    내덱 = len(나쪽.메인덱) + len(나쪽.상급덱)
    적덱 = len(적쪽.메인덱) + len(적쪽.상급덱)
    if 내덱 <= 6:
        값 -= (7 - 내덱) * 500
    if 적덱 <= 6:
        값 += (7 - 적덱) * 500

    값 += sum(sum(하나.카운터.values()) for 하나 in 나쪽.유닛존 if 하나 is not None) * 40
    if 나쪽.스킬존 is not None:
        값 += sum(나쪽.스킬존.카운터.values()) * 40

    if 상태.공유존_소유마커 == 누구:
        값 += 80
    elif 상태.공유존_소유마커 is not None:
        값 -= 80

    if 내수 == 0 and _직접위협(적쪽, 표) >= 나쪽.hp:
        값 -= 2500

    return 값


class 헤아림플레이어:
    """합법수마다 깊은 복사 위에서 실제로 둬 보고, 결과가 가장 좋은 수를 고른다.

    1층 맵이 있으면 먼저 거르고(기존 필터와 같음 — 공집합이면 되돌아간다), 남은 수와
    「더 안 둠」(None)을 전부 시뮬레이션한다. 하위 선택(대상 고르기 등)은 표본을 여러 번
    뽑아 가장 좋았던 조합을 기억해 두고, 진짜로 둘 때 그대로 재연한다 — 시뮬레이션과
    실제 적용이 같은 엔진 코드를 지나므로 질문 순서가 같다(어긋나면 그 자리에서 무작위로
    떨어지고 대기열을 비운다).
    """

    def __init__(self, 이름: str, 난수, 표: 카드표, 상수표: dict[str, 덱상수],
                 맵경로: Path | None = None, 적용기: 효과적용기 | None = None,
                 표본수: int = 2):
        self.이름 = 이름
        self.난수 = 난수
        self.표 = 표
        self.상수표 = dict(상수표)
        self.표본수 = 표본수
        self._맵 = 맵_읽기(맵경로) if 맵경로 is not None else None
        self._적용기 = 적용기 or 효과적용기(표=표)
        self._예정답: list[str] = []

    # 엔진이 하위 선택을 물을 때 — 고른 수의 시뮬에서 기억한 답을 재연한다.
    def 고르기(self, 질문: str, 후보: list[str]) -> str:
        if self._예정답:
            답 = self._예정답.pop(0)
            if 답 in 후보:
                return 답
            self._예정답.clear()          # 상태가 어긋났다 — 재연을 포기한다
        return self.난수.choice(후보)

    def _일층거르기(self, 상태, 합법수: list[str], 누구: str) -> list[str]:
        if self._맵 is None:
            return 합법수
        원래 = set(상태.가용수단)
        상태.가용수단 = set(합법수)
        try:
            결과 = 거르기(self._맵, 상태, {}, 나는=누구)
        finally:
            상태.가용수단 = 원래
        남은 = [하나 for 하나 in 합법수 if 하나 in set(결과.후보)]
        return 남은 or 합법수

    @staticmethod
    def _복사(상태):
        """상태의 깊은 복사 — pickle 왕복이 copy.deepcopy 보다 수 배 빠르다(상태는 순수
        dataclass 나무라 pickle 가능). 혹시 안 되는 값이 생기면 deepcopy 로 떨어진다."""
        try:
            return pickle.loads(pickle.dumps(상태, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception:
            return copy.deepcopy(상태)

    def _시뮬(self, 상태, 수: str, 누구: str, 씨앗: int) -> tuple[float, list[str]]:
        """수 하나를 복사본에 둬 보고 (점수, 그때 한 하위 선택들) 을 낸다."""
        사본 = self._복사(상태)
        속난수 = random.Random(씨앗)
        답들: list[str] = []

        def 시뮬고르기(질문: str, 후보: list[str]) -> str:
            답 = 속난수.choice(후보)
            답들.append(답)
            return 답

        버림기록 = 기보()
        try:
            수_적용(사본, 수, 누구=누구, 표=self.표, 상수=self.상수표[누구],
                   고르기=시뮬고르기, 기록=버림기록, 효과적용=self._적용기)
            강제트리거_처리(사본, self.표, self.상수표, self._적용기, 시뮬고르기, 버림기록)
        except 적용오류:
            return (-_큰수, 답들)     # 실제로 둘 수 없는 수 — 피한다
        except Exception:              # 시뮬에서만 터지는 길이면 그 수를 피하면 된다
            return (-_큰수, 답들)
        끝 = 승패_확인(사본)
        if 끝 is not None:
            return ((_큰수, 답들) if 끝.승자 == 누구 else (-_큰수, 답들))
        return (상태값(사본, 누구, self.표), 답들)

    def 수_고르기(self, 상태, 합법수: list[str], 누구: str) -> str | None:
        self._예정답.clear()
        if not 합법수:
            return None
        후보 = self._일층거르기(상태, 합법수, 누구)
        # 예산 — 후보가 많으면 하위 선택 표본을 줄이고, 그래도 많으면 무작위로 추린다.
        # 수 하나하나가 공평하게 뽑히므로 좋음/나쁨 선입견이 끼지 않는다(1층 원칙 유지).
        표본 = self.표본수 if len(후보) <= 8 else 1
        if len(후보) > 24:
            후보 = self.난수.sample(후보, 24)

        기준점 = 상태값(상태, 누구, self.표)       # 「더 안 둠」의 점수
        최고점 = 기준점
        최고들: list[tuple[str | None, list[str]]] = [(None, [])]

        for 수 in 후보:
            수최고 = None
            수답 : list[str] = []
            for 몇 in range(표본):
                점수, 답들 = self._시뮬(상태, 수, 누구, self.난수.randrange(1 << 30))
                if 수최고 is None or 점수 > 수최고:
                    수최고, 수답 = 점수, 답들
                if 점수 >= _큰수:
                    break                       # 이기는 수 — 더 볼 것 없다
            if 수최고 is None:
                continue
            if 수최고 > 최고점 + 1e-9:
                최고점 = 수최고
                최고들 = [(수, 수답)]
            elif abs(수최고 - 최고점) <= 1e-9:
                최고들.append((수, 수답))

        고른수, 답들 = self.난수.choice(최고들)
        self._예정답 = list(답들)
        return 고른수
