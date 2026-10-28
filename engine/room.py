"""방 · 자리 — 사람 둘이 붙어 한 판을 두고, 남는 자리는 AI가 메운다.

`scripts/웹듀얼.py` 가 쓰는 서버 쪽 알맹이다. 규칙은 여기 없다 — 합법수는
`engine/legalmoves.py`, 적용은 `engine/turn.py`, 효과는 `engine/effects.py` 가 한다.

**엔진은 방마다 스레드 하나**에서 평소대로 돈다. 사람에게 물어야 할 자리에서 그 자리의
큐에 질문을 넣고 답이 올 때까지 멈춘다. 브라우저는 폴링으로 질문을 받아 그리고, 누르면
답을 큐에 넣는다. 엔진이 멈춰 있는 동안에만 보드를 뜨므로 상태를 둘이 같이 만지는 일이
없다 — 그래서 락이 따로 없다.

**인원 상한 5명**(사용자 지시 2026-10-27) — 한 방에 플레이어 2 + 관전 3, 서버 전체도 5다.
"""

from __future__ import annotations

import json
import queue
import random
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .deck import 공용태그, 대전_준비, 덱_골라만들기, 덱_만들기, 덱_점검
from .effects import 효과적용기
from .legalmoves import 합법수_생성
from .players import 무작위플레이어, 필터플레이어
from .predicates import 덱상수
from .state import 단계
from .static import 기본카드표
from .turn import (
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
from .view import 기보_효과문, 보드_딕, 수_갈래들, 수_효과문

맵파일 = {"호박옥": "호박옥_봉인의_계약.yaml", "던전마스터": "던전마스터_셔플.yaml"}
효과뿌리 = Path(__file__).resolve().parent.parent / "cards" / "효과"
추천덱파일 = Path(__file__).resolve().parent.parent / "cards" / "추천덱.json"
_추천덱캐시: list = []


def 추천덱들() -> dict:
    """`cards/추천덱.json` — 카드 효과를 전수로 읽고 짠 덱별 추천 구성.

    룰지 0-1·0-2 범위 안에 들어가는 것을 기계로 확인해 둔 것이고(테스트가 지킨다),
    고르는 쪽이 그대로 쓰거나 덱 편집기에서 손봐 쓸 수 있다.
    """
    if not _추천덱캐시:
        try:
            _추천덱캐시.append(json.loads(추천덱파일.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            _추천덱캐시.append({})
    return _추천덱캐시[0]


def 추천카드목록(테마: str) -> list[str]:
    """추천 구성을 `덱_골라만들기` 가 받는 이름 목록(매수만큼 반복)으로 편다."""
    하나 = 추천덱들().get(테마) or {}
    목록: list[str] = []
    for 이름, 수 in (하나.get("카드") or {}).items():
        목록 += [이름] * int(수)
    return 목록
단계순서 = (단계.진행, 단계.전투, 단계.정비)
최대인원_기본 = 5

# 맵 YAML 머리에 적힌 덱 상수와 같은 값.
덱상수표 = {
    "호박옥": 덱상수(세금=2, 카운터명="봉인", 벽유지최소=1, 테마="호박옥"),
    "던전마스터": 덱상수(세금=0, 카운터명="봉인", 벽유지최소=0, 테마="던전마스터"),
}
맵뿌리 = Path(__file__).resolve().parent.parent / "maps"


def 덱목록() -> list[dict]:
    """고를 수 있는 덱과 그 상태. **없는 것을 있다고 하지 않는다.**

    - `필터가능` — 1층 필터 AI 는 그 덱의 맵이 있어야 둔다(지금은 두 덱뿐).
      나머지 덱은 무작위 AI 와 사람만 맡을 수 있다.
    - `효과` — `cards/효과/<덱>.yaml` 이 있는 덱만 효과가 실제로 적용된다. 없는 덱은
      카드를 내고 전투까지는 되지만 효과는 「미구현」으로 기보에 남는다. 덱 전용 상수
      (세금·벽)도 선언된 두 덱 말고는 기본값(없음)이다 — **추측으로 채우지 않았다.**
    """
    표 = 기본카드표()
    테마들 = sorted({표[이름].theme for 이름 in 표.이름들()} - {공용태그})
    나온것 = []
    for 테마 in 테마들:
        덱 = 덱_만들기(테마, 표)
        나온것.append({
            "이름": 테마,
            "메인": len(덱.메인덱),
            "상급": len(덱.상급덱),
            "스킬": 덱.스킬,
            "필터가능": 테마 in 맵파일,
            "효과있음": (효과뿌리 / f"{테마}.yaml").exists(),
            "상수선언됨": 테마 in 덱상수표,
            "추천": (추천덱들().get(테마) or {}).get("설명"),
            "추천카드": 추천카드목록(테마),
        })
    return 나온것


def 카드목록() -> list[dict]:
    """카드 열람용 전수 목록. `data/card_pool.json` 그대로이고 고치지 않는다."""
    표 = 기본카드표()
    나온것 = []
    for 이름 in 표.이름들():
        정의 = 표[이름]
        몬 = bool(정의.몬스터인가)
        나온것.append({
            "이름": 이름, "덱": 정의.theme, "종류": 정의.type,
            "색": 정의.color, "레벨": 정의.level if 몬 else None,
            "공": 정의.atk if 몬 else None, "수": 정의.df if 몬 else None,
            "텍스트": 정의.text or "",
        })
    나온것.sort(key=lambda 하나: (하나["덱"], -(하나["레벨"] or 0), 하나["이름"]))
    return 나온것


class 사람자리:
    """엔진이 물으면 멈추고, 웹에서 답이 오면 깨어난다."""

    def __init__(self, 자리: str):
        self.자리 = 자리
        self.질문큐: queue.Queue = queue.Queue()
        self.답큐: queue.Queue = queue.Queue()
        self.지금질문: dict | None = None
        self.기권했나 = False
        self.보드만들기 = None          # 대국이 꽂아 준다

    def _묻기(self, 꾸러미: dict):
        꾸러미["보드"] = self.보드만들기()
        꾸러미["때"] = time.time()
        self.질문큐.put(꾸러미)
        return self.답큐.get()

    def 고르기(self, 질문: str, 후보: list[str]) -> str:
        if len(후보) == 1:
            return 후보[0]
        답 = self._묻기({"종류": "고르기", "질문": 질문, "후보": 후보})
        return 후보[답] if isinstance(답, int) and 0 <= 답 < len(후보) else 후보[0]

    def 수_고르기(self, 상태, 합법수: list[str], 누구: str):
        if not 합법수:
            return None
        답 = self._묻기({"종류": "수", "질문": 상태.단계.value + " 단계", "후보": 합법수})
        if 답 == "기권":
            self.기권했나 = True
            return None
        if 답 == "넘김" or 답 is None:
            return None
        return 합법수[답] if isinstance(답, int) and 0 <= 답 < len(합법수) else None

    # -- 웹 스레드 쪽 --------------------------------------------------
    def 꺼내기(self) -> dict | None:
        if self.지금질문 is None:
            try:
                self.지금질문 = self.질문큐.get_nowait()
            except queue.Empty:
                pass
        return self.지금질문

    def 답하기(self, 값) -> bool:
        if self.지금질문 is None:
            return False
        self.지금질문 = None
        self.답큐.put(값)
        return True


갈래들 = ("버그", "헷갈림", "제안", "그냥")
피드백뿌리 = Path(__file__).resolve().parent.parent / "피드백"


@dataclass
class 메모:
    """플레이 중에 그 자리에서 남긴 한 줄 — 어느 턴 · 어느 단계였는지를 함께 묶는다.

    사용자 요청(2026-10-28): 배포해서 피드백을 받는데, 진행하다 **단계별로** 메모를
    남길 수 있어야 한다. 나중에 읽는 쪽(나)이 "무슨 장면이었나"를 되짚을 수 있도록
    그 시점 기보 꼬리도 같이 얼려 둔다 — 메모만 있으면 맥락이 없다.
    """

    때: float
    별명: str
    자리: str | None
    턴: int
    단계: str
    갈래: str
    글: str
    기보꼬리: list[str] = field(default_factory=list)

    def 딕(self) -> dict:
        return {
            "때": self.때, "별명": self.별명, "자리": self.자리, "턴": self.턴,
            "단계": self.단계, "갈래": self.갈래, "글": self.글,
            "기보꼬리": self.기보꼬리,
        }


@dataclass
class 참가자:
    토큰: str
    별명: str
    자리: str | None       # "나" · "상대" · None(관전)
    마지막접속: float = field(default_factory=time.time)


class 대국:
    """한 판. 자리 둘 중 사람이 앉은 쪽은 `사람자리`, 빈 쪽은 AI가 맡는다.

    **AI끼리 두는 판은 박자를 맞춰 보여 준다**(사용자 요청 2026-10-28) — 그냥 두면
    한순간에 끝나 버려 구경할 수가 없다. 수를 두기 전에 `박자()` 에서 멈춤·배속을 본다.
    사람 자리는 어차피 사람을 기다리므로 박자를 넣지 않는다.
    """

    기본간격 = 0.8          # 1배속에서 한 수 사이

    def __init__(self, 내덱: str, 상대덱: str, 역할: dict[str, str], 시드: int,
                 고른카드: dict[str, list[str]] | None = None):
        self.표 = 기본카드표()
        self.적용기 = 효과적용기(표=self.표)
        고른카드 = 고른카드 or {}
        self.고른카드 = {자리: list(고른카드.get(자리) or []) for 자리 in ("나", "상대")}
        self.상태, self.난수 = 대전_준비(
            내덱, 상대덱, 시드, self.표,
            나_카드=self.고른카드["나"] or None,
            상대_카드=self.고른카드["상대"] or None,
        )
        self.기록 = 기보()
        self.덱 = {"나": 내덱, "상대": 상대덱}
        # 선언 안 된 덱은 기본값(세금 0 · 벽 0) — "그 덱 전용 규칙을 아직 안 적었다"는
        # 뜻이고, 추측으로 채우지 않는다. 그런 덱은 효과도 대부분 미구현이다.
        self.상수표 = {"나": 덱상수표.get(내덱, 덱상수()),
                       "상대": 덱상수표.get(상대덱, 덱상수())}
        self.사람자리들: dict[str, 사람자리] = {}
        self.역할: dict[str, object] = {}
        for 자리 in ("나", "상대"):
            종류 = 역할[자리]
            if 종류 == "사람":
                한자리 = 사람자리(자리)
                한자리.보드만들기 = (lambda 쪽=자리: 보드_딕(self.상태, self.표, 쪽))
                self.사람자리들[자리] = 한자리
                self.역할[자리] = 한자리
            elif 종류 == "필터" and self.덱[자리] in 맵파일:
                self.역할[자리] = 필터플레이어(자리, self.난수, 맵뿌리 / 맵파일[self.덱[자리]])
            elif 종류 == "필터":
                # 맵이 없는 덱은 1층 필터가 둘 수 없다 — 조용히 무작위로 떨어진다.
                self.역할[자리] = 무작위플레이어(자리, self.난수)
            else:
                self.역할[자리] = 무작위플레이어(자리, self.난수)
        self.끝: 종료 | None = None
        self.배속 = 1.0                       # 0 이하면 기다리지 않는다(최대 속도)
        self.계속 = threading.Event()
        self.계속.set()
        self.걸음 = 0                          # 멈춘 채로 보내 줄 「한 걸음」 횟수
        self.걸음기준 = 0                      # 그 걸음을 시작할 때의 기보 줄 수
        self.걸음남은 = 0                      # 기보가 안 늘어도 더 볼 자리 수(헛도는 것 방지)
        self.걸음상한 = 24
        self.기록.적기(
            f"{내덱}(나) vs {상대덱}(상대) · 시드 {시드} · 선공 {self.상태.선공}"
        )
        threading.Thread(target=self._돌리기, daemon=True).start()

    def 박자(self, 사람인가: bool) -> None:
        """AI가 둘 차례면 멈춤·배속을 여기서 본다. 사람 차례면 그냥 지나간다.

        「한 걸음」은 **기보가 실제로 한 줄 늘 때까지** 보내 준다(사용자 보고
        2026-10-28). 전에는 "수를 고르는 자리" 하나만 통과시켜서, 둘 수가 없어 단계만
        넘어가는 자리에 걸리면 눌러도 화면이 그대로라 고장처럼 보였다. 판이 멈춰 있을
        때를 대비해 `걸음상한` 번까지만 보고 포기한다.
        """
        if 사람인가:
            return
        while not self.계속.is_set():
            if self.걸음 > 0:
                if len(self.기록.줄) > self.걸음기준 or self.걸음남은 <= 0:
                    self.걸음 -= 1             # 눈에 보이는 변화가 생겼다(또는 포기)
                else:
                    self.걸음남은 -= 1
                return
            if self.끝 is not None:
                return
            time.sleep(0.08)
        if self.배속 > 0:
            time.sleep(self.기본간격 / self.배속)

    def 진행조절(self, 배속=None, 멈춤=None, 한걸음: bool = False) -> dict:
        if 배속 is not None:
            try:
                self.배속 = max(0.0, min(64.0, float(배속)))
            except (TypeError, ValueError):
                pass
        if 멈춤 is not None:
            self.계속.clear() if 멈춤 else self.계속.set()
        if 한걸음:
            self.계속.clear()
            self.걸음 += 1
            self.걸음기준 = len(self.기록.줄)
            self.걸음남은 = self.걸음상한
        return {"배속": self.배속, "멈춤": not self.계속.is_set()}

    def _돌리기(self) -> None:
        """판을 끝까지 돌린다. **무슨 일이 있어도 조용히 죽지 않는다.**

        2026-10-28 — 전에는 못 보던 예외가 나면 스레드가 그대로 끝나 버려서, 보는
        쪽에는 「상대가 두는 중…」이 영원히 떠 있었다. 테스터가 그걸 보고할 방법도
        없다. 이제 잡아서 기보에 적고 판을 끝낸다 — 메모에 그 줄이 같이 실려 온다.
        """
        try:
            self._판돌리기()
        except Exception as 오류:                      # noqa: BLE001 — 마지막 그물
            import traceback
            self.기록.적기(f"  !! 엔진이 멈췄다({type(오류).__name__}): {오류}")
            for 줄 in traceback.format_exc().strip().split("\n")[-4:]:
                self.기록.적기("     " + 줄)
            self.기록.적기("  — 이 판은 여기서 끝난다. 메모를 남겨 주면 그대로 전달된다.")
            if self.끝 is None:
                self.끝 = 종료(승자="없음", 조건="오류",
                               근거=f"엔진 오류 — {type(오류).__name__}: {오류}")

    def _판돌리기(self) -> None:
        상태, 표, 기록 = self.상태, self.표, self.기록
        while self.끝 is None and 상태.턴번호 <= 200:
            누구 = 상태.턴플레이어
            나역 = self.역할[누구]
            기록.적기(f"[턴 {상태.턴번호} · {누구}]")
            self.끝 = 준비단계(상태, 누구, 나역.고르기, 기록)
            if self.끝 is not None:
                break
            for 이번단계 in 단계순서:
                상태.단계 = 이번단계
                while True:
                    상태.가용수단 = 합법수_생성(상태, 표, 누구, self.상수표[누구])
                    합법수 = sorted(상태.가용수단)
                    self.박자(누구 in self.사람자리들)
                    고른수 = 나역.수_고르기(상태, 합법수, 누구)
                    if getattr(나역, "기권했나", False):
                        반대 = "상대" if 누구 == "나" else "나"
                        self.끝 = 종료(승자=반대, 조건="기권", 근거="플레이어가 기권했다")
                        break
                    if 고른수 is None:
                        break
                    try:
                        수_적용(
                            상태, 고른수, 누구=누구, 표=표, 상수=self.상수표[누구],
                            고르기=나역.고르기, 기록=기록, 효과적용=self.적용기,
                        )
                        강제트리거_처리(
                            상태, 표, self.상수표, self.적용기, 나역.고르기, 기록
                        )
                        반응형트리거_기회(
                            상태, 표, self.상수표, self.역할, self.적용기, 기록
                        )
                    except 적용오류 as 오류:
                        기록.적기(f"  !! 적용 실패({고른수}): {오류}")
                        break
                    self.끝 = 승패_확인(상태)
                    if self.끝 is not None:
                        break
                if self.끝 is not None:
                    break
            if self.끝 is not None:
                break
            종료단계(
                상태, 누구, 기록,
                표=표, 상수표=self.상수표, 효과적용=self.적용기, 고르기=나역.고르기,
            )
            self.끝 = 승패_확인(상태)
        if self.끝 is None:
            기록.적기("— 200턴 상한에 걸려 중단")
        else:
            기록.적기(f"— 종료: {self.끝.승자} 승 ({self.끝.조건}) · {self.끝.근거}")


class 방:
    def __init__(self, 이름: str, 내덱: str, 상대덱: str, 역할: dict[str, str],
                 시드: int, 최대인원: int = 최대인원_기본,
                 고른카드: dict[str, list[str]] | None = None):
        self.이름 = 이름
        self.최대인원 = 최대인원
        self.참가자들: dict[str, 참가자] = {}
        self.만든때 = time.time()
        self.대국 = 대국(내덱, 상대덱, 역할, 시드, 고른카드)
        self.역할설정 = 역할
        self.메모들: list[메모] = []
        self.판정: dict[int, dict] = {}    # 메모 번호 → 루틴이 내린 건별 판정
        self.메모저장할까 = True            # 시험에서는 끈다(리포에 파일을 안 남기려고)

    # -- 자리 --------------------------------------------------------
    def 빈자리(self) -> str | None:
        찬자리 = {하나.자리 for 하나 in self.참가자들.values() if 하나.자리}
        for 자리 in ("나", "상대"):
            if self.역할설정[자리] == "사람" and 자리 not in 찬자리:
                return 자리
        return None

    def 덱점검(self) -> dict[str, list[str]]:
        """지금 쓰는 두 덱이 룰지 0-1·0-2 매수 범위에 맞는지. 막지 않고 알리기만 한다."""
        나온것 = {}
        for 자리 in ("나", "상대"):
            고른 = self.대국.고른카드.get(자리) or None
            테마 = self.대국.덱[자리]
            덱 = (덱_골라만들기(테마, 고른, self.대국.표) if 고른
                  else 덱_만들기(테마, self.대국.표))
            나온것[자리] = 덱_점검(덱)
        return 나온것

    def 방장토큰(self) -> str | None:
        """방을 만든 사람. 나가면 그 다음으로 들어온 사람이 이어받는다."""
        return next(iter(self.참가자들), None)

    def 다시하기(self, 토큰: str, 내덱=None, 상대덱=None, 역할=None,
                 고른카드=None) -> bool:
        """같은 방에서 새 판. **방장만** 누를 수 있고, 메모와 판정은 그대로 둔다.

        덱·역할을 안 주면 하던 그대로 다시 한다. 자리는 다시 배정한다 — 사람 자리가
        늘거나 줄 수 있기 때문이다.
        """
        if 토큰 != self.방장토큰():
            return False
        새역할 = dict(self.역할설정)
        if 역할:
            for 자리 in ("나", "상대"):
                if 역할.get(자리):
                    새역할[자리] = 역할[자리]
        self.역할설정 = 새역할
        self.대국 = 대국(내덱 or self.대국.덱["나"], 상대덱 or self.대국.덱["상대"],
                         새역할, random.randrange(1 << 20),
                         고른카드 if 고른카드 is not None else self.대국.고른카드)
        찬자리: set[str] = set()
        for 하나 in self.참가자들.values():
            하나.자리 = None
            for 자리 in ("나", "상대"):
                if 새역할[자리] == "사람" and 자리 not in 찬자리:
                    하나.자리 = 자리
                    찬자리.add(자리)
                    break
        return True

    def 들이기(self, 별명: str) -> 참가자:
        if len(self.참가자들) >= self.최대인원:
            raise ValueError(f"{self.이름} 방은 {self.최대인원}명이 꽉 찼다")
        하나 = 참가자(토큰=secrets.token_urlsafe(9), 별명=별명 or "손님", 자리=self.빈자리())
        self.참가자들[하나.토큰] = 하나
        return 하나

    def 내보내기(self, 토큰: str) -> None:
        self.참가자들.pop(토큰, None)

    # -- 메모(피드백) --------------------------------------------------
    def 메모남기기(self, 토큰: str, 글: str, 갈래: str = "그냥") -> 메모 | None:
        """플레이 중에 남긴 메모 하나. 어느 턴·어느 단계였는지는 **서버가 적는다**.

        화면이 보내 준 맥락을 믿지 않는다 — 사람이 적는 것은 글과 갈래뿐이다.
        """
        사람 = self.참가자들.get(토큰)
        if 사람 is None:
            return None
        글 = (글 or "").strip()
        if not 글:
            return None
        하나 = 메모(
            때=time.time(),
            별명=사람.별명,
            자리=사람.자리,
            턴=self.대국.상태.턴번호,
            단계=self.대국.상태.단계.value,
            갈래=갈래 if 갈래 in 갈래들 else "그냥",
            글=글[:2000],
            기보꼬리=list(self.대국.기록.줄[-6:]),
        )
        self.메모들.append(하나)
        self.메모_저장()
        return 하나

    def 메모_마크다운(self) -> str:
        """사람이 읽는 꼴. 이슈 본문·내려받기 파일이 이걸 쓴다."""
        덱 = self.대국.덱
        줄 = [
            f"# 플레이 메모 — 방 {self.이름}",
            "",
            f"- 덱: {덱['나']}(나) vs {덱['상대']}(상대)",
            f"- 자리: " + ", ".join(
                f"{하나.별명}({하나.자리 or '관전'})" for 하나 in self.참가자들.values()
            ),
            f"- 시작: {time.strftime('%Y-%m-%d %H:%M', time.localtime(self.만든때))}",
            f"- 메모 {len(self.메모들)}개",
            "",
            "처리: " + ("미처리" if self.안본메모들() else "처리됨"),
            "",
        ]
        for 번, 하나 in enumerate(self.메모들, 1):
            줄 += [
                f"## {번}. [{하나.갈래}] 턴 {하나.턴} · {하나.단계} 단계 — {하나.별명}",
                "",
                하나.글,
                "",
            ]
            if 하나.기보꼬리:
                줄 += ["<details><summary>그때 기보</summary>", "", "```"]
                줄 += [꼬리.rstrip() for 꼬리 in 하나.기보꼬리]
                줄 += ["```", "", "</details>", ""]
        return "\n".join(줄)

    def 메모파일이름(self) -> str:
        return time.strftime("%Y-%m-%d", time.localtime(self.만든때)) + "_" + self.이름

    def 판정받기(self, 꾸러미: dict) -> None:
        """루틴이 깃허브에 써 둔 건별 판정을 받아 둔다(서버가 주기적으로 읽어 넣는다).

        판정 꼴은 `피드백/README.md` 가 정본 — `{"메모": 1, "상태": "고침"|"안함"|"보류",
        "한일"/"까닭": "...", "커밋": "abc1234"}`. 모르는 상태는 버린다(화면은 대기로 둔다).
        """
        새것: dict[int, dict] = {}
        for 하나 in (꾸러미 or {}).get("판정", []):
            try:
                번 = int(하나.get("메모"))
            except (TypeError, ValueError):
                continue
            상태 = 하나.get("상태")
            if 상태 not in ("고침", "안함", "보류"):
                continue
            새것[번] = {
                "상태": 상태,
                "말": (하나.get("한일") or 하나.get("까닭") or "").strip()[:400],
                "커밋": (하나.get("커밋") or "")[:12],
            }
        self.판정 = 새것

    def 안본메모들(self) -> list[int]:
        """아직 판정이 안 달린 메모 번호들 — 루틴이 집어갈 몫."""
        return [번 for 번 in range(1, len(self.메모들) + 1) if 번 not in self.판정]

    def 메모_꾸러미(self) -> dict:
        """기계가 읽는 꼴. 루틴이 이걸 보고 무엇이 남았는지 센다.

        **루틴이 써 둔 판정을 덮지 않는다** — 서버는 `판정따라가기()` 로 깃허브에서
        읽어 둔 것을 그대로 다시 적고, 판정이 안 달린 메모가 하나라도 있으면
        `처리` 를 「미처리」로 되돌린다(새 메모가 들어왔다는 뜻이니 맞다).
        """
        판정목록 = [
            dict(self.판정[번], 메모=번) for 번 in sorted(self.판정)
            if 번 <= len(self.메모들)
        ]
        return {
            "방": self.이름,
            "덱": self.대국.덱,
            "시작": self.만든때,
            "처리": "미처리" if self.안본메모들() else "처리됨",
            "메모들": [
                dict(하나.딕(), 번호=번) for 번, 하나 in enumerate(self.메모들, 1)
            ],
            "판정": 판정목록,
        }

    def 메모_저장(self) -> None:
        """`피드백/` 에 사람용 .md 와 기계용 .json 을 같이 떨군다.

        서버를 돌리는 쪽 디스크에 남는다 — 사용자 PC 에서 돌리면 그대로 리포 안에
        쌓이고, 테스터가 자기 PC 에서 돌리면 화면의 「내려받기」로 보내 주면 된다.
        """
        if not self.메모저장할까:
            return
        try:
            피드백뿌리.mkdir(exist_ok=True)
            이름 = time.strftime("%Y-%m-%d", time.localtime(self.만든때)) + "_" + self.이름
            (피드백뿌리 / (이름 + ".md")).write_text(self.메모_마크다운(), encoding="utf-8")
            (피드백뿌리 / (이름 + ".json")).write_text(
                json.dumps(self.메모_꾸러미(), ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except OSError:
            pass   # 메모를 못 적는다고 판이 멈추면 안 된다

    # -- 화면 --------------------------------------------------------
    def 상태딕(self, 토큰: str) -> dict:
        사람 = self.참가자들.get(토큰)
        if 사람 is None:
            raise KeyError("모르는 토큰이다 — 다시 참가해라")
        사람.마지막접속 = time.time()
        자리 = 사람.자리
        끝 = self.대국.끝
        질문 = None
        if 끝 is None and 자리 is not None:
            질문 = self.대국.사람자리들[자리].꺼내기()
        if 질문 and 질문.get("종류") == "수" and "효과문" not in 질문:
            # 사용자 요청(2026-10-28) — "발동(…)" 선택지만 보고는 무슨 효과인지 알 수 없다.
            # 카드 문면을 버튼에 같이 보낸다. 규칙은 안 건드린다 — 보여 주기만.
            질문["효과문"] = [수_효과문(하나, self.대국.표) for 하나 in 질문["후보"]]
            # 같은 요청의 둘째 갈래 — 화면이 수를 판 위 카드·존에 묶을 수 있게 쪼개 준다
            # (끌어다 놓기 · 카드 눌러 효과 고르기). 색인이 그대로 답할 번호다.
            질문["갈래"] = 수_갈래들(질문["후보"], self.대국.표)
        보드 = (질문 or {}).get("보드") or 보드_딕(self.대국.상태, self.대국.표, 자리)
        기다리는자리 = [
            자리이름 for 자리이름, 한자리 in self.대국.사람자리들.items()
            if 한자리.꺼내기() is not None
        ]
        return {
            "방": self.이름,
            "나의자리": 자리,
            "별명": 사람.별명,
            "덱": self.대국.덱,
            "보드": 보드,
            "질문": 질문,
            # 화면용 사본 — 「…N번 발동」 줄 아래에 그 효과 문면을 끼운다(원본 기보는 그대로).
            "기보": 기보_효과문(self.대국.기록.줄, self.대국.표),
            "끝": (
                {"승자": 끝.승자, "조건": 끝.조건, "근거": 끝.근거} if 끝 else None
            ),
            "사람들": [
                {"별명": 하나.별명, "자리": 하나.자리} for 하나 in self.참가자들.values()
            ],
            "정원": self.최대인원,
            "방장인가": 토큰 == self.방장토큰(),
            "덱점검": self.덱점검(),
            "역할설정": dict(self.역할설정),
            "기다리는자리": 기다리는자리,
            "메모들": [
                dict(하나.딕(), 번호=번, 판정=self.판정.get(번))
                for 번, 하나 in enumerate(self.메모들, 1)
            ],
            "진행": {
                "배속": self.대국.배속,
                "멈춤": not self.대국.계속.is_set(),
                "AI끼리": not self.대국.사람자리들,
            },
        }

    def 답하기(self, 토큰: str, 값) -> bool:
        사람 = self.참가자들.get(토큰)
        if 사람 is None or 사람.자리 is None:
            return False
        return self.대국.사람자리들[사람.자리].답하기(값)


class 방장부:
    """서버 전체의 방 목록과 인원 상한."""

    def __init__(self, 최대인원: int = 최대인원_기본):
        self.최대인원 = 최대인원
        self.방들: dict[str, 방] = {}
        self.자물쇠 = threading.Lock()

    버림시간 = 600.0      # 10분 동안 화면이 한 번도 안 물어보면 나간 것으로 본다

    def 총인원(self) -> int:
        return sum(len(하나.참가자들) for 하나 in self.방들.values())

    def 청소(self) -> None:
        """오래 조용한 참가자와 빈 방을 지운다.

        2026-10-28 — 전에는 방을 떠나도 참가자가 남아서, 혼자 노는 사람이 방을 다섯 번
        만들면 「서버 정원 5명이 꽉 찼다」로 잠겼다. 화면이 0.9초마다 묻고 그때마다
        `마지막접속` 이 갱신되므로, 한참 조용한 쪽은 떠난 것으로 본다.
        """
        지금 = time.time()
        with self.자물쇠:
            for 이름, 하나 in list(self.방들.items()):
                for 토큰, 사람 in list(하나.참가자들.items()):
                    if 지금 - 사람.마지막접속 > self.버림시간:
                        하나.참가자들.pop(토큰, None)
                if not 하나.참가자들 and 지금 - 하나.만든때 > 60:
                    self.방들.pop(이름, None)

    def 나가기(self, 방이름: str, 토큰: str) -> bool:
        """화면이 「메인으로」 를 누르면 부른다. 아무도 안 남으면 방을 지운다."""
        with self.자물쇠:
            하나 = self.방들.get(방이름)
            if 하나 is None:
                return False
            하나.내보내기(토큰)
            if not 하나.참가자들:
                self.방들.pop(방이름, None)
            return True

    def 만들기(self, 별명: str, 내덱: str, 상대덱: str, 역할: dict[str, str],
               시드: int | None = None,
               고른카드: dict[str, list[str]] | None = None) -> tuple[방, 참가자]:
        self.청소()
        with self.자물쇠:
            if self.총인원() >= self.최대인원:
                raise ValueError(
                    f"서버 정원 {self.최대인원}명이 꽉 찼다 — 쓰지 않는 방은 잠시 뒤 저절로 치워진다"
                )
            이름 = secrets.token_hex(3)
            하나 = 방(이름, 내덱, 상대덱, 역할,
                     시드 if 시드 is not None else random.randrange(10 ** 6),
                     self.최대인원, 고른카드)
            self.방들[이름] = 하나
            return 하나, 하나.들이기(별명)

    def 참가(self, 방이름: str, 별명: str) -> tuple[방, 참가자]:
        with self.자물쇠:
            하나 = self.방들.get(방이름)
            if 하나 is None:
                raise KeyError("그런 방이 없다")
            if self.총인원() >= self.최대인원:
                raise ValueError(f"서버 정원 {self.최대인원}명이 꽉 찼다")
            return 하나, 하나.들이기(별명)

    def 목록(self) -> list[dict]:
        return [
            {
                "방": 하나.이름,
                "덱": 하나.대국.덱,
                "사람수": len(하나.참가자들),
                "정원": 하나.최대인원,
                "빈자리": 하나.빈자리(),
                "끝남": 하나.대국.끝 is not None,
            }
            for 하나 in self.방들.values()
        ]
