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
import tempfile
import platform

"""Main script for Mr. Bones, the pirate voice assistant.
Handles speech-to-text, prompt loading, LLM API requests, and text-to-speech output.
"""
dotenv.load_dotenv()

# Audio Configuration
SPEECH_RATE = os.getenv("SPEECH_RATE", "200")
AUDIO_PLAYER = os.getenv("AUDIO_PLAYER", "afplay")

# Performance Settings
TIMEOUT = int(os.getenv("TIMEOUT", "90"))
WAIT_INTERVAL = int(os.getenv("WAIT_INTERVAL", "3"))

def validate_environment():
    """Validate all required environment variables and configuration.
    Exits with error message if validation fails.
    """
    errors = []
    print("⬜ Environment validation starting")
    # Required variables
    required_vars = {
        "API_URL": "URL of your LLM API backend",
        "LLM_MODEL": "LLM model to use (e.g., llama3.1:8b-instruct-q4_K_M)"
    }
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            errors.append(f"Missing {var}: {description}")
    
    # Validate API_URL format
    api_url = os.getenv("API_URL")
    if api_url and not (api_url.startswith("http://") or api_url.startswith("https://")):
        errors.append("API_URL must start with http:// or https://")
    
    # Validate numeric values
    numeric_vars = {
        "SPEECH_RATE": (50, 300, "Speech rate should be between 50-300"),
        "TIMEOUT": (10, 300, "Timeout should be between 10-300 seconds"),
        "WAIT_INTERVAL": (1, 30, "Wait interval should be between 1-30 seconds"),
        "SAMPLE_RATE": (8000, 48000, "Sample rate should be between 8000-48000"),
        "BLOCKSIZE": (1000, 16000, "Block size should be between 1000-16000")
    }
    
    for var, (min_val, max_val, message) in numeric_vars.items():
        value = os.getenv(var)
        if value:
            try:
                num_value = int(value)
                if num_value < min_val or num_value > max_val:
                    errors.append(f"{var}={value}: {message}")
            except ValueError:
                errors.append(f"{var}={value}: Must be a valid number")
    
    # Validate file paths
    prompt_file = os.getenv("PROMPT_FILE", "prompt.txt")
    if not os.path.isfile(prompt_file):
        errors.append(f"Prompt file not found: {prompt_file}")
    
    vosk_model_path = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15")
    if not os.path.exists(vosk_model_path):
        errors.append(f"Vosk model not found: {vosk_model_path}")
    
    # Validate audio player
    audio_player = os.getenv("AUDIO_PLAYER", "afplay")
    try:
        subprocess.run([audio_player, "--help"], capture_output=True, check=False)
    except FileNotFoundError:
        errors.append(f"Audio player not found: {audio_player}")
    
    # Report errors
    if errors:
        print("❌ Environment validation failed:")
        for error in errors:
            print(f"  • {error}")
        print("\nPlease check your .env file and ensure all required tools are installed.")
        sys.exit(1)
    
    print("✅ Environment validation passed")

# Validate environment before starting
validate_environment()

# Get validated environment variables
API_URL = os.getenv("API_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

# Filler phrase counter for cycling through ElevenLabs audio files
filler_counter = 0

print(f"🎤 Speech Rate: {SPEECH_RATE}")
print(f"🔊 Audio Player: {AUDIO_PLAYER}")
print(f"⏱️  Timeout: {TIMEOUT}s")
print(f"⏳ Wait Interval: {WAIT_INTERVAL}s")
print(f"🌐 API URL: {API_URL}")
print(f"🤖 LLM Model: {LLM_MODEL}")

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

def speak_text(text):
    """Speak text using the system's text-to-speech.
    Args:
        text (str): Text to speak
    """
    try:
        # Use system say command for simple TTS feedback
        subprocess.run(["say", "-r", SPEECH_RATE, text], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"TTS error: {e}")
    except Exception as e:
        print(f"Error speaking text: {e}")

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
    print(f"\n🌐 === API REQUEST ===")
    print(f"📡 Endpoint: {API_URL}")
    print(f"🤖 Model: {chat_request.get('model', 'unknown')}")
    print(f"💬 Messages: {len(chat_request.get('messages', []))}")
    print(f"⏱️  Timeout: {TIMEOUT}s")
    
    if LLM_MODEL and LLM_MODEL.startswith("ai/mistral"):
        print("🔄 Formatting for Mistral model...")
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
        print("✅ Mistral formatting complete")

    print(f"📤 Request payload:")
    print(json.dumps(chat_request, indent=2))
    
    try:
        async with httpx.AsyncClient() as client:
            print("🔗 Establishing connection...")
            response = await client.post(API_URL, json=chat_request, timeout=TIMEOUT)
            
            print(f"\n🌐 === API RESPONSE ===")
            print(f"📊 Status: {response.status_code}")
            print(f"📏 Content-Length: {len(response.content)} bytes")
            print(f"🏷️  Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code != 200:
                print(f"❌ Error response body:")
                print(response.text)
            else:
                print("✅ Response received successfully")
                try:
                    response_json = response.json()
                    if "error" in response_json:
                        print(f"❌ API Error: {response_json['error']}")
                    elif "response" in response_json:
                        print(f"💭 Response text: {response_json['response'][:100]}...")
                        if "audio_base64" in response_json:
                            print(f"🔊 Audio included: {len(response_json['audio_base64'])} chars")
                        else:
                            print("🔇 No audio in response")
                    else:
                        print(f"🔍 Response keys: {list(response_json.keys())}")
                except Exception as parse_error:
                    print(f"❌ Failed to parse JSON response: {parse_error}")
                    print(f"📄 Raw response: {response.text[:200]}...")
            
            return response
            
    except httpx.TimeoutException:
        print(f"⏰ Request timed out after {TIMEOUT} seconds")
        raise
    except httpx.ConnectError as e:
        print(f"🔌 Connection failed: {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise

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

def play_filler_phrase():
    """Play a random filler phrase from the ElevenLabs generated audio files.
    Cycles through filler_01.mp3 to filler_25.mp3 to avoid repetition.
    """
    global filler_counter
    filler_counter += 1
    if filler_counter > 25:
        filler_counter = 1
    
    filler_file = f"audio/fillers/filler_{filler_counter:02d}.mp3"
    
    if os.path.exists(filler_file):
        try:
            print(f"🎵 Playing filler phrase: {filler_file}")
            subprocess.run([AUDIO_PLAYER, filler_file], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error playing filler phrase: {e}")
        except Exception as e:
            print(f"Unexpected error playing filler: {e}")
    else:
        print(f"Warning: Filler file not found: {filler_file}")


async def main():
    """Main event loop for the Mr. Bones assistant.
    Handles speech-to-text, LLM API requests, and output.
    """
    import concurrent.futures
    
    # Create a thread pool executor for running blocking STT calls
    with concurrent.futures.ThreadPoolExecutor() as executor:
        while True:
            # Run the blocking STT transcribe function in a separate thread
            print("Listening for speech...")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(executor, stt.transcribe)
            
            # Handle the new tuple return value (text, confidence)
            if result is None or result[0] is None:
                print("No valid transcription received, continuing to listen...")
                # Provide audio feedback for unclear speech
                speak_text("Sorry matey, I didn't catch that. Could you speak up?")
                continue
                
            text, confidence = result
            print(f"Transcribed text: '{text}' (confidence: {confidence})")
                
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
            
            # Natural pause before responding, then play filler phrase
            await asyncio.sleep(0.3)  # 300ms natural response delay
            play_filler_phrase()

            wait_time = 0
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
                        # Use temporary file for better management
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                            tmp_file.write(audio_bytes)
                            tmp_file.flush()
                            os.fsync(tmp_file.fileno())
                            print(f"Audio file {tmp_file.name} written and flushed.")
                            subprocess.run([AUDIO_PLAYER, tmp_file.name])
                            os.unlink(tmp_file.name)  # Clean up immediately
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