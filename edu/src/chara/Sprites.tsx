import React from 'react';
import { Img, staticFile } from 'remotion';

// Canva で作ったレトロゲーム風のキャラ（public/chara/cut/*.png、白背景を切り抜き済み）。
// 仙人（マスター）は構えごとに「口を閉じた絵／開けた絵」を持ち、声の大きさで切り替えて口パクにする。
// どの絵も同じ大きさ・同じ位置で描かれているので、差し替えてもキャラはずれない。

export type SenninPose = 'idle' | 'talk' | 'point' | 'surprised' | 'laugh' | 'fist' | 'arms';

const SENNIN: Record<SenninPose | 'fever', [string, string]> = {
  idle: ['sennin_01_idle', 'sennin_02_idle_open'],
  talk: ['sennin_01_idle', 'sennin_02_idle_open'],
  arms: ['sennin_01_idle', 'sennin_02_idle_open'],
  point: ['sennin_03_point', 'sennin_04_point_open'],
  fist: ['sennin_03_point', 'sennin_04_point_open'],
  surprised: ['sennin_05_surprised', 'sennin_05_surprised'], // 驚き・大笑いは口が開いた絵しかない
  laugh: ['sennin_06_laugh', 'sennin_06_laugh'],
  fever: ['sennin_07_fever', 'sennin_08_fever_open'],
};

/** 声の大きさ amp（0〜1）が一定を超えたら口を開けた絵。数コマごとにしか変えない（パカパカしすぎない） */
export const Sennin: React.FC<{ pose: SenninPose; fever: boolean; amp: number; size: number }> = ({ pose, fever, amp, size }) => {
  const [closed, open] = SENNIN[fever ? 'fever' : pose] ?? SENNIN.idle;
  const name = amp > 0.18 ? open : closed;
  return <Img src={staticFile(`chara/cut/${name}.png`)} style={{ width: size, height: size, imageRendering: 'auto' }} />;
};

export const STUDENT_FILES: Record<string, string> = {
  nekketsu: 'nekketsu', megane: 'megane', tsundere: 'tsundere',
  osananajimi: 'osananajimi', ikemen: 'ikemen', spartan: 'spartan',
};

/** 弟子（全身1枚）。話している間は弾ませて「しゃべっている」ことを見せる */
export const Student: React.FC<{ who: string; size: number; amp: number; local: number }> = ({ who, size, amp, local }) => {
  const hop = amp > 0.15 ? -Math.abs(Math.sin(local / 3)) * size * 0.025 : 0;
  return (
    <Img src={staticFile(`chara/cut/${STUDENT_FILES[who] ?? 'nekketsu'}.png`)}
      style={{ width: size, height: size, transform: `translateY(${hop}px)` }} />
  );
};
