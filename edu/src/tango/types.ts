// 「イメージで英単語エクササイズ」の中身。tango_exercise.py が作って --props で渡す
import { FPS } from '../types';

export type Who = 'master' | 'nekketsu' | 'megane' | 'tsundere' | 'osananajimi' | 'ikemen' | 'spartan';
export type Line = { who: Who; line: string; audio: string; dur: number };
export type Word = {
  no: number; headword: string; pos: string; meanings: string[];
  hint: string[]; // 語ごとの頭文字ヒント（'l_____'）
  img: string; voice: string; voiceDur: number;
};
export type TangoData = {
  keiko: number; range: [number, number]; series: string;
  book: { label: string };
  intro: Line[]; howto: Line[]; outro: Line[];
  outroBook?: Line[]; // 締めの直前の「本の案内」カード（無ければ出さない＝以前の動画と同じ長さ）
  words: Word[]; thumbs: string[];
  thumbTop?: string; // サムネの題の1行目（既定「イメージで」）
  // 大学別（scripts/tango_group.py）など、稽古ではない100語のとき。無ければ今までどおり「稽古N」
  label?: string; // 「稽古N」の札の代わり（上の帯・サムネ）。サムネの No. の範囲も出さない
  outroTitle?: string; // 締めの大きい字（既定「稽古N 完了！」）
  bookOf?: string; bookBig?: string; // 本の案内カードの「の」「稽古N」の代わり
  // 締め（Outro と本の案内カード）に出す QR（2026-10-27 稽古1の無料見本へ）。無ければ出さない＝以前の動画と同じ見た目
  qr?: { src: string; label?: string; sub?: string };
};

// 聞き流し（英語→日本語）。時間割は tango_exercise.py が1回だけ計算してコマで渡す（ずれないように）
export type ListenWord = Word & { ja: { audio: string; dur: number }[] };
export type ListenPlan = {
  intro: number; // 冒頭の長さ（コマ）
  words: { start: number; len: number; ja: number[] }[]; // 語の始まり・長さ・意味を読み始めるコマ（語の頭から）
  outro: number; // 締めの始まり
  book?: number; // 本の案内カードの始まり（無ければ出さない）
  total: number;
};
export type ListenData = Omit<TangoData, 'words'> & { words: ListenWord[]; plan: ListenPlan };

// 1語の時間割（秒）。tango_exercise.py の timeline() と同じ式
export const THINK = 3.5; // 絵とヒントだけを見せる時間（最後の3秒が秒読み）
export const AFTER1 = 0.9; // 1回目の発音のあと（まねする間）
export const AFTER2 = 1.6; // 2回目の発音のあと
export const LINE_GAP = 0.35; // セリフとセリフの間

export const sec = (s: number) => Math.round(s * FPS);
export const wordLen = (w: Word) => THINK + 0.1 + w.voiceDur + AFTER1 + w.voiceDur + AFTER2;
export const linesLen = (ls: Line[]) => ls.reduce((n, l) => n + l.dur + LINE_GAP, 0) + 0.6;
export const introLen = (d: TangoData) => Math.max(3, linesLen(d.intro)); // 冒頭は短く（一言だけ）

export const BOOK_CARD_MIN = 5; // 本の案内カードの最短（秒）
export const bookLen = (d: { outroBook?: Line[] }) =>
  d.outroBook?.length ? sec(Math.max(BOOK_CARD_MIN, linesLen(d.outroBook) + 0.8)) : 0;

export const sections = (d: TangoData) => {
  const intro = sec(introLen(d));
  const howto = sec(linesLen(d.howto));
  const words = d.words.map((w) => sec(wordLen(w)));
  const outro = sec(linesLen(d.outro) + 1.5);
  const wordsTotal = words.reduce((a, b) => a + b, 0);
  const book = bookLen(d);
  return { intro, howto, words, wordsTotal, outro, book, total: intro + howto + wordsTotal + outro + book };
};
