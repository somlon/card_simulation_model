#!/bin/bash
# 세션 시작 시 규정 브랜치(기본: default)의 최신 CLAUDE.md · workflow.md를 GitHub에서 읽어
# 세션 컨텍스트로 출력한다. 규정 브랜치를 바꾸려면 아래 RULES_BRANCH 값만 수정한다.
set -uo pipefail

RULES_BRANCH="${RULES_BRANCH:-default}"
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

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
