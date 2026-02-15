print("Importing script_gen...")
try:
    import script_gen
    print("script_gen imported.")
except Exception as e:
    print(f"Error importing script_gen: {e}")

print("Importing audio_gen...")
try:
    import audio_gen
    print("audio_gen imported.")
except Exception as e:
    print(f"Error importing audio_gen: {e}")

print("Importing video_gen...")
try:
    import video_gen
    print("video_gen imported.")
except Exception as e:
    print(f"Error importing video_gen: {e}")
