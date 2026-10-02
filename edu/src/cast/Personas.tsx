// ⚠ Personas.tsx は /Users/sakamototatsurou/kiai-line-shorts/src/Personas.tsx の写しです。ここでは編集しない（scripts/sync-cast.mjs が上書きする）。
import React from 'react';
import { MasterHead, INK, BODY } from './Character';

// 毎朝の相手7人の顔。マスターと同じ、黒地に白い線の手描き風。
// 髪型と小物で描き分ける（設定は lib/kline-persona.ts の性格どおり）
const PINK = '#ff6b8a';
const S = 5;
const line = { fill: 'none', stroke: INK, strokeWidth: S, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
const solid = { fill: BODY, stroke: INK, strokeWidth: S, strokeLinejoin: 'round' as const };

/** 顔の輪郭と首。女性はあごを丸く */
const Base: React.FC<{ soft?: boolean }> = ({ soft }) => (
  <g>
    <path d="M84 168 L82 200 M116 168 L118 200" {...line} />
    <path d="M40 200 C44 178 64 168 84 166 L100 178 L116 166 C136 168 156 178 160 200" {...solid} />
    {soft
      ? <path d="M58 92 C56 130 66 158 100 168 C134 158 144 130 142 92 Z" {...solid} />
      : <path d="M58 90 C56 126 62 146 78 160 L92 168 C96 171 104 171 108 168 L122 160 C138 146 144 126 142 90 Z" {...solid} />}
  </g>
);
const Blush = () => <path d="M66 128 L74 122 M72 130 L80 124 M120 124 L128 130 M126 122 L134 128" stroke={PINK} strokeWidth={3} strokeLinecap="round" />;

const FACES: Record<string, React.FC<{ frame: number }>> = {
  master: ({ frame }) => (
    <g transform="translate(-58 -42) scale(0.6)"><MasterHead face="stern" amp={0} frame={frame} /></g>
  ),
  // スパルタ女教師：まとめ髪、細い目、指し棒
  spartan: () => (
    <g>
      <circle cx={100} cy={36} r={18} {...solid} />
      <Base soft />
      <path d="M56 100 C52 60 76 44 100 44 C124 44 148 60 144 100 C130 80 110 70 100 72 C88 72 70 80 56 100 Z" {...solid} />
      <path d="M72 108 L92 104 M108 104 L128 108" {...line} />
      <path d="M74 118 L90 116 M110 116 L126 118" {...line} strokeWidth={4} />
      <path d="M92 146 C98 142 104 142 110 146" {...line} stroke={PINK} />
      <path d="M150 186 L186 60" stroke="#c9a46a" strokeWidth={6} strokeLinecap="round" />
    </g>
  ),
  // オラオラ系イケメン：流した髪、ピアス、にやり
  ikemen: () => (
    <g>
      <Base />
      <path d="M54 104 C46 56 90 36 128 46 C150 52 162 72 154 96 L140 78 L132 96 L118 72 C96 84 74 86 54 104 Z" {...solid} />
      <path d="M118 72 C126 60 140 56 160 60" {...line} />
      <path d="M72 110 L92 114 M108 114 L128 110" {...line} />
      <path d="M76 122 C82 118 88 118 92 122 M108 122 C112 118 118 118 124 122" {...line} strokeWidth={4} />
      <path d="M88 146 C98 150 110 148 118 140" {...line} />
      <circle cx={142} cy={136} r={4} fill="#ffd166" />
    </g>
  ),
  // ツンデレライバル：ツインテール、そっぽ、ふくれ顔
  tsundere: () => (
    <g>
      <path d="M50 86 C20 100 18 150 34 186 C44 160 46 120 58 100 Z M150 86 C180 100 182 150 166 186 C156 160 154 120 142 100 Z" {...solid} />
      <Base soft />
      <path d="M56 100 C52 58 78 44 100 44 C122 44 148 58 144 100 L132 84 L120 96 L106 80 L92 96 L78 82 L66 98 Z" {...solid} />
      <circle cx={58} cy={88} r={7} fill={PINK} /><circle cx={142} cy={88} r={7} fill={PINK} />
      <path d="M70 112 L92 108 M108 108 L130 112" {...line} />
      <path d="M78 124 L90 122 M114 122 L126 124" {...line} strokeWidth={4} />
      <circle cx={88} cy={126} r={3} fill={INK} /><circle cx={124} cy={126} r={3} fill={INK} />
      <path d="M94 148 L104 144 L112 148" {...line} />
      <Blush />
    </g>
  ),
  // 幼なじみ：ボブ、髪留め、やわらかい笑顔
  osananajimi: () => (
    <g>
      <Base soft />
      <path d="M52 132 C40 70 70 44 100 44 C130 44 160 70 148 132 C140 108 136 92 128 84 C110 96 84 96 66 84 C60 96 58 112 52 132 Z" {...solid} />
      <rect x={120} y={70} width={22} height={8} rx={4} fill="#ffd166" transform="rotate(-20 131 74)" />
      <path d="M74 118 C80 110 88 110 92 118 M108 118 C112 110 120 110 126 118" {...line} />
      <path d="M86 142 C94 152 106 152 114 142" {...line} />
      <Blush />
    </g>
  ),
  // ウザメガネ：四角い眼鏡、きっちり七三、したり顔
  megane: () => (
    <g>
      <Base />
      <path d="M56 100 C50 56 84 40 110 44 C136 48 152 66 144 100 C134 80 120 66 96 64 C80 70 66 82 56 100 Z" {...solid} />
      <path d="M96 64 L90 100" {...line} strokeWidth={3} />
      <rect x={66} y={108} width={30} height={20} rx={4} {...line} />
      <rect x={104} y={108} width={30} height={20} rx={4} {...line} />
      <path d="M96 116 L104 116" {...line} />
      <path d="M72 112 L80 120 M110 112 L118 120" stroke="#7fd3ff" strokeWidth={3} strokeLinecap="round" />
      <path d="M88 146 C96 148 108 146 116 140" {...line} />
    </g>
  ),
  // 熱血漢：炎の髪、太い眉、叫ぶ口
  nekketsu: ({ frame }) => (
    <g>
      <path d={`M40 120 C30 80 46 40 60 30 C60 60 70 64 76 50 C80 30 96 14 100 ${6 + Math.sin(frame / 4) * 4} C104 24 120 34 124 50 C130 64 140 60 140 30 C154 40 170 80 160 120 Z`} fill="#ff8a3d" opacity={0.35} />
      <Base />
      <path d="M56 100 L44 60 L68 72 L64 34 L88 58 L100 22 L112 58 L136 34 L132 72 L156 60 L144 100 C120 86 80 86 56 100 Z" {...solid} />
      <path d="M66 104 L94 112 L92 118 L64 110 Z M134 104 L106 112 L108 118 L136 110 Z" fill={INK} />
      <circle cx={82} cy={126} r={4} fill={INK} /><circle cx={118} cy={126} r={4} fill={INK} />
      <path d="M80 142 C90 140 110 140 120 142 C116 162 84 162 80 142 Z" fill="#2a0d14" stroke={INK} strokeWidth={S - 1} strokeLinejoin="round" />
    </g>
  ),
};

export const PersonaFace: React.FC<{ who: string; frame: number }> = ({ who, frame }) => {
  const F = FACES[who] ?? FACES.master;
  return (
    <svg viewBox="0 0 200 200" style={{ width: 250, height: 250 }}>
      <F frame={frame} />
    </svg>
  );
};
