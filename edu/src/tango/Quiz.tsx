// 「3秒クイズ」の縦長ショート（1080×1920）。YouTube ショートとインスタのリールに同じ動画を出す。
//   word   … 英単語を見せて発音 → 3・2・1 → 意味（Keita が読む）と単語帳の絵
//   phrase … 日本語を見せて読む → 3・2・1 → 英語の答え（ネイティブの声）とひとこと
// 最初のコマから問いかけ（題）が読めるようにする（リールは最初の1秒で離れられるので、前置きは入れない）。
// 時間割は tango_quiz.py が計算して data.plan（コマ）で渡す。ここでは計算しない（音とずれないように）。
// 大事な文字は横 120〜960・縦 1500 より上に置く（右端にボタン、下に説明文が重なる）
import React from 'react';
import { AbsoluteFill, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import { DELA, ROUNDED } from '../fonts';
import { BROWN, CREAM, Chara, DOJO, EMBER, GOLD, RED, SLAB, pop } from './Tango';
import type { Line } from './types';

export type QuizItem = {
  q: string; // word：英単語／phrase：日本語
  pos?: string; // 品詞（word だけ）
  img?: string; // 単語帳の絵（word だけ）
  a: string[]; // word：意味（①②…）／phrase：英語の答え1文
  note?: string; // phrase：ひとこと（なぜそう言うか）
};
export type QuizPlan = {
  items: { start: number; len: number; think: number; reveal: number }[]; // think＝秒読みの始まり（どれも語の頭から）
  outro: number; // 締めの始まり
  total: number;
};
export type QuizData = {
  mode: 'word' | 'phrase';
  badge: string; // 上の札（「気合の英単語 必修」など）
  title: string[]; // 問いかけ（2行まで）
  items: QuizItem[];
  outro: Line[];
  outroTitle: string;
  outroSub: string;
  cover?: string; // 締めに出す本の表紙
  plan: QuizPlan;
};

// 品詞の略を書き下す（「名・動」→「名詞・動詞」）。小さい1文字だと読めないため
const POS: Record<string, string> = { 名: '名詞', 動: '動詞', 形: '形容詞', 副: '副詞', 接: '接続詞', 前: '前置詞', 熟: '熟語', 代: '代名詞', 助: '助動詞' };
const posLabel = (p: string) => p.split('・').map((x) => POS[x] ?? x).join('・');

const fade = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

/** 上：札・問いかけ・何問目か。動画のあいだずっと出しておく（途中から見た人にも何の動画か分かるように） */
const Header: React.FC<{ d: QuizData; i: number }> = ({ d, i }) => (
  <div style={{ position: 'absolute', left: 0, right: 0, top: 150, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
    <span style={{ fontFamily: DELA, fontSize: 40, color: BROWN, background: GOLD, borderRadius: 999, padding: '8px 34px', border: `5px solid ${BROWN}` }}>
      {d.badge}
    </span>
    <div style={{ marginTop: 22, fontFamily: DELA, fontSize: 96, lineHeight: 1.15, color: CREAM, textShadow: SLAB(7), textAlign: 'center' }}>
      {d.title.map((t, k) => <div key={k}>{t}</div>)}
    </div>
    <div style={{ display: 'flex', gap: 14, marginTop: 26 }}>
      {d.items.map((_, k) => (
        <div key={k} style={{ width: 92, height: 16, borderRadius: 99, background: k < i ? GOLD : k === i ? '#ffe9a0' : '#4a2a1a',
          border: k === i ? `3px solid ${GOLD}` : '3px solid transparent' }} />
      ))}
    </div>
  </div>
);

/** 3・2・1 */
const Count: React.FC<{ f: number; think: number; size: number }> = ({ f, think, size }) => {
  const { fps } = useVideoConfig();
  if (f < think) return <div style={{ width: size, height: size }} />;
  const n = 3 - Math.floor((f - think) / fps);
  if (n <= 0) return <div style={{ width: size, height: size }} />;
  const k = Math.min(1, ((f - think) % fps) / 8);
  return (
    <div style={{ width: size, height: size, borderRadius: 999, background: RED, border: `8px solid ${GOLD}`, color: CREAM, fontFamily: DELA,
      fontSize: size * 0.62, display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${1.25 - 0.25 * k})` }}>{n}</div>
  );
};

const Card: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ position: 'absolute', left: 90, right: 90, top: 540, height: 900, background: CREAM, borderRadius: 36, border: `8px solid ${GOLD}`,
    boxShadow: '0 24px 50px rgba(0,0,0,0.55)', display: 'flex', flexDirection: 'column', alignItems: 'center', overflow: 'hidden' }}>
    {children}
  </div>
);

const WordItem: React.FC<{ it: QuizItem; think: number; reveal: number }> = ({ it, think, reveal }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const shown = f >= reveal;
  const r = pop(f, fps, reveal);
  const full = Math.min(170, Math.floor(820 / (it.q.length * 0.64)));
  const size = full - (full - Math.min(120, full)) * Math.min(1, r);
  const long = it.a.join('').length > 20;
  return (
    <Card>
      <div style={{ marginTop: 40, display: 'flex', alignItems: 'center', gap: 20 }}>
        {it.pos ? <span style={{ fontFamily: ROUNDED, fontSize: 38, color: CREAM, background: BROWN, borderRadius: 12, padding: '6px 22px' }}>{posLabel(it.pos)}</span> : null}
      </div>
      <div style={{ marginTop: 10, fontFamily: DELA, fontSize: size, color: BROWN, lineHeight: 1.1, whiteSpace: 'nowrap', transform: `scale(${0.9 + pop(f, fps, 0) * 0.1})` }}>
        {it.q}
      </div>
      {!shown ? (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 34, paddingBottom: 40 }}>
          <div style={{ fontFamily: DELA, fontSize: 64, color: RED }}>意味は？</div>
          <Count f={f} think={think} size={260} />
        </div>
      ) : (
        <div style={{ flex: 1, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: Math.min(1, r * 1.5) }}>
          {it.img ? (
            <Img src={staticFile(it.img)} style={{ marginTop: 16, width: 300, height: 300, borderRadius: 24, border: `6px solid ${BROWN}`, transform: `scale(${0.7 + r * 0.3})` }} />
          ) : null}
          <div style={{ marginTop: 20, padding: '0 50px', fontFamily: ROUNDED, fontSize: long ? 50 : 58, lineHeight: 1.3, color: BROWN, textAlign: 'center' }}>
            {it.a.map((m, k) => <div key={k}>{m}</div>)}
          </div>
        </div>
      )}
    </Card>
  );
};

const PhraseItem: React.FC<{ it: QuizItem; think: number; reveal: number }> = ({ it, think, reveal }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const shown = f >= reveal;
  const r = pop(f, fps, reveal);
  // 改行は台本の \n で（意味の切れ目で折る）。いちばん長い行がカードに1行で収まる大きさにする
  const lines = it.q.replace(/^「|」$/g, '').split('\n');
  lines[0] = `「${lines[0]}`;
  lines[lines.length - 1] += '」';
  const qSize = Math.min(88, Math.floor(800 / Math.max(...lines.map((l) => l.length))));
  return (
    <Card>
      <div style={{ marginTop: 56, fontFamily: DELA, fontSize: 44, color: RED }}>英語で言える？</div>
      <div style={{ marginTop: 26, padding: '0 56px', fontFamily: DELA, fontSize: qSize, lineHeight: 1.3, color: BROWN, textAlign: 'center',
        transform: `scale(${0.9 + pop(f, fps, 0) * 0.1})` }}>{lines.map((l, k) => <div key={k}>{l}</div>)}</div>
      {!shown ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', paddingBottom: 40 }}>
          <Count f={f} think={think} size={260} />
        </div>
      ) : (
        <div style={{ flex: 1, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 34, paddingBottom: 30,
          opacity: Math.min(1, r * 1.5) }}>
          <div style={{ margin: '0 48px', background: BROWN, borderRadius: 24, padding: '30px 40px', fontFamily: ROUNDED, fontSize: it.a[0].length > 34 ? 56 : 66,
            lineHeight: 1.3, color: GOLD, textAlign: 'center', transform: `scale(${0.75 + r * 0.25})` }}>{it.a[0]}</div>
          {it.note ? (
            <div style={{ margin: '0 60px', fontFamily: ROUNDED, fontSize: 46, lineHeight: 1.5, color: '#5a3524', textAlign: 'center',
              opacity: fade(f, reveal + 12, reveal + 22) }}>{it.note.split('\n').map((l, k) => <div key={k}>{l}</div>)}</div>
          ) : null}
        </div>
      )}
    </Card>
  );
};

/** 下：仙人のひとこと（考える間／答えのあと） */
const Coach: React.FC<{ shown: boolean; reveal: number }> = ({ shown, reveal }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <div style={{ position: 'absolute', left: 30, top: 1400 }}>
        <Chara who="master" size={340} talking={false} />
      </div>
      <div style={{ position: 'absolute', left: 340, top: 1500, background: CREAM, color: BROWN, fontFamily: ROUNDED, fontSize: 42, borderRadius: 24,
        padding: '14px 28px', border: `5px solid ${BROWN}`, whiteSpace: 'nowrap', transformOrigin: 'left center',
        transform: `scale(${pop(f, fps, shown ? reveal + 4 : 4)})` }}>
        {shown ? '言えたかの？' : '答えてみよ！'}
      </div>
    </>
  );
};

const Item: React.FC<{ d: QuizData; k: number }> = ({ d, k }) => {
  const f = useCurrentFrame();
  const p = d.plan.items[k];
  const it = d.items[k];
  return (
    <AbsoluteFill>
      {d.mode === 'word' ? <WordItem it={it} think={p.think} reveal={p.reveal} /> : <PhraseItem it={it} think={p.think} reveal={p.reveal} />}
      <Coach shown={f >= p.reveal} reveal={p.reveal} />
    </AbsoluteFill>
  );
};

const Outro: React.FC<{ d: QuizData }> = ({ d }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const line = d.outro[0];
  const talking = !!line && f < Math.round((line.dur + 0.3) * fps);
  return (
    <AbsoluteFill style={{ background: EMBER }}>
      <div style={{ position: 'absolute', top: 240, width: '100%', textAlign: 'center', fontFamily: DELA, fontSize: 120, lineHeight: 1.15, color: CREAM,
        textShadow: SLAB(9), transform: `scale(${pop(f, fps, 0)})` }}>{d.outroTitle}</div>
      <div style={{ position: 'absolute', top: 420, width: '100%', textAlign: 'center', fontFamily: ROUNDED, fontSize: 52, color: CREAM }}>{d.outroSub}</div>
      <div style={{ position: 'absolute', left: 60, top: 640, transform: `translateY(${talking ? Math.sin(f / 3) * -8 : 0}px)` }}>
        <Chara who="master" size={560} talking={talking} />
      </div>
      {d.cover ? (
        <Img src={staticFile(d.cover)} style={{ position: 'absolute', right: 110, top: 700, width: 360, height: 576, borderRadius: 14, border: `6px solid ${CREAM}`,
          boxShadow: '0 24px 44px rgba(60,0,0,0.5)', transform: `rotate(4deg) translateY(${(1 - pop(f, fps, 6)) * 300}px)` }} />
      ) : null}
      {line ? (
        <div style={{ position: 'absolute', left: 110, right: 110, top: 1330, display: 'flex', justifyContent: 'center' }}>
          <div style={{ background: 'rgba(27,10,4,0.88)', border: `4px solid ${GOLD}`, borderRadius: 18, padding: '16px 34px', fontFamily: ROUNDED, fontSize: 46,
            color: CREAM, lineHeight: 1.35, textAlign: 'center' }}>
            <span style={{ color: GOLD, marginRight: 16 }}>仙人</span>{line.line}
          </div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

export const TangoQuiz: React.FC<{ data: QuizData }> = ({ data: d }) => {
  const f = useCurrentFrame();
  let i = 0;
  while (i + 1 < d.plan.items.length && d.plan.items[i + 1].start <= f) i++;
  return (
    <AbsoluteFill style={{ background: DOJO }}>
      {f < d.plan.outro ? <Header d={d} i={i} /> : null}
      {d.plan.items.map((p, k) => (
        <Sequence key={k} from={p.start} durationInFrames={p.len}><Item d={d} k={k} /></Sequence>
      ))}
      <Sequence from={d.plan.outro}><Outro d={d} /></Sequence>
    </AbsoluteFill>
  );
};
