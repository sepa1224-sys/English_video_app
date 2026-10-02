import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';

// フォントは手元のファイルから（Google Fonts の日本語は分割が多く、書き出しが時間切れになる）。
// キャラの鉢巻の「気合」にも使うので、絵の部品からも読み込む
export const ROUNDED = 'KiaiRounded';
export const HAND = 'KiaiHand';
loadFont({ family: ROUNDED, url: staticFile('fonts/MPLUSRounded1c-ExtraBold.ttf'), weight: '800' });
loadFont({ family: HAND, url: staticFile('fonts/YuseiMagic-Regular.ttf') });
