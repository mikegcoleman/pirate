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
import time

"""Streaming client for Mr. Bones, the pirate voice assistant.
Handles speech-to-text, streaming HTTP audio requests, and real-time chunked audio playback.
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
    
    # Validate numeric settings  
    try:
        int(os.getenv("TIMEOUT", "90"))
    except ValueError:
        errors.append("TIMEOUT must be a valid integer (seconds)")
    
    try:
        int(os.getenv("WAIT_INTERVAL", "3"))
    except ValueError:
        errors.append("WAIT_INTERVAL must be a valid integer (seconds)")
    
    # Validate audio player
    audio_player = os.getenv("AUDIO_PLAYER", "afplay")
    try:
        subprocess.run([audio_player, "--help"], capture_output=True, check=False)
    except FileNotFoundError:
        errors.append(f"Audio player not found: {audio_player}")
    
    if errors:
        print("❌ Environment validation failed:")
        for error in errors:
            print(f"  • {error}")
        print("\n💡 Please check your .env file and system configuration")
        sys.exit(1)
    else:
        print("✅ Environment validation passed")

# Validate environment on startup
validate_environment()

# Environment variables (now guaranteed to be valid)
API_URL = os.getenv("API_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

# Filler phrase counter for cycling through ElevenLabs audio files
filler_counter = 1


class StreamingAudioPlayer:
    """Manages streaming audio playback with queued chunks."""
    
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.play_thread = None
        self.stop_event = threading.Event()
    
    def start_playback(self):
        """Start the playback thread."""
        if self.play_thread and self.play_thread.is_alive():
            return
        
        self.stop_event.clear()
        self.play_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.play_thread.start()
    
    def stop_playback(self):
        """Stop the playback thread."""
        self.stop_event.set()
        if self.play_thread:
            self.play_thread.join(timeout=2)
    
    def add_audio_chunk(self, audio_base64: str, chunk_id: int):
        """Add an audio chunk to the playback queue."""
        try:
            audio_bytes = base64.b64decode(audio_base64)
            self.audio_queue.put((chunk_id, audio_bytes))
            print(f"🎵 Queued audio chunk {chunk_id} ({len(audio_bytes)} bytes)")
        except Exception as e:
            print(f"❌ Failed to decode audio chunk {chunk_id}: {e}")
    
    def _playback_worker(self):
        """Worker thread that plays audio chunks in sequence."""
        print("🔊 Audio playback worker started")
        
        while not self.stop_event.is_set():
            try:
                # Get next chunk (with timeout to check stop_event)
                chunk_id, audio_bytes = self.audio_queue.get(timeout=0.5)
                
                print(f"🔊 Playing audio chunk {chunk_id} ({len(audio_bytes)} bytes)")
                
                # Create temporary file and play
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                    tmp_file.write(audio_bytes)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                    
                    try:
                        # Play audio (blocking)
                        result = subprocess.run([AUDIO_PLAYER, tmp_file.name], 
                                                capture_output=True)
                        if result.returncode != 0:
                            print(f"⚠️ Audio player returned {result.returncode}")
                        else:
                            print(f"✅ Completed chunk {chunk_id}")
                    finally:
                        os.unlink(tmp_file.name)
                
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue  # Check stop_event and try again
            except Exception as e:
                print(f"❌ Error in audio playback: {e}")
    
    def wait_for_completion(self):
        """Wait for all queued audio to finish playing."""
        self.audio_queue.join()
        print("🎵 All audio chunks completed")


async def send_streaming_request(chat_request):
    """Send a chat request to the streaming API and handle chunked audio response.
    Args:
        chat_request (dict): The request payload for the LLM API.
    """
    # Handle both base URL and full endpoint URL formats
    if API_URL.endswith("/api/chat"):
        streaming_url = API_URL.replace("/api/chat", "/api/chat/stream")
    elif API_URL.endswith("/"):
        streaming_url = API_URL + "api/chat/stream"
    else:
        streaming_url = API_URL + "/api/chat/stream"
    print(f"\n🌐 === STREAMING API REQUEST ===")
    print(f"📡 Endpoint: {streaming_url}")
    print(f"🤖 Model: {chat_request.get('model', 'unknown')}")
    print(f"💬 Messages: {len(chat_request.get('messages', []))}")
    print(f"⏱️  Timeout: {TIMEOUT}s")
    
    audio_player = StreamingAudioPlayer()
    total_chunks = 0
    received_chunks = 0
    response_text = ""
    first_chunk_time = None
    
    try:
        async with httpx.AsyncClient() as client:
            print("🔗 Establishing streaming connection...")
            
            async with client.stream('POST', streaming_url, 
                                     json=chat_request, 
                                     timeout=TIMEOUT) as response:
                
                print(f"\n🌐 === STREAMING RESPONSE ===")
                print(f"📊 Status: {response.status_code}")
                print(f"🏷️  Content-Type: {response.headers.get('content-type', 'unknown')}")
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    print(f"❌ Stream error: {error_text.decode()}")
                    return None
                
                print("🚀 Starting streaming audio playback...")
                audio_player.start_playback()
                
                # Process streaming response
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])  # Remove "data: " prefix
                            
                            if data['type'] == 'metadata':
                                total_chunks = data['total_chunks']
                                response_text = data['text']
                                print(f"📋 Metadata: {total_chunks} chunks, text: {response_text[:50]}...")
                                
                            elif data['type'] == 'audio_chunk':
                                chunk_id = data['chunk_id']
                                audio_base64 = data['audio_base64']
                                text_chunk = data.get('text_chunk', '')
                                
                                if first_chunk_time is None:
                                    first_chunk_time = time.time()
                                    print(f"⚡ FIRST CHUNK RECEIVED - Ready to play!")
                                
                                print(f"📦 Received chunk {chunk_id}/{total_chunks}: '{text_chunk[:30]}...'")
                                audio_player.add_audio_chunk(audio_base64, chunk_id)
                                received_chunks += 1
                                
                            elif data['type'] == 'complete':
                                print(f"✅ Stream complete: {received_chunks}/{total_chunks} chunks received")
                                break
                                
                            elif data['type'] == 'error':
                                print(f"❌ Stream error: {data['message']}")
                                return None
                                
                        except json.JSONDecodeError as e:
                            print(f"⚠️ Failed to parse streaming data: {e}")
                            continue
                
                # Wait for all audio to finish playing
                print("⏳ Waiting for audio playback to complete...")
                audio_player.wait_for_completion()
                audio_player.stop_playback()
                
                if first_chunk_time:
                    print(f"⚡ PERFORMANCE: First audio started in {first_chunk_time - time.time():.2f}s!")
                
                return {
                    'response': response_text,
                    'chunks_received': received_chunks,
                    'total_chunks': total_chunks
                }
                
    except httpx.TimeoutException:
        print(f"⏱️ Request timed out after {TIMEOUT} seconds")
        audio_player.stop_playback()
        return None
    except httpx.ConnectError as e:
        print(f"🔌 Connection failed: {e}")
        audio_player.stop_playback()
        return None
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        audio_player.stop_playback()
        return None


def remove_nonstandard(text):
    """Remove non-standard characters to prevent TTS issues."""
    # Remove emojis and other non-standard characters
    return re.sub(r'[^\x00-\x7F]+', '', text)


def load_character_prompt():
    """Load the character prompt from prompt.txt file."""
    try:
        with open('prompt.txt', 'r') as file:
            prompt = file.read().strip()
            print("✅ Character prompt loaded successfully")
            return prompt
    except FileNotFoundError:
        print("❌ prompt.txt file not found")
        print("💡 Please ensure prompt.txt exists in the current directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading prompt: {e}")
        sys.exit(1)


def play_filler_phrase():
    """Play a random filler phrase from the ElevenLabs generated audio files.
    These are pre-generated phrases like 'Ahoy!', 'Arrr!', 'Thinking...' that
    play while waiting for the LLM response to make the character feel more alive.
    """
    global filler_counter
    
    # Use ElevenLabs generated filler audio files
    filler_file = f"audio/fillers/filler_{filler_counter:02d}.mp3"
    
    if os.path.exists(filler_file):
        print(f"🏴‍☠️ Playing filler phrase: {filler_file}")
        subprocess.run([AUDIO_PLAYER, filler_file], capture_output=True)
        
        # Cycle through available filler files (01-10)
        filler_counter = (filler_counter % 10) + 1
    else:
        print(f"⚠️ Filler file not found: {filler_file}")
        print("💡 Consider generating filler phrases with generate_filler_audio.py")


async def main():
    """Main conversation loop with streaming audio."""
    print("🏴‍☠️ Mr. Bones Streaming Voice Assistant Starting...")
    print("=" * 50)
    
    # Load character prompt
    system_prompt = load_character_prompt()
    
    # Initialize conversation
    messages = [{"role": "system", "content": system_prompt}]
    
    try:
        while True:
            print(f"\n{'='*20} NEW INTERACTION {'='*20}")
            
            # Get speech input
            with concurrent.futures.ThreadPoolExecutor() as executor:
                print("🎤 Listening for speech...")
                result = await loop.run_in_executor(executor, stt.transcribe)
                
            if result is None or result[0] is None:
                print("❌ No speech detected, trying again...")
                continue
            
            user_text, confidence = result
            print(f"🗣️ User said: '{user_text}' (confidence: {confidence})")
            
            # Add user message
            messages.append({"role": "user", "content": user_text})
            
            # Prepare API request
            chat_request = {
                "model": LLM_MODEL,
                "messages": messages
            }
            
            # Start request and play filler
            print("🎭 Starting response generation...")
            request_task = asyncio.create_task(send_streaming_request(chat_request))
            
            # Small delay then play filler
            await asyncio.sleep(0.3)  # 300ms natural response delay
            
            # Play filler phrase while streaming starts
            with concurrent.futures.ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, play_filler_phrase)
            
            # Wait for streaming response
            print("⏳ Waiting for streaming response...")
            response_data = await request_task
            
            if response_data:
                clean_response = remove_nonstandard(response_data["response"])
                print(f"🏴‍☠️ Mr. Bones: {clean_response}")
                print(f"📊 Performance: {response_data['chunks_received']}/{response_data['total_chunks']} chunks")
                
                messages.append({
                    "role": "assistant", 
                    "content": clean_response
                })
            else:
                print("❌ Failed to get response, trying again...")
                
    except KeyboardInterrupt:
        print("\n👋 Goodbye! Mr. Bones is going back to sleep...")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")


if __name__ == "__main__":
    # Required import for thread executor
    import concurrent.futures
    
    # Get the event loop
    loop = asyncio.get_event_loop()
    
    # Run the main function
    asyncio.run(main())