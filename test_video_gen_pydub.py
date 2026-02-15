import os
import sys
import shutil

# Ensure we can import video_gen
sys.path.append(os.getcwd())

from video_gen import generate_video_from_segments

def run_test():
    print("Starting pydub integration test...")
    
    # Check assets
    bgm_path = "めちゃくちゃ可愛いフューチャーベース.mp3"
    if not os.path.exists(bgm_path):
        print(f"Warning: {bgm_path} not found in root. Creating dummy.")
        with open(bgm_path, "wb") as f:
            f.write(b"dummy mp3 content") # This will fail pydub, need real mp3
            
    # We need real audio for pydub
    voice_path = "test_audio.mp3"
    if not os.path.exists(voice_path):
        # Try to find any mp3
        candidates = [
            "assets/backchannels/Male_Yeah.mp3",
            "assets/podcast_bgm.mp3"
        ]
        for c in candidates:
            if os.path.exists(c):
                shutil.copy(c, voice_path)
                break
    
    if not os.path.exists(voice_path):
        print("Error: No audio file found for test.")
        return

    segments = [
        {
            "path": voice_path,
            "duration": 2.0,
            "type": "intro",
            "line_timings": [{"text": "Testing Pydub", "start": 0, "end": 2.0}]
        }
    ]
    
    background_image = "background.png"
    if not os.path.exists(background_image):
        # Create dummy image
        from PIL import Image
        img = Image.new('RGB', (1280, 720), color = 'red')
        img.save(background_image)

    script_data = {"title": "Test Video"}
    output_file = "test_pydub_output.mp4"
    
    try:
        generate_video_from_segments(segments, background_image, script_data, output_file, dev_mode=True)
        print("Test finished successfully.")
        if os.path.exists(output_file):
            print(f"Output file created: {output_file}")
            # Clean up
            # os.remove(output_file)
        else:
            print("Output file NOT created.")
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
