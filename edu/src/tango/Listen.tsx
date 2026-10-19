// 「英単語 聞き流し」（横長・稽古ごと100語）。英単語の発音 → 日本語の意味を①②と読み、読むのに合わせて出す。
// 以前ターゲット1900などで作っていた形式（英語→日本語）を、自前の単語帳『気合の英単語 初段』と道場の色で作り直したもの。
// 時間割は tango_exercise.py が計算して data.plan（コマ）で渡す。ここでは計算しない（音とずれないように）
import React from 'react';
import { AbsoluteFill, Img, Sequence, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import { DELA, ROUNDED } from '../fonts';
import { BROWN, CREAM, Chara, DOJO, GOLD, Intro, Outro, RED, SLAB, TopBar, pop } from './Tango';
import type { ListenData, ListenWord, Who } from './types';

// 10語ごとに横で一緒に聞くキャラ（エクササイズと同じ順）
const COACH: Who[] = ['nekketsu', 'megane', 'tsundere', 'osananajimi', 'ikemen', 'spartan', 'master'];

const WordCard: React.FC<{ w: ListenWord; ja: number[]; i: number }> = ({ w, ja, i }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pop(f, fps, 0);
  const letters = w.headword.length;
  const wordSize = Math.min(150, Math.floor(880 / (letters * 0.66)));
  const long = w.meanings.join('').length > 24;
  return (
    <AbsoluteFill>
      {/* 絵 */}
      <div style={{ position: 'absolute', left: 120, top: 190, width: 660, height: 660, background: CREAM, borderRadius: 30,
        border: `8px solid ${GOLD}`, boxShadow: '0 22px 46px rgba(0,0,0,0.5)', overflow: 'hidden',
        transform: `scale(${0.94 + p * 0.06})`, opacity: Math.min(1, p * 1.4) }}>
        <Img src={staticFile(w.img)} style={{ width: 644, height: 644 }} />
      </div>
      <div style={{ position: 'absolute', left: 146, top: 160, background: RED, color: CREAM, fontFamily: DELA, fontSize: 36,
        borderRadius: 12, padding: '4px 20px', border: `4px solid ${CREAM}` }}>No.{w.no}</div>

      {/* 単語と意味 */}
      <div style={{ position: 'absolute', left: 860, top: 190, width: 940, height: 660, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div style={{ fontFamily: DELA, fontSize: wordSize, color: GOLD, textShadow: SLAB(7), lineHeight: 1.1, whiteSpace: 'nowrap',
          transform: `translateX(${(1 - p) * 40}px)`, opacity: Math.min(1, p * 1.5) }}>{w.headword}</div>
        <div style={{ marginTop: 34, display: 'flex', alignItems: 'flex-start', gap: 22 }}>
          <span style={{ fontFamily: DELA, fontSize: 36, color: BROWN, background: CREAM, borderRadius: 10, padding: '4px 14px',
            whiteSpace: 'nowrap', opacity: Math.min(1, p * 1.5) }}>{w.pos}</span>
          <div style={{ fontFamily: ROUNDED, fontSize: long ? 52 : 64, lineHeight: 1.35 }}>
            {w.meanings.map((m, k) => {
              const at = ja[k] ?? ja[ja.length - 1];
              const shown = f >= at;
              const reading = shown && (k + 1 >= ja.length || f < ja[k + 1]);
              const q = pop(f, fps, at);
              return (
                <div key={k} style={{ color: reading ? GOLD : CREAM, opacity: shown ? Math.min(1, q * 1.5) : 0,
                  transform: `translateY(${shown ? (1 - q) * 14 : 14}px)` }}>{m}</div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 一緒に聞くキャラ */}
      <div style={{ position: 'absolute', right: 40, bottom: -30 }}>
        <Chara who={COACH[Math.floor(i / 10) % COACH.length]} size={300} />
      </div>
    </AbsoluteFill>
  );
};

const Words: React.FC<{ d: ListenData }> = ({ d }) => {
  const f = useCurrentFrame();
  const W = d.plan.words;
  const base = W[0]?.start ?? 0;
  let i = 0;
  while (i + 1 < W.length && W[i + 1].start - base <= f) i++;
  return (
    <AbsoluteFill style={{ background: DOJO }}>
      <TopBar d={d} i={i} within={f - (W[i].start - base)} len={W[i].len} />
      {d.words.map((w, k) => (
        <Sequence key={w.no} from={W[k].start - base} durationInFrames={W[k].len}>
          <WordCard w={w} ja={W[k].ja} i={k} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const TangoListen: React.FC<{ data: ListenData }> = ({ data: d }) => {
  const P = d.plan;
  const wordsEnd = P.outro;
  return (
    <AbsoluteFill style={{ background: BROWN }}>
      <Sequence durationInFrames={P.intro}><Intro d={d} /></Sequence>
      <Sequence from={P.intro} durationInFrames={wordsEnd - P.intro}><Words d={d} /></Sequence>
      <Sequence from={P.outro} durationInFrames={P.total - P.outro}><Outro d={d} /></Sequence>
    </AbsoluteFill>
  );
};
