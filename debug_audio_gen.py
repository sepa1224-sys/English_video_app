import os
import sys
import logging
from audio_gen import generate_vocalab_audio

# Setup logging to stdout
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

def test_audio():
    print("Starting audio test...", flush=True)
    
    script_data = {
        "mode": "vocalab",
        "word_cycles": [
            {
                "word": "create",
                "meaning": "作る",
                "example_en": "I create art.",
                "example_jp": "私は芸術を作ります。"
            }
        ],
        "story_section": None
    }
    
    output_dir = "debug_audio_output"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        print("Calling generate_vocalab_audio...", flush=True)
        results = generate_vocalab_audio(script_data, output_dir=output_dir)
        print(f"Success! Generated {len(results)} segments.", flush=True)
        for r in results:
            print(f" - {r['type']}: {r.get('path')}", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_audio()
