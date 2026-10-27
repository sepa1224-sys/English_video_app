// 単語帳『気合の英単語 必修』の YouTube 広告（横長 1920×1080・約27秒）とそのサムネ（1280×720）。
// 中身（声・見開き・QR）は scripts/book_ad.py が用意して --props で { ad } を渡す。
// --props は全部の Composition に渡るので、ほかの動画と取り違えないよう data ではなく ad という名前にする。
// 飛ばせる広告は最初の5秒で決まるので、0秒目から表紙をドンと出し、仙人が「新しい英単語帳が出たぞ！」と言う。
import React from 'react';
import { AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import { DELA, ROUNDED } from '../fonts';
import { BROWN, CREAM, Chara, DOJO, EMBER, GOLD, QrCard, RED, SLAB, pop } from '../tango/Tango';

export type AdLine = { who: 'master'; line: string; audio: string; dur: number; at: number };
export type AdData = {
  scenes: number[]; // 場面ごとの長さ（コマ）：つかみ／中身／聞き流し・アプリ／無料の案内
  total: number;
  lines: AdLine[];
  spreads: string[]; // 稽古1の見開き（public からの道）
  arts: string[]; // 絵
  qr: string; // 無料見本への QR
};

export const AD_SAMPLE: AdData = {
  scenes: [150, 240, 210, 210], total: 810, lines: [],
  spreads: [], arts: ['tango/art/likely.jpg'], qr: 'tango/qr_yt_qr.png',
};

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const fade = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], clamp);
const talkingAt = (f: number, l?: AdLine) => !!l && f >= l.at && f < l.at + l.dur * 30;
const COVER = 'tango/cover.jpg';

// ───────── 1. つかみ（0〜5秒）：表紙が落ちてくる＋「新発売｜気合の英単語 必修」 ─────────
const Hook: React.FC<{ line?: AdLine; from: number }> = ({ line, from }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const slam = interpolate(f, [0, 9], [2.4, 1], { ...clamp, easing: Easing.in(Easing.quad) });
  const shake = f >= 9 && f < 19 ? Math.sin(f * 2.7) * (19 - f) * 1.6 : 0;
  const flash = interpolate(f, [9, 11, 18], [0, 0.55, 0], clamp);
  const talking = talkingAt(f + from, line);
  return (
    <AbsoluteFill style={{ background: EMBER, transform: `translate(${shake}px, ${shake * 0.6}px)` }}>
      <div style={{ position: 'absolute', left: 90, top: 110, width: 860 }}>
        <div style={{ display: 'inline-block', fontFamily: DELA, fontSize: 120, color: CREAM, background: RED, border: `8px solid ${CREAM}`,
          borderRadius: 24, padding: '6px 40px 18px', transform: `rotate(-5deg) scale(${pop(f, fps, 10)})`, boxShadow: '0 12px 0 rgba(60,0,0,0.45)' }}>
          新発売
        </div>
        <div style={{ fontFamily: DELA, fontSize: 132, color: CREAM, textShadow: SLAB(10), marginTop: 56, lineHeight: 1.1, whiteSpace: 'nowrap',
          opacity: fade(f, 14, 20), transform: `translateX(${(1 - pop(f, fps, 14)) * -120}px)` }}>
          <span style={{ color: GOLD }}>気合</span>の英単語
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 28, marginTop: 34, transform: `scale(${pop(f, fps, 22)})`, transformOrigin: 'left center' }}>
          <span style={{ fontFamily: DELA, fontSize: 120, color: RED, background: GOLD, border: `7px solid ${BROWN}`, borderRadius: 22,
            padding: '0 34px 14px' }}>必修</span>
          <span style={{ fontFamily: DELA, fontSize: 64, color: CREAM, textShadow: SLAB(5), lineHeight: 1.15 }}>大学入試<br />1000語</span>
        </div>
      </div>
      <Img src={staticFile(COVER)} style={{
        position: 'absolute', left: 960, top: 90, width: 540, height: 864, borderRadius: 18, border: `7px solid ${CREAM}`,
        boxShadow: '0 34px 70px rgba(60,0,0,0.6)', opacity: fade(f, 0, 3),
        transform: `scale(${slam}) rotate(${interpolate(f, [0, 9], [-12, 3], clamp)}deg)` }} />
      <div style={{ position: 'absolute', left: 1470, top: 560, transform: `translateY(${(1 - pop(f, fps, 6)) * 500}px)` }}>
        <Chara who="master" size={460} talking={talking} />
      </div>
      <AbsoluteFill style={{ background: '#fff', opacity: flash }} />
    </AbsoluteFill>
  );
};

// ───────── 2. 中身（5〜13秒）：1000語・全部イラストつき・100語ずつの稽古＋見開きをめくる ─────────
const Inside: React.FC<{ d: AdData; len: number }> = ({ d, len }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = Math.max(1, d.spreads.length);
  const per = len / n;
  const k = Math.min(n - 1, Math.floor(f / per));
  const t = f - k * per;
  const turn = interpolate(t, [0, 7], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const second = Math.round(len * 0.45);
  return (
    <AbsoluteFill style={{ background: DOJO }}>
      <div style={{ position: 'absolute', left: 80, top: 80, width: 800 }}>
        <div style={{ fontFamily: DELA, fontSize: 62, color: CREAM, lineHeight: 1.3, opacity: fade(f, 0, 8) }}>
          大学入試の過去問を<br />数えて選んだ
        </div>
        <div style={{ fontFamily: DELA, fontSize: 190, color: GOLD, textShadow: SLAB(12), lineHeight: 1.05, whiteSpace: 'nowrap',
          transform: `scale(${pop(f, fps, 8)})`, transformOrigin: 'left center' }}>
          1000<span style={{ fontSize: 110 }}>語</span>
        </div>
        <div style={{ marginTop: 40, opacity: fade(f, second, second + 6), transform: `translateX(${(1 - pop(f, fps, second)) * -80}px)` }}>
          <div style={{ fontFamily: DELA, fontSize: 84, color: CREAM, textShadow: SLAB(6), whiteSpace: 'nowrap' }}>全部イラストつき</div>
        </div>
        <div style={{ marginTop: 18, opacity: fade(f, second + 12, second + 18), transform: `translateX(${(1 - pop(f, fps, second + 12)) * -80}px)` }}>
          <div style={{ fontFamily: DELA, fontSize: 84, color: GOLD, textShadow: SLAB(6), whiteSpace: 'nowrap' }}>100語ずつの稽古</div>
        </div>
      </div>
      {/* 見開き（稽古1の本物のページ） */}
      {d.spreads.length > 0 && (
        <div style={{ position: 'absolute', left: 900, top: 70, width: 960, height: 682 }}>
          {k > 0 && (
            <Img src={staticFile(d.spreads[k - 1])} style={{ position: 'absolute', inset: 0, width: 960, height: 682, borderRadius: 10 }} />
          )}
          <Img src={staticFile(d.spreads[k])} style={{
            position: 'absolute', inset: 0, width: 960, height: 682, borderRadius: 10, boxShadow: '0 26px 50px rgba(0,0,0,0.55)',
            transform: k === 0 ? `scale(${0.9 + pop(f, fps, 0) * 0.1})` : `translateX(${(1 - turn) * 160}px) rotate(${(1 - turn) * 3}deg)`,
            opacity: k === 0 ? fade(f, 0, 6) : turn }} />
          <div style={{ position: 'absolute', right: -10, top: -26, fontFamily: DELA, fontSize: 40, color: BROWN, background: GOLD,
            borderRadius: 999, padding: '6px 26px', border: `4px solid ${BROWN}` }}>本の中身</div>
        </div>
      )}
      {/* 絵が並ぶ */}
      <div style={{ position: 'absolute', left: 900, top: 790, display: 'flex', gap: 22 }}>
        {d.arts.slice(0, 6).map((src, i) => (
          <div key={src} style={{ width: 142, height: 142, background: '#fff', borderRadius: 18, border: `5px solid ${CREAM}`, overflow: 'hidden',
            transform: `scale(${pop(f, fps, second + 4 + i * 4)}) rotate(${i % 2 ? 3 : -3}deg)` }}>
            <Img src={staticFile(src)} style={{ width: 132, height: 132 }} />
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ───────── 3. 本・YouTube・アプリで番号が同じ（13〜20秒） ─────────
const NoTag: React.FC<{ lit: number }> = ({ lit }) => (
  <span style={{ fontFamily: DELA, fontSize: 44, color: CREAM, background: RED, borderRadius: 12, padding: '2px 18px 8px',
    boxShadow: `0 0 0 ${lit * 8}px rgba(255,210,63,0.9)` }}>No.1</span>
);
const Card: React.FC<{ title: string; s: number; children: React.ReactNode }> = ({ title, s, children }) => (
  <div style={{ width: 540, height: 560, background: CREAM, borderRadius: 30, border: `7px solid ${BROWN}`, boxShadow: '0 14px 0 rgba(60,0,0,0.45)',
    display: 'flex', flexDirection: 'column', alignItems: 'center', transform: `scale(${s})` }}>
    <div style={{ fontFamily: DELA, fontSize: 50, color: BROWN, marginTop: 24, whiteSpace: 'nowrap' }}>{title}</div>
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 18 }}>{children}</div>
  </div>
);
const Sync: React.FC<{ d: AdData; len: number }> = ({ d, len }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const last = Math.round(len * 0.5);
  const lit = f >= last ? 0.5 + 0.5 * Math.sin((f - last) / 4) : 0;
  const art = d.arts[0];
  return (
    <AbsoluteFill style={{ background: EMBER }}>
      <div style={{ position: 'absolute', top: 54, width: '100%', textAlign: 'center', fontFamily: DELA, fontSize: 84, color: CREAM,
        textShadow: SLAB(7), whiteSpace: 'nowrap', opacity: fade(f, 0, 6) }}>
        <span style={{ color: GOLD }}>YouTube</span>で聞き流し・<span style={{ color: GOLD }}>アプリ</span>でテスト
      </div>
      <div style={{ position: 'absolute', top: 210, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 50 }}>
        <Card title="本" s={pop(f, fps, 4)}>
          <Img src={staticFile(COVER)} style={{ width: 210, height: 336, borderRadius: 8, border: `4px solid ${BROWN}` }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}><NoTag lit={lit} /><span style={{ fontFamily: ROUNDED, fontSize: 50, color: BROWN }}>likely</span></div>
        </Card>
        <Card title="YouTube 聞き流し" s={pop(f, fps, 12)}>
          <div style={{ position: 'relative', width: 440, height: 248, background: '#111', borderRadius: 16, overflow: 'hidden',
            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {art && <Img src={staticFile(art)} style={{ width: 230, height: 230 }} />}
            <div style={{ position: 'absolute', left: 168, top: 84, width: 104, height: 76, background: '#ff0033', borderRadius: 20,
              display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.95 }}>
              <div style={{ width: 0, height: 0, borderTop: '18px solid transparent', borderBottom: '18px solid transparent', borderLeft: `30px solid #fff`, marginLeft: 8 }} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}><NoTag lit={lit} /><span style={{ fontFamily: ROUNDED, fontSize: 50, color: BROWN }}>likely</span></div>
        </Card>
        <Card title="アプリ テスト" s={pop(f, fps, 20)}>
          <div style={{ width: 250, height: 380, background: '#fff', border: `10px solid ${BROWN}`, borderRadius: 38, display: 'flex',
            flexDirection: 'column', alignItems: 'center', padding: '22px 16px', gap: 12 }}>
            <NoTag lit={lit} />
            <div style={{ fontFamily: ROUNDED, fontSize: 46, color: BROWN }}>likely</div>
            {['ありそうな', '少ない', '研究'].map((c, i) => (
              <div key={c} style={{ width: '100%', textAlign: 'center', fontFamily: ROUNDED, fontSize: 28, borderRadius: 12, padding: '6px 0',
                color: i === 0 && f > last ? '#fff' : BROWN, background: i === 0 && f > last ? '#2e9d4a' : '#f1e6cc' }}>{c}</div>
            ))}
          </div>
        </Card>
      </div>
      <div style={{ position: 'absolute', top: 820, width: '100%', textAlign: 'center', fontFamily: DELA, fontSize: 132, color: GOLD,
        textShadow: SLAB(11), whiteSpace: 'nowrap', transform: `scale(${pop(f, fps, last)})` }}>番号が全部同じ！</div>
    </AbsoluteFill>
  );
};

// ───────── 4. 稽古1は無料（最後の約7秒）：ボタン風の字＋QR ─────────
const Free: React.FC<{ d: AdData; line?: AdLine; from: number }> = ({ d, line, from }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const talking = talkingAt(f + from, line);
  const beat = 1 + Math.max(0, Math.sin((f - 30) / 5)) * 0.04 * fade(f, 30, 36);
  return (
    <AbsoluteFill style={{ background: DOJO }}>
      <Img src={staticFile(COVER)} style={{ position: 'absolute', left: 70, top: 90, width: 390, height: 624, borderRadius: 14,
        border: `6px solid ${CREAM}`, boxShadow: '0 26px 50px rgba(0,0,0,0.6)', transform: `rotate(-3deg) translateY(${(1 - pop(f, fps, 0)) * 300}px)` }} />
      <div style={{ position: 'absolute', left: 90, top: 660 }}>
        <Chara who="master" size={380} talking={talking} />
      </div>
      <div style={{ position: 'absolute', left: 560, top: 200, width: 900 }}>
        <div style={{ fontFamily: DELA, fontSize: 92, color: CREAM, textShadow: SLAB(7), whiteSpace: 'nowrap', opacity: fade(f, 2, 8) }}>
          稽古1<span style={{ fontSize: 64 }}>（100語）</span>は
        </div>
        <div style={{ fontFamily: DELA, fontSize: 170, color: GOLD, textShadow: SLAB(12), lineHeight: 1.1, whiteSpace: 'nowrap',
          transform: `scale(${pop(f, fps, 8)})`, transformOrigin: 'left center' }}>無料じゃ！</div>
        <div style={{ marginTop: 50, display: 'inline-flex', alignItems: 'center', gap: 22, fontFamily: DELA, fontSize: 60, color: BROWN,
          background: GOLD, border: `7px solid ${BROWN}`, borderRadius: 999, padding: '18px 54px 26px', boxShadow: '0 12px 0 rgba(0,0,0,0.5)',
          whiteSpace: 'nowrap', transform: `scale(${pop(f, fps, 18) * beat})`, transformOrigin: 'left center' }}>
          稽古1 無料ダウンロード
          <span style={{ fontSize: 48, color: RED }}>▶</span>
        </div>
        <div style={{ marginTop: 56, fontFamily: ROUNDED, fontSize: 46, color: CREAM, opacity: fade(f, 30, 40), whiteSpace: 'nowrap' }}>
          Amazonで発売中 1,650円（税込）
        </div>
      </div>
      <QrCard qr={{ src: d.qr, label: '無料で稽古1', sub: 'スマホで読み取り' }} size={300}
        style={{ position: 'absolute', right: 60, top: 330, transform: `scale(${pop(f, fps, 24)})` }} />
    </AbsoluteFill>
  );
};

export const BookAd: React.FC<{ ad: AdData }> = ({ ad: d }) => {
  const f = useCurrentFrame();
  const [a, b, c, e] = d.scenes;
  const starts = [0, a, a + b, a + b + c];
  const bgm = interpolate(f, [0, 10, d.total - 30, d.total], [0, 0.08, 0.08, 0], clamp);
  return (
    <AbsoluteFill style={{ background: BROWN }}>
      {/* BGM は解説ショートと同じ自前の曲（ElevenLabs Music で作ったもの） */}
      <Audio src={staticFile('bgm/02_quest.mp3')} volume={bgm} loop />
      {d.lines.map((l, i) => l.audio ? <Sequence key={i} from={l.at}><Audio src={staticFile(l.audio)} /></Sequence> : null)}
      <Sequence durationInFrames={a}><Hook line={d.lines[0]} from={0} /></Sequence>
      <Sequence from={starts[1]} durationInFrames={b}><Inside d={d} len={b} /></Sequence>
      <Sequence from={starts[2]} durationInFrames={c}><Sync d={d} len={c} /></Sequence>
      <Sequence from={starts[3]} durationInFrames={e}><Free d={d} line={d.lines[3]} from={starts[3]} /></Sequence>
    </AbsoluteFill>
  );
};

// ───────── サムネ（1280×720） ─────────
export const BookAdThumb: React.FC<{ ad?: AdData }> = () => (
  <AbsoluteFill style={{ background: EMBER, overflow: 'hidden' }}>
    <Img src={staticFile(COVER)} style={{ position: 'absolute', left: 60, top: 40, width: 400, height: 640, borderRadius: 14,
      border: `7px solid ${CREAM}`, boxShadow: '0 24px 48px rgba(60,0,0,0.6)', transform: 'rotate(-3deg)' }} />
    <div style={{ position: 'absolute', left: 30, top: 18, fontFamily: DELA, fontSize: 70, color: CREAM, background: RED,
      border: `7px solid ${CREAM}`, borderRadius: 20, padding: '0 26px 10px', transform: 'rotate(-8deg)', boxShadow: '0 10px 0 rgba(60,0,0,0.45)' }}>
      新発売
    </div>
    <div style={{ position: 'absolute', left: 500, right: 20, top: 70, fontFamily: DELA, lineHeight: 1.05 }}>
      <div style={{ fontSize: 118, color: CREAM, textShadow: SLAB(9), whiteSpace: 'nowrap' }}><span style={{ color: GOLD }}>気合</span>の英単語</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginTop: 22 }}>
        <span style={{ fontSize: 100, color: RED, background: GOLD, border: `6px solid ${BROWN}`, borderRadius: 18, padding: '0 26px 12px' }}>必修</span>
        <span style={{ fontSize: 50, color: CREAM, textShadow: SLAB(5), lineHeight: 1.15 }}>大学入試<br />1000語</span>
      </div>
      <div style={{ display: 'inline-block', marginTop: 40, fontSize: 104, color: BROWN, background: GOLD, border: `7px solid ${BROWN}`,
        borderRadius: 999, padding: '4px 44px 18px', boxShadow: '0 10px 0 rgba(60,0,0,0.45)', whiteSpace: 'nowrap' }}>
        稽古1 <span style={{ color: RED }}>無料</span>
      </div>
    </div>
  </AbsoluteFill>
);
