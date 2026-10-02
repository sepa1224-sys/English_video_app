// キャラクター（マスターと7人）の絵を、気合LINEのショート用プロジェクトから取り込む。
// キャラは別チャット（~/kiai-line-shorts）で作り込んでいるので、ここでは描き直さずに写す。
// 向こうで絵が直ったら、このスクリプトをもう一度走らせれば揃う。
//   node scripts/sync-cast.mjs [取り込み元のパス]
import fs from 'node:fs';
import path from 'node:path';

const SRC = process.argv[2] ?? path.join(process.env.HOME, 'kiai-line-shorts');
const here = path.dirname(new URL(import.meta.url).pathname);
const root = path.join(here, '..');

if (!fs.existsSync(path.join(SRC, 'src/Character.tsx'))) {
  console.error(`取り込み元が見つかりません: ${SRC}`);
  process.exit(1);
}

const head = (file) => `// ⚠ ${file} は ${SRC}/src/${file} の写しです。ここでは編集しない（scripts/sync-cast.mjs が上書きする）。\n`;

// Character.tsx は Pose の型を './scripts'（向こうの台本）から読んでいる。ここでは './pose' に差し替える
for (const file of ['Character.tsx', 'Personas.tsx']) {
  let s = fs.readFileSync(path.join(SRC, 'src', file), 'utf8');
  s = s.replace(/from '\.\/scripts'/g, "from './pose'");
  fs.writeFileSync(path.join(root, 'src/cast', file), head(file) + s);
  console.log('  src/cast/' + file);
}
// Pose の型だけ抜き出す
const scripts = fs.readFileSync(path.join(SRC, 'src/scripts.ts'), 'utf8');
const pose = scripts.match(/export type Pose = [^;]+;/);
if (!pose) { console.error('Pose の型が見つかりません'); process.exit(1); }
fs.writeFileSync(path.join(root, 'src/cast/pose.ts'), head('scripts.ts（Pose の型だけ）') + pose[0] + '\n');
console.log('  src/cast/pose.ts');

// フォントとロゴ。キャラの絵（PNG）が届いていれば、それも
for (const dir of ['fonts', 'chara']) {
  const from = path.join(SRC, 'public', dir);
  if (!fs.existsSync(from)) continue;
  fs.mkdirSync(path.join(root, 'public', dir), { recursive: true });
  for (const f of fs.readdirSync(from)) {
    fs.copyFileSync(path.join(from, f), path.join(root, 'public', dir, f));
    console.log(`  public/${dir}/${f}`);
  }
}
fs.copyFileSync(path.join(SRC, 'public/kiai-logo.png'), path.join(root, 'public/kiai-logo.png'));
console.log('  public/kiai-logo.png');
