import React from 'react';
import { Cheeks, Eyes, LINE, MasterHead, Mouth, SKIN, type Face } from './Chibi';

// マスター以外の7人の顔（ちびキャラ・ゆるかわ解説の絵柄）。頭だけを丸い枠に入れて使う。
// 性格は kiai-coaching-app の lib/kline-persona.ts と同じ。髪型と小物で描き分ける。

export const PERSONA_KEYS = ['master', 'spartan', 'ikemen', 'tsundere', 'osananajimi', 'megane', 'nekketsu'] as const;
export type PersonaKey = typeof PERSONA_KEYS[number];

const W = 7;
const sw = { stroke: LINE, strokeWidth: W, strokeLinejoin: 'round' as const, strokeLinecap: 'round' as const };

/** 顔の輪郭（頭の中心はおよそ 200,200）。女性はあごを少し丸く */
const FaceBase: React.FC<{ soft?: boolean }> = ({ soft }) => (
  <path d={soft
    ? 'M96 186 C94 262 136 300 200 300 C264 300 306 262 304 186 C304 136 264 110 200 110 C136 110 96 136 96 186 Z'
    : 'M94 184 C92 258 132 298 200 298 C268 298 308 258 306 184 C306 132 266 106 200 106 C134 106 94 132 94 184 Z'}
    fill={SKIN} {...sw} />
);

type P = { frame: number; amp: number };

const BROWS = (tilt: number, y = 186, color = LINE) => (
  <g fill="none" stroke={color} strokeWidth={6} strokeLinecap="round">
    <path d={`M136 ${y - tilt} Q152 ${y - 8} 170 ${y + tilt}`} />
    <path d={`M264 ${y - tilt} Q248 ${y - 8} 230 ${y + tilt}`} />
  </g>
);

const FACES: Record<Exclude<PersonaKey, 'master'>, React.FC<P>> = {
  // スパルタ女教師：まとめ髪、つり目、指し棒
  spartan: ({ frame, amp }) => (
    <g>
      <circle cx={200} cy={72} r={34} fill="#5b2a3a" {...sw} />
      <path d="M90 200 C80 120 130 90 200 90 C270 90 320 120 310 200 C300 160 260 130 200 132 C140 130 100 160 90 200 Z" fill="#5b2a3a" {...sw} />
      <FaceBase soft />
      <path d="M100 176 C130 120 170 120 200 140 C230 120 270 120 300 176 C270 150 230 146 200 160 C170 146 130 150 100 176 Z" fill="#5b2a3a" {...sw} />
      {BROWS(8, 190)}
      <Eyes face="stern" frame={frame} cx={200} cy={216} gap={46} seed="sp" />
      <Cheeks cx={200} cy={244} gap={70} />
      <Mouth face="stern" amp={amp} cx={200} cy={262} />
      <path d="M318 300 L366 130" stroke="#c9a46a" strokeWidth={9} strokeLinecap="round" />
      <circle cx={366} cy={128} r={7} fill="#ff7b9c" />
    </g>
  ),
  // オラオラ系イケメン：流した金髪、ピアス、にやり
  ikemen: ({ frame, amp }) => (
    <g>
      <FaceBase />
      {/* 横に流した金髪。前髪は右から左へ大きくかぶせる */}
      <path d="M88 196 C74 118 134 80 210 82 C286 86 326 128 314 196 C306 168 296 150 282 140 C250 158 200 166 150 170 C120 172 100 180 88 196 Z" fill="#ffd36b" {...sw} />
      <path d="M282 140 C300 120 316 118 336 126 M150 170 C170 150 200 136 236 128" fill="none" {...sw} strokeWidth={5} />
      <path d="M258 132 C276 108 300 104 330 112" fill="none" {...sw} />
      {BROWS(6, 192)}
      <Eyes face={amp > 0.1 ? 'calm' : 'smile'} frame={frame} cx={200} cy={216} gap={46} seed="ik" />
      <Cheeks cx={200} cy={244} gap={70} />
      {amp > 0.1 ? <Mouth face="calm" amp={amp} cx={204} cy={262} /> : <path d="M186 260 Q204 270 222 254" fill="none" {...sw} />}
      <circle cx={304} cy={244} r={7} fill="#ffd36b" stroke={LINE} strokeWidth={3} />
      <path d="M300 96 L310 80 M318 104 L334 96" stroke="#ffd36b" strokeWidth={5} strokeLinecap="round" />
    </g>
  ),
  // ツンデレライバル：ツインテール（リボン）、ほっぺを膨らませる
  tsundere: ({ frame, amp }) => (
    <g>
      <path d="M96 150 C40 170 36 260 60 320 C80 280 86 220 110 180 Z M304 150 C360 170 364 260 340 320 C320 280 314 220 290 180 Z" fill="#e8784f" {...sw} />
      <FaceBase soft />
      <path d="M98 186 C88 120 140 92 200 92 C260 92 312 120 302 186 L282 148 L262 176 L242 140 L220 172 L198 136 L176 172 L156 140 L134 176 L116 150 Z" fill="#e8784f" {...sw} />
      <path d="M86 150 L60 128 L66 166 Z M314 150 L340 128 L334 166 Z" fill="#ff7b9c" {...sw} />
      {BROWS(-6, 188)}
      <Eyes face="calm" frame={frame} cx={206} cy={216} gap={44} seed="ts" />
      <Cheeks cx={204} cy={246} gap={70} strong />
      {/* ぷいっ：口をとがらせる */}
      {amp > 0.1 ? <Mouth face="calm" amp={amp} cx={214} cy={262} /> : <path d="M206 262 Q216 254 226 262" fill="none" {...sw} />}
      <path d="M296 230 C304 222 316 226 312 238" fill="none" stroke={LINE} strokeWidth={4} strokeLinecap="round" />
    </g>
  ),
  // 幼なじみ：ボブにヘアピン、にっこり
  osananajimi: ({ frame, amp }) => (
    <g>
      <path d="M86 230 C70 120 130 84 200 84 C270 84 330 120 314 230 C300 250 290 250 284 230 L116 230 C110 250 100 250 86 230 Z" fill="#8a5a3c" {...sw} />
      <FaceBase soft />
      <path d="M98 180 C110 120 160 102 214 108 C176 130 150 150 136 168 C128 156 116 160 98 180 Z M214 108 C260 110 296 136 302 180 C280 160 250 140 214 108 Z" fill="#8a5a3c" {...sw} />
      <rect x={252} y={126} width={36} height={12} rx={6} fill="#ffd36b" stroke={LINE} strokeWidth={4} transform="rotate(-24 270 132)" />
      {BROWS(-2, 190)}
      <Eyes face={amp > 0.1 ? 'calm' : 'smile'} frame={frame} cx={200} cy={218} gap={46} seed="os" />
      <Cheeks cx={200} cy={246} gap={70} strong />
      <Mouth face="smile" amp={amp} cx={200} cy={262} />
    </g>
  ),
  // ウザメガネ：きっちり分けた髪、四角いメガネ（光る）、したり顔
  megane: ({ frame, amp }) => (
    <g>
      <FaceBase />
      <path d="M90 186 C82 116 140 86 200 86 C262 86 320 114 310 186 C300 150 270 130 214 128 L206 150 L196 128 C140 130 100 150 90 186 Z" fill="#3d4a6b" {...sw} />
      {BROWS(2, 184)}
      <Eyes face="calm" frame={frame} cx={200} cy={216} gap={46} seed="mg" />
      <g fill="rgba(255,255,255,0.25)" stroke={LINE} strokeWidth={6}>
        <rect x={124} y={190} width={64} height={48} rx={10} />
        <rect x={212} y={190} width={64} height={48} rx={10} />
      </g>
      <path d="M188 210 L212 210 M124 206 L100 196 M276 206 L300 196" stroke={LINE} strokeWidth={5} />
      {/* メガネのきらり。ときどき光る */}
      {Math.floor(frame / 45) % 3 === 0 && <path d="M136 198 L150 212 M144 196 L156 208" stroke="#fff" strokeWidth={5} strokeLinecap="round" />}
      <Cheeks cx={200} cy={250} gap={72} />
      {amp > 0.1 ? <Mouth face="calm" amp={amp} cx={200} cy={266} /> : <path d="M184 264 Q204 274 220 258" fill="none" {...sw} />}
    </g>
  ),
  // 熱血漢：赤いつんつん髪、太眉、大口、汗
  nekketsu: ({ frame, amp }) => (
    <g>
      <FaceBase />
      <path d="M88 180 L70 120 L104 134 L96 72 L140 110 L150 52 L184 100 L204 40 L226 100 L258 54 L268 110 L310 76 L300 134 L330 122 L312 180 C270 150 130 150 88 180 Z" fill="#e0443e" {...sw} />
      <g fill={LINE}>
        <path d="M126 186 L172 196 L170 208 L124 198 Z" /><path d="M274 186 L228 196 L230 208 L276 198 Z" />
      </g>
      <Eyes face="shout" frame={frame} cx={200} cy={222} gap={48} seed="nk" />
      <Cheeks cx={200} cy={248} gap={72} />
      <Mouth face="shout" amp={Math.max(0.35, amp)} cx={200} cy={262} />
      <path d="M318 170 C310 188 324 198 330 184 C334 176 324 170 318 170 Z" fill="#9fdcff" stroke={LINE} strokeWidth={3} />
      <path d="M56 230 L36 222 M60 254 L38 258" stroke="#ffb54d" strokeWidth={6} strokeLinecap="round" />
    </g>
  ),
};

/** 丸いアイコンの中の顔。size は表示の大きさ（px） */
export const PersonaFace: React.FC<{ who: string; frame: number; amp?: number; size?: number; face?: Face }> =
  ({ who, frame, amp = 0, size = 250, face = 'calm' }) => {
    const bob = Math.sin(frame / 12) * 4 - (amp > 0.15 ? Math.abs(Math.sin(frame / 3)) * 5 : 0);
    const F = who !== 'master' ? FACES[who as Exclude<PersonaKey, 'master'>] : null;
    return (
      <svg viewBox="30 30 340 340" style={{ width: size, height: size, overflow: 'visible' }}>
        <g transform={`translate(0 ${bob})`}>
          {F ? <F frame={frame} amp={amp} /> : <g transform="translate(0 4)"><MasterHead face={face} amp={amp} frame={frame} /></g>}
        </g>
      </svg>
    );
  };
