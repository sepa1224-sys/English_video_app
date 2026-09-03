# 「1日5分 英語で聞く教養」を毎日つくる — デスクトップ側の準備

毎晩21時に1本つくり、翌朝7時にYouTubeが自動公開する。
生成機は Windows デスクトップ（`C:\Users\PC_User\english_video_app`）。

## 1. コードを取り込む

```bat
cd /d C:\Users\PC_User\english_video_app
git pull
py -m pip install -r requirements.txt
py -m pip install anthropic edge-tts imageio-ffmpeg moviepy pillow python-dotenv requests
```

## 2. 認証情報を置く（Gitには入っていない）

開発機（Mac）から手で持ってくる。**公開リポジトリなので絶対にコミットしない。**

| 置き場所 | 中身 |
|---|---|
| `english_video_app\.env` | `ANTHROPIC_API_KEY` / `ELEVENLABS_API_KEY` |
| `english_video_app\config\youtube_token.json` | YouTube投稿用のトークン |
| `english_video_app\config\client_secret.json` | 同上 |
| `%USERPROFILE%\.config\higgsfield\credentials.json` | 画像・音楽生成用 |

Higgsfield は CLI を入れて `higgsfield auth login` でも可。

## 3. 教材の置き場所を決める

既定では `%USERPROFILE%\kiai-coaching-app\materials` を探し、無ければ
アプリ直下の `materials\` を使う。別の場所にしたいときだけ環境変数で指定する。

```bat
setx KIAI_MATERIALS_DIR "C:\Users\PC_User\english_video_app\materials"
```

## 4. 動作確認（公開せずに1本つくる）

```bat
py ondoku_daily.py --no-schedule --privacy unlisted --keep-files
```

うまくいけば限定公開で1本上がる。中身を見て問題なければ次へ。

## 5. タスクスケジューラに登録

- タスク名: `EnglishVideoApp_DailyKyoyo`
- トリガー: 毎日 21:00
- 操作: `C:\Users\PC_User\english_video_app\run_daily_kyoyo.bat`
- 「ユーザーがログオンしているかどうかにかかわらず実行する」にチェック
- 「タスクを実行するためにスリープを解除する」にチェック

大学リスニング（`EnglishVideoApp_DailyUpload`, 06:00）とは別枠。
時間が重ならないようにすること。

## 6. 動いているかの見かた

- `logs\daily_kyoyo.log` … 実行の記録。失敗の理由もここ
- `output\daily_logs\YYYYMMDD.txt` … その日の教材IDと動画URL
- `topics_kyoyo.json` … 題材の在庫。`used: true` が増えていく

## 気をつけること

- **題材の在庫が尽きると止まる。** `topics_kyoyo.json` に足しておく
- **ディスクの空きが2.5GB未満だと実行しない。** 書き出しに1〜2GB使うため
- 動画は公開後に手元から消す。毎日貯めると月4GBになるため。作り直したいときは
  絵コンテと教材から再生成する
- ElevenLabs は Creator プラン（月121,000文字）。1本あたり約3,800文字なので
  月32本ぶん。作り直しが続くと枠を使い切るので注意
