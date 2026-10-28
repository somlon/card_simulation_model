"""2단계 완성 기준 항목1(상태 전이) 테스트 — `engine/resolve.py` 다섯 원시 동작.

    python -m pytest tests -q      (pytest 가 있으면)
    python tests/test_resolve.py   (없으면 — 아래 __main__ 이 직접 돌린다)
"""

from __future__ import annotations

import sys
from pathlib import Path

뿌리 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(뿌리))

from engine import resolve
from engine.state import 게임상태, 앞뒤, 존, 카드인스턴스, 표시, 플레이어상태


def _판() -> 게임상태:
    return 게임상태(나=플레이어상태(이름="나"), 상대=플레이어상태(이름="상대"))


# ---------------------------------------------------------------- 1. 이동

def test_이동_드로우는_맨_위에서_순서대로():
    상태 = _판()
    카드들 = [카드인스턴스(card_id=f"카드{i}", 소유="나", 존=존.메인덱) for i in range(3)]
    상태.나.메인덱 = list(카드들)

    뽑힌것 = resolve.이동(상태, 존.패, 에서=존.메인덱, 소유="나", 수=2)

    assert [하나.card_id for 하나 in 뽑힌것] == ["카드0", "카드1"]
    assert [하나.card_id for 하나 in 상태.나.패] == ["카드0", "카드1"]
    assert [하나.card_id for 하나 in 상태.나.메인덱] == ["카드2"]
    assert all(하나.존 is 존.패 and 하나.소유 == "나" for 하나 in 뽑힌것)


def test_이동_덱이_모자라면_있는_만큼만():
    상태 = _판()
    상태.나.메인덱 = [카드인스턴스(card_id="마지막", 소유="나", 존=존.메인덱)]
    뽑힌것 = resolve.이동(상태, 존.패, 에서=존.메인덱, 소유="나", 수=5)
    assert len(뽑힌것) == 1
    assert 상태.나.메인덱 == []


def test_이동_파괴하면_필드를_벗어나_카운터가_리셋된다():
    상태 = _판()
    유닛 = 카드인스턴스(card_id="호박옥의 수호자 - 마르모르", 소유="나", 존=존.유닛존, 칸=2, 표시=표시.공격)
    유닛.카운터["봉인"] = 3
    상태.나.유닛존[2] = 유닛

    resolve.이동(상태, 존.아카이브, 카드=유닛)

    assert 상태.나.유닛존[2] is None
    assert 유닛 in 상태.나.아카이브
    assert 유닛.존 is 존.아카이브
    assert 유닛.칸 is None
    assert 유닛.카운터 == {}  # 상태모델 6장 — 필드를 벗어나면 카운터 리셋


def test_이동_소환은_기본으로_공격_표시_앞면이다():
    상태 = _판()
    손패 = 카드인스턴스(card_id="던전마스터 다크나이트", 소유="나", 존=존.패)
    상태.나.패 = [손패]

    resolve.이동(상태, 존.유닛존, 카드=손패)

    assert 손패.존 is 존.유닛존
    assert 손패 in 상태.나.유닛존
    assert 손패.앞뒤 is 앞뒤.앞면
    assert 손패.표시 is 표시.공격
    assert 손패.존입장턴 == 상태.턴번호


def test_이동_세트는_뒷면이고_뒷면으로_초기화를_받는다():
    상태 = _판()
    손패 = 카드인스턴스(card_id="호박옥 - 균열", 소유="나", 존=존.패)
    상태.나.패 = [손패]

    resolve.이동(상태, 존.이펙트존, 카드=손패, 앞뒤=앞뒤.뒷면)

    assert 손패.존 is 존.이펙트존
    assert 손패.앞뒤 is 앞뒤.뒷면
    assert 손패.표시 is None


def test_이동_덱_맨아래로_되돌리기():
    상태 = _판()
    기존 = 카드인스턴스(card_id="기존", 소유="나", 존=존.메인덱)
    상태.나.메인덱 = [기존]
    유닛 = 카드인스턴스(card_id="되돌릴 카드", 소유="나", 존=존.유닛존, 칸=0)
    상태.나.유닛존[0] = 유닛

    resolve.이동(상태, 존.메인덱, 카드=유닛, 맨아래=True)

    assert [하나.card_id for 하나 in 상태.나.메인덱] == ["기존", "되돌릴 카드"]
    assert 상태.나.유닛존[0] is None


def test_이동_빈칸_없으면_해결오류():
    상태 = _판()
    상태.나.유닛존 = [카드인스턴스(card_id=f"자리{i}", 소유="나", 존=존.유닛존, 칸=i) for i in range(5)]
    for i, 카드 in enumerate(상태.나.유닛존):
        카드.칸 = i
    새카드 = 카드인스턴스(card_id="여섯째", 소유="나", 존=존.패)
    상태.나.패 = [새카드]
    try:
        resolve.이동(상태, 존.유닛존, 카드=새카드)
    except resolve.해결오류:
        pass
    else:
        raise AssertionError("빈 칸이 없는데 이동이 성공했다")


# ---------------------------------------------------------------- 2. 카운터

def test_카운터_놓기와_떼기():
    상태 = _판()
    카드 = 카드인스턴스(card_id="호박옥의 수호자 - 카르분쿨루스", 소유="나", 존=존.유닛존, 칸=0)

    assert resolve.카운터(상태, 카드, 증감=2) == 2
    assert resolve.카운터(상태, 카드, 증감=1) == 3
    assert resolve.카운터(상태, 카드, 증감=-3) == 0
    assert "봉인" not in 카드.카운터  # 0 이 되면 키 자체를 지운다(카운터수() 는 여전히 0)
    assert 카드.카운터수() == 0


def test_카운터_있는_만큼만_뗄_수_있다():
    상태 = _판()
    카드 = 카드인스턴스(card_id="카드", 소유="나", 존=존.유닛존, 칸=0)
    resolve.카운터(상태, 카드, 증감=1)
    try:
        resolve.카운터(상태, 카드, 증감=-2)
    except resolve.해결오류:
        pass
    else:
        raise AssertionError("있는 것보다 많이 떼는데 성공했다")


# ---------------------------------------------------------------- 3. 수치

def test_수치_LP_증감과_배율():
    상태 = _판()
    assert resolve.수치(상태, "나", "LP", 증감=-1500) == 3500
    assert 상태.나.hp == 3500
    assert resolve.수치(상태, 상태.나, "LP", 배율=0.5) == 1750


def test_수치_ATK_DEF_증감은_누적된다():
    상태 = _판()
    카드 = 카드인스턴스(card_id="카드", 소유="나", 존=존.유닛존, 칸=0)
    resolve.수치(상태, 카드, "ATK", 증감=500)
    resolve.수치(상태, 카드, "ATK", 증감=300)
    resolve.수치(상태, 카드, "DEF", 배율=0.5)
    resolve.수치(상태, 카드, "DEF", 배율=0.5)
    assert 카드.능력치증감["ATK"] == 800
    assert 카드.능력치배율["DEF"] == 0.25


def test_수치_증감과_배율_동시지정은_오류():
    상태 = _판()
    try:
        resolve.수치(상태, "나", "LP", 증감=1, 배율=1.0)
    except resolve.해결오류:
        pass
    else:
        raise AssertionError("증감과 배율을 동시에 줬는데 성공했다")


# ---------------------------------------------------------------- 4. 표시변경

def test_표시변경_공수():
    상태 = _판()
    카드 = 카드인스턴스(card_id="카드", 소유="나", 존=존.유닛존, 칸=0, 표시=표시.공격)
    resolve.표시변경(상태, 카드, 공수=표시.수비)
    assert 카드.표시 is 표시.수비


def test_표시변경_뒷면은_뒷면으로_초기화를_받는다():
    상태 = _판()
    카드 = 카드인스턴스(card_id="카드", 소유="나", 존=존.유닛존, 칸=0, 표시=표시.공격)
    카드.카운터["봉인"] = 2
    카드.턴표지.add("소환됨")

    resolve.표시변경(상태, 카드, 앞뒤=앞뒤.뒷면)

    assert 카드.앞뒤 is 앞뒤.뒷면
    assert 카드.카운터 == {}
    assert 카드.턴표지 == set()


def test_표시변경_인수없으면_오류():
    상태 = _판()
    카드 = 카드인스턴스(card_id="카드", 소유="나", 존=존.유닛존, 칸=0)
    try:
        resolve.표시변경(상태, 카드)
    except resolve.해결오류:
        pass
    else:
        raise AssertionError("앞뒤도 공수도 없는데 성공했다")


# ---------------------------------------------------------------- 5. 금지

def test_금지_카드에_걸기():
    상태 = _판()
    카드 = 카드인스턴스(card_id="카드", 소유="나", 존=존.유닛존, 칸=0)
    표지 = resolve.금지(상태, 카드, "공격", "이번턴")
    assert 표지 == "금지:공격:이번턴"
    assert 표지 in 카드.상태표지


def test_금지_플레이어에_걸기():
    상태 = _판()
    resolve.금지(상태, 상태.나, "발동", "다음상대턴종료까지")
    assert "금지:발동:다음상대턴종료까지" in 상태.나.상태표지


def test_금지_중복은_집합이라_한_번만_남는다():
    상태 = _판()
    카드 = 카드인스턴스(card_id="카드", 소유="나", 존=존.유닛존, 칸=0)
    resolve.금지(상태, 카드, "효과", "영구")
    resolve.금지(상태, 카드, "효과", "영구")
    assert 카드.상태표지 == {"금지:효과:영구"}


def test_금지_대상_오류():
    상태 = _판()
    try:
        resolve.금지(상태, "나", "발동", "영구")
    except resolve.해결오류:
        pass
    else:
        raise AssertionError("문자열 대상인데 성공했다")


# ---------------------------------------------------------------- 직접 실행

def _직접돌리기() -> int:
    통과 = 실패 = 0
    for 이름, 함수 in sorted(globals().items()):
        if not 이름.startswith("test_") or not callable(함수):
            continue
        try:
            함수()
        except Exception as 오류:  # noqa: BLE001 — 테스트 러너 자리
            실패 += 1
            print(f"FAIL {이름}: {type(오류).__name__}: {오류}")
        else:
            통과 += 1
            print(f"ok   {이름}")
    print(f"\n{통과} passed, {실패} failed")
    return 1 if 실패 else 0


if __name__ == "__main__":
    raise SystemExit(_직접돌리기())
