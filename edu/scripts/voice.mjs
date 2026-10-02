// 台本（episodes/<id>.json）の全ビートに声を付ける。
//   node scripts/voice.mjs <id>        … public/ep/<id>/ に mp3 と、長さ・口パクを書き込んだ episode.json を作る
//   FORCE=1 node scripts/voice.mjs <id> … 作成済みの声も作り直す
// 誰の声かは cast.json で決める。edge は無料の仮の声、eleven は ElevenLabs（ELEVENLABS_API_KEY が要る）。
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

async function eleven(text, voiceId, out) {
  const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`, {
    method: 'POST',
    headers: { 'xi-api-key': process.env.ELEVENLABS_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, model_id: 'eleven_multilingual_v2',
      voice_settings: { stability: 0.5, similarity_boost: 0.8, style: 0.4, use_speaker_boost: true } }),
  });
  if (!r.ok) throw new Error(`ElevenLabs ${r.status} ${await r.text()}`);
  fs.writeFileSync(out, Buffer.from(await r.arrayBuffer()));
}

async function say(who, text, lang, out) {
  const c = cast[who] ?? cast.master;
  if (lang === 'en') return edge(text, c.en ?? 'en-US-GuyNeural', '-6%', '+0Hz', out);
  if (c.provider === 'eleven') return eleven(text, c.voice, out);
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
    const ja = path.join(outDir, `${b.id}.ja.mp3`);
    await say(b.who, b.line, 'ja', ja);
    if (b.en) {
      // 日本語 → 0.25秒 → 英文。英文は英語の声で
      const en = path.join(outDir, `${b.id}.en.mp3`);
      await say(b.who, b.en, 'en', en);
      ff(['-i', ja, '-f', 'lavfi', '-t', '0.25', '-i', 'anullsrc=r=24000:cl=mono', '-i', en,
        '-filter_complex', '[0:a]aresample=24000,aformat=channel_layouts=mono[a];[2:a]aresample=24000,aformat=channel_layouts=mono[c];[a][1:a][c]concat=n=3:v=0:a=1',
        '-c:a', 'libmp3lame', '-b:a', '128k', out]);
      fs.rmSync(en);
    } else {
      fs.copyFileSync(ja, out);
    }
    fs.rmSync(ja);
  }
  b.dur = Math.round(probe(out) * 100) / 100;
  b.env = envelope(out);
  console.log(`  ${b.id} ${b.who.padEnd(11)} ${String(b.dur).padStart(5)}s  ${b.line}${b.en ? ' / ' + b.en : ''}`);
}
fs.writeFileSync(path.join(outDir, 'episode.json'), JSON.stringify({ episode: ep }));
const total = ep.beats.reduce((n, b) => n + b.dur + 0.3 + (b.think ?? 0), 0);
console.log(`✅ ${ep.beats.length}ビート・約${Math.round(total)}秒 → public/ep/${id}/episode.json`);
