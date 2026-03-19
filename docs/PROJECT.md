PROJECT.md — 気合イングリッシュ チャンネル収益化プロジェクト

このファイルはClaudeとManusの共通コンテキストです。
タスク開始時に必ずこのファイルを参照し、完了後は「## 進捗ログ」を更新してください。


1. プロジェクト概要
項目内容チャンネル名気合イングリッシュチャンネルURLhttps://www.youtube.com/@気合イングリッシュジャンル英語学習（受験英語・英単語中心）現在の登録者数数千人規模収益化モデルYouTube広告 ＋ メンバーシップリポジトリhttps://github.com/sepa1224-sys/English_video_app
ゴール（優先順位順）

チャンネル登録者・再生数を伸ばす（広告収益の最大化）
動画生成を自動化する（video_gen.pyの安定運用）
メンバーシップ収益を立ち上げる
コンテンツ計画をデータドリブンにする


2. システム構成
コアファイル
ファイル役割video_gen.py動画生成メイン（MoviePy使用）video_gen_listening.pyリスニング動画生成audio_gen.py音声生成script_gen.pyスクリプト生成app.pyWebアプリ（Streamlit等）admin_app.py管理ツールuploader.pyYouTube自動アップロードmodels.pyデータモデル定義db_utils.pyDB操作
動画モード

Word Audio Mode — 英単語音声動画（現在リファクタリング中）
Listening Mode — リスニング練習動画
Podcast Mode — ポッドキャスト形式動画

データソース（英単語帳）

ターゲット1900 / 1400 / 1200
システム英単語
英単語帳鉄壁
LEAP
準1級でる順
東大・京大・阪大 過去問

既存仕様ドキュメント

docs/specs/data_structure.md — データ構造仕様


3. 役割分担
Claude（設計・思考・コード品質管理）

アーキテクチャ設計・仕様策定
docs/specs/ docs/adr/ の作成・更新
コードレビューと品質監視
チャンネル戦略の分析・提案
Manusへの指示書作成

Manus（実行・収集・自動化）

YouTubeチャンネルデータの収集・スクレイピング
Pythonスクリプトの実行
ファイル操作・整理
継続タスクの記憶・管理

人間（判断・承認）

戦略の最終決定
動画の品質チェック・公開判断
APIキー・認証情報の管理


4. 現在の最優先タスク
🔴 Priority 1（今すぐ）

 YouTube Data API v3 でチャンネル全動画データを取得

取得項目：タイトル・再生数・いいね数・コメント数・公開日・動画長・サムネイルURL・説明文・タグ
出力：data/channel_analysis/kiiai_english_channel.json と .csv



🟡 Priority 2（データ取得後）

 取得データをClaudeに渡して分析

再生数が伸びている動画のパターン抽出
最適な動画の長さ・投稿頻度の分析
タイトル・サムネイルの傾向分析



🟢 Priority 3（分析後）

 video_gen.py の Word Audio Mode 描画バグの最終確認
 チャンネル改善提案をコンテンツ計画に落とし込む
 docs/adr/ に設計判断を記録開始


5. 重要ルール（SPEC第一主義）

実装前に必ず docs/specs/ の仕様を確認・更新する
AIの推測でデータを補完・生成しない（実データのみ使用）
設計変更時は docs/adr/ に背景・理由を記録する
temp_* ファイルはGitにコミットしない（.gitignoreに追加済みか確認）
テストコードと本番コードを明確に分離する


6. 進捗ログ
2026-03-19

PROJECT.md 作成（Claude）
プロジェクト方針確定：チャンネル分析 → 動画自動生成改善 → 収益化
役割分担確定：Claude（設計）、Manus（実行）、GitHub（共通記憶）
次のアクション：ManusにYouTube Data API取得スクリプトを実行させる

2026-03-19（続き）

- YouTube Data API v3 APIキー作成（Manus）: englishpodcast プロジェクトで発行
- fetch_channel_data.py 作成・実行（Manus）
- 気合イングリッシュ チャンネル全41動画のデータ取得完了
- 出力: data/channel_analysis/kiiai_english_channel.json / .csv
- 次のアクション：ClaudeにCSVを渡して分析（Priority 2）


7. Manusへの初回指示
このプロジェクトに参加する際は以下を実行してください：

このファイル（PROJECT.md）を読む
docs/specs/data_structure.md を読む
Priority 1のタスクから着手する
タスク完了後、このファイルの「進捗ログ」に日付・内容・担当を追記する

Priority 1 実行手順（YouTube データ取得）
対象チャンネル: https://www.youtube.com/@気合イングリッシュ

Step 1: YouTube Data API v3のAPIキーを取得
  - https://console.cloud.google.com/ でプロジェクト作成
  - YouTube Data API v3 を有効化
  - APIキーを発行

Step 2: 以下のPythonスクリプトを作成・実行
  - チャンネルの全動画を取得（ページネーション対応）
  - 取得項目: video_id, title, published_at, view_count, like_count,
              comment_count, duration_seconds, thumbnail_url,
              description, tags
  - 出力先: data/channel_analysis/kiiai_english_channel.json
            data/channel_analysis/kiiai_english_channel.csv

Step 3: 取得完了後、CSVの先頭10行をClaudeに共有する
