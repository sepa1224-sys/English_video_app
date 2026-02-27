import os
import re
import time
import numpy as np
import textwrap
import traceback
from PIL import Image, ImageDraw, ImageFont
try:
    from moviepy import AudioFileClip, VideoFileClip, ImageClip, ColorClip, VideoClip, concatenate_videoclips, concatenate_audioclips, CompositeVideoClip, CompositeAudioClip
except ImportError:
    from moviepy.editor import AudioFileClip, VideoFileClip, ImageClip, ColorClip, VideoClip, concatenate_videoclips, concatenate_audioclips, CompositeVideoClip, CompositeAudioClip

try:
    from audio_gen_listening import generate_intro_audio, generate_section_audio
except ImportError:
    generate_intro_audio = None
    generate_section_audio = None

def log_debug(msg):
    try:
        with open("video_gen_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except:
        pass

def with_duration_compat(clip, duration):
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    else:
        return clip.set_duration(duration)

def with_audio_compat(clip, audio):
    if hasattr(clip, "with_audio"):
        return clip.with_audio(audio)
    else:
        return clip.set_audio(audio)

def with_position_compat(clip, pos):
    if hasattr(clip, "with_position"):
        return clip.with_position(pos)
    else:
        return clip.set_position(pos)

def apply_se_settings(clip, volume=0.3, fade_duration=0.5):
    if clip is None:
        return None
    
    if hasattr(clip, "with_volume_scaled"):
        clip = clip.with_volume_scaled(volume)
    elif hasattr(clip, "volumex"):
        clip = clip.volumex(volume)
        
    try:
        if hasattr(clip, "audio_fadein"):
            clip = clip.audio_fadein(fade_duration)
        if hasattr(clip, "audio_fadeout"):
            clip = clip.audio_fadeout(fade_duration)
    except:
        pass
        
    return clip

def get_font_path():
    candidates = [
        "C:\\Windows\\Fonts\\Montserrat-ExtraBold.ttf",
        "C:\\Windows\\Fonts\\Montserrat-Bold.ttf",
        "C:\\Windows\\Fonts\\NotoSans-Black.ttf",
        "C:\\Windows\\Fonts\\NotoSans-Bold.ttf",
        "C:\\Users\\PC_User\\AppData\\Local\\Microsoft\\Windows\\Fonts\\NotoSansJP-Bold.otf",
        "C:\\Users\\PC_User\\AppData\\Local\\Microsoft\\Windows\\Fonts\\NotoSansJP-Regular.otf",
        "C:\\Windows\\Fonts\\NotoSansJP-Bold.otf",
        "C:\\Windows\\Fonts\\NotoSansJP-Regular.otf",
        "C:\\Windows\\Fonts\\meiryo.ttc",
        "C:\\Windows\\Fonts\\msgothic.ttc",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def generate_background_illustration(topic: str, output_path: str = "background.png") -> str:
    log_debug(f"Generating background illustration for topic: {topic} (SKIPPING DALL-E)")
    
    black_bg_path = "assets/background_black.png"
    
    if os.path.exists(black_bg_path):
        try:
            import shutil
            shutil.copy(black_bg_path, output_path)
            log_debug(f"  - Using existing black background: {black_bg_path}")
            return output_path
        except Exception as e:
            log_debug(f"  ! Error copying black background: {e}")
            
    log_debug("  - Creating fresh black background.")
    img = Image.new('RGB', (1280, 720), color=(0, 0, 0))
    img.save(output_path)
    return output_path

def draw_centered_text(draw, text, font, img_w=1280, img_h=720, max_width_ratio=0.85, start_y=None, color="white", spacing=15, shadow=True):
    max_width = img_w * max_width_ratio
    
    dummy_img = Image.new('RGB', (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + " " + word if current_line else word
        
        if hasattr(dummy_draw, "textbbox"):
            bbox = dummy_draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
        else:
            try:
                w = font.getsize(test_line)[0]
            except:
                w = len(test_line) * 15
        
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                lines.append(test_line)
                current_line = ""
    
    if current_line:
        lines.append(current_line)

    line_heights = []
    for line in lines:
        if hasattr(dummy_draw, "textbbox"):
            bbox = dummy_draw.textbbox((0, 0), line, font=font)
            h = bbox[3] - bbox[1]
            if h < font.size:
                h = font.size
        else:
            try:
                h = font.getsize(line)[1]
            except:
                h = 30
        line_heights.append(h)
        
    total_h = sum(line_heights) + (len(lines) - 1) * spacing
    
    if start_y is None:
        current_y = (img_h - total_h) // 2
    else:
        current_y = start_y
        
    for i, line in enumerate(lines):
        if hasattr(draw, "textlength"):
            line_w = draw.textlength(line, font=font)
        else:
            try:
                line_w = font.getsize(line)[0]
            except:
                line_w = len(line) * 10
            
        start_x = (img_w - line_w) // 2
        
        if shadow:
            stroke_width = 2
            offsets = []
            
            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx == 0 and dy == 0:
                        continue
                    offsets.append((dx, dy))
            
            shadow_depth = 6
            for k in range(stroke_width + 1, shadow_depth + 1):
                offsets.append((k, k))

            for ox, oy in offsets:
                draw.text((start_x + ox, current_y + oy), line, font=font, fill="black")
        
        draw.text((start_x, current_y), line, font=font, fill=tuple(color) if isinstance(color, tuple) else color)
        
        if i < len(line_heights):
            current_y += line_heights[i] + spacing
        else:
            current_y += 30 + spacing
    
    return current_y

def generate_word_audio_video(audio_results: list, output_file: str, bg_style: str = "black", extras: dict = None):
    print(f"--- generate_word_audio_video (Count: {len(audio_results)}) ---")
    log_debug(f"--- generate_word_audio_video (Count: {len(audio_results)}) ---")
    
    if extras is None:
        extras = {}
    use_countdown = extras.get("use_countdown", True)
    end_left = extras.get("end_left", "")
    end_right = extras.get("end_right", "")
    end_duration = extras.get("end_duration", 10)
    countdown_audio_path = extras.get("countdown_audio") or "assets/Accent08-1.mp3"
    def detect_bgm_path():
        assets_dir = "assets"
        project_root = os.getcwd()
        candidates = []
        if os.path.isdir(assets_dir):
            for name in os.listdir(assets_dir):
                lower = name.lower()
                if lower.endswith(".mp3") or lower.endswith(".wav"):
                    candidates.append(os.path.join(assets_dir, name))
        # search project root as fallback
        try:
            for name in os.listdir(project_root):
                lower = name.lower()
                if lower.endswith(".mp3") or lower.endswith(".wav"):
                    candidates.append(os.path.join(project_root, name))
        except Exception:
            pass
        for p in candidates:
            base = os.path.basename(p)
            if ("歩いて" in base) or ("aruite" in base.lower()):
                print(f"[DEBUG] BGM detected (歩いて歩いて...): {p}")
                return p
        default = os.path.join(assets_dir, "BGM.mp3")
        if os.path.exists(default):
            print(f"[DEBUG] BGM detected (default): {default}")
            return default
        if candidates:
            print(f"[DEBUG] BGM detected (first candidate): {candidates[0]}")
            return candidates[0]
        print(f"!!! CRITICAL ERROR: No BGM audio file found in assets !!!")
        return None
    outro_audio_path = extras.get("outro_audio") or detect_bgm_path()
    
    clips = []
    
    font_path_jp = get_font_path() or "C:\\Windows\\Fonts\\msgothic.ttc"
    
    bg_image_path = "assets/background_black.png"
    bg_img = None
    if os.path.exists(bg_image_path):
        try:
            bg_img = Image.open(bg_image_path).convert("RGB").resize((1280, 720))
        except Exception as e:
            log_debug(f"WordAudio bg load error: {e}")
            bg_img = None
    
    logo_image_path = "assets/logo_kiai.png"
    logo_img = None
    if os.path.exists(logo_image_path):
        try:
            logo_img = Image.open(logo_image_path).convert("RGBA")
        except Exception as e:
            log_debug(f"WordAudio logo load error: {e}")
            logo_img = None
    
    def create_base_clip(duration, draw_func=None):
        if bg_img is None:
            raise RuntimeError("assets/background_black.png is required for Word Audio Mode.")
        img = bg_img.copy()
        if draw_func:
            draw = ImageDraw.Draw(img)
            draw_func(draw, img)
        base_clip = ImageClip(np.array(img))
        base_clip = with_duration_compat(base_clip, duration)
        if logo_img is not None:
            try:
                lw, lh = logo_img.size
            except Exception:
                lw, lh = (200, 80)
            target_width = 200
            if lw > 0:
                scale = min(1.0, float(target_width) / float(lw))
            else:
                scale = 1.0
            new_w = int(lw * scale)
            new_h = int(lh * scale)
            try:
                resized_logo = logo_img.resize((new_w, new_h), Image.LANCZOS)
            except Exception:
                resized_logo = logo_img
                new_w, new_h = lw, lh
            logo_clip = ImageClip(np.array(resized_logo))
            logo_clip = with_duration_compat(logo_clip, duration)
            x = 1280 - new_w - 20
            y = 20
            logo_clip = with_position_compat(logo_clip, (x, y))
            base_clip = CompositeVideoClip([base_clip, logo_clip])
        return base_clip
    
    if use_countdown:
        print("  - Generating Countdown...")
        for n in range(5, 0, -1):
            def draw_countdown(draw, img, text=str(n)):
                try:
                    font_num = ImageFont.truetype(font_path_jp, 200)
                except Exception:
                    font_num = ImageFont.load_default()
                if hasattr(draw, "textbbox"):
                    bbox = draw.textbbox((0, 0), text, font=font_num)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                else:
                    try:
                        w, h = draw.textsize(text, font=font_num)
                    except Exception:
                        w, h = (200, 200)
                try:
                    draw.text((640, 360), text, font=font_num, fill="white", anchor="mm")
                except Exception:
                    draw.text((640 - w // 2, 360 - h // 2), text, font=font_num, fill="white")
            clip = create_base_clip(1.0, draw_countdown)
            # prefer assets path, fallback to project root
            resolved_countdown_path = None
            if countdown_audio_path and os.path.exists(countdown_audio_path):
                resolved_countdown_path = countdown_audio_path
            else:
                alt_path = os.path.join(os.getcwd(), os.path.basename(countdown_audio_path))
                if os.path.exists(alt_path):
                    print(f"[DEBUG] Using fallback countdown audio at project root: {alt_path}")
                    resolved_countdown_path = alt_path
            if resolved_countdown_path:
                countdown_audio = None
                try:
                    countdown_audio = AudioFileClip(resolved_countdown_path)
                except Exception as e:
                    print(f"!!! CRITICAL ERROR: {resolved_countdown_path} not found or unreadable !!!")
                    countdown_audio = None
                if countdown_audio:
                    clip = with_audio_compat(clip, countdown_audio)
                    v_audio = getattr(clip, "audio", None)
                    if (v_audio is None) or (hasattr(v_audio, "duration") and v_audio.duration == 0):
                        print(f"!!! CRITICAL ERROR: Countdown clip audio missing or zero duration (n={n}) !!!")
                    else:
                        try:
                            print(f"[DEBUG] Countdown audio attached: duration={v_audio.duration:.3f}s (n={n})")
                        except Exception:
                            print(f"[DEBUG] Countdown audio attached (n={n})")
                else:
                    print(f"!!! CRITICAL ERROR: Countdown audio could not be loaded for n={n} !!!")
            else:
                print(f"!!! CRITICAL ERROR: {countdown_audio_path} not found !!!")
            clips.append(clip)

    print("  - Generating Word Cards...")
    
    black_candidates = [
        "C:\\Windows\\Fonts\\Montserrat-ExtraBold.ttf",
        "C:\\Windows\\Fonts\\Montserrat-Bold.ttf",
        "C:\\Users\\PC_User\\AppData\\Local\\Microsoft\\Windows\\Fonts\\NotoSansJP-Black.otf",
        "C:\\Windows\\Fonts\\NotoSansJP-Black.otf",
        "C:\\Users\\PC_User\\AppData\\Local\\Microsoft\\Windows\\Fonts\\NotoSansJP-ExtraBold.otf",
        "C:\\Windows\\Fonts\\NotoSansJP-ExtraBold.otf",
        "C:\\Users\\PC_User\\AppData\\Local\\Microsoft\\Windows\\Fonts\\NotoSansJP-Bold.otf",
        "C:\\Windows\\Fonts\\NotoSansJP-Bold.otf"
    ]
    regular_candidates = [
        "C:\\Windows\\Fonts\\Montserrat-SemiBold.ttf",
        "C:\\Windows\\Fonts\\Montserrat-Regular.ttf",
        "C:\\Users\\PC_User\\AppData\\Local\\Microsoft\\Windows\\Fonts\\NotoSansJP-Regular.otf",
        "C:\\Windows\\Fonts\\NotoSansJP-Regular.otf"
    ]
    black_path = None
    regular_path = None
    for p in black_candidates:
        if os.path.exists(p):
            black_path = p
            break
    for p in regular_candidates:
        if os.path.exists(p):
            regular_path = p
            break
    if black_path is None:
        black_path = font_path_jp
    if regular_path is None:
        regular_path = font_path_jp
    try:
        font_word = ImageFont.truetype(black_path, 140)
        font_mean = ImageFont.truetype(regular_path, 80)
        font_id = ImageFont.truetype(regular_path, 30)
    except:
        font_word = ImageFont.load_default()
        font_mean = ImageFont.load_default()
        font_id = ImageFont.load_default()

    for i, item in enumerate(audio_results):
        try:
            word_item = item.get("word_item", {})
            audio_path = item.get("path", "")
            
            if not audio_path or not os.path.exists(audio_path):
                print(f"    ! Skipping word {i+1}: Audio file not found ({audio_path})")
                continue
                
            if (i + 1) % 10 == 0:
                print(f"    Processing word {i+1}/{len(audio_results)}...")
            
            word_id = word_item.get("id", 0)
            try:
                numeric_id = int(word_id)
            except Exception:
                numeric_id = 0
            id_text = f"No. {numeric_id:04d}"
            word_text = word_item.get("word", "")
            meaning_text = word_item.get("meaning", "")
            segments = [s.strip() for s in re.split(r'[、/;；／\n]', meaning_text) if s.strip()]
            meaning_lines = []
            if segments:
                for idx, seg in enumerate(segments, start=1):
                    try:
                        circled = chr(0x2460 + (idx - 1))
                    except Exception:
                        circled = f"{idx}."
                    meaning_lines.append(f"{circled} {seg}")
            print(f"[DEBUG] Meaning segments after split (word={word_text}): {meaning_lines}")
            
            audio_clip = AudioFileClip(audio_path)
            
            meta_segments = item.get("metadata") or []
            eng_start = 0.0
            eng_end = audio_clip.duration
            jp_start = None
            jp_end = None
            
            if isinstance(meta_segments, list) and len(meta_segments) > 0:
                eng_starts = []
                eng_ends = []
                jp_starts = []
                jp_ends = []
                for s in meta_segments:
                    mode = str(s.get("display_mode"))
                    st = float(s.get("start", 0.0))
                    en = float(s.get("end", 0.0))
                    if en <= st:
                        continue
                    if mode in ["step1", "step3", "step4"]:
                        eng_starts.append(st)
                        eng_ends.append(en)
                    elif mode == "step2":
                        jp_starts.append(st)
                        jp_ends.append(en)
                if eng_starts and eng_ends:
                    eng_start = min(eng_starts)
                    eng_end = max(eng_ends)
                if jp_starts and jp_ends:
                    jp_start = min(jp_starts)
                    jp_end = max(jp_ends)
            
            try:
                eng_audio = audio_clip.subclip(eng_start, eng_end)
            except Exception:
                eng_audio = audio_clip
                eng_start = 0.0
                eng_end = audio_clip.duration
            
            jp_audio = None
            if jp_start is not None and jp_end is not None and jp_end > jp_start:
                try:
                    jp_audio = audio_clip.subclip(jp_start, jp_end)
                except Exception:
                    jp_audio = None
            
            eng_dur = eng_audio.duration
            gap_eng_jap = float(extras.get("gap_eng_to_jap", extras.get("interval_eng_jap", 0.5)))
            jp_trigger = eng_dur + gap_eng_jap if jp_audio is not None else eng_dur
            
            audio_elements = []
            if hasattr(eng_audio, "with_start"):
                audio_elements.append(eng_audio.with_start(0))
            else:
                audio_elements.append(eng_audio.set_start(0))
            if jp_audio is not None:
                if hasattr(jp_audio, "with_start"):
                    audio_elements.append(jp_audio.with_start(jp_trigger))
                else:
                    audio_elements.append(jp_audio.set_start(jp_trigger))
            
            try:
                mixed_audio = CompositeAudioClip(audio_elements)
            except Exception as e:
                print(f"    ! Error mixing audio for word {i+1} ({word_text}): {e}")
                mixed_audio = eng_audio
            
            if jp_audio is not None:
                total_duration = jp_trigger + jp_audio.duration + 0.5
            else:
                total_duration = eng_dur + 0.5
            
            def make_frame(t, id_text=id_text, w_text=word_text, m_text=meaning_text):
                img = Image.new("RGB", (1280, 720), (0, 0, 0))
                draw = ImageDraw.Draw(img)
                
                if logo_img is not None:
                    try:
                        lw, lh = logo_img.size
                    except Exception:
                        lw, lh = (200, 80)
                    target_width = 200
                    if lw > 0:
                        scale = min(1.0, float(target_width) / float(lw))
                    else:
                        scale = 1.0
                    new_w = int(lw * scale)
                    new_h = int(lh * scale)
                    try:
                        resized_logo = logo_img.resize((new_w, new_h), Image.LANCZOS)
                    except Exception:
                        resized_logo = logo_img
                        new_w, new_h = lw, lh
                    try:
                        img.paste(resized_logo, (1280 - new_w - 20, 20), mask=resized_logo)
                    except Exception:
                        img.paste(resized_logo, (1280 - new_w - 20, 20))
                
                if id_text:
                    try:
                        draw.text((50, 50), id_text, font=font_id, fill="gray")
                    except Exception:
                        draw.text((50, 50), id_text, fill="gray")
                
                text = w_text or ""
                if text:
                    try:
                        if hasattr(draw, "textbbox"):
                            x1, y1, x2, y2 = draw.textbbox((0, 0), text, font=font_word)
                            tw = x2 - x1
                            th = y2 - y1
                        else:
                            tw, th = font_word.getsize(text)
                    except Exception:
                        tw, th = (0, 0)
                    
                    if t < jp_trigger:
                        ty = 300 - th // 2
                    else:
                        ty = 220 - th // 2
                    tx = (1280 - tw) // 2
                    try:
                        draw.text((tx, ty), text, font=font_word, fill="white")
                    except Exception:
                        draw.text((tx, ty), text, fill="white")
                
                if t >= jp_trigger and m_text:
                    segments_local = [s.strip() for s in re.split(r'[、/;；／\n]', m_text) if s.strip()]
                    lines = []
                    if segments_local:
                        for idx, seg in enumerate(segments_local, start=1):
                            try:
                                circled = chr(0x2460 + (idx - 1))
                            except Exception:
                                circled = f"{idx}."
                            lines.append(f"{circled} {seg}")
                    else:
                        lines = [m_text]
                    
                    try:
                        jp_font = ImageFont.truetype(regular_path, 80)
                    except Exception:
                        jp_font = font_mean
                    
                    y = 450
                    x = 200
                    for line in lines:
                        try:
                            if hasattr(draw, "textbbox"):
                                x1, y1, x2, y2 = draw.textbbox((0, 0), line, font=jp_font)
                                lh = y2 - y1
                            else:
                                lh = jp_font.getsize(line)[1]
                        except Exception:
                            lh = 80
                        try:
                            draw.text((x, y), line, font=jp_font, fill="#CCCCCC")
                        except Exception:
                            draw.text((x, y), line, fill="#CCCCCC")
                        y += int(lh * 1.5)
                
                return np.array(img)
            
            dynamic_clip = VideoClip(make_frame).with_duration(total_duration)
            dynamic_clip = with_audio_compat(dynamic_clip, mixed_audio)
            clips.append(dynamic_clip)
            
        except Exception as e:
            msg = f"Error processing word {i+1} ({word_item.get('word', 'Unknown')}): {e}"
            print(f"    ! {msg}")
            log_debug(msg)
            import traceback
            tb = traceback.format_exc()
            print(tb)
            log_debug(tb)
            raise RuntimeError(msg) from e
            
    if end_left or end_right or outro_audio_path:
        print("  - Generating End Screen...")
        def draw_end(draw, img, left=end_left, right=end_right):
            try:
                font_end = ImageFont.truetype(regular_path, 56)
            except Exception:
                font_end = font_mean
            if left:
                draw.text((100, 650), left, font=font_end, fill="white")
            if right:
                try:
                    draw.text((1180, 650), right, font=font_end, fill="white", anchor="rm")
                except Exception:
                    try:
                        if hasattr(draw, "textbbox"):
                            x1, y1, x2, y2 = draw.textbbox((0, 0), right, font=font_end)
                            w_r = x2 - x1
                        else:
                            w_r = font_end.getsize(right)[0]
                    except Exception:
                        w_r = 0
                    draw.text((1180 - w_r, 650), right, font=font_end, fill="white")
        end_clip = create_base_clip(float(end_duration), draw_end)
        if outro_audio_path and os.path.exists(outro_audio_path):
            try:
                outro_audio_clip = AudioFileClip(outro_audio_path)
            except Exception:
                print(f"!!! CRITICAL ERROR: {outro_audio_path} not found or unreadable !!!")
                outro_audio_clip = None
            if outro_audio_clip:
                end_clip = with_audio_compat(end_clip, outro_audio_clip)
                v_audio = getattr(end_clip, "audio", None)
                if (v_audio is None) or (hasattr(v_audio, "duration") and v_audio.duration == 0):
                    print(f"!!! CRITICAL ERROR: End screen audio missing or zero duration !!!")
                else:
                    try:
                        print(f"[DEBUG] End screen audio attached: duration={v_audio.duration:.3f}s")
                    except Exception:
                        print(f"[DEBUG] End screen audio attached")
        else:
            if outro_audio_path:
                print(f"!!! CRITICAL ERROR: {outro_audio_path} not found !!!")
            else:
                print(f"!!! CRITICAL ERROR: No BGM path detected !!!")
        clips.append(end_clip)

    if not clips:
        raise RuntimeError("No clips generated for Word Audio Video.")
    
    print(f"  - Concatenating {len(clips)} clips...")
    try:
        for idx, c in enumerate(clips):
            c_dur = getattr(c, "duration", None)
            print(f"    clip[{idx}] type={type(c)} duration={c_dur}")
    except Exception as e:
        print(f"    ! Error while inspecting clips list: {e}")
        
    final_video = concatenate_videoclips(clips, method="compose")
    
    print(f"  - Writing video to {output_file}...")
    final_video.write_videofile(
        output_file,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None
    )
    
    try:
        final_video.close()
        for c in clips:
            try:
                c.close()
            except:
                pass
    except:
        pass
    
    print("  - Video generation complete.")

def generate_exam_video(audio_segments: list, questions: list, bg_image_path: str, output_file: str, topic: str, special_clips: dict = None, vocab_list: list = None, university: str = "todai"):
    if university == "todai":
        uni_label = "東京大学"
    elif university == "osaka":
        uni_label = "大阪大学"
    else:
        uni_label = "京都大学"

    log_debug(f"  - Generating Exam Video for {uni_label}...")
    
    resources_to_close = []
    
    if not os.path.exists("temp"):
        os.makedirs("temp")

    try:
        if special_clips is None:
            special_clips = {}
        if vocab_list is None:
            vocab_list = []
        
        font_path_jp = get_font_path() or "C:\\Windows\\Fonts\\msgothic.ttc"
        font_path_en = font_path_jp

        highlight_words_en = [v.get("word", "") for v in vocab_list if v.get("word")]
        
        highlight_words_jp = []
        for v in vocab_list:
            meaning = v.get("meaning", "")
            if not meaning:
                continue
            parts = re.split(r'[、,;]', meaning)
            for p in parts:
                p = p.strip()
                p = re.sub(r'\(.*?\)', '', p).strip()
                if len(p) > 1:
                    highlight_words_jp.append(p)
        
        highlight_words_jp = list(set([m for m in highlight_words_jp if len(m) > 1]))
        
        bg_target_path = "assets/background_black.png"
        
        log_debug(f"    > Enforcing Black Background: {bg_target_path}")
        
        if os.path.exists(bg_target_path):
            try:
                bg_img_base = Image.open(bg_target_path).convert('RGB').resize((1280, 720))
            except Exception as e:
                log_debug(f"    ! Error loading background {bg_target_path}: {e}")
                bg_img_base = Image.new('RGB', (1280, 720), color=(0, 0, 0))
        else:
            log_debug("    > Assets background not found. Using generated black background.")
            bg_img_base = Image.new('RGB', (1280, 720), color=(0, 0, 0))
        
        def create_bg_clip(duration, overlay_func=None):
            img = bg_img_base.copy()
            if overlay_func:
                draw = ImageDraw.Draw(img)
                overlay_func(draw, img)
            
            clip = ImageClip(np.array(img))
            clip = with_duration_compat(clip, duration)
            return clip

        def get_text_layout(text, font, max_width, draw_obj=None):
            lines = []
            words = text.split()
            current_line = ""
            
            if draw_obj is None:
                dummy_img = Image.new('RGB', (1, 1))
                draw_obj = ImageDraw.Draw(dummy_img)

            for word in words:
                test_line = current_line + " " + word if current_line else word
                
                if hasattr(draw_obj, "textbbox"):
                    bbox = draw_obj.textbbox((0, 0), test_line, font=font)
                    w = bbox[2] - bbox[0]
                else:
                    try:
                        w = font.getsize(test_line)[0]
                    except:
                        w = len(test_line) * 15
                
                if w <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                        current_line = word
                        if hasattr(draw_obj, "textbbox"):
                            bbox = draw_obj.textbbox((0, 0), current_line, font=font)
                            w = bbox[2] - bbox[0]
                        else:
                            w = len(current_line) * 15
                            
                        if w > max_width:
                            chars = list(current_line)
                            current_line = ""
                            temp_line = ""
                            for char in chars:
                                test_c = temp_line + char
                                if hasattr(draw_obj, "textbbox"):
                                    bbox = draw_obj.textbbox((0, 0), test_c, font=font)
                                    cw = bbox[2] - bbox[0]
                                else:
                                    cw = len(test_c) * 15
                                
                                if cw <= max_width:
                                    temp_line = test_c
                                else:
                                    lines.append(temp_line)
                                    temp_line = char
                            current_line = temp_line
                    else:
                        current_line = word
                        chars = list(current_line)
                        current_line = ""
                        temp_line = ""
                        for char in chars:
                            test_c = temp_line + char
                            if hasattr(draw_obj, "textbbox"):
                                bbox = draw_obj.textbbox((0, 0), test_c, font=font)
                                cw = bbox[2] - bbox[0]
                            else:
                                cw = len(test_c) * 15
                            
                            if cw <= max_width:
                                temp_line = test_c
                            else:
                                lines.append(temp_line)
                                temp_line = char
                        current_line = temp_line
            
            if current_line:
                lines.append(current_line)
            if not lines and text:
                lines = [text]
            
            line_heights = []
            for line in lines:
                if hasattr(draw_obj, "textbbox"):
                    bbox = draw_obj.textbbox((0, 0), line, font=font)
                    h = bbox[3] - bbox[1]
                    if h < font.size:
                        h = font.size
                else:
                    try:
                        h = font.getsize(line)[1]
                    except:
                        h = 30
                line_heights.append(h)
                
            total_h = sum(line_heights) + (len(lines) - 1) * 15
            return lines, total_h, line_heights

        def get_fitted_font(draw, text, font_path, max_width, max_height, initial_size, min_size=20, spacing=15):
            current_size = initial_size
            while current_size >= min_size:
                try:
                    font = ImageFont.truetype(font_path, current_size)
                except:
                    return ImageFont.load_default()
                
                lines, total_h, line_heights = get_text_layout(text, font, max_width, draw)
                real_total_h = sum(line_heights) + (len(lines) - 1) * spacing
                
                if real_total_h <= max_height:
                    return font
                
                current_size -= 2
            
            try:
                return ImageFont.truetype(font_path, min_size)
            except:
                return ImageFont.load_default()

        def draw_centered_text_inner(draw, text, font, img_w=1280, img_h=720, max_width_ratio=0.85, start_y=None, color="white", spacing=15, shadow=True, highlight_words=None):
            if highlight_words is None:
                highlight_words = []
            max_width = img_w * max_width_ratio
            
            lines, _, _ = get_text_layout(text, font, max_width, draw)
            
            line_heights = []
            for line in lines:
                if hasattr(draw, "textbbox"):
                    bbox = draw.textbbox((0, 0), line, font=font)
                    h = bbox[3] - bbox[1]
                    if h < font.size:
                        h = font.size
                else:
                    try:
                        h = font.getsize(line)[1]
                    except:
                        h = 30
                line_heights.append(h)
            
            total_h = sum(line_heights) + (len(lines) - 1) * spacing
            
            if start_y is None:
                current_y = (img_h - total_h) // 2
            else:
                current_y = start_y
                
            for i in range(len(lines)):
                line = lines[i]
                
                if hasattr(draw, "textlength"):
                    line_w = draw.textlength(line, font=font)
                else:
                    try:
                        line_w = font.getsize(line)[0]
                    except:
                        line_w = len(line) * 10
                    
                start_x = (img_w - line_w) // 2
                
                if highlight_words and color != "#FF0000":
                    patterns = []
                    for hw in highlight_words:
                        if not hw:
                            continue
                        esc = re.escape(hw)
                        if len(hw) > 3:
                            if hw.endswith('e'):
                                base = hw[:-1]
                                pat = re.escape(base) + r"(?:e|es|d|ed|ing|al|als|ation|ations|ely)?"
                            elif hw.endswith('y'):
                                base = hw[:-1]
                                pat = re.escape(base) + r"(?:y|ies|ied|ying|ily)"
                            else:
                                pat = esc + r"(?:s|es|d|ed|ing|ly|al|als|tion|tions)?"
                        else:
                            pat = esc
                        patterns.append(pat)
                    
                    full_pattern = r"(?i)\b(" + "|".join(patterns) + r")\b"
                    
                    try:
                        parts = re.split(full_pattern, line)
                        current_segments = []
                        for part in parts:
                            if not part:
                                continue
                            if re.fullmatch(full_pattern, part):
                                current_segments.append((part, "#FF0000"))
                            else:
                                current_segments.append((part, color))
                    except Exception as e:
                        log_debug(f"Highlight regex error: {e}")
                        current_segments = [(line, color)]
                else:
                    current_segments = [(line, color)]
                
                current_x = start_x
                for seg_text, seg_color in current_segments:
                    if hasattr(draw, "textlength"):
                        seg_w = draw.textlength(seg_text, font=font)
                    else:
                        try:
                            seg_w = font.getsize(seg_text)[0]
                        except:
                            seg_w = len(seg_text) * 10
                    
                    if shadow:
                        stroke_width = 2
                        offsets = []
                        
                        for dx in range(-stroke_width, stroke_width + 1):
                            for dy in range(-stroke_width, stroke_width + 1):
                                if dx == 0 and dy == 0:
                                    continue
                                offsets.append((dx, dy))
                        
                        shadow_depth = 6
                        for k in range(stroke_width + 1, shadow_depth + 1):
                            offsets.append((k, k))

                        for ox, oy in offsets:
                            draw.text((current_x + ox, current_y + oy), seg_text, font=font, fill="black")
                    
                    draw.text((current_x, current_y), seg_text, font=font, fill=seg_color)
                    current_x += seg_w
                
                if i < len(line_heights):
                    current_y += line_heights[i] + spacing
                else:
                    current_y += 30 + spacing
            
            return current_y

        log_debug("    > Building Intro...")
        intro_text_1 = f"{uni_label}受験リスニングトレーニング"
        intro_text_2 = "スクリプトと答え、解説は概要欄を参照"
        
        if university == "todai":
            intro_filename = "intro_todai.mp3"
        elif university == "osaka":
            intro_filename = "intro_osaka.mp3"
        else:
            intro_filename = "intro_kyoto.mp3"
            
        intro_audio_path = special_clips.get("intro", f"assets/{intro_filename}")
        
        if not os.path.exists(intro_audio_path) and generate_intro_audio:
            log_debug(f"      (Generating Intro Audio for {university}...)")
            intro_audio_path = f"temp/{intro_filename}"
            generate_intro_audio(intro_text_1, intro_audio_path)
             
        intro_clip = None
        if os.path.exists(intro_audio_path):
            ac_intro = AudioFileClip(intro_audio_path)
            resources_to_close.append(ac_intro)
            intro_duration = 3.0 
            
            def draw_intro(draw, img):
                try:
                    f_main = ImageFont.truetype(font_path_jp, 60)
                    f_sub = ImageFont.truetype(font_path_jp, 30)
                except:
                    f_main = ImageFont.load_default()
                    f_sub = ImageFont.load_default()
                    
                draw_centered_text_inner(draw, intro_text_1, f_main, start_y=300)
                draw_centered_text_inner(draw, intro_text_2, f_sub, start_y=400, color=(200, 200, 255))

            intro_clip = create_bg_clip(intro_duration, draw_intro)
            intro_clip = with_audio_compat(intro_clip, ac_intro)

        listening_segments = [s for s in audio_segments if s.get("type") == "listening_part"]
        questions_segments = [s for s in audio_segments if s.get("type") == "questions_part"]
        
        log_debug("    > Building Part 1: Listening Focus...")
        
        if not listening_segments:
            log_debug("  ! Warning: No listening_part segments found. Using all segments as fallback (deprecated).")
            listening_segments = audio_segments

        audio_clips_list = []
        valid_segments = [s for s in listening_segments if os.path.exists(s["audio_path"])]
        for seg in valid_segments:
            try:
                ac = AudioFileClip(seg["audio_path"])
                resources_to_close.append(ac)
                audio_clips_list.append(ac)
            except:
                pass
                
        if not audio_clips_list:
            return None
        full_dialog_audio = concatenate_audioclips(audio_clips_list)
        
        part1_audio_elements = []
        
        sec_list_audio_path = special_clips.get("sec_listening", "assets/listening_section.mp3")
        if not os.path.exists(sec_list_audio_path) and generate_section_audio:
            log_debug("      (Generating Listening Section Audio...)")
            sec_list_audio_path = "temp/sec_listening.mp3"
            generate_section_audio("Listening Section", sec_list_audio_path)

        if os.path.exists(sec_list_audio_path):
            ac_sec = AudioFileClip(sec_list_audio_path)
            resources_to_close.append(ac_sec)
            part1_audio_elements.append(ac_sec)
        
        se_complete_path = special_clips.get("se_complete", "assets/完了4.mp3")
        if not os.path.exists(se_complete_path):
            if os.path.exists("assets/完了4.mp3"):
                se_complete_path = "assets/完了4.mp3"
            elif os.path.exists("assets/パッ.mp3"):
                se_complete_path = "assets/パッ.mp3"
            elif os.path.exists("assets/next_word.mp3"):
                se_complete_path = "assets/next_word.mp3"
             
        if os.path.exists(se_complete_path):
            ac_se = AudioFileClip(se_complete_path)
            ac_se = apply_se_settings(ac_se)
            resources_to_close.append(ac_se)
            part1_audio_elements.append(ac_se)
            
        part1_audio_elements.append(full_dialog_audio)
        
        full_part1_audio = concatenate_audioclips(part1_audio_elements)
        duration_part1 = full_part1_audio.duration
        
        def draw_part1(draw, img):
            try:
                f_title = ImageFont.truetype(font_path_en, 80)
            except:
                f_title = ImageFont.load_default()
                
            draw_centered_text_inner(draw, "Listening Section", f_title)
        
        part1_video = create_bg_clip(duration_part1, draw_part1)
        part1_video = with_audio_compat(part1_video, full_part1_audio)
        
        log_debug("    > Building Part 2: Questions...")
        part2_clips = []
        
        sec_q_audio_path = special_clips.get("sec_questions", "assets/question_section.mp3")
        if not os.path.exists(sec_q_audio_path) and generate_section_audio:
            log_debug("      (Generating Question Section Audio...)")
            sec_q_audio_path = "temp/sec_questions.mp3"
            generate_section_audio("Question Section", sec_q_audio_path)

        q_title_audio = None
        if os.path.exists(sec_q_audio_path):
            q_title_audio = AudioFileClip(sec_q_audio_path)
            resources_to_close.append(q_title_audio)
            
        q_trans_clips = []
        if q_title_audio:
            q_trans_clips.append(q_title_audio)
        if os.path.exists(se_complete_path):
            ac_se_q = AudioFileClip(se_complete_path)
            ac_se_q = apply_se_settings(ac_se_q)
            resources_to_close.append(ac_se_q)
            q_trans_clips.append(ac_se_q)
        
        q_trans_audio = concatenate_audioclips(q_trans_clips) if q_trans_clips else None
        q_title_dur = (q_trans_audio.duration + 1.0) if q_trans_audio else 3.0
        
        def draw_q_title(draw, img):
            try:
                f = ImageFont.truetype(font_path_en, 80)
            except:
                f = ImageFont.load_default()
            draw_centered_text_inner(draw, "Question Section", f)
            
        trans_clip = create_bg_clip(q_title_dur, draw_q_title)
        if q_trans_audio:
            trans_clip = with_audio_compat(trans_clip, q_trans_audio)
        part2_clips.append(trans_clip)

        for i, q in enumerate(questions):
            q_audio = None
            q_audio_path = q.get("audio_path")
            
            if not (q_audio_path and os.path.exists(q_audio_path)):
                if generate_section_audio:
                    log_debug(f"      (Generating Question {i+1} Audio...)")
                    q_audio_path = f"temp/q_{i+1}_{int(time.time())}.mp3"
                    generate_section_audio(q["question"], q_audio_path)
            
            if q_audio_path and os.path.exists(q_audio_path):
                q_main_audio = AudioFileClip(q_audio_path)
                resources_to_close.append(q_main_audio)
                
                audio_elements = [(q_main_audio, 0)]
                
                # 英語→選択肢の順に、音声を「順次」再生させるためのオフセット
                current_time_q = q_main_audio.duration + 0.2
                
                choices_text = q.get("choices", [])
                if not choices_text:
                    choices_text = q.get("options", [])
                
                existing_paths = q.get("choices_audio_paths", [])
                
                for j, choice_text in enumerate(choices_text):
                    c_path = None
                    
                    if j < len(existing_paths) and existing_paths[j] and os.path.exists(existing_paths[j]):
                        c_path = existing_paths[j]
                    
                    if not c_path:
                        c_path = f"temp/q_{i+1}_c_{j+1}_{int(time.time())}.mp3"
                        if generate_section_audio:
                            generate_section_audio(choice_text, c_path)
                    
                    if c_path and os.path.exists(c_path):
                        try:
                            c_clip = AudioFileClip(c_path)
                            resources_to_close.append(c_clip)
                            audio_elements.append((c_clip, current_time_q))
                            current_time_q += c_clip.duration + 0.2
                        except Exception as e:
                            log_debug(f"      ! Error loading choice audio {c_path}: {e}")
                
                final_q_audio = CompositeAudioClip([clip.with_start(t) for clip, t in audio_elements])
                q_dur = current_time_q + 3.0 
                
            else:
                final_q_audio = None
                q_dur = 10.0

            def draw_question(draw, img):
                q_text = f"Q{i+1}: {q['question']}"
                choices = q.get("choices", [])
                
                total_chars = len(q_text) + sum(len(c) for c in choices)
                
                q_size = 50
                c_size = 40
                
                if total_chars > 200:
                    q_size = 35
                    c_size = 30
                
                max_total_height = 630
                
                while True:
                    try:
                        q_font = ImageFont.truetype(font_path_en, q_size)
                        c_font = ImageFont.truetype(font_path_en, c_size)
                    except:
                        q_font = ImageFont.load_default()
                        c_font = ImageFont.load_default()
                        break
                        
                    max_w = 1280 * 0.85
                    
                    _, h_q, _ = get_text_layout(q_text, q_font, max_w, draw)
                    
                    h_choices = []
                    for c in choices:
                        _, h_c, _ = get_text_layout(c, c_font, max_w, draw)
                        h_choices.append(h_c)
                    
                    total_h = h_q + 40 + sum(h_choices) + (25 * (len(choices) - 1))
                    
                    if total_h <= max_total_height:
                        break
                    
                    if q_size <= 15:
                        break
                    
                    q_size = max(15, q_size - 2)
                    c_size = max(15, c_size - 2)
                
                start_y = (720 - total_h) // 2
                start_y = max(30, start_y)
                
                current_y = start_y
                
                current_y = draw_centered_text_inner(draw, q_text, q_font, start_y=current_y, img_w=1280)
                
                current_y += 40
                
                for choice in choices:
                    current_y = draw_centered_text_inner(draw, choice, c_font, start_y=current_y, color=(200, 255, 200), spacing=15, img_w=1280)
                    current_y += 10
            
            slide_clip = create_bg_clip(q_dur, draw_question)
            if final_q_audio:
                slide_clip = with_audio_compat(slide_clip, final_q_audio)
            
            part2_clips.append(slide_clip)
            
        part2_video = concatenate_videoclips(part2_clips)
        
        log_debug("    > Building Part 3: Review...")
        part3_clips = []
        
        sec_rev_audio_path = special_clips.get("sec_review", "assets/review_section.mp3")
        if not os.path.exists(sec_rev_audio_path) and generate_section_audio:
            log_debug("      (Generating Review Section Audio...)")
            sec_rev_audio_path = "temp/sec_review.mp3"
            generate_section_audio("Review Section", sec_rev_audio_path)

        r_title_audio = None
        if os.path.exists(sec_rev_audio_path):
            r_title_audio = AudioFileClip(sec_rev_audio_path)
            resources_to_close.append(r_title_audio)
        
        r_trans_clips = []
        if r_title_audio:
            r_trans_clips.append(r_title_audio)
        if os.path.exists(se_complete_path):
            ac_se_r = AudioFileClip(se_complete_path)
            ac_se_r = apply_se_settings(ac_se_r)
            resources_to_close.append(ac_se_r)
            r_trans_clips.append(ac_se_r)
             
        r_trans_audio = concatenate_audioclips(r_trans_clips) if r_trans_clips else None
        r_title_dur = (r_trans_audio.duration + 1.0) if r_trans_audio else 3.0
        
        def draw_r_title(draw, img):
            try:
                f = ImageFont.truetype(font_path_en, 80)
            except:
                f = ImageFont.load_default()
            draw_centered_text_inner(draw, "Review Section", f)
            
        trans_clip3 = create_bg_clip(r_title_dur, draw_r_title)
        if r_trans_audio:
            trans_clip3 = with_audio_compat(trans_clip3, r_trans_audio)
            
        part3_clips.append(trans_clip3)
        
        valid_review_segments = [s for s in listening_segments if os.path.exists(s["audio_path"])]
        
        for seg in valid_review_segments:
            seg_dur = seg["duration"]
            if seg_dur <= 0:
                continue
            
            try:
                ac = AudioFileClip(seg["audio_path"])
                resources_to_close.append(ac)
            except:
                continue
            
            def draw_script(draw, img):
                speaker = seg.get("speaker")
                en_text = seg.get("text") or seg.get("content") or seg.get("dialog")
                jp_text = seg.get("japanese") or seg.get("translation")

                if (not speaker or not en_text) and seg.get("lines") and len(seg["lines"]) > 0:
                    first_line = seg["lines"][0]
                    if not speaker:
                        speaker = first_line.get("speaker")
                    if not en_text:
                        en_text = first_line.get("text")
                    if not jp_text:
                        jp_text = first_line.get("translation") or first_line.get("japanese")

                if not speaker or speaker == "Unknown":
                    speaker = "Student A" 

                if not en_text:
                    en_text = ""
                if not jp_text:
                    jp_text = ""
                
                en_text_display = en_text
                
                try:
                    s_font = ImageFont.truetype(font_path_en, 40)
                    e_font = ImageFont.truetype(font_path_en, 35)
                    j_font = ImageFont.truetype(font_path_jp, 35)
                except:
                    s_font = ImageFont.load_default()
                    e_font = ImageFont.load_default()
                    j_font = ImageFont.load_default()
                    
                max_width = 1280 * 0.85
                max_height = 600
                initial_size = 65
                min_size = 30
                
                e_font = get_fitted_font(draw, en_text_display, font_path_en, max_width, max_height, initial_size, min_size)

                draw_centered_text_inner(draw, en_text_display, e_font, start_y=None, color="white", highlight_words=highlight_words_en)
                
            clip = create_bg_clip(seg_dur, draw_script)
            clip = with_audio_compat(clip, ac)
            part3_clips.append(clip)
            
        part3_video = concatenate_videoclips(part3_clips)
        
        log_debug("    > Assembling Final Video (Listening -> Questions -> Review -> Questions)...")
        final_clips_list = []
        if intro_clip:
            final_clips_list.append(intro_clip)
        
        final_clips_list.append(part1_video)
        
        final_clips_list.append(part2_video)
        
        final_clips_list.append(part3_video)
        
        final_clips_list.append(part2_video)
        
        log_debug(f"DEBUG: final_clips_list length: {len(final_clips_list)}")
        final_video = concatenate_videoclips(final_clips_list)
        log_debug(f"DEBUG: final_video duration: {final_video.duration}")
        log_debug(f"DEBUG: Writing video to {output_file}")
        
        final_video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac")
        
        if os.path.exists(output_file):
            log_debug(f"DEBUG: Video file successfully created at {output_file}")
        else:
            log_debug(f"DEBUG: Video file NOT FOUND at {output_file} after write_videofile call")
        
        timestamps_log = []
        current_time = 0.0
        
        if intro_clip:
            timestamps_log.append({"type": "Intro", "start": current_time})
            current_time += intro_clip.duration
            
        timestamps_log.append({"type": "Listening Section", "start": current_time})
        current_time += part1_video.duration
        
        timestamps_log.append({"type": "Questions", "start": current_time})
        current_time += part2_video.duration
        
        timestamps_log.append({"type": "Review (Script)", "start": current_time})
        current_time += part3_video.duration
        
        timestamps_log.append({"type": "Questions (Review)", "start": current_time})
        current_time += part2_video.duration
        
        return output_file, timestamps_log

    except Exception as e:
        log_debug(f"CRITICAL ERROR in generate_exam_video: {e}")
        traceback.print_exc()
        raise e
    finally:
        log_debug("DEBUG: Cleaning up audio resources...")
        for res in resources_to_close:
            try:
                res.close()
            except:
                pass
