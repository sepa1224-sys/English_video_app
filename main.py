import os
import time
import json
import random
import datetime
import traceback
import pathlib
from pathlib import Path
from dotenv import load_dotenv
import history_manager

# Import custom modules
import script_gen
import audio_gen
import video_gen
import db_utils

# --- CONFIG ---
OUTPUT_BASE_DIR = Path("output")
DEV_MODE = False  # Set to True to limit audio/video generation for testing
# --------------

def run_word_audio_generation(
    book: str,
    target_range: str,
    mode: str = "normal",
    gap_eng_to_jap: float = 1.0,
    gap_between_jap: float = 1.0,
    gap_next_word: float = 2.0,
    use_countdown: bool = False,
    end_left_text: str = "",
    end_right_text: str = "",
    end_duration: int = 10,
    use_shuffle: bool = False
):
    """
    Generate Word Audio Mode video.
    Orchestrates script -> audio -> video generation.
    """
    print(f"--- run_word_audio_generation (Book: {book}, Range: {target_range}) ---")
    
    # 1. Generate Script
    print("Step 1: Generating Script...")
    try:
        script_data = script_gen.generate_word_audio_script(book, target_range, use_shuffle=use_shuffle)
        if not script_data:
            raise RuntimeError("script_gen.generate_word_audio_script returned None (Check CSV file or range).")
    except Exception as e:
        error_msg = f"[Step 1: Script/CSV Error] Failed to generate script. Cause: {str(e)}"
        print(f"  ! {error_msg}")
        raise RuntimeError(error_msg) from e
        
    # 2. Generate Audio
    print("Step 2: Generating Audio...")
    try:
        audio_results = audio_gen.generate_word_audio(
            script_data, 
            submode=mode,
            gap_eng_to_jap=gap_eng_to_jap,
            gap_between_jap=gap_between_jap,
            gap_next_word=gap_next_word
        )
        
        if not audio_results:
            raise RuntimeError("audio_gen.generate_word_audio returned empty results.")
    except Exception as e:
        error_msg = f"[Step 2: Audio Generation Error] Failed to generate audio. Cause: {str(e)}"
        print(f"  ! {error_msg}")
        raise RuntimeError(error_msg) from e
        
    # 3. Generate Video
    print("Step 3: Generating Video...")
    try:
        # Define output filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_range = target_range.replace(":", "-").replace(" ", "_")
        output_filename = f"word_audio_{book}_{safe_range}_{timestamp}.mp4"
        output_dir = os.path.join(OUTPUT_BASE_DIR, "word_audio")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        output_path = os.path.join(output_dir, output_filename)
        
        # Call video generation
        if hasattr(video_gen, "generate_word_audio_video"):
            video_gen.generate_word_audio_video(
                audio_results=audio_results,
                output_file=output_path,
                bg_style="black", 
                extras={
                    "use_countdown": use_countdown,
                    "end_left": end_left_text,
                    "end_right": end_right_text,
                    "end_duration": end_duration
                }
            )
        else:
            print("! Error: video_gen.generate_word_audio_video not found.")
            raise RuntimeError("video_gen.generate_word_audio_video implementation missing.")
            
        print(f"Word Audio Video generated: {output_path}")
        return output_path
    except Exception as e:
        error_msg = f"[Step 3: Video Generation Error] Failed to generate video. Cause: {str(e)}"
        print(f"  ! {error_msg}")
        raise RuntimeError(error_msg) from e

def run_podcast_generation(
    topic: str,
    level: str = "TOEIC600",
    day_number: int = 1,
    mode: str = "standard",
    university: str = None,
    generate_thumb: bool = True,
    custom_title: str = None
):
    """
    Generate a complete podcast video.
    Returns (video_path, description_path) or raises Exception.
    """
    try:
        # .envファイルから環境変数を読み込む
        load_dotenv()
        # DB初期化
        db_utils.init_db()
        
        def update_progress(msg, pct):
            print(f"[{pct}%] {msg}")

        update_progress("Step 1: Initializing...", 10)
        
        print(f"Topic: {topic}")
        print(f"Level: {level}")
        print(f"Mode: {mode}")
        if university:
            print(f"University: {university}")
        
        # 2. 原稿生成
        update_progress("Step 1: Generating Script (with Vocabulary)...", 10)
        script_data = script_gen.generate_script(
            topic, 
            level, 
            day_number=day_number, 
            mode=mode, 
            university=university, 
            custom_title=custom_title
        )
        
        if not script_data:
            print("  ! Error: script_gen.generate_script returned None.")
            raise RuntimeError("Failed to generate script data (None returned).")
        
        sections_count = len(script_data.get("sections", []))
        print(f"  - Script generated with {sections_count} sections.")
        
        if sections_count == 0:
            print("  ! Error: Script has no sections.")
            print(f"  - Script Data: {json.dumps(script_data, ensure_ascii=False, indent=2)[:500]}...") # Show partial data
            raise RuntimeError("Failed to generate script data (No sections).")
        
        # 3. 音声生成 (セクション別)
        update_progress("Step 2: Generating Audio Segments...", 40)
        
        # --- DEV_MODE: Limit Audio Generation Only ---
        audio_script_data = script_data.copy()
        if DEV_MODE:
            print("  ★ DEV_MODE: Limiting audio generation to first 4 sections (Intro + Vocab + Start of Dialog).")
            # Create a shallow copy of sections list to avoid modifying original script_data
            if "sections" in script_data:
                # Typically: Intro -> Dialog1 -> Takeaway (Vocab) -> Dialog2 -> Outro
                # We want Intro + Dialog1 (start) + maybe Takeaway?
                # User said: "Intro + first vocab explanation" which usually is Intro -> Dialog1 -> Takeaway
                # Let's keep first 4 sections to be safe.
                audio_script_data["sections"] = script_data["sections"][:4]
        # ---------------------------------------------
        
        print(f"  - Calling audio_gen.generate_audio_sections with {len(audio_script_data.get('sections', []))} sections...")
        # Use temp/ directory for audio segments
        temp_audio_segments_dir = os.path.join("temp", "temp_audio_segments")
        audio_segments = audio_gen.generate_audio_sections(audio_script_data, output_dir=temp_audio_segments_dir)
        
        print(f"  - Audio segments generation completed. Count: {len(audio_segments) if audio_segments else 0}")
        
        if not audio_segments:
            print("  ! Error: audio_gen.generate_audio_sections returned empty list.")
            raise RuntimeError("Failed to generate audio segments.")
        
        # 4. 背景画像生成
        update_progress("Step 3: Generating Background...", 60)
        bg_image_path = "background.png"
        # 毎回生成せず、なければ生成、あるいはサムネイル設定に依存させることも可能だが、
        # ここでは動画背景として必須なのでチェック
        if not os.path.exists(bg_image_path):
            video_gen.generate_background_illustration(topic=topic, output_path=bg_image_path)
        if not os.path.exists(bg_image_path):
             # 最悪の場合は単色画像を生成などのフォールバックが必要だが、ここではエラーにする
             raise RuntimeError("Failed to prepare background image.")
        
        # 5. 動画生成 (セグメント結合 & スライド切り替え)
        update_progress("Step 4: Generating Video (Switching Backgrounds)...", 75)
        
        # 出力ディレクトリの確認と作成 (pathlib)
        print(f"DEBUG: Checking output directory: {OUTPUT_BASE_DIR}")
        OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
        save_dir = str(OUTPUT_BASE_DIR) # Alias for compatibility
        
        # ファイル名の生成 (日時ベース)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        if mode == "university_listening" and university:
            # Create dedicated exam directory
            exam_dir = OUTPUT_BASE_DIR / "exam" / university
            exam_dir.mkdir(parents=True, exist_ok=True)
            
            # e.g. Todai_Listening_Sec10_20260206.mp4
            base_filename = f"{university.title()}_Listening_{timestamp}"
            
            # Update paths to use exam_dir
            final_video_path = (exam_dir / f"{base_filename}.mp4").resolve()
            final_desc_path = (exam_dir / f"{base_filename}_description.txt").resolve()
            final_script_path = (exam_dir / f"{base_filename}_script_only.txt").resolve()
            final_csv_path = (exam_dir / f"{base_filename}_anki.csv").resolve()
        else:
            base_filename = f"podcast_{timestamp}"
            final_video_path = (OUTPUT_BASE_DIR / f"{base_filename}.mp4").resolve()
            final_desc_path = (OUTPUT_BASE_DIR / f"{base_filename}_description.txt").resolve()
            final_script_path = (OUTPUT_BASE_DIR / f"{base_filename}_script_only.txt").resolve()
            final_csv_path = (OUTPUT_BASE_DIR / f"{base_filename}_anki.csv").resolve()
        
        # 文字列に変換 (ライブラリ用)
        str_final_video_path = str(final_video_path)
        str_final_desc_path = str(final_desc_path)
        str_final_script_path = str(final_script_path)
        str_final_csv_path = str(final_csv_path)
        
        print(f"DEBUG: Target video path: {str_final_video_path}")
        
        # 動画生成関数の呼び出し
        if mode == "university_listening":
            # Call Exam video generator (Todai/Kyoto)
            topic = script_data.get("topic", "")
            questions = script_data.get("questions", [])
            vocab_list = script_data.get("vocabulary", [])
            
            # Use generate_exam_video (will rename/update generate_todai_video)
            if hasattr(video_gen, "generate_exam_video"):
                 _, timestamps_log = video_gen.generate_exam_video(
                    audio_segments=audio_segments,
                    questions=questions,
                    bg_image_path=bg_image_path,
                    output_file=str_final_video_path,
                    topic=topic,
                    vocab_list=vocab_list,
                    university=university,
                    special_clips={} 
                )
            elif hasattr(video_gen, "generate_todai_video"):
                 # Fallback if not renamed yet (but university param might be missing in old func)
                 print("WARNING: generate_exam_video not found, using generate_todai_video fallback.")
                 _, timestamps_log = video_gen.generate_todai_video(
                    audio_segments=audio_segments,
                    questions=questions,
                    bg_image_path=bg_image_path,
                    output_file=str_final_video_path,
                    topic=topic,
                    vocab_list=vocab_list,
                    special_clips={} 
                )
            else:
                 raise RuntimeError("No suitable video generation function found for exam mode.")
        else:
            # Standard video generator
            video_gen.generate_video_from_segments(
                audio_segments=audio_segments,
                bg_image_path=bg_image_path,
                script_data=script_data,
                output_file=str_final_video_path,
                dev_mode=DEV_MODE,
                mode=mode
            )
            timestamps_log = [] # Standard mode logic if needed
        
        if not os.path.exists(str_final_video_path):
            raise RuntimeError(f"Video file was not created at {str_final_video_path}")
            
        update_progress("Step 5: Finalizing...", 90)
        
        # 6. 概要欄生成
        description = f"""
Title: {script_data.get('title', topic)}
Topic: {topic}
Level: {level}
Date: {datetime.datetime.now().strftime('%Y-%m-%d')}
"""

        # Q&A (Exam Mode)
        if mode == "university_listening":
            # Use the dedicated description generator from script_gen
            from script_gen import generate_exam_description, generate_clean_script
            
            # The description generation is now handled inside generate_exam_description
            # We just need to pass the data and path
            generate_exam_description(script_data, str_final_desc_path, university=university)
            
            # Generate Clean Script
            generate_clean_script(script_data, str_final_script_path)
            
            # Save History
            history_manager.save_exam_history(
                university=university,
                title=script_data.get('title', topic),
                topic=script_data.get('topic', topic),
                youtube_status="Generated"
            )
            
        else:
            # Default Description Logic (Existing)
            # Timestamps
            if timestamps_log:
                description += "\nTimestamps:\n"
                for ts in timestamps_log:
                    if isinstance(ts, dict):
                        # Format seconds to MM:SS
                        m, s = divmod(int(ts['start']), 60)
                        description += f"{m:02d}:{s:02d} {ts['type']}\n"
                    elif isinstance(ts, str):
                        description += f"{ts}\n"

            # Vocabulary
            description += "\nVocabulary:\n"
            if "vocabulary" in script_data:
                 for v in script_data["vocabulary"]:
                     description += f"- {v.get('word', '')}: {v.get('meaning', '')}\n"

            # Save
            with open(str_final_desc_path, "w", encoding="utf-8") as f:
                f.write(description.strip())
            
        update_progress("Done!", 100)
        
        return str_final_video_path, str_final_desc_path, str_final_script_path

    except Exception as e:
        print(f"Error in run_podcast_generation: {e}")
        traceback.print_exc()
        raise e  # app.py でキャッチさせるために再スロー

if __name__ == "__main__":
    # Test run
    # run_podcast_generation("AI Ethics", level="TOEIC800", mode="standard")
    pass