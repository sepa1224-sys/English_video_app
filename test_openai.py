
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
print(f"API Key present: {bool(api_key)}")

if api_key:
    client = OpenAI(api_key=api_key)
    try:
        print("Sending request with long prompt...")
        prompt = "Create the Introduction part of an English podcast about Climate Change Solutions. Target Level: Advanced. Length: Approx 3 minutes. " * 20
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        print("Response received:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")
else:
    print("No API key found.")
