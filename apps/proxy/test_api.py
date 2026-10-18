import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
URL = "https://openrouter.ai/api/v1/chat/completions"

if not API_KEY:
    raise ValueError(
        "OPEN_ROUTER_API_KEY not found. Check your .env file."
    )

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": (
                "Write a Python function to check if a string "
                "is a palindrome. Include a short example."
            ),
        }
    ],
    "max_tokens": 500,
}

try:
    response = requests.post(
        URL,
        headers=headers,
        json=payload,
        timeout=120,
    )

    try:
        data = response.json()
    except ValueError:
        print("Invalid JSON response:")
        print(response.text)
        raise SystemExit(1)

    if not response.ok or "error" in data:
        print("OpenRouter API request failed.")
        print("Status code:", response.status_code)
        print("Details:", data.get("error", data))
        raise SystemExit(1)

    choices = data.get("choices", [])

    if not choices:
        print("No completion returned.")
        print("Full response:", data)
        raise SystemExit(1)

    message = choices[0].get("message", {})
    content = message.get("content")

    if content:
        print("\n--- Model Response ---\n")
        print(content)
    else:
        print("The model returned no text.")
        print("Message:", message)

except requests.exceptions.Timeout:
    print("Request timed out. Try again later.")

except requests.exceptions.RequestException as error:
    print("Network error:", error)
