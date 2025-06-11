# Todo: Use wait time env variable to control how long to wait for speech input

import stt
import subprocess
import os
import asyncio
import httpx
import sys
import json
import dotenv
import re
import random
import base64

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

# Thinking and waiting phrases
THINKING_PHRASES = [
    "Hmm, let me think on that!",
    "A moment, matey, while I ponder!",
    "Let me see...",
    "Give me a hot second to think on that one!",
    "Let me consult me map of knowledge!",
    "Arr, that's a puzzler! Give me a moment!",
    "Let me search the seven seas for an answer!",
    "Hold tight, I'm wrackin' me brain!",
    "Let me put on me thinkin' hat!",
    "This one needs a bit o' thought, matey!"
]
WAITING_PHRASES = [
    "Don't worry, I'm still here!",
    "Still thinking, hold tight!",
    "Just a moment more, matey!",
    "I'm working on it, don't go anywhere!",
    "The answer be comin' soon, I promise!",
    "Still searchin' the depths for ye answer!",
    "Hang on, me brain's still churnin'!",
    "Almost there, matey!",
    "Patience, the seas be rough today!",
    "Keep yer hat on, I'm nearly done!"
]

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

def format_mistral_prompt(messages):
    prompt = ""
    first = True
    system_prefix = ""

    i = 0
    while i < len(messages):
        msg = messages[i]

        # First message can include system and user setup
        if first and msg["role"] == "system":
            system_prefix = msg["content"].strip()
            i += 1
            continue

        if msg["role"] == "user":
            user_input = msg["content"].strip()
            if first:
                # Start with BOS token for the first block
                prompt += f"<s>[INST] {system_prefix} {user_input} [/INST]"
                first = False
            else:
                prompt += f"\n[INST] {user_input} [/INST]"
        elif msg["role"] == "assistant":
            prompt += f"{msg['content'].strip()}"
        i += 1

    return prompt


async def send_request(chat_request):
    """Send a chat request to the LLM API and return the response.
    Args:
        chat_request (dict): The request payload for the LLM API.
    Returns:
        httpx.Response: The HTTP response from the API.
    """
    if LLM_MODEL and LLM_MODEL.startswith("ai/mistral"):
        # Format the prompt for Mistral models
        mistral_messages = format_mistral_prompt(chat_request["messages"])

        chat_request = {
            "model": LLM_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": mistral_messages
                }
            ],
        }
        

    print("Sending request to LLM API:", json.dumps(chat_request, indent=2))
    async with httpx.AsyncClient() as client:
        return await client.post(API_URL, json=chat_request, timeout=90)

# Build the initial JSON object for the chat request
messages = [{"role": "system", "content": load_prompt()}]

chat_request = {
    "model": LLM_MODEL,
    "messages": messages
}

def remove_nonstandard(text):
    """Remove all characters except letters, numbers, and normal punctuation (. , ! ? ; ,), 
    and replace pirate 'Arr' or 'Arrr...' (standalone, case-insensitive) with 'Are'."""
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
        # Play a random thinking phrase immediately (optional, can be removed)
        # speak_text(random.choice(THINKING_PHRASES))

        # Build chat history and send to API
        messages.append({"role": "user", "content": text})
        chat_request = {
            "model": LLM_MODEL,
            "messages": messages
        }
        request_task = asyncio.create_task(send_request(chat_request))

        wait_time = 0
        WAIT_INTERVAL = 3  # seconds
        while not request_task.done():
            await asyncio.sleep(1)
            wait_time += 1
            print(f"Waiting for response... {wait_time} seconds elapsed")
            # Every WAIT_INTERVAL seconds, play a waiting phrase (optional, can be removed)
            # if wait_time % WAIT_INTERVAL == 0:
            #     speak_text(random.choice(WAITING_PHRASES))

        try:
            response = await request_task
            response.raise_for_status()
            response_data = response.json()
            if "error" in response_data:
                print("Error from API:", response_data["error"])
            else:
                clean_response = remove_nonstandard(response_data["response"])
                print("Response:", clean_response)
                # Play the audio response from API
                if "audio_base64" in response_data:
                    audio_bytes = base64.b64decode(response_data["audio_base64"])
                    with open("tts_output.wav", "wb") as f:
                        f.write(audio_bytes)
                        f.flush()
                        os.fsync(f.fileno())
                    print("Audio file tts_output.wav written and flushed.")
                    subprocess.run(["afplay", "tts_output.wav"])
                else:
                    print("No audio response in API data, using text response.")
           
                messages.append({
                    "role": "assistant",
                    "content": clean_response
                })
        except Exception as e:
            print("Error:", str(e))

if __name__ == "__main__":
    asyncio.run(main())