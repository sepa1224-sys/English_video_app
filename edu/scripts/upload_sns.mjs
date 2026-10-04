// 作った解説ショートを気合のアプリ（/admin/sns-videos）に「承認待ち」で送る。
//   node scripts/upload_sns.mjs <エピソードID>
// 動画とサムネは Vercel Blob（非公開）に直接アップロードし（関数の4.5MB制限を避ける）、そのURLを登録する。
// 合言葉は ../.env の SNS_UPLOAD_SECRET（Vercel の env と同じ値）。
import fs from 'node:fs';
import path from 'node:path';
import { upload } from '@vercel/blob/client';

const root = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const APP = process.env.KIAI_APP_URL ?? 'https://kiai-coaching-app.vercel.app';
const id = process.argv[2];
if (!id) { console.error('usage: node scripts/upload_sns.mjs <episode-id>'); process.exit(1); }

const env = fs.readFileSync(path.join(root, '..', '.env'), 'utf8');
const secret = (env.match(/^SNS_UPLOAD_SECRET=(.+)$/m) ?? [])[1]?.trim();
if (!secret) { console.error('../.env に SNS_UPLOAD_SECRET がありません'); process.exit(1); }

const meta = JSON.parse(fs.readFileSync(path.join(root, '..', 'output', 'edu', `${id}.sns.json`), 'utf8'));
const video = fs.readFileSync(path.join(root, '..', 'output', 'edu', `${id}.mp4`));
const thumbPath = path.join(root, '..', 'output', 'edu', `${id}.jpg`);

const put = (name, body, contentType) => upload(`sns-video/${id}/${name}`, new Blob([body], { type: contentType }), {
  access: 'private', handleUploadUrl: `${APP}/api/sns-video/upload`, clientPayload: secret, contentType,
});

console.log(`⬆ 動画をアップロード中（${(video.length / 1e6).toFixed(1)}MB）`);
const v = await put(`${Date.now()}.mp4`, video, 'video/mp4');
const t = fs.existsSync(thumbPath) ? await put(`${Date.now()}.jpg`, fs.readFileSync(thumbPath), 'image/jpeg') : null;

const r = await fetch(`${APP}/api/sns-video`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${secret}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ ...meta, sourceId: id, videoUrl: v.url, thumbUrl: t?.url ?? null }),
});
const body = await r.json().catch(() => ({}));
if (!r.ok) { console.error(`登録に失敗（${r.status}）`, body); process.exit(1); }
console.log(`✅ 承認待ちに登録しました（#${body.id}）→ ${APP}/admin/sns-videos`);
