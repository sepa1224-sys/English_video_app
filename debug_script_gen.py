
import os
import json
from unittest.mock import MagicMock

# Set dummy API key so script_gen doesn't return None early
os.environ["OPENAI_API_KEY"] = "dummy"

# Import script_gen
import script_gen

# Mock response content
mock_content = json.dumps({
    "dialog": [
        {"speaker": "Student A", "text": "Hello", "translation": "こんにちは"},
        {"speaker": "Professor", "text": "Hi", "translation": "やあ"}
    ],
    "questions": [
        {"question": "What is it?"}
    ]
})

mock_response = MagicMock()
mock_response.choices[0].message.content = mock_content

# Mock OpenAI class
script_gen.OpenAI = MagicMock()
# When OpenAI() is called, return a mock client
mock_client = MagicMock()
script_gen.OpenAI.return_value = mock_client
# When client.chat.completions.create is called, return mock_response
mock_client.chat.completions.create.return_value = mock_response

# Call function
print("Calling generate_todai_script...")
try:
    data = script_gen.generate_todai_script("Test Topic", [{"word": "test", "meaning": "test"}])
    if data:
        print("Keys:", list(data.keys()))
        if "sections" in data:
            print("Sections count:", len(data["sections"]))
            print("Sections content:", json.dumps(data["sections"], indent=2))
        else:
            print("ERROR: No sections key")
    else:
        print("ERROR: Returned None")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
