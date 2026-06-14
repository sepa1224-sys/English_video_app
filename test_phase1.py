"""Phase 1 test: Generate exam video with bundled NotoSans fonts to compare with Hiragino."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import video_gen

# Build audio_segments from existing temp files
audio_segments = []
for i in range(8):
    path = f"temp/temp_audio_segments/section_{i}_listening_part.mp3"
    if os.path.exists(path):
        from moviepy import AudioFileClip
        ac = AudioFileClip(path)
        dur = ac.duration
        ac.close()
        audio_segments.append({
            "type": "listening_part",
            "audio_path": path,
            "duration": dur,
            "speaker": ["Student A", "Student B", "Student A", "Student B", "Professor", "Student A", "Student B", "Professor"][i],
            "text": f"Segment {i+1} text placeholder",
        })

# Questions from the last generated video
questions = [
    {
        "question": "According to Student A, what is the crucial weakness of grounding the significance of biodiversity purely in its utility to humans?",
        "choices": [
            "A) It ignores the suffering of non-human sentient animals entirely.",
            "B) It accepts the logic that biodiversity could be discarded once synthetic substitutes become possible.",
            "C) It conflicts with the findings of ecological research on trophic cascades.",
            "D) It prevents governments from setting legally binding conservation targets.",
        ],
    },
    {
        "question": "What can be inferred about the Professor's view on the relationship between philosophical disagreement and conservation action?",
        "choices": [
            "A) The Professor believes philosophical debate is indispensable and must be fully resolved before any policy is implemented.",
            "B) The Professor implies that despite real philosophical differences, all three frameworks converge on the same vital practical conclusion.",
            "C) The Professor suggests that deep ecology is the most essential framework.",
            "D) The Professor concludes that indigenous traditions are more vivid but less logically rigorous.",
        ],
    },
    {
        "question": "Which of the following best summarizes the main point of the discussion?",
        "choices": [
            "A) Anthropocentric and intrinsic value frameworks are fundamentally incompatible.",
            "B) Regardless of whether biodiversity is valued for human utility, sentient experience, or systemic ecological integrity, its protection is an essential and urgent imperative.",
            "C) De-extinction technology represents the most vital solution to the biodiversity crisis.",
            "D) Singer's utilitarian ethics is indispensable to conservation policy.",
        ],
    },
]

vocab_list = [
    {"word": "vital", "meaning": "非常に重要な"},
    {"word": "vivid", "meaning": "生き生きとした"},
    {"word": "essential", "meaning": "必要不可欠な"},
    {"word": "indispensable", "meaning": "必要不可欠な"},
    {"word": "crucial", "meaning": "決定的な"},
    {"word": "consequence", "meaning": "結果"},
]

output_file = "test_phase1_output.mp4"
print(f"Generating test video: {output_file}")
print(f"Font used: {video_gen.get_font_path()}")
print(f"FONT_PATH_BOLD: {video_gen.FONT_PATH_BOLD}")
print(f"FONT_PATH_BLACK: {video_gen.FONT_PATH_BLACK}")

result = video_gen.generate_exam_video(
    audio_segments=audio_segments,
    questions=questions,
    bg_image_path="background.png",
    output_file=output_file,
    topic="Biodiversity",
    vocab_list=vocab_list,
    university="todai",
    special_clips={},
)

print(f"\nResult: {result}")
if os.path.exists(output_file):
    size_mb = os.path.getsize(output_file) / 1024 / 1024
    print(f"File size: {size_mb:.1f} MB")
    from moviepy import VideoFileClip
    v = VideoFileClip(output_file)
    print(f"Resolution: {v.size}")
    print(f"Duration: {v.duration:.1f}s ({v.duration/60:.1f}min)")
    v.close()
