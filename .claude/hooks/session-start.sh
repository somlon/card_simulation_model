#!/bin/bash
# 세션 시작 시 규정 브랜치(기본: default)의 최신 CLAUDE.md · workflow.md를 GitHub에서 읽어
# 세션 컨텍스트로 출력한다. 규정 브랜치를 바꾸려면 아래 RULES_BRANCH 값만 수정한다.
# 세션 압축(source=compact) 뒤에 다시 불리면 CLAUDE.md R5의 인계 절차 알림을 먼저 출력한다.
set -uo pipefail

RULES_BRANCH="${RULES_BRANCH:-default}"
HOOK_SOURCE="$(python3 -c 'import sys, json; print(json.load(sys.stdin).get("source", ""))' 2>/dev/null || true)"
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

if [ "$HOOK_SOURCE" = "compact" ]; then
  echo "=== [세션 압축됨] CLAUDE.md R5 인계 절차를 지금 실행한다 ==="
  echo "① 그동안의 작업을 모두 작업 브랜치에 커밋 · 푸시 ② origin/default 의 workflow.md 「진행 중」 첫 항목 갱신"
  echo "③ 같은 클라우드 환경 · 같은 권한 모드로 새 세션을 만들어 workflow.md 진행 중 첫 항목을 이어서 하고 같은 매시 루틴을 만들라고 지시"
  echo "④ 새 세션이 루틴을 만든 것을 확인하면 이 세션의 옛 루틴을 끈다(update_trigger enabled=false)"
  echo "⑤ 채팅창에 보내는 출력의 마지막에 새 세션(제목 · ID · 이어서 할 일)을 열었다고 보고한다 (R7)"
  echo
fi

if ! git fetch -q origin "$RULES_BRANCH" 2>/dev/null; then
  echo "[규정] origin/$RULES_BRANCH 를 가져오지 못했다 — 로컬 CLAUDE.md 규정을 따르고, 사용자에게 알린다."
  exit 0
fi

echo "=== [규정] origin/$RULES_BRANCH:CLAUDE.md (최신 규정 — 로컬 사본보다 우선) ==="
git show "origin/$RULES_BRANCH:CLAUDE.md" 2>/dev/null || echo "(CLAUDE.md 없음)"
echo
echo "=== [진척] origin/$RULES_BRANCH:workflow.md (작업 전에 반드시 확인) ==="
git show "origin/$RULES_BRANCH:workflow.md" 2>/dev/null || echo "(workflow.md 없음 — 사용자에게 알린다)"
echo
echo "=== [현재] 체크아웃된 브랜치: $(git branch --show-current 2>/dev/null || echo '?') ==="
exit 0
