// 単語帳『気合の英単語 必修』の15秒の YouTube 広告。横長（1920×1080・動画の前に流れる広告）と縦長（1080×1920・ショートの広告）の2つを
// 同じ中身から作る（縦か横かは useVideoConfig の幅と高さで決める）。中身は scripts/book_ad15.py が用意して --props で { ad15 } を渡す。
// 27秒版（BookAd.tsx）との違い：飛ばされる前の最初の3秒で「共通テストの英文の単語が93%分かる」という数字を出す。最後は Amazon と値段。
// 数字は kiai-coaching-app の lib/tango-coverage.json（本・サイトと同じ。2026年の共通テストの本文で、中学の単語80%→この1000語を足して93%）。
import React from 'react';
import { AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import { DELA, ROUNDED } from '../fonts';
import { BROWN, CREAM, Chara, DOJO, EMBER, GOLD, QrCard, RED, SLAB, pop } from '../tango/Tango';

export type Ad15Line = { who: 'master'; line: string; audio: string; dur: number; at: number };
export type Ad15Data = {
  scenes: number[]; // つかみ（数字）／中身／本・YouTube・アプリ／Amazon（コマ）
  total: number;
  lines: Ad15Line[];
  spreads: string[];
  arts: string[];
  qr: string;
  base: number; // 中学の単語だけで分かる割合（切り捨て）
  w1000: number; // この1000語を足したとき
  year: number;
  paper: string; // 紙の本の値段（「1,650円」）
  kindle: string;
};

export const AD15_SAMPLE: Ad15Data = {
  scenes: [120, 120, 100, 110], total: 450, lines: [], spreads: [], arts: ['tango/art/likely.jpg'], qr: 'tango/qr_yt_ad15.png',
  base: 80, w1000: 93, year: 2026, paper: '1,650円', kindle: '1,200円',
};

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const fade = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], clamp);
const talkingAt = (f: number, l?: Ad15Line) => !!l && f >= l.at && f < l.at + l.dur * 30;
const COVER = 'tango/cover.jpg';
const useV = () => {
  const { width, height } = useVideoConfig();
  return height > width;
};

// ───────── 1. つかみ：表紙が落ちてきて、80% → 93% と数字が上がる ─────────
const Hook: React.FC<{ d: Ad15Data; line?: Ad15Line }> = ({ d, line }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const v = useV();
  const slam = interpolate(f, [0, 9], [2.3, 1], { ...clamp, easing: Easing.in(Easing.quad) });
  const shake = f >= 9 && f < 18 ? Math.sin(f * 2.7) * (18 - f) * 1.5 : 0;
  const count = Math.round(interpolate(f, [16, 46], [d.base, d.w1000], { ...clamp, easing: Easing.out(Easing.cubic) }));
  const hit = interpolate(f, [46, 50, 58], [1, 1.12, 1], clamp);
  const talking = talkingAt(f, line);

  const text = (
    <div style={{ fontFamily: DELA, color: CREAM, textShadow: SLAB(v ? 8 : 9) }}>
      <div style={{ fontSize: v ? 60 : 58, lineHeight: 1.3, opacity: fade(f, 4, 10), whiteSpace: 'nowrap' }}>
        共通テストの英文の
        <br />
        単語が
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', whiteSpace: 'nowrap', transform: `scale(${pop(f, fps, 12) * hit})`, transformOrigin: v ? 'center' : 'left center',
        justifyContent: v ? 'center' : 'flex-start' }}>
        <span style={{ fontSize: v ? 300 : 290, color: GOLD, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{count}</span>
        <span style={{ fontSize: v ? 150 : 140, color: GOLD }}>%</span>
        <span style={{ fontSize: v ? 96 : 92, marginLeft: 18 }}>分かる</span>
      </div>
      <div style={{ marginTop: v ? 18 : 10, fontSize: v ? 50 : 46, opacity: fade(f, 50, 58), whiteSpace: 'nowrap' }}>
        中学の単語＋<span style={{ color: GOLD }}>この1000語</span>で
      </div>
    </div>
  );
  const note = (
    <div style={{ fontFamily: ROUNDED, fontSize: v ? 26 : 24, color: CREAM, opacity: 0.85 * fade(f, 50, 60) }}>
      ※{d.year}年の共通テスト英語の本文で、分かる単語の割合を集計（中学の単語だけでは{d.base}%）。気合イングリッシュ調べ
    </div>
  );
  return (
    <AbsoluteFill style={{ background: EMBER, transform: `translate(${shake}px, ${shake * 0.6}px)` }}>
      {v ? (
        <>
          <div style={{ position: 'absolute', top: 190, left: 0, right: 0, textAlign: 'center' }}>{text}</div>
          <div style={{ position: 'absolute', left: 70, right: 70, top: 800, textAlign: 'center' }}>{note}</div>
          <Img src={staticFile(COVER)} style={{ position: 'absolute', left: 300, top: 920, width: 375, height: 600, borderRadius: 16,
            border: `7px solid ${CREAM}`, boxShadow: '0 30px 60px rgba(60,0,0,0.6)', opacity: fade(f, 0, 3),
            transform: `scale(${slam}) rotate(${interpolate(f, [0, 9], [-12, -4], clamp)}deg)` }} />
          <div style={{ position: 'absolute', left: 610, top: 1140, transform: `translateY(${(1 - pop(f, fps, 6)) * 600}px)` }}>
            <Chara who="master" size={370} talking={talking} />
          </div>
        </>
      ) : (
        <>
          <div style={{ position: 'absolute', left: 90, top: 120 }}>{text}</div>
          <Img src={staticFile(COVER)} style={{ position: 'absolute', left: 1130, top: 100, width: 500, height: 800, borderRadius: 18,
            border: `7px solid ${CREAM}`, boxShadow: '0 34px 70px rgba(60,0,0,0.6)', opacity: fade(f, 0, 3),
            transform: `scale(${slam}) rotate(${interpolate(f, [0, 9], [-12, 3], clamp)}deg)` }} />
          <div style={{ position: 'absolute', left: 1500, top: 600, transform: `translateY(${(1 - pop(f, fps, 6)) * 500}px)` }}>
            <Chara who="master" size={430} talking={talking} />
          </div>
          <div style={{ position: 'absolute', left: 90, bottom: 44, width: 1000 }}>{note}</div>
        </>
      )}
    </AbsoluteFill>
  );
};

// ───────── 2. 中身：出る順1000語・全部イラストつき＋本物の見開きをめくる ─────────
const Inside: React.FC<{ d: Ad15Data; len: number }> = ({ d, len }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const v = useV();
  const n = Math.max(1, d.spreads.length);
  const per = len / n;
  const k = Math.min(n - 1, Math.floor(f / per));
  const turn = interpolate(f - k * per, [0, 7], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const second = Math.round(len * 0.35);
  const sw = v ? 960 : 960;
  const sh = Math.round(sw * 0.71);
  const spread = d.spreads.length > 0 && (
    <div style={{ position: 'relative', width: sw, height: sh }}>
      {k > 0 && <Img src={staticFile(d.spreads[k - 1])} style={{ position: 'absolute', inset: 0, width: sw, height: sh, borderRadius: 10 }} />}
      <Img src={staticFile(d.spreads[k])} style={{ position: 'absolute', inset: 0, width: sw, height: sh, borderRadius: 10, boxShadow: '0 26px 50px rgba(0,0,0,0.55)',
        transform: k === 0 ? `scale(${0.9 + pop(f, fps, 0) * 0.1})` : `translateX(${(1 - turn) * 160}px) rotate(${(1 - turn) * 3}deg)`,
        opacity: k === 0 ? fade(f, 0, 6) : turn }} />
      <div style={{ position: 'absolute', right: -10, top: -26, fontFamily: DELA, fontSize: 40, color: BROWN, background: GOLD,
        borderRadius: 999, padding: '6px 26px', border: `4px solid ${BROWN}` }}>本の中身</div>
    </div>
  );
  const arts = (
    <div style={{ display: 'flex', gap: v ? 18 : 22, justifyContent: 'center' }}>
      {d.arts.slice(0, v ? 5 : 6).map((src, i) => (
        <div key={src} style={{ width: v ? 150 : 142, height: v ? 150 : 142, background: '#fff', borderRadius: 18, border: `5px solid ${CREAM}`, overflow: 'hidden',
          transform: `scale(${pop(f, fps, second + 4 + i * 3)}) rotate(${i % 2 ? 3 : -3}deg)` }}>
          <Img src={staticFile(src)} style={{ width: '100%', height: '100%' }} />
        </div>
      ))}
    </div>
  );
  const title = (
    <div style={{ fontFamily: DELA, textAlign: v ? 'center' : 'left' }}>
      <div style={{ fontSize: v ? 70 : 62, color: CREAM, opacity: fade(f, 0, 6), whiteSpace: 'nowrap' }}>入試に出る順の</div>
      <div style={{ fontSize: v ? 210 : 190, color: GOLD, textShadow: SLAB(12), lineHeight: 1.05, whiteSpace: 'nowrap',
        transform: `scale(${pop(f, fps, 4)})`, transformOrigin: v ? 'center' : 'left center' }}>
        1000<span style={{ fontSize: v ? 120 : 110 }}>語</span>
      </div>
      <div style={{ marginTop: 22, fontSize: v ? 92 : 84, color: CREAM, textShadow: SLAB(6), whiteSpace: 'nowrap',
        opacity: fade(f, second, second + 6), transform: `translateY(${(1 - pop(f, fps, second)) * 40}px)` }}>全部イラストつき</div>
    </div>
  );
  return (
    <AbsoluteFill style={{ background: DOJO }}>
      {v ? (
        <>
          <div style={{ position: 'absolute', top: 150, left: 0, right: 0 }}>{title}</div>
          <div style={{ position: 'absolute', top: 650, left: 0, right: 0 }}>{arts}</div>
          <div style={{ position: 'absolute', top: 880, left: 60 }}>{spread}</div>
        </>
      ) : (
        <>
          <div style={{ position: 'absolute', left: 80, top: 110 }}>{title}</div>
          <div style={{ position: 'absolute', left: 900, top: 70 }}>{spread}</div>
          <div style={{ position: 'absolute', left: 900, top: 800 }}>{arts}</div>
        </>
      )}
    </AbsoluteFill>
  );
};

// ───────── 3. 本・YouTube・アプリで番号が同じ ─────────
const NoTag: React.FC<{ lit: number; size?: number }> = ({ lit, size = 44 }) => (
  <span style={{ fontFamily: DELA, fontSize: size, color: CREAM, background: RED, borderRadius: 12, padding: '2px 18px 8px',
    boxShadow: `0 0 0 ${lit * 8}px rgba(255,210,63,0.9)` }}>No.1</span>
);
const Sync: React.FC<{ d: Ad15Data; len: number }> = ({ d, len }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const v = useV();
  const last = Math.round(len * 0.45);
  const lit = f >= last ? 0.5 + 0.5 * Math.sin((f - last) / 4) : 0;
  const art = d.arts[0];
  // 横は3枚を横に、縦は「絵＋文字」の帯を3本たてに並べる
  const items: { title: string; body: React.ReactNode }[] = [
    { title: '本で覚える', body: <Img src={staticFile(COVER)} style={{ width: v ? 120 : 190, height: v ? 192 : 304, borderRadius: 8, border: `4px solid ${BROWN}` }} /> },
    {
      title: 'YouTubeで聞く',
      body: (
        <div style={{ position: 'relative', width: v ? 230 : 400, height: v ? 130 : 225, background: '#111', borderRadius: 16, overflow: 'hidden',
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {art && <Img src={staticFile(art)} style={{ height: '92%' }} />}
          <div style={{ position: 'absolute', width: v ? 64 : 100, height: v ? 46 : 72, background: '#ff0033', borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 0, height: 0, borderTop: `${v ? 11 : 17}px solid transparent`, borderBottom: `${v ? 11 : 17}px solid transparent`, borderLeft: `${v ? 19 : 28}px solid #fff`, marginLeft: 6 }} />
          </div>
        </div>
      ),
    },
    {
      title: 'アプリでテスト',
      body: (
        <div style={{ width: v ? 170 : 230, background: '#fff', border: `${v ? 7 : 9}px solid ${BROWN}`, borderRadius: 30, display: 'flex',
          flexDirection: 'column', alignItems: 'center', padding: v ? '12px 10px' : '18px 14px', gap: v ? 6 : 10 }}>
          <div style={{ fontFamily: ROUNDED, fontSize: v ? 32 : 42, color: BROWN }}>likely</div>
          {['ありそうな', '少ない'].map((c, i) => (
            <div key={c} style={{ width: '100%', textAlign: 'center', fontFamily: ROUNDED, fontSize: v ? 22 : 28, borderRadius: 10, padding: '5px 0',
              color: i === 0 && f > last ? '#fff' : BROWN, background: i === 0 && f > last ? '#2e9d4a' : '#f1e6cc' }}>{c}</div>
          ))}
        </div>
      ),
    },
  ];
  return (
    <AbsoluteFill style={{ background: EMBER }}>
      <div style={{ position: 'absolute', top: v ? 130 : 60, width: '100%', textAlign: 'center', fontFamily: DELA, fontSize: v ? 88 : 80, color: CREAM,
        textShadow: SLAB(7), lineHeight: 1.25, opacity: fade(f, 0, 6) }}>
        本・<span style={{ color: GOLD }}>YouTube</span>・<span style={{ color: GOLD }}>アプリ</span>
        {v ? <br /> : ' '}がつながる
      </div>
      <div style={{ position: 'absolute', top: v ? 400 : 220, left: 0, right: 0, display: 'flex', flexDirection: v ? 'column' : 'row',
        alignItems: 'center', justifyContent: 'center', gap: v ? 30 : 46 }}>
        {items.map((it, i) => (
          <div key={it.title} style={{ width: v ? 900 : 520, height: v ? 280 : 520, background: CREAM, borderRadius: 30, border: `7px solid ${BROWN}`,
            boxShadow: '0 14px 0 rgba(60,0,0,0.45)', display: 'flex', flexDirection: v ? 'row' : 'column', alignItems: 'center',
            justifyContent: v ? 'flex-start' : 'center', gap: v ? 36 : 20, padding: v ? '0 40px' : 0, transform: `scale(${pop(f, fps, 3 + i * 6)})` }}>
            <div style={{ width: v ? 240 : 'auto', display: 'flex', justifyContent: 'center' }}>{it.body}</div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: v ? 'flex-start' : 'center', gap: 14 }}>
              <div style={{ fontFamily: DELA, fontSize: v ? 58 : 48, color: BROWN, whiteSpace: 'nowrap' }}>{it.title}</div>
              <NoTag lit={lit} size={v ? 40 : 40} />
            </div>
          </div>
        ))}
      </div>
      <div style={{ position: 'absolute', top: v ? 1330 : 830, width: '100%', textAlign: 'center', fontFamily: DELA, fontSize: v ? 120 : 124, color: GOLD,
        textShadow: SLAB(11), whiteSpace: 'nowrap', transform: `scale(${pop(f, fps, last)})` }}>番号が全部同じ！</div>
    </AbsoluteFill>
  );
};

// ───────── 4. Amazon で発売中（最後）：表紙・値段・紹介ページへのボタン ─────────
const Buy: React.FC<{ d: Ad15Data; line?: Ad15Line; from: number }> = ({ d, line, from }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const v = useV();
  const talking = talkingAt(f + from, line);
  const beat = 1 + Math.max(0, Math.sin((f - 24) / 5)) * 0.04 * fade(f, 24, 30);
  const price = (label: string, yen: string, delay: number) => (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, opacity: fade(f, delay, delay + 6), whiteSpace: 'nowrap' }}>
      <span style={{ fontFamily: DELA, fontSize: v ? 40 : 46, color: CREAM }}>{label}</span>
      <span style={{ fontFamily: DELA, fontSize: v ? 68 : 76, color: GOLD, textShadow: SLAB(6) }}>{yen}</span>
    </div>
  );
  const block = (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: v ? 'center' : 'flex-start' }}>
      <div style={{ fontFamily: DELA, fontSize: v ? 92 : 96, color: CREAM, textShadow: SLAB(8), whiteSpace: 'nowrap', opacity: fade(f, 0, 6) }}>
        <span style={{ color: GOLD }}>気合</span>の英単語
      </div>
      <div style={{ fontFamily: DELA, fontSize: v ? 104 : 120, color: GOLD, textShadow: SLAB(11), lineHeight: 1.15, whiteSpace: 'nowrap',
        transform: `scale(${pop(f, fps, 6)})`, transformOrigin: v ? 'center' : 'left center' }}>Amazonで発売中</div>
      <div style={{ display: 'flex', gap: v ? 34 : 46, marginTop: 18 }}>
        {price('紙の本', d.paper, 14)}
        {price('Kindle', d.kindle, 18)}
      </div>
      <div style={{ marginTop: v ? 40 : 40, display: 'inline-flex', alignItems: 'center', gap: 20, fontFamily: DELA, fontSize: v ? 46 : 50, color: BROWN,
        background: GOLD, border: `7px solid ${BROWN}`, borderRadius: 999, padding: '16px 48px 24px', boxShadow: '0 12px 0 rgba(0,0,0,0.5)',
        whiteSpace: 'nowrap', transform: `scale(${pop(f, fps, 22) * beat})` }}>
        稽古1（100語）を無料で見る
        <span style={{ fontSize: 42, color: RED }}>▶</span>
      </div>
    </div>
  );
  return (
    <AbsoluteFill style={{ background: DOJO }}>
      {v ? (
        <>
          <Img src={staticFile(COVER)} style={{ position: 'absolute', left: 330, top: 150, width: 420, height: 672, borderRadius: 14,
            border: `6px solid ${CREAM}`, boxShadow: '0 26px 50px rgba(0,0,0,0.6)', transform: `rotate(-3deg) translateY(${(1 - pop(f, fps, 0)) * 300}px)` }} />
          <div style={{ position: 'absolute', left: 0, right: 0, top: 880 }}>{block}</div>
          <div style={{ position: 'absolute', left: 700, top: 560 }}>
            <Chara who="master" size={330} talking={talking} />
          </div>
        </>
      ) : (
        <>
          <Img src={staticFile(COVER)} style={{ position: 'absolute', left: 70, top: 90, width: 390, height: 624, borderRadius: 14,
            border: `6px solid ${CREAM}`, boxShadow: '0 26px 50px rgba(0,0,0,0.6)', transform: `rotate(-3deg) translateY(${(1 - pop(f, fps, 0)) * 300}px)` }} />
          <div style={{ position: 'absolute', left: 90, top: 660 }}>
            <Chara who="master" size={380} talking={talking} />
          </div>
          <div style={{ position: 'absolute', left: 540, top: 150 }}>{block}</div>
          <QrCard qr={{ src: d.qr, label: '紹介ページ', sub: 'スマホで読み取り' }} size={260}
            style={{ position: 'absolute', right: 60, top: 640, transform: `scale(${pop(f, fps, 26)})` }} />
        </>
      )}
    </AbsoluteFill>
  );
};

export const BookAd15: React.FC<{ ad15: Ad15Data }> = ({ ad15: d }) => {
  const f = useCurrentFrame();
  const [a, b, c, e] = d.scenes;
  const starts = [0, a, a + b, a + b + c];
  const bgm = interpolate(f, [0, 8, d.total - 20, d.total], [0, 0.08, 0.08, 0], clamp);
  return (
    <AbsoluteFill style={{ background: BROWN }}>
      <Audio src={staticFile('bgm/02_quest.mp3')} volume={bgm} loop />
      {d.lines.map((l, i) => (l.audio ? <Sequence key={i} from={l.at}><Audio src={staticFile(l.audio)} /></Sequence> : null))}
      <Sequence durationInFrames={a}><Hook d={d} line={d.lines[0]} /></Sequence>
      <Sequence from={starts[1]} durationInFrames={b}><Inside d={d} len={b} /></Sequence>
      <Sequence from={starts[2]} durationInFrames={c}><Sync d={d} len={c} /></Sequence>
      <Sequence from={starts[3]} durationInFrames={e}><Buy d={d} line={d.lines[3]} from={starts[3]} /></Sequence>
    </AbsoluteFill>
  );
};
