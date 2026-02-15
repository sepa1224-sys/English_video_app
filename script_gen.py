import os
import time
import json
import random
import csv
import history_manager


# Example generation and caching
try:
    from example_gen import generate_examples
except ImportError:
    generate_examples = None

# OpenAI library
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Optional pandas for robust CSV loading
try:
    import pandas as pd
except ImportError:
    pd = None
def load_vocabulary(level: str, day_number: int = 1) -> list:
    """
    指定されたレベルの単語リストを読み込む。
    - ターゲット1900: CSVからDay番号に基づいて抽出
    - その他: JSONから取得
    """
    if level == "OsakaHybrid":
        return load_osaka_hybrid_vocab(total_count=15)

    if level == "英単語帳鉄壁":
        # Day 1 -> 1-10
        start_id = (day_number - 1) * 10 + 1
        end_id = start_id + 9
        vocab_list = load_teppeki_words(start_id, end_id)
        # Add empty fields for consistency
        for v in vocab_list:
            v["definition"] = ""
            v["example"] = ""
        return vocab_list

    if level == "ターゲット1900":
        csv_file = os.path.join("data", "ターゲット1900 - Sheet1.csv")
        if not os.path.exists(csv_file):
            print(f"  ! Warning: {csv_file} not found.")
            return []
        
        vocab_list = []
        try:
            # エンコーディング対応 (utf-8-sig -> cp932 -> utf-8)
            encodings = ["utf-8-sig", "cp932", "utf-8"]
            all_rows = []
            
            for enc in encodings:
                try:
                    with open(csv_file, "r", encoding=enc) as f:
                        # ヘッダーがない可能性が高いので、csv.readerで読み込む
                        reader = csv.reader(f)
                        all_rows_raw = list(reader)
                        
                        # 辞書リストに変換
                        all_rows = []
                        for i, r in enumerate(all_rows_raw):
                            if len(r) >= 3:
                                # col 0: ID, col 1: Word, col 2: Meaning
                                row_id = r[0].strip()
                                # 1行目のIDが空なら1とみなす補正 (ターゲット1900の仕様推測)
                                if i == 0 and not row_id and r[1].strip().lower() == "create":
                                    row_id = "1"
                                    
                                all_rows.append({
                                    "番号": row_id,
                                    "英単語": r[1].strip(),
                                    "意味": r[2].strip()
                                })
                                
                    if all_rows:
                        print(f"  - CSV loaded successfully with encoding: {enc} (Rows: {len(all_rows)})")
                        break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            
            if not all_rows:
                print("  ! Error: Failed to load CSV with any encoding.")
                return []
                
            # Day番号に基づいて10個選択 (Day 1: 0-9, Day 2: 10-19...)
            start_idx = (day_number - 1) * 10
            end_idx = start_idx + 10
            
            # 範囲外ならランダムまたはループ、ここではループさせる
            if start_idx >= len(all_rows):
                start_idx = start_idx % len(all_rows)
                end_idx = start_idx + 10
            
            selected_rows = all_rows[start_idx:end_idx]
            
            for row in selected_rows:
                vocab_list.append({
                    "id": row.get("番号", ""),
                    "word": row.get("英単語", ""),
                    "meaning": row.get("意味", ""),
                    "definition": "", # GPTに生成させる
                    "example": ""     # GPTに生成させる
                })
            return vocab_list
            
        except Exception as e:
            print(f"  ! Error loading CSV: {e}")
            return []

    # 既存のJSON読み込み
    vocab_file = os.path.join("data", "vocabulary.json")
    if not os.path.exists(vocab_file):
        print(f"  ! Warning: {vocab_file} not found.")
        return []
        
    try:
        with open(vocab_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get(level, [])
    except Exception as e:
        print(f"  ! Error loading vocabulary JSON: {e}")
        return []

def load_teppeki_words(start_id: int, end_id: int) -> list:
    """
    Load words from '英単語帳鉄壁.csv' by ID range.
    """
    csv_file = os.path.join("data", "英単語帳鉄壁.csv")
    if not os.path.exists(csv_file):
        print(f"  ! Error: {csv_file} not found.")
        return []
        
    words = []
    try:
        encodings = ["utf-8-sig", "cp932", "utf-8"]
        all_rows = []
        for enc in encodings:
            try:
                with open(csv_file, "r", encoding=enc) as f:
                    reader = csv.reader(f)
                    all_rows = list(reader)
                if all_rows:
                    break
            except:
                continue
                
        if not all_rows:
            return []
            
        for row in all_rows:
            if len(row) < 3: continue
            try:
                # ID, Word, Meaning
                row_id = int(row[0].strip().replace('"', ''))
                if start_id <= row_id <= end_id:
                    words.append({
                        "id": row_id,
                        "word": row[1].strip(),
                        "meaning": row[2].strip(),
                        "source": "鉄壁",
                        "source_label": f"鉄壁 #{row_id}"
                    })
            except ValueError:
                continue
                
        words.sort(key=lambda x: x["id"])
        print(f"  - Loaded {len(words)} Teppeki words (IDs {start_id}-{end_id}).")
        return words
    except Exception as e:
        print(f"  ! Error loading Teppeki CSV: {e}")
        return []

def load_target1900_words(start_id: int, end_id: int) -> list:
    """
    Load words from 'ターゲット1900 - Sheet1.csv' by ID range.
    """
    csv_file = os.path.join("data", "ターゲット1900 - Sheet1.csv")
    if not os.path.exists(csv_file):
        print(f"  ! Error: {csv_file} not found.")
        return []
        
    words = []
    try:
        encodings = ["utf-8-sig", "cp932", "utf-8"]
        all_rows = []
        for enc in encodings:
            try:
                with open(csv_file, "r", encoding=enc) as f:
                    reader = csv.reader(f)
                    all_rows = list(reader)
                if all_rows:
                    break
            except:
                continue
                
        if not all_rows:
            return []
            
        for i, row in enumerate(all_rows):
            if len(row) < 2: continue
            
            # Special handling for potentially missing ID in first row or weird formatting
            try:
                row_id_str = row[0].strip().replace('"', '')
                if not row_id_str and i == 0 and row[1].strip().lower() == "create":
                     row_id = 1
                elif row_id_str.isdigit():
                    row_id = int(row_id_str)
                else:
                    continue
                    
                if start_id <= row_id <= end_id:
                    words.append({
                        "id": row_id,
                        "word": row[1].strip(),
                        "meaning": row[2].strip() if len(row) > 2 else "",
                        "source": "ターゲット1900",
                        "source_label": f"ターゲット1900 #{row_id}"
                    })
            except ValueError:
                continue
                
        words.sort(key=lambda x: x["id"])
        print(f"  - Loaded {len(words)} Target 1900 words (IDs {start_id}-{end_id}).")
        return words
    except Exception as e:
        print(f"  ! Error loading Target 1900 CSV: {e}")
        return []

def load_csv_data(file_path: str, source_name: str) -> list:
    """
    Robust CSV loader that handles multiple encodings and column variations.
    Returns a list of dicts with keys: 'id', 'word', 'meaning', 'source', 'source_label'.
    """
    if not os.path.exists(file_path):
        print(f"  ! Error: File not found: {file_path}")
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    encodings_to_try = ["utf-8-sig", "utf-8", "cp932", "shift_jis"]
    loaded_rows = []
    used_encoding = ""
    
    # 1. Try encodings
    for enc in encodings_to_try:
        try:
            with open(file_path, "r", encoding=enc) as f:
                # Read first line to check if readable
                first_line = f.readline()
                f.seek(0) # Reset
                reader = csv.reader(f)
                loaded_rows = list(reader)
            if loaded_rows:
                used_encoding = enc
                print(f"  - Successfully loaded {os.path.basename(file_path)} using {enc}")
                break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  ! Warning: Failed to read with {enc}: {e}")
            continue
            
    if not loaded_rows:
        error_msg = f"Failed to load {os.path.basename(file_path)}. Tried encodings: {encodings_to_try}"
        print(f"  ! {error_msg}")
        raise ValueError(error_msg)

    # 2. Parse Rows (Header Detection & Column Mapping)
    parsed_words = []
    header_row = None
    data_rows = loaded_rows
    
    # Check first row for header-like strings
    if loaded_rows:
        first_row = loaded_rows[0]
        # Heuristic: If first col is NOT a number, assume header
        if first_row and len(first_row) > 0:
            first_col = first_row[0].strip().replace('"', '')
            if not first_col.isdigit():
                header_row = [c.lower().strip() for c in first_row]
                data_rows = loaded_rows[1:]
    
    # Column Indices (Default: 0=ID, 1=Word, 2=Meaning)
    idx_id, idx_word, idx_mean = 0, 1, 2
    
    # If header found, try to map columns
    if header_row:
        # Map for ID
        if "id" in header_row: idx_id = header_row.index("id")
        elif "no" in header_row: idx_id = header_row.index("no")
        elif "番号" in header_row: idx_id = header_row.index("番号")
        
        # Map for Word
        if "word" in header_row: idx_word = header_row.index("word")
        elif "単語" in header_row: idx_word = header_row.index("単語")
        elif "english" in header_row: idx_word = header_row.index("english")
        
        # Map for Meaning
        if "meaning" in header_row: idx_mean = header_row.index("meaning")
        elif "mean" in header_row: idx_mean = header_row.index("mean")
        elif "意味" in header_row: idx_mean = header_row.index("意味")
        elif "japanese" in header_row: idx_mean = header_row.index("japanese")
        
    for row in data_rows:
        if len(row) <= max(idx_id, idx_word, idx_mean):
            continue
            
        try:
            row_id_str = row[idx_id].strip().replace('"', '')
            if not row_id_str.isdigit():
                continue
                
            row_id = int(row_id_str)
            word_text = row[idx_word].strip()
            meaning_text = row[idx_mean].strip()
            
            if word_text and meaning_text:
                parsed_words.append({
                    "id": row_id,
                    "word": word_text,
                    "meaning": meaning_text,
                    "source": source_name,
                    "source_label": f"{source_name} #{row_id}"
                })
        except Exception:
            continue
            
    parsed_words.sort(key=lambda x: x["id"])
    return parsed_words

def load_reference_corpus(university: str) -> tuple:
    """
    Load reference corpus and key features for the specific university.
    Returns (script_content, key_features) or (None, None) if not found.
    Target File: data/data_reference_corpus.csv - シート1.csv
    """
    csv_file = os.path.join("data", "data_reference_corpus.csv - シート1.csv")
    if not os.path.exists(csv_file):
        print(f"  - Note: Reference corpus CSV not found at {csv_file}. Using standard prompts.")
        return None, None
        
    uni_map = {
        "todai": "UTokyo_L",
        "kyoto": "Kyoto_L",
        "osaka": "Osaka_L"
    }
    target_category = uni_map.get(university)
    if not target_category:
        return None, None
    
    # Try pandas first for robust handling of file name/encoding
    encodings = ["utf-8-sig", "utf-8", "cp932", "shift_jis"]
    if pd is not None:
        for enc in encodings:
            try:
                df = pd.read_csv(csv_file, encoding=enc)
                # Normalize columns
                cols = {c.lower().strip(): c for c in df.columns}
                col_cat = cols.get("category")
                col_script = cols.get("script_content") or cols.get("script")
                col_feat = cols.get("key_features") or cols.get("features") or cols.get("feature")
                if not col_cat or not col_script:
                    continue
                # Filter by category
                subset = df[df[col_cat].astype(str).str.strip() == target_category]
                if subset.empty:
                    continue
                first_row = subset.iloc[0]
                script_content = str(first_row[col_script]).strip()
                key_features = str(first_row[col_feat]).strip() if col_feat else ""
                print(f"  - Found reference corpus for {university} ({target_category}) via pandas ({enc})")
                return script_content, key_features
            except Exception as e:
                continue
        # If pandas failed, fall back to csv module
    
    # Fallback: csv module
    try:
        loaded_rows = []
        used_enc = ""
        for enc in encodings:
            try:
                with open(csv_file, "r", encoding=enc) as f:
                    reader = csv.reader(f)
                    loaded_rows = list(reader)
                if loaded_rows:
                    used_enc = enc
                    break
            except Exception:
                continue
        if not loaded_rows:
            return None, None
        header = [h.strip().lower() for h in loaded_rows[0]] if loaded_rows else []
        idx_cat = -1
        idx_script = -1
        idx_feat = -1
        for i, h in enumerate(header):
            if "category" in h: idx_cat = i
            elif "script_content" in h or "script" in h: idx_script = i
            elif "key_features" in h or "features" in h or "feature" in h: idx_feat = i
        if idx_cat == -1 or idx_script == -1:
            print("  ! Warning: Required columns (Category, Script_Content) not found in corpus CSV.")
            return None, None
        for row in loaded_rows[1:]:
            if len(row) <= max(idx_cat, idx_script, idx_feat):
                continue
            cat_val = row[idx_cat].strip()
            if cat_val == target_category:
                script_content = row[idx_script].strip()
                key_features = row[idx_feat].strip() if idx_feat != -1 else ""
                print(f"  - Found reference corpus for {university} ({target_category}) via csv ({used_enc})")
                return script_content, key_features
        print(f"  - No reference data found for category {target_category}")
        return None, None
    except Exception as e:
        print(f"  ! Error loading reference corpus: {e}")
        return None, None

def load_systan_words(start_id: int, end_id: int) -> list:
    """
    Load words from 'システム英単語 - シート1.csv' by ID range.
    """
    csv_file = os.path.join("data", "システム英単語 - シート1.csv")
    try:
        all_words = load_csv_data(csv_file, "システム英単語")
        # Filter by range
        filtered = [w for w in all_words if start_id <= w["id"] <= end_id]
        print(f"  - Loaded {len(filtered)} SysTan words (IDs {start_id}-{end_id}).")
        return filtered
    except Exception as e:
        print(f"  ! Error loading SysTan CSV: {e}")
        # Propagate error for main.py to display
        raise RuntimeError(f"SysTan Load Error: {e}")

def load_derujun_words(start_id: int, end_id: int) -> list:
    """
    Load words from 'でる順準1級 - シート1.csv' by ID range.
    """
    csv_file = os.path.join("data", "でる順準1級 - シート1.csv")
    try:
        all_words = load_csv_data(csv_file, "でる順準1級")
        # Filter by range
        filtered = [w for w in all_words if start_id <= w["id"] <= end_id]
        print(f"  - Loaded {len(filtered)} DeruJun words (IDs {start_id}-{end_id}).")
        return filtered
    except Exception as e:
        print(f"  ! Error loading DeruJun CSV: {e}")
        # Propagate error for main.py to display
        raise RuntimeError(f"DeruJun Load Error: {e}")

def load_osaka_hybrid_vocab(total_count: int = 15) -> list:
    """
    Load a mix of Teppeki and Target 1900 words for OsakaU mode.
    Randomly selects approx total_count words from the ENTIRE books.
    """
    print("  - Loading Hybrid Vocabulary for OsakaU (Global Random)...")
    try:
        # 1. Load ALL words from Teppeki (IDs 1-3000 cover everything)
        teppeki_all = load_teppeki_words(1, 3000)
        
        # 2. Load ALL words from Target 1900 (IDs 1-1900)
        target_all = load_target1900_words(1, 1900)
        
        if not teppeki_all and not target_all:
            print("  ! Error: No words loaded from either source.")
            return []
            
        # 3. Sample and Mix (50/50 split)
        half_count = total_count // 2
        
        selected_teppeki = []
        if teppeki_all:
            selected_teppeki = random.sample(teppeki_all, min(len(teppeki_all), half_count))
            
        selected_target = []
        if target_all:
            # If one source failed, take more from the other
            remaining_count = total_count - len(selected_teppeki)
            selected_target = random.sample(target_all, min(len(target_all), remaining_count))
            
        # If still need more (e.g. Target failed or was small), fill with Teppeki
        current_selection = selected_teppeki + selected_target
        if len(current_selection) < total_count and teppeki_all:
            needed = total_count - len(current_selection)
            # Filter out already selected
            # Note: Checking dict equality might be slow or tricky, using IDs is better
            selected_ids = {w["id"] for w in current_selection if w.get("source") == "鉄壁"}
            remaining_teppeki = [w for w in teppeki_all if w["id"] not in selected_ids]
            
            if remaining_teppeki:
                more_teppeki = random.sample(remaining_teppeki, min(len(remaining_teppeki), needed))
                selected_teppeki.extend(more_teppeki)
        
        hybrid_list = selected_teppeki + selected_target
        random.shuffle(hybrid_list)
        
        # Add empty fields for consistency
        for v in hybrid_list:
            v["definition"] = ""
            v["example"] = ""
            
        print(f"  - Hybrid Load Complete: {len(hybrid_list)} words ({len(selected_teppeki)} Teppeki, {len(selected_target)} Target).")
        return hybrid_list
        
    except Exception as e:
        print(f"  ! Error in load_osaka_hybrid_vocab: {e}")
        import traceback
        traceback.print_exc()
        return []


def generate_listening_story(words: list) -> dict:
    """
    Generate a short story using all the provided words for listening practice.
    Returns a dict with 'en' and 'jp' keys.
    """
    print("  - Generating listening story...", flush=True)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not OpenAI:
        print("  ! OpenAI API key missing or library not loaded. Using dummy story.")
        return {
            "en": "This is a dummy story because OpenAI API is not available. " + " ".join([w['word'] for w in words]),
            "jp": "これはOpenAI APIが利用できないためのダミーストーリーです。"
        }

    client = OpenAI(api_key=api_key)
    word_list_str = ", ".join([f"{w['word']} ({w['meaning']})" for w in words])
    
    prompt = f"""
    Create a short, coherent story (approx. 100-150 words) that naturally includes ALL of the following English words:
    {word_list_str}
    
    Requirements:
    1. The story should be interesting and easy to follow (CEFR B1/B2 level).
    2. Highlight the usage of the provided words.
    3. Provide a natural Japanese translation.
    
    Output format (JSON):
    {{
        "story_en": "English story text...",
        "story_jp": "Japanese translation..."
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert English teacher creating learning materials."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return {
            "en": result.get("story_en", ""),
            "jp": result.get("story_jp", "")
        }
    except Exception as e:
        print(f"  ! Error generating listening story: {e}")
        return {
            "en": "Story generation failed. " + " ".join([w['word'] for w in words]),
            "jp": "ストーリー生成に失敗しました。"
        }

def generate_vocalab_script(words: list, target_range: str = None) -> dict:
    """
    Generate a script structure for Vocalab Mode.
    """
    print("  - Generating Vocalab Mode script...")
    
    words_with_examples = []
    
    # 0. Handle Target Range (Target 1900)
    if target_range:
        csv_file = os.path.join("data", "ターゲット1900 - Sheet1.csv")
        
        if os.path.exists(csv_file):
            print(f"  - Loading from {csv_file} with range {target_range}")
            try:
                # Parse range
                start_str, end_str = target_range.split('-')
                start_idx = int(start_str)
                end_idx = int(end_str)
                
                loaded_words = []
                encodings = ["utf-8-sig", "cp932", "utf-8"]
                all_rows = []
                for enc in encodings:
                    try:
                        with open(csv_file, "r", encoding=enc) as f:
                            reader = csv.reader(f)
                            all_rows = list(reader)
                        if all_rows:
                            print(f"    > Successfully read CSV with {enc} (Rows: {len(all_rows)})")
                            break
                    except:
                        continue
                
                # Assuming format: ID, Word, Meaning (No header or handle header)
                for row in all_rows:
                    if len(row) < 2: continue
                    
                    # Try first column as ID
                    try:
                        row_id_str = row[0].strip().replace('"', '')
                        # Check if header
                        if not row_id_str.isdigit() and row[1] == "create":
                             # Special case for first line if ID is missing but it's word 1
                             r_id = 1
                        elif row_id_str.isdigit():
                            r_id = int(row_id_str)
                        else:
                            continue

                        if start_idx <= r_id <= end_idx:
                            loaded_words.append({
                                "id": r_id,
                                "word": row[1].strip(),
                                "meaning": row[2].strip() if len(row) > 2 else ""
                            })
                    except ValueError:
                        continue
                            
                if loaded_words:
                    print(f"  - Loaded {len(loaded_words)} words from CSV within range {start_idx}-{end_idx}.")
                    # Sort by ID just in case
                    loaded_words.sort(key=lambda x: x["id"])
                    words = loaded_words
                else:
                    print(f"  ! No words found in range {start_idx}-{end_idx} in {csv_file}.")
            except Exception as e:
                print(f"  ! Error loading CSV: {e}")
        else:
            print(f"  - {csv_file} not found. Generating from GPT for range {target_range}")
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key and OpenAI:
                client = OpenAI(api_key=api_key)
                prompt = f"""
                ターゲット1900の単語番号{target_range}から単語を抽出して、英単語・意味・例文・例文訳を生成して。
                単語数は範囲内の全ての単語（または最大10単語程度）としてください。
                
                出力フォーマット(JSON):
                {{
                    "words": [
                        {{"word": "英単語", "meaning": "意味", "example_en": "例文", "example_jp": "例文訳"}},
                        ...
                    ]
                }}
                """
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant for English learning."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                    result = json.loads(response.choices[0].message.content)
                    gpt_words = result.get("words", [])
                    
                    # Transform to expected format
                    for w in gpt_words:
                        words_with_examples.append({
                            "word": w["word"],
                            "meaning": w["meaning"],
                            "examples": [{"en": w["example_en"], "jp": w["example_jp"]}]
                        })
                    print(f"  - Generated {len(words_with_examples)} words via GPT.")
                except Exception as e:
                    print(f"  ! Error generating from GPT: {e}")
            else:
                print("  ! OpenAI API key missing. Cannot generate from GPT.")

    # If we haven't generated words_with_examples yet (e.g. from CSV or input list)
    if not words_with_examples:
        # Normalize input (handle list of strings)
        normalized_words = []
        for i, w in enumerate(words):
            if isinstance(w, str):
                # Use a hash or simple index for ID to ensure it's an integer for example_gen compatibility
                dummy_id = 90000 + i 
                normalized_words.append({"id": dummy_id, "word": w, "meaning": "Meaning placeholder"})
            else:
                normalized_words.append(w)
        words = normalized_words
        
        # 1. Ensure examples are generated
        if generate_examples:
            # Use existing cache/generation logic
            words_with_examples = generate_examples(words)
        else:
            print("  ! generate_examples not available. Using raw words.")
            words_with_examples = words

    # 2. Generate Listening Story
    story = generate_listening_story(words_with_examples)
    
    # 3. Construct Script Data
    script_data = {
        "mode": "vocalab",
        "word_cycles": [],
        "story_section": {
            "type": "story",
            "content_en": story["en"],
            "content_jp": story["jp"]
        }
    }
    
    for w in words_with_examples:
        # Pick the first example if available, otherwise dummy
        ex_en = ""
        ex_jp = ""
        if w.get("examples") and len(w["examples"]) > 0:
            ex_en = w["examples"][0]["en"]
            ex_jp = w["examples"][0]["jp"]
        else:
            ex_en = f"This is an example for {w['word']}."
            ex_jp = f"これは{w['word']}の例文です。"

        script_data["word_cycles"].append({
            "word": w["word"],
            "meaning": w["meaning"],
            "example_en": ex_en,
            "example_jp": ex_jp
        })
    
    return script_data

def generate_exam_script(topic: str, vocab_list: list, university: str = "todai", custom_title: str = None) -> dict:
    """
    Generate a script for University Entrance Exam Listening (Todai/Kyoto/Osaka).
    """
    print(f"  - Generating Exam Listening Script for {university.upper()}...")
    
    # 0. Get Episode Number & Prepare Title
    next_no = history_manager.get_next_episode_number(university)
    uni_label_map = {"todai": "東大", "kyoto": "京大", "osaka": "阪大"}
    uni_label = uni_label_map.get(university, university.capitalize())
    
    # If topic is not yet determined (generic), we will update title later, 
    # but we can set a base format now.
    
    # 1. Get Past Topics
    past_topics = history_manager.get_past_topics(university)
    past_topics_str = ""
    if past_topics:
        recent_topics = past_topics[-20:]
        past_topics_str = f"Avoid these past topics: {', '.join(recent_topics)}"

    # 1. Topic Refinement
    if university == "kyoto":
        categories = [
            "Philosophy of Language",
            "Epistemology & Truth",
            "Theoretical Physics & Cosmology",
            "Cognitive Linguistics",
            "History of Scientific Thought",
            "Ethics of Technology",
            "Cultural Anthropology"
        ]
    elif university == "osaka":
        categories = [
            "AI Ethics & Future Society",
            "Medical Technology Advances",
            "Environmental Conservation & Sustainability",
            "Smart Cities & Urban Planning",
            "Global Health Challenges",
            "Robotics in Daily Life",
            "Digital Privacy & Security"
        ]
    else: # Todai
        categories = [
            "History & Civilization", 
            "Science & Technology", 
            "Society & Ethics", 
            "Psychology & Human Behavior", 
            "Economics & Globalization", 
            "Art & Culture", 
            "Philosophy & Thought",
            "Environment & Sustainability"
        ]
    
    selected_category = random.choice(categories)
    print(f"  - Selected Category: {selected_category}")
    
    # Format vocab list for prompt
    vocab_text = "\n".join([f"- {v['word']} ({v['meaning']})" for v in vocab_list])
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    client = OpenAI(api_key=api_key)

    # Load Reference Corpus for prompt injection
    ref_script, ref_features = load_reference_corpus(university)
    corpus_injection = ""
    if ref_script:
        corpus_injection = f"""
        Reference Example (Golden Standard)
        ---
        {ref_script}
        ---
        """
    if ref_features:
        corpus_injection += f"""
        Specific Instructions for this University
        {ref_features}
        """

    # If topic is generic, generate a specific one
    if "Word Audio Mode" in topic or not topic:
        topic_prompt = f"""
        Based on the category '{selected_category}' and the following vocabulary: {vocab_text}
        Propose a specific, academic topic suitable for a University of {university.capitalize()} listening exam.
        {past_topics_str}
        Output just the topic title.
        """
        try:
            res = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": topic_prompt}]
            )
            topic = res.choices[0].message.content.strip()
            print(f"  - Generated Specific Topic: {topic}")
        except:
            topic = f"{selected_category} Lecture" if university == "kyoto" else f"{selected_category} Discussion"

    # 2. Generate Script
    if university == "kyoto":
        # KYOTO PROMPT (Lecture, Single Speaker)
        system_prompt = f"""
        You are an expert test creator for the Kyoto University (KyotoU) English Listening Exam.
        {corpus_injection}
        
        Task: Create a high-difficulty academic lecture script (monologue) and questions.
        Topic: {topic}
        {past_topics_str}
        Target Vocabulary (Teppeki): {vocab_text}
        
        Speaker:
        - Dr. Smith (Male, elderly, authoritative but engaging, "Grandfatherly Professor" tone).
        
        **CRITICAL INSTRUCTION: Style & Content**
        1. **Abstract & Deep**:
        # ... (rest of Kyoto prompt)
        """
        # Note: I need to preserve the Kyoto prompt content while inserting Osaka prompt
        # So I will construct the string carefully or use separate blocks.
        # It's better to split this large if/else block into clearer sections.
        
        # Re-constructing the Kyoto prompt to be safe as I am replacing the block start
        system_prompt = f"""
        You are an expert test creator for the Kyoto University (KyotoU) English Listening Exam.
        {corpus_injection}
        
        Task: Create a high-difficulty academic lecture script (monologue) and questions.
        Topic: {topic}
        {past_topics_str}
        Target Vocabulary (Teppeki): {vocab_text}
        
        Speaker:
        - Dr. Smith (Male, elderly, authoritative but engaging, "Grandfatherly Professor" tone).
        
        **CRITICAL INSTRUCTION: Style & Content**
        1. **Abstract & Deep**:
           - Focus on abstract concepts (Truth, Meaning, Time, Consciousness).
           - The logic should be dense and require deep thinking to follow.
           - Avoid superficial examples; use historical or philosophical analogies.
        
        2. **Lecture Structure**:
           - Introduction: Raises a fundamental question or paradox.
           - Body: Explores 2-3 perspectives or historical shifts in thought.
           - Synthesis/Conclusion: Offers a profound insight or leaves the question open-ended.
           - Use lecture markers: "Now, let us consider...", "This brings us to the crux of the matter...", "Conversely...".
        
        3. **Teppeki Vocabulary Usage**:
           - Use the target vocabulary naturally within the academic discourse.
           - They should carry significant weight in the sentence.
        
        4. **Length**:
           - Approx 550-600 words. (Slightly shorter than Todai, but denser).
           
        5. **Questions**: 3 Questions.
           - Q1: Specific Detail (What did the professor say about X?).
           - Q2: Logical Inference (Why does the professor mention Y?).
           - Q3: Main Idea/Theme.
           - **Rule**: The CORRECT ANSWER for at least 2 questions MUST paraphrase a Target Vocabulary word.
           
        6. **Translation**: Provide a natural Japanese translation (Lecture style: "〜である", "〜であろう").
        
        Output JSON:
        {{
            "topic": "{topic}",
            "dialog": [
                {{"speaker": "Dr. Smith", "text": "...", "translation": "..."}},
                {{"speaker": "Dr. Smith", "text": "...", "translation": "..."}} 
                // Split long monologue into 3-4 chunks for better audio generation
            ],
            "questions": [
                {{
                    "question": "Question text...",
                    "choices": ["A) ...", "B) ...", "C) ...", "D) ..."],
                    "correct_answer": "A",
                    "explanation": "...",
                    "explanation_jp": "..."
                }}
            ],
            "vocab_paraphrases": [
                {{"word": "vital", "paraphrase": "crucial", "usage_in_question": "Q1"}}
            ]
        }}
        """
    elif university == "osaka":
        # OSAKA PROMPT (Presentation/Report, Single Speaker)
        system_prompt = f"""
        You are an expert test creator for the Osaka University (OsakaU) English Listening Exam.
        {corpus_injection}
        
        Task: Create a practical academic presentation script (monologue) and questions.
        Topic: {topic}
        {past_topics_str}
        Target Vocabulary (Teppeki): {vocab_text}
        
        Speaker:
        - Student B (Sarah): Female, clear, articulate, enthusiastic, slightly faster pace (+5%).
        
        **CRITICAL INSTRUCTION: Style & Content**
        1. **Practical & Modern**:
           - Focus on concrete, modern issues (AI, Environment, Medical Tech).
           - Style is "Presentation" or "Research Report".
           - Clear structure: Introduction -> Methodology/Current Status -> Challenges -> Future Outlook.
        
        2. **Presentation Structure**:
           - "Good morning everyone. Today I'd like to present on..."
           - "First, let's look at the data..."
           - "However, a major challenge remains..."
           - "In conclusion..."
        
        3. **Teppeki Vocabulary Usage**:
           - Use words in a practical context.
        
        4. **Length**:
           - Approx 500 words. (Concise, well-structured).
           
        5. **Questions**: 3 Questions.
           - Q1: Specific Fact/Data.
           - Q2: Cause and Effect / Problem and Solution.
           - Q3: Speaker's Opinion/Conclusion.
           
        6. **Translation**: Provide a natural Japanese translation (Presentation style: "〜です", "〜ます").
        
        Output JSON:
        {{
            "topic": "{topic}",
            "dialog": [
                {{"speaker": "Student B", "text": "...", "translation": "..."}},
                {{"speaker": "Student B", "text": "...", "translation": "..."}}
            ],
            "questions": [
                {{
                    "question": "Question text...",
                    "choices": ["A) ...", "B) ...", "C) ...", "D) ..."],
                    "correct_answer": "A",
                    "explanation": "...",
                    "explanation_jp": "..."
                }}
            ],
            "vocab_paraphrases": []
        }}
        """
    else:
        # TODAI PROMPT (Discussion, 3 Speakers)
        system_prompt = f"""
        You are an expert test creator for the University of Tokyo (UTokyo) English Listening Exam.
        {corpus_injection}
        
        Task: Create a highly academic discussion script and questions.
        Topic: {topic}
        {past_topics_str}
        Target Vocabulary (Teppeki): {vocab_text}
        
        Speakers:
        - Student A (Male, logical, critical, challenges details)
        - Student B (Female, enthusiastic but analytical, provides specific counter-examples)
        - Professor (Neutral, authoritative, synthesizes conflicting views)
        
        **CRITICAL INSTRUCTION: Complexity & Interaction**
        1. **Interactive Argument**:
           - Do NOT just exchange opinions. Speakers must **challenge specific details** of each other's arguments.
           - Use phrases like "I see your point, but...", "That assumes X, which isn't entirely true...", "I'd have to disagree with that specific figure...".
        
        2. **Professor's Role (Moderator & Synthesizer)**:
           - **MANDATORY**: When the Professor speaks, they MUST first **acknowledge or summarize** the students' points before stating their own view.
           - Use specific names: "Sarah, your point about X is valid...", "Alex, you're overlooking...".
           - Use moderator phrases: "As a moderator...", "Looking at this from a historical perspective...", "Let's pause and consider...".
           - **Structure**: Receive/Acknowledge -> Bridge -> State Authority/Opinion.
        
        3. **Logical Twists**:
           - Include moments where a speaker **modifies their stance** or **partially agrees while raising a new concern**.
           - Example: "Granted, X is true, but Y makes it irrelevant in this context."
           - Structure: Thesis -> Detailed Counter-argument -> Modified Thesis/Synthesis.
        
        4. **Teppeki Vocabulary Usage**:
           - Use the target vocabulary in **academic definitions** or **sharp, incisive points**.
           - Do NOT use them in simple, flat sentences. Make them integral to the logic.
           - Example usage: "The *significance* of this data is not in its volume, but its variability."
        
        Structure:
        1. **Discussion**: Approx 800-1000 words.
           - Dense, academic, fast-paced.
           - "Hard to understand on first hearing, but convincing when read."
           
        2. **Questions**: 3 Questions.
           - Q1: Specific Detail (Fact retrieval).
           - Q2: Inference (Logic/Intent).
           - Q3: Main Idea/Summary.
           
        CRITICAL RULE:
        - The CORRECT ANSWER for at least 2 questions MUST paraphrase a Target Vocabulary word.
        
        4. **Translation**: Provide a natural Japanese translation.
        
        Output JSON:
        {{
            "topic": "{topic}",
            "dialog": [
                {{"speaker": "Student A", "text": "...", "translation": "..."}},
                {{"speaker": "Student B", "text": "...", "translation": "..."}},
                {{"speaker": "Professor", "text": "...", "translation": "..."}}
            ],
            "questions": [
                {{
                    "question": "Question text...",
                    "choices": ["A) ...", "B) ...", "C) ...", "D) ..."],
                    "correct_answer": "A",
                    "explanation": "...",
                    "explanation_jp": "..."
                }}
            ],
            "vocab_paraphrases": [
                {{"word": "vital", "paraphrase": "crucial", "usage_in_question": "Q1"}}
            ]
        }}
        """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        
        # Inject metadata
        if vocab_list is None:
             vocab_list = []
        data["vocabulary"] = vocab_list
        data["university"] = university
        
        # Ensure title exists and is formatted correctly
        final_topic = data.get("topic", topic)
        if custom_title:
            formatted_title = custom_title
        else:
            formatted_title = f"【{uni_label}リスニング】第{next_no}回：{final_topic}"
        data["title"] = formatted_title
        data["topic"] = final_topic
            
        print(f"DEBUG: GPT Raw Keys: {list(data.keys())}")
        
        # --- CONVERT TO SECTIONS for Audio Generation ---
        sections = []
        
        # 1. Dialog Section
        # Try multiple keys
        dialog_raw = data.get("dialog", [])
        if not dialog_raw:
            dialog_raw = data.get("dialogue", [])
        if not dialog_raw:
            dialog_raw = data.get("conversation", [])
        if not dialog_raw:
            dialog_raw = data.get("script", [])
            
        dialog_lines = []
        for item in dialog_raw:
            dialog_lines.append({
                "speaker": item.get("speaker", "Student A"),
                "text": item.get("text", ""),
                "translation": item.get("translation", ""),
                "type": "dialogue"
            })
        
        if dialog_lines:
            # Split into individual sections to ensure 1-to-1 audio generation
            # This allows video_gen to display subtitles per line in Part 3
            for line in dialog_lines:
                sections.append({
                    "type": "listening_part",
                    "lines": [line]
                })
        else:
            print("DEBUG: No dialog lines extracted!")
            
        # 2. Questions Section
        questions_raw = data.get("questions", [])
        # We don't need to add questions to 'sections' for audio generation 
        # because generate_exam_video handles questions separately via 'questions' key in script_data.
        # BUT, if we want audio for questions to be pre-generated by audio_gen, we might need to.
        # However, video_gen calls generate_section_audio explicitly for questions.
        # So we just need to ensure 'questions' key is in the returned dict.
        
        # Final Result Construction
        final_result = {
            "title": data.get("title", topic),
            "topic": topic,
            "sections": sections, # For Audio Gen (Dialog)
            "questions": questions_raw, # For Video Gen (Questions)
            "vocabulary": vocab_list,
            "university": university
        }
        
        return final_result
        
    except Exception as e:
        print(f"  ! Error generating exam script: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_exam_description(script_data: dict, output_path: str, university: str = "todai"):
    """
    Generate YouTube Description file for Exam Listening Mode.
    Format:
    【大学受験リスニング対策（{University}）】{topic}

    ■ Questions
    Q1. {question_text}
    (A) {choice_A} ...
    正解: {correct_answer}
    解説: {explanation_jp}

    ■ Vocabulary
    ・{word}: {meaning}
      {definition}
    """
    
    uni_label_map = {
        "todai": "東大",
        "kyoto": "京大",
        "osaka": "阪大"
    }
    uni_label = uni_label_map.get(university, "大学受験")
    
    trend_info_map = {
        "todai": "東大リスニングは、長い対話や講義を聞き、内容を正確に把握する力が求められます。この動画では、実際の形式に近い3者対話を用いて、要約力と情報処理能力を鍛えます。",
        "kyoto": "京大リスニングは、文脈の深い理解と、選択肢の微細な違いを見抜く論理的思考力が問われます。学術的な内容を含む講義形式で、思考力を養います。",
        "osaka": "阪大リスニングは、標準的ですが正確な聴き取りと、要点を素早く掴む力が重要です。実用的なテーマや社会的なトピックを通じて、実践力を高めます。"
    }
    trend_info = trend_info_map.get(university, "")
    
    # Title from Script Data (should be formatted)
    title = script_data.get("title", "")
    topic = script_data.get("topic", "")
    
    lines = []
    if title:
        lines.append(f"{title} | 受験リスニング対策")
    else:
        lines.append(f"【{uni_label}英語】{topic} | 受験リスニング対策")
        
    lines.append("")
    lines.append(f"■ {uni_label}リスニング対策のポイント")
    lines.append(trend_info)
    lines.append("")
    
    # Questions
    lines.append("■ Questions")
    questions = script_data.get("questions", [])
    for i, q in enumerate(questions):
        lines.append(f"Q{i+1}. {q.get('question', '')}")
        choices = q.get("choices", [])
        for c in choices:
             lines.append(c)
        lines.append(f"正解: {q.get('correct_answer', '')}")
        lines.append(f"解説: {q.get('explanation_jp', '')}")
        lines.append("")

    # Vocabulary
    lines.append("■ Vocabulary")
    vocab = script_data.get("vocabulary", [])
    
    # Check if we have source info (OsakaU Hybrid)
    has_source_info = any(v.get("source_label") for v in vocab)
    
    if has_source_info and university == "osaka":
        lines.append("【本日の重要語彙（出典別）】")
        for v in vocab:
            source_label = v.get("source_label", "")
            # If source_label is missing but it's Osaka mode, try to infer or skip
            label_str = f" [{source_label}]" if source_label else ""
            lines.append(f"・{v.get('word', '')}{label_str}")
            # Also append meaning for clarity? The prompt requested:
            # ・[単語] [ターゲット1900 #番号]
            # It didn't explicitly ask for meaning in the attribution line, but usually vocab lists have meaning.
            # However, strict adherence to prompt: "・[単語] [ターゲット1900 #番号]"
            # But earlier code appended meaning. I will append meaning on the next line or same line if user didn't forbid.
            # User said: "概要欄に出力する語彙リストを以下の形式にアップデートしろ"
            # ・[単語] [ターゲット1900 #番号]
            # So I should follow this. But maybe meaning is still useful? 
            # Let's keep the existing format below it or replace it?
            # "概要欄に出力する語彙リストを以下の形式にアップデートしろ" implies REPLACEMENT of the vocab section format or ADDITION?
            # Usually "Vocabulary" section lists meanings. 
            # Let's write the requested format.
            # Wait, the requested format is:
            # 【本日の重要語彙（出典別）】
            # ・[単語] [ターゲット1900 #番号]
            
            # I will output the meaning as well because a vocab list without meaning is useless for study.
            # I'll add ": meaning" after.
            lines.append(f"  {v.get('meaning', '')}")
            if 'example_en' in v:
                 lines.append(f"  {v['example_en']}")
            lines.append("")
    else:
        # Standard format
        for v in vocab:
            lines.append(f"・{v.get('word', '')}: {v.get('meaning', '')}")
            if 'example_en' in v:
                 lines.append(f"  {v['example_en']}")
            lines.append("")

    # Script
    lines.append("■ Script")
    sections = script_data.get("sections", [])
    for sec in sections:
        if sec.get("type") == "listening_part":
             for line in sec.get("lines", []):
                 speaker = line.get("speaker", "")
                 text = line.get("text", "")
                 trans = line.get("translation", "")
                 lines.append(f"{text}")
                 lines.append(f"{trans}")
                 lines.append("")
    
    # Hashtags
    lines.append("")
    lines.append("#東大リスニング #大学受験 #英語リスニング #英単語帳鉄壁 #難関大対策 #AI英語学習 #リスニング対策")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Todai description saved to: {output_path}")

def generate_clean_script(script_data: dict, output_path: str):
    """
    Generate a clean English script file for study purposes (dictation/shadowing).
    Format: English text only, no speaker names, no translations.
    """
    lines = []
    
    # Header
    lines.append(f"Topic: {script_data.get('topic', '')}")
    lines.append("")
    
    # 1. Dialogue
    sections = script_data.get("sections", [])
    for sec in sections:
        if sec.get("type") == "listening_part":
             for line in sec.get("lines", []):
                 # Just the English text
                 text = line.get("text", "")
                 speaker = line.get("speaker", "Unknown")
                 if text:
                     lines.append(f"{speaker}: {text}")
                     lines.append("") # Blank line for readability
    
    # 2. Questions (Optional? User said "script only", usually implies the dialogue. 
    # But questions are also English. Let's include them clearly separated.)
    lines.append("--- Questions ---")
    questions = script_data.get("questions", [])
    for i, q in enumerate(questions):
        lines.append(f"Q{i+1}. {q.get('question', '')}")
        choices = q.get("choices", [])
        for c in choices:
             lines.append(c)
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Clean script saved to: {output_path}")

def generate_word_audio_script(book: str, target_range: str, use_shuffle: bool = False) -> dict:
    """
    Generate script structure for Word Audio Mode.
    Handles dynamic book selection (t1200, t1400, t1900, teppeki, systan, derujun).
    """
    print(f"  - Generating Word Audio Mode script (Book: {book}, Range: {target_range}, Shuffle: {use_shuffle})...")
    
    csv_map = {
        "t1200": os.path.join("data", "ターゲット1200.csv"),
        "t1400": os.path.join("data", "ターゲット1400.csv"),
        "t1900": os.path.join("data", "ターゲット1900 - Sheet1.csv"),
        "teppeki": os.path.join("data", "英単語帳鉄壁.csv"),
        "systan": os.path.join("data", "システム英単語 - シート1.csv"),
        "derujun": os.path.join("data", "でる順準1級 - シート1.csv"),
        "leap": "LEAP.csv"
    }
    
    csv_file = csv_map.get(book)
    if not csv_file:
        print(f"  ! Error: Unknown book '{book}'. Supported: t1200, t1400, t1900, teppeki, systan, derujun, leap")
        return None
        
    # Check file existence
    if not os.path.exists(csv_file):
        print(f"  ! Error: CSV file '{csv_file}' not found.")
        return None

    words = []
    try:
        # Parse range
        start_str, end_str = target_range.split('-')
        start_idx = int(start_str)
        end_idx = int(end_str)
        
        # Use robust loader
        book_label_map = {
            "t1200": "ターゲット1200",
            "t1400": "ターゲット1400",
            "t1900": "ターゲット1900",
            "teppeki": "鉄壁",
            "systan": "システム英単語",
            "derujun": "でる順準1級",
            "leap": "LEAP"
        }
        source_label = book_label_map.get(book, book)
        
        print(f"  - Loading CSV data from {csv_file}...")
        all_words = load_csv_data(csv_file, source_label)
        
        # Filter by range
        words = [w for w in all_words if start_idx <= w["id"] <= end_idx]
        
        if not words:
            print(f"  ! No words found in range {target_range} (IDs {start_idx}-{end_idx})")
            return None
            
        print(f"  - Loaded {len(words)} words within range.")
        
        if use_shuffle:
            print("  - Shuffling words (Shuffle Mode: ON)")
            random.shuffle(words)
        else:
            # Sort by ID
            words.sort(key=lambda x: x["id"])
        
    except ValueError as ve:
        print(f"  ! Error parsing range or data: {ve}")
        return None
    except Exception as e:
        print(f"  ! Error generating word audio script: {e}")
        import traceback
        traceback.print_exc()
        return None

    return {"words": words, "book": book, "range": target_range, "topic": f"Word Audio Mode ({book})"}

def generate_script(topic: str, level: str = "TOEIC600", day_number: int = 1, mode: str = "standard", university: str = None, custom_title: str = None) -> dict:
    """
    Fluent Path English style script generation.
    Structure: Intro -> Dialog 1 -> Takeaway -> Dialog 2 -> Outro
    
    If mode is 'university_listening' (e.g. Todai):
    Structure: Intro -> Vocab Preview -> Main Discussion (1st) -> Focus Phrases -> Main Discussion (2nd) -> Outro
    """
    # DEBUG LOGGING TO FILE
    with open("debug_script_gen.txt", "w", encoding="utf-8") as f:
        f.write(f"generate_script called with:\n")
        f.write(f"  topic={topic}\n")
        f.write(f"  level={level}\n")
        f.write(f"  mode={mode}\n")
        f.write(f"  university={university}\n")
        f.write(f"  custom_title={custom_title}\n")

    print(f"Generating script for topic '{topic}', level '{level}', mode '{mode}', university '{university}'...")
    
    # 1. Load Vocabulary
    vocab_list = load_vocabulary(level, day_number=day_number)
    selected_vocab = []
    if vocab_list:
        if level == "ターゲット1900" or level == "英単語帳鉄壁":
            # Use 5-10 words
            selected_vocab = vocab_list[:10] 
        else:
            selected_vocab = random.sample(vocab_list, min(len(vocab_list), 5))
            
    if not selected_vocab:
        print("  ! Error: No vocabulary found.")
        return None

    # 2. Enrich Vocabulary (Use Cache via example_gen)
    if generate_examples:
        print("  - Fetching definitions and examples (cached)...")
        # Ensure 'id' is present and integer for example_gen
        for v in selected_vocab:
            if "id" in v and isinstance(v["id"], str) and v["id"].isdigit():
                v["id"] = int(v["id"])
            elif "id" not in v:
                v["id"] = 0 # Dummy
        
        selected_vocab = generate_examples(selected_vocab, difficulty=level)
    else:
        print("  ! Warning: example_gen not found. Skipping detailed examples.")

    vocab_text = ", ".join([f"{item['word']} ({item['meaning']})" for item in selected_vocab])
    print(f"  - Selected Vocabulary: {vocab_text}")

    # 3. Generate Dialog and Scripts
    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key) if (OpenAI and api_key) else None
    
    if not client:
        print("  ! Error: OpenAI client not available.")
        return None

    # --- Mode Branching ---
    if mode == "university_listening":
        # === Exam Listening Mode Logic (Todai / Kyoto) ===
        # Default to todai if not specified
        if not university: university = "todai"
        return generate_exam_script(topic, selected_vocab, university=university, custom_title=custom_title)

    # --- Standard / Podcast Mode ---
    system_prompt = f"""
    You are an expert podcast scriptwriter.
    Topic: {topic}
    Level: {level}
    
    Structure:
    1. Intro (Brief, catchy)
    2. Dialog 1 (Natural conversation)
    3. Takeaway (Explain 2-3 key vocabulary words from the dialog)
    4. Dialog 2 (Repeat Dialog 1 but slightly different or more advanced)
    5. Outro (Summary)
    
    Vocabulary to include: {vocab_text}
    
    Output JSON:
    {{
        "title": "Podcast Title",
        "sections": [
            {{"type": "intro", "speaker": "Host", "text": "...", "jp": "..."}},
            {{"type": "dialog", "speaker": "A", "text": "...", "jp": "... "}},
            ...
        ]
    }}
    """

    # === Standard / Sleep Mode Logic (Existing) ===
    if mode == "sleep":
        system_prompt = """
        You are a scriptwriter for a 'Before Sleep English Radio' (おやすみEnglishラジオ) hosted by Alex (Male) and Mia (Female).
        
        Tone and Style:
        - Extremely soothing, calm, and slow-paced.
        - Use soft, gentle language suitable for bedtime.
        - Avoid loud exclamations or high-energy greetings.
        - The conversation should be comforting and help the listener relax.
        
        Structure:
        1. **Intro**: Very soft greeting, introducing the relaxing theme. (e.g. "Good evening... welcome to your quiet time...")
        2. **Dialog**: A peaceful conversation using the target vocabulary. The content should be relaxing (nature, quiet daily life, stars, etc.).
        3. **Outro**: Gentle goodnight message.

        Output JSON format:
        {
          "intro": [ {"speaker": "Alex"|"Mia", "text": "...", "japanese": "..."} ],
          "dialog": [ {"speaker": "Alex"|"Mia", "text": "...", "japanese": "..."} ],
          "outro": [ {"speaker": "Alex"|"Mia", "text": "...", "japanese": "..."} ]
        }
        """
    else:
        system_prompt = """
        You are a scriptwriter for an English learning podcast hosted by Alex (Male) and Mia (Female).
        
        Structure:
        1. **Intro**: Energetic greeting, introducing the topic.
        2. **Dialog**: A natural conversation using the target vocabulary.
        3. **Outro**: Summary and call to action (subscribe).

        Output JSON format:
        {
          "intro": [ {"speaker": "Alex"|"Mia", "text": "...", "japanese": "..."} ],
          "dialog": [ {"speaker": "Alex"|"Mia", "text": "...", "japanese": "..."} ],
          "outro": [ {"speaker": "Alex"|"Mia", "text": "...", "japanese": "..."} ]
        }
        """
    
    if mode == "sleep":
        user_prompt = f"""
        Topic: {topic}
        Vocabulary to include in Dialog: {vocab_text}
        
        Create the sleep-inducing script.
        - Intro: Gentle, welcoming, and relaxing.
        - Dialog: Slow, peaceful conversation (approx 10-15 lines).
        - Outro: Wish the listener a good night sleep.
        """
    else:
        user_prompt = f"""
        Topic: {topic}
        Vocabulary to include in Dialog: {vocab_text}
        
        Create the script.
        - Intro: Short and catchy.
        - Dialog: Natural conversation (approx 10-15 lines). Use the vocabulary naturally.
        - Outro: Thank the listener, ask to subscribe.
        """

    print("  - Generating script content with GPT-4o...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        generated_data = json.loads(content)
    except Exception as e:
        print(f"  ! Error generating script: {e}")
        return None

    # 4. Construct Final Sections
    sections = []

    # Section 1: Intro
    sections.append({
        "type": "intro",
        "lines": generated_data.get("intro", [])
    })

    # Section 2: Dialog 1
    dialog_lines = generated_data.get("dialog", [])
    sections.append({
        "type": "dialog_1",
        "lines": dialog_lines
    })

    # Section 3: Takeaway (Explanation)
    # Cycle: Word -> Meaning (JP) -> Example 1 -> Example 2
    takeaway_lines = []
    
    # Intro to Takeaway
    takeaway_intro_text = "Let's review the vocabulary from the dialogue."
    if mode == "sleep":
        takeaway_intro_text = "Now, let's gently review the words..."

    takeaway_lines.append({
        "speaker": "Mia",
        "text": takeaway_intro_text,
        "japanese": "ダイアログに出てきた単語を復習しましょう。",
        "type": "narration"
    })

    for item in selected_vocab:
        word = item["word"]
        meaning = item["meaning"]
        definition = item.get("definition", "")
        examples = item.get("examples", [])
        
        # 1. Word Introduction
        takeaway_lines.append({
            "speaker": "Alex",
            "text": word,
            "japanese": meaning,
            "type": "word_intro",
            "display": { # For video generation
                "word": word,
                "meaning": meaning,
                "example": ""
            }
        })
        
        # 2. Definition (Optional, skipping for brevity based on "Word -> Meaning -> Examples" request)
        # User asked for "Word introduction -> JP Meaning explanation -> 2 Examples"
        # We can have the host read the meaning or definition.
        # Let's have the host read the definition then the JP meaning.
        takeaway_lines.append({
            "speaker": "Mia",
            "text": definition,
            "japanese": meaning,
            "type": "definition",
             "display": {
                "word": word,
                "meaning": meaning,
                "example": definition
            }
        })

        # 3. Examples
        for i, ex in enumerate(examples):
            ex_en = ex["en"]
            ex_jp = ex["jp"]
            
            line_type = "example_1" if i == 0 else "example_2"
            speed = 1.0
            if i == 1: # 2nd example
                speed = 0.8
            
            takeaway_lines.append({
                "speaker": "Alex", # Alternate? Or same? Let's use Alex for examples.
                "text": ex_en,
                "japanese": ex_jp,
                "type": line_type,
                "speed": speed,
                "display": {
                    "word": word,
                    "meaning": meaning,
                    "example": ex_en
                }
            })

    sections.append({
        "type": "takeaway",
        "lines": takeaway_lines
    })

    # Section 4: Dialog 2 (Repeat)
    sections.append({
        "type": "dialog_2",
        "lines": dialog_lines # Reuse exact lines
    })

    # Section 5: Outro
    sections.append({
        "type": "outro",
        "lines": generated_data.get("outro", [])
    })

    script_data = {
        "topic": topic,
        "level": level,
        "vocabulary": selected_vocab,
        "sections": sections
    }
    
    print("  - Script construction completed.")
    return script_data


if __name__ == "__main__":
    # テスト実行
    data = generate_script("Future of AI", "TOEIC800")
    if data:
        print(json.dumps(data, indent=2, ensure_ascii=False)[:500] + "...")
