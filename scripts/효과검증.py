"""효과 데이터 점검 — 완성_기준_듀얼.md 2번의 확인 방법.

    python scripts/효과검증.py

두 덱(호박옥 · 던전마스터)의 카드 텍스트에 번호가 붙은 효과를 전부 세고, 그 하나하나가
`cards/효과/<덱>.yaml` 에 **구현** 또는 **미구현/미해결 사유**로 적혀 있는지 본다.
빈자리(사유를 적어 둔 것)는 정답이고, **아무 데도 안 적힌 효과**만 실패다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.effects import 효과_읽기, 효과오류

덱들 = ("호박옥", "던전마스터", "격투가", "세리")  # 103회차 — 2단계 둘째 덱을 더했다
_효과줄 = re.compile(r"^(\d+)\.\s")


def 카드효과_세기(카드풀: list[dict], 테마: str) -> dict[str, list[int]]:
    """카드 텍스트에서 `N. ` 로 시작하는 줄의 번호를 모은다."""
    모음: dict[str, list[int]] = {}
    for 카드 in 카드풀:
        if 카드.get("theme") != 테마:
            continue
        번호들 = [
            int(맞음.group(1))
            for 줄 in (카드.get("text") or "").split("\n")
            if (맞음 := _효과줄.match(줄.strip()))
        ]
        if 번호들:
            모음[카드["name"]] = 번호들
    return 모음


def 주문() -> int:
    뿌리 = Path(__file__).resolve().parent.parent
    카드풀 = json.loads((뿌리 / "data" / "card_pool.json").read_text(encoding="utf-8"))
    try:
        데이터 = 효과_읽기()
    except 효과오류 as 오류:
        print(f"효과 데이터 파싱 실패: {오류}")
        return 1
    print(f"효과 데이터 로드: 카드 {len(데이터)}종")

    안적힘: list[str] = []
    합계 = {"구현": 0, "빈자리": 0, "안적힘": 0}

    for 테마 in 덱들:
        효과표 = 카드효과_세기(카드풀, 테마)
        전체 = sum(len(번호들) for 번호들 in 효과표.values())
        구현 = 빈자리 = 0
        for 카드이름, 번호들 in sorted(효과표.items()):
            적힌것 = 데이터.get(카드이름, {})
            for 번호 in 번호들:
                항목 = 적힌것.get(번호)
                if 항목 is None:
                    안적힘.append(f"{테마} / {카드이름} {번호}번")
                elif "동작" in 항목:
                    구현 += 1
                else:
                    빈자리 += 1
        print(f"\n[{테마}] 카드 {len(효과표)}종 · 효과 {전체}개")
        print(f"  구현 {구현} · 사유 적힌 빈자리 {빈자리} · 안 적힘 {전체 - 구현 - 빈자리}")
        합계["구현"] += 구현
        합계["빈자리"] += 빈자리

    합계["안적힘"] = len(안적힘)
    print("\n" + "=" * 60)
    print(f"합계 — 구현 {합계['구현']} · 빈자리 {합계['빈자리']} · 안 적힘 {합계['안적힘']}")
    if 안적힘:
        print("\n아무 데도 안 적힌 효과 (이것만 실패다):")
        for 하나 in 안적힘:
            print(f"  - {하나}")
        return 1
    print("전체 결과: 통과 (모든 효과가 구현되었거나 사유와 함께 비워져 있다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(주문())
