"""
ondoku_render.py — 音読動画の1フレームを描画する

レイアウト（1920x1080）:
  映像      : 全画面（16:9をそのまま敷き詰める）
  テロップ欄: 画面下部に独立した帯。映像と文字を分離する
                y  752-1080 : 帯
                y  776- 942 : SVO色分けの英文（ラベルが上、語が下）
                y  962-1010 : 日本語訳
                y 1074-1080 : 進捗バー
"""

import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080

# --- テロップ欄 ---
BAND_TOP = 836
BAND_BG = (18, 18, 34)         # 濃紺。LIFFのダーク面(#0f0f23)に近い色
BAND_EDGE = (233, 69, 96)      # 上端のアクセント線（ブランド色）
EN_TOP, EN_BOTTOM = 852, 994
JA_TOP = 1002
JA_COLOR = (216, 216, 224)

# 暗背景用に明度を上げたSVO配色（LIFFの明背景版と対応）
SVO_COLOR = {
    "S": (91, 155, 240),       # 主語 青
    "V": (255, 122, 107),      # 動詞 赤
    "O": (78, 204, 163),       # 目的語 緑
    "C": (232, 192, 77),       # 補語 金
    "M": (154, 154, 168),      # 修飾 灰
    "+": (154, 154, 168),      # 接続詞 灰
}
HL_BG = (233, 69, 96)          # ハイライト（ブランドの赤）
HL_TEXT = (255, 255, 255)
KATA_BG = (58, 52, 24)         # 熟語の帯
KATA_COLOR = (255, 209, 102)

_FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
F_BOLD = os.path.join(_FD, "NotoSansCJKjp-Bold.otf")
F_BLACK = os.path.join(_FD, "NotoSansCJKjp-Black.otf")

SZ_WORD, SZ_LABEL, SZ_JA = 42, 19, 30
GAP_X, GAP_Y = 24, 12

# --- カメラワーク ---
# 各シーンに1つ割り当てる。progress(0→1)に対して
# (zoom, ox, oy) を返す。ox/oy は -1〜1 で、切り出し余白の中での位置。
CAMERA_MOVES = {
    "push_in":    lambda t: (1.00 + 0.14 * t,  0.0, 0.0),
    "pull_out":   lambda t: (1.14 - 0.14 * t,  0.0, 0.0),
    "pan_right":  lambda t: (1.12, -1.0 + 2.0 * t, 0.0),
    "pan_left":   lambda t: (1.12,  1.0 - 2.0 * t, 0.0),
    "tilt_up":    lambda t: (1.12, 0.0,  1.0 - 2.0 * t),
    "tilt_down":  lambda t: (1.12, 0.0, -1.0 + 2.0 * t),
    "zoom_pan":   lambda t: (1.02 + 0.12 * t, -0.6 + 1.2 * t, 0.0),
    "rise":       lambda t: (1.14 - 0.10 * t, 0.0, 0.8 - 1.6 * t),
    "static":     lambda t: (1.0, 0.0, 0.0),
}
DEFAULT_MOVE = "push_in"


def camera_at(move: str, progress: float):
    """カメラワーク名と進捗から (zoom, ox, oy) を返す"""
    f = CAMERA_MOVES.get(move, CAMERA_MOVES[DEFAULT_MOVE])
    t = max(0.0, min(1.0, progress))
    # 端を緩めて、動きの出入りを滑らかにする（ease-in-out）
    e = t * t * (3 - 2 * t)
    return f(e)

_IMG_CACHE: dict[str, Image.Image] = {}


def _font(path, size):
    return ImageFont.truetype(path, size)


def _text_w(draw, s, f):
    return draw.textbbox((0, 0), s, font=f)[2]


def _load_illust(path):
    """イラストを画面比に合わせて切り出して保持（毎フレーム読み直さない）"""
    if path in _IMG_CACHE:
        return _IMG_CACHE[path]
    il = Image.open(path).convert("RGB")
    tw = W / H
    if il.width / il.height > tw:
        nw = int(il.height * tw)
        il = il.crop(((il.width - nw) // 2, 0, (il.width + nw) // 2, il.height))
    else:
        nh = int(il.width / tw)
        il = il.crop((0, (il.height - nh) // 2, il.width, (il.height + nh) // 2))
    _IMG_CACHE[path] = il
    return il


def layout_chunks(draw, chunks, f_word, f_label, max_w):
    """チャンクを折り返して配置する。各行 ([(chunk, x, w)], 行幅) を返す"""
    rows, cur, cur_w = [], [], 0
    for c in chunks:
        w = max(_text_w(draw, c["w"], f_word), _text_w(draw, c["l"], f_label))
        if cur and cur_w + GAP_X + w > max_w:
            rows.append((cur, cur_w)); cur, cur_w = [], 0
        if cur:
            cur_w += GAP_X
        cur.append((c, cur_w, w)); cur_w += w
    if cur:
        rows.append((cur, cur_w))
    return rows


def render_frame(illust, chunks, highlight_idx, ja_text, out_path=None,
                 progress=None, zoom=1.0, ox=0.0, oy=0.0, show_ja=True):
    """1フレームを描いて PIL Image を返す。

    illust: 画像パス、または既に画面比に整えた PIL.Image（動画クリップのフレーム）
    highlight_idx: いま読まれているチャンクの添字（Noneならハイライトなし）
    zoom: 1.0以上。静止画をゆっくり寄せる。クリップ使用時は1.0固定
    """
    # --- 映像を全画面に敷く ---
    src = None
    if isinstance(illust, Image.Image):
        src = illust
    elif illust and os.path.exists(illust):
        src = _load_illust(illust)

    if src is None:
        img = Image.new("RGB", (W, H), (14, 14, 26))
    else:
        if zoom > 1.0:
            cw, ch = int(src.width / zoom), int(src.height / zoom)
            mx, my = src.width - cw, src.height - ch      # 動かせる余白
            x0 = int(mx / 2 + ox * mx / 2)
            y0 = int(my / 2 + oy * my / 2)
            x0 = max(0, min(x0, mx))
            y0 = max(0, min(y0, my))
            src = src.crop((x0, y0, x0 + cw, y0 + ch))
        img = src.resize((W, H), Image.LANCZOS) if src.size != (W, H) else src.copy()

    d = ImageDraw.Draw(img)

    # --- テロップ欄 ---
    d.rectangle([0, BAND_TOP, W, H], fill=BAND_BG)
    d.rectangle([0, BAND_TOP, W, BAND_TOP + 3], fill=BAND_EDGE)

    f_word = _font(F_BOLD, SZ_WORD)
    f_label = _font(F_BOLD, SZ_LABEL)
    f_ja = _font(F_BOLD, SZ_JA)

    # --- 英文（インターリニア） ---
    # 2行に収まらない長文は、収まるまで文字を段階的に小さくする
    sz_w, sz_l = SZ_WORD, SZ_LABEL
    for _ in range(6):
        f_word, f_label = _font(F_BOLD, sz_w), _font(F_BOLD, sz_l)
        rows = layout_chunks(d, chunks, f_word, f_label, max_w=W - 220)
        if len(rows) <= 2:
            break
        sz_w, sz_l = sz_w - 3, max(14, sz_l - 1)
    row_h = sz_l + 4 + sz_w
    total_h = len(rows) * row_h + (len(rows) - 1) * GAP_Y
    y = EN_TOP + max(0, ((EN_BOTTOM - EN_TOP) - total_h) // 2)

    idx = 0
    for row, row_w in rows:
        x0 = (W - row_w) // 2
        for c, dx, w in row:
            x = x0 + dx
            on = (highlight_idx is not None and idx == highlight_idx)
            color = KATA_COLOR if c["kata"] else SVO_COLOR.get(c["l"], (200, 200, 210))

            if c["kata"] and not on:
                d.rounded_rectangle(
                    [x - 8, y - 4, x + w + 8, y + row_h + 4], 6, fill=KATA_BG)
            if on:
                d.rounded_rectangle(
                    [x - 10, y - 6, x + w + 10, y + row_h + 6], 8, fill=HL_BG)

            label = "V★" if c["kata"] else ("＋" if c["l"] == "+" else c["l"])
            lc = HL_TEXT if on else color
            d.text((x, y), label, font=f_label, fill=lc)
            d.text((x, y + sz_l + 4), c["w"], font=f_word, fill=lc)
            idx += 1
        y += row_h + GAP_Y

    # --- 日本語訳 ---
    # 訳が見えていると英語を読まずに済むため、既定では出さない。
    # 視聴者は YouTube の字幕から必要なときだけ参照する。
    if show_ja and ja_text:
        jw = _text_w(d, ja_text, f_ja)
        d.text(((W - jw) // 2, JA_TOP), ja_text, font=f_ja, fill=JA_COLOR)

    # --- 進捗バー ---
    if progress is not None:
        d.rectangle([0, H - 6, W, H], fill=(40, 40, 60))
        d.rectangle([0, H - 6, int(W * progress), H], fill=BAND_EDGE)

    if out_path:
        img.save(out_path)
    return img
