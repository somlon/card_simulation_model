"""헤아림 플레이어 시험 — docs/대전논리_설계.md 의 약속을 지키는지.

`tests/test_filter.py` 와 같은 꼴(표준 라이브러리만, 직접 실행)이다.

    python tests/test_policy.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.legalmoves import 합법수_생성
from engine.players import 무작위플레이어, 헤아림플레이어, 상태값
from engine.predicates import 덱상수
from engine.deck import 대전_준비
from engine.state import 단계, 앞뒤, 존, 카드인스턴스, 표시
from engine.static import 기본카드표

통과 = 0
실패 = 0


def _하나돌리기(이름, 함수):
    global 통과, 실패
    try:
        함수()
    except AssertionError as 오류:
        실패 += 1
        print(f"FAIL {이름}: {오류}")
    else:
        통과 += 1
        print(f"ok   {이름}")


상수표 = {"나": 덱상수(세금=2, 카운터명="봉인", 벽유지최소=1, 테마="호박옥"),
       "상대": 덱상수(세금=0, 카운터명="봉인", 벽유지최소=0, 테마="던전마스터")}


def _판짜기(시드=1):
    표 = 기본카드표()
    상태, 난수 = 대전_준비("호박옥", "던전마스터", 시드, 표)
    return 표, 상태, 난수


def _숫자(값):
    try:
        return int(값)
    except (TypeError, ValueError):
        return 0


def _호박옥몬스터들():
    import json
    풀 = json.loads((Path(__file__).resolve().parent.parent / "data" / "card_pool.json")
                   .read_text(encoding="utf-8"))
    카드들 = 풀 if isinstance(풀, list) else 풀.get("cards", 풀)
    return [(_숫자(c.get("atk")), c["name"]) for c in 카드들
            if c.get("theme") == "호박옥" and _숫자(c.get("atk")) > 0]


def _센몬스터(표):
    """공격력 1500 이상의 호박옥 몬스터 하나 — 카드 풀에서 찾는다(추측으로 안 박는다)."""
    센것 = [하나 for 하나 in _호박옥몬스터들() if 하나[0] >= 1500]
    assert 센것, "호박옥에 공격력 1500 이상 몬스터가 없다"
    힘, 이름 = max(센것)
    return 이름, 힘


def _유닛놓기(상태, 누구, 이름, 칸, 공수=표시.공격):
    쪽 = 상태.플레이어(누구)
    유닛 = 카드인스턴스(card_id=이름, 소유=누구, 존=존.유닛존, 칸=칸,
                   앞뒤=앞뒤.앞면, 표시=공수, 존입장턴=0)
    쪽.유닛존[칸] = 유닛
    return 유닛


def 시험_즉승수를_잡는다():
    표, 상태, 난수 = _판짜기()
    이름, 공격력 = _센몬스터(표)
    상태.턴번호 = 4
    상태.턴플레이어 = "나"
    상태.단계 = 단계.전투
    _유닛놓기(상태, "나", 이름, 0)
    상대 = 상태.플레이어("상대")
    상대.유닛존 = [None] * len(상대.유닛존)      # 직접공격 길이 열린다
    상대.hp = min(500, 공격력 - 1)
    상태.가용수단 = 합법수_생성(상태, 표, "나", 상수표["나"])
    합법수 = sorted(상태.가용수단)
    공격수 = [수 for 수 in 합법수 if 수.startswith("공격선언")]
    assert 공격수, f"공격 수가 없다: {합법수}"
    두는이 = 헤아림플레이어("나", random.Random(7), 표, 상수표)
    고른 = 두는이.수_고르기(상태, 합법수, "나")
    assert 고른 in 공격수, f"즉승 공격 대신 {고른!r} 을 골랐다"


def 시험_자살공격은_피한다():
    표, 상태, 난수 = _판짜기()
    이름, 공격력 = _센몬스터(표)
    상태.턴번호 = 4
    상태.턴플레이어 = "나"
    상태.단계 = 단계.전투
    # 내 쪽 — 공격력이 바닥인 몬스터 하나, HP 는 역파괴 피해로 바로 지는 수준
    약한것 = min(_호박옥몬스터들(), key=lambda x: x[0])
    _유닛놓기(상태, "나", 약한것[1], 0)
    나 = 상태.플레이어("나")
    나.hp = max(100, 공격력 - 약한것[0] - 100)   # 자살 공격이면 그 즉시 패배
    _유닛놓기(상태, "상대", 이름, 0)
    상태.가용수단 = 합법수_생성(상태, 표, "나", 상수표["나"])
    합법수 = sorted(상태.가용수단)
    자살수 = [수 for 수 in 합법수 if 수.startswith("공격선언")]
    if not 자살수:
        return                           # 이 판 구성에서 공격 수가 안 나면 시험 대상이 아니다
    두는이 = 헤아림플레이어("나", random.Random(7), 표, 상수표)
    고른 = 두는이.수_고르기(상태, 합법수, "나")
    assert 고른 not in 자살수, f"즉시 패배하는 자살 공격 {고른!r} 을 골랐다"


def 시험_같은씨앗이면_같은수():
    표, 상태, 난수 = _판짜기(시드=3)
    상태.가용수단 = 합법수_생성(상태, 표, "나", 상수표["나"])
    합법수 = sorted(상태.가용수단)
    if not 합법수:
        return
    고른들 = set()
    for _ in range(3):
        두는이 = 헤아림플레이어("나", random.Random(11), 표, 상수표)
        고른들.add(두는이.수_고르기(상태, 합법수, "나"))
    assert len(고른들) == 1, f"같은 씨앗인데 수가 갈렸다: {고른들}"


def 시험_헤아림이_무작위를_이긴다():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import importlib
    듀얼 = importlib.import_module("듀얼")
    승 = {"나": 0, "상대": 0, "미정": 0}
    for 시드 in range(12):
        끝, _ = 듀얼.한판("호박옥", "던전마스터", "헤아림", "무작위",
                      시드=시드, 최대턴=200, 조용히=True)
        승[끝.승자 if 끝 else "미정"] += 1
    assert 승["미정"] == 0, f"미정이 나왔다: {승}"
    assert 승["나"] >= 8, f"무작위 상대 12판에서 {승['나']}승뿐이다: {승}"


def 주문() -> int:
    for 함수 in (
        시험_즉승수를_잡는다,
        시험_자살공격은_피한다,
        시험_같은씨앗이면_같은수,
        시험_헤아림이_무작위를_이긴다,
    ):
        _하나돌리기(함수.__name__, 함수)
    print(f"\n{통과} passed, {실패} failed")
    return 1 if 실패 else 0


if __name__ == "__main__":
    raise SystemExit(주문())
