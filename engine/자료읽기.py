"""YAML 자료를 읽는 한 곳 — pyyaml 이 없는 PC 에서도 돌게 한다.

**왜 있는가** — 2026-10-28 배포본을 받은 테스터 PC 에서 `pip install pyyaml` 이 실패해
프로그램이 아예 안 떴다. 새 파이썬(3.13·3.14)에 그 버전용 휠이 아직 없으면 pip 가 소스
빌드로 넘어가고, 컴파일러가 없는 보통 PC 에서는 거기서 끝난다. pip 자체가 없는 설치본도
있다. **남의 PC 에서 도는 프로그램이 설치에 기대면 안 된다.**

그래서 규칙 자료(YAML)마다 **같은 내용의 `.json` 사본**을 리포에 같이 둔다. pyyaml 이
있으면 YAML 을 읽고(정본은 언제나 YAML), 없으면 사본을 읽는다. 둘이 어긋나면
`tests/test_duel.py` 가 잡는다 — 사람이 YAML 만 고치고 사본을 잊는 사고를 막는다.

사본 다시 만들기: `python scripts/자료사본만들기.py`
"""

from __future__ import annotations

import json
from pathlib import Path

try:                                    # pyyaml 이 있으면 그걸 쓴다(정본)
    import yaml as _yaml
except ImportError:                     # 없으면 사본으로 간다
    _yaml = None

yaml있나 = _yaml is not None


def 사본경로(경로: Path) -> Path:
    return 경로.with_suffix(".json")


def 읽기(경로: Path):
    """YAML 한 장을 읽어 파이썬 값으로. 비어 있으면 `{}`."""
    경로 = Path(경로)
    if _yaml is not None:
        return _yaml.safe_load(경로.read_text(encoding="utf-8")) or {}
    사본 = 사본경로(경로)
    if 사본.exists():
        return _숫자키되돌리기(json.loads(사본.read_text(encoding="utf-8")) or {})
    raise RuntimeError(
        f"{경로.name} 을(를) 읽을 수 없다 — pyyaml 이 없고 사본({사본.name})도 없다. "
        "`pip install pyyaml` 하거나 `python scripts/자료사본만들기.py` 로 사본을 만들어라."
    )


def _숫자키되돌리기(값):
    """JSON 은 사전 키를 전부 문자열로 만든다 — 숫자였던 키를 되돌린다.

    효과 번호(`1:` · `2:` …)가 YAML 에서는 정수라 그대로 두면 로더가 "효과 번호는
    정수라야 한다"로 거부한다. 이 자료에서 숫자로만 된 키는 효과 번호뿐이고(나머지는
    전부 한글 낱말) `사본검증()` 이 YAML 원본과 같은지 매번 확인한다.
    """
    if isinstance(값, dict):
        나온것 = {}
        for 키, 속 in 값.items():
            if isinstance(키, str) and 키.lstrip("-").isdigit():
                키 = int(키)
            나온것[키] = _숫자키되돌리기(속)
        return 나온것
    if isinstance(값, list):
        return [_숫자키되돌리기(하나) for 하나 in 값]
    return 값


def 사본검증(경로: Path) -> bool:
    """사본이 YAML 원본과 **똑같은 값**인지. pyyaml 이 있어야 한다(시험용)."""
    if _yaml is None:
        raise RuntimeError("검증하려면 pyyaml 이 필요하다")
    원본 = _yaml.safe_load(Path(경로).read_text(encoding="utf-8")) or {}
    사본 = 사본경로(Path(경로))
    if not 사본.exists():
        return False
    return _숫자키되돌리기(json.loads(사본.read_text(encoding="utf-8")) or {}) == 원본


def 사본쓰기(경로: Path) -> Path:
    """그 YAML 의 `.json` 사본을 다시 만든다. pyyaml 이 있어야 한다."""
    if _yaml is None:
        raise RuntimeError("사본을 만들려면 pyyaml 이 필요하다 — 개발자 PC 에서만 한다.")
    경로 = Path(경로)
    값 = _yaml.safe_load(경로.read_text(encoding="utf-8")) or {}
    낸곳 = 사본경로(경로)
    낸곳.write_text(
        json.dumps(값, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 낸곳


def 자료파일들(뿌리: Path | None = None) -> list[Path]:
    """사본을 둬야 하는 YAML 전부 — `cards/` 와 `maps/` 밑."""
    뿌리 = Path(뿌리 or Path(__file__).resolve().parent.parent)
    나온것: list[Path] = []
    for 갈래 in ("cards", "maps"):
        나온것 += sorted((뿌리 / 갈래).rglob("*.yaml"))
    return 나온것
