---
name: kiai-youtube
description: 気合イングリッシュ(english_video_app)の大学リスニング動画をYouTubeへ全自動でアップする運用ランナー。「YouTubeにアップ」「続きをアップ」「自動アップが止まった」「次のPartを上げて」「東大/京大/阪大のリスニングをアップ」等で使う。前提チェック→生成→アップ→再生リスト追加を1フローで行い、トークン失効・APIクレジット切れ等の既知の失敗は原因と対処まで案内する。
---

# kiai-youtube 運用ランナー

このskillは気合イングリッシュ（チャンネルID `UCU2D3_9VQ-qPDxMeof7BMyg`）の
大学リスニング動画を生成→YouTubeアップ→再生リスト追加するまでを面倒見る。
リポジトリ: `C:\Users\PC_User\english_video_app`（Windows・`py`ランチャ使用）。

## 大前提（毎回まずこれ）
- **作業ディレクトリは必ずリポジトリルート** `C:\Users\PC_User\english_video_app`。
- Windowsのcp932対策で、Pythonを呼ぶときは `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` を付ける。
- `python` ではなく **`py`** を使う（`python`はMS Storeスタブで壊れている）。
- 動画生成は数分〜十数分かかる。**`run_in_background: true` で実行**し、完了通知を待つ。
- ログは `logs/` に出す（例: `> logs/run_xxx.log 2>&1`）。

## 手順

### 1. 前提チェック（必須・最初に1回）
```
PYTHONUTF8=1 py .claude/skills/kiai-youtube/preflight.py
```
- 末尾が `PREFLIGHT: OK` なら次へ。
- `PREFLIGHT: NG` なら、出力の指示に従って先に直す（→「既知の失敗と対処」）。
  YouTubeトークン失効と思しき場合は**ユーザーにブラウザ再認証を依頼**（自分では実行不可）。

### 2. 生成＋アップロード
対象大学を確認（指定が無ければ **todai** 既定。毎日6:00の自動タスク `EnglishVideoApp_DailyUpload` もtodaiのみ）。

次Partを生成してそのままアップ:
```
PYTHONUTF8=1 PYTHONUNBUFFERED=1 py auto_upload.py --generate --university todai > logs/run_todai.log 2>&1
```
`--university` は `todai|kyoto|osaka`。公開範囲は既定 `unlisted`（公開にするなら `--privacy public`）。

**生成済みのmp4を再アップする場合**（生成は成功したがアップだけ失敗した時など。再生成不要・APIコスト無し）:
```
PYTHONUTF8=1 PYTHONUNBUFFERED=1 py auto_upload.py --university todai "output/exam/todai/<最新>.mp4" > logs/upload.log 2>&1
```
最新mp4は `ls -lat output/exam/<uni>/*.mp4 | head` で探す。`_description.txt` が同名で隣にある前提。

### 3. 結果確認
ログから要点を抜く:
```
grep -E "Uploaded:|Title:|playlist|Done|! " logs/run_todai.log
```
`Uploaded: https://youtu.be/...` と `Done. ... next part = N` が出ていれば成功。
Part番号カウンタ（`data/<uni>_publish_part.txt`）は**成功時のみ+1**される。失敗時は番号据え置きなので、直しただけで同コマンド再実行すればよい。

### 4. ダッシュボード更新（アップ成功後）
状況監視ダッシュボード(kiai-dashboard, Vercel)へ最新状況を反映:
```
scripts\update_dashboard.bat
```
（中身: `py scripts/build_status.py --out ../kiai-dashboard/public/status.json` で status.json 再生成 → `npx vercel --prod --yes` で再デプロイ）
daily タスク `run_daily_upload.bat` からは自動で呼ばれる。手動アップ時はここで実行。

### 5. 報告
アップしたURL・タイトル・Part番号・再生リスト追加可否・ダッシュボード更新可否を簡潔に伝える。

## ダッシュボード(kiai-dashboard)
- リポジトリ: `C:\Users\PC_User\kiai-dashboard`（Next.js / Vercel・チーム michaelts-projects）
- データ源: ローカルが生成する `public/status.json`（YouTube実状況＋基本指標＋トークン残日数＋アラート）
- 状況だけ素早く見たい時は `py scripts/build_status.py` で `data/status.json` を作り中身を確認してもよい（デプロイ不要）。
- 分析の深掘り（視聴維持率/CTR）は YouTube Analytics API + 追加スコープ再認証が必要（未実装・将来）。

## 既知の失敗と対処（重要）
今日まで自動アップが止まっていた原因は下記が**重なって**いた。preflightで切り分ける。

1. **Anthropic クレジット切れ**（台本生成で死ぬ）
   症状: `anthropic.BadRequestError: 400 ... Your credit balance is too low`
   対処: ユーザーがコンソールでクレジット購入。こちらでは直せない。

2. **YouTube OAuthトークン失効**（アップ直前で死ぬ・最頻出）
   症状: `google.auth.exceptions.RefreshError: invalid_grant: Token has been expired or revoked`
   原因: GCP同意画面(プロジェクト`englishpodcast`)が**「テスト」状態**→リフレッシュトークンが**7日で失効**。
   `scripts/oauth_setup.py` は死んだトークンを更新しようとして自爆するので、**先に退避してから**再認証:
   ```
   # まずClaudeが退避（ファイル操作なので可）
   mv config/token.json config/token.json.expired_bak
   ```
   その後**ユーザーに**下記をブラウザで実行してもらう（`!`付き・自分では不可）:
   ```
   !cd /c/Users/PC_User/english_video_app && py scripts/oauth_setup.py
   ```
   気合イングリッシュのGoogleアカウントを選択→「未確認アプリ」警告は「詳細→移動」で進む→許可。
   「認証成功!」が出たら再開。
   **恒久対策**: GCP同意画面を「本番(Production)」に公開すれば7日失効が止まる（ユーザー作業）。

3. **再生リストが追加されない**
   症状: ログに `No playlist for genre 'listening_<uni>'`
   原因: `data/channel_analysis/genre_master.json` にその大学のジャンル/`playlist_id`が無い。
   既存の再生リストがYouTubeにある場合があるので**まず確認**（重複作成を避ける）。
   無ければジャンルを追加して `py scripts/create_playlists.py` で作成→IDが書き戻る。
   既存リストに過去動画を入れ直すのは `playlistItems().insert` で対応。

## 補足
- 大学別設定は `auto_upload.py` の `UNI_CONFIG`（level/genre/サムネ位置/seq）。
- todai/kyotoは鉄壁ID順(seq)。osakaはhybridでvocabランダム。
- サムネ土台: `assets/thumbnail_base_<uni>.png`（番号無し）。`thumbnail_gen.py`が"Part N"を描画。
- 2台運用(Mac/Windows)。重要な変更後は `git add/commit/push` をユーザーに確認。
