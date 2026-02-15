
import os
from dotenv import load_dotenv
import sys

print("Loading .env...")
load_dotenv()

api_key = os.environ.get("OPENAI_API_KEY")
print(f"API Key present: {bool(api_key)}")

try:
    from openai import OpenAI
    print("OpenAI module imported.")
    client = OpenAI(api_key=api_key)
    print("Client initialized. Sending test request...")
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5
    )
    print(f"Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
