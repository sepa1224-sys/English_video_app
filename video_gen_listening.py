import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict

try:
    from moviepy import ImageClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, ColorClip, TextClip, CompositeAudioClip
except ImportError:
    from moviepy.editor import ImageClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, ColorClip, TextClip, CompositeAudioClip

# Constants
VIDEO_SIZE = (1920, 1080)
BG_COLOR = (40, 44, 52) # Dark Slate / VSCode-ish
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (100, 200, 255) # Light Blue
ASSETS_DIR = "assets"

def get_bg_image_path():
    """Returns the path to the background image if it exists."""
    candidates = [
        os.path.join(ASSETS_DIR, "background.jpg"),
        os.path.join(ASSETS_DIR, "background.png"),
        os.path.join(ASSETS_DIR, "background.jpeg"),
        os.path.join(ASSETS_DIR, "background_wood.png"), # Legacy support if user followed exact instructions
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def get_intro_music_path():
    """Returns the path to the intro music if it exists."""
    p = os.path.join(ASSETS_DIR, "intro_music.mp3")
    if os.path.exists(p):
        return p
    # Fallback to pop search result if manually placed
    p2 = os.path.join(ASSETS_DIR, "intro_pop.mp3")
    if os.path.exists(p2):
        return p2
    return None

def get_font(size: int, font_path: str = None):
    # If explicit path provided and exists, use it
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass

    # Windows font paths
    candidates = [
        "C:\\Windows\\Fonts\\meiryo.ttc",
        "C:\\Windows\\Fonts\\msgothic.ttc",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    path = None
    for p in candidates:
        if os.path.exists(p):
            path = p
            break
            
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def wrap_text(text: str, font, max_width: int, draw: ImageDraw):
    """
    簡易的なテキスト折り返し処理
    """
    lines = []
    if not text:
        return lines
        
    # 文字単位で処理（日本語対応のため）
    # 厳密な禁則処理は省略
    current_line = ""
    for char in text:
        test_line = current_line + char
        # bbox: (left, top, right, bottom)
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        
        if w <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = char
    if current_line:
        lines.append(current_line)
    return lines

def create_slide_image(text: str, word_id: int, word: str, type_label: str, is_japanese: bool, font_path_en: str = None, font_path_jp: str = None) -> np.ndarray:
    """
    PILでスライド画像を生成し、NumPy配列(RGB)で返す
    """
    # Background Image or Color
    bg_path = get_bg_image_path()
    if bg_path:
        try:
            img = Image.open(bg_path).convert('RGB')
            # Resize/Crop to fit 1920x1080
            # Aspect Ratio fill
            img_ratio = img.width / img.height
            target_ratio = VIDEO_SIZE[0] / VIDEO_SIZE[1]
            
            if img_ratio > target_ratio:
                # Image is wider, crop width
                new_height = VIDEO_SIZE[1]
                new_width = int(new_height * img_ratio)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                left = (new_width - VIDEO_SIZE[0]) // 2
                img = img.crop((left, 0, left + VIDEO_SIZE[0], VIDEO_SIZE[1]))
            else:
                # Image is taller, crop height
                new_width = VIDEO_SIZE[0]
                new_height = int(new_width / img_ratio)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                top = (new_height - VIDEO_SIZE[1]) // 2
                img = img.crop((0, top, VIDEO_SIZE[0], top + VIDEO_SIZE[1]))
                
            # Darken overlay for readability
            overlay = Image.new('RGBA', VIDEO_SIZE, (0, 0, 0, 100)) # Semi-transparent black
            img.paste(overlay, (0, 0), overlay)
            
        except Exception as e:
            print(f"Error loading background image: {e}")
            img = Image.new('RGB', VIDEO_SIZE, color=BG_COLOR)
    else:
        img = Image.new('RGB', VIDEO_SIZE, color=BG_COLOR)

    draw = ImageDraw.Draw(img)
    
    # Fonts
    # is_japaneseフラグに応じてフォントを切り替える
    
    # メインテキスト用フォント
    current_font_path = font_path_jp if is_japanese else font_path_en
    font_main = get_font(80, current_font_path)
    
    # ラベル・コーナー用フォント（基本は英語フォント、なければデフォルト）
    font_sub = get_font(40, font_path_en)
    font_corner = get_font(50, font_path_en)
    
    # Corner Info (Top Left)
    corner_text = f"No. {word_id} [{word}]"
    draw.text((50, 50), corner_text, font=font_corner, fill=ACCENT_COLOR)
    
    # Type Label (Bottom Center or Top Center)
    # type_label: "Normal Speed", "Japanese", "Slow Speed (0.8x)"
    if type_label:
        bbox = draw.textbbox((0, 0), type_label, font=font_sub)
        w = bbox[2] - bbox[0]
        x = (VIDEO_SIZE[0] - w) // 2
        y = 150
        draw.text((x, y), type_label, font=font_sub, fill=(200, 200, 200))
    
    # Main Text (Center)
    max_w = VIDEO_SIZE[0] - 200
    lines = wrap_text(text, font_main, max_w, draw)
    
    # Calculate total height to center vertically
    line_height = 100 # approximate
    total_h = len(lines) * line_height
    start_y = (VIDEO_SIZE[1] - total_h) // 2
    
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        lw = bbox[2] - bbox[0]
        lx = (VIDEO_SIZE[0] - lw) // 2
        ly = start_y + (i * line_height)
        draw.text((lx, ly), line, font=font_main, fill=TEXT_COLOR)
        
    return np.array(img)

def create_intro_clip(intro_text: str, font_path: str = None) -> CompositeVideoClip:
    """
    イントロクリップを生成する
    """
    duration = 5.0 # default duration
    
    # Background
    bg_path = get_bg_image_path()
    if bg_path and os.path.exists(bg_path):
        # Resize logic duplicated roughly or rely on ImageClip resize
        # MoviePy's resize is easier
        bg_clip = ImageClip(bg_path)
        # Resize to cover
        bg_w, bg_h = bg_clip.size
        target_ratio = VIDEO_SIZE[0] / VIDEO_SIZE[1]
        current_ratio = bg_w / bg_h
        
        if current_ratio > target_ratio:
            bg_clip = bg_clip.resized(height=VIDEO_SIZE[1])
            bg_clip = bg_clip.cropped(x1=(bg_clip.w - VIDEO_SIZE[0])/2, width=VIDEO_SIZE[0])
        else:
            bg_clip = bg_clip.resized(width=VIDEO_SIZE[0])
            bg_clip = bg_clip.cropped(y1=(bg_clip.h - VIDEO_SIZE[1])/2, height=VIDEO_SIZE[1])
    else:
        bg_clip = ColorClip(size=VIDEO_SIZE, color=BG_COLOR)
    
    bg_clip = bg_clip.with_duration(duration)
    
    # Overlay - Darken
    dark_clip = ColorClip(size=VIDEO_SIZE, color=(0,0,0)).with_opacity(0.3).with_duration(duration)
    
    # Text
    if not intro_text:
        intro_text = "Listening Practice"
        
    font = font_path if font_path else "Arial"
    
    # Note: TextClip in MoviePy can be tricky with fonts. 
    # If font_path is absolute, it might work, or might fail depending on ImageMagick.
    # We will use PIL to create text image to be safe.
    
    img = Image.new('RGBA', VIDEO_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_obj = get_font(100, font_path)
    
    # Center text
    bbox = draw.textbbox((0, 0), intro_text, font=font_obj)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (VIDEO_SIZE[0] - text_w) // 2
    y = (VIDEO_SIZE[1] - text_h) // 2
    
    draw.text((x, y), intro_text, font=font_obj, fill=(255, 255, 255, 255))
    
    text_clip = ImageClip(np.array(img)).with_duration(duration)
    
    video = CompositeVideoClip([bg_clip, dark_clip, text_clip])
    
    # Audio
    music_path = get_intro_music_path()
    if music_path:
        try:
            audio = AudioFileClip(music_path)
            if audio.duration > duration:
                audio = audio.subclipped(0, duration)
                audio = audio.with_effects([lambda c: c.audio_fadeout(1.0)]) # Fadeout
            else:
                # Loop if shorter? Or just play once.
                pass
            video = video.with_audio(audio)
        except Exception as e:
            print(f"Error loading intro music: {e}")
            
    return video

def generate_listening_video(audio_data: Dict, output_file: str, font_path_en: str = None, font_path_jp: str = None, intro_text: str = None):
    """
    音声データ情報に基づいて動画を生成する
    audio_data: {
        "audio_path": str,
        "segments": [
            {"id": 1, "text": "...", "type": "en_normal", "start": 0.0, "end": 5.0},
            ...
        ]
    }
    """
    print(f"Generating listening video: {output_file}")
    
    segments = audio_data.get("segments", [])
    audio_path = audio_data.get("audio_path")
    
    clips = []
    
    # 各セグメントに対応するクリップを作成
    # 隙間（ポーズ）がある場合、前の画像を維持するか、黒にするか？
    # audio_gen側でポーズも含めてクリップ化しているので、
    # segmentsのendと次のstartの間にギャップがある場合、その間を埋める必要がある。
    # ここでは単純に segments の情報に基づいてクリップを作り、concatする。
    # ギャップは自動的に埋まらないので、前のクリップを延長するか、黒クリップを入れる。
    
    current_time = 0.0
    
    # 0. Intro Clip
    if intro_text:
        print("Generating intro clip...")
        intro_clip = create_intro_clip(intro_text, font_path_en)
        clips.append(intro_clip)
        current_time += intro_clip.duration
    
    for i, seg in enumerate(segments):
        start = seg["start"]
        end = seg["end"]
        duration = end - start
        
        # ギャップ埋め（前のスライドを延長、または黒）
        if start > current_time:
            gap = start - current_time
            # ひとつ前の画像で埋めるのが自然
            if clips:
                # 前のクリップのコピーを作り、durationを設定... 
                # moviepyでは既に追加済みのクリップを変更するのは面倒なので、
                # 黒（または直前の画像）のColorClipを入れる
                # ここでは「前のスライドの静止画」を再利用したいが、アクセスが面倒なので
                # 「準備中」的な画像か、単に黒背景にする。
                # しかしポーズ中も文字が出ていたほうが復習になるので、
                # 前のセグメントのテキストを維持するのがベスト。
                # 今回は実装を単純にするため、gapの間は「前の内容を表示し続ける」ロジックにする。
                # つまり、gapを前のclipのdurationに足すのではなく、新しいclipとして追加する。
                pass
            
        # ラベル決定
        label = seg.get("label", "")
        stype = seg.get("type", "en")
        
        # Fallback for old data or if label missing
        if not label:
            if stype == "en_normal": label = "English (Normal)"
            elif stype == "jp": label = "Japanese"
            elif stype == "en_slow": label = "English (Slow 0.8x)"
        
        # Determine if Japanese
        is_japanese = (stype == "jp")
        
        # 画像生成
        img_array = create_slide_image(seg["text"], seg["id"], seg.get("word", ""), label, is_japanese, font_path_en, font_path_jp)
        
        # クリップ化
        # 次のセグメントの開始まで表示を延長する（ポーズ中も表示し続けるため）
        next_start = segments[i+1]["start"] if i < len(segments) - 1 else end
        
        # もし次の開始まで間が空いているなら、そこまで伸ばす
        display_duration = duration
        if next_start > end:
            display_duration += (next_start - end)
            
        clip = ImageClip(img_array).with_duration(display_duration)
        clips.append(clip)
        
        current_time = start + display_duration

    if not clips:
        return None
        
    final_video = concatenate_videoclips(clips, method="compose")
    
    # 音声を付与 (イントロ音楽とメイン音声を合成)
    audio_clips_to_mix = []
    main_audio = None
    
    # 1. 映像側の音声 (イントロ音楽など)
    if final_video.audio:
        audio_clips_to_mix.append(final_video.audio)
    
    # 2. メイン音声 (イントロ分だけ遅らせる)
    if audio_path and os.path.exists(audio_path):
        main_audio = AudioFileClip(audio_path)
        
        # 遅延時間を計算
        delay = 0.0
        if intro_text and clips:
            # 最初のクリップがイントロであると仮定
            delay = clips[0].duration
            
        main_audio = main_audio.with_start(delay)
        audio_clips_to_mix.append(main_audio)
        
    if audio_clips_to_mix:
        final_mixed_audio = CompositeAudioClip(audio_clips_to_mix)
        final_video = final_video.with_audio(final_mixed_audio)
        
        # 動画の長さを調整 (映像の長さを正とする)
        final_video = final_video.with_duration(final_video.duration)
        
    try:
        final_video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac", logger=None)
        print("Video generation completed.")
    finally:
        # リソース解放 (WindowsでのPermissionError回避のため)
        if main_audio:
            main_audio.close()
        
        # 各クリップと音声も閉じる
        for clip in clips:
            if clip.audio:
                clip.audio.close()
            clip.close()
            
        if final_video:
            if final_video.audio:
                final_video.audio.close()
            final_video.close()

    return output_file

if __name__ == "__main__":
    # Test
    # ダミーデータで画像生成テスト
    img = create_slide_image("This is a test sentence for checking layout.", 100, "apple", "English (Normal)")
    Image.fromarray(img).save("test_slide.png")
    print("Test image saved to test_slide.png")
