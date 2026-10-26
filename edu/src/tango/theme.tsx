// サムネの色と札の決まり（2026-10-26 坂本さん「全部一緒に見える」「イメージで覚えると耳で覚えるの違いがわかりにくい」）
//   稽古・イメージで覚える … 赤〜オレンジ（今までどおり）
//   聞き流し（稽古・大学別とも）… 濃い青。「聞き流し」を大きく＋ヘッドホン
//   大学別・イメージで覚える … 緑
// 種類は props の data から決める（thumbTop が「聞き流し」か series に「聞き流し」）。theme を渡せばそれが優先
import React from 'react';
import type { TangoData } from './types';

export type ThumbKind = 'exercise' | 'listen';
export type ThumbTheme = { bg: string; slab: string; shadow: string; accent: string; band: string };

export const thumbKind = (d: TangoData, theme?: ThumbKind): ThumbKind =>
  theme ?? (d.thumbTop === '聞き流し' || /聞き流し/.test(d.series ?? '') ? 'listen' : 'exercise');

const slabOf = (c: string) => (n: number) => Array.from({ length: n }, (_, i) => `${i + 1}px ${i + 1}px 0 ${c}`).join(',');

export const THEMES = {
  exercise: {
    bg: 'radial-gradient(ellipse at 50% 62%, #ffb43a 0%, #f2701f 32%, #d7262e 68%, #a8141c 100%)',
    slab: '#5a1208', shadow: 'rgba(60,0,0,0.5)', accent: '#d7262e', band: '#1b0a04',
  },
  listen: {
    bg: 'radial-gradient(ellipse at 50% 62%, #4fc3f7 0%, #1e88e5 34%, #1546a8 70%, #0b2466 100%)',
    slab: '#061a4a', shadow: 'rgba(0,10,50,0.55)', accent: '#1e88e5', band: '#06163d',
  },
  group: {
    bg: 'radial-gradient(ellipse at 50% 62%, #b6e35a 0%, #43b049 34%, #17803e 70%, #0a4d26 100%)',
    slab: '#073318', shadow: 'rgba(0,30,10,0.55)', accent: '#17803e', band: '#06261a',
  },
} satisfies Record<string, ThumbTheme>;

export const slab = (t: ThumbTheme) => slabOf(t.slab);

// ヘッドホン（SVGで描く・外部の素材は使わない）
export const Headphones: React.FC<{ size: number; color: string; outline: string }> = ({ size, color, outline }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" style={{ flexShrink: 0, overflow: 'visible' }}>
    <g stroke={outline} strokeWidth={6} strokeLinejoin="round" strokeLinecap="round">
      <path d="M14 62 V50 A36 36 0 0 1 86 50 V62" fill="none" strokeWidth={22} />
      <path d="M14 62 V50 A36 36 0 0 1 86 50 V62" fill="none" stroke={color} strokeWidth={11} />
      <rect x={4} y={52} width={24} height={40} rx={10} fill={color} />
      <rect x={72} y={52} width={24} height={40} rx={10} fill={color} />
    </g>
  </svg>
);
