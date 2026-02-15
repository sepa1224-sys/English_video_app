
try:
    import video_gen
    print("Import OK")
except Exception as e:
    print(f"Import Failed: {e}")
    import traceback
    traceback.print_exc()
