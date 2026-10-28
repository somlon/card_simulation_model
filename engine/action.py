"""행동 서술자 — 간선의 `후보` · `금지` 항목을 읽는다.

식(engine/expr.py)과 **다른 언어**다. 식은 참/거짓이나 수를 내지만 이쪽은 행동을 가리키는 이름표다.
맵에 실제로 쓰인 꼴:

    발동('호박옥 - 태고의 수해')
    발동('호박옥의 수호자 - 카르분쿨루스', 3)
    발동('호박옥 - 아우렘 티라누스', 4, 제거개수)
    세금차감(카운터최다유닛(), 잔량>=1)
    소환('호박옥의 수호자 - 마르모르', 1, 대체비용=카운터3)
    카운터지출(목적='제거')
    카운터지출(목적='제거'|'재전개', 대상=유일몬스터, 잔량=0까지)

`'제거'|'재전개'` 합집합과 `잔량>=1` 제약까지 받아야 하므로 식 언어보다 느슨하다. 각 인수는
구조만 잡고 값은 원문 조각으로 들고 있는다 — 1층 필터가 할 일은 **고르는 것이 아니라 거르는 것**이라,
인수의 의미까지 해석할 필요가 없다(docs/맵_형식.md 7장).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class 행동오류(Exception):
    pass


@dataclass(frozen=True)
class 인수:
    """하나의 인수. 세 꼴 중 하나다.

    - 위치 인수: `이름` 이 None. 예) `3`, `'호박옥 - 균열'`, `제거개수`
    - 이름붙은 인수: `이름` 과 `값`. 예) `대체비용=카운터3`
    - 제약: `이름` · `비교` · `값`. 예) `잔량>=1`
    """

    이름: str | None
    비교: str | None
    값들: tuple[str, ...]      # `'제거'|'재전개'` 는 두 값

    @property
    def 값(self) -> str:
        return self.값들[0]

    def 글로(self) -> str:
        합 = "|".join(self.값들)
        if self.이름 is None:
            return 합
        return f"{self.이름}{self.비교 or '='}{합}"


@dataclass(frozen=True)
class 행동:
    동작: str                  # 발동 · 소환 · 세금차감 · 표시변경 · 공격선언 · 카운터지출 …
    인수들: tuple[인수, ...]
    원문: str

    @property
    def 카드명(self) -> str | None:
        """첫 위치 인수가 따옴표 문자열이면 카드 이름으로 본다."""
        for 하나 in self.인수들:
            if 하나.이름 is None:
                값 = 하나.값
                if 값.startswith(("'", '"')):
                    return 값[1:-1]
                return None
        return None

    def 글로(self) -> str:
        return f"{self.동작}({', '.join(하나.글로() for 하나 in self.인수들)})"


_머리 = re.compile(r"^\s*([A-Za-z_가-힣][A-Za-z0-9_가-힣]*)\s*\(")
_제약머리 = re.compile(r"^([A-Za-z_가-힣][A-Za-z0-9_가-힣]*)\s*(==|!=|>=|<=|>|<|=)\s*(.+)$", re.S)


def _인수쪼개기(안쪽: str) -> list[str]:
    """괄호 · 대괄호 · 따옴표 안의 쉼표는 건드리지 않고 최상위 쉼표로만 자른다."""
    조각: list[str] = []
    깊이 = 0
    따옴표: str | None = None
    현재: list[str] = []
    for 글자 in 안쪽:
        if 따옴표:
            현재.append(글자)
            if 글자 == 따옴표:
                따옴표 = None
            continue
        if 글자 in "'\"":
            따옴표 = 글자
            현재.append(글자)
            continue
        if 글자 in "([":
            깊이 += 1
        elif 글자 in ")]":
            깊이 -= 1
        if 글자 == "," and 깊이 == 0:
            조각.append("".join(현재))
            현재 = []
            continue
        현재.append(글자)
    남은 = "".join(현재).strip()
    if 남은:
        조각.append(남은)
    return [하나.strip() for 하나 in 조각 if 하나.strip()]


def _값쪼개기(원문: str) -> tuple[str, ...]:
    """`'제거'|'재전개'` 합집합을 쪼갠다. 따옴표 안의 `|` 는 건드리지 않는다."""
    값들: list[str] = []
    따옴표: str | None = None
    현재: list[str] = []
    for 글자 in 원문:
        if 따옴표:
            현재.append(글자)
            if 글자 == 따옴표:
                따옴표 = None
            continue
        if 글자 in "'\"":
            따옴표 = 글자
            현재.append(글자)
            continue
        if 글자 == "|":
            값들.append("".join(현재).strip())
            현재 = []
            continue
        현재.append(글자)
    값들.append("".join(현재).strip())
    return tuple(하나 for 하나 in 값들 if 하나)


def 읽기(원문: str) -> 행동:
    원문 = " ".join(원문.split())
    맞춤 = _머리.match(원문)
    if 맞춤 is None or not 원문.rstrip().endswith(")"):
        raise 행동오류(f"행동 서술자 꼴이 아니다 — {원문!r}")
    동작 = 맞춤.group(1)
    안쪽 = 원문.rstrip()[맞춤.end() : -1]

    인수들: list[인수] = []
    for 조각 in _인수쪼개기(안쪽):
        제약 = _제약머리.match(조각)
        # `카운터최다유닛()` 처럼 함수 호출인 위치 인수는 제약으로 오해하면 안 된다.
        if 제약 and not 조각.startswith(("'", '"')):
            이름, 비교, 값 = 제약.groups()
            인수들.append(인수(이름, "=" if 비교 == "=" else 비교, _값쪼개기(값)))
        else:
            인수들.append(인수(None, None, _값쪼개기(조각)))

    return 행동(동작, tuple(인수들), 원문)


# ---------------------------------------------------------------- 금지 대조

class 대조결과:
    차단 = "차단"
    통과 = "통과"
    보류 = "보류"


구체동작 = frozenset({"발동", "소환", "표시변경", "공격선언", "세금차감", "계승", "릴리스"})
"""카드 한 장과 수 하나를 직접 가리키는 동작. 이 중 서로 다른 둘은 그냥 다른 수다."""

추상동작_꼬리 = "지출"
"""`카운터지출` 처럼 **자원 지출의 범주**를 가리키는 동작의 이름 규칙 (2026-10-25 결정).

`<자원>지출` 꼴로 적고, 그 금지는 개별 후보가 아니라 **간선의 속성**(`자원:` · `목적:`)과
대조한다. 균열을 쏘는 것도 카운터 지출이라 후보 하나하나에 목적을 다시 적는 것은 중복이고,
목적은 원래 간선 단위의 성질이기 때문이다.
"""


def 추상동작인가(동작: str) -> bool:
    return 동작 not in 구체동작 and 동작.endswith(추상동작_꼬리)


def 자원이름(동작: str) -> str:
    """`카운터지출` → `카운터`."""
    return 동작[: -len(추상동작_꼬리)] if 추상동작인가(동작) else 동작


def _술어호출인가(값: str) -> bool:
    """`카운터최다유닛()` 처럼 술어 호출로 적힌 인수인가."""
    return 값.endswith("()") and not 값.startswith(("'", '"'))


def _벗기기(값: str) -> str:
    return 값[1:-1] if 값[:1] in ("'", '"') and len(값) >= 2 else 값


def _이름화(것: Any) -> Any:
    """술어가 돌려준 객체를 비교 가능한 이름(또는 이름 집합)으로 바꾼다."""
    if 것 is None:
        return None
    if isinstance(것, (list, tuple, set)):
        return {_이름화(하나) for 하나 in 것}
    card_id = getattr(것, "card_id", None)
    return card_id if card_id is not None else 것


def _값풀기(값: str, 술어: dict[str, Any] | None) -> tuple[bool, Any]:
    """(풀렸는가, 값). 술어 호출이면 평가해서 이름으로 바꾼다.

    2026-10-25 결정 — **대상 해석은 1층이 한다.** 안 풀면 `금지: 세금차감(임시봉인상태유닛())`
    과 `후보: 세금차감(카운터최다유닛(), …)` 를 영원히 대조할 수 없고, 그러면 함정을 박아 둔
    금지가 작동하지 않는다. 금지의 존재 이유가 사라지므로 1층이 푸는 쪽이 맞다.
    """
    if not _술어호출인가(값):
        return True, _벗기기(값)
    if not 술어:
        return False, 값
    함수 = 술어.get(값[:-2])
    if 함수 is None:
        return False, 값
    try:
        return True, _이름화(함수())
    except Exception:  # noqa: BLE001 — 술어가 못 돌면 대조 불가로 보고한다
        return False, 값


def _맞는가(금지값: Any, 후보값: Any) -> bool:
    """금지 쪽이 집합이면 후보가 그 안에 있으면 걸린다. 둘 다 하나면 같을 때 걸린다."""
    if isinstance(금지값, set):
        if isinstance(후보값, set):
            return bool(금지값 & 후보값)
        return 후보값 in 금지값
    if isinstance(후보값, set):
        return 금지값 in 후보값
    return 금지값 == 후보값


def 금지가_막는가(
    금지: 행동,
    후보: 행동,
    술어: dict[str, Any] | None = None,
    간선속성: dict[str, str] | None = None,
) -> tuple[str, str]:
    """하나의 금지가 하나의 후보를 막는지 본다. (결과, 설명) 을 돌려준다.

    세 갈래다 —
    - `차단` : 금지가 거는 모든 축이 맞는다
    - `통과` : 축 하나라도 분명히 다르다
    - `보류` : 대조가 불가능하다 — 술어를 못 풀었거나(술어 사전이 없거나 미구현),
      추상 동작 금지인데 간선이 `자원:` 을 선언하지 않은 경우

    `술어` 를 주면 인수의 술어 호출을 풀어서 대조한다. `간선속성` 은 후보가 속한 간선의
    `자원` · `목적` 이며 추상 동작 금지가 이것과 대조된다.
    """
    if 추상동작인가(금지.동작):
        return _추상금지(금지, 후보, 간선속성)

    if 금지.동작 != 후보.동작:
        return (대조결과.통과, f"동작이 다르다 ({금지.동작} ≠ {후보.동작})")

    후보_위치 = [하나 for 하나 in 후보.인수들 if 하나.이름 is None]
    후보_이름 = {하나.이름: 하나 for 하나 in 후보.인수들 if 하나.이름 is not None}

    위치자리 = 0
    for 금지인수 in 금지.인수들:
        if 금지인수.이름 is None:
            if 위치자리 >= len(후보_위치):
                return (대조결과.통과, f"후보에 {위치자리 + 1}번째 위치 인수가 없다")
            짝 = 후보_위치[위치자리]
            위치자리 += 1
        else:
            짝 = 후보_이름.get(금지인수.이름)
            if 짝 is None:
                return (대조결과.통과, f"금지가 거는 축 '{금지인수.이름}' 이 후보에 없다")

        걸림 = False
        못품: list[str] = []
        for 금지값 in 금지인수.값들:
            풀린금지, ㄱ = _값풀기(금지값, 술어)
            if not 풀린금지:
                못품.append(금지값)
                continue
            for 후보값 in 짝.값들:
                풀린후보, ㄴ = _값풀기(후보값, 술어)
                if not 풀린후보:
                    못품.append(후보값)
                    continue
                if _맞는가(ㄱ, ㄴ):
                    걸림 = True
                    break
            if 걸림:
                break

        if 걸림:
            continue
        if 못품:
            return (
                대조결과.보류,
                f"{금지인수.글로()} ↔ {짝.글로()} — {', '.join(sorted(set(못품)))} 를 풀 수 없다",
            )
        return (대조결과.통과, f"{금지인수.글로()} 가 후보 값 {짝.글로()} 과 다르다")

    return (대조결과.차단, f"{금지.글로()} 에 걸린다")


def _추상금지(
    금지: 행동, 후보: 행동, 간선속성: dict[str, str] | None
) -> tuple[str, str]:
    속성 = 간선속성 or {}
    자원 = 속성.get("자원")
    필요자원 = 자원이름(금지.동작)

    if 자원 is None:
        return (
            대조결과.보류,
            f"금지 '{금지.동작}' 은 간선 속성과 대조하는데 이 간선에 `자원:` 선언이 없다",
        )
    if 자원 != 필요자원:
        return (대조결과.통과, f"간선 자원 '{자원}' 이 '{필요자원}' 과 다르다")

    for 금지인수 in 금지.인수들:
        if 금지인수.이름 is None:
            continue  # 추상 금지의 위치 인수는 쓰지 않는다
        값 = 속성.get(금지인수.이름)
        if 값 is None:
            return (
                대조결과.통과,
                f"간선이 '{금지인수.이름}' 을 선언하지 않았다 — 그 축을 쓰지 않는 간선으로 본다",
            )
        if 값 not in {_벗기기(하나) for 하나 in 금지인수.값들}:
            return (대조결과.통과, f"간선 {금지인수.이름}='{값}' 이 금지 값과 다르다")

    return (
        대조결과.차단,
        f"{금지.글로()} 에 걸린다 (간선 자원 '{자원}'"
        + (f", 목적 '{속성['목적']}'" if 속성.get("목적") else "")
        + f", 후보 {후보.동작})",
    )
