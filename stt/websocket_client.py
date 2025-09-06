#!/usr/bin/env python3
"""
WebSocket client for Mr. Bones pirate voice assistant with streaming TTS.
Connects to the Flask-SocketIO server for real-time chat with streaming audio.
"""

import os
import sys
import json
import asyncio
import base64
import tempfile
import subprocess
import queue
import threading
import time
import signal
from urllib.parse import urlparse
import socketio
import dotenv
import aiohttp

import stt

dotenv.load_dotenv()

# Audio Configuration
SPEECH_RATE = os.getenv("SPEECH_RATE", "200")
AUDIO_PLAYER = os.getenv("AUDIO_PLAYER", "afplay")

# Performance Settings
TIMEOUT = int(os.getenv("TIMEOUT", "90"))
WAIT_INTERVAL = int(os.getenv("WAIT_INTERVAL", "3"))

class StreamingAudioPlayer:
    """Handles streaming audio playback with proper queueing."""
    
    def __init__(self, audio_player="afplay"):
        self.audio_player = audio_player
        self.audio_queue = queue.Queue()
        self.playback_thread = None
        self.stop_playback = False
        self.current_request_id = None
        self.chunks_received = {}
        self.next_sequence = 0
        self.total_chunks = 0
        
    def start_playback_thread(self):
        """Start the audio playback worker thread."""
        if self.playback_thread is None or not self.playback_thread.is_alive():
            self.stop_playback = False
            self.playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
            self.playback_thread.start()
    
    def _playback_worker(self):
        """Worker thread for sequential audio playback."""
        while not self.stop_playback:
            try:
                # Check if we have the next expected chunk
                if self.next_sequence in self.chunks_received:
                    audio_data = self.chunks_received.pop(self.next_sequence)
                    print(f"🔊 Playing chunk {self.next_sequence + 1}/{self.total_chunks}")
                    self._play_audio_chunk(audio_data)
                    self.next_sequence += 1
                    print(f"✅ Completed chunk {self.next_sequence}/{self.total_chunks}")
                    
                    # Check if we're done
                    if self.next_sequence >= self.total_chunks:
                        print(f"✅ All chunks played!")
                        break
                else:
                    # Wait a bit for the next chunk
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"❌ Error in playback worker: {e}")
                import traceback
                traceback.print_exc()
    
    def _play_audio_chunk(self, audio_data: bytes):
        """Play a single audio chunk."""
        # Validate that we have actual audio data
        if not audio_data or len(audio_data) < 100:  # MP3 files should be at least 100 bytes
            print(f"⚠️ Skipping invalid audio chunk: {len(audio_data)} bytes")
            return
        
        # Check for basic MP3 header (starts with ID3 or 0xFF 0xFB)
        if not (audio_data[:3] == b'ID3' or (len(audio_data) >= 2 and audio_data[0] == 0xFF and (audio_data[1] & 0xE0) == 0xE0)):
            print(f"⚠️ Skipping non-MP3 data: {audio_data[:10].hex()}")
            return
            
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file.flush()  # Ensure data is written to disk
            temp_filename = temp_file.name
        
        try:
            result = subprocess.run([self.audio_player, temp_filename], 
                                  capture_output=True, timeout=10)
            if result.returncode != 0:
                print(f"❌ Audio playback failed: {result.stderr.decode() if result.stderr else 'Unknown error'}")
        except subprocess.TimeoutExpired:
            print("⏰ Audio playback timeout")
        except subprocess.CalledProcessError as e:
            print(f"❌ Audio playback error: {e}")
        except Exception as e:
            print(f"❌ Unexpected playback error: {e}")
        finally:
            try:
                os.unlink(temp_filename)
            except:
                pass
    
    def start_stream(self, request_id: str, total_chunks: int):
        """Start a new audio stream."""
        self.current_request_id = request_id
        self.total_chunks = total_chunks
        self.chunks_received.clear()
        self.next_sequence = 0
        self.start_playback_thread()
        print(f"🎵 Started audio stream: {total_chunks} chunks expected")
    
    def add_chunk(self, sequence: int, audio_data: bytes, request_id: str):
        """Add an audio chunk to the stream."""
        if request_id != self.current_request_id:
            print(f"⚠️ Ignoring chunk from different request: {request_id}")
            return
            
        self.chunks_received[sequence] = audio_data
        print(f"📥 Received chunk {sequence + 1}/{self.total_chunks}")
    
    def complete_stream(self, request_id: str):
        """Mark the stream as complete."""
        if request_id != self.current_request_id:
            return
            
        # Wait for all chunks to be played
        while self.next_sequence < self.total_chunks and not self.stop_playback:
            time.sleep(0.1)
        
        print(f"✅ Audio stream complete")
    
    def play_single_audio(self, audio_b64: str):
        """Play a single audio file (fallback mode)."""
        try:
            audio_data = base64.b64decode(audio_b64)
            self._play_audio_chunk(audio_data)
        except Exception as e:
            print(f"❌ Error playing fallback audio: {e}")

class PirateWebSocketClient:
    """WebSocket client for the pirate voice assistant."""
    
    def __init__(self, server_url: str, model: str):
        self.server_url = server_url
        self.model = model
        self.sio = socketio.AsyncClient()
        self.audio_player = StreamingAudioPlayer(AUDIO_PLAYER)
        self.conversation_history = []
        self.audio_playing = False
        self.waiting_for_response = False
        self.partial_chunks = {}  # For assembling multi-part chunks
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        # Register event handlers
        self.sio.on('connect', self._on_connect)
        self.sio.on('disconnect', self._on_disconnect)
        self.sio.on('connected', self._on_connected)
        self.sio.on('text_response', self._on_text_response)
        self.sio.on('audio_start', self._on_audio_start)
        self.sio.on('chunk_data', self._on_chunk_data)
        self.sio.on('audio_complete', self._on_audio_complete)
        self.sio.on('audio_complete_fallback', self._on_audio_complete_fallback)
        self.sio.on('audio_error', self._on_audio_error)
        self.sio.on('error', self._on_error)
        self.sio.on('test_event', self._on_test_event)
        self.sio.on('simple_test', self._on_simple_test)
        
        # Debug: Register a catch-all event handler to see ALL events
        @self.sio.event
        async def generic_event_handler(event_name, *args):
            print(f"🔍 CLIENT: Received event '{event_name}' with {len(args) if args else 0} args")
            if args and len(args) > 0:
                print(f"🔍 CLIENT: First arg type: {type(args[0])}, content preview: {str(args[0])[:200]}...")
                
            # If it's chunk_data and our dedicated handler isn't working, process it here
            if event_name == 'chunk_data':
                print(f"🚨 CLIENT: MANUAL chunk_data processing via catch-all!")
                if args and len(args) > 0:
                    await self._on_audio_chunk(args[0])
        
        print("✅ CLIENT: All WebSocket event handlers registered")
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt from file."""
        prompt_file = os.getenv("PROMPT_FILE", "prompt.txt")
        if not os.path.isfile(prompt_file):
            print(f"Error: Prompt file '{prompt_file}' not found.")
            sys.exit(1)
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    async def _on_connect(self):
        """Handle successful connection."""
        print("🔌 Connected to pirate server!")
        print(f"🔍 CLIENT: My socket ID is: {self.sio.sid}")
    
    async def _on_disconnect(self):
        """Handle disconnection."""
        print("🔌 Disconnected from pirate server")
    
    async def _on_connected(self, data):
        """Handle connection confirmation."""
        print(f"✅ {data.get('status', 'Connected')}")
    
    async def _on_text_response(self, data):
        """Handle text response from LLM."""
        text = data.get('text', '')
        request_id = data.get('request_id', 'unknown')
        print(f"🤖 [{request_id}] Mr. Bones says: {text}")
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": text
        })
    
    async def _on_audio_start(self, data):
        """Handle start of audio stream."""
        total_chunks = data.get('total_chunks', 0)
        request_id = data.get('request_id', 'unknown')
        self.audio_playing = True
        self.audio_player.start_stream(request_id, total_chunks)
    
    async def _on_chunk_data(self, data):
        """Handle chunk_data events specifically."""
        print(f"📡 CLIENT: Received chunk_data event! Data: {data}")
        await self._on_audio_chunk(data)
    
    async def _on_audio_chunk(self, data):
        """Handle incoming audio chunk."""
        try:
            print(f"🔊 CLIENT: _on_audio_chunk called! Data type: {type(data)}")
            print(f"🔊 CLIENT: Received audio_chunk event! Data keys: {list(data.keys()) if hasattr(data, 'keys') else 'No keys'}")
            
            if not data:
                print("❌ CLIENT: Empty data received in audio_chunk")
                return
            
            sequence = data.get('sequence', 0)
            request_id = data.get('request_id', 'unknown')
            chunk_data = data.get('data', '')
            
            # Check if this is a multi-part chunk
            if 'part' in data:
                part = data.get('part', 0)
                total_parts = data.get('total_parts', 1)
                is_complete = data.get('is_complete', False)
                
                print(f"🔊 CLIENT: Multi-part chunk - seq={sequence}, part={part}/{total_parts}, complete={is_complete}")
                
                # Initialize chunk assembly if needed
                chunk_key = f"{request_id}_{sequence}"
                if chunk_key not in self.partial_chunks:
                    self.partial_chunks[chunk_key] = {'parts': {}, 'total_parts': total_parts}
                
                # Store this part
                self.partial_chunks[chunk_key]['parts'][part] = chunk_data
                
                # Check if we have all parts
                if len(self.partial_chunks[chunk_key]['parts']) == total_parts:
                    # Reassemble the complete base64 data
                    audio_b64 = ''
                    for i in range(total_parts):
                        audio_b64 += self.partial_chunks[chunk_key]['parts'][i]
                    
                    # Clean up partial data
                    del self.partial_chunks[chunk_key]
                    
                    print(f"🔊 CLIENT: Reassembled chunk {sequence}: {len(audio_b64)} chars")
                else:
                    print(f"🔊 CLIENT: Partial chunk stored: {len(self.partial_chunks[chunk_key]['parts'])}/{total_parts} parts")
                    return  # Wait for more parts
                    
            else:
                # Single-part chunk
                audio_b64 = chunk_data
                print(f"🔊 CLIENT: Single-part chunk - seq={sequence}, b64_len={len(audio_b64)}")
            
            if not audio_b64:
                print(f"❌ CLIENT: Empty base64 data in chunk {sequence}")
                return
            
            try:
                audio_data = base64.b64decode(audio_b64)
                print(f"📦 Chunk {sequence}: {len(audio_data)} bytes, base64: {len(audio_b64)} chars")
                
                # Basic validation of decoded data
                if len(audio_data) > 0:
                    self.audio_player.add_chunk(sequence, audio_data, request_id)
                    print(f"✅ CLIENT: Chunk {sequence} added to audio player")
                else:
                    print(f"⚠️ CLIENT: Empty chunk {sequence} - skipping")
                    
            except Exception as decode_error:
                print(f"❌ CLIENT: Failed to decode chunk {sequence}: {decode_error}")
                return
            
        except Exception as e:
            print(f"❌ CRITICAL: Error in _on_audio_chunk: {e}")
            import traceback
            traceback.print_exc()
    
    async def _on_audio_complete(self, data):
        """Handle completion of audio stream."""
        request_id = data.get('request_id', 'unknown')
        self.audio_player.complete_stream(request_id)
        self.audio_playing = False
        self.waiting_for_response = False
    
    async def _on_audio_complete_fallback(self, data):
        """Handle fallback audio (single file)."""
        audio_b64 = data.get('audio_base64', '')
        request_id = data.get('request_id', 'unknown')
        print(f"🔊 [{request_id}] Playing fallback audio...")
        
        self.audio_playing = True
        # Play audio and wait for completion
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.audio_player.play_single_audio, audio_b64)
        self.audio_playing = False
        self.waiting_for_response = False
        print(f"✅ [{request_id}] Fallback audio playback complete")
    
    async def _on_audio_error(self, data):
        """Handle audio generation error."""
        error = data.get('error', 'Unknown audio error')
        request_id = data.get('request_id', 'unknown')
        print(f"❌ [{request_id}] Audio error: {error}")
        self.waiting_for_response = False
    
    async def _on_error(self, data):
        """Handle general errors."""
        error = data.get('error', 'Unknown error')
        request_id = data.get('request_id', 'unknown')
        print(f"❌ [{request_id}] Server error: {error}")
        self.waiting_for_response = False
    
    async def _on_test_event(self, data):
        """Handle test event for debugging."""
        message = data.get('message', 'No message')
        request_id = data.get('request_id', 'unknown')
        print(f"🧪 [{request_id}] TEST EVENT RECEIVED: {message}")
    
    async def _on_simple_test(self, data):
        """Handle simple test event for debugging."""
        message = data.get('message', 'No message')
        request_id = data.get('request_id', 'unknown')
        print(f"🧪 [{request_id}] SIMPLE TEST EVENT RECEIVED: {message}")
    
    async def connect(self):
        """Connect to the WebSocket server."""
        try:
            await self.sio.connect(self.server_url)
            return True
        except Exception as e:
            print(f"❌ Failed to connect to {self.server_url}: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        await self.sio.disconnect()
    
    async def send_message(self, message: str):
        """Send a chat message to the server."""
        print(f"📤 Sending: {message}")
        
        # Mark that we're waiting for a response
        self.waiting_for_response = True
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user", 
            "content": message
        })
        
        # Build full message history with system prompt
        messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
        
        # Send to server
        await self.sio.emit('chat', {
            'messages': messages,
            'model': self.model
        })
    
    async def listen_and_respond(self):
        """Main conversation loop with speech-to-text."""
        print("🎤 Starting voice conversation loop...")
        print("🗣️  Say something to Mr. Bones!")
        
        while True:
            try:
                # Get speech input
                print("\n👂 Listening for speech...")
                
                # Run STT in thread with timeout to make it interruptible
                loop = asyncio.get_event_loop()
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, stt.transcribe), 
                        timeout=30.0  # 30 second timeout for each transcription attempt
                    )
                except asyncio.TimeoutError:
                    print("⏰ Transcription timeout, trying again...")
                    continue
                
                if result is None or result[0] is None:
                    print("❌ No valid transcription, trying again...")
                    await self.speak_text("Sorry matey, I didn't catch that. Could you speak up?")
                    continue
                
                text, confidence = result
                print(f"🎤 Transcribed: '{text}' (confidence: {confidence})")
                
                if text.strip():
                    await self.send_message(text)
                    
                    # Wait for complete response (both text and audio) before listening again
                    print("⏳ Waiting for Mr. Bones to finish speaking...")
                    timeout_counter = 0
                    max_timeout = 300  # 30 seconds timeout (300 * 0.1s)
                    while (self.waiting_for_response or self.audio_playing) and timeout_counter < max_timeout:
                        await asyncio.sleep(0.1)
                        timeout_counter += 1
                    
                    if timeout_counter >= max_timeout:
                        print("⏰ Response timeout - continuing...")
                        self.waiting_for_response = False
                        self.audio_playing = False
                    
                    print("✅ Ready for next question!")
                    
            except KeyboardInterrupt:
                print("\n👋 Shutting down...")
                break
            except Exception as e:
                print(f"❌ Error in conversation loop: {e}")
                await asyncio.sleep(1)
    
    async def speak_text(self, text: str):
        """Speak text using system TTS (for feedback)."""
        try:
            # Run in thread to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._speak_text_sync, text)
        except Exception as e:
            print(f"❌ TTS error: {e}")
    
    def _speak_text_sync(self, text: str):
        """Synchronous TTS function."""
        subprocess.run(["say", "-r", SPEECH_RATE, text], 
                      capture_output=True, check=True)

def validate_environment():
    """Validate WebSocket client environment."""
    errors = []
    
    # Required variables
    api_url = os.getenv("API_URL")
    if not api_url:
        errors.append("Missing API_URL: WebSocket server URL")
    
    model = os.getenv("LLM_MODEL") 
    if not model:
        errors.append("Missing LLM_MODEL: Model to use for chat")
    
    # Validate audio player
    audio_player = os.getenv("AUDIO_PLAYER", "afplay")
    try:
        subprocess.run([audio_player, "--help"], capture_output=True, check=False)
    except FileNotFoundError:
        errors.append(f"Audio player not found: {audio_player}")
    
    # Validate STT dependencies
    vosk_model_path = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15")
    if not os.path.exists(vosk_model_path):
        errors.append(f"Vosk model not found: {vosk_model_path}")
    
    if errors:
        print("❌ Environment validation failed:")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)
    
    print("✅ WebSocket client environment validated")

def convert_http_to_ws(api_url: str) -> str:
    """Convert HTTP API URL to WebSocket URL."""
    parsed = urlparse(api_url)
    
    # Replace http/https with ws/wss
    if parsed.scheme == "http":
        ws_scheme = "ws"
    elif parsed.scheme == "https":
        ws_scheme = "wss"
    else:
        ws_scheme = "ws"  # Default
    
    # Build WebSocket URL
    ws_url = f"{ws_scheme}://{parsed.netloc}"
    
    return ws_url

async def check_health(api_url: str, max_attempts: int = 3, retry_delay: int = 10) -> bool:
    """Check the health endpoint with retries."""
    # Parse the URL and construct health endpoint
    parsed = urlparse(api_url)
    health_url = f"{parsed.scheme}://{parsed.netloc}/health"
    
    print(f"🏥 Checking API health at {health_url}")
    
    for attempt in range(1, max_attempts + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ API is healthy: {data.get('status', 'OK')}")
                        return True
                    else:
                        print(f"⚠️ Health check failed (attempt {attempt}/{max_attempts}): HTTP {response.status}")
        except aiohttp.ClientError as e:
            print(f"⚠️ Health check failed (attempt {attempt}/{max_attempts}): {e}")
        except asyncio.TimeoutError:
            print(f"⚠️ Health check timed out (attempt {attempt}/{max_attempts})")
        except Exception as e:
            print(f"⚠️ Health check error (attempt {attempt}/{max_attempts}): {e}")
        
        if attempt < max_attempts:
            print(f"⏱️ Waiting {retry_delay} seconds before retry...")
            await asyncio.sleep(retry_delay)
    
    print(f"❌ API health check failed after {max_attempts} attempts")
    return False

def signal_handler(signum, frame):
    """Handle Ctrl-C gracefully."""
    print(f"\n👋 Received signal {signum}, shutting down...")
    # Force exit if asyncio loop is stuck
    os._exit(0)

async def main():
    """Main function for WebSocket client."""
    validate_environment()
    
    api_url = os.getenv("API_URL")
    model = os.getenv("LLM_MODEL")
    
    # Check API health before connecting
    if not await check_health(api_url):
        print("❌ Unable to connect to API server. Please ensure the server is running.")
        sys.exit(1)
    
    # Convert HTTP URL to WebSocket URL
    ws_url = convert_http_to_ws(api_url)
    
    print(f"🌐 WebSocket Server: {ws_url}")
    print(f"🤖 LLM Model: {model}")
    print(f"🔊 Audio Player: {AUDIO_PLAYER}")
    
    client = PirateWebSocketClient(ws_url, model)
    
    try:
        # Connect to server
        if await client.connect():
            # Start conversation loop
            await client.listen_and_respond()
        else:
            print("❌ Failed to connect to server")
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        try:
            await client.disconnect()
        except:
            pass  # Ignore disconnect errors during shutdown

if __name__ == "__main__":
    # Install required packages
    try:
        import socketio
    except ImportError:
        print("❌ Missing python-socketio. Install with: pip install python-socketio[asyncio_client]")
        sys.exit(1)
    
    # Set up signal handlers for Ctrl-C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)