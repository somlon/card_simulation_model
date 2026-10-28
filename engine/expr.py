"""맵 식 언어 — docs/맵_형식.md 4장 · 7장.

허용: 산술 비교 · and/or/not · 함수 호출. 금지: 분기 · 반복 · 변수 정의.
이 제약은 설계 결정이므로 파서 자체가 그 이상을 받지 않는다(제안서 5장의 약점 방어).

쓰이는 곳은 노드의 `불변식`, 간선의 `조건`, `위반시.식` 세 자리뿐이다.
간선의 `후보`/`금지`는 식이 아니라 행동 서술자이므로 engine/action.py 가 따로 읽는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


class 식오류(Exception):
    """식을 파싱하지 못했다. 문법 위반이거나 이 언어가 의도적으로 안 받는 구문이다."""


class 미지정변수(Exception):
    """식이 참조하는 자유 변수(제거개수 · 타격합 등)가 평가 문맥에 없다.

    조용히 거짓으로 떨어뜨리면 필터가 후보를 말없이 버린다. 그래서 예외로 올린다.
    """

    def __init__(self, 이름: str):
        self.이름 = 이름
        super().__init__(f"식이 참조하는 변수 '{이름}' 가 평가 문맥에 없다")


# ---------------------------------------------------------------- 토큰

_토큰_규칙 = [
    ("공백", r"[ \t\n]+"),
    ("수", r"\d+(?:\.\d+)?"),
    ("문자열", r"'[^']*'|\"[^\"]*\""),
    ("비교", r"==|!=|>=|<=|>|<"),
    ("산술", r"[+\-*/]"),
    ("괄호", r"[()\[\]]"),
    ("쉼표", r","),
    ("점", r"\."),
    ("등호", r"="),
    ("이름", r"[A-Za-z_가-힣][A-Za-z0-9_가-힣]*"),
]
_토큰_정규식 = re.compile("|".join(f"(?P<{이름}>{패턴})" for 이름, 패턴 in _토큰_규칙))

_예약어 = {"and", "or", "not", "항상"}


@dataclass(frozen=True)
class 토큰:
    종류: str
    값: str
    위치: int


def 토큰화(원문: str) -> list[토큰]:
    결과: list[토큰] = []
    자리 = 0
    while 자리 < len(원문):
        맞춤 = _토큰_정규식.match(원문, 자리)
        if 맞춤 is None:
            raise 식오류(f"읽을 수 없는 문자 {원문[자리]!r} (위치 {자리}) — {원문!r}")
        종류 = 맞춤.lastgroup
        assert 종류 is not None
        if 종류 != "공백":
            결과.append(토큰(종류, 맞춤.group(), 자리))
        자리 = 맞춤.end()
    return 결과


# ---------------------------------------------------------------- 구문 트리

@dataclass(frozen=True)
class 상수:
    값: Any


@dataclass(frozen=True)
class 변수:
    이름: str


@dataclass(frozen=True)
class 호출:
    이름: str
    인수: tuple[Any, ...]
    이름붙은인수: tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class 목록:
    항목: tuple[Any, ...]


@dataclass(frozen=True)
class 단항:
    연산: str
    대상: Any


@dataclass(frozen=True)
class 이항:
    연산: str
    좌: Any
    우: Any


# ---------------------------------------------------------------- 파서

class _파서:
    def __init__(self, 토큰들: list[토큰], 원문: str):
        self.토큰들 = 토큰들
        self.원문 = 원문
        self.자리 = 0

    def 현재(self) -> 토큰 | None:
        return self.토큰들[self.자리] if self.자리 < len(self.토큰들) else None

    def 먹기(self, 종류: str | None = None, 값: str | None = None) -> 토큰:
        현 = self.현재()
        if 현 is None:
            raise 식오류(f"식이 중간에 끊겼다 — {self.원문!r}")
        if 종류 and 현.종류 != 종류:
            raise 식오류(f"{종류} 가 필요한데 {현.값!r} 가 왔다 — {self.원문!r}")
        if 값 and 현.값 != 값:
            raise 식오류(f"{값!r} 가 필요한데 {현.값!r} 가 왔다 — {self.원문!r}")
        self.자리 += 1
        return 현

    def 다음이(self, 값: str) -> bool:
        현 = self.현재()
        return 현 is not None and 현.값 == 값

    def 식(self) -> Any:
        return self.논리합()

    def 논리합(self) -> Any:
        좌 = self.논리곱()
        while self.다음이("or"):
            self.먹기()
            좌 = 이항("or", 좌, self.논리곱())
        return 좌

    def 논리곱(self) -> Any:
        좌 = self.부정()
        while self.다음이("and"):
            self.먹기()
            좌 = 이항("and", 좌, self.부정())
        return 좌

    def 부정(self) -> Any:
        if self.다음이("not"):
            self.먹기()
            return 단항("not", self.부정())
        return self.비교()

    def 비교(self) -> Any:
        좌 = self.덧셈()
        현 = self.현재()
        if 현 is not None and 현.종류 == "비교":
            self.먹기()
            return 이항(현.값, 좌, self.덧셈())
        return 좌

    def 덧셈(self) -> Any:
        좌 = self.곱셈()
        while True:
            현 = self.현재()
            if 현 is None or 현.값 not in ("+", "-"):
                return 좌
            self.먹기()
            좌 = 이항(현.값, 좌, self.곱셈())

    def 곱셈(self) -> Any:
        좌 = self.단항식()
        while True:
            현 = self.현재()
            if 현 is None or 현.값 not in ("*", "/"):
                return 좌
            self.먹기()
            좌 = 이항(현.값, 좌, self.단항식())

    def 단항식(self) -> Any:
        if self.다음이("-"):
            self.먹기()
            return 단항("-", self.단항식())
        return self.기본()

    def 기본(self) -> Any:
        현 = self.현재()
        if 현 is None:
            raise 식오류(f"식이 중간에 끊겼다 — {self.원문!r}")

        if 현.종류 == "수":
            self.먹기()
            값 = float(현.값) if "." in 현.값 else int(현.값)
            return 상수(값)

        if 현.종류 == "문자열":
            self.먹기()
            return 상수(현.값[1:-1])

        if 현.값 == "(":
            self.먹기()
            안 = self.식()
            self.먹기(값=")")
            return 안

        if 현.값 == "[":
            self.먹기()
            항목: list[Any] = []
            if not self.다음이("]"):
                항목.append(self.식())
                while self.다음이(","):
                    self.먹기()
                    항목.append(self.식())
            self.먹기(값="]")
            return 목록(tuple(항목))

        if 현.종류 == "이름":
            return self.이름경로()

        raise 식오류(f"여기 올 수 없는 토큰 {현.값!r} — {self.원문!r}")

    def 이름경로(self) -> Any:
        조각 = [self.먹기("이름").값]
        while self.다음이("."):
            self.먹기()
            조각.append(self.먹기("이름").값)
        경로 = ".".join(조각)

        if 경로 == "항상":
            return 상수(True)

        if not self.다음이("("):
            if 경로 in _예약어:
                raise 식오류(f"예약어 {경로!r} 를 변수로 쓸 수 없다 — {self.원문!r}")
            return 변수(경로)

        self.먹기(값="(")
        인수: list[Any] = []
        이름붙은: list[tuple[str, Any]] = []
        if not self.다음이(")"):
            while True:
                self._인수하나(인수, 이름붙은)
                if self.다음이(","):
                    self.먹기()
                    continue
                break
        self.먹기(값=")")
        return 호출(경로, tuple(인수), tuple(이름붙은))

    def _인수하나(self, 인수: list[Any], 이름붙은: list[tuple[str, Any]]) -> None:
        """`제외=[...]` 형태와 평범한 식을 가른다."""
        현 = self.현재()
        if (
            현 is not None
            and 현.종류 == "이름"
            and self.자리 + 1 < len(self.토큰들)
            and self.토큰들[self.자리 + 1].종류 == "등호"
        ):
            이름 = self.먹기("이름").값
            self.먹기("등호")
            이름붙은.append((이름, self.식()))
        else:
            인수.append(self.식())


def 파싱(원문: str) -> Any:
    원문 = 원문.strip()
    if not 원문:
        raise 식오류("빈 식")
    파서 = _파서(토큰화(원문), 원문)
    나무 = 파서.식()
    남은 = 파서.현재()
    if 남은 is not None:
        raise 식오류(f"식 뒤에 남은 토큰 {남은.값!r} — {원문!r}")
    return 나무


# ---------------------------------------------------------------- 평가

_비교연산: dict[str, Callable[[Any, Any], Any]] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


def 평가(나무: Any, 술어: dict[str, Callable[..., Any]], 문맥: dict[str, Any] | None = None) -> Any:
    """`술어`는 이름 → 함수, `문맥`은 자유 변수(제거개수 · 타격합 등) 바인딩."""
    문맥 = 문맥 or {}

    if isinstance(나무, 상수):
        return 나무.값

    if isinstance(나무, 목록):
        return [평가(항, 술어, 문맥) for 항 in 나무.항목]

    if isinstance(나무, 변수):
        if 나무.이름 in 문맥:
            return 문맥[나무.이름]
        if 나무.이름 in 술어:
            return 술어[나무.이름]()
        raise 미지정변수(나무.이름)

    if isinstance(나무, 호출):
        함수 = 술어.get(나무.이름)
        if 함수 is None:
            raise 식오류(f"없는 술어 {나무.이름!r} — docs/맵_형식.md 4장 목록에 추가하고 구현해야 한다")
        인수 = [평가(항, 술어, 문맥) for 항 in 나무.인수]
        이름붙은 = {이름: 평가(값, 술어, 문맥) for 이름, 값 in 나무.이름붙은인수}
        return 함수(*인수, **이름붙은)

    if isinstance(나무, 단항):
        if 나무.연산 == "not":
            return not 평가(나무.대상, 술어, 문맥)
        return -평가(나무.대상, 술어, 문맥)

    if isinstance(나무, 이항):
        if 나무.연산 == "and":
            return bool(평가(나무.좌, 술어, 문맥)) and bool(평가(나무.우, 술어, 문맥))
        if 나무.연산 == "or":
            return bool(평가(나무.좌, 술어, 문맥)) or bool(평가(나무.우, 술어, 문맥))
        좌 = 평가(나무.좌, 술어, 문맥)
        우 = 평가(나무.우, 술어, 문맥)
        if 나무.연산 in _비교연산:
            return _비교연산[나무.연산](좌, 우)
        if 나무.연산 == "+":
            return 좌 + 우
        if 나무.연산 == "-":
            return 좌 - 우
        if 나무.연산 == "*":
            return 좌 * 우
        if 나무.연산 == "/":
            return 좌 / 우

    raise 식오류(f"평가할 수 없는 노드 {나무!r}")


def 돌리기(원문: str, 술어: dict[str, Callable[..., Any]], 문맥: dict[str, Any] | None = None) -> Any:
    return 평가(파싱(원문), 술어, 문맥)
