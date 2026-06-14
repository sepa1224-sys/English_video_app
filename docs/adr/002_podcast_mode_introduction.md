# ADR 002: Podcast Mode の導入

## ステータス
**提案中 (Proposed)** — ユーザーレビュー待ち

## 日付
2026-04-23

## コンテキスト

### 問題
YouTube 収益化ポリシー（2025年7月改定）により、既存の Word Audio Mode（英単語＋日本語訳のみを繰り返すフラッシュカード形式）がテンプレート動画と判定され、広告収益化の対象外となるリスクが発生した。

### チャンネルデータからの知見
`docs/content_plan.md` の分析結果より:
- 30〜60分の長尺動画の平均再生数は **9,779回**（5分以下の **48倍**）
- 視聴者は「通勤・作業中の聞き流し」として利用している
- 音声主体の長尺コンテンツに強い需要がある

### 技術的制約
- 既存の `video_gen.py` は Word Audio Mode と Exam Video Mode の2関数を持ち、密結合ではないが同一ファイル内に共存している
- 既存の `audio_gen.py` は OpenAI / ElevenLabs / Edge-TTS の3つの TTS エンジンに対応済み
- プロジェクトのルール「SPEC第一主義」により、実装前に仕様を確定する必要がある

---

## 検討した選択肢

### 選択肢 A: video_gen.py に `generate_podcast_video()` を追加
- **メリット**: 既存の描画ユーティリティ（`draw_centered_text`, `get_font_path` 等）を直接再利用できる
- **デメリット**: video_gen.py がさらに肥大化する（現時点で約1400行）。Word Audio / Exam の既存ロジックに影響を与えるリスク

### 選択肢 B: 独立ファイル `podcast_video_gen.py` として新規作成（採用）
- **メリット**: 既存モードに一切影響しない。独立してテスト・開発できる。ユーザー要件「既存モードには一切手を加えない」を確実に満たす
- **デメリット**: 描画ユーティリティの一部をコピーまたは共通モジュールに抽出する必要がある

### 選択肢 C: 共通描画ライブラリを先に抽出してからPodcast Modeを実装
- **メリット**: 最もクリーンなアーキテクチャ
- **デメリット**: 既存の video_gen.py をリファクタリングする必要があり、「既存モードに手を加えない」制約に反する。スコープが大きすぎる

---

## 決定事項

**選択肢 B** を採用する。

Podcast Mode は以下の3つの独立ファイルとして実装する:
- `podcast_script_gen.py` — 台本生成（Claude API）
- `podcast_audio_gen.py` — 音声生成（ElevenLabs + フォールバック）
- `podcast_video_gen.py` — 動画合成（MoviePy）

既存ファイルへの変更は `main.py`（エントリーポイント追加）と `app.py`（UI追加）のみに限定する。

---

## 理由

1. **ユーザー要件の厳守**: 「既存の Word Audio Mode、Exam Video Mode には一切手を加えない」が明確な制約として示されている
2. **リスク最小化**: ADR 001 で記録された Word Audio Mode の二重描画バグ修正の成果を保護する。独立ファイルであれば、Podcast Mode の開発中に既存モードのリグレッションが発生しない
3. **段階的な共通化**: 将来的に描画ユーティリティの共通モジュール化が必要になった場合は、その時点で別ADRを起こして判断する。現時点では `get_font_path()` 等の小さなユーティリティは podcast_video_gen.py 内にコピーして使用する

---

## 技術的な決定の詳細

### TTS エンジンの選定
- **主選択: ElevenLabs API** — 日本語の自然さと英語の明瞭さの両立。多言語対応モデル `eleven_multilingual_v2` を使用
- **フォールバック順**: ElevenLabs → OpenAI TTS → Edge-TTS
- 既存 `audio_gen.py` の `generate_audio_segment_elevenlabs()` / `generate_audio_segment_openai()` / `generate_audio_segment_edge()` を import して流用する（コピーではなく呼び出し）

### 台本生成に Claude API を使う理由
- 既存の `script_gen.py` は単語帳CSVからの読み込みに特化しており、解説文・例文の自動生成機能を持たない
- ポッドキャスト台本は「フレーズ＋意味＋解説＋例文」の構造を持ち、これは LLM の得意領域
- ただし、生成結果は必ず JSON ファイルとして保存し、ユーザー確認を経てから音声生成に進む（AIの推測やテストデータの混入を防ぐ）

### BGM の扱い
- Word Audio Mode の target_spec では「学習パートでBGMを一切使用しない」とされているが、Podcast Mode は「聞き流し」が前提であり、BGM なしでは長時間聴取時に単調になる
- BGM 音量はメイン音声の邪魔にならないよう 0.08〜0.15 の範囲に設定

### 環境変数の命名
- 既存の `OPENAI_API_KEY` は audio_gen.py で既に使用されているため共有
- ElevenLabs の Voice ID は Podcast Mode 専用の変数名（`ELEVENLABS_VOICE_ID_ENGLISH_MALE` / `ELEVENLABS_VOICE_ID_USER_JA`）を新設する。既存の `audio_gen.py` のグローバル定数（`ELEVENLABS_VOICE_MALE` 等）とは独立させ、影響範囲を限定する
- Podcast Mode の環境変数はプレフィックス `PODCAST_` で統一（例: `PODCAST_SCRIPT_MODEL`, `PODCAST_TTS_MODEL`）。ただし `ELEVENLABS_*` / `ANTHROPIC_*` 等のAPIキー・Voice IDはプロジェクト横断で使うためプレフィックスを付けない

### 音声戦略: ハイブリッド型の採用（2026-05-14 追記）

YouTube 収益化ポリシー（2025年7月改定）で AI 完全自動の量産コンテンツが "inauthentic content" と判定されるリスクへの対応として、音声戦略を検討した。

#### 却下した案

**案 A: AI 完全自動**
- 英語・日本語ともに AI プリセット声を使用
- メリット: 最も簡単、Voice Cloning 不要
- **却下理由**: YouTube が AI 完全自動と判定した場合に収益化を剥奪されるリスクが高い。2025年7月以降、同様の英語学習チャンネルで収益化停止の事例が複数報告されている

**案 B: フル人間声**
- 英語・日本語ともにユーザー自身が録音
- メリット: 収益化リスクゼロ
- **却下理由**: 英語フレーズの発音品質がネイティブレベルに届かない。毎回30フレーズ分を録音する工数が量産フェーズで現実的でない

#### 採用案

**案 C: ハイブリッド型（採用）**
- 英語フレーズ: ネイティブ AI 声（ElevenLabs Adam）で学習教材としての正統性を担保
- 日本語ナレーション: ユーザー自身の Voice Cloning で人間味を担保
- バランス: 収益化リスクを抑えつつ、量産可能な工数に収める
- Voice Cloning は一度セットアップすれば全シリーズで再利用可能

### 音声戦略の修正: クローン声 → プリセット声（2026-05-14 追記）

先行テストで Voice Cloning（Instant）の品質を検証した結果、戦略を修正した。

#### テスト内容
- オープニングナレーション（228文字）を3パターンの voice_settings で生成
  - default: stability=0.5, similarity_boost=0.75 → 34.5秒
  - clone_boost: stability=0.5, similarity_boost=0.85 → 33.7秒
  - clone_stable: stability=0.7, similarity_boost=0.85 → 32.1秒

#### 判断
- 3パターンとも「品質がもう一歩」「AI特有の違和感がある」とユーザーが判断
- Instant Voice Cloning の日本語品質が、学習コンテンツのナレーションとしては不十分

#### 修正後の戦略: プリセット声ベース
- 日本語: ElevenLabs プリセット声「Morioki」（日本人女性声）を採用
- 英語: Adam（変更なし）
- Voice Cloning は将来 Professional Voice Cloning（Creator プラン以上）で再検討

#### 収益化リスクへの代替対策
音声面でのハイブリッド（人間声の混入）は行わず、以下の運用面で対応：
- 動画説明欄での運営者情報・AI使用の透明性開示
- コメント欄での運営者本人による交流
- シリーズ内でのテーマ・構成バリエーション
- オリジナル台本（解説・例文・文化的注意点付き）による独自性担保

---

## 結果（実装後に記入）

_（未実装のためブランク）_

---

## 参照

- `docs/specs/podcast_mode_spec.md` — Podcast Mode 仕様書
- `docs/specs/video_gen_current_spec.md` — 既存 video_gen.py の現状仕様
- `docs/content_plan.md` — チャンネルデータ分析と戦略
- `docs/adr/001_word_audio_mode_rendering.md` — Word Audio Mode 描画ロジックの設計判断
