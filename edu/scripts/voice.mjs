// 台本（episodes/<id>.json）の全ビートに声を付ける。
//   node scripts/voice.mjs <id>        … public/ep/<id>/ に mp3 と、長さ・口パクを書き込んだ episode.json を作る
//   FORCE=1 node scripts/voice.mjs <id> … 作成済みの声も作り直す
// 誰の声かは cast.json で決める。
//   voicevox … VOICEVOX ENGINE（無料・Macで動く。scripts/voicevox.sh で起動）。動画には「VOICEVOX:キャラ名」のクレジットが要る
//   eleven   … ElevenLabs（ELEVENLABS_API_KEY が要る）
//   edge     … 無料の仮の声
// en（英文）は、日本語のセリフのあとに英語の声で続けて読む。
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const root = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const id = process.argv[2];
if (!id) { console.error('usage: node scripts/voice.mjs <episode-id>'); process.exit(1); }
const ep = JSON.parse(fs.readFileSync(path.join(root, 'episodes', `${id}.json`), 'utf8'));
const cast = JSON.parse(fs.readFileSync(path.join(root, 'cast.json'), 'utf8'));
const outDir = path.join(root, 'public/ep', id);
fs.mkdirSync(outDir, { recursive: true });

// ElevenLabs のキーは動画生成リポジトリの .env にある
const envFile = path.join(root, '..', '.env');
if (!process.env.ELEVENLABS_API_KEY && fs.existsSync(envFile)) {
  const m = fs.readFileSync(envFile, 'utf8').match(/^ELEVENLABS_API_KEY=(.+)$/m);
  if (m) process.env.ELEVENLABS_API_KEY = m[1].trim();
}

const ff = (args, opts = {}) => execFileSync('npx', ['remotion', 'ffmpeg', '-y', '-v', 'error', ...args], { cwd: root, ...opts });
const probe = (file) => Number(execFileSync('npx', ['remotion', 'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file], { cwd: root }).toString().trim());

function edge(text, voice, rate, pitch, out) {
  for (let i = 0; i < 3; i++) {
    try {
      execFileSync('python3', ['-m', 'edge_tts', '--text', text, '--voice', voice, `--rate=${rate ?? '+0%'}`, `--pitch=${pitch ?? '+0Hz'}`, '--write-media', out], { stdio: 'pipe' });
      if (fs.existsSync(out) && fs.statSync(out).size > 500) return;
    } catch (e) { if (i === 2) throw e; }
  }
  throw new Error(`声を作れませんでした: ${text}`);
}

// eleven_v3 は感情が乗りやすい（掛け合い向き）。一時的なエラーは少し待って3回まで試す
// 既定は eleven_multilingual_v2。eleven_v3 は感情豊かだが、セリフごとに声色がぶれて別人に聞こえた（仙人で確認）
async function eleven(text, voiceId, out, model = 'eleven_multilingual_v2') {
  for (let i = 0; i < 3; i++) {
    const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`, {
      method: 'POST',
      headers: { 'xi-api-key': process.env.ELEVENLABS_API_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, model_id: model }),
    });
    if (r.ok) { fs.writeFileSync(out, Buffer.from(await r.arrayBuffer())); return; }
    const body = await r.text();
    if (r.status < 500 && r.status !== 429) throw new Error(`ElevenLabs ${r.status} ${body}`);
    await new Promise((res) => setTimeout(res, 3000 * (i + 1)));
  }
  throw new Error(`ElevenLabs で声を作れませんでした: ${text}`);
}

// VOICEVOX。声は「キャラ名/スタイル名」で指定し、話者IDはエンジンに問い合わせて引く
const VV = process.env.VOICEVOX_URL ?? 'http://127.0.0.1:50021';
let vvSpeakers = null;
async function vvId(voice) {
  if (!vvSpeakers) {
    const r = await fetch(`${VV}/speakers`).catch(() => null);
    if (!r?.ok) throw new Error('VOICEVOX ENGINE に接続できません。scripts/voicevox.sh で起動してください');
    vvSpeakers = await r.json();
  }
  const [name, style = 'ノーマル'] = voice.split('/');
  const sp = vvSpeakers.find((x) => x.name === name);
  const st = sp?.styles.find((x) => x.name === style);
  if (!st) throw new Error(`VOICEVOX に「${voice}」がありません`);
  return st.id;
}
async function voicevox(text, c, out) {
  const id = await vvId(c.voice);
  const q = await (await fetch(`${VV}/audio_query?speaker=${id}&text=${encodeURIComponent(text)}`, { method: 'POST' })).json();
  // キャラの個性：速さ・高さ・抑揚・声の大きさ
  Object.assign(q, { speedScale: c.speed ?? 1.1, pitchScale: c.pitch ?? 0, intonationScale: c.intonation ?? 1.1,
    volumeScale: c.volume ?? 1.0, prePhonemeLength: 0.05, postPhonemeLength: 0.1 });
  const r = await fetch(`${VV}/synthesis?speaker=${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(q) });
  if (!r.ok) throw new Error(`VOICEVOX ${r.status} ${await r.text()}`);
  const wav = out.replace(/\.mp3$/, '.wav');
  fs.writeFileSync(wav, Buffer.from(await r.arrayBuffer()));
  ff(['-i', wav, '-c:a', 'libmp3lame', '-b:a', '160k', out]);
  fs.rmSync(wav);
}

async function say(who, text, lang, out) {
  const c = cast[who] ?? cast.master;
  // 英文は英語ネイティブの声で（ElevenLabs のキャラなら en_voice、なければ無料の仮の声）
  if (lang === 'en') return c.en_voice ? eleven(text, c.en_voice, out, c.model) : edge(text, c.en ?? 'en-US-GuyNeural', '-6%', '+0Hz', out);
  if (c.provider === 'voicevox') return voicevox(text, c, out);
  if (c.provider === 'eleven') return eleven(text, c.voice, out, c.model);
  return edge(text, c.voice, c.rate, c.pitch, out);
}

// 1コマ（1/30秒）ごとの声の大きさ 0〜1。口パクに使う
function envelope(file) {
  const wav = execFileSync('npx', ['remotion', 'ffmpeg', '-v', 'error', '-i', file, '-ac', '1', '-ar', '8000', '-acodec', 'pcm_s16le', '-f', 'wav', '-'], { cwd: root, maxBuffer: 1 << 26 });
  const pcm = wav.subarray(wav.indexOf('data') + 8);
  const n = pcm.length / 2, per = Math.round(8000 / 30), out = [];
  for (let i = 0; i < n; i += per) {
    let sum = 0, c = 0;
    for (let j = i; j < Math.min(n, i + per); j++) { const v = pcm.readInt16LE(j * 2); sum += v * v; c++; }
    out.push(Math.sqrt(sum / Math.max(1, c)));
  }
  const max = Math.max(...out, 1);
  return out.map((v) => Math.round((v / max) * 100) / 100);
}

for (const b of ep.beats) {
  const out = path.join(outDir, `${b.id}.mp3`);
  if (!fs.existsSync(out) || process.env.FORCE) {
    fs.rmSync(out + '.sped', { force: true });
    const ja = path.join(outDir, `${b.id}.ja.mp3`);
    await say(b.who, b.line, 'ja', ja);
    if (b.en) {
      // 日本語 → 0.25秒 → 英文。英文は英語の声で
      const en = path.join(outDir, `${b.id}.en.mp3`);
      await say(b.who, b.en, 'en', en);
      ff(['-i', ja, '-f', 'lavfi', '-t', '0.25', '-i', 'anullsrc=r=44100:cl=mono', '-i', en,
        '-filter_complex', '[0:a]aresample=44100,aformat=channel_layouts=mono[a];[2:a]aresample=44100,aformat=channel_layouts=mono[c];[a][1:a][c]concat=n=3:v=0:a=1',
        '-c:a', 'libmp3lame', '-b:a', '160k', out]);
      fs.rmSync(en);
    } else {
      fs.copyFileSync(ja, out);
    }
    fs.rmSync(ja);
  }
  // キャラの話す速さ（cast.json の speed、既定 1.1）。ショートは間延びすると離脱されるので少し速める
  const speed = (cast[b.who] ?? cast.master).speed ?? 1.1;
  if (speed !== 1 && !fs.existsSync(out + '.sped')) {
    const tmp = out.replace(/\.mp3$/, '.tmp.mp3');
    ff(['-i', out, '-filter:a', `atempo=${speed}`, '-c:a', 'libmp3lame', '-b:a', '160k', tmp]);
    fs.renameSync(tmp, out);
    fs.writeFileSync(out + '.sped', String(speed)); // 二重に速めないための印
  }
  b.dur = Math.round(probe(out) * 100) / 100;
  b.env = envelope(out);
  console.log(`  ${b.id} ${b.who.padEnd(11)} ${String(b.dur).padStart(5)}s  ${b.line}${b.en ? ' / ' + b.en : ''}`);
}
fs.writeFileSync(path.join(outDir, 'episode.json'), JSON.stringify({ episode: ep }));
const total = ep.beats.reduce((n, b) => n + b.dur + 0.3 + (b.think ?? 0), 0);
console.log(`✅ ${ep.beats.length}ビート・約${Math.round(total)}秒 → public/ep/${id}/episode.json`);
