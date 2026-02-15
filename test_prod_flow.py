import os
import sys
import shutil
from dotenv import load_dotenv

# Load env
load_dotenv()

# Set env for test
os.environ["TEST_MODE"] = "true"
os.environ["LAYOUT_CHECK_MODE"] = "false" # Force disable layout mode
os.environ["DEV_MODE"] = "true" # For video_gen 30s cut

# Import modules
try:
    import audio_gen
    import video_gen
except ImportError:
    # Add current dir to path if needed
    sys.path.append(os.getcwd())
    import audio_gen
    import video_gen

def run_test():
    print("=== Starting Production Flow Test ===")
    
    # 1. Create dummy script data
    script_data = {
        "title": "Test Episode",
        "sections": [
            {
                "type": "intro",
                "lines": [
                    {"speaker": "James", "text": "Hello everyone, welcome back to the channel.", "type": "dialogue"},
                    {"speaker": "Emily", "text": "Hi James! I am so excited for today's topic. It is going to be amazing.", "type": "dialogue"}
                ]
            },
            {
                "type": "dialog_1",
                "lines": [
                     {"speaker": "James", "text": "Let's dive right in.", "type": "dialogue"}
                ]
            }
        ]
    }
    
    # 2. Generate Audio
    print("\n--- Generating Audio (Test Mode / Edge-TTS) ---")
    audio_output_dir = "test_audio_output"
    if os.path.exists(audio_output_dir):
        shutil.rmtree(audio_output_dir)
    os.makedirs(audio_output_dir)
        
    segments = audio_gen.generate_audio_sections(script_data, output_dir=audio_output_dir)
    
    if not segments:
        print("! Audio generation failed.")
        return
        
    print(f"Generated {len(segments)} segments.")
    for s in segments:
        print(f"  - {s['type']}: {s['path']} ({s['duration']:.2f}s)")
    
    # 3. Generate Video
    print("\n--- Generating Video (Dev Mode) ---")
    # Pexels integration will be triggered if PEXELS_API_KEY is in env
    api_key = os.environ.get("PEXELS_API_KEY")
    if api_key:
        print(f"PEXELS_API_KEY found: {api_key[:5]}...")
    else:
        print("WARNING: PEXELS_API_KEY not found. Video background will be skipped.")
    
    # Dummy background image path (fallback)
    bg_image = "background.png"
    if not os.path.exists(bg_image):
        from PIL import Image
        Image.new('RGB', (1280, 720), color='blue').save(bg_image)
        
    output_video = "test_prod_output.mp4"
    
    # Generate
    try:
        final_path = video_gen.generate_video_from_segments(
            segments, 
            bg_image, 
            script_data, 
            output_file=output_video, 
            dev_mode=True
        )
        print(f"\nSUCCESS! Video generated at: {final_path}")
    except Exception as e:
        print(f"\nFAILURE! Video generation error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
