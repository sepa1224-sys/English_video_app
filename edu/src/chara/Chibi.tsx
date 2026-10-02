import React from 'react';
import { random } from 'remotion';
import { HAND } from '../fonts';

// 気合イングリッシュのキャラクター（ちびキャラ・ゆるかわ解説の絵柄）。
// 2頭身、やわらかい茶色の線、パステルの塗り。マスターは「黒い道着＋ピンクの『気合』鉢巻」の空手家。
// 白い道着・赤い鉢巻・破れた袖は特定のゲームキャラと重なるので使わない。
//
// 解説動画（このプロジェクト）と気合LINEのショート（~/kiai-line-shorts）で共通に使う。
// 使い方は今までの Character と同じ: <Character pose frame amp />（amp は口の開き 0〜1）

export type Pose = 'idle' | 'talk' | 'point' | 'surprised' | 'fist' | 'arms';
export type Face = 'calm' | 'stern' | 'surprised' | 'shout' | 'smile';

export const LINE = '#4a3530'; // 線（こげ茶）
export const SKIN = '#ffe2cc';
export const CHEEK = '#ffb0b0';
export const GI = '#2f2f3d'; // 道着（黒に近い紺）
export const GI_LIGHT = '#4a4a5c';
export const BAND = '#ff7b9c'; // 鉢巻（ブランドのピンク）
export const HAIR = '#3a2a24';
const W = 7; // 線の太さ

/** ほんの少しの線のゆらぎ（手描き感）。4コマごと */
const wobble = (frame: number, key: string, a = 0.9) => {
  const s = Math.floor(frame / 4);
  return `translate(${(random(`${key}x${s}`) - 0.5) * a * 2} ${(random(`${key}y${s}`) - 0.5) * a * 2})`;
};

/** まばたき。だいたい3秒に1回、4コマだけ閉じる */
export const blinking = (frame: number, seed = 'b') => {
  const cycle = 84 + Math.floor(random(`${seed}${Math.floor(frame / 90)}`) * 30);
  return frame % cycle < 4;
};

const faceFor = (pose: Pose): Face =>
  pose === 'surprised' ? 'surprised' : pose === 'fist' ? 'shout' : pose === 'arms' ? 'stern' : pose === 'point' ? 'stern' : 'calm';

/** 目。顔の向きで描き分ける */
export const Eyes: React.FC<{ face: Face; frame: number; cx?: number; cy?: number; gap?: number; seed?: string }> =
  ({ face, frame, cx = 200, cy = 196, gap = 46, seed = 'm' }) => {
    const L = cx - gap, R = cx + gap;
    if (face === 'smile' || blinking(frame, seed)) {
      return <path d={`M${L - 12} ${cy + 2} Q${L} ${cy - 10} ${L + 12} ${cy + 2} M${R - 12} ${cy + 2} Q${R} ${cy - 10} ${R + 12} ${cy + 2}`}
        fill="none" stroke={LINE} strokeWidth={W} strokeLinecap="round" />;
    }
    if (face === 'surprised') {
      return (
        <g>
          {[L, R].map((x) => (
            <g key={x}><circle cx={x} cy={cy} r={15} fill="#fff" stroke={LINE} strokeWidth={W - 2} /><circle cx={x} cy={cy + 1} r={6} fill={LINE} /></g>
          ))}
        </g>
      );
    }
    const ry = face === 'shout' ? 9 : 13;
    return (
      <g>
        {[L, R].map((x) => (
          <g key={x}>
            <ellipse cx={x} cy={cy} rx={9} ry={ry} fill={LINE} />
            <circle cx={x + 3} cy={cy - 5} r={3.5} fill="#fff" />
          </g>
        ))}
        {/* きりっとした目は、上まぶたを一本 */}
        {face === 'stern' && <path d={`M${L - 14} ${cy - 12} L${L + 12} ${cy - 8} M${R + 14} ${cy - 12} L${R - 12} ${cy - 8}`} stroke={LINE} strokeWidth={W - 2} strokeLinecap="round" />}
      </g>
    );
  };

/** 口。amp（声の大きさ）で開く */
export const Mouth: React.FC<{ face: Face; amp: number; cx?: number; cy?: number }> = ({ face, amp, cx = 200, cy = 240 }) => {
  const open = face === 'shout' ? Math.max(0.7, amp) : amp;
  if (open > 0.1) {
    const h = 6 + open * 22, w = 14 + open * 8;
    return (
      <g>
        <path d={`M${cx - w} ${cy - 2} Q${cx} ${cy - 6} ${cx + w} ${cy - 2} Q${cx + w * 0.8} ${cy + h} ${cx} ${cy + h} Q${cx - w * 0.8} ${cy + h} ${cx - w} ${cy - 2} Z`}
          fill="#8a3b3b" stroke={LINE} strokeWidth={W - 2} strokeLinejoin="round" />
        <path d={`M${cx - w * 0.5} ${cy + h * 0.75} Q${cx} ${cy + h * 0.45} ${cx + w * 0.5} ${cy + h * 0.75}`} fill="#ff8f9c" />
      </g>
    );
  }
  if (face === 'smile' || face === 'calm') {
    return <path d={`M${cx - 12} ${cy} Q${cx} ${cy + 10} ${cx + 12} ${cy}`} fill="none" stroke={LINE} strokeWidth={W - 1} strokeLinecap="round" />;
  }
  if (face === 'surprised') return <ellipse cx={cx} cy={cy + 4} rx={8} ry={10} fill="#8a3b3b" stroke={LINE} strokeWidth={W - 2} />;
  return <path d={`M${cx - 12} ${cy + 3} L${cx + 12} ${cy + 3}`} stroke={LINE} strokeWidth={W - 1} strokeLinecap="round" />;
};

export const Cheeks: React.FC<{ cx?: number; cy?: number; gap?: number; strong?: boolean }> = ({ cx = 200, cy = 226, gap = 74, strong }) => (
  <g opacity={strong ? 0.95 : 0.7}>
    <ellipse cx={cx - gap} cy={cy} rx={17} ry={10} fill={CHEEK} />
    <ellipse cx={cx + gap} cy={cy} rx={17} ry={10} fill={CHEEK} />
  </g>
);

/** マスターの頭。髪・鉢巻・顔。頭の中心はおよそ (200, 185) */
export const MasterHead: React.FC<{ face: Face; amp: number; frame: number }> = ({ face, amp, frame }) => {
  const t = frame / 30;
  const wave = (k: number) => Math.sin(t * 5 + k) * 8;
  const browY = face === 'surprised' ? -10 : 0;
  const browTilt = face === 'stern' || face === 'shout' ? 8 : face === 'smile' ? -3 : 3;
  return (
    <g strokeLinejoin="round" strokeLinecap="round">
      {/* 鉢巻のたなびく端（頭の後ろ） */}
      <path d={`M300 128 C330 ${118 + wave(0)} 352 ${100 + wave(1)} 380 ${110 + wave(2)} L374 ${126 + wave(2)} C350 ${120 + wave(1)} 330 ${138 + wave(0)} 304 146 Z`} fill={BAND} stroke={LINE} strokeWidth={W - 2} />
      <path d={`M302 142 C334 ${152 + wave(1)} 356 ${150 + wave(2)} 372 ${172 + wave(3)} L360 ${180 + wave(3)} C344 ${164 + wave(2)} 328 ${166 + wave(1)} 300 158 Z`} fill={BAND} stroke={LINE} strokeWidth={W - 2} />
      {/* 髪（後ろ）。つんつんの房は頭の輪郭より外へ突き出す */}
      <path d="M84 172 L60 126 L94 130 L76 78 L122 102 L128 40 L168 86 L198 22 L226 84 L264 36 L272 98 L318 68 L306 128 L342 120 L316 172 Z" fill={HAIR} stroke={LINE} strokeWidth={W} />
      {/* 顔 */}
      <path d="M90 168 C88 248 130 290 200 290 C270 290 312 248 310 168 C310 120 270 96 200 96 C130 96 90 120 90 168 Z" fill={SKIN} stroke={LINE} strokeWidth={W} />
      {/* 生え際（鉢巻の上は髪） */}
      <path d="M90 156 C92 112 140 92 200 92 C260 92 308 112 310 156 Z" fill={HAIR} stroke={LINE} strokeWidth={W} />
      <path d="M150 104 L160 124 M200 98 L200 120 M250 104 L240 124" stroke="#5a463e" strokeWidth={4} strokeLinecap="round" />
      {/* 鉢巻 */}
      <path d="M86 138 C150 120 250 120 314 138 L312 166 C250 148 150 148 88 166 Z" fill={BAND} stroke={LINE} strokeWidth={W - 1} />
      <text x={200} y={160} textAnchor="middle" fontSize={27} fontWeight={800} fill="#fff" style={{ fontFamily: HAND }}>気合</text>
      {/* 太眉 */}
      <g transform={`translate(0 ${browY})`} fill={LINE}>
        <path d={`M128 ${176 - browTilt} Q148 ${168 - browTilt} 170 ${176 + browTilt} L168 ${184 + browTilt} Q148 ${178 - browTilt} 130 ${184 - browTilt} Z`} />
        <path d={`M272 ${176 - browTilt} Q252 ${168 - browTilt} 230 ${176 + browTilt} L232 ${184 + browTilt} Q252 ${178 - browTilt} 270 ${184 - browTilt} Z`} />
      </g>
      <Eyes face={face} frame={frame} cx={200} cy={210} gap={50} seed="master" />
      <Cheeks cx={200} cy={240} gap={76} />
      <Mouth face={face} amp={amp} cx={200} cy={258} />
      {face === 'surprised' && <path d="M318 196 C312 212 324 222 330 210 C334 202 324 196 318 196 Z" fill="#9fdcff" stroke={LINE} strokeWidth={3} />}
      {face === 'shout' && <path d="M60 110 L78 124 M48 150 L72 152 M340 84 L326 102" stroke="#ffb54d" strokeWidth={6} strokeLinecap="round" />}
    </g>
  );
};

/** まるい手（ミトン） */
const Hand: React.FC<{ x: number; y: number; r?: number; fist?: boolean; point?: number }> = ({ x, y, r = 22, fist, point }) => (
  <g>
    {point != null && (
      <rect x={x - 6} y={y - r - 26} width={13} height={30} rx={6.5} fill={SKIN} stroke={LINE} strokeWidth={W - 2}
        transform={`rotate(${point} ${x} ${y})`} />
    )}
    <circle cx={x} cy={y} r={r} fill={SKIN} stroke={LINE} strokeWidth={W - 1} />
    {fist && <path d={`M${x - 10} ${y - 6} L${x - 10} ${y + 4} M${x} ${y - 8} L${x} ${y + 4} M${x + 10} ${y - 6} L${x + 10} ${y + 4}`} stroke={LINE} strokeWidth={3} strokeLinecap="round" />}
  </g>
);

/** 腕（道着の袖）。肩 → 手まで太い線で */
const Sleeve: React.FC<{ x1: number; y1: number; x2: number; y2: number }> = ({ x1, y1, x2, y2 }) => (
  <g strokeLinecap="round">
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={LINE} strokeWidth={46} />
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={GI} strokeWidth={34} />
  </g>
);

const Arms: React.FC<{ pose: Pose; frame: number }> = ({ pose, frame }) => {
  const shake = pose === 'fist' ? Math.sin(frame * 1.6) * 3 : 0;
  const wave = pose === 'talk' ? Math.sin(frame / 7) * 6 : 0;
  const Ls = { x: 138, y: 322 }, Rs = { x: 262, y: 322 };
  switch (pose) {
    case 'talk': // 片手を広げて語る
      return <g><Sleeve x1={Ls.x} y1={Ls.y} x2={112} y2={392} /><Hand x={110} y={398} />
        <Sleeve x1={Rs.x} y1={Rs.y} x2={322} y2={300 + wave} /><Hand x={330} y={292 + wave} /></g>;
    case 'point': // 上を指す
      return <g><Sleeve x1={Ls.x} y1={Ls.y} x2={112} y2={392} /><Hand x={110} y={398} />
        <Sleeve x1={Rs.x} y1={Rs.y} x2={330} y2={250} /><Hand x={336} y={240} point={20} /></g>;
    case 'surprised': // 両手をあげる
      return <g><Sleeve x1={Ls.x} y1={Ls.y} x2={70} y2={262} /><Hand x={64} y={252} />
        <Sleeve x1={Rs.x} y1={Rs.y} x2={330} y2={262} /><Hand x={336} y={252} /></g>;
    case 'fist': // こぶしを突き上げる
      return <g transform={`translate(${shake} 0)`}><Sleeve x1={Ls.x} y1={Ls.y} x2={112} y2={392} /><Hand x={110} y={398} />
        <Sleeve x1={Rs.x} y1={Rs.y} x2={318} y2={230} /><Hand x={322} y={218} r={26} fist />
        <path d="M290 172 L280 150 M322 162 L322 138 M354 172 L364 150" stroke="#ffb54d" strokeWidth={6} strokeLinecap="round" /></g>;
    case 'arms': // 腕組み
      return <g><Sleeve x1={Ls.x} y1={Ls.y} x2={240} y2={368} /><Sleeve x1={Rs.x} y1={Rs.y} x2={160} y2={372} />
        <Hand x={246} y={366} r={19} /><Hand x={154} y={370} r={19} /></g>;
    default:
      return <g><Sleeve x1={Ls.x} y1={Ls.y} x2={112} y2={392} /><Hand x={110} y={398} />
        <Sleeve x1={Rs.x} y1={Rs.y} x2={288} y2={392} /><Hand x={290} y={398} /></g>;
  }
};

/** 胴（道着）と足 */
const Body: React.FC = () => (
  <g strokeLinejoin="round" strokeLinecap="round">
    {/* 足 */}
    <rect x={150} y={420} width={40} height={42} rx={16} fill={GI} stroke={LINE} strokeWidth={W} />
    <rect x={210} y={420} width={40} height={42} rx={16} fill={GI} stroke={LINE} strokeWidth={W} />
    <ellipse cx={164} cy={466} rx={24} ry={12} fill={SKIN} stroke={LINE} strokeWidth={W - 1} />
    <ellipse cx={236} cy={466} rx={24} ry={12} fill={SKIN} stroke={LINE} strokeWidth={W - 1} />
    {/* 胴 */}
    <path d="M128 312 C128 290 160 282 200 282 C240 282 272 290 272 312 L282 420 C282 432 270 436 200 436 C130 436 118 432 118 420 Z" fill={GI} stroke={LINE} strokeWidth={W} />
    {/* 襟（合わせ）。道着らしさは、この白い線で */}
    <path d="M172 286 L200 346 L228 286" fill="none" stroke="#e9e4dc" strokeWidth={9} />
    <path d="M178 290 L200 336 L222 290 Z" fill={SKIN} />
    <path d="M200 346 L236 404" stroke={GI_LIGHT} strokeWidth={5} />
    {/* 黒帯と結び目 */}
    <path d="M120 386 C160 378 240 378 280 386 L281 406 C240 398 160 398 119 406 Z" fill="#111" stroke={LINE} strokeWidth={W - 2} />
    <path d="M196 394 L180 428 M204 394 L222 426" stroke="#111" strokeWidth={10} />
    <circle cx={200} cy={394} r={9} fill="#111" stroke={LINE} strokeWidth={3} />
  </g>
);

export const Character: React.FC<{ pose: Pose; frame: number; amp: number }> = ({ pose, frame, amp }) => {
  const bob = Math.sin(frame / 14) * 4; // 呼吸でぽよぽよ
  const talkHop = amp > 0.15 ? -Math.abs(Math.sin(frame / 3)) * 3 : 0;
  const armsFront = pose === 'arms';
  return (
    <svg viewBox="20 30 360 450" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' }}>
      {/* 足元の影 */}
      <ellipse cx={200} cy={474} rx={110} ry={14} fill="rgba(74,53,48,0.15)" />
      <g transform={`translate(0 ${bob + talkHop})`}>
        <g transform={wobble(frame, 'body')}><Body /></g>
        {!armsFront && <g transform={wobble(frame, 'arms')}><Arms pose={pose} frame={frame} /></g>}
        <g transform={`${wobble(frame, 'head')} rotate(${Math.sin(frame / 22) * 2} 200 280)`}>
          <MasterHead face={faceFor(pose)} amp={amp} frame={frame} />
        </g>
        {armsFront && <g transform={wobble(frame, 'arms')}><Arms pose={pose} frame={frame} /></g>}
      </g>
    </svg>
  );
};
