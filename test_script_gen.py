
import script_gen
import os
from dotenv import load_dotenv

load_dotenv()
print("Starting test_script_gen...")
try:
    script = script_gen.generate_script("Climate Change Solutions", "Advanced")
    print("Script generation finished.")
    print(script)
except Exception as e:
    print(f"Error: {e}")
