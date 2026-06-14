# Podcast Mode 仕様書

> ステータス: **ドラフト（レビュー待ち）**
> 作成日: 2026-04-23
> 関連ADR: docs/adr/002_podcast_mode_introduction.md

---

## 1. 概要

YouTube 収益化ポリシー（2025年7月改定）により、単語＋訳のみのテンプレート動画は収益化不可となった。
解説・文脈を加えた長尺ポッドキャスト型動画で差別化し、広告収益の対象となるコンテンツを生成する。

**ターゲット視聴者**: 通勤・作業中に英語を聞き流したい社会人・大学生
**用途**: 日中の聞き流し（画面を見なくても学習が成立する音声主体コンテンツ）

---

## 2. 動画構成（試作1本: 約30分）

### テーマ: ビジネスメールで使える英語表現30選

```
[オープニング] → [メインパート x30] → [復習パート] → [エンディング]
```

### 2.1 オープニング（約2分）

| 要素 | 内容 |
|---|---|
| 目的 | テーマ紹介と挨拶 |
| 話者 | 女性声（日本語） |
| 内容 | チャンネル名、テーマ説明、動画の使い方ガイド |
| BGM | Lo-Fi系BGM（フェードイン、音量小） |
| 画面 | タイトルカード（テーマ名＋チャンネルロゴ） |

### 2.2 メインパート（約24分 = 30フレーズ × 約50秒）

各フレーズの構成（約50秒）:

| # | 要素 | 話者 | 速度 | 想定秒数 |
|---|---|---|---|---|
| 1 | 英語フレーズ読み上げ | 男性声（英語） | ゆっくり（speed=0.85） | 約3-5秒 |
| 2 | ポーズ | — | — | 1.0秒 |
| 3 | 日本語訳 | 女性声（日本語） | 通常 | 約3-5秒 |
| 4 | 使用場面の解説（1〜2文） | 女性声（日本語） | 通常 | 約8-12秒 |
| 5 | 例文（英語） | 男性声（英語） | ゆっくり（speed=0.85） | 約5-8秒 |
| 6 | ポーズ | — | — | 0.5秒 |
| 7 | 英語フレーズ再読 | 男性声（英語） | 通常（speed=1.0） | 約2-4秒 |

フレーズ間のポーズ: 1.5秒

### 2.3 復習パート（約3分）

| 要素 | 内容 |
|---|---|
| 目的 | 重要フレーズの再放送（10フレーズ選定） |
| 導入 | 「それでは復習です」（女性声） |
| 構成 | 英語フレーズ（ゆっくり）→ 1秒ポーズ → 日本語訳 × 10 |
| 選定基準 | 台本生成時にフレーズごとの `is_review: true` フラグで指定 |

### 2.4 エンディング（約1分）

| 要素 | 内容 |
|---|---|
| 内容 | 締めの挨拶、チャンネル登録促し、次回予告 |
| 話者 | 女性声（日本語） |
| BGM | Lo-Fi系BGM（フェードアウト） |
| 画面 | エンドスクリーン（チャンネルロゴ＋登録ボタン誘導） |

---

## 3. 画面レイアウト

解像度: 1280 × 720（既存モードと統一）

### 3.1 メインパートの画面構成

```
┌──────────────────────────────────┐
│  [フレーズ番号]         [ロゴ]    │  上部エリア
│                                  │
│     英語フレーズ（大文字）        │  中央上
│     日本語訳                     │  中央
│                                  │
│     解説テキスト / 例文          │  中央下
│                                  │
│  ────────────────────────────    │
│  [プログレスバー: 3/30]          │  下部エリア
└──────────────────────────────────┘
```

### 3.2 描画仕様

| 要素 | フォント | サイズ | 色 | 位置 |
|---|---|---|---|---|
| フレーズ番号 | Regular | 28 | `#888888` | 左上 (50, 40) |
| 英語フレーズ | Bold/ExtraBold | 72 | `#FFFFFF` | 水平中央, y=240 |
| 日本語訳 | Regular | 48 | `#CCCCCC` | 水平中央, y=340 |
| 解説テキスト | Regular | 36 | `#AAAAAA` | 水平中央, y=440, 折り返し幅1100px |
| 例文（英語） | Bold | 44 | `#88CCFF` | 水平中央, y=440 |
| プログレスバー | — | — | `#4488FF` | x=90, y=680, 幅1100px, 高さ4px |
| ロゴ | — | 最大幅150px | — | 右上 (1280-w-20, 20) |

### 3.3 画面遷移

各フレーズ内の表示は音声の進行に合わせて段階的に切り替える:

| タイミング | 表示内容 |
|---|---|
| Step 1: 英語フレーズ再生中 | 英語フレーズのみ表示 |
| Step 2: 日本語訳〜解説再生中 | 英語フレーズ＋日本語訳＋解説テキスト |
| Step 3: 例文再生中 | 英語フレーズ＋例文（解説を例文に差し替え） |
| Step 4: 再読再生中 | 英語フレーズのみ（Step 1に戻る） |

---

## 4. 音声仕様

### 4.0 音声戦略: プリセット声ベース

> **設計意図**: 英語フレーズはネイティブ AI 声（Adam）で学習教材としての正統性を保ち、日本語パートは ElevenLabs プリセット声（Morioki: 日本人女性声）で自然なナレーションを実現する。
>
> **Voice Cloning 不採用の経緯**: 先行テスト（2026-05-14）でユーザーの Voice Cloning を3パターン検証したが、「品質がもう一歩」「AI特有の違和感がある」と判断し不採用。将来 Professional Voice Cloning（高品質版）で再検討予定。
>
> **YouTube 収益化リスクへの対応**: 音声面でのハイブリッド戦略ではなく、以下の運用面で「人間味・オリジナリティ」を担保する：
> - 動画説明欄での運営者情報・AI使用の透明性開示
> - コメント欄での運営者本人による交流
> - シリーズ内でのテーマ・構成バリエーション
> - オリジナル台本（解説・例文・文化的注意点付き）

| パート | 声 | Voice ID 環境変数 |
|---|---|---|
| オープニング（日本語） | Morioki（プリセット日本人女性声） | `ELEVENLABS_VOICE_ID_USER_JA` |
| 日本語訳・解説 | Morioki（同上） | `ELEVENLABS_VOICE_ID_USER_JA` |
| 英語フレーズ・例文・再読 | Adam（プリセット英語男性声） | `ELEVENLABS_VOICE_ID_ENGLISH_MALE` |
| エンディング（日本語） | Morioki（同上） | `ELEVENLABS_VOICE_ID_USER_JA` |

### 4.1 TTS エンジン・モデル

**使用モデル**: `eleven_multilingual_v2`（環境変数 `PODCAST_TTS_MODEL` で変更可能）

| モデル | 品質 | 速度 | 日本語対応 | クレジット消費 | 用途 |
|---|---|---|---|---|---|
| `eleven_multilingual_v2` | 最高 | 遅い | Yes | 1文字=1クレジット | **推奨（英語・日本語両方）** |
| `eleven_turbo_v2_5` | 高い | 速い | Yes | 0.5〜1/文字 | 大量生成時の代替 |
| `eleven_flash_v2_5` | 中 | 最速 | Yes | 0.5〜1/文字 | プロトタイプ用 |

### 4.1.1 Voice Settings

| パラメータ | 英語 Adam | 日本語 Morioki | 説明 |
|---|---|---|---|
| `stability` | 0.5 | 0.7 | 声の安定性。Morioki は高めで安定したナレーション調に |
| `similarity_boost` | 0.75 | 0.85 | 声の再現度 |
| `speed` | 0.85（ゆっくり読み）/ 1.0（再読） | 1.0 | 読み上げ速度 |

> **speed=0.85 の根拠**: 聞き流し学習では初回の英語フレーズを 15% 減速して聞き取りやすくする。再読（7番目のステップ）は通常速度 1.0 で自然なリズムを体験させる。先行テスト（2026-05-14）で 0.85 と 1.0 を聴き比べ、0.85 が自然に聞き取りやすいと判断し採用。

### 4.2 フォールバック

ElevenLabs API が利用不可の場合:
1. OpenAI TTS API（既存 `audio_gen.py` の `generate_audio_segment_openai` を流用）
2. Edge-TTS（既存 `audio_gen.py` の `generate_audio_segment_edge` を流用）

フォールバック順序はユーザー設定可能（後述の設定ファイル参照）。
> **注意**: 試作フェーズでは ElevenLabs を前提とし、フォールバックの実装は将来フェーズとする。

### 4.3 BGM

| 区間 | BGM | 音量 |
|---|---|---|
| オープニング | Lo-Fi系（`assets/podcast_bgm.mp3` または指定ファイル） | 0.15（メイン音量比） |
| メインパート | 同上 | 0.08（解説の邪魔にならないレベル） |
| 復習パート | 同上 | 0.10 |
| エンディング | 同上 | 0.15（フェードアウト: 最後5秒） |

BGMはループ再生し、動画長に合わせて自動トリミングする。

### 4.4 SE（効果音）

| タイミング | SE | 音量 |
|---|---|---|
| フレーズ切替時 | チャイム音（`assets/phrase_chime.mp3`、なければスキップ） | 0.2 |
| セクション切替時 | 既存 `assets/` 内のSE | 0.3 |

---

## 5. 台本データ構造

### 5.1 台本生成の入力

台本は Claude API を使って自動生成する。

**入力パラメータ**:

| パラメータ | 型 | 説明 |
|---|---|---|
| `theme` | str | テーマ名（例: "ビジネスメールで使える英語表現30選"） |
| `phrase_count` | int | フレーズ数（デフォルト: 30） |
| `target_audience` | str | 対象者（例: "社会人・大学生"） |
| `detail_level` | str | 解説の詳しさ: "brief" / "normal" / "detailed" |

### 5.2 台本 JSON 構造

```json
{
  "meta": {
    "theme": "ビジネスメールで使える英語表現30選",
    "phrase_count": 30,
    "target_audience": "社会人・大学生",
    "generated_at": "2026-04-23T12:00:00Z",
    "generator": "claude-api",
    "version": "1.0"
  },
  "opening": {
    "narration_ja": "こんにちは、気合イングリッシュです。今回は..."
  },
  "phrases": [
    {
      "id": 1,
      "phrase_en": "I hope this email finds you well.",
      "meaning_ja": "お元気でお過ごしのことと存じます。",
      "explanation_ja": "ビジネスメールの冒頭で最も一般的な挨拶表現です。初めての相手にも、既知の相手にも使えます。",
      "example_en": "Dear Mr. Smith, I hope this email finds you well. I am writing to inquire about...",
      "is_review": true
    }
  ],
  "ending": {
    "narration_ja": "今回はビジネスメールで使える表現を30個ご紹介しました..."
  }
}
```

### 5.3 台本生成後のフロー

1. Claude API が台本 JSON を生成
2. **JSON ファイルとして保存し、ユーザーに確認を求める**（自動で動画生成に進まない）
3. ユーザー承認後、音声生成 → 動画合成へ進む

> **重要**: AIの推測やテストデータの混入は厳禁。30フレーズ全てユーザー確認を取る。

### 5.4 Field Reference

#### meta オブジェクト

| フィールド | 型 | 必須 | 説明 | 例 |
|---|---|---|---|---|
| `theme` | string | Yes | テーマ名 | `"ビジネスメールで使える英語表現30選"` |
| `phrase_count` | int | Yes | フレーズ数 | `30` |
| `target_audience` | string | Yes | 対象者 | `"社会人・大学生"` |
| `detail_level` | string | Yes | 解説の詳しさ: `"brief"` / `"normal"` / `"detailed"` | `"normal"` |
| `difficulty_distribution` | object | Yes | 難易度配分 `{beginner, intermediate, advanced}` | `{"beginner": 10, "intermediate": 15, "advanced": 5}` |
| `generated_at` | string | Yes | 生成日時（ISO 8601 UTC） | `"2026-05-14T12:00:00+00:00"` |
| `generator` | string | Yes | 生成元識別子 | `"claude-api"` |
| `model_version` | string | Yes | 使用モデルID | `"claude-sonnet-4-6"` |
| `dialogue_mode` | bool | Yes | 対話型フォーマットか否か（試作では `false` 固定） | `false` |
| `version` | string | Yes | 台本スキーマバージョン | `"1.0"` |
| `title_candidates` | string[] | Yes | タイトル候補（3要素） | `["【通勤中の聞き流し】...", "...", "..."]` |

#### opening / ending オブジェクト

| フィールド | 型 | 必須 | 説明 | 例 |
|---|---|---|---|---|
| `narration_ja` | string | Yes | 日本語ナレーション | `"こんにちは、気合イングリッシュです。今回は..."` |

#### phrases[] 配列の各要素

| フィールド | 型 | 必須 | 説明 | 例 |
|---|---|---|---|---|
| `id` | int | Yes | 1始まりの連番 | `1` |
| `phrase_en` | string | Yes | 英語フレーズ（単独で意味が通る最小単位） | `"I hope this email finds you well."` |
| `meaning_ja` | string | Yes | 日本語訳（意訳） | `"お元気でお過ごしのことと存じます。"` |
| `explanation_ja` | string | Yes | 使用場面の解説（1〜2文） | `"ビジネスメールの冒頭で最も一般的な挨拶表現です。初めての相手にも使えます。"` |
| `example_en` | string | Yes | 例文（15語以内、フレーズを含む） | `"Hi Tom, I hope this email finds you well."` |
| `difficulty` | string | Yes | `"beginner"` / `"intermediate"` / `"advanced"` | `"beginner"` |
| `category` | string | Yes | テーマ内カテゴリ名 | `"挨拶"` |
| `is_review` | bool | Yes | 復習パートに含めるか（`true` は最大10個） | `true` |

---

## 6. ファイル構成

新規作成するファイル:

| ファイル | 役割 |
|---|---|
| `podcast_script_gen.py` | 台本生成（Claude API 呼び出し） |
| `podcast_audio_gen.py` | 音声生成（ElevenLabs / フォールバック） |
| `podcast_video_gen.py` | 動画合成（MoviePy、メインパート描画） |

既存ファイルへの変更:

| ファイル | 変更内容 |
|---|---|
| `main.py` | `run_podcast_generation()` エントリーポイント追加 |
| `app.py` | Podcast Mode の UI 追加（Streamlit） |

**変更しないファイル**:
- `video_gen.py`（Word Audio Mode / Exam Video Mode）
- `audio_gen.py`（既存モードの音声生成）— ただしユーティリティ関数は import して流用
- `script_gen.py`（既存モードの台本生成）
- `video_gen_listening.py`（リスニング動画生成）

---

## 7. 環境変数

`.env` ファイルで管理する:

| 変数名 | 用途 | 必須 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API（台本生成） | Yes |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS | Yes（フォールバック使用時は No） |
| `ELEVENLABS_VOICE_ID_ENGLISH_MALE` | 英語ネイティブ声（Adam） | No（デフォルト: `pNInz6obpgDQGcFmaJgB`） |
| `ELEVENLABS_VOICE_ID_USER_JA` | ユーザーのクローン声（日本語） | Yes（Voice Cloning で事前作成） |
| `OPENAI_API_KEY` | OpenAI TTS（フォールバック用） | No |
| `PODCAST_BGM_PATH` | BGMファイルパス | No（デフォルト: `assets/podcast_bgm.mp3`） |
| `PODCAST_TTS_PROVIDER` | TTS優先順位: `elevenlabs` / `openai` / `edge` | No（デフォルト: `elevenlabs`） |
| `PODCAST_SCRIPT_MODEL` | 台本生成モデル | No（デフォルト: `claude-sonnet-4-6`） |

> **環境変数命名規則**: Podcast Mode の環境変数はすべてプレフィックス `PODCAST_` で統一する（例: `PODCAST_SCRIPT_MODEL`, `PODCAST_TTS_PROVIDER`, `PODCAST_BGM_PATH`）。将来 `PODCAST_TTS_MODEL` 等が追加されても一貫性を保てる。ただし `ANTHROPIC_API_KEY` / `ELEVENLABS_API_KEY` 等のAPIキーはプロジェクト横断で使うため `PODCAST_` プレフィックスを付けない。

---

## 8. 出力仕様

| 項目 | 値 |
|---|---|
| 解像度 | 1280 × 720 |
| FPS | 24 |
| コーデック | libx264 |
| 音声コーデック | aac |
| 出力先 | `output/podcast/{theme}_{timestamp}.mp4` |
| 台本保存先 | `output/podcast/{theme}_{timestamp}_script.json` |

---

## 9. 処理フロー

```
1. ユーザーがテーマ・パラメータを入力
2. podcast_script_gen.py → Claude API で台本 JSON 生成
3. 台本 JSON をファイル保存 → ユーザーに確認依頼
4. ユーザー承認
5. podcast_audio_gen.py → 各セグメントの音声ファイル生成
   - opening_narration.mp3
   - phrase_{id}_en.mp3 (x30)
   - phrase_{id}_ja.mp3 (x30)
   - phrase_{id}_explanation.mp3 (x30)
   - phrase_{id}_example_en.mp3 (x30)
   - phrase_{id}_en_repeat.mp3 (x30)
   - review_intro.mp3
   - review_phrase_{id}_en.mp3 (x10)
   - review_phrase_{id}_ja.mp3 (x10)
   - ending_narration.mp3
6. podcast_video_gen.py → 音声＋画面を合成して MP4 出力
7. 出力ファイルパスを表示 → ユーザーが品質チェック
```

---

## 10. 既存モードとの関係

| 観点 | Word Audio Mode | Exam Video Mode | Podcast Mode（新規） |
|---|---|---|---|
| 生成関数の場所 | `video_gen.py` | `video_gen.py` | `podcast_video_gen.py`（独立） |
| 音声生成 | `audio_gen.py` | `audio_gen.py` / `audio_gen_listening.py` | `podcast_audio_gen.py`（独立、ユーティリティは流用） |
| 台本生成 | `script_gen.py` | `script_gen.py` | `podcast_script_gen.py`（独立） |
| データソース | CSV（単語帳） | CSV + script_gen | Claude API（動的生成） |
| BGM | あり（※target_specでは学習パート不使用） | なし | あり（Lo-Fi系、常時低音量） |
| 動画長 | 5〜60分 | 5〜15分 | 約30分 |

---

## 11. 未決定事項（ユーザー確認待ち）

- [ ] ElevenLabs の具体的な Voice ID（男性英語 / 女性日本語）
- [ ] BGM ファイルの選定（既存 `assets/podcast_bgm.mp3` を使うか、新規追加か）
- [ ] 復習パートの選定基準の詳細（上位10個固定か、ランダムか）
- [ ] Streamlit UI のデザイン（app.py への統合方針）
- [ ] 試作1本のフレーズ30個の内容（Claude API 生成後にレビュー）

---

## Future Work（試作後の発展方針）

### Voice Cloning の再検討
- 試作時（2026-05-14）の先行テストで Instant Voice Cloning を検証したが、品質不十分と判断し不採用
- 将来的に ElevenLabs の Professional Voice Cloning（より高品質な声のクローン、Creator プラン以上で利用可能）で再検討する
- 再採用条件: Professional Voice Cloning の日本語品質がプリセット声（Morioki）と同等以上であること

### 対話型フォーマットへの進化
- 現状の仕様は「説明型」: 男性英語声＋女性日本語声の交互読み上げ＋解説
- 業界調査（2025年）で「2人のAI音声による対話形式」が新興英語学習チャンネルの伸び筋と判明
- 将来的に以下のフォーマットへ拡張する：
  - キャラクターA（講師役）とキャラクターB（学習者役）の自然な対話
  - 学習者役が「これってどう違うんですか？」と質問し、講師役が解説する流れ
  - 視聴維持率の向上と差別化を狙う
- 設計余地: 台本JSONに `dialogue_mode: true/false` フラグを追加できる構造で実装する
- 試作1本目では `dialogue_mode: false`（説明型）で固定

### 復習パートの拡張
- 現状: 英語フレーズ（ゆっくり）→ 日本語訳 の2ステップ
- 将来: 英語フレーズ（ゆっくり）→ 日本語訳 → 英語フレーズ（通常速度）の3ステップに拡張可能
- 設計余地: `podcast_audio_gen.py` の復習パート生成ロジックを変更するだけで対応できる構造とする

### シリーズ展開計画
試作1本目（ビジネスメール編）が成功した場合、以下のシリーズ展開を想定：
- ビジネスメール編 ← 試作1本目
- 会議英語編
- 電話応対編
- 顧客対応編
- 出張・海外赴任編
- 上司への報告・相談編

---

## Video Title Guidelines

タイトルには以下の3要素を必ず含める：

1. **利用シーンの明示**
   - 例: 「通勤中」「作業用」「聞き流し」「BGM代わりに」
2. **効果・規模の強調**
   - 例: 「完全攻略」「これだけでOK」「30選」「保存版」
3. **具体的テーマ**
   - 例: 「ビジネスメール」「会議英語」「電話応対」

### 試作1本目のタイトル候補
- 「【通勤中の聞き流し】ビジネスメールで使える英語表現30選 〜完全保存版〜」
- 「【作業用BGM】ビジネスメール英語30フレーズ完全攻略」
- 「英語のビジネスメールで困らない！実用フレーズ30選【聞き流し30分】」

実際のタイトルは動画完成後にYouTubeアップロード時に決定する。台本生成時はメタデータとして候補3つを提案する。

### サムネイル方針（参考）
- 青基調（信頼感）＋ 黄色アクセント（注目）
- 大きなゴシック体で「30選」「完全攻略」を強調
- 顔写真なし、シンプル背景
- 将来的にAI生成キャラクター（講師役）を配置検討
