import stt
import subprocess
import os
import asyncio
import httpx
import sys
import json
import dotenv
import re

"""Main script for Mr. Bones, the pirate voice assistant.
Handles speech-to-text, prompt loading, LLM API requests, and text-to-speech output.
"""
dotenv.load_dotenv()

VOICE       = os.getenv("VOICE", "Samantha")
SPEECH_RATE = os.getenv("SPEECH_RATE", "200")
API_URL     = os.getenv("API_URL")
if not API_URL:
    print("Error: API_URL environment variable is not set.")
    sys.exit(1)
LLM_MODEL   = os.getenv("LLM_MODEL") 
if not LLM_MODEL:
    print("Error: LLM_MODEL environment variable is not set.")
    sys.exit(1)

def load_prompt():
    """Load the pirate prompt from a file specified by PROMPT_FILE env var or an error if the file is not found.
    Returns:
        str: The prompt text.
    """
    prompt_file = os.getenv("PROMPT_FILE", "prompt.txt")
    if not os.path.isfile(prompt_file):
        print(f"Error: Prompt file '{prompt_file}' not found.")
        sys.exit(1)
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read().strip()

def speak_text(text):
    """Speak the given text using macOS 'say' command with the configured voice and rate.
    Args:
        text (str): The text to speak.
    """
    subprocess.run(["say", "-v", VOICE, "-r", SPEECH_RATE, text])

async def send_request(chat_request):
    """Send a chat request to the LLM API and return the response.
    Args:
        chat_request (dict): The request payload for the LLM API.
    Returns:
        httpx.Response: The HTTP response from the API.
    """
    async with httpx.AsyncClient() as client:
        return await client.post(API_URL, json=chat_request, timeout=90)

messages = [{"role": "system", "content": load_prompt()}]

chat_request = {
    "model": LLM_MODEL,
    "messages": messages
}

def remove_nonstandard(text):
    """Remove all characters except letters, numbers, and normal punctuation (. , ! ? ; ,), and replace pirate 'Arr' or 'Arrr...' (standalone, case-insensitive) with 'Are'."""
    import re
    # Replace standalone 'Arr', 'Arrr', etc. (case-insensitive, not part of another word) with 'Are'
    text = re.sub(r'\b[Aa]rr*\b', 'Are', text)
    # Only keep letters, numbers, space, and . , ! ? ; ,
    return re.sub(r"[^a-zA-Z0-9\s\.,!\?;:]", "", text)

async def main():
    """Main event loop for the Mr. Bones assistant.
    Handles speech-to-text, LLM API requests, and output.
    """
    while True:
        text = stt.transcribe()
        print("Transcribed text:", text)
        # If the transcription is just 'huh' (case-insensitive, with or without punctuation), skip sending to LLM
        if text.strip().lower().strip('.,!?;:') == "huh":
            print("Heard only 'huh', ignoring and waiting for next input...")
            continue
        print("\nMr. Bones is thinking...")
        # speak_text("Mr. Bones is thinking")

        request_task = asyncio.create_task(send_request(chat_request))
        messages.append({"role": "user", "content": text})

        while not request_task.done():
            print("Still waiting...")
            await asyncio.sleep(1)  # Check every second

        try:
            response = await request_task
            response.raise_for_status()
            response_data = response.json()
            if "error" in response_data:
                print("Error from API:", response_data["error"])
            else:
                clean_response = remove_nonstandard(response.json()["response"])
                print("Response:", clean_response)
            # speak_text(clean_response)
            messages.append({
                "role": "assistant",
                "content": clean_response
            })
        except Exception as e:
            print("Error:", str(e))

if __name__ == "__main__":
    asyncio.run(main())