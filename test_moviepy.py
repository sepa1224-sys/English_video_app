
try:
    from moviepy import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, TextClip, ColorClip, CompositeAudioClip, ImageSequenceClip, concatenate_audioclips
    print("Imported ALL from moviepy")
except ImportError as e:
    print(f"Failed to import from moviepy: {e}")

try:
    from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, TextClip, ColorClip, CompositeAudioClip, ImageSequenceClip, concatenate_audioclips
    print("Imported ALL from moviepy.editor")
except ImportError as e:
    print(f"Failed to import from moviepy.editor: {e}")
