"""게임 화면용 이미지 만들기 — viewer/assets.py 로 업로드 원본을 잘라 파일로 저장한다(빌드할 때 한 번, Pillow 필요).
출력: <out>/index.json {ratio, mat_size, faces: {카드 이름: 파일}} · mat.webp · back.webp · c/<번호>.webp"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'viewer'))
import assets as AS   # noqa: E402


def build(out, quality=AS.QUALITY):
    os.makedirs(os.path.join(out, 'c'), exist_ok=True)
    ratio = AS.face_ratio(); mat = AS.field_mat()
    mat.save(os.path.join(out, 'mat.webp'), 'WEBP', quality=85, method=6)
    AS.card_back(ratio).save(os.path.join(out, 'back.webp'), 'WEBP', quality=quality, method=6)
    faces = {}
    for i, (name, im) in enumerate(sorted(AS.card_faces().items())):
        fn = f'c/{i}.webp'; im.save(os.path.join(out, fn), 'WEBP', quality=quality, method=6); faces[name] = fn
    idx = {'ratio': ratio, 'mat_size': list(mat.size), 'faces': faces}
    with open(os.path.join(out, 'index.json'), 'w', encoding='utf-8') as f: json.dump(idx, f, ensure_ascii=False)
    return idx


if __name__ == '__main__':
    idx = build(sys.argv[1]); print(sys.argv[1], len(idx['faces']), '장')
