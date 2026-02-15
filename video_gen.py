import os
import re
import time
import numpy as np
import textwrap
import traceback
from PIL import Image, ImageDraw, ImageFont
try:
    from moviepy import AudioFileClip, VideoFileClip, ImageClip, ColorClip, concatenate_videoclips, concatenate_audioclips, CompositeVideoClip, CompositeAudioClip
except ImportError:
    from moviepy.editor import AudioFileClip, VideoFileClip, ImageClip, ColorClip, concatenate_videoclips, concatenate_audioclips, CompositeVideoClip, CompositeAudioClip

# Import dynamic audio generation
try:
    from audio_gen_listening import generate_intro_audio, generate_section_audio
except ImportError:
    generate_intro_audio = None
    generate_section_audio = None

# LOGGING HELPER
def log_debug(msg):
    try:
        with open("video_gen_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except: pass

# Compatibility helpers for MoviePy v1/v2
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
        # Fallback for MoviePy v1
        return clip.set_position(pos)

def apply_se_settings(clip, volume=0.3, fade_duration=0.5):
    """
    Apply volume reduction and fade in/out to Sound Effect clips.
    User Request: Volume 30% (0.3), Fade In/Out to avoid harshness.
    """
    if clip is None: return None
    
    # 1. Volume Adjustment
    if hasattr(clip, "with_volume_scaled"):
        clip = clip.with_volume_scaled(volume)
    elif hasattr(clip, "volumex"):
        clip = clip.volumex(volume)
        
    # 2. Fade In/Out
    # Note: audio_fadein/out might be methods of AudioFileClip or require audio_fadein fx
    try:
        if hasattr(clip, "audio_fadein"):
             clip = clip.audio_fadein(fade_duration)
        if hasattr(clip, "audio_fadeout"):
             clip = clip.audio_fadeout(fade_duration)
    except:
        pass
        
    return clip

def get_font_path():
    """Return a valid font path for Japanese text."""
    candidates = [
        # Noto Sans JP (Google Fonts / Adobe Fonts) - User Request Priority
        "C:\\Users\\PC_User\\AppData\\Local\\Microsoft\\Windows\\Fonts\\NotoSansJP-Bold.otf",
        "C:\\Users\\PC_User\\AppData\\Local\\Microsoft\\Windows\\Fonts\\NotoSansJP-Regular.otf",
        "C:\\Windows\\Fonts\\NotoSansJP-Bold.otf",
        "C:\\Windows\\Fonts\\NotoSansJP-Regular.otf",
        # Fallbacks
        "C:\\Windows\\Fonts\\meiryo.ttc",
        "C:\\Windows\\Fonts\\msgothic.ttc",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def generate_background_illustration(topic: str, output_path: str = "background.png") -> str:
    """
    Generate a background illustration.
    UPDATED: Now strictly uses 'assets/background_black.png' (or generates black) to avoid DALL-E costs and unify design.
    """
    log_debug(f"Generating background illustration for topic: {topic} (SKIPPING DALL-E)")
    
    # Target black background
    black_bg_path = "assets/background_black.png"
    
    if os.path.exists(black_bg_path):
        try:
            # Copy or just load? The caller might move it.
            # Safe to just copy content to output_path
            import shutil
            shutil.copy(black_bg_path, output_path)
            log_debug(f"  - Using existing black background: {black_bg_path}")
            return output_path
        except Exception as e:
            log_debug(f"  ! Error copying black background: {e}")
            
    # Fallback: Create Black Image
    log_debug("  - Creating fresh black background.")
    img = Image.new('RGB', (1280, 720), color=(0, 0, 0))
    img.save(output_path)
    return output_path

def generate_exam_video(audio_segments: list, questions: list, bg_image_path: str, output_file: str, topic: str, special_clips: dict = None, vocab_list: list = None, university: str = "todai"):
    """
    Generate the 4-part Exam Listening Video (Todai/Kyoto).
    Part 1: Listening (No Subtitles)
    Part 2: Questions (Slides + Reading Audio)
    Part 3: Review (Script + Red Highlights)
    Part 4: Questions (Repeat)
    """
    if university == "todai":
        uni_label = "東京大学"
    elif university == "osaka":
        uni_label = "大阪大学"
    else:
        uni_label = "京都大学"

    log_debug(f"  - Generating Exam Video for {uni_label}...")
    
    resources_to_close = []
    
    # Ensure temp directory exists
    if not os.path.exists("temp"):
        os.makedirs("temp")

    try:
        if special_clips is None: special_clips = {}
        if vocab_list is None: vocab_list = []
        
        # Fonts
        # User Request: Use Noto Sans JP for both Japanese and English text to ensure consistent design.
        font_path_jp = get_font_path() or "C:\\Windows\\Fonts\\msgothic.ttc"
        # Force English font to match Japanese font (Noto Sans JP)
        font_path_en = font_path_jp

        # Prepare highlight words
        # English words and Japanese meanings
        highlight_words_en = [v.get("word", "") for v in vocab_list if v.get("word")]
        
        # Improved Japanese meaning extraction: Split by delimiters to capture key terms
        highlight_words_jp = []
        for v in vocab_list:
            meaning = v.get("meaning", "")
            if not meaning: continue
            # Split by common delimiters
            parts = re.split(r'[、,;]', meaning)
            for p in parts:
                p = p.strip()
                # Remove parenthesis content if any (optional, but good for "word (context)")
                p = re.sub(r'\(.*?\)', '', p).strip()
                if len(p) > 1: # Avoid single chars
                    highlight_words_jp.append(p)
        
        # Filter out empty or too short meanings (to avoid accidental highlighting of single chars)
        highlight_words_jp = list(set([m for m in highlight_words_jp if len(m) > 1]))
        
        # --- Common Background ---
        # User Request: FORCE Black Background throughout (0s to end). DALL-E generation is disabled.
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
        
        # Helper to create an ImageClip from the common background with overlays
        def create_bg_clip(duration, overlay_func=None):
            img = bg_img_base.copy()
            if overlay_func:
                draw = ImageDraw.Draw(img)
                overlay_func(draw, img)
            
            clip = ImageClip(np.array(img))
            clip = with_duration_compat(clip, duration)
            return clip

        def get_text_layout(text, font, max_width, draw_obj=None):
            """
            Calculates the lines and total height for wrapped text.
            Returns: (lines, total_height, line_heights)
            """
            lines = []
            words = text.split()
            current_line = ""
            
            # Use a dummy draw if none provided (for textbbox)
            if draw_obj is None:
                dummy_img = Image.new('RGB', (1, 1))
                draw_obj = ImageDraw.Draw(dummy_img)

            for word in words:
                test_line = current_line + " " + word if current_line else word
                
                if hasattr(draw_obj, "textbbox"):
                    bbox = draw_obj.textbbox((0, 0), test_line, font=font)
                    w = bbox[2] - bbox[0]
                else:
                    try: w = font.getsize(test_line)[0]
                    except: w = len(test_line) * 15
                
                if w <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                        current_line = word
                        # Check if single word is too long
                        if hasattr(draw_obj, "textbbox"):
                            bbox = draw_obj.textbbox((0, 0), current_line, font=font)
                            w = bbox[2] - bbox[0]
                        else: w = len(current_line) * 15
                            
                        if w > max_width:
                             # Force split
                             chars = list(current_line)
                             current_line = ""
                             temp_line = ""
                             for char in chars:
                                 test_c = temp_line + char
                                 if hasattr(draw_obj, "textbbox"):
                                     bbox = draw_obj.textbbox((0, 0), test_c, font=font)
                                     cw = bbox[2] - bbox[0]
                                 else: cw = len(test_c) * 15
                                 
                                 if cw <= max_width:
                                     temp_line = test_c
                                 else:
                                     lines.append(temp_line)
                                     temp_line = char
                             current_line = temp_line
                    else:
                         current_line = word
                         # Force split
                         chars = list(current_line)
                         current_line = ""
                         temp_line = ""
                         for char in chars:
                             test_c = temp_line + char
                             if hasattr(draw_obj, "textbbox"):
                                 bbox = draw_obj.textbbox((0, 0), test_c, font=font)
                                 cw = bbox[2] - bbox[0]
                             else: cw = len(test_c) * 15
                             
                             if cw <= max_width:
                                 temp_line = test_c
                             else:
                                 lines.append(temp_line)
                                 temp_line = char
                         current_line = temp_line
            
            if current_line: lines.append(current_line)
            if not lines and text: lines = [text]
            
            line_heights = []
            for line in lines:
                if hasattr(draw_obj, "textbbox"):
                    bbox = draw_obj.textbbox((0, 0), line, font=font)
                    h = bbox[3] - bbox[1]
                    if h < font.size: h = font.size
                else:
                    try: h = font.getsize(line)[1]
                    except: h = 30
                line_heights.append(h)
                
            total_h = sum(line_heights) + (len(lines) - 1) * 15 # default spacing 15
            return lines, total_h, line_heights

        def get_fitted_font(draw, text, font_path, max_width, max_height, initial_size, min_size=20, spacing=15):
            """
            Finds the largest font size that fits the text within max_width and max_height.
            """
            current_size = initial_size
            while current_size >= min_size:
                try:
                    font = ImageFont.truetype(font_path, current_size)
                except:
                    return ImageFont.load_default()
                
                lines, total_h, line_heights = get_text_layout(text, font, max_width, draw)
                # Recalculate total_h with correct spacing
                real_total_h = sum(line_heights) + (len(lines) - 1) * spacing
                
                if real_total_h <= max_height:
                    return font
                
                current_size -= 2
            
            # Return min size
            try: return ImageFont.truetype(font_path, min_size)
            except: return ImageFont.load_default()

        def draw_centered_text(draw, text, font, img_w=1280, img_h=720, max_width_ratio=0.85, start_y=None, color="white", spacing=15, shadow=True, highlight_words=None):
            """
            Draws text wrapped and centered.
            """
            if highlight_words is None: highlight_words = []
            max_width = img_w * max_width_ratio
            
            lines, _, _ = get_text_layout(text, font, max_width, draw)
            
            # User Request: SAFETY FIX & Rebuild line_heights to ensure 1:1 match
            line_heights = []
            for line in lines:
                if hasattr(draw, "textbbox"):
                    bbox = draw.textbbox((0, 0), line, font=font)
                    h = bbox[3] - bbox[1]
                    if h < font.size: h = font.size
                else:
                    try: h = font.getsize(line)[1]
                    except: h = 30
                line_heights.append(h)
            
            # Recalculate total_h
            total_h = sum(line_heights) + (len(lines) - 1) * spacing
            
            if start_y is None:
                current_y = (img_h - total_h) // 2
            else:
                current_y = start_y
                
            # User Request: Safe Loop using range(len(lines))
            for i in range(len(lines)):
                line = lines[i]
                
                if hasattr(draw, "textlength"):
                    line_w = draw.textlength(line, font=font)
                else:
                    try: line_w = font.getsize(line)[0]
                    except: line_w = len(line) * 10
                    
                start_x = (img_w - line_w) // 2
                
                # Highlight Logic
                # 1. Build a robust regex for all highlight words
                # Handle inflections: if ends in 'e', make it optional for suffixes like 'ing', 'al'
                # revive -> reviv(e|ed|ing|al|als)
                if highlight_words and color != "#FF0000": # Don't highlight inside already highlighted (if recursive?)
                    # log_debug(f"DEBUG: Highlighting enabled. Words: {len(highlight_words)} items")
                    patterns = []
                    for hw in highlight_words:
                        if not hw: continue
                        esc = re.escape(hw)
                        # Heuristic for inflections
                        if len(hw) > 3:
                            if hw.endswith('e'):
                                base = hw[:-1] # reviv
                                # Match: revive, revives, revived, reviving, revival, revivals
                                # Pattern: reviv(?:e|es|ed|ing|al|als|ation|ations|ely)
                                pat = re.escape(base) + r"(?:e|es|d|ed|ing|al|als|ation|ations|ely)?"
                            elif hw.endswith('y'):
                                base = hw[:-1] # stud
                                # Match: study, studies, studied, studying
                                # Pattern: stud(?:y|ies|ied|ying)
                                pat = re.escape(base) + r"(?:y|ies|ied|ying|ily)"
                            else:
                                # Standard
                                pat = esc + r"(?:s|es|d|ed|ing|ly|al|als|tion|tions)?"
                        else:
                            pat = esc
                        patterns.append(pat)
                    
                    # Combine into one regex
                    full_pattern = r"(?i)\b(" + "|".join(patterns) + r")\b"
                    
                    try:
                        # Split by the full pattern
                        # re.split with capturing group returns [text, match, text, match...]
                        parts = re.split(full_pattern, line)
                        current_segments = []
                        for part in parts:
                            if not part: continue
                            # Check if this part matches one of the words (it should be a match if it was captured)
                            # But re.split might return empty strings or non-matches.
                            # We can check if it matches the pattern or logic.
                            # Actually, capturing groups in split are returned.
                            # We can verify if it 'looks like' a keyword or just context.
                            # Simple check: does it match the pattern?
                            if re.fullmatch(full_pattern, part):
                                current_segments.append((part, "#FF0000")) # RED, No Brackets
                            else:
                                current_segments.append((part, color))
                    except Exception as e:
                        log_debug(f"Highlight regex error: {e}")
                        current_segments = [(line, color)]
                else:
                    current_segments = [(line, color)]
                
                # Draw Segments
                
                # Draw Segments
                current_x = start_x
                for seg_text, seg_color in current_segments:
                    if hasattr(draw, "textlength"):
                        seg_w = draw.textlength(seg_text, font=font)
                    else:
                        try: seg_w = font.getsize(seg_text)[0]
                        except: seg_w = len(seg_text) * 10
                    
                    if shadow:
                         # Thick Stroke / Drop Shadow
                         # User Request: Black Drop Shadow (No Zabuton)
                         stroke_width = 2
                         offsets = []
                         
                         # Stroke (Outline)
                         for dx in range(-stroke_width, stroke_width + 1):
                             for dy in range(-stroke_width, stroke_width + 1):
                                 if dx == 0 and dy == 0: continue
                                 offsets.append((dx, dy))
                         
                         # Drop Shadow (Directional)
                         shadow_depth = 6
                         for k in range(stroke_width + 1, shadow_depth + 1):
                             offsets.append((k, k))

                         for ox, oy in offsets:
                              draw.text((current_x + ox, current_y + oy), seg_text, font=font, fill="black")
                    
                    draw.text((current_x, current_y), seg_text, font=font, fill=seg_color)
                    current_x += seg_w
                
                # Safe access to line_heights
                if i < len(line_heights):
                    current_y += line_heights[i] + spacing
                else:
                    current_y += 30 + spacing # Fallback
            
            return current_y

        # --- Intro Sequence ---
        log_debug("    > Building Intro...")
        intro_text_1 = f"{uni_label}受験リスニングトレーニング"
        intro_text_2 = "スクリプトと答え、解説は概要欄を参照"
        
        # Audio for Intro (Line 1 only)
        # Use a generic intro or generate one if missing
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
            # User Request: Intro must be short (approx 3s) so Listening Section starts immediately.
            # Fixed duration to 3.0s.
            intro_duration = 3.0 
            
            def draw_intro(draw, img):
                try:
                    f_main = ImageFont.truetype(font_path_jp, 60)
                    f_sub = ImageFont.truetype(font_path_jp, 30)
                except:
                    f_main = ImageFont.load_default()
                    f_sub = ImageFont.load_default()
                    
                # Draw Main Title Centered
                draw_centered_text(draw, intro_text_1, f_main, start_y=300)
                draw_centered_text(draw, intro_text_2, f_sub, start_y=400, color=(200, 200, 255))

            intro_clip = create_bg_clip(intro_duration, draw_intro)
            intro_clip = with_audio_compat(intro_clip, ac_intro)

        # Filter segments by type to strict separation
        listening_segments = [s for s in audio_segments if s.get("type") == "listening_part"]
        questions_segments = [s for s in audio_segments if s.get("type") == "questions_part"]
        
        # --- Part 1: Main Discussion (Listening Focus) ---
        log_debug("    > Building Part 1: Listening Focus...")
        
        if not listening_segments:
            log_debug("  ! Warning: No listening_part segments found. Using all segments as fallback (deprecated).")
            listening_segments = audio_segments

        # Concatenate main audio
        audio_clips_list = []
        valid_segments = [s for s in listening_segments if os.path.exists(s["audio_path"])]
        for seg in valid_segments:
            try:
                ac = AudioFileClip(seg["audio_path"])
                resources_to_close.append(ac)
                audio_clips_list.append(ac)
            except: pass
                
        if not audio_clips_list:
            return None
        full_dialog_audio = concatenate_audioclips(audio_clips_list)
        
        # Construct Audio Sequence: [Title] -> [SE] -> [Dialog]
        part1_audio_elements = []
        
        # 1. Title Audio ("Listening Section")
        sec_list_audio_path = special_clips.get("sec_listening", "assets/listening_section.mp3")
        if not os.path.exists(sec_list_audio_path) and generate_section_audio:
             log_debug("      (Generating Listening Section Audio...)")
             sec_list_audio_path = "temp/sec_listening.mp3"
             generate_section_audio("Listening Section", sec_list_audio_path)

        if os.path.exists(sec_list_audio_path):
            ac_sec = AudioFileClip(sec_list_audio_path)
            resources_to_close.append(ac_sec)
            part1_audio_elements.append(ac_sec)
        
        # 2. SE ("Complete 4") - Play AFTER Title
        se_complete_path = special_clips.get("se_complete", "assets/完了4.mp3")
        # Fallback logic if passed path doesn't exist
        if not os.path.exists(se_complete_path):
             if os.path.exists("assets/完了4.mp3"): se_complete_path = "assets/完了4.mp3"
             elif os.path.exists("assets/パッ.mp3"): se_complete_path = "assets/パッ.mp3"
             elif os.path.exists("assets/next_word.mp3"): se_complete_path = "assets/next_word.mp3"
             
        if os.path.exists(se_complete_path):
            ac_se = AudioFileClip(se_complete_path)
            ac_se = apply_se_settings(ac_se) # User Request: Lower SE volume
            resources_to_close.append(ac_se)
            part1_audio_elements.append(ac_se)
            
        # 3. Main Dialog
        part1_audio_elements.append(full_dialog_audio)
        
        full_part1_audio = concatenate_audioclips(part1_audio_elements)
        duration_part1 = full_part1_audio.duration
        
        # Visual: Persistent "Listening Section" text
        def draw_part1(draw, img):
            try:
                f_title = ImageFont.truetype(font_path_en, 80)
            except:
                f_title = ImageFont.load_default()
                
            draw_centered_text(draw, "Listening Section", f_title)

        part1_video = create_bg_clip(duration_part1, draw_part1)
        part1_video = with_audio_compat(part1_video, full_part1_audio)
        
        # --- Part 2: Questions ---
        log_debug("    > Building Part 2: Questions...")
        part2_clips = []
        
        # Transition / Title for Questions
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
        if q_title_audio: q_trans_clips.append(q_title_audio)
        if os.path.exists(se_complete_path):
             ac_se_q = AudioFileClip(se_complete_path)
             ac_se_q = apply_se_settings(ac_se_q) # User Request: Lower SE volume
             resources_to_close.append(ac_se_q)
             q_trans_clips.append(ac_se_q)
        
        q_trans_audio = concatenate_audioclips(q_trans_clips) if q_trans_clips else None
        q_title_dur = (q_trans_audio.duration + 1.0) if q_trans_audio else 3.0
        
        def draw_q_title(draw, img):
            try: f = ImageFont.truetype(font_path_en, 80)
            except: f = ImageFont.load_default()
            draw_centered_text(draw, "Question Section", f)
            
        trans_clip = create_bg_clip(q_title_dur, draw_q_title)
        if q_trans_audio:
            trans_clip = with_audio_compat(trans_clip, q_trans_audio)
        part2_clips.append(trans_clip)

        for i, q in enumerate(questions):
            # Audio for Question
            # 1. Check if provided path exists
            # 2. If not, generate via TTS
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
                
                # Add Choice Audio (Option A, B, C, D)
                # Ensure 0.5s gap between all elements
                current_time = q_main_audio.duration + 0.5
                
                # ROBUST LOGIC: Ensure we have audio for choices
                # 1. Get text choices
                choices_text = q.get("choices", [])
                if not choices_text:
                    choices_text = q.get("options", [])
                
                # 2. Get existing paths (if any)
                existing_paths = q.get("choices_audio_paths", [])
                
                for j, choice_text in enumerate(choices_text):
                    c_path = None
                    
                    # Try using existing path
                    if j < len(existing_paths) and existing_paths[j] and os.path.exists(existing_paths[j]):
                        c_path = existing_paths[j]
                    
                    # If no valid path, generate it
                    if not c_path:
                        c_path = f"temp/q_{i+1}_c_{j+1}_{int(time.time())}.mp3"
                        if generate_section_audio:
                            # Use Student A voice (same as generate_section_audio default)
                            # Or we can import generate_audio_segment_edge if needed, but generate_section_audio works for now
                            generate_section_audio(choice_text, c_path)
                    
                    # 3. Load Clip
                    if c_path and os.path.exists(c_path):
                        try:
                            c_clip = AudioFileClip(c_path)
                            resources_to_close.append(c_clip)
                            audio_elements.append((c_clip, current_time))
                            current_time += c_clip.duration + 0.5 # Gap after option
                        except Exception as e:
                            log_debug(f"      ! Error loading choice audio {c_path}: {e}")
                
                final_q_audio = CompositeAudioClip([clip.with_start(t) for clip, t in audio_elements])
                # User Request: 3-second pause after all audio finishes
                q_dur = current_time + 3.0 
                
            else:
                final_q_audio = None
                q_dur = 10.0 # Default if no audio

            def draw_question(draw, img):
                # 1. Dynamic Font Sizing & Layout Calculation
                q_text = f"Q{i+1}: {q['question']}"
                choices = q.get("choices", [])
                
                # Calculate total characters to determine initial font size
                total_chars = len(q_text) + sum(len(c) for c in choices)
                
                # Base sizes (User Requirement 2: Dynamic Sizing)
                q_size = 50
                c_size = 40
                
                # Reduce if content is heavy (Threshold: 200 chars)
                if total_chars > 200:
                    q_size = 35
                    c_size = 30
                
                # Iterative sizing to ensure fit within safe area (User Requirement 3: Vertical Optimization)
                # Max height allowed: 720 - 60 (bottom margin) - 30 (top margin) = 630
                # Expanded safe area slightly to accommodate Option D
                max_total_height = 630
                
                # Loop to find fitting font size
                while True:
                    try:
                        q_font = ImageFont.truetype(font_path_en, q_size)
                        c_font = ImageFont.truetype(font_path_en, c_size)
                    except:
                        q_font = ImageFont.load_default()
                        c_font = ImageFont.load_default()
                        break
                        
                    # Measure Heights using 85% width (User Requirement 1: Auto-wrap at 85%)
                    # Simulating method='caption' behavior
                    max_w = 1280 * 0.85
                    
                    _, h_q, _ = get_text_layout(q_text, q_font, max_w, draw)
                    
                    h_choices = []
                    for c in choices:
                        _, h_c, _ = get_text_layout(c, c_font, max_w, draw)
                        h_choices.append(h_c)
                    
                    # Calculate Total Block Height
                    # Q + gap(40) + Choice1 + gap(15) + Choice2 ...
                    # Note: gap between Q and Choices = 40
                    # Gap between Choices = 25 (15 internal spacing + 10 extra)
                    total_h = h_q + 40 + sum(h_choices) + (25 * (len(choices) - 1))
                    
                    # Check if fits (with a small buffer)
                    if total_h <= max_total_height:
                        break
                    
                    # Stop if too small
                    if q_size <= 15:
                        break
                    
                    # Reduce sizes and retry
                    q_size = max(15, q_size - 2)
                    c_size = max(15, c_size - 2)
                
                # 2. Vertical Centering
                # Start Y = (Screen Height - Total Height) / 2
                # User Requirement 3: Center vertically
                start_y = (720 - total_h) // 2
                start_y = max(30, start_y) # Ensure at least 30px from top
                
                # 3. Draw
                current_y = start_y
                
                # Draw Question
                current_y = draw_centered_text(draw, q_text, q_font, start_y=current_y, img_w=1280)
                
                # Gap between Q and Choices
                current_y += 40
                
                # Draw Choices
                # User Requirement 4: Appropriate line spacing
                for choice in choices:
                    current_y = draw_centered_text(draw, choice, c_font, start_y=current_y, color=(200, 255, 200), spacing=15, img_w=1280)
                    current_y += 10 # Extra spacing between choices
            
            slide_clip = create_bg_clip(q_dur, draw_question)
            if final_q_audio:
                slide_clip = with_audio_compat(slide_clip, final_q_audio)
            
            part2_clips.append(slide_clip)
            
        part2_video = concatenate_videoclips(part2_clips)
        
        # --- Part 3: Review (Script + Translation) ---
        log_debug("    > Building Part 3: Review...")
        part3_clips = []
        
        # Transition
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
        if r_title_audio: r_trans_clips.append(r_title_audio)
        if os.path.exists(se_complete_path):
             ac_se_r = AudioFileClip(se_complete_path)
             ac_se_r = apply_se_settings(ac_se_r) # User Request: Lower SE volume
             resources_to_close.append(ac_se_r)
             r_trans_clips.append(ac_se_r)
             
        r_trans_audio = concatenate_audioclips(r_trans_clips) if r_trans_clips else None
        r_title_dur = (r_trans_audio.duration + 1.0) if r_trans_audio else 3.0
        
        def draw_r_title(draw, img):
            try: f = ImageFont.truetype(font_path_en, 80)
            except: f = ImageFont.load_default()
            draw_centered_text(draw, "Review Section", f)
            
        trans_clip3 = create_bg_clip(r_title_dur, draw_r_title)
        if r_trans_audio:
            trans_clip3 = with_audio_compat(trans_clip3, r_trans_audio)
            
        part3_clips.append(trans_clip3)
        
        # Re-use audio segments (Listening Part ONLY)
        # Use listening_segments defined at start
        valid_review_segments = [s for s in listening_segments if os.path.exists(s["audio_path"])]
        
        for seg in valid_review_segments:
            seg_dur = seg["duration"]
            if seg_dur <= 0: continue
            
            try:
                ac = AudioFileClip(seg["audio_path"])
                resources_to_close.append(ac)
            except: continue
            
            def draw_script(draw, img):
                # Text Retrieval with Fallbacks
                speaker = seg.get("speaker")
                en_text = seg.get("text") or seg.get("content") or seg.get("dialog")
                jp_text = seg.get("japanese") or seg.get("translation")

                # Try extracting from 'lines' if missing (Common in Production Pipeline)
                if (not speaker or not en_text) and seg.get("lines") and len(seg["lines"]) > 0:
                    first_line = seg["lines"][0]
                    if not speaker: speaker = first_line.get("speaker")
                    if not en_text: en_text = first_line.get("text")
                    if not jp_text: jp_text = first_line.get("translation") or first_line.get("japanese")

                if not speaker or speaker == "Unknown":
                    # Simple fallback logic
                    speaker = "Student A" 

                if not en_text: en_text = ""
                if not jp_text: jp_text = ""
                
                # Helper to add brackets around target words (preserving case)
                # DEPRECATED: User requested RED highlight instead of brackets.
                # Keeping raw text.
                en_text_display = en_text
                
                try:
                    s_font = ImageFont.truetype(font_path_en, 40)
                    e_font = ImageFont.truetype(font_path_en, 35)
                    j_font = ImageFont.truetype(font_path_jp, 35)
                except:
                    s_font = ImageFont.load_default()
                    e_font = ImageFont.load_default()
                    j_font = ImageFont.load_default()
                    
                # Draw Speaker (Disabled by User Request)
                # y = draw_centered_text(draw, f"[{speaker}]", s_font, start_y=100, color="yellow")
                y = 100 # Default start Y

                # Draw EN (Centered, English Only - User Request)
                # Maximize visibility: Center Vertically & Horizontally, Large Font
                
                # 1. Determine optimal font size
                max_width = 1280 * 0.85
                max_height = 600 # Leave some margin (720 - 120)
                initial_size = 65 # Max size for 720p (approx 90-100px on 1080p)
                min_size = 30
                
                # Use a dummy image/draw for measurement if needed, but get_fitted_font uses 'draw'
                # We can pass the current 'draw' object.
                e_font = get_fitted_font(draw, en_text_display, font_path_en, max_width, max_height, initial_size, min_size)

                # 2. Draw Centered (start_y=None triggers vertical centering)
                # Color: White for max contrast against black background
                # CRITICAL FIX: Pass highlight_words_en to enable RED highlighting
                draw_centered_text(draw, en_text_display, e_font, start_y=None, color="white", highlight_words=highlight_words_en)
                
                # Draw JP (Disabled by User Request)
                # ...
            
            clip = create_bg_clip(seg_dur, draw_script)
            clip = with_audio_compat(clip, ac)
            part3_clips.append(clip)
            
        part3_video = concatenate_videoclips(part3_clips)
        
        # --- Final Assembly ---
        log_debug("    > Assembling Final Video (Sandwich Format: Listening -> Questions -> Review -> Questions)...")
        final_clips_list = []
        if intro_clip: final_clips_list.append(intro_clip)
        
        # 1. Listening
        final_clips_list.append(part1_video)
        
        # 2. Questions
        final_clips_list.append(part2_video)
        
        # 3. Review
        final_clips_list.append(part3_video)
        
        # 4. Final Questions (Repeat Part 2)
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
        
        # Calculate timestamps for Description
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
        log_debug(f"CRITICAL ERROR in generate_todai_video: {e}")
        traceback.print_exc()
        raise e # Re-raise to be caught by caller if needed
    finally:
        log_debug("DEBUG: Cleaning up audio resources...")
        for res in resources_to_close:
            try: res.close()
            except: pass

# ... (Rest of file unchanged, assuming create_section_overlay and others are below)
# Wait, I need to make sure I don't overwrite the rest of the file.
# The Read output showed line 858 was generate_word_audio_video.
# So I should stop before that.
# I'll just write the entire top part of the file up to generate_todai_video end.
# I need to be careful to include 'format_time_mm_ss' and 'create_section_overlay' if they were used in generate_todai_video?
# 'create_section_overlay' is NOT used in generate_todai_video (it uses create_bg_clip).
# 'format_time_mm_ss' is NOT used.
# So I can just replace everything up to the end of generate_todai_video.
# I'll use SearchReplace to replace the entire function.
