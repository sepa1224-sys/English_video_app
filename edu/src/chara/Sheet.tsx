import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { Character, type Pose } from './Chibi';
import { PersonaFace, PERSONA_KEYS } from './Faces';

// キャラの見た目を一覧で確かめるための絵（動画には使わない）
const POSES: Pose[] = ['idle', 'talk', 'point', 'surprised', 'fist', 'arms'];
export const Sheet: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: '#fbf4ea', display: 'flex', flexWrap: 'wrap', padding: 30, gap: 10 }}>
      {POSES.map((p, i) => (
        <div key={p} style={{ position: 'relative', width: 300, height: 380 }}>
          <Character pose={p} frame={f + i * 7} amp={p === 'talk' ? 0.6 : p === 'fist' ? 0.8 : 0} />
          <div style={{ position: 'absolute', bottom: -6, width: '100%', textAlign: 'center', fontSize: 26, color: '#4a3530' }}>{p}</div>
        </div>
      ))}
      {PERSONA_KEYS.map((k, i) => (
        <div key={k} style={{ width: 220, height: 250, textAlign: 'center' }}>
          <PersonaFace who={k} frame={f + i * 11} amp={i % 2 ? 0.5 : 0} size={210} />
          <div style={{ fontSize: 24, color: '#4a3530' }}>{k}</div>
        </div>
      ))}
    </AbsoluteFill>
  );
};
