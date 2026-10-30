"""매트 v2(사용자 지시 2026-10-30): 몬스터 존 3칸(열 1 · 3 · 5, 이름 1 · 2 · 3) · 공유 존 2칸(가운데 줄 열 2 · 4) · 스킬 존(가운데 줄 열 1 = P2 · 5 = P1) · 필드 존(가운데).
원본 매트(사용자 업로드 field_mat.png)의 칸 그림을 그대로 옮겨 만든다(글꼴: 우분투 fonts-nanum).
  python3 make_mat_v2.py assets/src/field_mat.png assets/src/field_mat_v2.png — sheets.json 의 mat 이 이 파일"""
import sys
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1:3]
im = Image.open(src).convert('RGB'); W, H = im.size
X0, DX, Y0, DY, TW, TH, PAD = 160, 224, 318, 304, 200, 280, 3
def box(c, r, pad=PAD):
    cx, cy = X0 + DX * c, Y0 + DY * r
    return (cx - TW // 2 - pad, cy - TH // 2 - pad, cx + TW // 2 + pad, cy + TH // 2 + pad)
tile = lambda c, r: im.crop(box(c, r))
T = {k: tile(*v) for k, v in {'p1m2': (2, 3), 'p1m3': (3, 3), 'p2m2': (4, 1), 'p2m3': (3, 1), 'field': (0, 2), 'shared': (3, 2),
                                'p2sk': (2, 2), 'p1sk': (4, 2)}.items()}
orig = im.copy(); bg_at = lambda x, y: orig.getpixel((x, y))
d = ImageDraw.Draw(im)
# 몬스터 줄: 2 · 4열 칸을 지우고(판 배경), 3 · 5열(P1) · 3 · 1열(P2)에 2 · 3번 칸
for r in (1, 3):
    panel = bg_at(X0 + DX * 1 + DX // 2, Y0 + DY * r)   # 칸 사이 판 배경
    for c in (2, 4): d.rectangle(box(c, r, 6), fill=panel)
im.paste(T['p1m2'], box(3, 3)[:2]); im.paste(T['p1m3'], box(5, 3)[:2])
im.paste(T['p2m2'], box(3, 1)[:2]); im.paste(T['p2m3'], box(1, 1)[:2])
# 가운데 줄: 비우고 다시 놓는다
page = bg_at(X0 + DX * 1, Y0 + DY * 2 - 120)   # 원본 가운데 줄의 빈 곳(열 1)
d.rectangle((box(0, 2, 8)[0], box(0, 2, 8)[1], 1398, box(5, 2, 8)[3]), fill=page)   # 연결선 끝(주인 토큰 원 앞)까지
im.paste(T['p2sk'], box(1, 2)[:2]); im.paste(T['p1sk'], box(5, 2)[:2]); im.paste(T['field'], box(3, 2)[:2])
F = '/usr/share/fonts/truetype/nanum/NanumSquareB.ttf'
big = ImageFont.truetype(F, 30); small = ImageFont.truetype('/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf', 15)
for k, c in enumerate((2, 4)):
    im.paste(T['shared'], box(c, 2)[:2])
    cx, cy = X0 + DX * c, Y0 + DY * 2
    fill = im.getpixel((cx, cy + 70)); title = max((im.getpixel((x, y)) for x in range(cx - 60, cx + 60) for y in range(cy - 25, cy)), key=sum)
    d.rectangle((cx - 85, cy - 40, cx + 85, cy + 30), fill=fill)
    d.text((cx, cy - 8), f'공유 존 {k + 1}', font=big, fill=title, anchor='mm')
    d.text((cx, cy + 20), 'SHARED MONSTER', font=small, fill=tuple(int(v * 0.75 + f * 0.25) for v, f in zip(title, fill)), anchor='mm')
# 아래 설명 줄
fy = 1817; foot = im.getpixel((900, fy)); col = max((im.getpixel((x, fy)) for x in range(1200, 1600)), key=sum)
d.rectangle((1150, fy - 14, W - 40, fy + 14), fill=im.getpixel((1100, fy)))
d.text((W - 66, fy), 'HP 5000  •  MONSTER 3  •  SHARED 2  •  SPELL 5  •  FIELD 1 (SHARED)', font=ImageFont.truetype('/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf', 15), fill=col, anchor='rm')
im.save(out); print(out, im.size)
