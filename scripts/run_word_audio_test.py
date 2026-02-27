import os
import sys
sys.path.insert(0, os.getcwd())
import video_gen

def main():
    print("[TEST] Word Audio Mode generation start")
    audio_results = [
        {
            "word_item": {"id": 1, "word": "listen", "meaning": "聞く", "source_label": "Test"},
            "path": "c:/Users/PC_User/Documents/trae_projects/englishPodcast/test_vocalab_audio/vocalab_word_5_listen.mp3",
        },
        {
            "word_item": {"id": 2, "word": "understand", "meaning": "理解する", "source_label": "Test"},
            "path": "c:/Users/PC_User/Documents/trae_projects/englishPodcast/test_vocalab_audio/vocalab_word_6_understand.mp3",
        },
        {
            "word_item": {"id": 3, "word": "develop", "meaning": "発展させる", "source_label": "Test"},
            "path": "c:/Users/PC_User/Documents/trae_projects/englishPodcast/test_vocalab_audio/vocalab_word_8_develop.mp3",
        },
    ]
    extras = {
        "use_countdown": True,
        "end_left": "Thank you",
        "end_right": "Subscribe",
        "end_duration": 5,
    }
    out_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "word_audio_test_run.mp4")
    print("[TEST] Word Audio Mode generation start")
    print(f"[TEST] Output path: {out_path}")
    video_gen.generate_word_audio_video(audio_results, out_path, extras=extras)
    print("[TEST] DONE:", out_path)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[TEST] ERROR: {e}")
        sys.exit(1)
