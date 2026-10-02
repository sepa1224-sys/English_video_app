// ⚠ Character.tsx は /Users/sakamototatsurou/kiai-line-shorts/src/Character.tsx の写しです。ここでは編集しない（scripts/sync-cast.mjs が上書きする）。
import React from 'react';
import { random } from 'remotion';
import type { Pose } from './pose';

// 語り手「マスター」。ロゴと同じ、黒地に白い線の手描き風。
// パーツ（胴・腕・頭・眉・目・口・鉢巻）に分けて描くので、表情や腕を差し替えられ、
// 口は声の大きさ（amp 0〜1）に合わせて開く。アプリの中で動かすときも同じ部品が使える。

export const INK = '#ffffff';
export const BODY = '#14142a';
const PINK = '#ff6b8a';
const SW = 6; // 線の太さ

/** 手描きアニメの「線のふるえ」。3コマごとに、部品ごとに少しだけずらす */
const boil = (frame: number, key: string, a = 1.4) => {
  const s = Math.floor(frame / 3);
  const dx = (random(`${key}x${s}`) - 0.5) * a * 2;
  const dy = (random(`${key}y${s}`) - 0.5) * a * 2;
  const r = (random(`${key}r${s}`) - 0.5) * a * 0.6;
  return `translate(${dx} ${dy}) rotate(${r} 260 400)`;
};

/** 線分に沿った太い腕（角の丸い長方形） */
const Limb: React.FC<{ x1: number; y1: number; x2: number; y2: number; w: number }> = ({ x1, y1, x2, y2, w }) => {
  const len = Math.hypot(x2 - x1, y2 - y1);
  const deg = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI;
  return <rect x={0} y={-w / 2} width={len} height={w} rx={w / 2} transform={`translate(${x1} ${y1}) rotate(${deg})`} fill={BODY} stroke={INK} strokeWidth={SW} />;
};

/** 握りこぶし。指の線を3本入れる */
const Fist: React.FC<{ x: number; y: number; r?: number; rot?: number }> = ({ x, y, r = 34, rot = 0 }) => (
  <g transform={`translate(${x} ${y}) rotate(${rot})`}>
    <rect x={-r} y={-r * 0.85} width={r * 2} height={r * 1.7} rx={r * 0.55} fill={BODY} stroke={INK} strokeWidth={SW} />
    <path d={`M${-r * 0.35} ${-r * 0.8} L${-r * 0.35} ${-r * 0.1} M${r * 0.2} ${-r * 0.8} L${r * 0.2} ${-r * 0.1} M${-r} ${r * 0.05} C${-r * 0.3} ${r * 0.3} ${r * 0.4} ${r * 0.3} ${r} ${r * 0.05}`}
      fill="none" stroke={INK} strokeWidth={SW - 1.5} strokeLinecap="round" />
  </g>
);

/** 人差し指を立てた手 */
const PointHand: React.FC<{ x: number; y: number; rot: number }> = ({ x, y, rot }) => (
  <g transform={`translate(${x} ${y}) rotate(${rot})`}>
    <rect x={-30} y={-26} width={60} height={52} rx={20} fill={BODY} stroke={INK} strokeWidth={SW} />
    <rect x={18} y={-22} width={62} height={20} rx={10} fill={BODY} stroke={INK} strokeWidth={SW} />
    <path d="M-24 6 C-8 14 8 14 22 8" fill="none" stroke={INK} strokeWidth={SW - 1.5} strokeLinecap="round" />
  </g>
);

/** 開いた手のひら */
const Palm: React.FC<{ x: number; y: number; rot: number }> = ({ x, y, rot }) => (
  <g transform={`translate(${x} ${y}) rotate(${rot})`} fill={BODY} stroke={INK} strokeWidth={SW} strokeLinejoin="round">
    {[-24, -8, 8, 24].map((fx, i) => <rect key={i} x={fx - 7} y={-64 + Math.abs(fx) * 0.5} width={14} height={40} rx={7} />)}
    <rect x={-32} y={-34} width={64} height={56} rx={22} />
    <rect x={-52} y={-18} width={30} height={14} rx={7} transform="rotate(-30 -37 -11)" />
  </g>
);

type Face = 'calm' | 'stern' | 'surprised' | 'shout' | 'smile';
const faceFor = (pose: Pose): Face =>
  pose === 'surprised' ? 'surprised' : pose === 'fist' ? 'shout' : pose === 'arms' || pose === 'point' ? 'stern' : 'calm';

/** 頭。髪・鉢巻・顔のつくり。amp は口の開き（0〜1） */
export const MasterHead: React.FC<{ face: Face; amp: number; frame: number }> = ({ face, amp, frame }) => {
  const t = frame / 30;
  const wave = (k: number) => Math.sin(t * 4 + k) * 10;
  const browY = face === 'surprised' ? -12 : 0;
  const open = face === 'shout' ? Math.max(0.6, amp) : amp;
  return (
    <g>
      {/* 鉢巻のたなびく端（頭の後ろ） */}
      <path d={`M322 212 C360 ${200 + wave(0)} 395 ${178 + wave(1)} 452 ${190 + wave(2)} L446 ${206 + wave(2)} C392 ${198 + wave(1)} 362 ${222 + wave(0)} 326 230 Z`} fill={PINK} stroke={INK} strokeWidth={SW - 1} strokeLinejoin="round" />
      <path d={`M324 226 C362 ${236 + wave(1)} 398 ${232 + wave(2)} 440 ${258 + wave(3)} L430 ${270 + wave(3)} C392 ${250 + wave(2)} 360 ${252 + wave(1)} 322 240 Z`} fill={PINK} stroke={INK} strokeWidth={SW - 1} strokeLinejoin="round" />
      {/* 耳 */}
      <path d="M192 250 C172 246 168 280 190 292 M328 250 C348 246 352 280 330 292" fill={BODY} stroke={INK} strokeWidth={SW} strokeLinecap="round" />
      {/* 輪郭（角ばったあご） */}
      <path d="M190 210 C186 260 192 300 214 330 L240 352 C252 360 268 360 280 352 L306 330 C328 300 334 260 330 210 Z" fill={BODY} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
      {/* 髪：逆立った房 */}
      <path d="M186 214 L168 168 L198 182 L188 128 L226 160 L232 102 L262 150 L284 96 L298 154 L332 116 L326 178 L356 160 L334 214 C300 196 220 196 186 214 Z" fill={BODY} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
      <path d="M214 180 L226 160 M252 166 L262 150 M300 170 L298 154" stroke={INK} strokeWidth={SW - 2} strokeLinecap="round" />
      {/* 鉢巻 */}
      <path d="M184 206 C220 190 300 190 336 206 L334 234 C300 220 220 220 186 234 Z" fill={PINK} stroke={INK} strokeWidth={SW - 1} strokeLinejoin="round" />
      <text x={260} y={225} textAnchor="middle" fontSize={22} fontWeight={800} fill="#fff" style={{ fontFamily: 'KiaiHand' }}>気合</text>
      {/* 眉：太く、角度で感情を出す */}
      <g transform={`translate(0 ${browY})`} fill={INK}>
        {face === 'smile'
          ? <><path d="M206 258 C218 248 236 248 246 256 L244 262 C234 256 220 256 208 264 Z" /><path d="M314 258 C302 248 284 248 274 256 L276 262 C286 256 300 256 312 264 Z" /></>
          : <><path d="M202 248 L248 262 L246 272 L200 260 Z" /><path d="M318 248 L272 262 L274 272 L320 260 Z" /></>}
      </g>
      {/* 目 */}
      {face === 'surprised'
        ? <g fill="none" stroke={INK} strokeWidth={SW - 1}><circle cx={226} cy={284} r={11} /><circle cx={294} cy={284} r={11} /><circle cx={226} cy={284} r={3} fill={INK} /><circle cx={294} cy={284} r={3} fill={INK} /></g>
        : face === 'smile'
          ? <path d="M212 286 C220 278 232 278 240 286 M280 286 C288 278 300 278 308 286" fill="none" stroke={INK} strokeWidth={SW - 1} strokeLinecap="round" />
          : <g><path d="M210 282 L242 286 M278 286 L310 282" stroke={INK} strokeWidth={SW - 1} strokeLinecap="round" /><circle cx={228} cy={289} r={4} fill={INK} /><circle cx={292} cy={289} r={4} fill={INK} /></g>}
      {/* 鼻・頬のしわ・無精ひげ（師匠らしさ） */}
      <path d="M262 290 L254 314 L266 316" fill="none" stroke={INK} strokeWidth={SW - 2} strokeLinecap="round" strokeLinejoin="round" />
      <path d="M214 304 L222 318 M306 304 L298 318" stroke={INK} strokeWidth={SW - 3} strokeLinecap="round" />
      {[[236, 344], [248, 348], [272, 348], [284, 344], [260, 350]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r={1.8} fill={INK} />)}
      {/* 口：声の大きさで開く */}
      {open > 0.12
        ? <path d={`M${240 - open * 6} 330 C${248} ${330 + open * 2} ${272} ${330 + open * 2} ${280 + open * 6} 330 C${276} ${330 + 8 + open * 22} ${244} ${330 + 8 + open * 22} ${240 - open * 6} 330 Z`} fill="#2a0d14" stroke={INK} strokeWidth={SW - 1.5} strokeLinejoin="round" />
        : face === 'smile'
          ? <path d="M240 330 C252 340 268 340 280 330" fill="none" stroke={INK} strokeWidth={SW - 1.5} strokeLinecap="round" />
          : <path d="M242 332 L278 332" stroke={INK} strokeWidth={SW - 1.5} strokeLinecap="round" />}
      {face === 'surprised' && <path d="M346 236 C340 252 352 262 358 250 C362 242 352 236 346 236 Z" fill="#7fd3ff" stroke={INK} strokeWidth={3} />}
    </g>
  );
};

/** 胴（道着）。たくましい肩と、合わせの襟 */
const Torso: React.FC = () => (
  <g>
    <path d="M232 352 L228 392 M288 352 L292 392" stroke={INK} strokeWidth={SW} strokeLinecap="round" />
    <path d="M70 640 C76 480 140 412 230 390 L260 452 L290 390 C380 412 444 480 450 640 Z" fill={BODY} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
    {/* 胸元（はだけた道着からのぞく胸板） */}
    <path d="M230 390 L260 452 L290 390" fill="none" stroke={INK} strokeWidth={SW - 2} />
    <path d="M244 420 C252 432 268 432 276 420" fill="none" stroke={INK} strokeWidth={SW - 3} strokeLinecap="round" />
    {/* 襟（左前） */}
    <path d="M230 390 C236 440 262 512 316 600 L344 600 C300 520 276 450 268 410" fill={BODY} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
    <path d="M290 390 C284 420 274 446 266 462" fill="none" stroke={INK} strokeWidth={SW} strokeLinecap="round" />
    {/* 黒帯 */}
    <path d="M86 596 C200 584 320 584 434 596 L436 640 L84 640 Z" fill="#000" stroke={INK} strokeWidth={SW} />
    {/* 破れた袖口 */}
    <path d="M118 470 L132 488 L142 470 L156 492 L166 474 M402 470 L388 488 L378 470 L364 492 L354 474" fill="none" stroke={INK} strokeWidth={SW - 2} strokeLinecap="round" strokeLinejoin="round" />
  </g>
);

/** 腕。表情（ポーズ）ごとに形を変える。frame は気合のポーズで揺らすため */
const Arms: React.FC<{ pose: Pose; frame: number }> = ({ pose, frame }) => {
  const shake = pose === 'fist' ? Math.sin(frame * 1.7) * 2 : 0;
  switch (pose) {
    case 'arms': // 腕組み
      return (
        <g>
          <Limb x1={128} y1={500} x2={352} y2={548} w={62} />
          <Fist x={360} y={548} r={30} rot={-10} />
          <Limb x1={392} y1={500} x2={168} y2={556} w={62} />
          <Fist x={160} y={556} r={30} rot={10} />
        </g>
      );
    case 'point': // 画面（左上）を指さす
      return (
        <g>
          <Limb x1={126} y1={470} x2={70} y2={360} w={64} />
          <Limb x1={70} y1={360} x2={30} y2={250} w={56} />
          <PointHand x={26} y={238} rot={-112} />
          <Limb x1={392} y1={480} x2={410} y2={640} w={64} />
        </g>
      );
    case 'talk': // 手のひらを見せて語る
      return (
        <g>
          <Limb x1={128} y1={480} x2={150} y2={600} w={64} />
          <Limb x1={150} y1={600} x2={106} y2={470} w={56} />
          <Palm x={100} y={448} rot={-12} />
          <Limb x1={392} y1={480} x2={410} y2={640} w={64} />
        </g>
      );
    case 'surprised': // 両手を上げて驚く
      return (
        <g>
          <Limb x1={126} y1={470} x2={84} y2={360} w={60} />
          <Palm x={82} y={330} rot={-18} />
          <Limb x1={394} y1={470} x2={436} y2={360} w={60} />
          <Palm x={438} y={330} rot={18} />
        </g>
      );
    case 'fist': // 拳を突き上げる
      return (
        <g transform={`translate(${shake} 0)`}>
          <Limb x1={128} y1={480} x2={110} y2={640} w={64} />
          <Limb x1={394} y1={470} x2={450} y2={330} w={64} />
          <Limb x1={450} y1={330} x2={446} y2={196} w={58} />
          <Fist x={446} y={170} r={38} rot={-4} />
          {/* 気合の線 */}
          <path d="M400 120 L380 90 M446 104 L446 70 M492 120 L512 90" stroke="#ffd166" strokeWidth={7} strokeLinecap="round" />
        </g>
      );
    default: // 構えずに立つ
      return (
        <g>
          <Limb x1={128} y1={480} x2={108} y2={640} w={64} />
          <Limb x1={392} y1={480} x2={412} y2={640} w={64} />
        </g>
      );
  }
};

export const Character: React.FC<{ pose: Pose; frame: number; amp: number }> = ({ pose, frame, amp }) => {
  const breathe = Math.sin(frame / 18) * 3;
  // 腕を手前に描くポーズ（腕組み・語り）は胴の上に、上げるポーズは頭より後ろに描く
  const armsFront = pose === 'arms' || pose === 'talk';
  return (
    <svg viewBox="-20 60 560 580" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' }}>
      <g transform={`translate(0 ${breathe})`} strokeLinecap="round">
        <g transform={boil(frame, 'torso')}><Torso /></g>
        {!armsFront && <g transform={boil(frame, 'arms')}><Arms pose={pose} frame={frame} /></g>}
        <g transform={`${boil(frame, 'head')} rotate(${Math.sin(frame / 24) * 1.5} 260 300)`}>
          <MasterHead face={faceFor(pose)} amp={amp} frame={frame} />
        </g>
        {armsFront && <g transform={boil(frame, 'arms')}><Arms pose={pose} frame={frame} /></g>}
      </g>
    </svg>
  );
};
