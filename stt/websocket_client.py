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
from urllib.parse import urlparse
import socketio
import dotenv

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
                    self._play_audio_chunk(audio_data)
                    self.next_sequence += 1
                    print(f"🔊 Played chunk {self.next_sequence}/{self.total_chunks}")
                else:
                    # Wait a bit for the next chunk
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"❌ Error in playback worker: {e}")
    
    def _play_audio_chunk(self, audio_data: bytes):
        """Play a single audio chunk."""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_filename = temp_file.name
        
        try:
            subprocess.run([self.audio_player, temp_filename], 
                          capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Audio playback error: {e}")
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
        
        # Register event handlers
        self.sio.on('connect', self._on_connect)
        self.sio.on('disconnect', self._on_disconnect)
        self.sio.on('connected', self._on_connected)
        self.sio.on('text_response', self._on_text_response)
        self.sio.on('audio_start', self._on_audio_start)
        self.sio.on('audio_chunk', self._on_audio_chunk)
        self.sio.on('audio_complete', self._on_audio_complete)
        self.sio.on('audio_complete_fallback', self._on_audio_complete_fallback)
        self.sio.on('audio_error', self._on_audio_error)
        self.sio.on('error', self._on_error)
    
    async def _on_connect(self):
        """Handle successful connection."""
        print("🔌 Connected to pirate server!")
    
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
        self.audio_player.start_stream(request_id, total_chunks)
    
    async def _on_audio_chunk(self, data):
        """Handle incoming audio chunk."""
        sequence = data.get('sequence', 0)
        audio_b64 = data.get('data', '')
        request_id = data.get('request_id', 'unknown')
        
        try:
            audio_data = base64.b64decode(audio_b64)
            self.audio_player.add_chunk(sequence, audio_data, request_id)
        except Exception as e:
            print(f"❌ Error processing audio chunk: {e}")
    
    async def _on_audio_complete(self, data):
        """Handle completion of audio stream."""
        request_id = data.get('request_id', 'unknown')
        self.audio_player.complete_stream(request_id)
    
    async def _on_audio_complete_fallback(self, data):
        """Handle fallback audio (single file)."""
        audio_b64 = data.get('audio_base64', '')
        request_id = data.get('request_id', 'unknown')
        print(f"🔊 [{request_id}] Playing fallback audio...")
        self.audio_player.play_single_audio(audio_b64)
    
    async def _on_audio_error(self, data):
        """Handle audio generation error."""
        error = data.get('error', 'Unknown audio error')
        request_id = data.get('request_id', 'unknown')
        print(f"❌ [{request_id}] Audio error: {error}")
    
    async def _on_error(self, data):
        """Handle general errors."""
        error = data.get('error', 'Unknown error')
        request_id = data.get('request_id', 'unknown')
        print(f"❌ [{request_id}] Server error: {error}")
    
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
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user", 
            "content": message
        })
        
        # Send to server
        await self.sio.emit('chat', {
            'message': message,
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
                
                # Run STT in thread to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, stt.transcribe)
                
                if result is None or result[0] is None:
                    print("❌ No valid transcription, trying again...")
                    await self.speak_text("Sorry matey, I didn't catch that. Could you speak up?")
                    continue
                
                text, confidence = result
                print(f"🎤 Transcribed: '{text}' (confidence: {confidence})")
                
                if text.strip():
                    await self.send_message(text)
                    
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

async def main():
    """Main function for WebSocket client."""
    validate_environment()
    
    api_url = os.getenv("API_URL")
    model = os.getenv("LLM_MODEL")
    
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
    finally:
        await client.disconnect()

if __name__ == "__main__":
    # Install required packages
    try:
        import socketio
    except ImportError:
        print("❌ Missing python-socketio. Install with: pip install python-socketio[asyncio_client]")
        sys.exit(1)
    
    asyncio.run(main())