"""한 판을 끝까지 두는 대전 환경 — 완성_기준_듀얼.md 3 · 6 · 7번.

    python scripts/듀얼.py --덱 호박옥 --상대 던전마스터        # 사람이 둔다
    python scripts/듀얼.py --시드 1 --나 무작위 --상대 무작위    # 자동 대전
    python scripts/듀얼.py --시드 1 --나 필터 --상대 무작위 --조용히

사람 쪽은 보드와 합법수 목록을 보고 번호를 친다. `q` 는 기권, 빈 줄은 「더 안 둠」(단계를
넘긴다). 비대화 모드(`--수` 로 수 목록을 주거나 표준입력으로 넣기)도 된다.

**아직 안 되는 것** — 카드 효과는 `cards/효과/<덱>.yaml` 에 적힌 것만 실제로 적용된다.
안 적힌 효과는 발동해도 상태가 안 바뀌고 기보에 「효과 미구현」으로 남는다. 추측으로
채우지 않는 것이 완성_기준_듀얼.md 2번의 요구다. 미구현 목록은 `docs/듀얼_점검.md`.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.deck import 대전_준비
from engine.effects import 효과적용기
from engine.legalmoves import 합법수_생성
from engine.players import 무작위플레이어, 필터플레이어
from engine.predicates import 덱상수
from engine.state import 게임상태, 단계, 앞뒤, 표시
from engine.static import 기본카드표
from engine.turn import (
    강제트리거_처리,
    기보,
    반응형트리거_기회,
    수_적용,
    승패_확인,
    적용오류,
    종료,
    종료단계,
    준비단계,
)

맵파일 = {
    "호박옥": "호박옥_봉인의_계약.yaml",
    "던전마스터": "던전마스터_셔플.yaml",
}

# 맵 YAML 머리에 적힌 덱 상수와 같은 값. 맵을 읽는 플레이어는 맵에서 가져오고,
# 여기 표는 맵을 안 읽는 쪽(사람 · 무작위)이 세금차감을 판정할 때 쓴다.
덱상수표 = {
    "호박옥": 덱상수(세금=2, 카운터명="봉인", 벽유지최소=1, 테마="호박옥"),
    "던전마스터": 덱상수(세금=0, 카운터명="봉인", 벽유지최소=0, 테마="던전마스터"),
}

단계순서 = (단계.진행, 단계.전투, 단계.정비)


def 보드_글(상태: 게임상태, 표, 누구: str = "나") -> str:
    줄 = []
    for 쪽이름 in ("상대", "나"):
        쪽 = 상태.플레이어(쪽이름)
        표식 = " ←턴" if 상태.턴플레이어 == 쪽이름 else ""
        줄.append(
            f"[{쪽이름}] HP {쪽.hp} / 패 {len(쪽.패)} / 메인덱 {len(쪽.메인덱)} "
            f"/ 상급덱 {len(쪽.상급덱)} / 아카이브 {len(쪽.아카이브)}{표식}"
        )
        유닛글 = []
        for 칸, 하나 in enumerate(쪽.유닛존):
            if 하나 is None:
                continue
            정의 = 표.찾기(하나.card_id)
            수치 = f" {정의.atk}/{정의.df}" if 정의 and 정의.몬스터인가 else ""
            카운터 = f" [봉인{하나.카운터수()}]" if 하나.카운터수() else ""
            모양 = "뒷면" if 하나.앞뒤 is 앞뒤.뒷면 else (하나.표시.value if 하나.표시 else "")
            유닛글.append(f"{칸}:{하나.card_id}{수치}({모양}){카운터}")
        줄.append("   유닛: " + (" | ".join(유닛글) if 유닛글 else "-"))
        이펙트글 = [
            f"{칸}:" + ("뒷면" if 하나.앞뒤 is 앞뒤.뒷면 else 하나.card_id)
            for 칸, 하나 in enumerate(쪽.이펙트존)
            if 하나 is not None
        ]
        줄.append("   이펙트: " + (" | ".join(이펙트글) if 이펙트글 else "-"))
    return "\n".join(줄)


def 패_글(상태: 게임상태, 표, 누구: str) -> str:
    쪽 = 상태.플레이어(누구)
    if not 쪽.패:
        return "   (패 없음)"
    줄 = []
    for 번호, 하나 in enumerate(쪽.패):
        정의 = 표.찾기(하나.card_id)
        본문 = (정의.text or "").replace("\n", "\n        ") if 정의 else ""
        줄.append(f"   {번호}. {하나.card_id}\n        {본문}")
    return "\n".join(줄)


class 사람플레이어:
    """표준입력으로 수를 받는다. 비대화 모드면 미리 받은 수 목록을 차례로 쓴다."""

    def __init__(self, 이름: str, 미리정한수: list[str] | None = None):
        self.이름 = 이름
        self.대기열 = list(미리정한수 or [])
        self.기권했나 = False
        self._빈응답 = 0
        self._입력끝 = False

    def _묻기(self, 글: str) -> str:
        """대기열 → 표준입력 순. 터미널이 아니면 **묻지 않는다.**

        비대화 실행(CI · 자동 점검)에서 `input()` 을 부르면 그대로 멈춘다. 대기열이 비었고
        표준입력이 터미널이 아니면 「더 안 둠」(빈 줄)으로 떨어뜨리고, 그 상태가 길게
        이어지면(판이 아무 데도 안 가는 것) 기권으로 끝낸다 — 무한 대기 대신 끝나는 쪽.
        """
        if self.대기열:
            답 = self.대기열.pop(0)
            print(글 + 답 + "   (미리 정한 입력)")
            return 답
        if self._입력끝 or not sys.stdin.isatty():
            self._빈응답 += 1
            return "q" if self._빈응답 > 200 else ""
        try:
            return input(글).strip()
        except EOFError:
            # 표준입력이 닫혔다(파이프 · /dev/null). `isatty()` 는 쉘에 따라 True 를 내놓기도
            # 해서 믿을 수 없으므로, 한 번 EOF 를 만나면 그 뒤로는 묻지 않는다.
            self._입력끝 = True
            self._빈응답 += 1
            return ""

    def 고르기(self, 질문: str, 후보: list[str]) -> str:
        if len(후보) == 1:
            return 후보[0]
        print("   " + 질문)
        for 번호, 하나 in enumerate(후보):
            print(f"     {번호}. {하나}")
        while True:
            답 = self._묻기("   번호> ")
            if 답.isdigit() and 0 <= int(답) < len(후보):
                return 후보[int(답)]
            if (self._입력끝 or not sys.stdin.isatty()) and not self.대기열:
                # 비대화 실행 — 물어볼 사람이 없다. 첫 후보로 떨어뜨린다(되묻기 금지).
                print("   (비대화 — 첫 후보로)")
                return 후보[0]
            print("   그 번호는 없다.")

    def 수_고르기(self, 상태: 게임상태, 합법수: list[str], 누구: str) -> str | None:
        if not 합법수:
            print("   둘 수 있는 수가 없다 — 다음 단계로.")
            return None
        print(f"   [{상태.단계.value} 단계] 둘 수 있는 수:")
        for 번호, 하나 in enumerate(합법수):
            print(f"     {번호}. {하나}")
        while True:
            답 = self._묻기("   번호 (빈 줄=다음 단계, q=기권)> ")
            if 답 == "":
                return None
            if 답.lower() == "q":
                self.기권했나 = True
                return None
            if 답.isdigit() and 0 <= int(답) < len(합법수):
                return 합법수[int(답)]
            print("   그 번호는 없다.")


def 역할_만들기(종류: str, 이름: str, 난수: random.Random, 테마: str, 미리정한수=None):
    if 종류 == "사람":
        return 사람플레이어(이름, 미리정한수)
    if 종류 == "무작위":
        return 무작위플레이어(이름, 난수)
    if 종류 == "필터":
        경로 = Path(__file__).resolve().parent.parent / "maps" / 맵파일[테마]
        return 필터플레이어(이름, 난수, 경로)
    raise SystemExit(f"모르는 역할: {종류}")


def 한판(
    나_테마: str,
    상대_테마: str,
    나_역할: str,
    상대_역할: str,
    시드: int,
    최대턴: int = 200,
    조용히: bool = False,
    미리정한수: list[str] | None = None,
) -> tuple[종료 | None, 기보]:
    표 = 기본카드표()
    적용기 = 효과적용기(표=표)
    상태, 난수 = 대전_준비(나_테마, 상대_테마, 시드, 표)
    기록 = 기보()
    역할 = {
        "나": 역할_만들기(나_역할, "나", 난수, 나_테마, 미리정한수),
        "상대": 역할_만들기(상대_역할, "상대", 난수, 상대_테마),
    }
    상수표 = {"나": 덱상수표[나_테마], "상대": 덱상수표[상대_테마]}
    기록.적기(f"시드 {시드} · 나={나_테마}({나_역할}) vs 상대={상대_테마}({상대_역할})")
    기록.적기(f"선공: {상태.선공}")

    끝 = None
    while 끝 is None and 상태.턴번호 <= 최대턴:
        누구 = 상태.턴플레이어
        나역 = 역할[누구]
        기록.적기(f"[턴 {상태.턴번호} · {누구}]")

        끝 = 준비단계(상태, 누구, 나역.고르기, 기록)
        if 끝 is not None:
            break

        for 이번단계 in 단계순서:
            상태.단계 = 이번단계
            while True:
                상태.가용수단 = 합법수_생성(상태, 표, 누구, 상수표[누구])
                합법수 = sorted(상태.가용수단)
                if not 조용히 and isinstance(나역, 사람플레이어):
                    print("\n" + 보드_글(상태, 표, 누구))
                    print(f"   내 패 ({누구}):")
                    print(패_글(상태, 표, 누구))
                고른수 = 나역.수_고르기(상태, 합법수, 누구)
                if getattr(나역, "기권했나", False):
                    반대 = "상대" if 누구 == "나" else "나"
                    끝 = 종료(승자=반대, 조건="기권", 근거="플레이어가 기권했다")
                    break
                if 고른수 is None:
                    break
                try:
                    수_적용(
                        상태, 고른수, 누구=누구, 표=표, 상수=상수표[누구],
                        고르기=나역.고르기, 기록=기록, 효과적용=적용기,
                    )
                    강제트리거_처리(상태, 표, 상수표, 적용기, 나역.고르기, 기록)
                    반응형트리거_기회(상태, 표, 상수표, 역할, 적용기, 기록)
                except 적용오류 as 오류:
                    기록.적기(f"  !! 적용 실패({고른수}): {오류}")
                    break
                끝 = 승패_확인(상태)
                if 끝 is not None:
                    break
            if 끝 is not None:
                break
        if 끝 is not None:
            break

        종료단계(
            상태, 누구, 기록,
            표=표, 상수표=상수표, 효과적용=적용기, 고르기=나역.고르기,
        )
        끝 = 승패_확인(상태)

    if 끝 is None:
        기록.적기(f"— {최대턴}턴 상한에 걸려 중단 (승패 미정)")
    else:
        기록.적기(f"— 종료: {끝.승자} 승 ({끝.조건}) · {끝.근거}")
    return 끝, 기록


def 주문() -> int:
    받기 = argparse.ArgumentParser(description="뉴 네오 듀얼 환경")
    받기.add_argument("--덱", default="호박옥", help="내 덱 테마")
    받기.add_argument("--상대", default="던전마스터", help="상대 덱 테마")
    받기.add_argument("--나", dest="나역할", default=None, help="사람 · 무작위 · 필터")
    받기.add_argument("--상대역할", default=None, help="사람 · 무작위 · 필터")
    받기.add_argument("--시드", type=int, default=0)
    받기.add_argument("--최대턴", type=int, default=200)
    받기.add_argument("--판수", type=int, default=1, help="자가 대전 반복 횟수")
    받기.add_argument("--조용히", action="store_true", help="기보만 출력")
    받기.add_argument("--수", nargs="*", default=None, help="비대화 모드로 미리 줄 수 목록")
    받기.add_argument("--기보", default=None, help="기보를 저장할 파일 경로")
    인수 = 받기.parse_args()

    나역할 = 인수.나역할 or ("사람" if 인수.수 is None else "사람")
    상대역할 = 인수.상대역할 or "무작위"
    if 인수.나역할 in ("무작위", "필터"):
        나역할 = 인수.나역할

    합계 = {"나": 0, "상대": 0, "미정": 0}
    마지막기보 = None
    for 판 in range(인수.판수):
        끝, 기록 = 한판(
            인수.덱, 인수.상대, 나역할, 상대역할,
            시드=인수.시드 + 판, 최대턴=인수.최대턴,
            조용히=인수.조용히, 미리정한수=인수.수,
        )
        마지막기보 = 기록
        합계[끝.승자 if 끝 else "미정"] += 1
        if 인수.판수 == 1:
            print("\n".join(기록.줄))

    if 인수.판수 > 1:
        print(f"{인수.판수}판 — 나 {합계['나']}승 · 상대 {합계['상대']}승 · 미정 {합계['미정']}")

    if 인수.기보 and 마지막기보 is not None:
        Path(인수.기보).write_text("\n".join(마지막기보.줄), encoding="utf-8")
        print(f"기보 저장: {인수.기보}")
    return 0


if __name__ == "__main__":
    raise SystemExit(주문())
