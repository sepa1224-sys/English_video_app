// 解説動画の台本（エピソード）。edu_script.py が Claude に書かせ、scripts/voice.mjs が声を付ける。
// 1ビート = 1人の1セリフ。画面（visual）は書いたビートから切り替わり、書かないビートでは前のものが残る。

export type Speaker =
  | 'master' | 'spartan' | 'ikemen' | 'tsundere' | 'osananajimi' | 'megane' | 'nekketsu';

export type Label = 'S' | 'V' | 'O' | 'C' | 'M' | '+' | '';
export type Chunk = { w: string; l: Label };

export type Visual =
  | { kind: 'title'; text: string; sub?: string }
  | { kind: 'word'; en: string; ja: string; pos?: string; note?: string }
  | { kind: 'image'; emoji: string; label?: string }
  // 意味のかたまりごとに色分けした英文。順に飛び出す。mark は丸で囲むかたまりの番号（0始まり）
  | { kind: 'sentence'; chunks: Chunk[]; ja?: string; mark?: number[] }
  // 間違い → ×のハンコ → 正しい文
  | { kind: 'wrong'; wrong: string; right: string; why?: string }
  | { kind: 'compare'; a: { label: string; en: string; ja?: string }; b: { label: string; en: string; ja?: string } }
  | { kind: 'rule'; title?: string; lines: string[] }
  // クイズ。reveal が false のビートで考えさせ（think 秒）、true のビートで答えを光らせる
  | { kind: 'quiz'; q: string; choices: string[]; answer: number; reveal?: boolean }
  | { kind: 'none' };

export type Beat = {
  id: string;
  who: Speaker;
  line: string; // 読み上げる日本語（セリフ）
  en?: string; // セリフのあとに英語の声で読む英文（例文など）
  caption?: string; // 字幕。無ければ line（＋en）をそのまま出す
  pose?: 'idle' | 'talk' | 'point' | 'surprised' | 'fist' | 'arms'; // マスターの構え
  visual?: Visual;
  think?: number; // 声のあとに足す秒数（クイズの考える時間など）
  // voice.mjs が書き込む
  dur?: number; // 声の長さ（秒）
  env?: number[]; // 1コマごとの声の大きさ 0〜1（口パク用）
};

export type Episode = {
  id: string;
  format: 'short' | 'long';
  kind: 'word' | 'grammar';
  title: string; // 画面上部に出す題（短く）
  series?: string; // 「3分文法」など。左上のバッジ
  beats: Beat[];
};

export const FPS = 30;
export const TAIL = 1.0; // 最後のビートのあとの余韻（秒）

export const beatFrames = (b: Beat) =>
  Math.round(((b.dur ?? Math.max(1.6, b.line.length / 7)) + 0.3 + (b.think ?? 0)) * FPS);

export const totalFrames = (ep: Episode) =>
  ep.beats.reduce((n, b) => n + beatFrames(b), 0) + Math.round(TAIL * FPS);
