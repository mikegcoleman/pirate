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
import queue
import threading

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

print(f"Speech Rate: {SPEECH_RATE}")
print(f"Audio Player: {AUDIO_PLAYER}")
print(f"Timeout: {TIMEOUT}s")
print(f"Wait Interval: {WAIT_INTERVAL}s")
print(f"API URL: {API_URL}")
print(f"LLM Model: {LLM_MODEL}")

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


async def send_streaming_request(chat_request):
    """Send a streaming chat request to the LLM API and yield audio chunks.
    Args:
        chat_request (dict): The request payload for the LLM API.
    Yields:
        dict: Audio chunk data containing sentence and audio_base64
    """
    # Use streaming endpoint
    streaming_api_url = API_URL.replace('/api/chat', '/api/chat/stream')
    
    print("Sending streaming request to LLM API:", json.dumps(chat_request, indent=2))
    
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            'POST', 
            streaming_api_url, 
            json=chat_request,
            headers={'Accept': 'text/event-stream'}
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    data_str = line[6:]  # Remove 'data: ' prefix
                    try:
                        chunk_data = json.loads(data_str)
                        yield chunk_data
                    except json.JSONDecodeError:
                        continue

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
        return await client.post(API_URL, json=chat_request, timeout=TIMEOUT)

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

def play_audio_chunk(audio_base64):
    """Play a single audio chunk from base64 encoded WAV data (fallback function)."""
    try:
        audio_bytes = base64.b64decode(audio_base64)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file.flush()
            subprocess.run([AUDIO_PLAYER, tmp_file.name], check=True)
    except Exception as e:
        print(f"Error playing audio chunk: {e}")

async def handle_streaming_response(chat_request):
    """Handle streaming response with real-time audio playback."""
    full_response = ""
    audio_queue = queue.Queue()
    audio_thread = None
    audio_chunks_queued = 0
    audio_chunks_played = 0
    audio_lock = threading.Lock()
    
    def audio_player_worker():
        """Worker thread to play audio chunks sequentially with minimal delay."""
        nonlocal audio_chunks_played
        
        while True:
            try:
                audio_data = audio_queue.get(timeout=120)
                if audio_data is None:  # Sentinel value to stop
                    audio_queue.task_done()
                    break
                    
                # Play audio chunk and wait for completion (sequential)
                audio_bytes = base64.b64decode(audio_data)
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    tmp_file.write(audio_bytes)
                    tmp_file.flush()
                    
                    # Play and wait for completion to maintain sequence
                    process = subprocess.Popen([AUDIO_PLAYER, tmp_file.name])
                    process.wait()  # Wait for this sentence to finish
                    
                    # Clean up immediately
                    try:
                        os.unlink(tmp_file.name)
                    except:
                        pass
                
                with audio_lock:
                    audio_chunks_played += 1
                    print(f"Audio progress: {audio_chunks_played}/{audio_chunks_queued} chunks played")
                audio_queue.task_done()
                
            except queue.Empty:
                print("Audio worker timed out waiting for chunks")
                break
            except Exception as e:
                print(f"Audio worker error: {e}")
                audio_queue.task_done()
    
    try:
        # Start audio worker thread
        audio_thread = threading.Thread(target=audio_player_worker, daemon=False)  # Not daemon so it completes
        audio_thread.start()
        
        async for chunk in send_streaming_request(chat_request):
            if chunk['type'] == 'text_preview':
                # Show text immediately while TTS generates
                sentence = chunk['sentence']
                print(f"Preview: {sentence}")
                
            elif chunk['type'] == 'audio_chunk':
                sentence = chunk['sentence']
                print(f"Audio ready: {sentence}")
                full_response += sentence + " "
                
                # Queue audio for playback
                audio_queue.put(chunk['audio_base64'])
                with audio_lock:
                    audio_chunks_queued += 1
                
            elif chunk['type'] == 'text_chunk':
                # Fallback for failed TTS
                sentence = chunk['sentence']
                print(f"Text only: {sentence}")
                full_response += sentence + " "
                speak_text(sentence)  # Use system TTS as fallback
                
            elif chunk['type'] == 'complete':
                print("Streaming complete")
                break
                
            elif chunk['type'] == 'error':
                print(f"Streaming error: {chunk['error']}")
                break
        
        print(f"Streaming finished. Waiting for {audio_chunks_queued} audio chunks to complete...")
        
        # Signal audio worker to stop after processing all chunks
        audio_queue.put(None)
        
        # Wait for all audio chunks to be processed
        audio_queue.join()
        
        # Wait for audio thread to complete with longer timeout
        if audio_thread and audio_thread.is_alive():
            print("Waiting for audio playback to complete...")
            audio_thread.join(timeout=60)  # Much longer timeout
            
        print("All audio playback completed")
        return full_response.strip()
        
    except Exception as e:
        print(f"Streaming error: {e}")
        # Fallback to non-streaming request
        print("Falling back to non-streaming API...")
        response = await send_request(chat_request)
        response.raise_for_status()
        response_data = response.json()
        
        if "error" in response_data:
            print("Error from fallback API:", response_data["error"])
            return None
        else:
            # Handle fallback response
            clean_response = remove_nonstandard(response_data["response"])
            if "audio_base64" in response_data:
                play_audio_chunk(response_data["audio_base64"])
            else:
                speak_text(clean_response)
            return clean_response


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

            # Build chat history and send to streaming API
            messages.append({"role": "user", "content": text})
            chat_request = {
                "model": LLM_MODEL,
                "messages": messages
            }
            
            try:
                # Use streaming response handler
                clean_response = await handle_streaming_response(chat_request)
                
                if clean_response:
                    clean_response = remove_nonstandard(clean_response)
                    print("Final Response:", clean_response)
                    
                    messages.append({
                        "role": "assistant", 
                        "content": clean_response
                    })
                else:
                    print("No response received")
                    
            except Exception as e:
                print("Error:", str(e))

if __name__ == "__main__":
    asyncio.run(main())