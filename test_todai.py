import os
import sys
import traceback

def test_todai_generation():
    print("Test script started.")
    with open("test_result.txt", "w", encoding="utf-8") as f:
        f.write("STARTING TEST (Pre-import)\n")
    
    try:
        print("Importing main...")
        import main
        print("Main imported.")
        
        print(f"--- Starting Todai Video Generation Test (Simple) ---")
        
        # Mock parameters
        topic = "AI Ethics"
        level = "英単語帳鉄壁"
        mode = "university_listening"
        university = "todai"
        day_number = 1
        
        print("Calling main.run_podcast_generation...")
        video_path, desc_path = main.run_podcast_generation(
            topic=topic,
            level=level,
            mode=mode,
            university=university,
            day_number=day_number,
            generate_thumb=False
        )
        print(f"SUCCESS: Video generated at {video_path}")
        with open("test_result.txt", "a", encoding="utf-8") as f:
            f.write(f"SUCCESS: Video generated at {video_path}\n")
            f.write(f"Description at {desc_path}\n")
        
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        with open("test_result.txt", "a", encoding="utf-8") as f:
            f.write(f"ERROR: {e}\n")
            f.write(traceback.format_exc())

if __name__ == "__main__":
    test_todai_generation()
