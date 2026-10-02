import { Composition } from 'remotion';
import { Episode } from './Episode';
import { Sheet } from './chara/Sheet';
import { FPS, totalFrames, type Episode as Ep } from './types';

// 台本は書き出し時に --props で渡す（scripts/render.mjs）。長さは台本から決める
const SAMPLE: Ep = {
  id: 'sample', format: 'short', kind: 'grammar', title: 'サンプル',
  beats: [{ id: 'b01', who: 'master', line: 'これは見本じゃ。', pose: 'talk', visual: { kind: 'title', text: '見本' } }],
};

const meta = ({ props }: { props: { episode: Ep } }) => ({ durationInFrames: totalFrames(props.episode) });

export const Root = () => (
  <>
    <Composition id="EduShort" component={Episode} defaultProps={{ episode: SAMPLE }}
      width={1080} height={1920} fps={FPS} durationInFrames={90} calculateMetadata={meta} />
    <Composition id="EduLong" component={Episode} defaultProps={{ episode: { ...SAMPLE, format: 'long' as const } }}
      width={1920} height={1080} fps={FPS} durationInFrames={90} calculateMetadata={meta} />
    <Composition id="CharaSheet" component={Sheet} width={1620} height={2020} fps={FPS} durationInFrames={60} />
  </>
);
