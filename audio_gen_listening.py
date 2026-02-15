import os
import tempfile
import time
from typing import List, Dict
import numpy as np
import subprocess
import asyncio
import edge_tts
from gtts import gTTS

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from moviepy import AudioFileClip, concatenate_audioclips, AudioClip
except ImportError:
    from moviepy.editor import AudioFileClip, concatenate_audioclips, AudioClip

# Constants
VOICE_EN = "onyx"
VOICE_JP = "shimmer" # or alloy
MODEL_TTS = "tts-1"
PAUSE_DURATION = 1.5 # seconds between steps

# Edge-TTS Voices
EDGE_VOICE_MALE = "en-US-ChristopherNeural"
EDGE_VOICE_FEMALE = "en-US-AriaNeural"
EDGE_VOICE_JP = "ja-JP-NanamiNeural"

async def _generate_edge_tts_async(text, voice, output_path, rate_str):
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(output_path)

def generate_audio_segment_gtts(text: str, output_path: str, lang: str = 'en') -> bool:
    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(output_path)
        return True
    except Exception as e:
        print(f"      ! gTTS Fallback Error: {e}")
        return False

def generate_audio_segment_edge(text: str, voice: str, output_path: str, speed: float = 1.0) -> bool:
    """
    Edge-TTSを使用して音声ファイルを生成する。
    pythonライブラリの edge_tts を使用し、失敗時は gTTS にフォールバックする。
    """
    try:
        # Calculate rate string
        rate_str = "+0%"
        if speed != 1.0:
            # 0.8 -> -20%, 1.2 -> +20%
            diff_pct = int((speed - 1.0) * 100)
            sign = "+" if diff_pct >= 0 else "-"
            rate_str = f"{sign}{abs(diff_pct)}%"

        # Use library directly with asyncio
        # Check if loop exists (for safety in some envs)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use asyncio.run(). 
                # But in this app context, we likely don't have a running loop in the main thread 
                # where this is called, unless Streamlit does something.
                # If we are here, we might need nest_asyncio or similar, but let's try standard approach.
                # Actually, creating a new task might be better if async.
                # But this function is synchronous.
                # If loop is running, we might need to use loop.run_until_complete, but that fails if loop is running.
                # For now, let's assume standard script execution.
                # If Error "This event loop is already running", we need another strategy.
                pass
        except RuntimeError:
            pass # No loop

        asyncio.run(_generate_edge_tts_async(text, voice, output_path, rate_str))
        return True
    except Exception as e:
        print(f"      ! Edge-TTS Library Error: {e}")
        print("      Switching to gTTS fallback...")
        
        # Determine language from voice
        lang = 'ja' if "ja-JP" in voice else 'en'
        return generate_audio_segment_gtts(text, output_path, lang)

def generate_tts_segment(client, text: str, voice: str, speed: float = 1.0) -> bytes:
    try:
        response = client.audio.speech.create(
            model=MODEL_TTS,
            voice=voice,
            input=text,
            speed=speed
        )
        return response.content
    except Exception as e:
        print(f"Error generating TTS: {e}")
        return None

def generate_intro_audio(text: str, output_path: str) -> bool:
    """
    Generate intro audio using Japanese voice.
    """
    return generate_audio_segment_edge(text, EDGE_VOICE_JP, output_path)

def generate_section_audio(text: str, output_path: str) -> bool:
    """
    Generate section title audio using English voice.
    """
    return generate_audio_segment_edge(text, EDGE_VOICE_MALE, output_path)

def make_silence(duration):
    try:
        def make_frame(t):
            if np.isscalar(t):
                return np.array([0.0, 0.0])
            else:
                return np.zeros((len(t), 2))
        return AudioClip(make_frame, duration=duration, fps=44100)
    except Exception:
        return None

def generate_listening_audio(words_data: List[Dict], output_file: str = "listening_audio.mp3", step_config: List[Dict] = None) -> Dict:
    """
    単語リストから聞き流し用音声を生成する。
    step_config: [
        {"type": "en", "label": "Example (Normal)", "speed": 1.0, "repeat": 1},
        ...
    ]
    """
    # Mode Check
    layout_check_mode = os.environ.get("LAYOUT_CHECK_MODE", "false").lower() == "true"
    test_mode = os.environ.get("TEST_MODE", "false").lower() == "true"
    
    mode = "prod"
    if layout_check_mode: mode = "layout"
    elif test_mode: mode = "test"

    print(f"Generating listening audio... (Mode: {mode})")

    client = None
    if mode == "prod":
        api_key = os.environ.get("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key) if (OpenAI and api_key) else None
        
        if not client:
            print("OpenAI API key missing. Cannot generate audio in prod mode.")
            return None
    
    # Default config if not provided
    if not step_config:
        step_config = [
            {"type": "en", "label": "English (Normal)", "speed": 1.0, "repeat": 1},
            {"type": "jp", "label": "Japanese", "speed": 1.0, "repeat": 1},
            {"type": "en", "label": "English (Slow 0.8x)", "speed": 0.8, "repeat": 1}
        ]

    final_clips = []
    segments_info = [] # { "text": "...", "start": 0.0, "end": 0.0, "type": "en"|"jp", "label": "..." }
    
    current_time = 0.0
    
    print(f"Generating listening audio for {len(words_data)} words...")
    
    # Ensure temp root exists
    if not os.path.exists("temp"):
        os.makedirs("temp")

    with tempfile.TemporaryDirectory(dir="temp") as temp_dir:
        for i, item in enumerate(words_data):
            word_id = item["id"]
            print(f"  - Processing No.{word_id}...")
            
            # Process each configured step
            for step_idx, step in enumerate(step_config):
                stype = step.get("type", "en") # "en" or "jp"
                speed = step.get("speed", 1.0)
                repeat = step.get("repeat", 1)
                label = step.get("label", "")
                
                text = item["example_en"] if stype == "en" else item["example_jp"]
                
                # Determine voice/engine based on mode
                audio_bin = None
                generated_file_path = None
                
                if mode == "layout":
                    # Dummy logic
                    # Calculate dummy duration: 5 chars / sec
                    char_count = len(text)
                    dur = max(1.0, char_count / 5.0)
                    silence = make_silence(dur)
                    
                    base_filename = f"{word_id}_step{step_idx}_{stype}_layout.mp3"
                    path = os.path.join(temp_dir, base_filename)
                    # We need a file for AudioFileClip
                    silence.write_audiofile(path, fps=44100, logger=None)
                    generated_file_path = path
                    
                elif mode == "test":
                    # Edge-TTS
                    voice = EDGE_VOICE_MALE if stype == "en" else EDGE_VOICE_JP
                    base_filename = f"{word_id}_step{step_idx}_{stype}_edge.mp3"
                    path = os.path.join(temp_dir, base_filename)
                    
                    if generate_audio_segment_edge(text, voice, path, speed=speed):
                        generated_file_path = path
                        
                else: # prod
                    voice = VOICE_EN if stype == "en" else VOICE_JP
                    # OpenAI TTS
                    audio_bin = generate_tts_segment(client, text, voice, speed=speed)
                    if audio_bin:
                        base_filename = f"{word_id}_step{step_idx}_{stype}.mp3"
                        path = os.path.join(temp_dir, base_filename)
                        with open(path, "wb") as f: f.write(audio_bin)
                        generated_file_path = path
                
                if generated_file_path and os.path.exists(generated_file_path):
                    # Repeat logic
                    for r in range(repeat):
                        clip = AudioFileClip(generated_file_path)
                        final_clips.append(clip)
                        
                        segments_info.append({
                            "id": word_id,
                            "word": item["word"],
                            "text": text,
                            "type": stype, # "en" or "jp"
                            "label": label,
                            "start": current_time,
                            "end": current_time + clip.duration
                        })
                        current_time += clip.duration
                        
                        # Short Pause between repetitions or steps
                        pause_dur = 0.5
                        silence = make_silence(pause_dur)
                        final_clips.append(silence)
                        current_time += pause_dur

            # Pause between words (Longer)
            silence_long = make_silence(PAUSE_DURATION)
            final_clips.append(silence_long)
            current_time += PAUSE_DURATION
            
        # Combine all
            
        # Combine all
        if final_clips:
            print("  Merging audio clips...")
            final_audio = concatenate_audioclips(final_clips)
            final_audio.write_audiofile(output_file, fps=44100, logger=None)
            
            # Close clips
            for c in final_clips:
                try: c.close()
                except: pass
                
            return {
                "audio_path": output_file,
                "segments": segments_info,
                "duration": current_time
            }
        else:
            return None

if __name__ == "__main__":
    # Test
    from dotenv import load_dotenv
    load_dotenv()
    test_data = [
        {"id": 1, "example_en": "This is a test sentence.", "example_jp": "これはテストの文です。"},
        {"id": 2, "example_en": "I love programming.", "example_jp": "私はプログラミングが大好きです。"}
    ]
    res = generate_listening_audio(test_data, "test_listening.mp3")
    print(res)
