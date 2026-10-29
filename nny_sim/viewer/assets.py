"""재생 화면용 이미지 준비 — 사용자 업로드 원본(assets/src)을 잘라 data URI로 만든다.

- 카드 시트: sheets.json 의 격자(가로 · 세로 칸 수)와 칸 순서의 카드 이름대로 잘라 카드 이름별 앞면 이미지로.
  (시트에 적힌 코드는 풀 코드와 다른 테마가 있어 이름으로 잇는다 — sheets.json 설명)
- 카드 뒷면: 앞면과 같은 가로세로비로 맞춘다. 늘이거나 줄이지 않고, 테두리 안쪽 무늬의 좌우 여백을 같은 폭만큼 걷어 낸다.
- 필드 매트: 그대로(webp로 줄임).
"""
import base64, io, json, os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'assets', 'src')
CARD_W = 240          # 앞면 이미지 가로(px) — 상세 보기(화면 150px)의 1.6배. 원본이 더 작으면 원본 크기
QUALITY = 82          # webp 품질
FRAME = 40            # 뒷면 테두리 띠 폭(px, 원본 기준) — 이 띠는 그대로 두고 안쪽만 걷어 낸다


def _uri(im, quality=QUALITY):
    buf = io.BytesIO(); im.save(buf, 'WEBP', quality=quality, method=6)
    return 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode()


def manifest():
    with open(os.path.join(SRC, 'sheets.json'), encoding='utf-8') as f:
        return json.load(f)


def sheets():
    """파일이 있는 시트만"""
    return [sh for sh in manifest()['sheets'] if os.path.exists(os.path.join(SRC, sh['file']))]


def card_faces(names=None):
    """카드 이름 → PIL 이미지. names를 주면 그 이름만"""
    out = {}
    for sh in sheets():
        im = Image.open(os.path.join(SRC, sh['file'])).convert('RGB')
        cw, ch = im.width / sh['cols'], im.height / sh['rows']
        for i, name in enumerate(sh['names']):
            if names is not None and name not in names: continue
            r, c = divmod(i, sh['cols'])
            face = im.crop((round(c * cw), round(r * ch), round((c + 1) * cw), round((r + 1) * ch)))
            if face.width > CARD_W:
                face = face.resize((CARD_W, round(face.height * CARD_W / face.width)), Image.LANCZOS)
            out[name] = face
    return out


def face_ratio():
    """앞면 가로 / 세로 (첫 시트의 한 칸)"""
    sh = sheets()[0]
    w, h = Image.open(os.path.join(SRC, sh['file'])).size
    return (w / sh['cols']) / (h / sh['rows'])


def card_back(ratio):
    im = Image.open(os.path.join(SRC, manifest()['back'])).convert('RGB')
    w, h = im.size
    cut = max(0, w - round(h * ratio))          # 걷어 낼 전체 폭
    a, b = cut // 2, cut - cut // 2
    out = Image.new('RGB', (w - cut, h))
    out.paste(im.crop((0, 0, FRAME, h)), (0, 0))
    out.paste(im.crop((FRAME + a, 0, w - FRAME - b, h)), (FRAME, 0))
    out.paste(im.crop((w - FRAME, 0, w, h)), (w - cut - FRAME, 0))
    if out.width > CARD_W:
        out = out.resize((CARD_W, round(out.height * CARD_W / out.width)), Image.LANCZOS)
    return out


def field_mat():
    return Image.open(os.path.join(SRC, manifest()['mat'])).convert('RGB')


def check(pool_names):
    """시트 이름 점검: (풀에 없는 시트 이름, 이미지가 없는 풀 카드) — 오타 · 시트 누락 확인용"""
    have = [n for sh in sheets() for n in sh['names']]
    return [n for n in have if n not in pool_names], [n for n in pool_names if n not in have]


def bundle(names):
    """재생 화면에 넣을 이미지 묶음: {'mat', 'back', 'ratio', 'mat_size', 'faces': {카드 이름: uri}}"""
    ratio = face_ratio(); mat = field_mat()
    return {'mat': _uri(mat, 85), 'mat_size': list(mat.size), 'back': _uri(card_back(ratio)), 'ratio': ratio,
            'faces': {k: _uri(v) for k, v in card_faces(set(names)).items()}}


if __name__ == '__main__':   # 확인용: 잘린 이미지를 폴더에 저장 — python3 assets.py <출력 폴더>
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else 'assets_out'
    os.makedirs(out, exist_ok=True)
    for k, v in card_faces().items(): v.save(os.path.join(out, f'{k}.webp'), 'WEBP', quality=QUALITY)
    card_back(face_ratio()).save(os.path.join(out, 'back.webp'), 'WEBP', quality=QUALITY)
    print(out, len(os.listdir(out)), '장')
