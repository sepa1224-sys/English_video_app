import os
import csv
import json
import time
from typing import List, Dict

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

CSV_FILE = os.path.join("data", "ターゲット1900 - Sheet1.csv")
CACHE_FILE = os.path.join("data", "target1900_examples_cache.json")

def load_words_from_csv(start_id: int, end_id: int) -> List[Dict]:
    """
    指定された範囲の単語をCSVから読み込む
    """
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found.")
        return []

    words = []
    encodings = ["utf-8-sig", "cp932", "utf-8"]
    
    # 全行読み込み
    all_rows = []
    for enc in encodings:
        try:
            with open(CSV_FILE, "r", encoding=enc) as f:
                reader = csv.reader(f)
                all_rows = list(reader)
            if all_rows:
                break
        except Exception:
            continue
            
    if not all_rows:
        return []

    # パースしてフィルタリング
    for i, r in enumerate(all_rows):
        if len(r) < 3:
            continue
            
        row_id_str = r[0].strip()
        # 1行目のID補正
        if i == 0 and not row_id_str and r[1].strip().lower() == "create":
            row_id_str = "1"
            
        if not row_id_str.isdigit():
            continue
            
        row_id = int(row_id_str)
        
        if start_id <= row_id <= end_id:
            words.append({
                "id": row_id,
                "word": r[1].strip(),
                "meaning": r[2].strip()
            })
            
    return words

def load_cache() -> Dict[str, Dict]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_cache(cache: Dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Cache save failed: {e}")

def generate_examples(words: List[Dict], difficulty: str = "middle") -> List[Dict]:
    """
    単語リストに対して定義と例文(2つ)を付与する。
    キャッシュ構造:
    {
        "id": {
            "word": "...",
            "definition": "...",
            "examples": [
                {"en": "...", "jp": "..."},
                {"en": "...", "jp": "..."}
            ],
            "difficulty": "..."
        }
    }
    """
    cache = load_cache()
    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key) if (OpenAI and api_key) else None
    
    updated = False
    results = []
    
    print(f"Processing {len(words)} words for examples (Difficulty: {difficulty})...")
    
    words_to_gen = []
    for w in words:
        wid = str(w["id"])
        # キャッシュチェック (新しい構造を持っているか確認)
        if wid in cache and cache[wid].get("difficulty") == difficulty and "examples" in cache[wid] and len(cache[wid]["examples"]) >= 2:
            # キャッシュあり
            c = cache[wid]
            w["definition"] = c.get("definition", "")
            w["examples"] = c["examples"]
            results.append(w)
        else:
            # 生成必要
            words_to_gen.append(w)
            
    batch_size = 3 # 例文2つ生成でトークン増えるので少なめに
    for i in range(0, len(words_to_gen), batch_size):
        batch = words_to_gen[i:i+batch_size]
        
        if not client:
            # ダミーデータ
            for w in batch:
                w["definition"] = f"Dummy definition for {w['word']}"
                w["examples"] = [
                    {"en": f"Example 1 for {w['word']}", "jp": f"{w['word']}の例文1"},
                    {"en": f"Example 2 for {w['word']}", "jp": f"{w['word']}の例文2"}
                ]
                results.append(w)
            continue
            
        # プロンプト作成
        prompt_text = ""
        for w in batch:
            prompt_text += f"- ID {w['id']}: {w['word']} (Meaning: {w['meaning']})\n"
            
        level_desc = "University entrance exam (Target 1900 level)"
        
        prompt = (
            "For each of the following words, provide:\n"
            "1. A simple English definition.\n"
            "2. TWO example sentences with Japanese translations.\n"
            f"Level: {level_desc}.\n"
            "Return the result as a JSON object with a key 'data' containing a list of objects.\n"
            "Each object must have:\n"
            "- 'id' (integer)\n"
            "- 'word' (string)\n"
            "- 'definition' (string)\n"
            "- 'examples' (list of objects with 'en' and 'jp' keys)\n\n"
            f"Words:\n{prompt_text}"
        )
        
        try:
            print(f"  Generating extended examples for batch {i//batch_size + 1}...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an English teacher. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            gen_list = data.get("data", [])
            
            # 結果をマッピング
            gen_map = {int(g["id"]): g for g in gen_list if "id" in g}
            
            for w in batch:
                if w["id"] in gen_map:
                    g = gen_map[w["id"]]
                    w["definition"] = g.get("definition", "")
                    w["examples"] = g.get("examples", [])
                    
                    # キャッシュ更新
                    cache[str(w["id"])] = {
                        "word": w["word"],
                        "definition": w["definition"],
                        "examples": w["examples"],
                        "difficulty": difficulty
                    }
                    updated = True
                else:
                    # 失敗時フォールバック
                    w["definition"] = "Definition not found."
                    w["examples"] = []
                
                results.append(w)
                
        except Exception as e:
            print(f"  ! Error generating batch: {e}")
            for w in batch:
                w["definition"] = "Error"
                w["examples"] = []
                results.append(w)
                
    if updated:
        save_cache(cache)
        
    results.sort(key=lambda x: x["id"])
    print(f"Finished generating examples. Count: {len(results)}", flush=True)
    return results

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # Test
    words = [{"id": 1, "word": "create", "meaning": "創造する"}]
    res = generate_examples(words)
    print(json.dumps(res, indent=2, ensure_ascii=False))
