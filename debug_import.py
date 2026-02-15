from moviepy import VideoFileClip
print(f"VideoFileClip attributes: {dir(VideoFileClip)}")

try:
    from moviepy import vfx
    print(f"vfx.Loop type: {type(vfx.Loop)}")
except: pass
