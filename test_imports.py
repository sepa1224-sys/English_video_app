
print("1. Importing os, sys, time, re, numpy, textwrap, traceback")
import os
import sys
import time
import re
import numpy as np
import textwrap
import traceback
print("2. Importing PIL")
from PIL import Image, ImageDraw, ImageFont
print("3. Importing MoviePy")
try:
    from moviepy import AudioFileClip, VideoFileClip, ImageClip, ColorClip, concatenate_videoclips, concatenate_audioclips, CompositeVideoClip
    print("   - MoviePy v2 imported")
except ImportError:
    try:
        from moviepy.editor import AudioFileClip, VideoFileClip, ImageClip, ColorClip, concatenate_videoclips, concatenate_audioclips, CompositeVideoClip
        print("   - MoviePy v1 imported")
    except Exception as e:
        print(f"   ! MoviePy import failed: {e}")

print("4. Importing audio_gen_listening")
try:
    import audio_gen_listening
    print("   - audio_gen_listening imported")
except Exception as e:
    print(f"   ! audio_gen_listening import failed: {e}")

print("5. Importing video_gen")
try:
    import video_gen
    print("   - video_gen imported successfully")
except Exception as e:
    print(f"   ! video_gen import failed: {e}")
    traceback.print_exc()
