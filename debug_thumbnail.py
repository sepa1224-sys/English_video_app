
import os
import video_gen
from dotenv import load_dotenv

load_dotenv()

print("Checking API Key...")
api_key = os.environ.get("OPENAI_API_KEY")
if api_key:
    print(f"API Key found: {api_key[:5]}...")
else:
    print("API Key NOT found.")

print("\nTesting generate_thumbnail...")
try:
    path = video_gen.generate_thumbnail("Debug Topic", "ターゲット1900", day_number=1, output_path="debug_thumb.png")
    print(f"Result path: {path}")
except Exception as e:
    print(f"Exception caught: {e}")
