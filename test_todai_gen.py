print("DEBUG: STARTING TEST SCRIPT")
import os
import sys
import json
import shutil
from moviepy import AudioFileClip
from video_gen import generate_todai_video
from script_gen import generate_todai_script
# Import from audio_gen to use the exact same logic/constants as production
from audio_gen import generate_audio_segment_edge, EDGE_VOICE_MALE, EDGE_VOICE_FEMALE, EDGE_VOICE_GUEST

def create_todai_audio(text, speaker, output_path):
    """
    Generate audio using Edge-TTS with production voice assignments.
    Student A -> Christopher (Male)
    Student B -> Emma (Female)
    Professor -> Guy (Guest)
    """
    voice = EDGE_VOICE_MALE
    if speaker == "Student B":
        voice = EDGE_VOICE_FEMALE
    elif speaker == "Professor":
        voice = EDGE_VOICE_GUEST
        
    print(f"Generating audio for {speaker} ({voice}): {text[:20]}...")
    
    # Use the imported function from audio_gen.py
    # speed=1.0 is default
    success = generate_audio_segment_edge(text, voice, output_path, speed=1.0)
    
    if not success:
        print(f"Failed to generate audio for {output_path}")
        # Fallback to dummy file if generation fails (shouldn't happen with Edge-TTS usually)
        if os.path.exists("assets/next_word.mp3"):
             shutil.copy("assets/next_word.mp3", output_path)

def run_test():
    # Redirect stdout to a file to capture logs
    # sys.stdout = open("test_stdout_log.txt", "w", encoding="utf-8")
    
    print("Running Todai Video Generation Test (Production Config)...")
    
    output_file = "output/test_todai_video_final.mp4"
    if not os.path.exists("output"):
        os.makedirs("output")
    if not os.path.exists("temp"):
        os.makedirs("temp")
        
    # 1. Get Script Data from script_gen.py (Mock or Real)
    # This ensures we are testing the actual data structure and content from the generator
    vocab_list = [
        {"word": "vital", "meaning": "不可欠な", "definition": "Absolutely necessary or important; essential.", "example": "Secrecy is of vital importance."},
        {"word": "agency", "meaning": "主体性", "definition": "Action or intervention, especially such as to produce a particular effect.", "example": "Canals carved by the agency of running water."},
        {"word": "oversight", "meaning": "監視", "definition": "The action of overseeing something.", "example": "Effective oversight of the financial industry."}
    ]
    
    # MOCK DATA FOR TESTING
    print("Using Mock Script Data for Testing...")
    script_data = {
        "topic": "AI Ethics (Mock)",
        "dialog": [
            {
                "speaker": "Student A", 
                "text": "Hi, I'm Alex. I believe AI is vital for our future.", 
                "translation": "こんにちは、アレックスです。AIは私たちの未来にとって不可欠だと思います。"
            },
            {
                "speaker": "Student B", 
                "text": "I'm Sarah. But we must consider the agency of humans.", 
                "translation": "サラです。でも私たちは人間の主体性を考慮しなければなりません。"
            }
        ],
        "questions": [
            {
                "question": "What is Alex's stance?",
                "choices": ["A) AI is vital", "B) AI is dangerous", "C) AI is neutral", "D) AI is unknown"],
                "correct_answer": "A",
                "explanation": "He says it is vital.",
                "explanation_jp": "彼は不可欠だと言っています。"
            }
        ]
    }
    
    # script_data = generate_todai_script("AI Ethics", vocab_list)
    
    if not script_data:
        print("Error: Failed to generate script data.")
        return

    dialog_data = script_data["dialog"]
    questions_data = script_data["questions"]
    topic = script_data["topic"]

    print(f"Generated Script Topic: {topic}")
    print(f"Dialog Lines: {len(dialog_data)}")
    print(f"Questions: {len(questions_data)}")
    
    # 2. Generate Audio for Dialog
    audio_segments = []
    for i, line in enumerate(dialog_data):
        path = f"temp/test_seg_{i}.mp3"
        create_todai_audio(line["text"], line["speaker"], path)
        
        # Calculate duration
        dur = 0
        if os.path.exists(path):
            try:
                with AudioFileClip(path) as af:
                    dur = af.duration
            except Exception as e:
                print(f"Warning: Could not get duration for {path}: {e}")
        
        audio_segments.append({
            "audio_path": path,
            "text": line["text"],
            "japanese": line["translation"], # script_gen uses 'translation', video_gen might expect 'japanese'? 
            # script_gen output keys: speaker, text, translation
            # video_gen input keys expected: speaker, text, japanese
            # Let's map it explicitly.
            "speaker": line["speaker"],
            "duration": dur
        })

    # 3. Prepare Questions
    questions = []
    for i, q in enumerate(questions_data):
        # Generate Question Audio
        q_audio_path = f"temp/test_q{i+1}.mp3"
        create_todai_audio(q["question"], "Student A", q_audio_path)
        
        # Generate Choice Audio (User Request: Full Option Reading)
        # SKIP GENERATION HERE TO TEST video_gen.py ROBUSTNESS
        choices_audio_paths = []
        # for j, choice in enumerate(q.get("choices", [])):
        #     c_path = f"temp/test_q{i+1}_c{j+1}.mp3"
        #     # Read the choice text (e.g. "A) It is vital...")
        #     create_todai_audio(choice, "Student A", c_path)
        #     choices_audio_paths.append(c_path)
        
        q_item = q.copy()
        q_item["audio_path"] = q_audio_path
        q_item["choices_audio_paths"] = choices_audio_paths
        questions.append(q_item)
    
    # Background Image (Fixed Black)
    bg_image = "assets/background_black.png"
    if not os.path.exists(bg_image):
        print("Creating dummy black background...")
        from PIL import Image
        img = Image.new('RGB', (1280, 720), color=(0, 0, 0))
        img.save(bg_image)
    
    # Run Video Generation
    try:
        print("Calling generate_todai_video with Production arguments...")
        output_path, timestamps = generate_todai_video(
            audio_segments=audio_segments,
            questions=questions,
            bg_image_path=bg_image, # Fixed black background
            output_file=output_file,
            topic=topic,
            vocab_list=vocab_list
        )
        print(f"Success! Video saved to {output_path}")
        print("Timestamps:", json.dumps(timestamps, indent=2))
        
    except Exception as e:
        error_msg = f"Test Failed: {e}"
        print(error_msg)
        with open("test_error_log.txt", "w") as f:
            f.write(error_msg)
            import traceback
            traceback.print_exc(file=f)


    # Run Description Generation Test
    desc_output = output_file.replace(".mp4", "_description.txt")
    from script_gen import generate_todai_description
    generate_todai_description(script_data, desc_output)
    print(f"Description generated at: {desc_output}")

if __name__ == "__main__":
    run_test()
