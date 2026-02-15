
import os
import sys
import json
from dotenv import load_dotenv
load_dotenv()

from script_gen import generate_vocalab_script
from audio_gen import generate_vocalab_audio
from video_gen import generate_vocalab_video

def test_vocalab_flow():
    with open("run_test_output_py.txt", "w", encoding="utf-8") as log_file:
        def log(msg):
            print(msg, flush=True)
            log_file.write(str(msg) + "\n")
            log_file.flush()

        try:
            log("=== Testing Vocalab Mode Flow ===")
            
            # 1. Input Data
            # words = ["ephemeral", "serendipity"]
            target_range = "1-1" # Test with Target 1900 range (1 word)
            
            # 2. Script Generation
            log(f"\n[1] Generating Script (Range: {target_range})...")
            script_data = generate_vocalab_script([], target_range=target_range)
            log(f"Script Data Keys: {script_data.keys()}")
            if "word_cycles" in script_data:
                log(f"Generated {len(script_data['word_cycles'])} word cycles.")
                if len(script_data["word_cycles"]) > 0:
                    log(f"Sample Word: {script_data['word_cycles'][0]['word']}")
            
            # 3. Audio Generation
            log("\n[2] Generating Audio...")
            output_audio_dir = "test_vocalab_audio"
            audio_segments = generate_vocalab_audio(script_data, output_dir=output_audio_dir)
            log(f"Generated {len(audio_segments)} audio segments.")
            
            # Save segments for debugging
            with open("debug_audio_segments.json", "w") as f:
                json.dump(audio_segments, f, indent=2)
            log("Saved debug_audio_segments.json")
            
            # 4. Video Generation
            log("\n[3] Generating Video...")
            output_video_file = "test_vocalab_video.mp4"
            if os.path.exists(output_video_file):
                os.remove(output_video_file)
                
            final_video = generate_vocalab_video(audio_segments, topic=f"Target 1900 ({target_range})", output_file=output_video_file)
            
            # 5. Verification
            if final_video and os.path.exists(final_video):
                log(f"\nSUCCESS: Video generated at {final_video}")
                log(f"Size: {os.path.getsize(final_video) / 1024 / 1024:.2f} MB")
            else:
                log("\nFAILURE: Video generation failed.")
                
        except Exception as e:
            log(f"\nCRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc(file=log_file)

if __name__ == "__main__":
    test_vocalab_flow()
