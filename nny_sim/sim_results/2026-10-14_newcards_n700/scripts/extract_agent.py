"""에이전트 기록(jsonl)의 마지막 답변 텍스트에서 본문을 잘라 파일로 저장한다.
  python3 extract_agent.py <agent.jsonl> <출력.md> [시작 표지 정규식]
"""
import json, re, sys

src, out = sys.argv[1:3]
start = sys.argv[3] if len(sys.argv) > 3 else r'^(\*\*5줄 요약\*\*|### |## )'
last = None
for line in open(src, encoding='utf-8'):
    try: d = json.loads(line)
    except Exception: continue
    if d.get('type') != 'assistant': continue
    c = d.get('message', {}).get('content')
    if isinstance(c, list):
        t = '\n'.join(b.get('text', '') for b in c if b.get('type') == 'text').strip()
        if t: last = t
if not last: sys.exit('답변 없음')
m = re.search(start, last, re.M)
body = last[m.start():] if m else last
open(out, 'w', encoding='utf-8').write(body.rstrip() + '\n')
print(out, len(body.split('\n')), '줄', '(표지 찾음)' if m else '(표지 없음 — 전체 저장)')
