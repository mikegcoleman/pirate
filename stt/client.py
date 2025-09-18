#!/usr/bin/env python3
"""
Main Client for Raspberry Pi Pirate Project
Handles the full conversation loop: speech input → STT → LLM API → audio playback

Architecture:
1. Capture audio via USB microphone (using stt.py)
2. Convert speech to text via Vosk STT
3. Send text to LLM API for pirate response
4. Receive audio response from API
5. Play audio through Bluetooth speaker

Environment Variables:
- API_URL: LLM API endpoint
- LLM_MODEL: Model to use
- AUDIO_PLAYER: Audio player command (default: paplay)
- BLUETOOTH_SPEAKER: Optional Bluetooth speaker MAC address

Audio Routing Notes:
- Use `pactl set-default-sink "bluez_output.24_F4_95_F4_CA_45.1"` to force Bluetooth speaker
- Use `pactl set-default-source "alsa_input.usb-Antlion_Audio_Antlion_USB_Microphone-00.mono-fallback"` to force USB mic
"""

import stt
import subprocess
import os
import asyncio
import httpx
import sys
import json
import re
import base64
import tempfile
import queue
import threading
import time
from typing import Optional

# Load environment
import dotenv
dotenv.load_dotenv()

# Import skeleton controllers
try:
    from skeleton_movement import get_skeleton_controller, disconnect_skeleton
    from skeleton_setup import setup_skeleton_for_client
    SKELETON_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Skeleton integration disabled: {e}")
    SKELETON_AVAILABLE = False

# Audio Configuration
SPEECH_RATE = os.getenv("SPEECH_RATE", "200")
AUDIO_PLAYER = os.getenv("AUDIO_PLAYER", "paplay")
BLUETOOTH_SPEAKER = os.getenv("BLUETOOTH_SPEAKER")  # Optional Bluetooth speaker address
BLUETOOTH_PIN = os.getenv("BLUETOOTH_PIN", "1234")  # Bluetooth pairing PIN

# Performance Settings
TIMEOUT = int(os.getenv("TIMEOUT", "90"))
WAIT_INTERVAL = int(os.getenv("WAIT_INTERVAL", "3"))

# Skeleton Configuration
SKELETON_MOVEMENT_ENABLED = os.getenv("SKELETON_MOVEMENT_ENABLED", "true").lower() == "true"
SKELETON_MOVEMENT_COOLDOWN = int(os.getenv("SKELETON_MOVEMENT_COOLDOWN", "10"))

def validate_environment():
    """Validate all required environment variables and configuration."""
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
    audio_player = os.getenv("AUDIO_PLAYER", "paplay")
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

def play_wav_bytes(wav_bytes: bytes, sink_name: Optional[str] = None):
    """
    Play WAV audio bytes directly through PulseAudio.
    
    Args:
        wav_bytes: Raw WAV file bytes
        sink_name: Optional PulseAudio sink name (e.g., "bluez_output.24_F4_95_F4_CA_45.1")
                  If None, uses default sink.
    
    Returns:
        bool: True if playback succeeded, False otherwise
    """
    try:
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_file.write(wav_bytes)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            
            try:
                # Build paplay command with volume boost
                cmd = [AUDIO_PLAYER]
                if sink_name:
                    cmd.extend(["--device", sink_name])
                # Add volume boost for better audibility
                cmd.extend(["--volume", "65536"])  # Max volume
                cmd.append(tmp_file.name)
                
                # Play audio (blocking)
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    return True
                else:
                    print(f"❌ Audio playback failed (exit code {result.returncode})")
                    if result.stderr:
                        print(f"   Error: {result.stderr.strip()}")
                    return False
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_file.name)
                except OSError:
                    pass
                    
    except Exception as e:
        print(f"❌ Error playing WAV bytes: {e}")
        return False

def play_any_bytes(audio_bytes: bytes, sink_name: Optional[str] = None):
    """
    Play audio bytes of unknown format (MP3, OGG, Opus, etc.) by piping through FFmpeg to PulseAudio.
    
    Args:
        audio_bytes: Raw audio file bytes (any format supported by FFmpeg)
        sink_name: Optional PulseAudio sink name (e.g., "bluez_output.24_F4_95_F4_CA_45.1")
                  If None, uses default sink.
    
    Returns:
        bool: True if playback succeeded, False otherwise
    """
    try:
        # Build paplay command with volume boost
        paplay_cmd = [AUDIO_PLAYER]
        if sink_name:
            paplay_cmd.extend(["--device", sink_name])
        # Add volume boost for better audibility  
        paplay_cmd.extend(["--volume", "65536"])  # Max volume
        
        # Create pipeline: ffmpeg stdin → wav stdout → paplay stdin
        pipeline_cmd = [
            "bash", "-c",
            f"ffmpeg -hide_banner -loglevel error -i pipe:0 -f wav - | {' '.join(paplay_cmd)}"
        ]
        
        # Execute pipeline
        process = subprocess.Popen(
            pipeline_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False  # Binary data
        )
        
        # Feed audio bytes to FFmpeg and get result
        stdout, stderr = process.communicate(input=audio_bytes)
        
        if process.returncode == 0:
            return True
        else:
            print(f"❌ Audio pipeline failed (exit code {process.returncode})")
            if stderr:
                print(f"   Error: {stderr.decode().strip()}")
            return False
            
    except Exception as e:
        print(f"❌ Error playing audio bytes: {e}")
        return False

def connect_bluetooth_speaker():
    """Connect to Bluetooth speaker if configured."""
    if not BLUETOOTH_SPEAKER:
        print("🔊 No Bluetooth speaker configured")
        return True
    
    print(f"🔵 Connecting to Bluetooth speaker: {BLUETOOTH_SPEAKER}")
    
    try:
        # Check if bluetoothctl is available
        result = subprocess.run(["which", "bluetoothctl"], capture_output=True)
        if result.returncode != 0:
            print("❌ bluetoothctl not found - install bluez-utils")
            return False
        
        # First, try to connect (in case already paired)
        connect_cmd = f"echo 'connect {BLUETOOTH_SPEAKER}' | bluetoothctl"
        result = subprocess.run(connect_cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if "Connection successful" in result.stdout or "Already connected" in result.stdout:
            print("✅ Bluetooth speaker connected successfully")
            return True
        
        print(f"⚠️ Bluetooth connection may have failed")
        print(f"💡 Try pairing manually: bluetoothctl -> pair {BLUETOOTH_SPEAKER} -> PIN: {BLUETOOTH_PIN}")
        return False
            
    except subprocess.TimeoutExpired:
        print("⏱️ Bluetooth connection timed out")
        return False
    except Exception as e:
        print(f"❌ Bluetooth connection error: {e}")
        return False

class StreamingAudioPlayer:
    """Manages streaming audio playback with queued chunks using the new audio helpers."""
    
    def __init__(self, sink_name: Optional[str] = None):
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.play_thread = None
        self.stop_event = threading.Event()
        self.sink_name = sink_name
    
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
        """Worker thread that plays audio chunks in sequence using the new audio helpers."""
        print("🔊 Audio playback worker started")
        
        while not self.stop_event.is_set():
            try:
                # Get next chunk (with timeout to check stop_event)
                chunk_id, audio_bytes = self.audio_queue.get(timeout=0.5)
                
                print(f"🔊 Playing audio chunk {chunk_id} ({len(audio_bytes)} bytes)")
                
                # Try to determine if it's WAV or other format
                # WAV files start with "RIFF" magic bytes
                if audio_bytes.startswith(b'RIFF') and b'WAVE' in audio_bytes[:12]:
                    # It's a WAV file - use direct playback
                    success = play_wav_bytes(audio_bytes, self.sink_name)
                else:
                    # Unknown format - use FFmpeg pipeline
                    success = play_any_bytes(audio_bytes, self.sink_name)
                
                if success:
                    print(f"✅ Completed chunk {chunk_id}")
                else:
                    print(f"⚠️ Failed to play chunk {chunk_id}")
                
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue  # Check stop_event and try again
            except Exception as e:
                print(f"❌ Error in audio playback: {e}")
    
    def wait_for_completion(self):
        """Wait for all queued audio to finish playing."""
        self.audio_queue.join()
        print("🎵 All audio chunks completed")

async def send_streaming_request(chat_request, start_time=None):
    """Send a chat request to the streaming API and handle chunked audio response."""
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
    
    # Determine sink name for audio routing
    # If skeleton setup ran, it should have set the default sink correctly
    # Otherwise fall back to BLUETOOTH_SPEAKER env variable
    sink_name = None
    if BLUETOOTH_SPEAKER:
        # Convert MAC address to PulseAudio sink name format
        sink_name = f"bluez_output.{BLUETOOTH_SPEAKER.replace(':', '_')}.1"
        print(f"🔊 Audio routing to: {sink_name}")
    
    audio_player = StreamingAudioPlayer(sink_name=sink_name)
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
                if sink_name:
                    print(f"🔊 Audio routing to: {sink_name}")
                
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
                                    if start_time:
                                        time_to_first_audio = first_chunk_time - start_time
                                        print(f"⚡ FIRST AUDIO READY in {time_to_first_audio:.2f}s!")
                                    else:
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

async def main():
    """Main conversation loop with streaming audio."""
    print("🏴‍☠️ Mr. Bones Streaming Voice Assistant Starting...")
    print("=" * 50)
    
    # Set up skeleton connections (BLE + BT Classic audio)
    skeleton_controller = None
    if SKELETON_AVAILABLE and SKELETON_MOVEMENT_ENABLED:
        print("🤖 Setting up Mr. Bones skeleton connections...")
        try:
            # Run skeleton setup (BLE + BT Classic pairing)
            skeleton_ready = await setup_skeleton_for_client()
            
            if skeleton_ready:
                print("✅ Skeleton BLE and BT Classic audio setup complete!")
                
                # Initialize movement controller
                skeleton_controller = await get_skeleton_controller()
                if skeleton_controller.connected:
                    print("🎭 Mr. Bones skeleton movement enabled!")
                else:
                    print("⚠️ Skeleton setup complete but movement controller failed")
            else:
                print("❌ Skeleton setup failed - movement disabled")
                
        except Exception as e:
            print(f"⚠️ Skeleton setup error: {e}")
    elif not SKELETON_MOVEMENT_ENABLED:
        print("🤖 Skeleton movement disabled via configuration")
    
    # Note: Bluetooth speaker connection no longer needed - skeleton handles audio
    
    # Load character prompt
    system_prompt = load_character_prompt()
    
    # Initialize conversation
    messages = [{"role": "system", "content": system_prompt}]
    
    try:
        while True:
            print(f"\n{'='*20} NEW INTERACTION {'='*20}")
            
            # Get speech input using stt module
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                print("🎤 Listening for speech...")
                result = await asyncio.get_event_loop().run_in_executor(executor, stt.transcribe)
                
            if result is None or result[0] is None:
                print("❌ No speech detected, trying again...")
                continue
            
            user_text, confidence = result
            print(f"🗣️ User said: '{user_text}'")
            if confidence is not None:
                print(f"   Confidence: {confidence:.2f}")
            
            # Record start time for performance measurement
            start_time = time.time()
            
            # Add user message
            messages.append({"role": "user", "content": user_text})
            
            # Prepare API request
            chat_request = {
                "model": LLM_MODEL,
                "messages": messages
            }
            
            # Trigger skeleton movement when starting to speak
            if (SKELETON_MOVEMENT_ENABLED and 
                skeleton_controller and skeleton_controller.connected):
                try:
                    movement_triggered = await skeleton_controller.trigger_speech_movement()
                    if movement_triggered:
                        print("🎭 Mr. Bones movement triggered!")
                except Exception as e:
                    print(f"⚠️ Skeleton movement error: {e}")
            
            # Start request
            print("🎭 Starting response generation...")
            response_data = await send_streaming_request(chat_request, start_time)
            
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
    finally:
        # Cleanup skeleton connection
        if SKELETON_AVAILABLE:
            try:
                await disconnect_skeleton()
            except Exception as e:
                print(f"⚠️ Error disconnecting skeleton: {e}")

if __name__ == "__main__":
    asyncio.run(main())