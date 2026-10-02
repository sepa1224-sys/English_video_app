import React, { useLayoutEffect, useMemo, useRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { continueRender, delayRender } from 'remotion';

// ベクターで描いたキャラを、毎コマ「ドット絵」に変換して表示する。
//   1. 小さい解像度（w×h ピクセル）で描く
//   2. 半透明を切り捨て、色をパレットに丸める（中間色が出ないように）
//   3. 外側に1ピクセルの濃い縁取りを足す
//   4. ぼかさずに拡大する
// こうすると、構え・口パク・まばたきは今まで通り動かしながら、見た目は16ビット機のドット絵になる。

const parse = (hex: string): [number, number, number] => {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
};

const cache = new Map<string, ImageData>();

export const PixelSprite: React.FC<{
  viewBox: string; // ベクター側の座標
  w: number; h: number; // ドットの数（横・縦）
  scale: number; // 1ドットを何pxで表示するか
  palette: string[];
  outline?: string;
  children: React.ReactNode;
}> = ({ viewBox, w, h, scale, palette, outline = '#140c0a', children }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  const svg = useMemo(() => renderToStaticMarkup(
    <svg xmlns="http://www.w3.org/2000/svg" viewBox={viewBox} width={w} height={h} shapeRendering="crispEdges">{children}</svg>,
  ), [viewBox, w, h, children]);
  // 描き終わるまで書き出しを待たせる（画像の読み込みは非同期なので）
  const handle = useMemo(() => delayRender('pixel sprite'), [svg]);
  const pal = useMemo(() => palette.map(parse), [palette]);
  const ol = useMemo(() => parse(outline), [outline]);

  useLayoutEffect(() => {
    const draw = (data: ImageData) => {
      const small = document.createElement('canvas');
      small.width = w; small.height = h;
      small.getContext('2d')!.putImageData(data, 0, 0);
      const big = ref.current!;
      const ctx = big.getContext('2d')!;
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, big.width, big.height);
      ctx.drawImage(small, 0, 0, w * scale, h * scale);
      continueRender(handle);
    };
    const hit = cache.get(svg);
    if (hit) { draw(hit); return; }
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      const cx = c.getContext('2d')!;
      cx.drawImage(img, 0, 0, w, h);
      const d = cx.getImageData(0, 0, w, h);
      const px = d.data;
      const solid = new Uint8Array(w * h);
      for (let i = 0; i < w * h; i++) {
        const a = px[i * 4 + 3];
        if (a < 110) { px[i * 4 + 3] = 0; continue; }
        solid[i] = 1;
        // いちばん近いパレット色に丸める
        let best = 0, bd = Infinity;
        for (let k = 0; k < pal.length; k++) {
          const dr = px[i * 4] - pal[k][0], dg = px[i * 4 + 1] - pal[k][1], db = px[i * 4 + 2] - pal[k][2];
          const dd = dr * dr * 0.3 + dg * dg * 0.59 + db * db * 0.11;
          if (dd < bd) { bd = dd; best = k; }
        }
        px[i * 4] = pal[best][0]; px[i * 4 + 1] = pal[best][1]; px[i * 4 + 2] = pal[best][2]; px[i * 4 + 3] = 255;
      }
      // 外側の縁取り（上下左右に隣が塗られている透明ドットを濃い色に）
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const i = y * w + x;
        if (solid[i]) continue;
        const n = (x > 0 && solid[i - 1]) || (x < w - 1 && solid[i + 1]) || (y > 0 && solid[i - w]) || (y < h - 1 && solid[i + w]);
        if (n) { px[i * 4] = ol[0]; px[i * 4 + 1] = ol[1]; px[i * 4 + 2] = ol[2]; px[i * 4 + 3] = 255; }
      }
      if (cache.size > 400) cache.clear();
      cache.set(svg, d);
      draw(d);
    };
    img.onerror = () => continueRender(handle);
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }, [svg]);

  return <canvas ref={ref} width={w * scale} height={h * scale} style={{ width: w * scale, height: h * scale, imageRendering: 'pixelated' }} />;
};
