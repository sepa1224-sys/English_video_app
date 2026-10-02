// 声を付けたエピソードを動画に書き出す。
//   node scripts/render.mjs <id>   → ../output/edu/<id>.mp4
// ショートは縦（EduShort）、長尺は横（EduLong）。
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const root = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const id = process.argv[2];
if (!id) { console.error('usage: node scripts/render.mjs <episode-id>'); process.exit(1); }
const props = path.join(root, 'public/ep', id, 'episode.json');
if (!fs.existsSync(props)) { console.error(`先に node scripts/voice.mjs ${id} を実行してください`); process.exit(1); }
const { episode } = JSON.parse(fs.readFileSync(props, 'utf8'));
const comp = episode.format === 'long' ? 'EduLong' : 'EduShort';
const outDir = path.join(root, '..', 'output', 'edu');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, `${id}.mp4`);
execFileSync('npx', ['remotion', 'render', 'src/index.ts', comp, out, `--props=${props}`, '--log=error'], { cwd: root, stdio: 'inherit' });
console.log(`✅ ${out}`);
