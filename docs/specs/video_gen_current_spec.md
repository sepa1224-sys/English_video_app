# video_gen.py 現状仕様書

> コードから読み取れる事実のみを記述。推測・補足は含まない。

---

## 1. 実装されている関数

| 関数名 | 行 | 用途 |
|---|---|---|
| `generate_word_audio_video` | L194 | 単語カード動画生成 |
| `generate_exam_video` | L678 | リスニング試験動画生成 |

---

## 2. generate_word_audio_video のシーン構成

### 2-1. カウントダウン（L294〜L346）
- `use_countdown=True`（デフォルト）の場合のみ生成
- 5→4→3→2→1 の順で、各1.0秒のクリップを生成
- 計5クリップ

### 2-2. 単語カード（L348〜L595）
- `audio_results` の各アイテムに対して1クリップ生成
- クリップは `VideoClip(make_frame)` で構築（動的フレーム）
- 各クリップの長さ:
  - jp_audio あり: `jp_trigger + jp_audio.duration + 0.5` 秒
  - jp_audio なし: `eng_dur + 0.5` 秒

### 2-3. エンドスクリーン（L597〜L641）
- `end_left`、`end_right`、`outro_audio_path` のいずれかが存在する場合のみ生成
- 長さ: `end_duration`（デフォルト10秒）

### シーン順序
```
[カウントダウン x5] → [単語カード x N] → [エンドスクリーン]
```
`concatenate_videoclips(clips, method="compose")` で結合（L654）

---

## 3. generate_exam_video のシーン構成

### 3-1. イントロ（L971〜L1007）
- 固定長: 3.0秒（L993）
- 音声: `assets/intro_{university}.mp3`（todai / osaka / kyoto で切り替え）
- 条件: 音声ファイルが存在する場合のみ生成

### 3-2. Part1: Listening Section（L1012〜L1074）
- 長さ: `full_part1_audio.duration`（= sec_list_audio + se_complete + full_dialog_audio の合計）
- 表示: "Listening Section" 文字列のみ

### 3-3. Part2: Question Section（L1076〜L1229）
- 先頭に "Question Section" タイトルスライド（長さ: `q_trans_audio.duration + 1.0` または 3.0秒）
- 続けて `questions` リストの各問題スライド（各 `q_dur` 秒）

### 3-4. Part3: Review Section（L1231〜L1329）
- 先頭に "Review Section" タイトルスライド（長さ: `r_trans_audio.duration + 1.0` または 3.0秒）
- 続けて `listening_segments` の各発話セグメントスライド

### シーン順序（L1331〜L1342）
```
[イントロ] → [Listening Section] → [Question Section] → [Review Section] → [Question Section（再掲）]
```
`concatenate_videoclips(final_clips_list)` で結合（L1345）

---

## 4. 描画要素

### 4-1. フォント解決順序（共通）

**`get_font_path()`（L63〜L80）**
以下の順で存在チェックし、最初に見つかったものを返す:
1. `C:\Windows\Fonts\Montserrat-ExtraBold.ttf`
2. `C:\Windows\Fonts\Montserrat-Bold.ttf`
3. `C:\Windows\Fonts\NotoSans-Black.ttf`
4. `C:\Windows\Fonts\NotoSans-Bold.ttf`
5. `C:\Users\PC_User\AppData\Local\Microsoft\Windows\Fonts\NotoSansJP-Bold.otf`
6. `C:\Users\PC_User\AppData\Local\Microsoft\Windows\Fonts\NotoSansJP-Regular.otf`
7. `C:\Windows\Fonts\NotoSansJP-Bold.otf`
8. `C:\Windows\Fonts\NotoSansJP-Regular.otf`
9. `C:\Windows\Fonts\meiryo.ttc`
10. `C:\Windows\Fonts\msgothic.ttc`
11. `C:\Windows\Fonts\arial.ttf`

**Black フォント候補（L350〜L358）**（単語カードの英単語用）:
1. Montserrat-ExtraBold.ttf
2. Montserrat-Bold.ttf
3. NotoSansJP-Black.otf（AppData or System）
4. NotoSansJP-ExtraBold.otf（AppData or System）
5. NotoSansJP-Bold.otf（AppData or System）
→ 見つからない場合 `font_path_jp` にフォールバック

**Regular フォント候補（L360〜L365）**（日本語意味・ID テキスト用）:
1. Montserrat-SemiBold.ttf
2. Montserrat-Regular.ttf
3. NotoSansJP-Regular.otf（AppData or System）
→ 見つからない場合 `font_path_jp` にフォールバック

---

### 4-2. generate_word_audio_video の描画要素

#### カウントダウン（L297〜L315）
| 要素 | フォント | サイズ | 色 | 位置 |
|---|---|---|---|---|
| カウント数字 | font_path_jp | 200 | white | center (640, 360), anchor="mm" |

#### 単語カード（L492〜L581, make_frame 関数内）

**ID テキスト（L518〜L522）**
| 要素 | フォント | サイズ | 色 | 位置 |
|---|---|---|---|---|
| `No. {id:04d}` | regular_path | 30 | "gray" | (50, 50) |

**英単語（L524〜L543）**
| 状態 | フォント | サイズ | 色 | y 座標 |
|---|---|---|---|---|
| `t < jp_trigger` | black_path | 140 | "white" | `300 - th//2` |
| `t >= jp_trigger` | black_path | 140 | "white" | `220 - th//2` |
- x 座標: `(1280 - tw) // 2`（水平中央）

**日本語意味（L546〜L579）**
`t >= jp_trigger` のときのみ表示
| 要素 | フォント | サイズ | 色 | 開始位置 |
|---|---|---|---|---|
| 意味テキスト（各行） | regular_path | 80 | "#CCCCCC" | x=200, y=450 |
- 行区切り: `[、/;；／\n]` で分割
- 各行の先頭に丸数字（①②...）を付与（U+2460〜）
- 行間: `lh * 1.5`（lh = textbbox で計測した行高）

#### ロゴ（L496〜L516）
- ソース: `assets/logo_kiai.png`
- 最大幅: 200px（アスペクト比を維持してリサイズ）
- 位置: `(1280 - new_w - 20, 20)`（右上）
- paste 時に RGBA の mask を使用

#### エンドスクリーン（L599〜L618）
| 要素 | フォント | サイズ | 色 | 位置 |
|---|---|---|---|---|
| end_left | regular_path | 56 | "white" | (100, 650) |
| end_right | regular_path | 56 | "white" | (1180, 650), anchor="rm" |

---

### 4-3. generate_exam_video の描画要素

#### イントロ（L995〜L1004）
| 要素 | フォント | サイズ | 色 | start_y |
|---|---|---|---|---|
| intro_text_1（大学名＋受験リスニング...） | font_path_jp | 60 | "white" | 300 |
| intro_text_2（「スクリプトと答え、解説は概要欄を参照」） | font_path_jp | 30 | (200, 200, 255) | 400 |

#### Listening Section タイトル（L1065〜L1071）
| 要素 | フォント | サイズ | 色 | 位置 |
|---|---|---|---|---|
| "Listening Section" | font_path_en | 80 | "white" | 垂直中央（start_y=None） |

#### Question Section タイトル（L1102〜L1107）
| 要素 | フォント | サイズ | 色 | 位置 |
|---|---|---|---|---|
| "Question Section" | font_path_en | 80 | "white" | 垂直中央（start_y=None） |

#### 問題スライド（L1166〜L1221）
- `total_chars > 200` の場合: q_size=35, c_size=30
- デフォルト: q_size=50, c_size=40
- フォントサイズは2ずつ縮小して `total_h <= 630` になるまで繰り返す（最小15）
- start_y: `max(30, (720 - total_h) // 2)`

| 要素 | 色 | spacing |
|---|---|---|
| 問題文 (`Q{n}: {question}`) | "white" | 15 |
| 各選択肢 | (200, 255, 200) | 15 |
- 問題文と選択肢の間隔: 40px（L1217）
- 選択肢間の間隔: 10px（L1221）

#### Review Section タイトル（L1257〜L1262）
| 要素 | フォント | サイズ | 色 | 位置 |
|---|---|---|---|---|
| "Review Section" | font_path_en | 80 | "white" | 垂直中央（start_y=None） |

#### スクリプトスライド（L1283〜L1326）
- 英語テキスト: 初期サイズ65、最小サイズ30、max_width=1280*0.85、max_height=600 で `get_fitted_font` により自動縮小
- 色: "white"
- 語彙ハイライト: 単語リスト内の語（活用形含む）を "#FF0000" で表示
- 位置: 垂直中央（start_y=None）

---

## 5. BGM・音声の合成ロジック

### 5-1. generate_word_audio_video

#### BGM 検索順序（L205〜L235）
1. `assets/` 内のファイル名に "歩いて" または "aruite" を含む MP3/WAV
2. プロジェクトルート内のファイル名に同条件のもの
3. `assets/BGM.mp3`
4. `assets/` 内の最初の MP3/WAV ファイル
5. プロジェクトルートの最初の MP3/WAV ファイル

#### カウントダウン音声（L317〜L346）
- パス: `extras.get("countdown_audio")` または `"assets/Accent08-1.mp3"`
- フォールバック: プロジェクトルートの同ファイル名
- 各カウントに同じ音声ファイルをそのまま付与（ループなし）

#### 単語音声の合成（L420〜L490）
- metadata の `display_mode` によって eng/jp に分類:
  - `step1`, `step3`, `step4` → 英語音声区間
  - `step2` → 日本語音声区間
- `eng_audio` を start=0 で配置
- `jp_audio` を start=`jp_trigger` で配置
  - `jp_trigger = eng_dur + gap_eng_jap`
  - `gap_eng_jap = extras.get("gap_eng_to_jap", extras.get("interval_eng_jap", 0.5))`
- `CompositeAudioClip(audio_elements)` でミックス

#### エンドスクリーン音声（L620〜L640）
- BGM ファイルをそのまま付与（音量調整なし）

#### 出力設定（L657〜L664）
```
fps=24, codec="libx264", audio_codec="aac", threads=4, logger=None
```

---

### 5-2. generate_exam_video

#### SE（効果音）設定（L44〜L61, `apply_se_settings`）
- volume: 0.3（`with_volume_scaled` または `volumex`）
- audio_fadein: 0.5秒
- audio_fadeout: 0.5秒

#### SE ファイル検索順（L1045〜L1052）
1. `special_clips.get("se_complete")` で指定されたパス
2. `assets/完了4.mp3`
3. `assets/パッ.mp3`
4. `assets/next_word.mp3`

#### Part1 音声構成（L1032〜L1062）
```
sec_listening.mp3 → se_complete（volume=0.3, fade=0.5s）→ full_dialog_audio
```
`concatenate_audioclips` で直列結合

#### Question Section 遷移音声（L1090〜L1099）
```
question_section.mp3 → se_complete（volume=0.3, fade=0.5s）
```

#### 問題音声構成（L1128〜L1159）
```
q_main_audio（offset=0）
+ choice_1_audio（offset=q_main_audio.duration + 0.2）
+ choice_2_audio（offset=前の終端 + 0.2）
+ ...
```
`CompositeAudioClip` で合成
クリップ長: `current_time_q + 3.0`（最後3秒無音）

#### Review Section 遷移音声（L1245〜L1254）
```
review_section.mp3 → se_complete（volume=0.3, fade=0.5s）
```

#### 出力設定（L1349）
```
fps=24, codec="libx264", audio_codec="aac"
```

---

## 6. アニメーション・タイミングの実装

### 6-1. 単語カードの動的フレーム（L492〜L581）

`VideoClip(make_frame).with_duration(total_duration)` を使用。
`make_frame(t)` の中で時刻 `t` を参照して描画内容を切り替える:

| 時刻 | 英単語 y 座標 | 日本語意味 |
|---|---|---|
| `t < jp_trigger` | `300 - th//2` | 非表示 |
| `t >= jp_trigger` | `220 - th//2` | 表示（x=200, y=450） |

- `jp_trigger = eng_dur + gap_eng_jap`
- フレームレートは書き出し時の fps=24 に依存（中間補完なし）

### 6-2. カウントダウンのタイミング（L294〜L315）
- `for n in range(5, 0, -1)` で5回ループ
- 各クリップ: `create_base_clip(1.0, draw_countdown)` → 1秒固定
- アニメーションなし（静止画＋音声）

### 6-3. 問題スライドのタイミング（L1160〜L1165）
- 音声が存在する場合: `q_dur = current_time_q + 3.0`
  - `current_time_q` は問題音声・選択肢音声を順次配置した総長
- 音声が存在しない場合: `q_dur = 10.0`（固定）
- アニメーションなし（静止画＋音声）

### 6-4. イントロの固定タイミング（L993）
- `intro_duration = 3.0`（固定値、コメントで `#` のみ記載）

### 6-5. Review Section セグメントのタイミング（L1272〜L1274）
- `seg_dur = seg["duration"]`（外部から渡された値をそのまま使用）
- `seg_dur <= 0` のセグメントはスキップ

### 6-6. セクション遷移スライドのタイミング
- `q_trans_audio.duration + 1.0`（音声あり）または `3.0`（音声なし）（L1100）
- `r_trans_audio.duration + 1.0`（音声あり）または `3.0`（音声なし）（L1255）

---

## 7. 背景・ロゴ

### 背景（共通）
- `assets/background_black.png` を優先使用（1280x720 にリサイズ）
- ファイルが存在しない場合: `Image.new('RGB', (1280, 720), color=(0, 0, 0))` で純黒を生成

### ロゴ（generate_word_audio_video のみ）
- `assets/logo_kiai.png`
- 最大幅200px、アスペクト比維持（`Image.LANCZOS`）
- 位置: `(1280 - new_w - 20, 20)`
- `create_base_clip` 内では CompositeVideoClip で合成（L286〜L291）
- `make_frame` 内では `img.paste` で直接合成（L514〜L516）

---

## 8. シャドウ描画の実装（`draw_centered_text` / `draw_centered_text_inner`）

- `stroke_width = 2`
- (-2,-2) 〜 (+2,+2) の全オフセット（中心除く）を黒で描画
- さらに (3,3)〜(6,6) の斜め方向4点を黒で描画（`shadow_depth = 6`）
- 最後に本体テキストを前景色で描画
