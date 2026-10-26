import { Composition } from 'remotion';
import { Episode } from './Episode';
import { Sheet } from './chara/Sheet';
import { FPS, totalFrames, type Episode as Ep } from './types';
import { ChannelBanner, ChannelIcon, TangoExercise, TangoThumb } from './tango/Tango';
import { TangoGroupThumb } from './tango/GroupThumb';
import { TangoListen } from './tango/Listen';
import { TangoQuiz, type QuizData } from './tango/Quiz';
import { sections, type ListenData, type TangoData } from './tango/types';

// 台本は書き出し時に --props で渡す（scripts/render.mjs）。長さは台本から決める
const SAMPLE: Ep = {
  id: 'sample', format: 'short', kind: 'grammar', title: 'サンプル',
  beats: [{ id: 'b01', who: 'master', line: 'これは見本じゃ。', pose: 'talk', visual: { kind: 'title', text: '見本' } }],
};

const meta = ({ props }: { props: { episode: Ep } }) => ({ durationInFrames: totalFrames(props.episode) });

// イメージで英単語エクササイズ。中身は tango_exercise.py が --props で渡す
const TANGO_SAMPLE: TangoData = {
  keiko: 1, range: [1, 1], series: 'イメージで英単語エクササイズ', book: { label: '近日発売' },
  intro: [], howto: [], outro: [], thumbs: ['tango/art/likely.jpg'],
  words: [{ no: 1, headword: 'likely', pos: '形', meanings: ['ありそうな、～しそうだ'], hint: ['l_____'],
    img: 'tango/art/likely.jpg', voice: 'tango/voice/likely.mp3', voiceDur: 0.6 }],
};
const tangoMeta = ({ props }: { props: { data: TangoData } }) => ({ durationInFrames: sections(props.data).total });
const LISTEN_SAMPLE: ListenData = {
  ...TANGO_SAMPLE, words: TANGO_SAMPLE.words.map((w) => ({ ...w, ja: [] })),
  plan: { intro: 0, words: [{ start: 0, len: 90, ja: [30] }], outro: 90, total: 90 },
};
// 3秒クイズ（縦長ショート）。中身は tango_quiz.py が --props で渡す
const QUIZ_SAMPLE: QuizData = {
  mode: 'word', badge: '気合の英単語 必修', title: ['3秒で', '意味を言える？'], outro: [], outroTitle: '何問言えた？', outroSub: 'コメントで教えてね',
  items: [{ q: 'likely', pos: '形', a: ['ありそうな、～しそうだ'] }],
  plan: { items: [{ start: 0, len: 150, think: 20, reveal: 110 }], outro: 150, total: 210 },
};
// --props はすべての Composition に渡るので、別の動画の中身（plan が無い）でも落ちないようにする
const quizMeta = ({ props }: { props: { data: QuizData } }) => ({ durationInFrames: props.data.plan?.total ?? 90 });
const listenMeta = ({ props }: { props: { data: ListenData } }) => ({ durationInFrames: props.data.plan?.total ?? 90 });

export const Root = () => (
  <>
    <Composition id="EduShort" component={Episode} defaultProps={{ episode: SAMPLE }}
      width={1080} height={1920} fps={FPS} durationInFrames={90} calculateMetadata={meta} />
    <Composition id="EduLong" component={Episode} defaultProps={{ episode: { ...SAMPLE, format: 'long' as const } }}
      width={1920} height={1080} fps={FPS} durationInFrames={90} calculateMetadata={meta} />
    <Composition id="TangoExercise" component={TangoExercise} defaultProps={{ data: TANGO_SAMPLE }}
      width={1920} height={1080} fps={FPS} durationInFrames={90} calculateMetadata={tangoMeta} />
    <Composition id="TangoListen" component={TangoListen} defaultProps={{ data: LISTEN_SAMPLE }}
      width={1920} height={1080} fps={FPS} durationInFrames={90} calculateMetadata={listenMeta} />
    <Composition id="TangoQuiz" component={TangoQuiz} defaultProps={{ data: QUIZ_SAMPLE }}
      width={1080} height={1920} fps={FPS} durationInFrames={90} calculateMetadata={quizMeta} />
    <Composition id="TangoThumb" component={TangoThumb} defaultProps={{ data: TANGO_SAMPLE }} width={1280} height={720} fps={FPS} durationInFrames={1} />
    {/* 大学グループ別のサムネ（グループ名をいちばん大きく）。group は省くと data.label（「GMARCH頻出100」）から取る */}
    <Composition id="TangoGroupThumb" component={TangoGroupThumb} defaultProps={{ data: TANGO_SAMPLE, group: 'GMARCH', variant: 'A' as const }} width={1280} height={720} fps={FPS} durationInFrames={1} />
    <Composition id="ChannelIcon" component={ChannelIcon} width={800} height={800} fps={FPS} durationInFrames={1} />
    <Composition id="ChannelBanner" component={ChannelBanner} width={2560} height={1440} fps={FPS} durationInFrames={1} />
    <Composition id="CharaSheet" component={Sheet} width={1620} height={2020} fps={FPS} durationInFrames={60} />
  </>
);
