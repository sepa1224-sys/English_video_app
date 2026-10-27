// 「イメージで英単語エクササイズ」（横長・稽古ごと100語）と、そのサムネ・チャンネルのアイコン／バナー。
// 色と書体は単語帳「気合の英単語」とアプリの道場にそろえる（こげ茶・生成り・金・朱、Dela Gothic One）。
// 赤い面の光は柔らかい放射状のグラデーションだけにする（放射線は旭日旗に似るので使わない）
import React from 'react';
import {
  AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';

import { DELA, ROUNDED } from '../fonts';
import { type Line, type TangoData, type Who, type Word, AFTER1, LINE_GAP, THINK, sec, sections } from './types';
import { Headphones, THEMES, type ThumbKind, slab, thumbKind } from './theme';

export const BROWN = '#1b0a04';
export const BROWN2 = '#2e1409';
export const CREAM = '#fff3d6';
export const GOLD = '#ffd23f';
export const RED = '#d7262e';
export const EMBER = 'radial-gradient(ellipse at 50% 62%, #ffb43a 0%, #f2701f 32%, #d7262e 68%, #a8141c 100%)';
export const DOJO = `radial-gradient(ellipse at 50% 45%, ${BROWN2} 0%, ${BROWN} 70%)`;
// 表紙の文字と同じ、こげ茶の段の影
export const SLAB = (n: number) => Array.from({ length: n }, (_, i) => `${i + 1}px ${i + 1}px 0 #5a1208`).join(',');

const NAMES: Record<Who, string> = {
  master: '仙人', nekketsu: '熱血', megane: 'メガネ', tsundere: 'ツンデレ',
  osananajimi: '幼なじみ', ikemen: 'イケメン', spartan: 'スパルタ師範代',
};
const CREW: Who[] = ['nekketsu', 'megane', 'tsundere', 'osananajimi', 'ikemen', 'spartan', 'master'];
// 10語ごとに横で見守るキャラと、そのひとこと（考える間／答えのあと）
const COACH: { who: Who; think: string; repeat: string }[] = [
  { who: 'nekketsu', think: '言ってみろ！', repeat: '続けて言え！' },
  { who: 'megane', think: 'わかりますか？', repeat: 'まねしましょう' },
  { who: 'tsundere', think: '早く言いなさいよ！', repeat: 'ほら、言って！' },
  { who: 'osananajimi', think: 'せーので言おう！', repeat: 'いっしょに言おう' },
  { who: 'ikemen', think: '君ならいける', repeat: 'いい発音だ' },
  { who: 'spartan', think: '3秒で答えよ！', repeat: '声が小さい！' },
  { who: 'master', think: '答えてみよ', repeat: 'まねするのじゃ' },
];

/** キャラの立ち絵。仙人は話している間だけ口を開け閉めする */
export const Chara: React.FC<{ who: Who; size: number; talking?: boolean; style?: React.CSSProperties }> = ({ who, size, talking, style }) => {
  const f = useCurrentFrame();
  const file = who === 'master' ? (talking && Math.floor(f / 4) % 2 ? 'sennin_04_point_open' : 'sennin_03_point') : who;
  return <Img src={staticFile(`chara/cut/${file}.png`)} style={{ width: size, height: size, ...style }} />;
};

export const pop = (f: number, fps: number, delay = 0) => spring({ frame: f - delay, fps, config: { damping: 12, stiffness: 160 } });
const fadeIn = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

/** セリフの字幕（画面の下） */
const Caption: React.FC<{ line?: Line; bottom?: number; right?: number }> = ({ line, bottom = 36, right = 120 }) => (line ? (
  <div style={{ position: 'absolute', left: 120, right, bottom, display: 'flex', justifyContent: 'center' }}>
    <div style={{ background: 'rgba(27,10,4,0.88)', border: `4px solid ${GOLD}`, borderRadius: 18, padding: '14px 34px',
      fontFamily: ROUNDED, fontSize: 44, color: CREAM, lineHeight: 1.35, textAlign: 'center' }}>
      <span style={{ color: GOLD, marginRight: 18 }}>{NAMES[line.who]}</span>{line.line}
    </div>
  </div>
) : null);

/** セリフを順に流し、今しゃべっているセリフを返す */
const useLines = (lines: Line[]) => {
  const f = useCurrentFrame();
  let t = sec(0.3);
  const at = lines.map((l) => { const s = t; t += sec(l.dur + LINE_GAP); return s; });
  let cur = -1;
  at.forEach((s, i) => { if (f >= s) cur = i; });
  const talking = cur >= 0 && f < at[cur] + sec(lines[cur].dur);
  return { at, cur, line: lines[cur], talking };
};
const LineAudio: React.FC<{ lines: Line[] }> = ({ lines }) => {
  const { at } = useLines(lines);
  return <>{lines.map((l, i) => <Sequence key={i} from={at[i]}><Audio src={staticFile(l.audio)} /></Sequence>)}</>;
};

/** 表紙のタイトル（「気合の 英単語 ＋ 必修」）を横書きで */
const BookTitle: React.FC<{ scale?: number }> = ({ scale = 1 }) => (
  <div style={{ fontFamily: DELA, lineHeight: 1, transform: `scale(${scale})`, transformOrigin: 'left top' }}>
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 22 }}>
      <span style={{ fontSize: 96, color: GOLD, textShadow: SLAB(6) }}>気合の</span>
      <span style={{ fontSize: 60, color: RED, background: GOLD, borderRadius: 16, padding: '10px 16px 14px',
        border: `5px solid ${BROWN}`, transform: 'rotate(6deg)', marginBottom: 14 }}>必修</span>
    </div>
    <div style={{ fontSize: 190, color: CREAM, textShadow: SLAB(10), marginTop: 10, letterSpacing: 8 }}>英単語</div>
  </div>
);

// ───────────────────────── 冒頭：単語帳の紹介 ─────────────────────────
export const Intro: React.FC<{ d: TangoData }> = ({ d }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { line, talking } = useLines(d.intro);
  const cover = pop(f, fps, 4);
  return (
    <AbsoluteFill style={{ background: EMBER }}>
      <LineAudio lines={d.intro} />
      <div style={{ position: 'absolute', left: 130, top: 110, opacity: fadeIn(f, 0, 10) }}>
        <div style={{ fontFamily: ROUNDED, fontSize: 40, color: CREAM, marginBottom: 26 }}>気合イングリッシュの単語帳</div>
        <BookTitle />
        <div style={{ display: 'flex', gap: 22, marginTop: 34, alignItems: 'center' }}>
          <span style={{ fontFamily: DELA, fontSize: 44, color: CREAM, borderTop: `4px solid ${GOLD}`, borderBottom: `4px solid ${GOLD}`, padding: '8px 4px' }}>
            大学入試 頻出1000語
          </span>
          <span style={{ fontFamily: DELA, fontSize: 40, color: BROWN, background: GOLD, borderRadius: 999, padding: '10px 30px',
            transform: `scale(${pop(f, fps, 18)})` }}>{d.book.label}</span>
        </div>
      </div>
      <Img src={staticFile('tango/cover.jpg')} style={{
        position: 'absolute', left: 1290, top: 96, width: 500, height: 800, borderRadius: 18,
        boxShadow: '0 30px 60px rgba(60,0,0,0.55)', border: `6px solid ${CREAM}`,
        transform: `translateY(${(1 - cover) * 260}px) rotate(${4 - cover * 1}deg) scale(${0.85 + cover * 0.15})`,
      }} />
      {/* 本のキャラが勢ぞろい */}
      <div style={{ position: 'absolute', left: 60, top: 630, display: 'flex' }}>
        {CREW.map((w, i) => {
          const p = pop(f, fps, 10 + i * 4);
          return <div key={w} style={{ width: 170, transform: `translateY(${(1 - p) * 300}px)` }}>
            <Chara who={w} size={300} talking={w === 'master' && talking} style={{ marginLeft: -65 }} />
          </div>;
        })}
      </div>
      <Caption line={line} />
    </AbsoluteFill>
  );
};

// ───────────────────────── やり方 ─────────────────────────
const HowTo: React.FC<{ d: TangoData }> = ({ d }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { line, cur, talking } = useLines(d.howto);
  const steps = [
    { n: '1', t: '絵を見る', s: '頭文字のヒントつき' },
    { n: '2', t: '3秒で英語を言う', s: '声に出して答える' },
    { n: '3', t: '発音をまねする', s: '2回、あとについて' },
  ];
  const lit = cur <= 0 ? [0, 1] : cur === 1 ? [2] : [0, 1, 2];
  return (
    <AbsoluteFill style={{ background: DOJO }}>
      <LineAudio lines={d.howto} />
      <div style={{ position: 'absolute', top: 90, width: '100%', textAlign: 'center', fontFamily: DELA, fontSize: 84, color: GOLD, textShadow: SLAB(6) }}>
        エクササイズのやり方
      </div>
      <div style={{ position: 'absolute', top: 260, left: 110, right: 110, display: 'flex', gap: 46 }}>
        {steps.map((s, i) => {
          const on = lit.includes(i);
          const p = pop(f, fps, 6 + i * 6);
          return (
            <div key={i} style={{ flex: 1, height: 400, background: on ? CREAM : '#3b2116', borderRadius: 28, border: `6px solid ${on ? GOLD : '#5a3524'}`,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 18,
              transform: `scale(${p * (on ? 1.03 : 0.97)})`, transition: 'none' }}>
              <div style={{ width: 120, height: 120, borderRadius: 999, background: RED, color: CREAM, fontFamily: DELA, fontSize: 76,
                display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{s.n}</div>
              <div style={{ fontFamily: DELA, fontSize: 54, color: on ? BROWN : '#a88a72' }}>{s.t}</div>
              <div style={{ fontFamily: ROUNDED, fontSize: 36, color: on ? '#7a3a1c' : '#7d5d4a' }}>{s.s}</div>
            </div>
          );
        })}
      </div>
      {line ? (
        <div style={{ position: 'absolute', right: 70, top: 640, transform: `translateY(${talking ? Math.sin(f / 3) * -6 : 0}px)` }}>
          <Chara who={line.who} size={420} talking={talking} />
        </div>
      ) : null}
      <Caption line={line} bottom={60} right={500} />
    </AbsoluteFill>
  );
};

// ───────────────────────── 1語 ─────────────────────────
const Hint: React.FC<{ hint: string[]; size: number }> = ({ hint, size }) => (
  <div style={{ display: 'flex', gap: size * 0.7, flexWrap: 'wrap', justifyContent: 'center' }}>
    {hint.map((w, i) => (
      <div key={i} style={{ display: 'flex', gap: size * 0.14 }}>
        {[...w].map((c, j) => (
          <span key={j} style={{ fontFamily: DELA, fontSize: size, width: size * 0.72, textAlign: 'center',
            color: j === 0 ? GOLD : CREAM, lineHeight: 1 }}>{j === 0 ? c : '＿'}</span>
        ))}
      </div>
    ))}
  </div>
);

const WordCard: React.FC<{ d: TangoData; w: Word; i: number }> = ({ d, w, i }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveal = sec(THINK);
  const v1 = sec(THINK + 0.1);
  const v2 = v1 + sec(w.voiceDur + AFTER1);
  const shown = f >= reveal;
  const r = pop(f, fps, reveal);
  const count = f < sec(THINK - 3) ? null : 3 - Math.floor((f - sec(THINK - 3)) / fps);
  const coach = COACH[Math.floor(i / 10) % COACH.length];
  const letters = w.headword.length;
  const wordSize = Math.min(168, Math.floor(860 / (letters * 0.66)));
  const hintSize = Math.min(84, Math.floor(820 / (letters * 0.86 + (w.hint.length - 1) * 0.7)));
  const voicing = (f >= v1 && f < v1 + sec(w.voiceDur)) || (f >= v2 && f < v2 + sec(w.voiceDur));
  const img = pop(f, fps, 0);
  return (
    <AbsoluteFill>
      {[sec(THINK - 3), sec(THINK - 2), sec(THINK - 1)].map((s) => (
        <Sequence key={s} from={s} durationInFrames={10}><Audio src={staticFile('tango/tick.mp3')} volume={0.45} /></Sequence>
      ))}
      <Sequence from={v1}><Audio src={staticFile(w.voice)} /></Sequence>
      <Sequence from={v2}><Audio src={staticFile(w.voice)} /></Sequence>

      {/* 絵 */}
      <div style={{ position: 'absolute', left: 110, top: 180, width: 780, height: 780, background: CREAM, borderRadius: 34,
        border: `8px solid ${GOLD}`, boxShadow: '0 24px 50px rgba(0,0,0,0.5)', overflow: 'hidden',
        transform: `scale(${0.9 + img * 0.1})`, opacity: img }}>
        <Img src={staticFile(w.img)} style={{ width: 764, height: 764 }} />
      </div>
      <div style={{ position: 'absolute', left: 140, top: 150, background: RED, color: CREAM, fontFamily: DELA, fontSize: 40,
        borderRadius: 14, padding: '6px 22px', border: `4px solid ${CREAM}` }}>No.{w.no}</div>

      {/* 右：考える間はヒントと秒読み、答えが出たら単語・品詞・意味 */}
      <div style={{ position: 'absolute', left: 960, top: 180, width: 860, height: 560, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center' }}>
        {!shown ? (
          <>
            <div style={{ fontFamily: DELA, fontSize: 64, color: CREAM, marginBottom: 46 }}>英語で言うと？</div>
            <Hint hint={w.hint} size={hintSize} />
            <div style={{ height: 190, marginTop: 40, display: 'flex', alignItems: 'center' }}>
              {count != null && count > 0 ? (
                <div key={count} style={{ width: 170, height: 170, borderRadius: 999, background: RED, border: `6px solid ${GOLD}`,
                  color: CREAM, fontFamily: DELA, fontSize: 110, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transform: `scale(${1.25 - 0.25 * Math.min(1, ((f - sec(THINK - 3)) % fps) / 8)})` }}>{count}</div>
              ) : null}
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', transform: `scale(${0.6 + r * 0.4})`, opacity: Math.min(1, r * 1.5) }}>
            <div style={{ fontFamily: DELA, fontSize: wordSize, color: GOLD, textShadow: SLAB(8), lineHeight: 1.1, whiteSpace: 'nowrap' }}>{w.headword}</div>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 24, marginTop: 40, maxWidth: 860 }}>
              <span style={{ fontFamily: DELA, fontSize: 40, color: BROWN, background: CREAM, borderRadius: 12, padding: '6px 16px', whiteSpace: 'nowrap' }}>{w.pos}</span>
              <div style={{ fontFamily: ROUNDED, fontSize: w.meanings.join('').length > 22 ? 44 : 56, color: CREAM, lineHeight: 1.3 }}>
                {w.meanings.map((m, k) => <div key={k}>{m}</div>)}
              </div>
            </div>
            <div style={{ marginTop: 44, fontFamily: ROUNDED, fontSize: 40, color: voicing ? GOLD : '#c9a98a',
              display: 'flex', alignItems: 'center', gap: 14 }}>
              <span style={{ display: 'inline-block', width: 22, height: 22, borderRadius: 99, background: voicing ? GOLD : '#7d5d4a',
                transform: `scale(${voicing ? 1 + Math.sin(f / 2.5) * 0.25 : 1})` }} />
              {voicing ? '聞いて…' : 'まねして言おう！'}
            </div>
          </div>
        )}
      </div>

      {/* 見守るキャラ */}
      <div style={{ position: 'absolute', right: 40, bottom: -30 }}>
        <Chara who={coach.who} size={330} talking={voicing} />
      </div>
      <div style={{ position: 'absolute', right: 330, bottom: 150, background: CREAM, color: BROWN, fontFamily: ROUNDED, fontSize: 36,
        borderRadius: 24, padding: '14px 26px', border: `4px solid ${BROWN}`, whiteSpace: 'nowrap',
        transform: `scale(${pop(f, fps, shown ? reveal + 6 : 6)})`, transformOrigin: 'right center' }}>
        {shown ? coach.repeat : coach.think}
      </div>
    </AbsoluteFill>
  );
};

/** 上の帯：シリーズ名・稽古・進み具合 */
export const TopBar: React.FC<{ d: TangoData; i: number; within: number; len: number }> = ({ d, i, within, len }) => {
  const done = (i + Math.min(1, within / len)) / d.words.length;
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 120 }}>
      <div style={{ position: 'absolute', left: 110, top: 34, display: 'flex', alignItems: 'center', gap: 22 }}>
        <span style={{ fontFamily: DELA, fontSize: 36, color: BROWN, background: GOLD, borderRadius: 10, padding: '4px 18px' }}>{d.label ?? `稽古${d.keiko}`}</span>
        <span style={{ fontFamily: DELA, fontSize: 36, color: CREAM }}>{d.series}</span>
      </div>
      <div style={{ position: 'absolute', right: 110, top: 40, fontFamily: ROUNDED, fontSize: 34, color: '#e8cfa8' }}>
        気合の英単語 必修　<span style={{ color: GOLD }}>{i + 1}</span> / {d.words.length}
      </div>
      <div style={{ position: 'absolute', left: 110, right: 110, top: 104, height: 12, borderRadius: 99, background: '#3b2116' }}>
        <div style={{ width: `${done * 100}%`, height: '100%', borderRadius: 99, background: GOLD }} />
      </div>
    </div>
  );
};

const Words: React.FC<{ d: TangoData }> = ({ d }) => {
  const f = useCurrentFrame();
  const S = sections(d);
  let t = 0;
  const starts = S.words.map((n) => { const s = t; t += n; return s; });
  let i = 0;
  while (i + 1 < starts.length && starts[i + 1] <= f) i++;
  return (
    <AbsoluteFill style={{ background: DOJO }}>
      <TopBar d={d} i={i} within={f - starts[i]} len={S.words[i]} />
      {d.words.map((w, k) => (
        <Sequence key={w.no} from={starts[k]} durationInFrames={S.words[k]}>
          <WordCard d={d} w={w} i={k} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

// ───────────────────────── 締めの QR（稽古1の無料見本へ・2026-10-27） ─────────────────────────
// 白地に黒の QR（PNG に白い余白＝クワイエットゾーン込み）。読み取りやすいよう動かさず、拡大はドットのまま
export const QrCard: React.FC<{ qr: NonNullable<TangoData['qr']>; size?: number; style?: React.CSSProperties }> = ({ qr, size = 300, style }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', background: CREAM, border: `6px solid ${BROWN}`,
    borderRadius: 26, padding: '16px 22px 14px', boxShadow: '0 12px 0 rgba(60,0,0,0.45)', ...style }}>
    <div style={{ fontFamily: DELA, fontSize: 36, color: RED, marginBottom: 10, whiteSpace: 'nowrap' }}>{qr.label ?? '無料で稽古1（100語）'}</div>
    <Img src={staticFile(qr.src)} style={{ width: size, height: size, imageRendering: 'pixelated', display: 'block', background: '#fff' }} />
    <div style={{ fontFamily: ROUNDED, fontSize: 30, color: BROWN, marginTop: 8, whiteSpace: 'nowrap' }}>{qr.sub ?? 'スマホで読み取り'}</div>
  </div>
);

// ───────────────────────── 締め ─────────────────────────
export const Outro: React.FC<{ d: TangoData }> = ({ d }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { line, talking } = useLines(d.outro);
  return (
    <AbsoluteFill style={{ background: EMBER }}>
      <LineAudio lines={d.outro} />
      <div style={{ position: 'absolute', top: 90, width: '100%', textAlign: 'center', fontFamily: DELA, fontSize: 130, color: CREAM,
        textShadow: SLAB(9), transform: `scale(${pop(f, fps, 0)})` }}>{d.outroTitle ?? `稽古${d.keiko} 完了！`}</div>
      <div style={{ position: 'absolute', top: 280, width: '100%', textAlign: 'center', fontFamily: ROUNDED, fontSize: 44, color: CREAM }}>
        チャンネル登録で、次の稽古へ
      </div>
      <div style={{ position: 'absolute', left: 70, top: 400, display: 'flex' }}>
        {CREW.map((w, i) => {
          const hop = Math.max(0, Math.sin((f - i * 5) / 6)) * 30;
          return <div key={w} style={{ width: 176, transform: `translateY(${-hop * fadeIn(f, i * 4, i * 4 + 10)}px)` }}>
            <Chara who={w} size={340} talking={w === 'master' && talking} style={{ marginLeft: -70 }} />
          </div>;
        })}
      </div>
      {d.qr ? (
        <QrCard qr={d.qr} style={{ position: 'absolute', right: 70, top: 370 }} />
      ) : (
        <div style={{ position: 'absolute', right: 120, top: 330, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
          <Img src={staticFile('tango/cover.jpg')} style={{ width: 300, height: 480, borderRadius: 12, border: `5px solid ${CREAM}`,
            boxShadow: '0 20px 40px rgba(60,0,0,0.5)', transform: 'rotate(3deg)' }} />
          <span style={{ fontFamily: DELA, fontSize: 34, color: BROWN, background: GOLD, borderRadius: 999, padding: '8px 26px' }}>{d.book.label}</span>
        </div>
      )}
      <Caption line={line} />
    </AbsoluteFill>
  );
};

// ───────────────────────── 本の案内カード（締めの直前・約5秒） ─────────────────────────
// 2026-10-23：動画から紙の本『気合の英単語 必修』へ。リンクは概要欄とピン留めコメント
export const BookCard: React.FC<{ d: TangoData }> = ({ d }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { line, talking } = useLines(d.outroBook ?? []);
  const cover = pop(f, fps, 2);
  const big = d.bookBig ?? `稽古${d.keiko}`;
  return (
    <AbsoluteFill style={{ background: EMBER }}>
      <LineAudio lines={d.outroBook ?? []} />
      <Img src={staticFile('tango/cover.jpg')} style={{
        position: 'absolute', left: 170, top: 90, width: 520, height: 832, borderRadius: 18, border: `6px solid ${CREAM}`,
        boxShadow: '0 30px 60px rgba(60,0,0,0.55)',
        transform: `translateY(${(1 - cover) * 240}px) rotate(${-4 + cover * 1}deg) scale(${0.85 + cover * 0.15})` }} />
      <div style={{ position: 'absolute', left: 780, top: 130, width: 1060, opacity: fadeIn(f, 6, 18) }}>
        <div style={{ fontFamily: ROUNDED, fontSize: 56, color: CREAM, textShadow: '0 3px 0 #5a1208' }}>この100語は</div>
        <div style={{ fontFamily: DELA, fontSize: 84, color: GOLD, textShadow: SLAB(7), lineHeight: 1.25, marginTop: 14 }}>
          『気合の英単語 必修』
        </div>
        <div style={{ fontFamily: DELA, fontSize: 56, color: CREAM, textShadow: SLAB(5), marginTop: 6 }}>{d.bookOf ?? 'の'}</div>
        {/* QR があるときは右に QR の札が来るので、大きい字は札の手前（幅 590）に収める */}
        <div style={{ fontFamily: DELA, fontSize: d.qr ? Math.min(170, Math.floor(590 / [...big].length)) : 170, color: CREAM, textShadow: SLAB(10), lineHeight: 1.1,
          whiteSpace: 'nowrap', transform: `scale(${pop(f, fps, 10)})`, transformOrigin: 'left center' }}>{big}</div>
      </div>
      <div style={{ position: 'absolute', left: 780, top: 660, transform: `scale(${pop(f, fps, 22)})`, transformOrigin: 'left center' }}>
        <span style={{ fontFamily: DELA, fontSize: 64, color: BROWN, background: GOLD, borderRadius: 999, padding: '14px 44px',
          border: `5px solid ${BROWN}`, boxShadow: '0 8px 0 rgba(60,0,0,0.45)' }}>本は概要欄から</span>
      </div>
      {d.qr ? (<>
        <QrCard qr={d.qr} style={{ position: 'absolute', right: 70, top: 370 }} />
        <div style={{ position: 'absolute', right: 440, bottom: 120 }}>
          <Chara who="master" size={240} talking={talking} />
        </div>
      </>) : (
        <div style={{ position: 'absolute', right: 40, bottom: 110 }}>
          <Chara who="master" size={300} talking={talking} />
        </div>
      )}
      <Caption line={line} bottom={30} />
    </AbsoluteFill>
  );
};

// BGM は解説ショートと同じレトロRPG風（村）を小さく
export const TangoExercise: React.FC<{ data: TangoData }> = ({ data: d }) => {
  const S = sections(d);
  const f = useCurrentFrame();
  const bgm = interpolate(f, [0, 20, S.total - 60, S.total], [0, 0.06, 0.06, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ background: BROWN }}>
      <Audio src={staticFile('bgm/03_village.mp3')} volume={bgm} loop />
      <Sequence durationInFrames={S.intro}><Intro d={d} /></Sequence>
      <Sequence from={S.intro} durationInFrames={S.howto}><HowTo d={d} /></Sequence>
      <Sequence from={S.intro + S.howto} durationInFrames={S.wordsTotal}><Words d={d} /></Sequence>
      <Sequence from={S.intro + S.howto + S.wordsTotal} durationInFrames={S.outro}><Outro d={d} /></Sequence>
      {S.book > 0 && (
        <Sequence from={S.intro + S.howto + S.wordsTotal + S.outro} durationInFrames={S.book}><BookCard d={d} /></Sequence>
      )}
    </AbsoluteFill>
  );
};

// ───────────────────────── サムネ（1280×720） ─────────────────────────
// 左に本の絵を4枚大きく、右に「イメージで覚える英単語」。左上に「気合の英単語 必修」（2026-10-20 坂本さん）
export const TangoThumb: React.FC<{ data: TangoData; theme?: ThumbKind }> = ({ data: d, theme }) => {
  const imgs = d.thumbs.slice(0, 4);
  const listen = thumbKind(d, theme) === 'listen';
  const t = listen ? THEMES.listen : THEMES.exercise;
  const S = slab(t);
  const tilt = [-4, 3, 3, -3];
  return (
    <AbsoluteFill style={{ background: t.bg, overflow: 'hidden' }}>
      {/* 左：絵を4枚（2×2） */}
      <div style={{ position: 'absolute', left: 28, top: 124, width: 560, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {imgs.map((src, k) => (
          <div key={k} style={{ width: 268, height: 268, background: '#fff', borderRadius: 22, border: `7px solid ${CREAM}`, overflow: 'hidden',
            transform: `rotate(${tilt[k]}deg)`, boxShadow: `0 14px 28px ${t.shadow}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Img src={staticFile(src)} style={{ width: 254, height: 254, objectFit: 'contain' }} />
          </div>
        ))}
      </div>
      {/* 左上：気合の英単語 */}
      <div style={{ position: 'absolute', left: 28, top: 22, display: 'flex', alignItems: 'center', gap: 12, fontFamily: DELA, lineHeight: 1 }}>
        <span style={{ fontSize: 44, color: CREAM, textShadow: S(4) }}><span style={{ color: GOLD }}>気合</span>の英単語</span>
        <span style={{ fontSize: 32, color: RED, background: GOLD, borderRadius: 10, padding: '6px 12px' }}>必修</span>
      </div>
      {/* 右：題 */}
      <div style={{ position: 'absolute', left: 612, right: 10, top: 0, bottom: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center',
        fontFamily: DELA, lineHeight: 1.02 }}>
        {listen ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginTop: -30 }}>
              <Headphones size={118} color={CREAM} outline={t.band} />
              <span style={{ fontSize: 96, color: CREAM, textShadow: S(7), whiteSpace: 'nowrap' }}>英単語</span>
            </div>
            <div style={{ fontSize: 158, color: GOLD, textShadow: S(13), marginTop: 18, marginLeft: -8, letterSpacing: -4, whiteSpace: 'nowrap',
              WebkitTextStroke: `5px ${t.band}`, paintOrder: 'stroke fill' }}>聞き流し</div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 62, color: CREAM, textShadow: S(6), whiteSpace: 'nowrap', marginTop: -40 }}>イメージで覚える</div>
            <div style={{ fontSize: 218, color: GOLD, textShadow: S(13), marginTop: 14, marginLeft: -10, letterSpacing: -6, whiteSpace: 'nowrap', WebkitTextStroke: `5px ${BROWN}` }}>英単語</div>
          </>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 26 }}>
          <span style={{ fontSize: 48, color: t.band, background: GOLD, padding: '8px 16px', borderRadius: 12 }}>{d.label ?? `稽古${d.keiko}`}</span>
          {d.label ? null : <span style={{ fontSize: 36, color: CREAM, textShadow: S(4) }}>No.{d.range[0]}〜{d.range[1]}</span>}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ───────────────────────── チャンネルのアイコン（800×800・丸く切られる） ─────────────────────────
// 小さく表示されるので文字は入れず、仙人の顔だけ
export const ChannelIcon: React.FC = () => (
  <AbsoluteFill style={{ background: EMBER, overflow: 'hidden' }}>
    <Img src={staticFile('chara/cut/sennin_03_point.png')} style={{ position: 'absolute', width: 1250, height: 1250, left: -190, top: -10 }} />
  </AbsoluteFill>
);

// ───────────────────────── チャンネルのバナー（2560×1440） ─────────────────────────
// どの画面でも見えるのは中央の 1546×423 だけ。文字はそこに入れ、キャラは横に広げる（パソコンでは横幅いっぱいに見える）
export const ChannelBanner: React.FC = () => {
  const side: Who[] = ['nekketsu', 'megane', 'tsundere'];
  const side2: Who[] = ['osananajimi', 'ikemen', 'spartan'];
  return (
    <AbsoluteFill style={{ background: DOJO, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 0, right: 0, top: 508, height: 423, background: EMBER }} />
      <div style={{ position: 'absolute', left: 30, top: 520, display: 'flex' }}>
        {side.map((w) => <div key={w} style={{ width: 150 }}><Img src={staticFile(`chara/cut/${w}.png`)} style={{ width: 400, height: 400, marginLeft: -120 }} /></div>)}
      </div>
      <div style={{ position: 'absolute', right: 30, top: 520, display: 'flex', flexDirection: 'row-reverse' }}>
        {side2.map((w) => <div key={w} style={{ width: 150 }}><Img src={staticFile(`chara/cut/${w}.png`)} style={{ width: 400, height: 400, marginLeft: -120 }} /></div>)}
      </div>
      {/* 中央の安全な範囲（x 507〜2053, y 508〜931） */}
      <Img src={staticFile('chara/cut/sennin_03_point.png')} style={{ position: 'absolute', left: 500, top: 520, width: 410, height: 410 }} />
      <div style={{ position: 'absolute', left: 920, top: 560, width: 1120, fontFamily: DELA, lineHeight: 1 }}>
        <div style={{ fontSize: 118, color: CREAM, textShadow: SLAB(9), whiteSpace: 'nowrap' }}>気合イングリッシュ</div>
        <div style={{ fontFamily: ROUNDED, fontSize: 54, color: CREAM, marginTop: 34 }}>キャラと鍛える、受験の英単語・英文法</div>
        <div style={{ display: 'flex', gap: 18, marginTop: 28 }}>
          {['絵で英単語', 'キャラ解説', 'リスニング'].map((t) => (
            <span key={t} style={{ fontSize: 40, color: BROWN, background: GOLD, borderRadius: 999, padding: '8px 26px' }}>{t}</span>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
