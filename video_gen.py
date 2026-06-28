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

# --- Bundled Font Paths (OS-independent) ---
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
FONT_PATH_BOLD = os.path.join(_FONT_DIR, "NotoSansCJKjp-Bold.otf")
FONT_PATH_BLACK = os.path.join(_FONT_DIR, "NotoSansCJKjp-Black.otf")

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
    # Bundled fonts (top priority — OS-independent)
    if os.path.exists(FONT_PATH_BOLD):
        return FONT_PATH_BOLD
    candidates = [
        # macOS (Japanese + English)
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Windows
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
        "C:\\Windows\\Fonts\\arial.ttf",
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

    def detect_word_se_path():
        assets_dir = "assets"
        candidates = []
        if os.path.isdir(assets_dir):
            for name in os.listdir(assets_dir):
                lower = name.lower()
                if not (lower.endswith(".mp3") or lower.endswith(".wav")):
                    continue
                if any(kw in name for kw in ["シュ", "shu", "wind", "woosh", "whoosh"]):
                    candidates.append(os.path.join(assets_dir, name))
        if candidates:
            return candidates[0]
        fallback = os.path.join(assets_dir, "Accent08-1.mp3")
        if os.path.exists(fallback):
            return fallback
        return None

    word_se_path = detect_word_se_path()

    clips = []
    
    font_path_jp = get_font_path() or FONT_PATH_BOLD
    
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
    
    # Bundled fonts first, then system fallbacks
    black_path = FONT_PATH_BLACK if os.path.exists(FONT_PATH_BLACK) else None
    regular_path = FONT_PATH_BOLD if os.path.exists(FONT_PATH_BOLD) else None
    if black_path is None:
        black_candidates = [
            "C:\\Windows\\Fonts\\Montserrat-ExtraBold.ttf",
            "C:\\Windows\\Fonts\\Montserrat-Bold.ttf",
            "C:\\Windows\\Fonts\\NotoSansJP-Black.otf",
            "C:\\Windows\\Fonts\\NotoSansJP-Bold.otf",
        ]
        for p in black_candidates:
            if os.path.exists(p):
                black_path = p
                break
    if regular_path is None:
        regular_candidates = [
            "C:\\Windows\\Fonts\\Montserrat-SemiBold.ttf",
            "C:\\Windows\\Fonts\\Montserrat-Regular.ttf",
            "C:\\Windows\\Fonts\\NotoSansJP-Regular.otf",
        ]
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
            total_audio_dur = audio_clip.duration

            # --- Parse per-segment timing from audio metadata ---
            # audio_gen emits items with: label ("en"/"jp"/"gap"...), part_index
            # (for jp meanings), absolute "start"/"end", and "text".
            meta_segments = item.get("metadata") or []
            jp_reveals = []  # (start_time, part_index, text)
            if isinstance(meta_segments, list):
                for s in meta_segments:
                    label = str(s.get("label", ""))
                    seg_type = str(s.get("type", ""))
                    try:
                        seg_start = float(s.get("start", 0.0))
                    except Exception:
                        seg_start = 0.0
                    if label == "jp" and seg_type in ("content", "silent_text"):
                        try:
                            pidx = int(s.get("part_index", len(jp_reveals)))
                        except Exception:
                            pidx = len(jp_reveals)
                        jp_reveals.append((seg_start, pidx, str(s.get("text", ""))))

            # Sort by spoken order, attach circled numbers (①②③...)
            jp_reveals.sort(key=lambda x: (x[1], x[0]))
            reveal_lines = []  # (reveal_time, display_text)
            for order, (seg_start, pidx, txt) in enumerate(jp_reveals):
                circled = chr(0x2460 + order) if order < 20 else f"{order + 1}."
                clean = re.sub(r'[①-⑳]', '', txt).strip()
                reveal_lines.append((seg_start, f"{circled} {clean}"))

            # Fallback when metadata lacks per-meaning timing: reveal all at once
            # after the English word + the EN->JP gap.
            if not reveal_lines and meaning_lines:
                gap_eng_jap = float(extras.get("gap_eng_to_jap", extras.get("interval_eng_jap", 1.0)))
                fallback_trigger = min(total_audio_dur, max(0.0, gap_eng_jap))
                for line in meaning_lines:
                    reveal_lines.append((fallback_trigger, line))

            # --- Audio: play the pre-concatenated clip as-is (EN + gaps + JP) ---
            audio_elements = []
            if hasattr(audio_clip, "with_start"):
                audio_elements.append(audio_clip.with_start(0))
            else:
                audio_elements.append(audio_clip.set_start(0))

            if word_se_path:
                try:
                    se_clip = AudioFileClip(word_se_path)
                    se_clip = apply_se_settings(se_clip, volume=0.4, fade_duration=0.1)
                    if hasattr(se_clip, "with_start"):
                        audio_elements.insert(0, se_clip.with_start(0))
                    else:
                        audio_elements.insert(0, se_clip.set_start(0))
                except Exception as e:
                    log_debug(f"Word SE load error: {e}")

            try:
                mixed_audio = CompositeAudioClip(audio_elements)
            except Exception as e:
                print(f"    ! Error mixing audio for word {i+1} ({word_text}): {e}")
                mixed_audio = audio_clip

            total_duration = total_audio_dur + 0.5

            # --- Layout (English word raised; meanings lowered for clear spacing) ---
            WORD_CENTER_Y = 190
            MEANING_START_Y = 370
            MEANING_LINE_STEP = 115
            
            def make_frame(t, id_text=id_text, w_text=word_text, reveal_lines=reveal_lines):
                # Use the same textured background as the countdown / end screen
                if bg_img is not None:
                    img = bg_img.copy()
                else:
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
                        draw.text((50, 50), id_text, font=font_id, fill="white")
                    except Exception:
                        draw.text((50, 50), id_text, fill="white")

                # English word: always visible at a fixed (raised) position
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

                    ty = WORD_CENTER_Y - th // 2
                    tx = (1280 - tw) // 2
                    try:
                        stroke_w = 3
                        for ox in range(-stroke_w, stroke_w + 1):
                            for oy in range(-stroke_w, stroke_w + 1):
                                if ox == 0 and oy == 0:
                                    continue
                                draw.text((tx + ox, ty + oy), text, font=font_word, fill="white")
                        draw.text((tx, ty), text, font=font_word, fill="#2060C0")
                    except Exception:
                        draw.text((tx, ty), text, fill="#2060C0")

                # Japanese meanings: progressive reveal synced to each meaning's audio.
                # Each meaning keeps a fixed slot so earlier lines never shift.
                try:
                    jp_font = ImageFont.truetype(regular_path, 80)
                except Exception:
                    jp_font = font_mean
                y = MEANING_START_Y
                for reveal_t, line in reveal_lines:
                    if t >= reveal_t:
                        try:
                            if hasattr(draw, "textbbox"):
                                x1, y1, x2, y2 = draw.textbbox((0, 0), line, font=jp_font)
                                lw_line = x2 - x1
                            else:
                                lw_line, _ = jp_font.getsize(line)
                        except Exception:
                            lw_line = 0
                        x = (1280 - lw_line) // 2
                        try:
                            draw.text((x, y), line, font=jp_font, fill="#FFFFFF")
                        except Exception:
                            draw.text((x, y), line, fill="#FFFFFF")
                    y += MEANING_LINE_STEP

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
        
        font_path_jp = get_font_path() or FONT_PATH_BOLD
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

        exam_logo_img = None
        exam_logo_image_path = "assets/logo_kiai.png"
        if os.path.exists(exam_logo_image_path):
            try:
                exam_logo_img = Image.open(exam_logo_image_path).convert("RGBA")
            except Exception as e:
                log_debug(f"Exam logo load error: {e}")

        # --- Phase 5: optional animated (discussion-style) background ---
        # Set env EXAM_MOTION_BG=false to fall back to the static image (much
        # faster render). The motion clip is dimmed with a dark scrim so all
        # text stays readable.
        motion_bg_enabled = os.environ.get("EXAM_MOTION_BG", "false").lower() == "true"
        motion_bg_src = None
        SCRIM_ALPHA = 150
        if motion_bg_enabled and os.path.exists("background_video.mp4"):
            try:
                _mbg = VideoFileClip("background_video.mp4")
                try:
                    motion_bg_src = _mbg.resized((1280, 720))
                except Exception:
                    motion_bg_src = _mbg.resize((1280, 720))
                try:
                    motion_bg_src = motion_bg_src.without_audio()
                except Exception:
                    pass
                resources_to_close.append(motion_bg_src)
                log_debug("    > Motion background ENABLED (background_video.mp4)")
            except Exception as e:
                log_debug(f"    ! Motion bg load failed, using static: {e}")
                motion_bg_src = None

        def _paste_logo(target_img):
            if exam_logo_img is None:
                return
            try:
                lw, lh = exam_logo_img.size
            except Exception:
                lw, lh = (200, 80)
            target_width = 200
            scale = min(1.0, float(target_width) / float(lw)) if lw > 0 else 1.0
            new_w = int(lw * scale)
            new_h = int(lh * scale)
            try:
                resized_logo = exam_logo_img.resize((new_w, new_h), Image.LANCZOS)
            except Exception:
                resized_logo = exam_logo_img
                new_w, new_h = lw, lh
            try:
                target_img.paste(resized_logo, (1280 - new_w - 20, 20), mask=resized_logo)
            except Exception:
                target_img.paste(resized_logo, (1280 - new_w - 20, 20))

        def _looped_bg(duration):
            try:
                from moviepy import vfx
                return motion_bg_src.with_effects([vfx.Loop(duration=duration)])
            except Exception:
                try:
                    return motion_bg_src.subclipped(0, min(duration, motion_bg_src.duration))
                except Exception:
                    return with_duration_compat(motion_bg_src, duration)

        def create_bg_clip(duration, overlay_func=None):
            # Motion background: dark scrim + text drawn on a transparent overlay,
            # composited over the looped video.
            if motion_bg_src is not None:
                try:
                    overlay_img = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
                    draw = ImageDraw.Draw(overlay_img)
                    draw.rectangle([0, 0, 1280, 720], fill=(0, 0, 0, SCRIM_ALPHA))
                    if overlay_func:
                        overlay_func(draw, overlay_img)
                    _paste_logo(overlay_img)
                    bg = _looped_bg(duration)
                    ov = ImageClip(np.array(overlay_img), transparent=True)
                    ov = with_duration_compat(ov, duration)
                    comp = CompositeVideoClip([bg, ov])
                    return with_duration_compat(comp, duration)
                except Exception as e:
                    log_debug(f"    ! Motion composite failed, static fallback: {e}")

            # Static background fallback
            img = bg_img_base.copy()
            if overlay_func:
                draw = ImageDraw.Draw(img)
                overlay_func(draw, img)
            _paste_logo(img)
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

        # --- Phase 5-A: Pre-Listening question screen removed ---
        # Start directly with the Listening Section (the question-preview screen
        # made viewers drop off). Questions are now shown twice later instead.
        pre_listening_video = None

        log_debug("    > Building Part 1: Listening Focus...")
        
        if not listening_segments:
            log_debug("  ! Warning: No listening_part segments found. Using all segments as fallback (deprecated).")
            listening_segments = audio_segments

        valid_segments = [s for s in listening_segments if os.path.exists(s["audio_path"])]
        if not valid_segments:
            return None

        # SE path (shared with Part 2/3)
        se_complete_path = special_clips.get("se_complete", "assets/完了4.mp3")
        if not os.path.exists(se_complete_path):
            if os.path.exists("assets/完了4.mp3"):
                se_complete_path = "assets/完了4.mp3"
            elif os.path.exists("assets/パッ.mp3"):
                se_complete_path = "assets/パッ.mp3"
            elif os.path.exists("assets/next_word.mp3"):
                se_complete_path = "assets/next_word.mp3"

        # --- Part 1: Title clip + per-segment speaker-label clips ---
        part1_clips = []

        # 1a. Title clip: "Listening Section" text + title audio + SE
        title_audio_elements = []
        sec_list_audio_path = special_clips.get("sec_listening", "assets/listening_section.mp3")
        if not os.path.exists(sec_list_audio_path) and generate_section_audio:
            log_debug("      (Generating Listening Section Audio...)")
            sec_list_audio_path = "temp/sec_listening.mp3"
            generate_section_audio("Listening Section", sec_list_audio_path)

        if os.path.exists(sec_list_audio_path):
            ac_sec = AudioFileClip(sec_list_audio_path)
            resources_to_close.append(ac_sec)
            title_audio_elements.append(ac_sec)

        if os.path.exists(se_complete_path):
            ac_se = AudioFileClip(se_complete_path)
            ac_se = apply_se_settings(ac_se)
            resources_to_close.append(ac_se)
            title_audio_elements.append(ac_se)

        if title_audio_elements:
            title_audio = concatenate_audioclips(title_audio_elements)
            title_dur = title_audio.duration + 0.5
        else:
            title_audio = None
            title_dur = 3.0

        def draw_listening_title(draw, img):
            try:
                f_title = ImageFont.truetype(font_path_en, 80)
            except:
                f_title = ImageFont.load_default()
            draw_centered_text_inner(draw, "Listening Section", f_title)

        title_clip = create_bg_clip(title_dur, draw_listening_title)
        if title_audio:
            title_clip = with_audio_compat(title_clip, title_audio)
        part1_clips.append(title_clip)

        # 1b. Helper: extract speaker from segment
        def _get_speaker(seg):
            sp = seg.get("speaker")
            if sp:
                return sp
            lines = seg.get("lines") or []
            if lines and isinstance(lines, list):
                sp = lines[0].get("speaker")
                if sp:
                    return sp
            lt = seg.get("line_timings") or []
            if lt and isinstance(lt, list):
                sp = lt[0].get("speaker")
                if sp:
                    return sp
            return "Speaker"

        # 1c. Per-segment clips with speaker labels (merge consecutive same-speaker)
        merged_groups = []
        for seg in valid_segments:
            sp = _get_speaker(seg)
            if merged_groups and merged_groups[-1]["speaker"] == sp:
                merged_groups[-1]["segments"].append(seg)
            else:
                merged_groups.append({"speaker": sp, "segments": [seg]})

        for group in merged_groups:
            sp = group["speaker"]
            group_audio_clips = []
            for seg in group["segments"]:
                try:
                    ac = AudioFileClip(seg["audio_path"])
                    resources_to_close.append(ac)
                    group_audio_clips.append(ac)
                except:
                    pass
            if not group_audio_clips:
                continue
            group_audio = concatenate_audioclips(group_audio_clips) if len(group_audio_clips) > 1 else group_audio_clips[0]
            group_dur = group_audio.duration

            def draw_speaker_label(draw, img, speaker=sp):
                try:
                    f_sub = ImageFont.truetype(font_path_en, 50)
                    f_speaker = ImageFont.truetype(font_path_en, 90)
                except:
                    f_sub = ImageFont.load_default()
                    f_speaker = ImageFont.load_default()
                draw_centered_text_inner(draw, "Listening Section", f_sub, start_y=200, color=(180, 180, 180))
                draw_centered_text_inner(draw, speaker, f_speaker, start_y=340)

            seg_clip = create_bg_clip(group_dur, draw_speaker_label)
            seg_clip = with_audio_compat(seg_clip, group_audio)
            part1_clips.append(seg_clip)

        part1_video = concatenate_videoclips(part1_clips)
        
        # 6分台化(2026-06-28): 設問・解説は読み上げず画面表示のみにして大幅短縮。
        # 視聴維持率データ上、短い動画ほど維持率が2〜3倍高い。Trueに戻せば従来の読み上げ。
        SPOKEN_QUESTIONS = False
        SPOKEN_EXPLANATIONS = False

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
            choices_text = q.get("choices", []) or q.get("options", [])

            if SPOKEN_QUESTIONS:
                q_audio_path = q.get("audio_path")
                if not (q_audio_path and os.path.exists(q_audio_path)):
                    if generate_section_audio:
                        log_debug(f"      (Generating Question {i+1} Audio...)")
                        q_audio_path = f"temp/q_{i+1}_{int(time.time())}.mp3"
                        # Phase 5: announce "Question N" before reading, slightly slower pace.
                        generate_section_audio(f"Question {i+1}. {q['question']}", q_audio_path, speed=0.92)

                if q_audio_path and os.path.exists(q_audio_path):
                    q_main_audio = AudioFileClip(q_audio_path)
                    resources_to_close.append(q_main_audio)

                    audio_elements = [(q_main_audio, 0)]

                    # 英語→選択肢の順に、音声を「順次」再生させるためのオフセット
                    current_time_q = q_main_audio.duration + 0.2

                    existing_paths = q.get("choices_audio_paths", [])

                    for j, choice_text in enumerate(choices_text):
                        c_path = None

                        if j < len(existing_paths) and existing_paths[j] and os.path.exists(existing_paths[j]):
                            c_path = existing_paths[j]

                        if not c_path:
                            c_path = f"temp/q_{i+1}_c_{j+1}_{int(time.time())}.mp3"
                            if generate_section_audio:
                                generate_section_audio(choice_text, c_path, speed=0.92)

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
            else:
                # 無音・画面表示のみ。読む時間を文字量から確保（6〜14秒）。
                final_q_audio = None
                chars = len(q.get("question", "")) + sum(len(str(c)) for c in choices_text)
                q_dur = max(6.0, min(14.0, chars / 16))

            def draw_question(draw, img):
                q_text = f"Q{i+1}: {q['question']}"
                choices = q.get("choices", [])
                
                total_chars = len(q_text) + sum(len(c) for c in choices)

                q_size = 56
                c_size = 46

                if total_chars > 200:
                    q_size = 40
                    c_size = 34

                max_total_height = 650
                
                total_h = 0
                while True:
                    try:
                        q_font = ImageFont.truetype(font_path_en, q_size)
                        c_font = ImageFont.truetype(font_path_en, c_size)
                    except:
                        q_font = ImageFont.load_default()
                        c_font = ImageFont.load_default()

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
        
        # Phase 5-C: Review shows the FULL script (every listening segment),
        # not an excerpt. Red highlighting of target vocab is preserved below.
        all_review = [s for s in listening_segments if os.path.exists(s["audio_path"])]
        valid_review_segments = all_review
        log_debug(f"    [INFO] Review (full script): {len(valid_review_segments)} segments")
        
        # Slightly larger review font; paginate so long turns never overflow.
        REVIEW_FONT_SIZE = 60          # was 55 (user: a bit larger)
        REVIEW_MAX_LINES = 7           # lines per slide that fit below the speaker label
        REVIEW_TEXT_TOP = 150
        review_max_width = 1280 * 0.85

        for seg in valid_review_segments:
            seg_dur = seg["duration"]
            if seg_dur <= 0:
                continue

            try:
                ac_full = AudioFileClip(seg["audio_path"])
                resources_to_close.append(ac_full)
            except:
                continue

            # Extract speaker / English text (once, outside the draw closure)
            speaker = seg.get("speaker")
            en_text = seg.get("text") or seg.get("content") or seg.get("dialog")
            if (not speaker or not en_text) and seg.get("lines"):
                fl = seg["lines"][0]
                speaker = speaker or fl.get("speaker")
                en_text = en_text or fl.get("text")
            if not speaker or speaker == "Unknown":
                speaker = "Student A"
            en_text = en_text or ""

            try:
                r_font = ImageFont.truetype(font_path_en, REVIEW_FONT_SIZE)
            except:
                r_font = ImageFont.load_default()

            wrapped = get_text_layout(en_text, r_font, review_max_width)[0]
            pages = []
            if wrapped:
                for k in range(0, len(wrapped), REVIEW_MAX_LINES):
                    pages.append(" ".join(wrapped[k:k + REVIEW_MAX_LINES]))
            else:
                pages = [en_text]
            n_pages = max(1, len(pages))

            for pi, page_text in enumerate(pages):
                a0 = seg_dur * pi / n_pages
                a1 = seg_dur * (pi + 1) / n_pages
                page_dur = max(0.1, a1 - a0)
                try:
                    sub_ac = ac_full.subclipped(a0, a1)
                except Exception:
                    try:
                        sub_ac = ac_full.subclip(a0, a1)
                    except Exception:
                        sub_ac = ac_full

                def draw_script(draw, img, speaker=speaker, page_text=page_text, r_font=r_font):
                    try:
                        f_section = ImageFont.truetype(font_path_en, 32)
                        f_speaker = ImageFont.truetype(font_path_en, 56)
                    except:
                        f_section = ImageFont.load_default()
                        f_speaker = ImageFont.load_default()
                    draw_centered_text_inner(draw, "Review Section", f_section, start_y=30, color=(150, 150, 150), shadow=False)
                    draw_centered_text_inner(draw, speaker, f_speaker, start_y=78)
                    draw_centered_text_inner(draw, page_text, r_font, start_y=REVIEW_TEXT_TOP, color="white", highlight_words=highlight_words_en)

                clip = create_bg_clip(page_dur, draw_script)
                clip = with_audio_compat(clip, sub_ac)
                part3_clips.append(clip)

        part3_video = concatenate_videoclips(part3_clips)
        
        # Phase 5-D (improved): "Answers & Explanations" section after the Review.
        # Re-showing identical questions risks YouTube's repetitious-content flag,
        # so the second pass reveals the correct answer + a Japanese explanation
        # (higher learning value, safer for monetization).
        log_debug("    > Building Part 4: Answers & Explanations...")
        part4_clips = []

        sec_ans_audio_path = "temp/sec_answers.mp3"
        if generate_section_audio and not os.path.exists(sec_ans_audio_path):
            generate_section_audio("Answers and Explanations", sec_ans_audio_path, speed=0.92)
        a_trans_clips = []
        if os.path.exists(sec_ans_audio_path):
            a_title_audio = AudioFileClip(sec_ans_audio_path)
            resources_to_close.append(a_title_audio)
            a_trans_clips.append(a_title_audio)
        if os.path.exists(se_complete_path):
            ac_se_a = AudioFileClip(se_complete_path)
            ac_se_a = apply_se_settings(ac_se_a)
            resources_to_close.append(ac_se_a)
            a_trans_clips.append(ac_se_a)
        a_trans_audio = concatenate_audioclips(a_trans_clips) if a_trans_clips else None
        a_title_dur = (a_trans_audio.duration + 1.0) if a_trans_audio else 3.0

        def draw_a_title(draw, img):
            try:
                f = ImageFont.truetype(font_path_en, 70)
            except:
                f = ImageFont.load_default()
            draw_centered_text_inner(draw, "Answers & Explanations", f)
        a_trans_clip = create_bg_clip(a_title_dur, draw_a_title)
        if a_trans_audio:
            a_trans_clip = with_audio_compat(a_trans_clip, a_trans_audio)
        part4_clips.append(a_trans_clip)

        for i, q in enumerate(questions):
            correct = str(q.get("correct_answer", "")).strip()
            choices = q.get("choices", []) or q.get("options", [])
            correct_text = ""
            for c in choices:
                cs = str(c).strip()
                if correct and cs[:1].upper() == correct[:1].upper():
                    correct_text = cs
                    break
            exp_jp = q.get("explanation_jp") or q.get("explanation") or ""
            exp_en = q.get("explanation") or ""

            ans_audio = None
            if SPOKEN_EXPLANATIONS and generate_section_audio:
                # Final explanation is spoken in Japanese (ja-JP voice).
                ans_path = f"temp/ans_{i+1}_{int(time.time())}.mp3"
                spoken = f"第{i+1}問。正解は {correct} です。{exp_jp}"
                generate_section_audio(spoken, ans_path, speed=0.95, voice="ja-JP-NanamiNeural")
                if os.path.exists(ans_path):
                    ans_audio = AudioFileClip(ans_path)
                    resources_to_close.append(ans_audio)
            if ans_audio:
                ans_dur = ans_audio.duration + 2.0
            else:
                # 無音・画面表示のみ。解説を読む時間を文字量から確保（6〜14秒）。
                ans_dur = max(6.0, min(14.0, len(str(exp_jp)) / 14))

            def draw_answer(draw, img, idx=i, correct=correct, correct_text=correct_text, exp_jp=exp_jp):
                try:
                    f_head = ImageFont.truetype(font_path_en, 52)
                except:
                    f_head = ImageFont.load_default()
                y = draw_centered_text_inner(draw, f"Q{idx+1}   Answer: {correct}", f_head, start_y=40, color=(120, 255, 120))
                if correct_text:
                    cf = get_fitted_font(draw, correct_text, font_path_en, 1280 * 0.85, 130, 46, 28)
                    y = draw_centered_text_inner(draw, correct_text, cf, start_y=y + 20, color=(120, 255, 120))
                if exp_jp:
                    ef = get_fitted_font(draw, exp_jp, font_path_en, 1280 * 0.85, 360, 46, 26)
                    draw_centered_text_inner(draw, exp_jp, ef, start_y=max(y + 40, 280), color="white")

            a_clip = create_bg_clip(ans_dur, draw_answer)
            if ans_audio:
                a_clip = with_audio_compat(a_clip, ans_audio)
            part4_clips.append(a_clip)

        part4_video = concatenate_videoclips(part4_clips)

        log_debug("    > Assembling Final Video (Intro -> Listening -> Questions -> Review -> Answers & Explanations)...")
        final_clips_list = []
        if intro_clip:
            final_clips_list.append(intro_clip)

        # YouTube向け短縮(2026-06-27): Part3「Review」=本文の2周目を省略し「本文1回読み」に。
        # 伸びている動画(東大Part1-3)が6分台=本文1回のため。スクリプト全文は概要欄にあり冗長。
        INCLUDE_REVIEW = False
        final_clips_list.append(part1_video)     # Listening
        final_clips_list.append(part2_video)     # Questions (attempt)
        if INCLUDE_REVIEW:
            final_clips_list.append(part3_video) # Review (full script)
        final_clips_list.append(part4_video)     # Answers & Explanations

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

        timestamps_log.append({"type": "Questions (1st)", "start": current_time})
        current_time += part2_video.duration

        if INCLUDE_REVIEW:
            timestamps_log.append({"type": "Review (Full Script)", "start": current_time})
            current_time += part3_video.duration

        timestamps_log.append({"type": "Answers & Explanations", "start": current_time})
        current_time += part4_video.duration

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
