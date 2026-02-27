import os
import re
import io
import tempfile
import numpy as np
import random
import requests
import json
import subprocess
from typing import List, Dict

# 必要なライブラリのインポート
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    # moviepy v2.0対応
    from moviepy import AudioFileClip, concatenate_audioclips, AudioClip, CompositeAudioClip
except ImportError:
    try:
        # moviepy v1.0互換
        from moviepy.editor import AudioFileClip, concatenate_audioclips, AudioClip, CompositeAudioClip
    except ImportError:
        AudioFileClip = None
        AudioClip = None
        concatenate_audioclips = None
        print("Warning: moviepy is not installed. Audio merging will not work properly.")

# 定数設定
# OpenAI Voices
OPENAI_VOICE_MALE = "onyx"
OPENAI_VOICE_FEMALE = "shimmer" 
OPENAI_VOICE_GUEST = "alloy" # 3rd speaker
MODEL_TTS = "tts-1"

# ElevenLabs Voices (Default IDs - Change if needed)
ELEVENLABS_VOICE_MALE = "pNInz6obpgDQGcFmaJgB" # Adam
ELEVENLABS_VOICE_FEMALE = "21m00Tcm4TlvDq8ikWAM" # Rachel
ELEVENLABS_VOICE_GUEST = "TxGEqnHWrfWFTfGW9XjX" # Josh (Example ID, replace with actual if needed)
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

PAUSE_DURATION = 0.5 

# Edge-TTS Voices
EDGE_VOICE_MALE = "en-US-ChristopherNeural"
EDGE_VOICE_FEMALE = "en-US-EmmaNeural"
EDGE_VOICE_GUEST = "en-US-GuyNeural" # Professor
EDGE_VOICE_NARRATOR = "en-US-AvaNeural" # Exam Narrator (Clear, professional)

# Gap Constants for Word Audio Mode (Defaults)
GAP_ENG_TO_JAP = 0.5
GAP_BETWEEN_JAP = 1.2
GAP_NEXT_WORD = 1.3

def generate_audio_segment_openai(client, text: str, voice: str, model: str) -> bytes:
    """
    OpenAI APIを使用して音声セグメントを生成し、バイナリデータとして返す。
    """
    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text
        )
        return response.content
    except Exception as e:
        print(f"      ! OpenAI TTS Error: {e}")
        return None

def generate_audio_segment_elevenlabs(text: str, voice_id: str, api_key: str) -> bytes:
    """
    ElevenLabs APIを使用して音声セグメントを生成する。
    """
    if not api_key:
        return None
        
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }
    
    try:
        url = ELEVENLABS_API_URL.format(voice_id=voice_id)
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            return response.content
        else:
            print(f"      ! ElevenLabs Error ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"      ! ElevenLabs Exception: {e}")
        return None

def generate_audio_segment_edge(text: str, voice: str, output_path: str, speed: float = 1.0) -> bool:
    """
    Edge-TTSを使用して音声ファイルを生成する。
    """
    try:
        # Calculate rate string
        rate_str = "+0%"
        if speed != 1.0:
            # 0.8 -> -20%, 1.2 -> +20%
            diff_pct = int((speed - 1.0) * 100)
            sign = "+" if diff_pct >= 0 else "-"
            rate_str = f"{sign}{abs(diff_pct)}%"

        cmd = [
            "py", "-m", "edge_tts", # Use python module call instead of direct executable
            "--text", text,
            "--write-media", output_path,
            "--voice", voice,
            "--rate", rate_str
        ]
        
        # Windowsのsubprocessで実行する際、コンソールウィンドウが出ないようにする設定
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        subprocess.run(cmd, check=True, startupinfo=startupinfo, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"      ! Edge-TTS Error: {e}")
        return False
    except Exception as e:
        print(f"      ! Edge-TTS Exception: {e}")
        return False

def change_speed_ffmpeg(input_path: str, output_path: str, speed: float) -> bool:
    """
    ffmpegを使用して音声の速度を変更する (ピッチは維持)
    atempoフィルタを使用 (0.5 <= speed <= 2.0)
    """
    try:
        # ffmpeg -i input.mp3 -filter:a "atempo=0.8" -vn output.mp3
        cmd = [
            "ffmpeg",
            "-y", # Overwrite
            "-i", input_path,
            "-filter:a", f"atempo={speed}",
            "-ar", "44100", # Force 44.1kHz to fix pitch issues
            "-vn",
            output_path
        ]
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        subprocess.run(cmd, check=True, startupinfo=startupinfo, capture_output=True)
        return True
    except Exception as e:
        print(f"      ! Speed change error: {e}")
        return False

def get_backchannel_audio(client, speaker_gender: str, cache_dir: str = "assets/backchannels", mode: str = "prod") -> str:
    """
    相槌音声を返す（キャッシュにあればそれを、なければ生成）。
    """
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        
    words = ["Uh-huh", "I see", "Right", "Yeah", "Hmm"]
    word = random.choice(words)
    
    # ファイル名: gender_word.mp3
    filename = f"{speaker_gender}_{word}.mp3"
    filepath = os.path.join(cache_dir, filename)
    
    if os.path.exists(filepath):
        return filepath
        
    # 生成 (Layout Check Modeのときは生成しない、Test ModeのときはEdgeTTSで生成してもいいが、既存のOpenAI製があればそれを使う)
    if mode == "layout":
        return None # Layout checkでは相槌不要または無音で代用
        
    # 生成
    voice = OPENAI_VOICE_MALE if speaker_gender == "Male" else OPENAI_VOICE_FEMALE
    if client and mode == "prod":
        print(f"    + Generating backchannel: {word} ({speaker_gender})")
        audio_data = generate_audio_segment_openai(client, word, voice, MODEL_TTS)
        if audio_data:
            with open(filepath, "wb") as f:
                f.write(audio_data)
            return filepath
    
    # TEST_MODEでEdgeTTSを使って生成するロジックも追加可能だが、キャッシュがあればそれを使うのが基本
    # キャッシュがない場合は一旦スキップ（複雑化を防ぐため）
    return None

def parse_dialogue(text: str) -> List[Dict[str, str]]:
    """
    (Legacy) テキストを解析して、話者とセリフのリストに変換する。
    """
    pattern = r'\[(Male|Female) Speaker\]:\s*(.*?)(?=\[(?:Male|Female) Speaker\]:|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    dialogue_list = []
    if not matches:
        return [{"speaker": "Male", "text": text.strip()}]
        
    for speaker_type, content in matches:
        clean_text = content.strip()
        if clean_text:
            dialogue_list.append({
                "speaker": speaker_type, 
                "text": clean_text
            })
    return dialogue_list

def generate_audio_sections(script_data: dict, output_dir: str = None) -> List[Dict]:
    """
    Generate audio files for each section of the script.
    """
    if output_dir is None:
        output_dir = os.path.join("temp", "temp_audio_sections")
    print(f"セクション別音声生成開始: 出力先 '{output_dir}'")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # モードの確認
    layout_check_mode = os.environ.get("LAYOUT_CHECK_MODE", "false").lower() == "true"
    test_mode = os.environ.get("TEST_MODE", "false").lower() == "true"
    
    mode = "prod"
    if layout_check_mode: mode = "layout"
    elif test_mode: mode = "test"
    
    print(f"  - Execution Mode: {mode.upper()}")

    # API Keys
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
    use_elevenlabs = os.environ.get("USE_ELEVENLABS", "true").lower() == "true"
    
    client = None
    if OpenAI and openai_api_key:
        client = OpenAI(api_key=openai_api_key)
    
    # API Key Checks for Prod Mode
    if mode == "prod":
        if not openai_api_key:
            print("  ! Warning: OPENAI_API_KEY is missing. OpenAI TTS will fail.")
        if use_elevenlabs and not elevenlabs_api_key:
            print("  ! Warning: ELEVENLABS_API_KEY is missing but USE_ELEVENLABS is true.")

    # 共通の無音クリップ生成関数
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

    sections = script_data.get("sections", [])
    results = []

    for i, section in enumerate(sections):
        section_type = section.get("type", "unknown")
        print(f"  - Section {i+1}/{len(sections)} ({section_type}) 処理中...")
        
        section_clips = []
        temp_files_to_clean = []
        line_timings = []
        current_section_time = 0.0
        
        # データの取得（新形式 vs 旧形式）
        lines = section.get("lines", [])
        if not lines:
            # 旧形式（parse_dialogue利用）
            content = section.get("content", "")
            parsed = parse_dialogue(content)
            # lines形式に変換して統一的に扱う
            lines = []
            for p in parsed:
                lines.append({
                    "speaker": "James" if p["speaker"] == "Male" else "Emily",
                    "text": p["text"],
                    "type": "dialogue", # Default
                    "emotion": "neutral"
                })
        
        # セクション内の一時ディレクトリ
        # Ensure temp root exists
        if not os.path.exists("temp"):
            os.makedirs("temp")

        with tempfile.TemporaryDirectory(dir="temp") as temp_dir:
            if not lines:
                print(f"    ! Warning: Section {i+1} has no lines to process.")

            for j, line in enumerate(lines):
                speaker = line.get("speaker", "James")
                text = line.get("text", "")
                
                if not text or not text.strip():
                    print(f"      [{j+1}/{len(lines)}] Warning: Empty text for speaker {speaker}. Skipping.")
                    continue

                line_type = line.get("type", "dialogue")
                emotion = line.get("emotion", "neutral")
                speed = line.get("speed", 1.0)
                display_info = line.get("display", None)
                
                # 話者判定 (Alex/James -> Male, Mia/Emily -> Female, Guest/Professor -> Guest)
                is_male = (speaker in ["James", "Male", "Alex", "Student A"])
                is_guest = (speaker in ["Guest", "Professor", "Lecturer"])
                is_female = not (is_male or is_guest)
                
                # OSAKA MODE SPEED ADJUSTMENT
                university = script_data.get("university", "todai")
                if university == "osaka" and speaker in ["Student B", "Sarah", "Professor"]:
                    speed = 1.05
                    print(f"      [{j+1}/{len(lines)}] Osaka Speed Boost ({speaker}): x{speed}")
                
                temp_path = os.path.join(temp_dir, f"s{i}_l{j}.mp3")
                generated_clip = None
                
                # --- モード別処理 ---
                # Force Edge-TTS for Todai/Kyoto/Osaka speakers
                is_todai_speaker = speaker in ["Student A", "Student B", "Professor", "Narrator", "Dr. Smith", "Andrew", "Sarah"]
                
                if mode == "layout":
                    # 文字数から長さを計算 (5文字/秒)
                    char_count = len(text)
                    calc_duration = max(1.0, char_count / 5.0)
                    if speed != 1.0:
                        calc_duration = calc_duration / speed
                    print(f"      [{j+1}/{len(lines)}] Layout Mock ({speaker}): {char_count} chars -> {calc_duration:.2f}s (Speed: {speed})")
                    
                    silence_clip = make_silence(calc_duration)
                    if silence_clip:
                        # ファイルとして保存する必要がある (AudioFileClipで読み込むため)
                        silence_clip.write_audiofile(temp_path, fps=44100, logger=None)
                        generated_clip = AudioFileClip(temp_path)
                        
                elif mode == "test" or is_todai_speaker:
                    # Edge-TTSを使用 (Test Mode OR Todai Speakers)
                    # Strict mapping for Todai speakers
                    if speaker == "Student A":
                        voice = EDGE_VOICE_MALE
                    elif speaker in ["Student B", "Sarah"]:
                        voice = EDGE_VOICE_FEMALE
                    elif speaker == "Professor":
                        voice = EDGE_VOICE_GUEST
                    elif speaker in ["Dr. Smith", "Andrew"]:
                        voice = EDGE_VOICE_GUEST # Use Professor voice for Kyoto lecturer
                    elif speaker == "Narrator":
                        voice = EDGE_VOICE_NARRATOR
                        speed = 1.05 # Force +5% speed for Narrator
                    # Fallback/Other logic
                    elif is_guest:
                        voice = EDGE_VOICE_GUEST
                    elif is_male:
                        voice = EDGE_VOICE_MALE
                    else:
                        voice = EDGE_VOICE_FEMALE
                        
                    print(f"      [{j+1}/{len(lines)}] Edge-TTS ({speaker}): {text[:30]}... (Voice: {voice})")
                    if generate_audio_segment_edge(text, voice, temp_path, speed=speed):
                        try:
                            generated_clip = AudioFileClip(temp_path)
                            # Edge-TTS側で速度調整済みなので、後続のffmpeg処理をスキップさせるためにspeedをリセット
                            # ただし、後続処理は speed != 1.0 をチェックしているので、ここで一時的に変数を上書きするアプローチが必要
                            # 変数 speed 自体はこのループスコープなので上書きしても次のイテレーションには影響しない
                            speed = 1.0 
                        except Exception as e:
                            print(f"      ! Error loading Edge-TTS clip: {e}")
                    else:
                        print(f"      ! Failed to generate Edge-TTS audio")
                
                else: # prod (OpenAI / ElevenLabs)
                    # 音声生成エンジンの選択
                    audio_binary = None
                    used_engine = "OpenAI"
                    
                    # Story/Dialogue かつ ElevenLabsキーがある場合はElevenLabsを使用
                    if (line_type in ["story", "dialogue"]) and elevenlabs_api_key and use_elevenlabs:
                        if is_guest:
                            voice_id = ELEVENLABS_VOICE_GUEST
                        elif is_male:
                            voice_id = ELEVENLABS_VOICE_MALE
                        else:
                            voice_id = ELEVENLABS_VOICE_FEMALE
                            
                        print(f"      [{j+1}/{len(lines)}] ElevenLabs ({speaker}): {text[:30]}...")
                        audio_binary = generate_audio_segment_elevenlabs(text, voice_id, elevenlabs_api_key)
                        if audio_binary:
                            used_engine = "ElevenLabs"
                    
                    # フォールバック または Explanation は OpenAI
                    if not audio_binary:
                        if client:
                            if is_guest:
                                voice = OPENAI_VOICE_GUEST
                            elif is_male:
                                voice = OPENAI_VOICE_MALE
                            else:
                                voice = OPENAI_VOICE_FEMALE
                                
                            print(f"      [{j+1}/{len(lines)}] OpenAI ({speaker}): {text[:30]}...")
                            audio_binary = generate_audio_segment_openai(client, text, voice, MODEL_TTS)
                        else:
                            print(f"      ! Error: OpenAI client is not available. Cannot generate audio for '{text[:20]}...'")
                    
                    if audio_binary:
                        with open(temp_path, "wb") as f:
                            f.write(audio_binary)
                    else:
                        print(f"      ! Error: Failed to generate audio binary (Both ElevenLabs and OpenAI failed or skipped). Text: {text[:50]}...")

                # Post-processing (Speed & Loading) for non-layout modes
                if mode != "layout":
                    if os.path.exists(temp_path):
                        # Apply Speed
                        if speed != 1.0:
                            processed_path = temp_path.replace(".mp3", f"_s{speed}.mp3")
                            print(f"      ... Applying speed {speed}x")
                            if change_speed_ffmpeg(temp_path, processed_path, speed):
                                temp_path = processed_path
                        
                        try:
                            generated_clip = AudioFileClip(temp_path)
                            
                            # IMPORTANT: Close the file handle if we are not keeping this clip immediately open in a way that locks it?
                            # Actually, AudioFileClip keeps file open.
                            # We are appending generated_clip to section_clips.
                            # BUT temp_dir is cleaned up at end of with block.
                            # If AudioFileClip holds a handle, cleanup fails on Windows.
                            # Solution: We must copy the audio data or ensure close() is called before cleanup.
                            # However, we need these clips for concatenate_audioclips later in the loop.
                            # The concatenation happens INSIDE the with block.
                            # So the clips are used, then closed.
                            # Wait, where are they closed?
                            # lines 499-500 close them.
                            # BUT, if an exception happens or logic flow is tricky, they might stay open.
                            # Also, generated_clip is created here.
                            
                        except Exception as e:
                            print(f"      ! Error loading clip: {e}")
                            if generated_clip:
                                try: generated_clip.close()
                                except: pass
                            generated_clip = None

                # --- クリップ処理とメタデータ ---
                if generated_clip:
                    section_clips.append(generated_clip)
                    
                    # Timing update for line
                    line_start = current_section_time
                    line_duration = generated_clip.duration
                    line_end = line_start + line_duration
                    current_section_time = line_end
                    
                    line_timings.append({
                        "text": text,
                        "speaker": speaker,
                        "type": line_type,
                        "emotion": emotion,
                        "display": display_info,
                        "start": line_start,
                        "end": line_end
                    })
                else:
                    print(f"      ! Critical Error: Failed to create audio clip for line {j+1}. Text: {text[:30]}...")
                    
                    # ポーズ (感情や文脈によって変えるのもありだが固定)
                    pause_dur = PAUSE_DURATION
                    if line_type == "story":
                        pause_dur = 0.8 # 物語は少し余韻を持たせる
                        
                    # 相槌 (Backchannel) の挿入判定
                    # Layout Check Modeではスキップ
                    inserted_backchannel = False
                    if mode != "layout" and random.random() < 0.2 and line_type == "dialogue":
                        other_gender = "Female" if is_male else "Male"
                        bc_path = get_backchannel_audio(client, other_gender, mode=mode)
                        if bc_path:
                            try:
                                # Pydubで音量調整 (MoviePyエラー回避)
                                try:
                                    from pydub import AudioSegment
                                    bc_seg = AudioSegment.from_file(bc_path)
                                    bc_seg = bc_seg - 6 # -6dB approx 0.5
                                    
                                    # Unique temp file
                                    fd, temp_bc_path = tempfile.mkstemp(suffix=".mp3")
                                    os.close(fd)
                                    bc_seg.export(temp_bc_path, format="mp3")
                                    temp_files_to_clean.append(temp_bc_path)
                                    
                                    bc_clip = AudioFileClip(temp_bc_path)
                                except Exception as e:
                                    print(f"      ! Pydub failed for backchannel: {e}")
                                    bc_clip = AudioFileClip(bc_path) # Fallback
                                
                                # 0.5s - 1.0s のランダムな無音時間
                                gap_duration = random.uniform(0.5, 1.0)
                                silence_base = make_silence(gap_duration)
                                
                                if silence_base:
                                    # 無音の中に相槌をミックス
                                    # 開始位置は少し遅らせる (例: 0.1s後)
                                    bc_start = 0.1
                                    # 相槌が長すぎる場合はクリップ自体を伸ばす必要はない
                                    if bc_start + bc_clip.duration > gap_duration:
                                        gap_duration = bc_start + bc_clip.duration + 0.1
                                        silence_base = make_silence(gap_duration)

                                    # CompositeAudioClipで合成
                                    if hasattr(bc_clip, "with_start"):
                                        bc_clip_positioned = bc_clip.with_start(bc_start)
                                    else:
                                        bc_clip_positioned = bc_clip.set_start(bc_start)
                                        
                                    gap_clip = CompositeAudioClip([silence_base, bc_clip_positioned])
                                    
                                    section_clips.append(gap_clip)
                                    inserted_backchannel = True
                                    
                            except Exception as e:
                                print(f"    ! Backchannel error: {e}")
                    
                    if not inserted_backchannel:
                        silence = make_silence(pause_dur)
                        if silence:
                            section_clips.append(silence)
            
            university_all = script_data.get("university")
            if university_all == "todai":
                extra_pause = make_silence(0.8)
                if extra_pause:
                    section_clips.append(extra_pause)
                    current_section_time += 0.8
            
            # セクション結合と保存
            if section_clips:
                final_section_clip = None
                try:
                    final_section_clip = concatenate_audioclips(section_clips)
                    output_filename = f"section_{i}_{section_type}.mp3"
                    output_path = os.path.join(output_dir, output_filename)
                    
                    final_section_clip.write_audiofile(output_path, fps=44100, logger=None)
                    duration = final_section_clip.duration
                    
                    results.append({
                        "path": output_path,
                        "audio_path": output_path, # Added for compatibility with video_gen
                        "type": section_type,
                        "duration": duration,
                        "lines": lines, # 後続の字幕生成で使うために保持
                        "line_timings": line_timings
                    })
                except Exception as e:
                    print(f"    ! Section merge error: {e}")
                finally:
                    # Close composite clip
                    if final_section_clip:
                        try: final_section_clip.close()
                        except: pass
                        del final_section_clip
                        
                    # Close individual clips
                    for clip in section_clips:
                        try: clip.close()
                        except: pass
                    section_clips = [] # Clear list
                    
                    # Force garbage collection
                    import gc
                    gc.collect()
                        
                    # Cleanup temp files
                    for tp in temp_files_to_clean:
                        try:
                            if os.path.exists(tp):
                                os.remove(tp)
                        except: pass
            else:
                print(f"    ! Warning: No audio generated for section {i}")

    if not results:
        print("  ! Error: generate_audio_sections finished with empty results.")
        
    return results

def generate_word_audio(script_data: Dict, submode: str, output_dir: str = "output_audio_word", 
                        gap_eng_to_jap: float = GAP_ENG_TO_JAP, 
                        gap_between_jap: float = GAP_BETWEEN_JAP, 
                        gap_next_word: float = GAP_NEXT_WORD) -> List[Dict]:
    """
    Generate audio for Word Audio Mode with precise timing.
    Timing:
      - EN -> JP: gap_eng_to_jap
      - JP -> JP: gap_between_jap
      - Word End -> Next: gap_next_word
    """
    print(f"--- Generating Word Audio (Submode: {submode}, Gaps: {gap_eng_to_jap}/{gap_between_jap}/{gap_next_word}) ---")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    results = []
    words = script_data.get("words", [])
    
    # Voices: Calm Male
    VOICE_EN = "en-US-ChristopherNeural"
    VOICE_JP = "ja-JP-KeitaNeural"
    
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

    # Ensure temp root exists
    if not os.path.exists("temp"):
        os.makedirs("temp")

    with tempfile.TemporaryDirectory(dir="temp") as temp_dir:
        for i, word_item in enumerate(words):
            print(f"  - Processing Word {i+1}/{len(words)}: {word_item['word']}")
            
            word_text = word_item["word"]
            meaning_text = word_item["meaning"]
            
            # Split meanings for precise timing
            # User requested split by "、"
            if "、" in meaning_text:
                parts = meaning_text.split("、")
            else:
                # Fallback to existing logic or treat as single
                # But user said "Example: meaning_list = original_text.split('、')"
                # If no comma, it becomes a list of 1 element automatically by split?
                # Actually str.split("、") returns [text] if "、" not found.
                parts = meaning_text.split("、")
                
            clean_parts = [p.strip() for p in parts if p.strip()]
            if not clean_parts:
                clean_parts = [meaning_text]
            
            clips_to_concat = []
            current_seq_metadata = []
            
            # Helper to generate clip
            def get_clip(text, voice, label):
                fname = f"w{i}_{label}_{random.randint(0,9999)}.mp3"
                fpath = os.path.join(temp_dir, fname)
                if generate_audio_segment_edge(text, voice, fpath):
                    try:
                        c = AudioFileClip(fpath)
                        # Apply slight boost
                        if hasattr(c, "volumex"): c = c.volumex(1.1)
                        elif hasattr(c, "with_volume_scaled"): c = c.with_volume_scaled(1.1)
                        return c
                    except:
                        return None
                return None

            # --- Sequence Logic ---
            
            if submode == "en_jp":
                # 1. EN
                c = get_clip(word_text, VOICE_EN, "en")
                if c:
                    clips_to_concat.append(c)
                    current_seq_metadata.append({"label": "en", "duration": c.duration, "type": "content", "text": word_text})
                
                # 2. JP Parts
                if clean_parts:
                    # Initial Gap
                    gap = make_silence(gap_eng_to_jap)
                    clips_to_concat.append(gap)
                    current_seq_metadata.append({"label": "gap", "duration": gap_eng_to_jap, "type": "pause"})
                    
                    for idx, part_text in enumerate(clean_parts):
                        if idx > 0:
                            # Gap between JPs
                            gap = make_silence(gap_between_jap)
                            clips_to_concat.append(gap)
                            current_seq_metadata.append({"label": "gap", "duration": gap_between_jap, "type": "pause"})
                        
                        # TTS text should NOT contain numbers (as requested)
                        text_to_speak = re.sub(r'[①-⑳]', '', part_text)
                        # Note: video_gen.py handles adding numbers to the display based on part_index.

                        c = get_clip(text_to_speak, VOICE_JP, "jp")
                        if c:
                            clips_to_concat.append(c)
                            current_seq_metadata.append({"label": "jp", "part_index": idx, "duration": c.duration, "type": "content", "text": part_text})

            elif submode == "jp_en":
                # JP -> EN (Simple implementation)
                for idx, part_text in enumerate(clean_parts):
                    text_to_speak = re.sub(r'[①-⑳]', '', part_text)
                    c = get_clip(text_to_speak, VOICE_JP, "jp")
                    if c:
                        clips_to_concat.append(c)
                        current_seq_metadata.append({"label": "jp", "part_index": idx, "duration": c.duration, "type": "content", "text": part_text})
                    # Gap 0.5s
                    clips_to_concat.append(make_silence(0.5))
                    current_seq_metadata.append({"label": "gap", "duration": 0.5, "type": "pause"})
                
                c = get_clip(word_text, VOICE_EN, "en")
                if c:
                    clips_to_concat.append(c)
                    current_seq_metadata.append({"label": "en", "duration": c.duration, "type": "content", "text": word_text})

            elif submode == "en_only":
                c = get_clip(word_text, VOICE_EN, "en")
                if c:
                    clips_to_concat.append(c)
                    current_seq_metadata.append({"label": "en", "duration": c.duration, "type": "content", "text": word_text})
                
                # Insert metadata for JP text so it appears in video
                for idx, part_text in enumerate(clean_parts):
                    current_seq_metadata.append({
                        "label": "jp", 
                        "part_index": idx, 
                        "duration": 0.0, 
                        "type": "silent_text", 
                        "text": part_text
                    })

                # Add Eng -> Jap Gap
                if gap_eng_to_jap > 0:
                    gap_ej = make_silence(gap_eng_to_jap)
                    clips_to_concat.append(gap_ej)
                    current_seq_metadata.append({"label": "gap", "duration": gap_eng_to_jap, "type": "pause"})
            
            else:
                print(f"  ! Unknown submode: {submode}")
                continue
                
            # 3. Final Gap
            gap_end = make_silence(gap_next_word)
            clips_to_concat.append(gap_end)
            current_seq_metadata.append({"label": "gap_end", "duration": gap_next_word, "type": "pause"})
            
            # --- Concatenate ---
            if clips_to_concat:
                try:
                    final_clip = concatenate_audioclips(clips_to_concat)
                    
                    # Build final metadata with absolute timings
                    curr = 0.0
                    abs_metadata = []
                    for item in current_seq_metadata:
                        item_copy = item.copy()
                        item_copy["start"] = curr
                        dur = item["duration"]
                        item_copy["end"] = curr + dur
                        abs_metadata.append(item_copy)
                        curr += dur
                    
                    # Safe filename
                    safe_word = re.sub(r'[\\/*?:"<>|]', "", word_text)
                    out_filename = f"word_{i}_{safe_word}.mp3"
                    out_path = os.path.join(output_dir, out_filename)
                    
                    final_clip.write_audiofile(out_path, fps=44100, logger=None)
                    
                    results.append({
                        "word_item": word_item,
                        "path": os.path.abspath(out_path),
                        "duration": final_clip.duration,
                        "metadata": abs_metadata
                    })
                    
                    # Close clips
                    final_clip.close()
                    for c in clips_to_concat:
                        try: c.close()
                        except: pass
                        
                except Exception as e:
                    print(f"    ! Error concatenating audio for {word_text}: {e}")
                    
    if not results:
        print("  ! Error: generate_audio_sections finished with empty results.")
        
    return results

def generate_vocalab_audio(script_data: Dict, output_dir: str = "output_audio") -> List[Dict]:
    """
    Generate audio segments for Vocalab Mode.
    Structure:
    - Word Cycle 1
    - Transition
    - Word Cycle 2
    ...
    - Story Section
    """
    print("--- Generating Vocalab Audio ---")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    results = []
    
    # Check for transition SFX
    sfx_path = os.path.join("assets", "パッ.mp3")
    if not os.path.exists(sfx_path):
        print(f"  ! SFX not found at {sfx_path}. Transition sound will be skipped.")
        # User requested to abolish "Next...", so we do not generate a placeholder.


    # Load SFX clip once
    sfx_clip = None
    try:
        if os.path.exists(sfx_path):
            sfx_clip = AudioFileClip(sfx_path)
            # Apply female boost if it sounds like a voice, or just keep it.
            # Let's apply boost just in case it's quiet
            if hasattr(sfx_clip, "volumex"): sfx_clip = sfx_clip.volumex(1.2)
            elif hasattr(sfx_clip, "with_volume_scaled"): sfx_clip = sfx_clip.with_volume_scaled(1.2)
    except Exception as e:
        print(f"  ! Error loading SFX: {e}")

    # Process Word Cycles
    word_cycles = script_data.get("word_cycles", [])
    
    # We use a temp dir for individual clips
    # Ensure temp root exists
    if not os.path.exists("temp"):
        os.makedirs("temp")

    with tempfile.TemporaryDirectory(dir="temp") as temp_dir:
        for i, cycle in enumerate(word_cycles):
            print(f"  - Processing Word {i+1}/{len(word_cycles)}: {cycle['word']}")
            
            cycle_clips = []
            cycle_metadata = [] # To track start times and display modes
            
            # Helper to generate/add clip
            def add_clip(text, voice, display_mode, repeat=1, is_jp=False):
                # Generate audio
                filename = f"w{i}_{display_mode}_{random.randint(0,9999)}.mp3"
                path = os.path.join(temp_dir, filename)
                
                # Determine voice (use female for EN, Nanami for JP)
                print(f"    + add_clip: {text[:20]}... ({display_mode})", flush=True)
                use_voice = voice
                if is_jp:
                    use_voice = "ja-JP-NanamiNeural"
                
                if generate_audio_segment_edge(text, use_voice, path):
                    # Load clip
                    try:
                        print(f"      - Loading clip: {path}", flush=True)
                        clip = AudioFileClip(path)
                        
                        # Add to cycle N times
                        for _ in range(repeat):
                            cycle_clips.append(clip)
                            # We'll calculate timing later
                            cycle_metadata.append({
                                "text": text,
                                "display_mode": display_mode,
                                "duration": clip.duration,
                                "word_data": cycle # Pass full data for video gen
                            })
                    except Exception as e:
                        print(f"    ! Error loading clip {path}: {e}")
            
            # Step 1: Word EN x2
            add_clip(cycle["word"], EDGE_VOICE_FEMALE, "step1", repeat=2)
            
            # Step 2: Meaning JP x1
            add_clip(cycle["meaning"], "ja-JP-NanamiNeural", "step2", repeat=1, is_jp=True)
            
            # Step 3: Example EN x2 (Display None)
            add_clip(cycle["example_en"], EDGE_VOICE_FEMALE, "step3", repeat=2)
            
            # Step 4: Example EN x1 (Display Full)
            add_clip(cycle["example_en"], EDGE_VOICE_FEMALE, "step4", repeat=1)
            
            # Step 5: Example JP x1 (Display Full)
            add_clip(cycle["example_jp"], "ja-JP-NanamiNeural", "step5", repeat=1, is_jp=True)
            
            # Combine clips for this word cycle
            if cycle_clips:
                try:
                    final_cycle_clip = concatenate_audioclips(cycle_clips)
                    output_filename = f"vocalab_word_{i}_{cycle['word']}.mp3"
                    output_path = os.path.join(output_dir, output_filename)
                    final_cycle_clip.write_audiofile(output_path, fps=44100, logger=None)
                    
                    # Calculate timestamps
                    current_time = 0.0
                    final_metadata = []
                    for meta in cycle_metadata:
                        final_metadata.append({
                            "start": current_time,
                            "end": current_time + meta["duration"],
                            "display_mode": meta["display_mode"],
                            "word_data": meta["word_data"]
                        })
                        current_time += meta["duration"]
                    
                    results.append({
                        "type": "word_cycle",
                        "path": output_path,
                        "duration": final_cycle_clip.duration,
                        "metadata": final_metadata
                    })
                    
                    # Clean up
                    final_cycle_clip.close()
                    for c in cycle_clips:
                        c.close()
                        
                except Exception as e:
                    print(f"    ! Error concatenating word cycle {i}: {e}")
            
            # Add Transition SFX (if not the last word? User said "between words", usually implies after each except last, or after each?)
            # "1つの単語（Step 1-5）が終わるごとに...次の単語に移ることを明示して" -> After every word.
            if sfx_clip:
                # We can either append it to the word clip or make it a separate segment.
                # Separate segment is easier.
                # But we need to save it to a file? We have sfx_path.
                results.append({
                    "type": "transition",
                    "path": sfx_path,
                    "duration": sfx_clip.duration,
                    "metadata": []
                })

    # Close SFX clip
    if sfx_clip:
        sfx_clip.close()

    # Process Listening Story
    story = script_data.get("story_section")
    if story:
        print("  - Processing Listening Story (Sentence-by-Sentence)...")
        
        # Ensure temp root exists
        if not os.path.exists("temp"):
            os.makedirs("temp")

        with tempfile.TemporaryDirectory(dir="temp") as story_temp_dir:
            # 1. Split story into sentences
            raw_text = story["content_en"]
            # Simple split by . ! ? followed by space or end of line
            # Keep delimiters
            sentences = re.split(r'(?<=[.!?])\s+', raw_text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            sentence_clips = []
            sentence_metadata = [] # temporary metadata for one pass
            
            # 2. Generate audio for each sentence
            for idx, sent in enumerate(sentences):
                temp_sent_path = os.path.join(story_temp_dir, f"sent_{idx}.mp3")
                print(f"    > Generating story sentence {idx+1}/{len(sentences)}: {sent[:20]}...", flush=True)
                
                if generate_audio_segment_edge(sent, EDGE_VOICE_FEMALE, temp_sent_path):
                    try:
                        clip = AudioFileClip(temp_sent_path)
                        # Boost
                        if hasattr(clip, "volumex"): clip = clip.volumex(1.4)
                        elif hasattr(clip, "with_volume_scaled"): clip = clip.with_volume_scaled(1.4)
                        
                        sentence_clips.append(clip)
                        sentence_metadata.append({
                            "text": sent,
                            "duration": clip.duration
                        })
                    except Exception as e:
                        print(f"    ! Error loading sentence clip {idx}: {e}")
            
            if sentence_clips:
                try:
                    # 3. Create One Full Pass Clip
                    full_pass_clip = concatenate_audioclips(sentence_clips)
                    full_pass_duration = full_pass_clip.duration
                    
                    # 4. Create Final Clip (Repeated 2 times)
                    final_story_clips = [full_pass_clip, full_pass_clip] # Reference same clip twice
                    final_story_clip = concatenate_audioclips(final_story_clips)
                    
                    final_story_path = os.path.join(output_dir, "vocalab_story_final.mp3")
                    final_story_clip.write_audiofile(final_story_path, fps=44100, logger=None)
                    
                    # 5. Build Final Metadata (Pass 1 + Pass 2)
                    final_metadata = []
                    current_time = 0.0
                    
                    # Pass 1
                    for meta in sentence_metadata:
                        final_metadata.append({
                            "start": current_time,
                            "end": current_time + meta["duration"],
                            "display_mode": "story",
                            "text": meta["text"],
                            "full_text": raw_text # Context for video gen
                        })
                        current_time += meta["duration"]
                        
                    # Pass 2 (Append same metadata with offset)
                    # Note: There might be a tiny gap due to concatenation? 
                    # concatenate_audioclips usually handles it well.
                    # Start time for Pass 2 is full_pass_duration
                    current_time = full_pass_duration
                    for meta in sentence_metadata:
                        final_metadata.append({
                            "start": current_time,
                            "end": current_time + meta["duration"],
                            "display_mode": "story",
                            "text": meta["text"],
                            "full_text": raw_text
                        })
                        current_time += meta["duration"]

                    results.append({
                        "type": "story",
                        "path": final_story_path,
                        "duration": final_story_clip.duration,
                        "metadata": final_metadata
                    })
                    
                    # Clean up
                    final_story_clip.close()
                    full_pass_clip.close()
                    for c in sentence_clips:
                        c.close()

                except Exception as e:
                    print(f"    ! Error concatenating story: {e}")
            else:
                print("    ! No sentence clips generated for story.")

    return results
