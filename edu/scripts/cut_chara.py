"""Canvaで作ったキャラ画像（白背景）を切り抜く。
外周から白い背景を塗りつぶしでたどって透明にする（キャラの中の白、ひげや道着は残る）。
public/chara/sennin/*.png → public/chara/cut/*.png（余白を詰めて、足元を下端にそろえる）
"""
import sys
from collections import deque
from pathlib import Path
from PIL import Image

SRC = Path('public/chara/sennin')
DST = Path('public/chara/cut')
TOL = 34  # 白からのずれの許容

def cut(path: Path) -> Image.Image:
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h - 1))
    for y in range(h):
        q.append((0, y)); q.append((w - 1, y))
    def bg(c):
        return c[0] > 255 - TOL and c[1] > 255 - TOL and c[2] > 255 - TOL
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        if not bg(px[x, y]):
            continue
        px[x, y] = (255, 255, 255, 0)
        if x > 0: q.append((x - 1, y))
        if x < w - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < h - 1: q.append((x, y + 1))
    return im

for p in sorted(SRC.glob('*.png')):
    im = cut(p)
    bbox = im.getbbox()
    im.save(DST / p.name)
    print(p.name, 'bbox', bbox)
