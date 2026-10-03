import React from 'react';
import {
  AbsoluteFill, Audio, Easing, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';

import { Sennin, Student, type SenninPose } from './chara/Sprites';
import { type Beat, type Episode as Ep, type Label, type Speaker, type Visual, FPS, TAIL, beatFrames } from './types';

// フォントは手元のファイルから（Google Fonts の日本語は分割が多く、書き出しが時間切れになる）
import { DOT } from './fonts';
// 画面の文字はすべてドット文字。太字は無い書体なので、太らせない（ドットがにじむ）


const PINK = '#ff6f91';
const NAVY = '#15132b'; // 背景（夜の道場）
const INK = '#ffffff'; // 文字
const YELLOW = '#ffcf3a';
const GREEN = '#6ee87a';
const RED = '#ff5a5a';
const CARD = '#0d0c22'; // ウィンドウの地
const SHADOW = '6px 6px 0 rgba(0,0,0,0.55)'; // ドット絵風の、ぼかさない影
// RPGの会話ウィンドウの枠（白い太枠＋内側の細い紫）
const WINDOW: React.CSSProperties = {
  background: CARD, border: '6px solid #f2efe6', borderRadius: 12,
  boxShadow: `inset 0 0 0 4px #5b57a6, ${SHADOW}`,
};
// 文字の縁取り（ゲームの文字のように、くっきりした黒い影）
const PIXEL_TEXT = '4px 4px 0 #000';

// 英文のかたまりの色。音読教材（SVO色分け）と同じ考え方
const LABEL_COLOR: Record<Label, string> = {
  S: '#6fb7ff', V: '#ff6f6f', O: '#6ee87a', C: '#ffbf4d', M: '#b9b6d6', '+': '#d29bff', '': INK,
};
const LABEL_NAME: Record<Label, string> = { S: '主語', V: '動詞', O: '目的語', C: '補語', M: '修飾', '+': 'つなぎ', '': '' };

const NAMES: Record<Speaker, string> = {
  master: '仙人', spartan: 'スパルタ師範代', ikemen: 'イケメン', tsundere: 'ツンデレ',
  osananajimi: '幼なじみ', megane: 'メガネ', nekketsu: '熱血',
};

/** 画面の向きで変わる配置 */
type Layout = {
  W: number; H: number; vertical: boolean;
  stage: { left: number; top: number; width: number; height: number }; // 解説の絵を置く場所
  caption: { left: number; top: number; width: number }; // 字幕
  master: { left: number; top: number; width: number; height: number };
  avatar: { left: number; top: number; size: number }; // 話している生徒の顔
};
const layoutFor = (W: number, H: number): Layout => (H > W
  ? { // 縦（ショート）。下3分の1はUIと重なるので、大事なものは上に寄せる
      W, H, vertical: true,
      stage: { left: 50, top: 260, width: W - 100, height: 760 },
      caption: { left: 50, top: 1030, width: W - 100 },
      // 字幕（最大3行）の下からキャラ。ショートの下端はタイトル等と重なるので足元が隠れる程度は許す
      master: { left: W - 560, top: H - 600, width: 560, height: 560 },
      avatar: { left: -10, top: H - 560, size: 520 },
    }
  : { // 横（長尺）
      W, H, vertical: false,
      stage: { left: 60, top: 150, width: 1300, height: 640 },
      caption: { left: 60, top: 830, width: 1300 },
      master: { left: W - 600, top: H - 620, width: 600, height: 600 },
      avatar: { left: 1360, top: 60, size: 440 },
    });

export const Episode: React.FC<{ episode: Ep }> = ({ episode }) => {
  const { width, height } = useVideoConfig();
  const L = layoutFor(width, height);
  const beats = episode.beats;
  let from = 0;
  const starts = beats.map((b) => { const s = from; from += beatFrames(b); return s; });
  // 画面（visual）は書いたビートから次に書くビートまで残す
  const visuals: (Visual | undefined)[] = [];
  let cur: Visual | undefined;
  beats.forEach((b, i) => { if (b.visual) cur = b.visual.kind === 'none' ? undefined : b.visual; visuals[i] = cur; });
  // 同じ絵が続く間は、出し直しのアニメを繰り返さない
  const visualStart = beats.map((b, i) => {
    let j = i;
    while (j > 0 && !beats[j].visual) j--;
    return starts[j];
  });

  return (
    <AbsoluteFill style={{ background: NAVY, fontFamily: DOT, color: INK }}>
      <Backdrop L={L} />
      <Header episode={episode} L={L} />
      {beats.map((b, i) => (
        <Sequence key={b.id} from={starts[i]} durationInFrames={beatFrames(b) + (i === beats.length - 1 ? Math.round(TAIL * FPS) : 0)}>
          {b.dur != null && <Audio src={staticFile(`ep/${episode.id}/${b.id}.mp3`)} />}
          {b.visual?.kind === 'quiz' && !b.visual.reveal && b.think ? (
            <Sequence from={Math.round(((b.dur ?? 0) + 0.3) * FPS)}>
              <Audio src={staticFile('se/tick.mp3')} volume={0.5} />
            </Sequence>
          ) : null}
        </Sequence>
      ))}
      <StageTrack beats={beats} starts={starts} visuals={visuals} visualStart={visualStart} L={L} />
      <MasterTrack beats={beats} starts={starts} L={L} />
      <SpeakerTrack beats={beats} starts={starts} L={L} />
    </AbsoluteFill>
  );
};

/** 今のビートの番号と、その中での経過コマ */
const useBeat = (starts: number[]) => {
  const f = useCurrentFrame();
  let i = 0;
  while (i + 1 < starts.length && starts[i + 1] <= f) i++;
  return { f, i, local: f - starts[i] };
};

// 星の位置は毎回同じになるよう、決まった式で散らす
const STARS = Array.from({ length: 70 }, (_, i) => ({
  x: (i * 7919) % 1000 / 1000, y: (i * 104729) % 1000 / 1000 * 0.75, s: 1 + (i % 3), tw: i % 7,
}));

const Backdrop: React.FC<{ L: Layout }> = ({ L }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ overflow: 'hidden', background: 'linear-gradient(#0e0c22, #241f4d 70%, #3a2a4a)' }}>
      {STARS.map((st, i) => (
        <div key={i} style={{ position: 'absolute', left: st.x * L.W, top: st.y * L.H, width: st.s * 4, height: st.s * 4,
          background: '#fff', opacity: 0.35 + 0.65 * (Math.floor((f + st.tw * 9) / 20) % 2) }} />
      ))}
      {/* 道場の床（板目） */}
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: L.H * 0.16,
        background: 'repeating-linear-gradient(90deg, #6b4a2f 0 120px, #5a3d27 120px 124px)', borderTop: '8px solid #2a1a10' }} />
      {/* 走査線（ブラウン管の横縞） */}
      <div style={{ position: 'absolute', inset: 0, opacity: 0.08,
        backgroundImage: 'repeating-linear-gradient(0deg, #000 0 2px, transparent 2px 6px)' }} />
    </AbsoluteFill>
  );
};

/** フィーバー：光線が回り、入った瞬間に画面がフラッシュする */
const FeverFX: React.FC<{ local: number; L: Layout }> = ({ local, L }) => {
  const flash = interpolate(local, [0, 8], [0.85, 0], { extrapolateRight: 'clamp' });
  const rot = local * 1.5;
  const cx = L.master.left + L.master.width / 2, cy = L.master.top + L.master.height * 0.45;
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <div style={{ position: 'absolute', left: cx - L.H, top: cy - L.H, width: L.H * 2, height: L.H * 2, opacity: 0.35,
        background: `repeating-conic-gradient(from ${rot}deg, ${YELLOW} 0deg 8deg, transparent 8deg 22deg)`,
        maskImage: 'radial-gradient(circle, #000 15%, transparent 65%)', WebkitMaskImage: 'radial-gradient(circle, #000 15%, transparent 65%)' }} />
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flash }} />
    </AbsoluteFill>
  );
};

const Header: React.FC<{ episode: Ep; L: Layout }> = ({ episode, L }) => (
  <div style={{ position: 'absolute', left: L.vertical ? 50 : 60, top: L.vertical ? 120 : 40, right: 50, display: 'flex', alignItems: 'center', gap: 20 }}>
    <div style={{ ...WINDOW, padding: '6px 22px', color: YELLOW, fontSize: L.vertical ? 40 : 34, fontWeight: 400, whiteSpace: 'nowrap', textShadow: PIXEL_TEXT }}>
      {episode.series ?? (episode.kind === 'grammar' ? '気合の文法' : '気合の英単語')}
    </div>
    <div style={{ fontSize: L.vertical ? 46 : 40, fontWeight: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textShadow: PIXEL_TEXT }}>{episode.title}</div>
  </div>
);

/* ───────── 解説の絵 ───────── */

const StageTrack: React.FC<{ beats: Beat[]; starts: number[]; visuals: (Visual | undefined)[]; visualStart: number[]; L: Layout }> =
  ({ beats, starts, visuals, visualStart, L }) => {
    const { f, i } = useBeat(starts);
    const v = visuals[i];
    if (!v) return null;
    const local = f - visualStart[i];
    const beat = beats[i];
    const s = L.stage;
    return (
      <div style={{ position: 'absolute', left: s.left, top: s.top, width: s.width, height: s.height,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Visualize v={v} local={local} beatLocal={f - starts[i]} beat={beat} L={L} />
      </div>
    );
  };

const pop = (frame: number, delay = 0, stiff = 170) =>
  spring({ frame: frame - delay, fps: FPS, config: { damping: 12, stiffness: stiff } });

const Visualize: React.FC<{ v: Visual; local: number; beatLocal: number; beat: Beat; L: Layout }> = ({ v, local, beatLocal, beat, L }) => {
  const k = pop(local);
  const big = L.vertical ? 1 : 0.9;
  switch (v.kind) {
    case 'title':
      return (
        <div style={{ textAlign: 'center', transform: `scale(${k}) rotate(${(1 - k) * -6}deg)` }}>
          <div style={{ fontSize: 120 * big, lineHeight: 1.15, fontWeight: 400, color: YELLOW, WebkitTextStroke: '14px #000', paintOrder: 'stroke fill', textShadow: `8px 8px 0 ${PINK}` }}>
            {v.text.split('\n').map((l, i) => <div key={i}>{l}</div>)}
          </div>
          {v.sub && <div style={{ marginTop: 30, fontSize: 52 * big, color: YELLOW }}>{v.sub}</div>}
        </div>
      );
    case 'word': {
      const letters = [...v.en];
      const jaK = pop(local, 14);
      return (
        <div style={{ textAlign: 'center' }}>
          {v.pos && <div style={{ display: 'inline-block', marginBottom: 20, padding: '6px 24px', borderRadius: 999, border: `4px solid ${YELLOW}`, color: YELLOW, fontSize: 44 * big, opacity: k }}>{v.pos}</div>}
          <div style={{ fontSize: Math.min(190, 1500 / Math.max(6, letters.length)) * big, fontWeight: 400, letterSpacing: 2, fontFamily: DOT }}>
            {letters.map((c, i) => {
              const p = pop(local, i * 2, 220);
              return <span key={i} style={{ display: 'inline-block', color: '#6fe3ff', transform: `translateY(${(1 - p) * -80}px) scale(${p})`,
                WebkitTextStroke: `12px #000`, paintOrder: 'stroke fill', textShadow: `8px 8px 0 #2b4bb8` }}>{c === ' ' ? ' ' : c}</span>;
            })}
          </div>
          <div style={{ marginTop: 30, fontSize: 86 * big, fontWeight: 400, opacity: jaK, transform: `translateY(${(1 - jaK) * 40}px)`, textShadow: PIXEL_TEXT }}>{v.ja}</div>
          {v.note && <div style={{ marginTop: 26, fontSize: 46 * big, color: '#c9c6e8', opacity: pop(local, 24), textShadow: PIXEL_TEXT }}>{v.note}</div>}
        </div>
      );
    }
    case 'image': {
      const t = local / FPS;
      return (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 340 * big, transform: `scale(${k}) rotate(${Math.sin(t * 3) * 6}deg) translateY(${Math.sin(t * 2.4) * 16}px)` }}>{v.emoji}</div>
          {v.label && <div style={{ fontSize: 64 * big, fontWeight: 400, marginTop: 10, opacity: pop(local, 10), textShadow: PIXEL_TEXT }}>{v.label}</div>}
        </div>
      );
    }
    case 'sentence':
      return <Sentence v={v} local={local} big={big} />;
    case 'wrong': {
      const stamp = pop(local, 12, 260);
      const right = pop(local, Math.round(FPS * 1.4));
      return (
        <div style={{ width: '100%', textAlign: 'center' }}>
          <div style={{ ...WINDOW, position: 'relative', display: 'inline-block', fontSize: 70 * big, fontWeight: 400, color: '#a6a3c4', fontFamily: DOT, padding: '10px 30px' }}>
            {v.wrong}
            <div style={{ position: 'absolute', left: 0, right: 0, top: '52%', height: 10, background: RED, transform: `scaleX(${stamp})`, transformOrigin: 'left' }} />
            <div style={{ position: 'absolute', right: -70, top: -90, fontSize: 200, color: RED, transform: `scale(${stamp * 1.0 + (1 - stamp) * 3}) rotate(-12deg)`, opacity: stamp }}>✕</div>
          </div>
          <div style={{ marginTop: 50, fontSize: 70 * big, fontWeight: 400, color: GREEN, fontFamily: DOT, opacity: right, transform: `scale(${0.7 + right * 0.3})`, textShadow: PIXEL_TEXT }}>
            ⭕ {v.right}
          </div>
          {v.why && <div style={{ marginTop: 30, fontSize: 48 * big, color: YELLOW, opacity: pop(local, Math.round(FPS * 2)), textShadow: PIXEL_TEXT }}>{v.why}</div>}
        </div>
      );
    }
    case 'compare': {
      const a = pop(local), b = pop(local, 10);
      const card = (x: { label: string; en: string; ja?: string }, p: number, from: number, color: string) => (
        <div style={{ ...WINDOW, flex: 1, padding: 34, border: `6px solid ${color}`,
          transform: `translateX(${(1 - p) * from}px)`, opacity: p, textAlign: 'center' }}>
          <div style={{ fontSize: 46 * big, color, fontWeight: 400 }}>{x.label}</div>
          <div style={{ marginTop: 16, fontSize: 58 * big, fontWeight: 400, fontFamily: DOT }}>{x.en}</div>
          {x.ja && <div style={{ marginTop: 12, fontSize: 40 * big, color: '#c9c6e8' }}>{x.ja}</div>}
        </div>
      );
      return (
        <div style={{ width: '100%', display: 'flex', flexDirection: L.vertical ? 'column' : 'row', gap: 34 }}>
          {card(v.a, a, -900, '#6fb7ff')}
          {card(v.b, b, 900, PINK)}
        </div>
      );
    }
    case 'rule':
      return (
        <div style={{ ...WINDOW, width: '100%', padding: '40px 50px', transform: `scale(${k})` }}>
          {v.title && <div style={{ fontFamily: DOT, fontSize: 70 * big, color: YELLOW, marginBottom: 20 }}>{v.title}</div>}
          {v.lines.map((l, i) => {
            const p = pop(local, 8 + i * 10);
            return <div key={i} style={{ fontFamily: DOT, fontSize: 60 * big, lineHeight: 1.5, opacity: p, transform: `translateX(${(1 - p) * -40}px)` }}>{l}</div>;
          })}
        </div>
      );
    case 'quiz':
      return <Quiz v={v} local={local} beatLocal={beatLocal} beat={beat} big={big} />;
    default:
      return null;
  }
};

const Sentence: React.FC<{ v: Extract<Visual, { kind: 'sentence' }>; local: number; big: number }> = ({ v, local, big }) => {
  const size = Math.max(54, Math.min(84, 2200 / Math.max(20, v.chunks.reduce((n, c) => n + c.w.length, 0)))) * big;
  const jaK = pop(local, v.chunks.length * 6 + 8);
  return (
    <div style={{ width: '100%', textAlign: 'center' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '18px 14px' }}>
        {v.chunks.map((c, i) => {
          const p = pop(local, i * 6, 200);
          const marked = v.mark?.includes(i);
          const ring = marked ? interpolate(local, [v.chunks.length * 6 + 12, v.chunks.length * 6 + 24], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0;
          const color = LABEL_COLOR[c.l] ?? '#fff';
          return (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', transform: `translateY(${(1 - p) * 60}px) scale(${p})` }}>
              <div style={{ position: 'relative', padding: '6px 18px', borderRadius: 8, background: CARD, border: `4px solid ${color}`, boxShadow: SHADOW,
                fontSize: size, fontWeight: 400, fontFamily: DOT, color }}>
                {c.w}
                {marked && (
                  <svg style={{ position: 'absolute', inset: -16, width: 'calc(100% + 32px)', height: 'calc(100% + 32px)', overflow: 'visible' }} viewBox="0 0 100 100" preserveAspectRatio="none">
                    <ellipse cx="50" cy="50" rx="49" ry="47" fill="none" stroke={YELLOW} strokeWidth={4} vectorEffect="non-scaling-stroke"
                      pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ring} style={{ strokeWidth: 8 }} />
                  </svg>
                )}
              </div>
              {c.l && <div style={{ marginTop: 6, fontSize: 30 * big, color, opacity: 0.9 }}>{c.l} {LABEL_NAME[c.l]}</div>}
            </div>
          );
        })}
      </div>
      {v.ja && <div style={{ marginTop: 40, fontSize: 54 * big, color: '#e6e3ff', opacity: jaK, textShadow: PIXEL_TEXT }}>{v.ja}</div>}
    </div>
  );
};

const Quiz: React.FC<{ v: Extract<Visual, { kind: 'quiz' }>; local: number; beatLocal: number; beat: Beat; big: number }> = ({ v, local, beatLocal, beat, big }) => {
  const thinkFrom = ((beat.dur ?? 0) + 0.3) * FPS;
  const thinkLen = (beat.think ?? 0) * FPS;
  const bar = !v.reveal && thinkLen ? interpolate(beatLocal, [thinkFrom, thinkFrom + thinkLen], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : null;
  return (
    <div style={{ width: '100%' }}>
      <div style={{ fontSize: 66 * big, fontWeight: 400, textAlign: 'center', marginBottom: 34, fontFamily: DOT, opacity: pop(local), textShadow: PIXEL_TEXT }}>{v.q}</div>
      <div style={{ display: 'grid', gridTemplateColumns: v.choices.length > 2 ? '1fr 1fr' : '1fr', gap: 24 }}>
        {v.choices.map((c, i) => {
          const p = pop(local, 6 + i * 5);
          const isAns = v.reveal && i === v.answer;
          const dim = v.reveal && i !== v.answer;
          const glow = isAns ? pop(beatLocal, 4, 220) : 0;
          return (
            <div key={i} style={{ ...WINDOW, padding: '22px 30px', fontSize: 56 * big, fontWeight: 400, fontFamily: DOT,
              background: isAns ? '#1f5a2a' : CARD, color: INK, borderColor: isAns ? GREEN : '#f2efe6',
              opacity: p * (dim ? 0.35 : 1), transform: `scale(${p * (1 + glow * 0.06)})` }}>
              <span style={{ color: isAns ? GREEN : YELLOW, marginRight: 16 }}>{isAns ? '▶' : ''}{'ABCD'[i]}</span>{c}
            </div>
          );
        })}
      </div>
      {bar != null && (
        <div style={{ marginTop: 40, height: 28, background: '#000', border: '4px solid #f2efe6' }}>
          <div style={{ width: `${bar * 100}%`, height: '100%', background: YELLOW }} />
        </div>
      )}
    </div>
  );
};

/* ───────── キャラ ───────── */

/** マスターは出しっぱなし。話しているときだけ口が動き、構えはビートごとに変わる */
const MasterTrack: React.FC<{ beats: Beat[]; starts: number[]; L: Layout }> = ({ beats, starts, L }) => {
  const { f, i, local } = useBeat(starts);
  const b = beats[i];
  const speaking = b.who === 'master';
  // 最後にマスターが取った構えを保つ（生徒が話している間も、急に姿勢を変えない）
  let pose: SenninPose = 'idle';
  for (let j = i; j >= 0; j--) if (beats[j].who === 'master') { pose = (beats[j].pose ?? 'talk') as SenninPose; break; }
  // フィーバー：台本で指定したビートと、クイズの答えを出すビート
  const fever = !!b.fever || (b.visual?.kind === 'quiz' && !!b.visual.reveal);
  // 口パクは2コマに1回だけ更新する（パカパカしすぎない）
  const amp = speaking ? (b.env?.[local - (local % 2)] ?? 0) : 0;
  const enter = spring({ frame: f, fps: FPS, config: { damping: 14, stiffness: 110 } });
  const posePop = speaking ? spring({ frame: local, fps: FPS, config: { damping: 8, stiffness: 220 } }) : 1;
  const rise = fever ? spring({ frame: local, fps: FPS, config: { damping: 12, stiffness: 90 } }) : 0;
  const float = fever ? Math.sin(local / 8) * 14 - rise * 90 : 0;
  const m = L.master;
  return (
    <>
      {fever && <FeverFX local={local} L={L} />}
      <div style={{ position: 'absolute', left: m.left, top: m.top, width: m.width, height: m.height,
        transform: `translateX(${(1 - enter) * 700}px) translateY(${float}px) scale(${(0.94 + posePop * 0.06) * (1 + rise * 0.12)})`,
        transformOrigin: 'bottom center', filter: speaking || fever ? 'none' : 'brightness(0.7)' }}>
        <Sennin pose={pose} fever={fever} amp={amp} size={m.width} />
      </div>
    </>
  );
};

/** 字幕と、話している生徒の顔 */
const SpeakerTrack: React.FC<{ beats: Beat[]; starts: number[]; L: Layout }> = ({ beats, starts, L }) => {
  const { i, local } = useBeat(starts);
  const b = beats[i];
  const isMaster = b.who === 'master';
  const amp = b.env?.[local] ?? 0;
  const enter = pop(local, 0, 200);
  const text = b.caption ?? (b.en ? `${b.line}\n${b.en}` : b.line);
  const c = L.caption;
  const a = L.avatar;
  return (
    <>
      {!isMaster && (
        <div style={{ position: 'absolute', left: a.left, top: a.top, width: a.size, height: a.size,
          transform: `translateX(${(1 - enter) * -500}px)` }}>
          <Student who={b.who} size={a.size} amp={b.env?.[local - (local % 2)] ?? 0} local={local} />
        </div>
      )}
      <div style={{ ...WINDOW, position: 'absolute', left: c.left, top: c.top, width: c.width, padding: '26px 34px 22px',
        opacity: Math.min(1, enter * 1.5) }}>
        {/* 話している人の名前の札 */}
        <div style={{ ...WINDOW, position: 'absolute', left: 24, top: -40, padding: '0 18px', fontSize: L.vertical ? 34 : 30, fontWeight: 400,
          color: isMaster ? YELLOW : '#6fe3ff', boxShadow: 'none' }}>{NAMES[b.who]}</div>
        {text.split('\n').map((l, k) => {
          const en = /^[\x00-\x7F’'"“”…—–]+$/.test(l.trim());
          return (
            <div key={k} style={{ fontSize: (L.vertical ? 52 : 46) * (en ? 1.05 : 1), lineHeight: 1.35, fontWeight: 400,
              fontFamily: DOT, color: en ? YELLOW : INK, textShadow: PIXEL_TEXT }}>{l}</div>
          );
        })}
      </div>
    </>
  );
};
