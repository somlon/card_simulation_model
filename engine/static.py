"""정적 테이블 + 정적 전처리 — docs/엔진_상태모델.md 2-1 · 8장.

전체 게임에서 한 번 로드하고 읽기 전용으로 모든 상태가 공유한다. 상태 복제 비용을 아끼기 위한
설계이므로(9장) 여기 있는 객체는 절대 게임 중에 고치지 않는다.

8장이 꼽은 두 갭(둘 다 "상태를 못 읽는다"가 아니라 "텍스트를 미리 구조화해 두지 않았다")을
여기서 메운다:

1. `대상지정` — 재정 6차 Q2 의 「대상으로 하고 발동」=대상 / 「고르고」=비대상 을 로드 시 한 번 판정
2. `수입분류` — maps/호박옥_봉인의_계약.md 3-3 의 확정/조건부 표를 data/수입분류.json 에서 읽는다
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

저장소뿌리 = Path(__file__).resolve().parent.parent
카드풀_경로 = 저장소뿌리 / "data" / "card_pool.json"
수입분류_경로 = 저장소뿌리 / "data" / "수입분류.json"


@dataclass(frozen=True)
class 수입항목:
    카드: str
    구분: str      # 확정 · 조건부
    시점: str      # 유지 · 발동
    값: int
    수단: str | None
    근거: str


@dataclass(frozen=True)
class 카드정의:
    code: str
    name: str
    type: str
    level: int | None
    atk: int | None
    df: int | None
    text: str
    tags: tuple[str, ...]
    groups: tuple[str, ...]
    theme: str | None
    race: str | None
    attr: str | None
    color: str | None
    deck: str | None
    subtype: str | None = None
    """마법 카드의 일반 · 신속 · 트리거 · 지속 구분(룰지 1-2). `card_pool.json`의 `subtype`
    필드를 그대로 옮긴 것 — 텍스트를 다시 파싱할 필요가 없다(43회차에 확인)."""

    # --- 정적 전처리 결과 (상태모델 8장)
    대상지정: bool = False
    """카드 텍스트가 「대상으로 하고 발동」을 쓰는가. 재정 6차 Q2 — 「고르고」는 대상이 아니다."""

    계승불가: bool = False
    """「계승할 수 없다」·「계승되지 않는다」가 적혀 있는가 (룰지 3-2 "계승할 수 없는 카드").

    합법수 생성(engine/legalmoves.py)의 일반 소환 계승 판정이 쓴다. 지금 카드 풀 전체에 이
    텍스트를 쓴 카드가 없어(2026-10-25 확인) 효과는 아직 0건이지만, 룰지가 명시한 조건이라
    추측 없이 미리 전처리해 둔다 — 대상지정과 같은 패턴."""

    발동코스트있음: bool = False
    """카드 텍스트에 「~고 발동」 구문이 있는가(43회차 전처리, `engine/legalmoves.py`
    `_발동_후보들` 가 쓴다).

    룰지 3-2 "코스트의 계승"이 이 구문의 뜻을 직접 정의한다 — "「~를 계승하고 발동」이라고
    적힌 효과는, 적힌 카드를 아카이브로 보내야 발동할 수 있다." 즉 "…하고 발동"은 이 룰지가
    명시한 **코스트** 표시 구문이고, 대상 지정(대상으로 하고 발동) · 제외(제외하고 발동) ·
    릴리스(릴리스하고 발동) · 반환(되돌리고 발동) 등 같은 구문이 카드 풀 전체에서 같은 뜻으로
    쓰인다(200장 전수 확인, 43회차) — 추측이 아니라 룰지 3-2가 준 정의의 일반화다. 이 구문이
    **없는** 카드는 (룰지가 "처리의 계승"으로 구분한 것과 같이) 비용이 아니라 결과 처리만 있는
    카드라는 뜻이라, 발동 가능 여부가 카드별로 다른 자원 유무에 걸리지 않는다 — 그래서 이
    플래그 하나로 "일반" 구분 마법 카드의 발동을 코스트 종류를 가리지 않고 일반화할 수 있다."""

    수입: tuple[수입항목, ...] = field(default_factory=tuple)

    @property
    def 몬스터인가(self) -> bool:
        return self.type == "몬스터"


def _정수(값: object) -> int | None:
    try:
        return int(str(값))
    except (TypeError, ValueError):
        return None


class 카드표:
    """이름 → 카드정의. 맵이 카드를 이름으로 가리키므로 이름이 1차 키다."""

    def __init__(self, 정의들: dict[str, 카드정의]):
        self._정의 = 정의들
        self._코드별 = {하나.code: 하나 for 하나 in 정의들.values()}

    def __len__(self) -> int:
        return len(self._정의)

    def __contains__(self, 이름: object) -> bool:
        return 이름 in self._정의

    def __getitem__(self, 이름: str) -> 카드정의:
        try:
            return self._정의[이름]
        except KeyError:
            raise KeyError(
                f"카드 풀에 '{이름}' 이 없다 — 맵의 카드 이름이 data/card_pool.json 과 어긋났다"
            ) from None

    def 찾기(self, 이름: str) -> 카드정의 | None:
        return self._정의.get(이름)

    def 코드로(self, code: str) -> 카드정의 | None:
        return self._코드별.get(code)

    def 이름들(self) -> list[str]:
        return list(self._정의)


def 수입분류_읽기(경로: Path | None = None) -> dict[str, tuple[수입항목, ...]]:
    원본 = json.loads((경로 or 수입분류_경로).read_text(encoding="utf-8"))
    모음: dict[str, list[수입항목]] = {}
    for 줄 in 원본["항목"]:
        하나 = 수입항목(
            카드=줄["카드"],
            구분=줄["구분"],
            시점=줄["시점"],
            값=int(줄["값"]),
            수단=줄.get("수단"),
            근거=줄.get("근거", ""),
        )
        모음.setdefault(하나.카드, []).append(하나)
    return {이름: tuple(값) for 이름, 값 in 모음.items()}


def 카드표_읽기(경로: Path | None = None, 수입경로: Path | None = None) -> 카드표:
    원본 = json.loads((경로 or 카드풀_경로).read_text(encoding="utf-8"))
    수입 = 수입분류_읽기(수입경로)

    정의들: dict[str, 카드정의] = {}
    for 줄 in 원본:
        이름 = 줄["name"]
        본문 = 줄.get("text", "") or ""
        정의들[이름] = 카드정의(
            code=줄.get("code", ""),
            name=이름,
            type=줄.get("type", ""),
            level=_정수(줄.get("level")),
            atk=_정수(줄.get("atk")),
            df=_정수(줄.get("def")),
            text=본문,
            tags=tuple(줄.get("tags") or ()),
            groups=tuple(줄.get("groups") or ()),
            theme=줄.get("theme"),
            race=줄.get("race"),
            attr=줄.get("attr"),
            color=줄.get("color"),
            deck=줄.get("deck"),
            subtype=줄.get("subtype"),
            대상지정="대상으로 하고 발동" in 본문,
            계승불가=("계승할 수 없" in 본문) or ("계승되지 않" in 본문),
            발동코스트있음="고 발동" in 본문,
            수입=수입.get(이름, ()),
        )

    없는카드 = sorted(set(수입) - set(정의들))
    if 없는카드:
        raise ValueError(
            f"data/수입분류.json 이 카드 풀에 없는 이름을 가리킨다: {없는카드}"
        )
    return 카드표(정의들)


_기본표: 카드표 | None = None


def 기본카드표() -> 카드표:
    """프로세스 수명 동안 한 번만 읽는다(2-1 — 모든 상태가 참조만 공유)."""
    global _기본표
    if _기본표 is None:
        _기본표 = 카드표_읽기()
    return _기본표


# ---------------------------------------------------------------------------
# 효과의 1턴 사용 상한 — 룰지 1장 「전역 규칙」
#
#   "모든 효과는 1턴에 1번밖에 사용할 수 없다. 이 턴에 동일한 카드의 동일한 효과를
#    이미 사용했다면 더는 사용할 수 없다."
#   "룰지와 카드 효과가 충돌할 경우 카드 효과를 따른다."
#
# 그래서 기본값은 1이고, 카드 텍스트가 다르게 적었으면 그쪽을 따른다. 예외 문구는 카드
# 풀 전체에서 **문면이 일정하다**(2026-10-28 전수 확인) — 추측해서 읽는 것이 아니라
# 적힌 그대로 읽는다.
#
#   (이 효과는 1턴에 1번 제약을 받지 않는다.)                     → 상한 없음  51개
#   (이 효과는 1턴에 N번까지 사용할 수 있다.)                      → 상한 N     8개
#   (이 효과는 1턴에 1번 제약을 받지 않으며 종료 단계에서만 …)      → 상한 없음  1개
#   (이 효과는 계속해서 사용할 수 있다.)                           → 상한 없음  1개
# ---------------------------------------------------------------------------

import re as _re

_번호머리 = _re.compile(r"(?:(?<=\s)|^)(\d{1,2})\.\s")
_제약없음 = _re.compile(r"1턴에 1번 제약을 받지 않")
_계속사용 = _re.compile(r"계속해서 사용할 수 있다")
_몇번까지 = _re.compile(r"1턴에 (\d+)번까지 사용할 수 있다")


def 효과조각들(텍스트: str) -> dict[int, str]:
    """카드 텍스트를 효과 번호별로 쪼갠다 — `"1. … 2. …"` → `{1: …, 2: …}`.

    번호가 **1부터 하나씩 늘어나는 것만** 머리로 인정한다. 문장 속 숫자나 「럭키 다이스」의
    "- 1: …" 가짓수 목록을 효과 머리로 잘못 읽지 않기 위해서다.
    """
    글 = (텍스트 or "").strip()
    if not 글:
        return {}
    머리들 = []
    다음 = 1
    for 맞음 in _번호머리.finditer(글):
        if int(맞음.group(1)) != 다음:
            continue
        머리들.append((다음, 맞음.start(), 맞음.end()))
        다음 += 1
    if not 머리들:
        return {1: 글}
    조각 = {}
    for 자리, (번호, _시작, 끝) in enumerate(머리들):
        마침 = 머리들[자리 + 1][1] if 자리 + 1 < len(머리들) else len(글)
        조각[번호] = 글[끝:마침].strip()
    return 조각


def 턴사용상한(표: "카드표", 카드이름: str, 번호: int = 1) -> int | None:
    """그 효과를 한 턴에 몇 번까지 쓸 수 있는가. `None` 이면 상한이 없다."""
    정의 = 표.찾기(카드이름)
    if 정의 is None:
        return 1
    조각 = 효과조각들(정의.text or "").get(번호, "")
    if _제약없음.search(조각) or _계속사용.search(조각):
        return None
    맞음 = _몇번까지.search(조각)
    if 맞음:
        return int(맞음.group(1))
    return 1
