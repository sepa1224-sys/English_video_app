import React, { createContext, useContext } from 'react';
import { PixelSprite } from './PixelSprite';

// マスター（ドット絵版）。16ビット機の格闘ゲーム風、約3頭身。
// 見た目（道着の色・髪型・鉢巻・ひげ・目）は LOOKS で切り替える。
// 特定のゲームキャラと重なる組み合わせ（白い道着＋赤い鉢巻＋破れた袖＋グローブ）は使わない。
// ベクターで描いて PixelSprite でドット化する。光は左上から。

export type Pose = 'idle' | 'talk' | 'point' | 'surprised' | 'fist' | 'arms';
export type Face = 'calm' | 'stern' | 'surprised' | 'shout' | 'smile';

const BASE = {
  ol: '#140c0a',
  skin: '#f2b98f', skinS: '#c98559', skinH: '#ffdcbc',
  hair: '#2a1c17', hairH: '#5a3d31',
  gi: '#2c2c44', giS: '#191929', giH: '#4a4a6e',
  lapel: '#e6dfd2', lapelS: '#a99f90',
  belt: '#0f0f12', beltH: '#3d3d46',
  band: '#ff4f7b', bandS: '#b8264f',
  white: '#ffffff', iris: '#2f6fd6', irisD: '#163f8c',
  mouth: '#5a1414', tongue: '#ff6f86',
  wrap: '#efe9dc', wrapS: '#b9ae9c',
  sweat: '#7fd0ff', spark: '#ffcf3a',
};
export type Look = typeof BASE & { hairStyle: 'spiky' | 'short' | 'messy'; headband: boolean; beard: boolean };

// 見た目の候補。どれにするかは坂本さんが選ぶ
export const LOOKS: Record<string, Look> = {
  // A 道場の師範：白い道着、鉢巻なし、短い黒髪にあごひげ、黒い瞳
  sensei: { ...BASE, gi: '#f1ede4', giS: '#bdb5a6', giH: '#ffffff', lapel: '#f8f6f1', lapelS: '#a59c8c',
    hair: '#1e1a1a', hairH: '#555050', iris: '#3a2418', irisD: '#1c100a', hairStyle: 'short', headband: false, beard: true },
  // B 若き武道家：白い道着に紺の鉢巻、ぼさぼさの茶髪
  young: { ...BASE, gi: '#f1ede4', giS: '#bdb5a6', giH: '#ffffff', lapel: '#f8f6f1', lapelS: '#a59c8c',
    hair: '#5a3620', hairH: '#8a5a36', band: '#2f4fa8', bandS: '#1c2f6b', iris: '#3a2418', irisD: '#1c100a',
    hairStyle: 'messy', headband: true, beard: false },
  // C 藍の拳士：藍染めの道着にオレンジの鉢巻、短い黒髪
  indigo: { ...BASE, gi: '#2f4478', giS: '#1d2b52', giH: '#4c64a6', band: '#ff8a1f', bandS: '#b85a0c',
    hairStyle: 'short', headband: true, beard: false },
};
const LookCtx = createContext<Look>(LOOKS.sensei);
const C = BASE; // 縁取りなど、見た目で変わらない色
const paletteOf = (l: Look) => Object.values(l).filter((v): v is string => typeof v === 'string' && v.startsWith('#'));

const ln = { stroke: C.ol, strokeWidth: 6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };

const faceFor = (pose: Pose): Face =>
  pose === 'surprised' ? 'surprised' : pose === 'fist' ? 'shout' : pose === 'arms' || pose === 'point' ? 'stern' : 'calm';

/* ───── 頭 ───── */
const Head: React.FC<{ face: Face; amp: number; blink: boolean; t: number }> = ({ face, amp, blink, t }) => {
  const C = useContext(LookCtx);
  const flap = Math.round(Math.sin(t * 6) * 2) * 5; // 鉢巻の端（1ドット単位で揺らす）
  const open = face === 'shout' ? Math.max(0.7, amp) : amp;
  const browUp = face === 'surprised' ? -10 : 0;
  const angry = face === 'stern' || face === 'shout';
  return (
    <g>
      {/* 鉢巻の端 */}
      {C.headband && <>
        <path d={`M262 112 L318 ${96 + flap} L326 ${112 + flap} L268 126 Z`} fill={C.band} />
        <path d={`M264 124 L312 ${142 - flap} L304 ${154 - flap} L262 134 Z`} fill={C.bandS} />
      </>}
      {/* 後ろ髪 */}
      {C.hairStyle === 'spiky' && <>
        <path d="M128 134 L104 104 L130 100 L114 58 L152 76 L158 30 L190 64 L206 18 L224 62 L254 28 L258 76 L292 58 L276 100 L300 106 L272 134 Z" fill={C.hair} />
        <path d="M158 30 L170 62 M206 18 L210 56 M254 28 L244 64" stroke={C.hairH} strokeWidth={8} />
      </>}
      {C.hairStyle === 'short' && <>
        <path d="M126 140 C118 70 154 40 200 40 C246 40 282 70 274 140 Z" fill={C.hair} />
        <path d="M160 56 C176 46 196 44 214 48" stroke={C.hairH} strokeWidth={8} fill="none" />
      </>}
      {C.hairStyle === 'messy' && <>
        <path d="M124 150 L100 126 L122 116 L104 80 L140 84 L138 44 L176 62 L196 26 L222 58 L252 34 L262 70 L298 64 L284 102 L308 118 L280 132 L276 150 Z" fill={C.hair} />
        <path d="M138 44 L156 74 M196 26 L204 60 M252 34 L242 66 M298 64 L270 88" stroke={C.hairH} strokeWidth={8} />
      </>}
      {/* 耳 */}
      <ellipse cx={134} cy={164} rx={13} ry={19} fill={C.skin} />
      <ellipse cx={266} cy={164} rx={13} ry={19} fill={C.skinS} />
      {/* 顔（あごは少し角ばらせる） */}
      <path d="M136 120 C136 82 164 66 200 66 C236 66 264 82 264 120 L262 174 C258 208 232 230 200 232 C168 230 142 208 138 174 Z" fill={C.skin} />
      {/* 右側の影 */}
      <path d="M238 80 C258 92 264 118 262 174 C258 208 232 230 204 232 C228 212 244 188 246 160 C248 128 246 100 238 80 Z" fill={C.skinS} />
      <path d="M150 140 C148 120 152 104 160 96" stroke={C.skinH} strokeWidth={8} fill="none" />
      {/* 生え際の髪 */}
      <path d="M134 126 C130 80 160 56 200 56 C240 56 270 80 266 126 C240 112 160 112 134 126 Z" fill={C.hair} />
      {/* もみあげ（耳の前まで髪を下ろす。無いと坊主頭に見える） */}
      <path d="M132 126 L132 170 L146 178 L150 128 Z" fill={C.hair} />
      <path d="M268 126 L268 170 L254 178 L250 128 Z" fill={C.hair} />
      {/* 鉢巻。無い見た目では、額に前髪を少し下ろす */}
      {C.headband ? <>
        <path d="M130 112 C170 100 230 100 270 112 L270 132 C230 120 170 120 130 132 Z" fill={C.band} />
        <path d="M130 126 C170 114 230 114 270 126 L270 132 C230 120 170 120 130 132 Z" fill={C.bandS} />
      </> : C.hairStyle === 'messy'
        ? <path d="M134 126 L150 150 L162 124 L182 146 L194 120 L214 144 L226 120 L244 142 L254 120 L266 130 L266 112 L134 112 Z" fill={C.hair} />
        : <path d="M134 130 C150 112 176 106 200 108 C186 116 178 126 176 136 C200 118 236 112 266 130 L266 112 L134 112 Z" fill={C.hair} />}
      {/* 太眉 */}
      <g transform={`translate(0 ${browUp})`} fill={C.hair}>
        <path d={angry ? 'M156 140 L192 150 L190 160 L154 150 Z' : 'M154 144 L192 146 L192 156 L154 154 Z'} />
        <path d={angry ? 'M244 140 L208 150 L210 160 L246 150 Z' : 'M246 144 L208 146 L208 156 L246 154 Z'} />
      </g>
      {/* 目 */}
      {blink || face === 'smile'
        ? <path d="M160 170 L190 170 M210 170 L240 170" stroke={C.ol} strokeWidth={7} />
        : face === 'surprised'
          ? <g>{[176, 224].map((x) => <g key={x}><ellipse cx={x} cy={170} rx={15} ry={18} fill={C.white} {...ln} /><rect x={x - 4} y={166} width={9} height={10} fill={C.ol} /></g>)}</g>
          : <g>{[176, 224].map((x) => (
            <g key={x}>
              <ellipse cx={x} cy={170} rx={13} ry={angry ? 13 : 17} fill={C.white} {...ln} />
              <ellipse cx={x + (x < 200 ? 4 : -4)} cy={172} rx={7} ry={angry ? 9 : 11} fill={C.iris} />
              <rect x={x + (x < 200 ? 1 : -7)} y={170} width={7} height={8} fill={C.irisD} />
              <rect x={x + (x < 200 ? 3 : -5)} y={162} width={5} height={5} fill={C.white} />
            </g>
          ))}</g>}
      {/* 鼻 */}
      <path d="M204 176 C214 186 214 196 200 198 L194 196" fill={C.skinS} stroke={C.skinS} strokeWidth={4} />
      {/* 口 */}
      {open > 0.12
        ? <g>
            <path d={`M176 208 Q200 204 224 208 Q220 ${214 + open * 18} 200 ${216 + open * 18} Q180 ${214 + open * 18} 176 208 Z`} fill={C.mouth} {...ln} strokeWidth={5} />
            <rect x={182} y={208} width={36} height={6} fill={C.white} />
            <path d={`M188 ${212 + open * 14} Q200 ${206 + open * 12} 212 ${212 + open * 14}`} fill={C.tongue} />
          </g>
        : face === 'calm'
          ? <path d="M180 210 Q202 220 222 206" fill="none" {...ln} strokeWidth={5} />
          : <path d="M182 212 L218 212" {...ln} strokeWidth={5} />}
      {/* あごひげ（口ひげは付けない。口の動きが見えなくなるので） */}
      {C.beard && <path d="M170 220 Q200 252 230 220 L234 232 Q200 268 166 232 Z" fill={C.hair} />}
      {face === 'surprised' && <path d="M276 150 C270 166 284 174 290 162 C294 154 284 150 276 150 Z" fill={C.sweat} />}
    </g>
  );
};

/* ───── 腕 ───── */
const Arm: React.FC<{ s: [number, number]; e: [number, number]; h: [number, number]; hand: 'fist' | 'open' | 'point'; flip?: boolean }> =
  ({ s, e, h, hand, flip }) => {
  const C = useContext(LookCtx);
  return (
    <g>
      {/* 袖（肩〜ひじ） */}
      {/* 前腕（たくましく）。袖より先に描いて、袖口を上にかぶせる */}
      <line x1={e[0]} y1={e[1]} x2={h[0]} y2={h[1]} stroke={C.ol} strokeWidth={42} strokeLinecap="round" />
      <line x1={e[0]} y1={e[1]} x2={h[0]} y2={h[1]} stroke={C.skin} strokeWidth={32} strokeLinecap="round" />
      <line x1={e[0]} y1={e[1]} x2={h[0]} y2={h[1]} stroke={C.skinS} strokeWidth={10} strokeLinecap="round" transform="translate(6 2)" />
      {/* 袖（肩〜ひじの少し先）と袖口 */}
      <line x1={s[0]} y1={s[1]} x2={e[0] + (h[0] - e[0]) * 0.25} y2={e[1] + (h[1] - e[1]) * 0.25} stroke={C.ol} strokeWidth={58} strokeLinecap="round" />
      <line x1={s[0]} y1={s[1]} x2={e[0] + (h[0] - e[0]) * 0.25} y2={e[1] + (h[1] - e[1]) * 0.25} stroke={C.gi} strokeWidth={48} strokeLinecap="round" />
      <circle cx={e[0] + (h[0] - e[0]) * 0.25} cy={e[1] + (h[1] - e[1]) * 0.25} r={22} fill={C.giH} />
      {/* 手首のテーピング */}
      <circle cx={(e[0] + h[0] * 2) / 3} cy={(e[1] + h[1] * 2) / 3} r={15} fill={C.wrap} />
      {/* 手 */}
      {hand === 'fist' && (
        <g>
          <rect x={h[0] - 24} y={h[1] - 22} width={48} height={42} rx={14} fill={C.skin} {...ln} />
          <path d={`M${h[0] - 14} ${h[1] - 18} L${h[0] - 14} ${h[1] - 4} M${h[0]} ${h[1] - 20} L${h[0]} ${h[1] - 4} M${h[0] + 14} ${h[1] - 18} L${h[0] + 14} ${h[1] - 4}`} stroke={C.skinS} strokeWidth={5} />
        </g>
      )}
      {hand === 'open' && (
        <g transform={`translate(${h[0]} ${h[1]}) scale(${flip ? -1 : 1} 1)`}>
          {[-16, -5, 6, 17].map((fx, i) => <rect key={i} x={fx - 5} y={-42 + Math.abs(fx) * 0.5} width={11} height={30} rx={5} fill={C.skin} {...ln} strokeWidth={4} />)}
          <rect x={-24} y={-20} width={48} height={38} rx={14} fill={C.skin} {...ln} />
          <rect x={-40} y={-8} width={22} height={12} rx={6} fill={C.skin} {...ln} strokeWidth={4} />
        </g>
      )}
      {hand === 'point' && (
        <g transform={`translate(${h[0]} ${h[1]})`}>
          <rect x={-6} y={-52} width={13} height={36} rx={6} fill={C.skin} {...ln} strokeWidth={4} />
          <rect x={-22} y={-22} width={44} height={40} rx={14} fill={C.skin} {...ln} />
        </g>
      )}
    </g>
  );
};

const Arms: React.FC<{ pose: Pose; t: number }> = ({ pose, t }) => {
  const C = useContext(LookCtx);
  const L: [number, number] = [118, 284], R: [number, number] = [282, 284];
  const wave = Math.round(Math.sin(t * 6)) * 5;
  switch (pose) {
    case 'talk':
      return <g><Arm s={L} e={[96, 352]} h={[104, 414]} hand="fist" /><Arm s={R} e={[318, 344]} h={[344, 292 + wave]} hand="open" flip /></g>;
    case 'point':
      return <g><Arm s={L} e={[96, 352]} h={[104, 414]} hand="fist" /><Arm s={R} e={[322, 218]} h={[334, 158]} hand="point" /></g>;
    case 'surprised':
      return <g><Arm s={L} e={[76, 236]} h={[70, 176]} hand="open" /><Arm s={R} e={[324, 236]} h={[330, 176]} hand="open" flip /></g>;
    case 'fist':
      return (
        <g>
          <Arm s={L} e={[100, 350]} h={[136, 392]} hand="fist" />
          <Arm s={R} e={[322, 214]} h={[316, 140]} hand="fist" />
          <path d={`M284 ${86 + wave} L276 ${66 + wave} M316 ${78 + wave} L316 ${54 + wave} M348 ${86 + wave} L358 ${66 + wave}`} stroke={C.spark} strokeWidth={8} strokeLinecap="square" />
        </g>
      );
    case 'arms':
      return <g><Arm s={L} e={[134, 352]} h={[244, 336]} hand="fist" /><Arm s={R} e={[266, 352]} h={[156, 340]} hand="fist" /></g>;
    default:
      return <g><Arm s={L} e={[96, 352]} h={[104, 414]} hand="fist" /><Arm s={R} e={[304, 352]} h={[296, 414]} hand="fist" /></g>;
  }
};

/* ───── 胴と脚 ───── */
const Body: React.FC = () => {
  const C = useContext(LookCtx);
  return (
  <g>
    {/* 首 */}
    <rect x={180} y={222} width={40} height={32} fill={C.skinS} />
    {/* 道着の上 */}
    <path d="M100 284 C106 258 154 246 200 246 C246 246 294 258 300 284 L278 396 L122 396 Z" fill={C.gi} />
    <path d="M252 252 C278 258 296 268 300 284 L278 396 L256 396 C266 350 266 300 252 252 Z" fill={C.giS} />
    <path d="M128 296 C130 330 134 360 138 390" stroke={C.giH} strokeWidth={10} fill="none" />
    {/* 胸元（はだけた道着からのぞく胸） */}
    <path d="M168 248 L200 330 L232 248 Z" fill={C.skin} />
    <path d="M200 300 L200 322 M180 286 Q190 296 200 290 Q210 296 220 286" stroke={C.skinS} strokeWidth={6} fill="none" />
    {/* 襟 */}
    <path d="M160 246 L200 336 L208 316 L172 244 Z" fill={C.lapel} />
    <path d="M240 246 L200 336 L192 316 L228 244 Z" fill={C.lapelS} />
    {/* 帯 */}
    <rect x={118} y={384} width={164} height={24} fill={C.belt} />
    <rect x={118} y={386} width={164} height={5} fill={C.beltH} />
    <rect x={190} y={388} width={22} height={30} fill={C.belt} />
    <path d="M196 418 L180 466 L194 468 L204 420 Z M206 418 L224 462 L236 456 L214 418 Z" fill={C.belt} />
    {/* 袴（ゆったりしたズボン） */}
    <path d="M122 406 L278 406 L304 500 L318 540 L216 540 L200 462 L184 540 L82 540 L96 500 Z" fill={C.gi} />
    <path d="M236 406 L278 406 L304 500 L318 540 L252 540 Z" fill={C.giS} />
    <path d="M200 420 L200 462" stroke={C.giS} strokeWidth={8} />
    <path d="M132 430 L104 520" stroke={C.giH} strokeWidth={10} />
    {/* 裾のしぼり */}
    <rect x={84} y={526} width={100} height={14} fill={C.giH} />
    <rect x={216} y={526} width={100} height={14} fill={C.giS} />
    {/* 裸足 */}
    <path d="M92 540 L172 540 L176 562 C150 572 104 572 82 562 Z" fill={C.skin} />
    <path d="M228 540 L308 540 L318 562 C296 572 250 572 224 562 Z" fill={C.skinS} />
  </g>
  );
};

/** ベクターのままのマスター（ドット化する前） */
export const FighterVector: React.FC<{ pose: Pose; amp: number; blink: boolean; t: number }> = ({ pose, amp, blink, t }) => {
  const front = pose === 'arms';
  return (
    <g>
      <Body />
      {!front && <Arms pose={pose} t={t} />}
      <g transform="translate(200 236) scale(1.2) translate(-200 -236)">
        <Head face={faceFor(pose)} amp={amp} blink={blink} t={t} />
      </g>
      {front && <Arms pose={pose} t={t} />}
    </g>
  );
};

/** まばたき。だいたい3秒に1回、4コマだけ閉じる */
const isBlink = (frame: number) => frame % 97 < 4;

/** 動画で使うマスター。1ドット = scale px。足元が箱の下端に来る */
export const Character: React.FC<{ pose: Pose; frame: number; amp: number; scale?: number; look?: string }> = ({ pose, frame, amp, scale = 4, look = 'sensei' }) => {
  const L = LOOKS[look] ?? LOOKS.sensei;
  const t = frame / 30;
  // 口は3段階（閉・半開き・開き）に丸める。中間の形が多いとドット絵らしくない
  const a = amp < 0.15 ? 0 : amp < 0.5 ? 0.4 : 1;
  // 呼吸は1ドット単位で上下
  const bob = Math.round((Math.sin(frame / 14) + 1) / 2) * scale;
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, display: 'flex', justifyContent: 'center', transform: `translateY(${bob}px)` }}>
      <PixelSprite viewBox="40 -44 320 624" w={80} h={156} scale={scale} palette={paletteOf(L)} outline={C.ol}>
        <LookCtx.Provider value={L}>
          <FighterVector pose={pose} amp={a} blink={isBlink(frame)} t={Math.floor(frame / 6) * 6 / 30} />
        </LookCtx.Provider>
      </PixelSprite>
    </div>
  );
};
