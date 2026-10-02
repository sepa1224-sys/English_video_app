import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { Character, type Pose } from './Fighter';

// キャラの見た目を一覧で確かめるための絵（動画には使わない）
const POSES: Pose[] = ['idle', 'talk', 'point', 'surprised', 'fist', 'arms'];
export const Sheet: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: '#d9d4cc', display: 'flex', flexWrap: 'wrap', padding: 30, gap: 20 }}>
      {POSES.map((p, i) => (
        <div key={p} style={{ position: 'relative', width: 340, height: 620 }}>
          <Character pose={p} frame={f + i * 7} amp={p === 'talk' ? 0.6 : p === 'fist' ? 0.8 : 0} scale={4} />
          <div style={{ position: 'absolute', top: 0, width: '100%', textAlign: 'center', fontSize: 26, color: '#333' }}>{p}</div>
        </div>
      ))}
    </AbsoluteFill>
  );
};
