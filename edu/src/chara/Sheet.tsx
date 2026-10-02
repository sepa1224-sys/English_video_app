import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { Character, type Pose } from './Fighter';

// 見た目の候補を並べて比べるための絵（動画には使わない）
const ROWS: [string, string][] = [['sensei', 'A 道場の師範'], ['young', 'B 若き武道家'], ['indigo', 'C 藍の拳士']];
const POSES: Pose[] = ['idle', 'talk', 'point', 'fist'];
export const Sheet: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: '#d9d4cc', padding: 20 }}>
      {ROWS.map(([look, name]) => (
        <div key={look} style={{ display: 'flex', alignItems: 'flex-end', gap: 10, height: 660 }}>
          <div style={{ width: 200, fontSize: 40, fontWeight: 800, color: '#333' }}>{name}</div>
          {POSES.map((p, i) => (
            <div key={p} style={{ position: 'relative', width: 340, height: 640 }}>
              <Character look={look} pose={p} frame={f + i * 7} amp={p === 'talk' ? 0.6 : p === 'fist' ? 0.8 : 0} scale={4} />
            </div>
          ))}
        </div>
      ))}
    </AbsoluteFill>
  );
};
