// 大学グループ別（GMARCH・早慶など）の英単語動画のサムネ（1280×720）。
// 「サムネがもっとGMARCHをアピールしないといけない」（2026-10-26 坂本さん）→ グループ名をいちばん大きく。
// 大学のロゴ・校章・スクールカラーは使わない（文字だけ）。色は稽古のサムネと同じ赤・金・こげ茶。
// variant A：右に「によく出る／GMARCH／英単語100」、左に絵を4枚
// variant B：上のこげ茶の帯にグループ名を横いっぱいに、下に「頻出 英単語」「100語」と絵
// 色（2026-10-26）：大学別のイメージで覚える＝緑、聞き流し＝青＋「聞き流し」とヘッドホン（theme.tsx）。稽古の赤と見分ける
import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';

import { DELA } from '../fonts';
import { CREAM, GOLD, RED } from './Tango';
import { Headphones, THEMES, type ThumbKind, type ThumbTheme, slab, thumbKind } from './theme';
import type { TangoData } from './types';

export type GroupThumbProps = { data: TangoData; group?: string; variant?: 'A' | 'B'; theme?: ThumbKind };

// Dela Gothic One のおおよその字幅（em）。グループ名を幅に合わせて最大の大きさにする
const em = (s: string) => [...s].reduce((n, c) => n + (/[A-Z]/.test(c) ? 0.98 : /[ -~]/.test(c) ? 0.6 : 1.0), 0);
const fit = (s: string, width: number, max: number) => Math.min(max, Math.floor(width / Math.max(em(s), 0.1)));

const groupOf = (p: GroupThumbProps) => p.group ?? (p.data.label ?? '').replace(/頻出.*$/, '') ?? '';

const Card: React.FC<{ src: string; size: number; tilt: number; shadow: string; style?: React.CSSProperties }> = ({ src, size, tilt, shadow, style }) => (
  <div style={{ width: size, height: size, background: '#fff', borderRadius: 22, border: `7px solid ${CREAM}`, overflow: 'hidden',
    transform: `rotate(${tilt}deg)`, boxShadow: `0 14px 28px ${shadow}`, display: 'flex', alignItems: 'center', justifyContent: 'center', ...style }}>
    <Img src={staticFile(src)} style={{ width: size - 14, height: size - 14, objectFit: 'contain' }} />
  </div>
);

const Brand: React.FC<{ t: ThumbTheme; size?: number }> = ({ t, size = 44 }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontFamily: DELA, lineHeight: 1 }}>
    <span style={{ fontSize: size, color: CREAM, textShadow: slab(t)(4) }}><span style={{ color: GOLD }}>気合</span>の英単語</span>
    <span style={{ fontSize: size * 0.73, color: RED, background: GOLD, borderRadius: 10, padding: '6px 12px' }}>必修</span>
  </div>
);

const A: React.FC<{ d: TangoData; g: string; t: ThumbTheme; listen: boolean }> = ({ d, g, t, listen }) => {
  const SLAB = slab(t);
  const imgs = d.thumbs.slice(0, 4);
  const tilt = [-4, 3, 3, -3];
  // 英字の名前は少し横を詰めて（0.9）背を高くする
  const sx = /^[ -~]+$/.test(g) ? 0.9 : 1;
  const big = fit(g, 830 / sx, 300);
  return (
    <AbsoluteFill style={{ background: t.bg, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 24, top: 160, width: 430, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
        {imgs.map((src, k) => <Card key={k} src={src} size={206} tilt={tilt[k]} shadow={t.shadow} />)}
      </div>
      <div style={{ position: 'absolute', left: 28, top: 22 }}><Brand t={t} /></div>
      <div style={{ position: 'absolute', left: 462, right: 10, top: 70, bottom: 0, display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', fontFamily: DELA, lineHeight: 1 }}>
        <div style={{ fontSize: 70, color: CREAM, textShadow: SLAB(6), whiteSpace: 'nowrap', alignSelf: 'flex-end', marginRight: 20 }}>によく出る</div>
        <div style={{ fontSize: big, color: GOLD, textShadow: SLAB(14), whiteSpace: 'nowrap', letterSpacing: -4, marginTop: 10, transform: `scaleX(${sx})`,
          WebkitTextStroke: `6px ${t.band}`, paintOrder: 'stroke fill' }}>{g}</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 18, background: t.band, borderRadius: 18, padding: '10px 28px 14px' }}>
          <span style={{ fontSize: 76, color: CREAM }}>英単語</span>
          <span style={{ fontSize: 96, color: GOLD }}>100</span>
          {listen ? <span style={{ fontSize: 60, color: GOLD, marginLeft: 18 }}>聞き流し</span> : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const B: React.FC<{ d: TangoData; g: string; t: ThumbTheme; listen: boolean }> = ({ d, g, t, listen }) => {
  const SLAB = slab(t);
  // 聞き流しは「聞き流し」を大きく出すので絵は2枚
  const imgs = d.thumbs.slice(0, listen ? 2 : 3);
  const tilt = [-5, 4, -3];
  const short = [...g].length <= 3;
  const big = fit(g, short ? 860 : 1150, short ? 300 : 280);
  return (
    <AbsoluteFill style={{ background: t.bg, overflow: 'hidden' }}>
      {/* 上：濃い色の帯にグループ名 */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 380, background: t.band, borderBottom: `10px solid ${GOLD}` }} />
      <div style={{ position: 'absolute', left: 24, top: 18 }}><Brand t={t} size={36} /></div>
      <div style={{ position: 'absolute', left: 0, right: 0, top: 62, height: 318, display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: 18, fontFamily: DELA, lineHeight: 1 }}>
        {short ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
            {['合', '格', 'へ'].map((c) => (
              <span key={c} style={{ fontSize: 64, color: t.band, background: GOLD, borderRadius: 12, width: 84, height: 84,
                display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{c}</span>
            ))}
          </div>
        ) : null}
        <div style={{ fontSize: big, color: GOLD, whiteSpace: 'nowrap', letterSpacing: short ? 10 : -4,
          textShadow: `0 0 0 ${GOLD}, 8px 8px 0 ${t.accent}` }}>{g}</div>
        <div style={{ writingMode: 'vertical-rl', fontSize: 58, color: CREAM, whiteSpace: 'nowrap', marginTop: -10 }}>によく出る</div>
      </div>
      {/* 下：頻出 英単語 100語 と絵（聞き流しは「聞き流し」を大きく） */}
      {listen ? (
        <div style={{ position: 'absolute', left: 34, top: 412, fontFamily: DELA, lineHeight: 1 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', whiteSpace: 'nowrap' }}>
            <span style={{ fontSize: 70, color: CREAM, textShadow: SLAB(6) }}>頻出英単語</span>
            <span style={{ fontSize: 92, color: GOLD, textShadow: SLAB(8), WebkitTextStroke: `4px ${t.band}`, paintOrder: 'stroke fill', marginLeft: 14 }}>100</span>
            <span style={{ fontSize: 58, color: CREAM, textShadow: SLAB(5), marginLeft: 4 }}>語</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 22 }}>
            <Headphones size={126} color={CREAM} outline={t.band} />
            <span style={{ fontSize: 142, color: GOLD, textShadow: SLAB(12), WebkitTextStroke: `5px ${t.band}`, paintOrder: 'stroke fill',
              letterSpacing: -4, whiteSpace: 'nowrap' }}>聞き流し</span>
          </div>
        </div>
      ) : (
        <div style={{ position: 'absolute', left: 34, top: 418, fontFamily: DELA, lineHeight: 1 }}>
          <div style={{ fontSize: 96, color: CREAM, textShadow: SLAB(8), whiteSpace: 'nowrap' }}>頻出英単語</div>
          <div style={{ display: 'flex', alignItems: 'baseline', marginTop: 22 }}>
            <span style={{ fontSize: 150, color: GOLD, textShadow: SLAB(12), WebkitTextStroke: `5px ${t.band}`, paintOrder: 'stroke fill' }}>100</span>
            <span style={{ fontSize: 80, color: CREAM, textShadow: SLAB(6), marginLeft: 8 }}>語</span>
          </div>
        </div>
      )}
      <div style={{ position: 'absolute', right: 26, top: 420, display: 'flex', gap: 14 }}>
        {imgs.map((src, k) => <Card key={k} src={src} size={226} tilt={tilt[k]} shadow={t.shadow} style={{ marginTop: k === 1 ? 40 : 0 }} />)}
      </div>
    </AbsoluteFill>
  );
};

export const TangoGroupThumb: React.FC<GroupThumbProps> = (p) => {
  const g = groupOf(p) || 'GMARCH';
  const listen = thumbKind(p.data, p.theme) === 'listen';
  const t = listen ? THEMES.listen : THEMES.group;
  return p.variant === 'B' ? <B d={p.data} g={g} t={t} listen={listen} /> : <A d={p.data} g={g} t={t} listen={listen} />;
};
