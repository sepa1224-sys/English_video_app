import React from 'react';
import {
  AbsoluteFill, Audio, Easing, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';

import { Character, type Pose } from './chara/Chibi';
import { PersonaFace } from './chara/Faces';
import { type Beat, type Episode as Ep, type Label, type Speaker, type Visual, FPS, TAIL, beatFrames } from './types';

// フォントは手元のファイルから（Google Fonts の日本語は分割が多く、書き出しが時間切れになる）
import { ROUNDED, HAND } from './fonts';


const PINK = '#ff7b9c';
const NAVY = '#fbf4ea'; // 背景（クリーム）。名前は旧デザインの名残
const INK = '#4a3530'; // 文字（こげ茶）
const YELLOW = '#f2a81d';
const GREEN = '#2fa866';
const RED = '#e0475b';
const CARD = '#ffffff';
const SHADOW = '0 10px 30px -12px rgba(74,53,48,0.35)';

// 英文のかたまりの色。音読教材（SVO色分け）と同じ考え方
const LABEL_COLOR: Record<Label, string> = {
  S: '#2f7fd8', V: '#e0475b', O: '#2fa866', C: '#e08a1e', M: '#8a8299', '+': '#9b5cc9', '': INK,
};
const LABEL_NAME: Record<Label, string> = { S: '主語', V: '動詞', O: '目的語', C: '補語', M: '修飾', '+': 'つなぎ', '': '' };

const NAMES: Record<Speaker, string> = {
  master: 'マスター', spartan: 'スパルタ先生', ikemen: 'イケメン', tsundere: 'ツンデレ',
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
      master: { left: W - 500, top: H - 590, width: 500, height: 540 },
      avatar: { left: 50, top: H - 540, size: 280 },
    }
  : { // 横（長尺）
      W, H, vertical: false,
      stage: { left: 60, top: 150, width: 1300, height: 640 },
      caption: { left: 60, top: 830, width: 1300 },
      master: { left: W - 560, top: H - 600, width: 540, height: 580 },
      avatar: { left: 1400, top: 140, size: 300 },
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
    <AbsoluteFill style={{ background: NAVY, fontFamily: ROUNDED, color: INK }}>
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

const Backdrop: React.FC<{ L: Layout }> = ({ L }) => {
  const t = useCurrentFrame() / FPS;
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0,
        background: `radial-gradient(${L.W * 0.55}px ${L.W * 0.45}px at ${L.W * 0.12 + Math.sin(t * 0.5) * 60}px ${L.H * 0.12 + Math.cos(t * 0.4) * 60}px, #ffd0dc, transparent 70%),
                     radial-gradient(${L.W * 0.5}px ${L.W * 0.45}px at ${L.W * 0.9 + Math.cos(t * 0.45) * 60}px ${L.H * 0.85 + Math.sin(t * 0.35) * 60}px, #d5e7ff, transparent 70%),
                     radial-gradient(${L.W * 0.35}px ${L.W * 0.3}px at ${L.W * 0.85}px ${L.H * 0.2}px, #fff0c9, transparent 70%)` }} />
      {/* 黒板の罫線をうっすら */}
      <div style={{ position: 'absolute', inset: 0, opacity: 0.07,
        backgroundImage: 'linear-gradient(rgba(74,53,48,1) 2px, transparent 2px), linear-gradient(90deg, rgba(74,53,48,1) 2px, transparent 2px)',
        backgroundSize: '80px 80px' }} />
    </AbsoluteFill>
  );
};

const Header: React.FC<{ episode: Ep; L: Layout }> = ({ episode, L }) => (
  <div style={{ position: 'absolute', left: L.vertical ? 50 : 60, top: L.vertical ? 120 : 40, right: 50, display: 'flex', alignItems: 'center', gap: 20 }}>
    <div style={{ padding: '8px 22px', borderRadius: 14, background: PINK, color: '#fff', fontSize: L.vertical ? 40 : 34, fontWeight: 800, whiteSpace: 'nowrap', boxShadow: SHADOW }}>
      {episode.series ?? (episode.kind === 'grammar' ? '気合の文法' : '気合の英単語')}
    </div>
    <div style={{ fontSize: L.vertical ? 46 : 40, fontWeight: 800, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{episode.title}</div>
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
          <div style={{ fontSize: 120 * big, lineHeight: 1.15, fontWeight: 800, color: INK, WebkitTextStroke: '16px #fff', paintOrder: 'stroke fill', textShadow: `0 10px 0 ${PINK}` }}>
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
          <div style={{ fontSize: Math.min(190, 1500 / Math.max(6, letters.length)) * big, fontWeight: 800, letterSpacing: 2, fontFamily: 'sans-serif' }}>
            {letters.map((c, i) => {
              const p = pop(local, i * 2, 220);
              return <span key={i} style={{ display: 'inline-block', color: '#2f7fd8', transform: `translateY(${(1 - p) * -80}px) scale(${p})`,
                WebkitTextStroke: `12px #fff`, paintOrder: 'stroke fill', textShadow: '0 8px 0 rgba(74,53,48,0.15)' }}>{c === ' ' ? ' ' : c}</span>;
            })}
          </div>
          <div style={{ marginTop: 30, fontSize: 86 * big, fontWeight: 800, opacity: jaK, transform: `translateY(${(1 - jaK) * 40}px)` }}>{v.ja}</div>
          {v.note && <div style={{ marginTop: 26, fontSize: 46 * big, color: '#8a7a72', opacity: pop(local, 24) }}>{v.note}</div>}
        </div>
      );
    }
    case 'image': {
      const t = local / FPS;
      return (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 340 * big, transform: `scale(${k}) rotate(${Math.sin(t * 3) * 6}deg) translateY(${Math.sin(t * 2.4) * 16}px)` }}>{v.emoji}</div>
          {v.label && <div style={{ fontSize: 64 * big, fontWeight: 800, marginTop: 10, opacity: pop(local, 10) }}>{v.label}</div>}
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
          <div style={{ position: 'relative', display: 'inline-block', fontSize: 70 * big, fontWeight: 800, color: '#9a8d86', fontFamily: 'sans-serif', padding: '10px 30px', background: CARD, borderRadius: 24, boxShadow: SHADOW }}>
            {v.wrong}
            <div style={{ position: 'absolute', left: 0, right: 0, top: '52%', height: 10, background: RED, transform: `scaleX(${stamp})`, transformOrigin: 'left' }} />
            <div style={{ position: 'absolute', right: -70, top: -90, fontSize: 200, color: RED, transform: `scale(${stamp * 1.0 + (1 - stamp) * 3}) rotate(-12deg)`, opacity: stamp }}>✕</div>
          </div>
          <div style={{ marginTop: 50, fontSize: 70 * big, fontWeight: 800, color: GREEN, fontFamily: 'sans-serif', opacity: right, transform: `scale(${0.7 + right * 0.3})` }}>
            ⭕ {v.right}
          </div>
          {v.why && <div style={{ marginTop: 30, fontSize: 48 * big, color: YELLOW, opacity: pop(local, Math.round(FPS * 2)) }}>{v.why}</div>}
        </div>
      );
    }
    case 'compare': {
      const a = pop(local), b = pop(local, 10);
      const card = (x: { label: string; en: string; ja?: string }, p: number, from: number, color: string) => (
        <div style={{ flex: 1, padding: 34, borderRadius: 30, background: CARD, border: `5px solid ${color}`, boxShadow: SHADOW,
          transform: `translateX(${(1 - p) * from}px)`, opacity: p, textAlign: 'center' }}>
          <div style={{ fontSize: 46 * big, color, fontWeight: 800 }}>{x.label}</div>
          <div style={{ marginTop: 16, fontSize: 58 * big, fontWeight: 800, fontFamily: 'sans-serif' }}>{x.en}</div>
          {x.ja && <div style={{ marginTop: 12, fontSize: 40 * big, color: '#8a7a72' }}>{x.ja}</div>}
        </div>
      );
      return (
        <div style={{ width: '100%', display: 'flex', flexDirection: L.vertical ? 'column' : 'row', gap: 34 }}>
          {card(v.a, a, -900, '#2f7fd8')}
          {card(v.b, b, 900, PINK)}
        </div>
      );
    }
    case 'rule':
      return (
        <div style={{ width: '100%', padding: '40px 50px', borderRadius: 30, background: '#3f6b55', border: '12px solid #c9a46a', color: '#fff',
          boxShadow: '0 30px 60px -20px rgba(0,0,0,.7)', transform: `scale(${k})` }}>
          {v.title && <div style={{ fontFamily: HAND, fontSize: 70 * big, color: YELLOW, marginBottom: 20 }}>{v.title}</div>}
          {v.lines.map((l, i) => {
            const p = pop(local, 8 + i * 10);
            return <div key={i} style={{ fontFamily: HAND, fontSize: 60 * big, lineHeight: 1.5, opacity: p, transform: `translateX(${(1 - p) * -40}px)` }}>{l}</div>;
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
              <div style={{ position: 'relative', padding: '6px 18px', borderRadius: 16, background: CARD, borderBottom: `8px solid ${color}`, boxShadow: SHADOW,
                fontSize: size, fontWeight: 800, fontFamily: 'sans-serif', color }}>
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
      {v.ja && <div style={{ marginTop: 40, fontSize: 54 * big, color: '#6a5a52', opacity: jaK }}>{v.ja}</div>}
    </div>
  );
};

const Quiz: React.FC<{ v: Extract<Visual, { kind: 'quiz' }>; local: number; beatLocal: number; beat: Beat; big: number }> = ({ v, local, beatLocal, beat, big }) => {
  const thinkFrom = ((beat.dur ?? 0) + 0.3) * FPS;
  const thinkLen = (beat.think ?? 0) * FPS;
  const bar = !v.reveal && thinkLen ? interpolate(beatLocal, [thinkFrom, thinkFrom + thinkLen], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : null;
  return (
    <div style={{ width: '100%' }}>
      <div style={{ fontSize: 66 * big, fontWeight: 800, textAlign: 'center', marginBottom: 34, fontFamily: 'sans-serif', opacity: pop(local) }}>{v.q}</div>
      <div style={{ display: 'grid', gridTemplateColumns: v.choices.length > 2 ? '1fr 1fr' : '1fr', gap: 24 }}>
        {v.choices.map((c, i) => {
          const p = pop(local, 6 + i * 5);
          const isAns = v.reveal && i === v.answer;
          const dim = v.reveal && i !== v.answer;
          const glow = isAns ? pop(beatLocal, 4, 220) : 0;
          return (
            <div key={i} style={{ padding: '22px 30px', borderRadius: 24, fontSize: 56 * big, fontWeight: 800, fontFamily: 'sans-serif',
              background: isAns ? GREEN : CARD, color: isAns ? '#fff' : INK, border: `5px solid ${isAns ? GREEN : '#eadfd3'}`, boxShadow: SHADOW,
              opacity: p * (dim ? 0.35 : 1), transform: `scale(${p * (1 + glow * 0.06)})` }}>
              <span style={{ color: isAns ? '#fff' : PINK, marginRight: 16 }}>{'ABCD'[i]}</span>{c}
            </div>
          );
        })}
      </div>
      {bar != null && (
        <div style={{ marginTop: 40, height: 22, borderRadius: 11, background: '#eadfd3' }}>
          <div style={{ width: `${bar * 100}%`, height: '100%', borderRadius: 11, background: YELLOW, margin: '0 auto' }} />
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
  let pose: Pose = 'idle';
  for (let j = i; j >= 0; j--) if (beats[j].who === 'master') { pose = (beats[j].pose ?? 'talk') as Pose; break; }
  const amp = speaking ? (b.env?.[local] ?? 0) : 0;
  const enter = spring({ frame: f, fps: FPS, config: { damping: 14, stiffness: 110 } });
  const posePop = speaking ? spring({ frame: local, fps: FPS, config: { damping: 8, stiffness: 220 } }) : 1;
  const m = L.master;
  return (
    <div style={{ position: 'absolute', left: m.left, top: m.top, width: m.width, height: m.height,
      transform: `translateX(${(1 - enter) * 600}px) scale(${0.94 + posePop * 0.06})`, transformOrigin: 'bottom center',
      filter: speaking ? 'none' : 'saturate(0.6) opacity(0.85)' }}>
      <Character pose={pose} frame={f} amp={amp} />
    </div>
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
  const color = isMaster ? PINK : '#7fb2f0';
  return (
    <>
      {!isMaster && (
        <div style={{ position: 'absolute', left: a.left, top: a.top, width: a.size, height: a.size + 60,
          transform: `translateY(${(1 - enter) * 200}px) scale(${1 + amp * 0.06}) rotate(${Math.sin(local / 4) * amp * 4}deg)`, transformOrigin: 'bottom center' }}>
          <div style={{ width: a.size, height: a.size, borderRadius: '50%', background: CARD, border: `8px solid ${color}`, overflow: 'hidden', boxShadow: SHADOW,
            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <PersonaFace who={b.who} frame={local} amp={amp} size={a.size * 0.95} />
          </div>
          <div style={{ textAlign: 'center', marginTop: 8, fontSize: 34, fontWeight: 800, color: INK }}>{NAMES[b.who]}</div>
        </div>
      )}
      <div style={{ position: 'absolute', left: c.left, top: c.top, width: c.width, textAlign: 'center', opacity: Math.min(1, enter * 1.5) }}>
        {text.split('\n').map((l, k) => {
          const en = /^[\x00-\x7F’'"“”…—–]+$/.test(l.trim());
          return (
            <div key={k} style={{ display: 'inline-block', margin: '4px 0', padding: '8px 26px', borderRadius: 22,
              fontSize: (L.vertical ? 56 : 48) * (en ? 1.05 : 1), lineHeight: 1.3, fontWeight: 800,
              fontFamily: en ? 'sans-serif' : ROUNDED, color: en ? '#d94f70' : INK,
              background: CARD, boxShadow: SHADOW, border: `4px solid ${isMaster ? '#ffc2d1' : '#cfe0f7'}` }}>{l}</div>
          );
        }).reduce<React.ReactNode[]>((acc, el, k) => (k ? [...acc, <br key={`b${k}`} />, el] : [el]), [])}
      </div>
    </>
  );
};
