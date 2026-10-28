"""1층 맵 필터 — docs/맵_형식.md 7장 · 8장.

    합법수 집합 → [이 필터] → 후보 집합 → (상위 층: belief → 착취 → CFR) → 행동 분포

맵은 수를 **고르지 않는다.** 노드의 `조건` · `후보` · `금지` 로 거르기만 하고, 가중치는 없다
(경질 필터 — 7-1 · 7-2). 그래서 이 모듈의 출력에는 점수가 없고 통과/탈락과 그 이유만 있다.

필터가 전부 걸러 버리는 경우(후보 공집합)의 규약은 아직 미결이다 — 7-1 이 "공집합은 버그가 아니라
관측 대상"으로 기록하라고 했으므로 결과 객체에 그대로 담아 보고한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .자료읽기 import 읽기 as _자료읽기

from . import action, expr
from .predicates import 덱상수, 술어집
from .state import 게임상태
from .static import 카드표, 기본카드표


class 맵오류(Exception):
    pass


# ---------------------------------------------------------------- 맵 자료구조

@dataclass(frozen=True)
class 간선:
    이름: str
    조건: str
    후보: tuple[action.행동, ...]
    금지: tuple[action.행동, ...]
    근거: str
    자원: str | None = None
    """이 간선이 쓰는 자원 이름(예: `카운터`). 추상 동작 금지(`카운터지출`)가 이것과 대조된다."""

    목적: str | None = None
    """이 간선의 목적(예: `제거` · `재전개`). 목적은 후보 하나하나의 성질이 아니라 간선의 성질이다."""

    예외: tuple[str, ...] = ()
    """이 간선이 **깨는** 금지들 — 금지를 건 간선의 이름을 적는다.

    2026-10-25 결정. 맵 4-6 이 「체인 방어 예외는 금지선보다 우선한다」고 말로만 적어 둔 것을
    데이터로 옮긴 자리다. D 노드처럼 「기본 금지 + 조건 만족 시 예외」 구조를 쓰는 곳은
    예외 쪽 간선이 기본 금지의 이름을 여기 적는다.
    """

    @property
    def 속성(self) -> dict[str, str]:
        나온것 = {}
        if self.자원:
            나온것["자원"] = self.자원
        if self.목적:
            나온것["목적"] = self.목적
        return 나온것


@dataclass(frozen=True)
class 노드:
    id: str
    이름: str
    공통: bool
    우선순위: int
    불변식: str | None
    위반시: dict[str, Any]
    간선들: tuple[간선, ...]


@dataclass(frozen=True)
class 맵:
    덱: str
    설명_문서: str | None
    상수: 덱상수
    노드들: tuple[노드, ...]
    경로: Path | None = None

    def 노드(self, id: str) -> 노드:
        for 하나 in self.노드들:
            if 하나.id == id:
                return 하나
        raise KeyError(f"없는 노드 {id!r}")


def _행동들(값: Any, 자리: str) -> tuple[action.행동, ...]:
    if 값 is None:
        return ()
    if not isinstance(값, list):
        raise 맵오류(f"{자리} 는 목록이어야 한다 — {값!r}")
    나온것 = []
    for 하나 in 값:
        if not isinstance(하나, str):
            raise 맵오류(f"{자리} 의 항목은 문자열이어야 한다 — {하나!r}")
        나온것.append(action.읽기(하나))
    return tuple(나온것)


def _가중키가_있는가(값: Any) -> bool:
    if isinstance(값, dict):
        return any(키 == "가중" for 키 in 값) or any(
            _가중키가_있는가(안) for 안 in 값.values()
        )
    if isinstance(값, list):
        return any(_가중키가_있는가(안) for 안 in 값)
    return False


def 맵_읽기(경로: str | Path, 상수: 덱상수 | None = None) -> 맵:
    경로 = Path(경로)
    원본 = _자료읽기(경로)
    if not isinstance(원본, dict) or "노드" not in 원본:
        raise 맵오류(f"맵 꼴이 아니다 (최상위에 '노드' 가 없다) — {경로}")

    상수블록 = 원본.get("덱상수") or {}
    쓸상수 = 상수 or 덱상수(
        세금=int(상수블록.get("세금", 0)),
        카운터명=str(상수블록.get("카운터명", "봉인")),
        벽유지최소=int(상수블록.get("벽유지최소", 0)),
        테마=str(상수블록.get("테마", "")),
    )
    # 주석이 아니라 **실제 키**만 본다. 맵 머리 주석에는 "가중을 쓰지 않는다"는 설명이 있다.
    if _가중키가_있는가(원본):
        raise 맵오류(
            f"{경로} 에 `가중:` 키가 있다 — 1층은 경질 필터라 가중치를 두지 않는다"
            " (docs/맵_형식.md 7-1 · 7-2)"
        )

    노드들 = []
    for 줄 in 원본["노드"]:
        간선들 = tuple(
            간선(
                이름=변["이름"],
                조건=str(변.get("조건", "항상")),
                후보=_행동들(변.get("후보"), f"{줄['id']}/{변['이름']}/후보"),
                금지=_행동들(변.get("금지"), f"{줄['id']}/{변['이름']}/금지"),
                근거=str(변.get("근거", "")),
                자원=변.get("자원"),
                목적=변.get("목적"),
                예외=tuple(변.get("예외") or ()),
            )
            for 변 in 줄.get("간선", [])
        )
        노드들.append(
            노드(
                id=str(줄["id"]),
                이름=str(줄.get("이름", "")),
                공통=bool(줄.get("공통", False)),
                우선순위=int(줄.get("우선순위", 0)),
                불변식=줄.get("불변식"),
                위반시=줄.get("위반시") or {},
                간선들=간선들,
            )
        )

    노드들.sort(key=lambda 하나: 하나.우선순위)
    return 맵(
        덱=str(원본.get("덱", 경로.stem)),
        설명_문서=원본.get("설명_문서"),
        상수=쓸상수,
        노드들=tuple(노드들),
        경로=경로,
    )


# ---------------------------------------------------------------- 검증

@dataclass
class 검증결과:
    없는카드: list[tuple[str, str]] = field(default_factory=list)
    없는술어: list[tuple[str, str]] = field(default_factory=list)
    못읽은식: list[tuple[str, str, str]] = field(default_factory=list)
    서술형불변식: list[tuple[str, str]] = field(default_factory=list)
    없는예외: list[tuple[str, str]] = field(default_factory=list)
    자원미선언: list[str] = field(default_factory=list)

    @property
    def 깨끗한가(self) -> bool:
        return not (
            self.없는카드 or self.없는술어 or self.못읽은식 or self.없는예외
        )

    def 글로(self) -> str:
        줄 = []
        for 자리, 이름 in self.없는카드:
            줄.append(f"[없는 카드] {자리}: {이름}")
        for 자리, 이름 in self.없는술어:
            줄.append(f"[없는 술어] {자리}: {이름}()")
        for 자리, 원문, 까닭 in self.못읽은식:
            줄.append(f"[못 읽은 식] {자리}: {원문} — {까닭}")
        for 자리, 이름 in self.없는예외:
            줄.append(f"[없는 예외 대상] {자리}: '{이름}' 이라는 간선이 맵에 없다")
        for 자리, 원문 in self.서술형불변식:
            줄.append(f"[서술형 불변식 — 기계 검사 불가] {자리}: {원문}")
        for 자리 in self.자원미선언:
            줄.append(f"[참고] {자리}: 자원을 쓰는 후보가 있는데 `자원:` 선언이 없다")
        return "\n".join(줄) or "문제 없음"


def _식안의_술어이름(나무: Any) -> set[str]:
    찾은: set[str] = set()
    if isinstance(나무, expr.호출):
        찾은.add(나무.이름)
        for 항 in 나무.인수:
            찾은 |= _식안의_술어이름(항)
        for _, 값 in 나무.이름붙은인수:
            찾은 |= _식안의_술어이름(값)
    elif isinstance(나무, expr.이항):
        찾은 |= _식안의_술어이름(나무.좌) | _식안의_술어이름(나무.우)
    elif isinstance(나무, expr.단항):
        찾은 |= _식안의_술어이름(나무.대상)
    elif isinstance(나무, expr.목록):
        for 항 in 나무.항목:
            찾은 |= _식안의_술어이름(항)
    return 찾은


def 맵_검증(대상: 맵, 카드표_: 카드표 | None = None, 술어이름: set[str] | None = None) -> 검증결과:
    """맵이 실제로 돌아갈 수 있는 상태인지 본다 — 식이 파싱되는가, 카드 이름이 풀에 있는가,
    부르는 술어가 구현돼 있는가. 돌려 보기 전에 한 번 거르는 자리다."""
    표 = 카드표_ or 기본카드표()
    이름들 = 술어이름
    if 이름들 is None:
        빈상태 = 게임상태(나=_빈플레이어("나"), 상대=_빈플레이어("상대"))
        이름들 = set(술어집(빈상태, 대상.상수, 표).사전())

    결과 = 검증결과()

    def 식하나(자리: str, 원문: str, 서술형허용: bool = False) -> None:
        try:
            나무 = expr.파싱(원문)
        except expr.식오류 as 오류:
            if 서술형허용:
                결과.서술형불변식.append((자리, 원문))
            else:
                결과.못읽은식.append((자리, 원문, str(오류)))
            return
        for 이름 in _식안의_술어이름(나무):
            if 이름 not in 이름들:
                결과.없는술어.append((자리, 이름))

    모든간선이름 = {변.이름 for 노 in 대상.노드들 for 변 in 노.간선들}
    추상금지있음 = any(
        action.추상동작인가(금.동작)
        for 노 in 대상.노드들
        for 변 in 노.간선들
        for 금 in 변.금지
    )

    for 노 in 대상.노드들:
        if 노.불변식:
            식하나(f"{노.id}/불변식", str(노.불변식), 서술형허용=True)
        if isinstance(노.위반시, dict) and 노.위반시.get("식"):
            식하나(f"{노.id}/위반시.식", str(노.위반시["식"]))
        for 변 in 노.간선들:
            식하나(f"{노.id}/{변.이름}/조건", 변.조건)
            for 묶음, 자리이름 in ((변.후보, "후보"), (변.금지, "금지")):
                for 하나 in 묶음:
                    카드명 = 하나.카드명
                    if 카드명 and 카드명 not in 표:
                        결과.없는카드.append((f"{노.id}/{변.이름}/{자리이름}", 카드명))
            for 깰것 in 변.예외:
                if 깰것 not in 모든간선이름:
                    결과.없는예외.append((f"{노.id}/{변.이름}/예외", 깰것))
            if 추상금지있음 and 변.후보 and not 변.자원:
                결과.자원미선언.append(f"{노.id}/{변.이름}")
    return 결과


def _빈플레이어(이름: str):
    from .state import 플레이어상태

    return 플레이어상태(이름=이름)


# ---------------------------------------------------------------- 필터 실행

@dataclass
class 간선결과:
    노드: str
    간선: str
    조건: str
    조건값: bool | None
    평가불가: str | None
    통과후보: list[str] = field(default_factory=list)
    차단후보: list[tuple[str, str]] = field(default_factory=list)
    보류: list[tuple[str, str]] = field(default_factory=list)
    깬금지: list[str] = field(default_factory=list)
    """이 간선이 `예외:` 로 깬 금지들. 예외가 조용히 작동하면 안 되므로 보고에 남긴다."""

    근거: str = ""


@dataclass
class 필터결과:
    덱: str
    후보: list[str] = field(default_factory=list)
    """통과한 후보. **순서는 맵에 적힌 순서**이고 좋음/나쁨의 순위가 아니다 — 고르는 일은
    상위 층이 한다(맵_형식.md 7장)."""

    불변식위반: list[dict[str, Any]] = field(default_factory=list)
    간선들: list[간선결과] = field(default_factory=list)
    평가불가: list[tuple[str, str]] = field(default_factory=list)
    보류: list[tuple[str, str]] = field(default_factory=list)

    @property
    def 공집합인가(self) -> bool:
        """7-1 — 공집합은 버그가 아니라 관측 대상이다."""
        return not self.후보

    def 글로(self) -> str:
        줄 = [f"덱: {self.덱}"]
        for 위반 in self.불변식위반:
            줄.append(
                f"  !! 불변식 위반 [{위반['노드']}] {위반['불변식']}"
                + (f" → {위반['효과']} {위반.get('수치', '')}" if 위반.get("효과") else "")
            )
        줄.append(f"  통과 후보 {len(self.후보)}개:")
        for 하나 in self.후보:
            줄.append(f"    - {하나}")
        깬것 = [
            (하나.노드, 하나.간선, 금)
            for 하나 in self.간선들
            for 금 in 하나.깬금지
        ]
        if 깬것:
            줄.append("  예외로 깬 금지:")
            for 노, 변, 금 in 깬것:
                줄.append(f"    > [{노}/{변}] 가 {금} 를 깼다")
        if self.평가불가:
            줄.append("  평가 불가:")
            for 자리, 까닭 in self.평가불가:
                줄.append(f"    ? {자리} — {까닭}")
        if self.보류:
            줄.append("  금지 판정 보류(어휘 불일치):")
            for 자리, 까닭 in self.보류:
                줄.append(f"    ~ {자리} — {까닭}")
        return "\n".join(줄)


def 거르기(
    대상: 맵,
    상태: 게임상태,
    문맥: dict[str, Any] | None = None,
    카드표_: 카드표 | None = None,
    나는: str = "나",
) -> 필터결과:
    """맵 하나를 상태 하나에 적용한다.

    `문맥` 은 맵이 묶지 않는 자유 변수(`타격합` · `제거개수`)를 넣는 자리다. 안 넣으면 그 간선은
    조용히 떨어지지 않고 「평가 불가」로 보고된다.
    """
    술어 = 술어집(상태, 대상.상수, 카드표_ or 기본카드표(), 나는).사전()
    결과 = 필터결과(덱=대상.덱)

    # 노드 전체에서 모은 금지. 금지는 한 간선 안에서만 쓰이는 게 아니라 다른 노드의 후보까지
    # 막는다(B 노드의 '지출 가능 게이트' 가 C 노드의 지출 간선 전부에 걸리는 것 — 맵 4-6).
    걸린금지: list[tuple[str, str, action.행동]] = []   # (자리, 금지를 건 간선 이름, 금지)
    간선목록: list[tuple[노드, 간선, bool | None, str | None]] = []

    for 노 in 대상.노드들:
        if 노.불변식:
            판정 = _불변식판정(노, 술어, 문맥)
            if 판정 is not None:
                결과.불변식위반.append(판정)

        for 변 in 노.간선들:
            try:
                값 = bool(expr.돌리기(변.조건, 술어, 문맥))
                막힘 = None
            except expr.미지정변수 as 오류:
                값, 막힘 = None, f"변수 '{오류.이름}' 미지정"
            except expr.식오류 as 오류:
                값, 막힘 = None, f"식 오류: {오류}"

            간선목록.append((노, 변, 값, 막힘))
            if 값 is True:
                for 금 in 변.금지:
                    걸린금지.append((f"{노.id}/{변.이름}", 변.이름, 금))
            if 막힘:
                결과.평가불가.append((f"{노.id}/{변.이름}/조건", 막힘))

    for 노, 변, 값, 막힘 in 간선목록:
        하나 = 간선결과(
            노드=노.id, 간선=변.이름, 조건=변.조건, 조건값=값,
            평가불가=막힘, 근거=변.근거,
        )
        if 값 is True:
            for 후 in 변.후보:
                막은것 = None
                for 자리, 금지간선, 금 in 걸린금지:
                    if 금지간선 in 변.예외:
                        쪽지 = f"{자리} ({금.글로()})"
                        if 쪽지 not in 하나.깬금지:
                            하나.깬금지.append(쪽지)
                        continue
                    결론, 설명 = action.금지가_막는가(금, 후, 술어, 변.속성)
                    if 결론 == action.대조결과.차단:
                        막은것 = (자리, 설명)
                        break
                    if 결론 == action.대조결과.보류:
                        # 같은 (금지 자리, 후보 동작) 쌍은 한 번만 센다 — 같은 갭이 후보
                        # 개수만큼 복제되면 보고가 읽히지 않는다.
                        하나.보류.append((f"{자리} → {후.동작}(…)", 설명))
                if 막은것:
                    하나.차단후보.append((후.글로(), f"{막은것[0]} — {막은것[1]}"))
                else:
                    하나.통과후보.append(후.글로())
                    if 후.글로() not in 결과.후보:
                        결과.후보.append(후.글로())
        결과.간선들.append(하나)
        for 자리, 설명 in 하나.보류:
            if (자리, 설명) not in 결과.보류:
                결과.보류.append((자리, 설명))

    return 결과


def _불변식판정(노: 노드, 술어: dict[str, Callable[..., Any]], 문맥: dict[str, Any] | None):
    원문 = str(노.불변식)
    try:
        성립 = bool(expr.돌리기(원문, 술어, 문맥))
    except (expr.식오류, expr.미지정변수):
        # B 노드처럼 서술로만 적힌 불변식이 있다. 기계 검사 불가를 숨기지 않는다.
        return None
    if 성립:
        return None
    판정: dict[str, Any] = {"노드": 노.id, "불변식": 원문}
    효과 = 노.위반시.get("효과") if isinstance(노.위반시, dict) else None
    if 효과:
        판정["효과"] = 효과
    식 = 노.위반시.get("식") if isinstance(노.위반시, dict) else None
    if 식:
        try:
            판정["수치"] = expr.돌리기(str(식), 술어, 문맥)
        except (expr.식오류, expr.미지정변수) as 오류:
            판정["수치"] = f"(계산 불가: {오류})"
    return 판정
