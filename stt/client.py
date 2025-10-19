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
from functools import partial
from typing import Optional

# Import structured logging utilities
from logger_utils import (
    get_logger,
    generate_request_id,
    set_request_id,
    get_request_id,
    clear_request_id,
    add_request_id_header
)

# Import filler player for engaging audio during API delays
from filler_player import create_filler_player

# Import ambient player for continuous background audio
from ambient_player import create_ambient_player

# Load environment
import dotenv
dotenv.load_dotenv()

# Initialize structured logger
logger = get_logger("mr-bones-client")

# Import skeleton controllers
try:
    from skeleton_movement import get_skeleton_controller, disconnect_skeleton
    from skeleton_setup import setup_skeleton_for_client, disconnect_skeleton_connections
    SKELETON_AVAILABLE = True
except ImportError as e:
    logger.warn("Skeleton integration disabled", error=str(e))
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

# Filler Configuration
FILLER_ENABLED = os.getenv("FILLER_ENABLED", "true").lower() == "true"
POST_FILLER_DELAY = float(os.getenv("POST_FILLER_DELAY", "0.5"))  # Delay in seconds after filler stops

# Ambient Audio Configuration
AMBIENT_ENABLED = os.getenv("AMBIENT_ENABLED", "true").lower() == "true"
AMBIENT_VOLUME = float(os.getenv("AMBIENT_VOLUME", "0.3"))  # Background volume (0.0 to 1.0)

def validate_environment():
    """Validate all required environment variables and configuration."""
    errors = []
    logger.info("Environment validation starting")

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

    try:
        conv_length = int(os.getenv("CONVERSATION_LENGTH", "180"))
        if conv_length <= 0:
            errors.append("CONVERSATION_LENGTH must be greater than zero")
    except ValueError:
        errors.append("CONVERSATION_LENGTH must be a valid integer (seconds)")

    try:
        max_silence = int(os.getenv("MAX_SILENCE", "30"))
        if max_silence <= 0:
            errors.append("MAX_SILENCE must be greater than zero")
    except ValueError:
        errors.append("MAX_SILENCE must be a valid integer (seconds)")

    try:
        post_filler_delay = float(os.getenv("POST_FILLER_DELAY", "0.5"))
        if post_filler_delay < 0:
            errors.append("POST_FILLER_DELAY must be non-negative")
    except ValueError:
        errors.append("POST_FILLER_DELAY must be a valid number (seconds)")

    try:
        ambient_volume = float(os.getenv("AMBIENT_VOLUME", "0.3"))
        if not (0.0 <= ambient_volume <= 1.0):
            errors.append("AMBIENT_VOLUME must be between 0.0 and 1.0")
    except ValueError:
        errors.append("AMBIENT_VOLUME must be a valid number (0.0 to 1.0)")

    # Validate audio player
    audio_player = os.getenv("AUDIO_PLAYER", "paplay")
    try:
        subprocess.run([audio_player, "--help"], capture_output=True, check=False)
    except FileNotFoundError:
        errors.append(f"Audio player not found: {audio_player}")

    if errors:
        logger.error("Environment validation failed", error_count=len(errors))
        for error in errors:
            print(f"  • {error}")
        print("\n💡 Please check your .env file and system configuration")
        sys.exit(1)
    else:
        logger.info("Environment validation passed")

# Validate environment on startup
validate_environment()

# Environment variables (now guaranteed to be valid)
API_URL = os.getenv("API_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
CONVERSATION_LENGTH = max(1, int(os.getenv("CONVERSATION_LENGTH", "180")))
MAX_SILENCE = max(1, int(os.getenv("MAX_SILENCE", "30")))

CONVERSATION_CONCLUSION_PROMPTS = {
    "time_limit": (
        "In character as Mister Bones, let the guest know their three minutes are up, "
        "thank them for the chat, and invite the next matey to step forward."
    ),
    "silence": (
        "In character as Mister Bones, comment that no one seems to be around, say you are "
        "heading back to sleep, and gently invite them to wake you again later."
    ),
}

def _play_with_paplay(audio_bytes: bytes, sink_name: Optional[str] = None, suffix: str = ".tmp") -> bool:
    """Write audio bytes to a temp file and hand them directly to paplay."""
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            tmp_path = tmp_file.name

        cmd = [AUDIO_PLAYER]
        if sink_name:
            cmd.extend(["--device", sink_name])
        cmd.extend(["--volume", "65536"])  # Max volume
        if tmp_path is not None:
            cmd.append(tmp_path)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True

        print(f"❌ Audio playback failed (exit code {result.returncode})")
        if result.stderr:
            print(f"   Error: {result.stderr.strip()}")
        return False
    except Exception as exc:
        print(f"❌ Error playing audio bytes: {exc}")
        return False
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def play_wav_bytes(wav_bytes: bytes, sink_name: Optional[str] = None) -> bool:
    """Play WAV bytes using paplay."""
    return _play_with_paplay(wav_bytes, sink_name, suffix=".wav")


def play_any_bytes(audio_bytes: bytes, sink_name: Optional[str] = None) -> bool:
    """Play arbitrary audio bytes (e.g. MP3) using paplay directly."""
    return _play_with_paplay(audio_bytes, sink_name, suffix=".mp3")


async def play_conversation_conclusion(reason: str, system_prompt: str) -> None:
    """Play a closing line for the current conversation."""
    prompt_text = CONVERSATION_CONCLUSION_PROMPTS.get(reason)
    if not prompt_text:
        print(f"⚠️ No conclusion prompt configured for reason: {reason}")
        return

    chat_request = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text},
        ],
    }

    try:
        print(f"🕰️ Playing conversation closer for reason: {reason}")
        await send_streaming_request(
            chat_request,
            start_time=time.time(),
            sink_name_override=resolve_sink_name(),
            disable_filler=True
        )
    except Exception as exc:
        print(f"⚠️ Failed to play conversation conclusion ({reason}): {exc}")


def resolve_sink_name() -> Optional[str]:
    """Return the PulseAudio sink name for the configured Bluetooth speaker."""
    if BLUETOOTH_SPEAKER:
        return f"bluez_output.{BLUETOOTH_SPEAKER.replace(':', '_')}.1"
    return None

def setup_microphone():
    """Configure microphone volume and sensitivity settings."""
    mic_device = os.getenv("MIC_DEVICE", "")
    mic_volume = os.getenv("MIC_VOLUME", "150%")
    
    if not mic_device:
        print("🎤 No specific microphone configured, using system default")
        return True
    
    print(f"🎤 Setting up microphone: {mic_device}")
    print(f"🔊 Setting volume to: {mic_volume}")
    
    try:
        # Set microphone volume for better pickup at distance
        result = subprocess.run([
            "pactl", "set-source-volume", mic_device, mic_volume
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️ Could not set microphone volume: {result.stderr}")
            return False
        
        # Set as default input source
        result = subprocess.run([
            "pactl", "set-default-source", mic_device
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Microphone configured for improved distance pickup")
        else:
            print(f"⚠️ Could not set as default microphone: {result.stderr}")
        
        return True
        
    except Exception as e:
        print(f"⚠️ Error setting up microphone: {e}")
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
            print("⚠️ StreamingAudioPlayer thread already running")
            return
        
        self.is_playing = True
        self.stop_event.clear()
        self.play_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.play_thread.start()
        print("🔊 StreamingAudioPlayer thread started")
    
    def stop_playback(self):
        """Stop the playback thread."""
        self.stop_event.set()
        if self.play_thread:
            self.play_thread.join(timeout=2)
        self.is_playing = False
        print("🔊 StreamingAudioPlayer stopped")
    
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
        chunks_played = 0
        
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
                    chunks_played += 1
                    print(f"✅ Completed chunk {chunk_id} (total played: {chunks_played})")
                else:
                    print(f"⚠️ Failed to play chunk {chunk_id}")
                
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue  # Check stop_event and try again
            except Exception as e:
                print(f"❌ Error in audio playback: {e}")
        
        print(f"🔊 Audio playback worker finished (played {chunks_played} chunks)")
    
    def wait_for_completion(self):
        """Wait for all queued audio to finish playing."""
        self.audio_queue.join()
        print("🎵 All audio chunks completed")

async def send_streaming_request(chat_request, start_time=None, sink_name_override=None, disable_filler=False):
    """Send a chat request to the streaming API and handle chunked audio response."""
    # Get reqId from context (should be set at conversation turn start)
    req_id = get_request_id()

    # Handle both base URL and full endpoint URL formats
    if API_URL.endswith("/api/chat"):
        streaming_url = API_URL.replace("/api/chat", "/api/chat/stream")
    elif API_URL.endswith("/"):
        streaming_url = API_URL + "api/chat/stream"
    else:
        streaming_url = API_URL + "/api/chat/stream"

    logger.info("Streaming API request starting",
                endpoint=streaming_url,
                model=chat_request.get('model', 'unknown'),
                message_count=len(chat_request.get('messages', [])),
                timeout=TIMEOUT)
    
    # Determine sink name for audio routing
    # If skeleton setup ran, it should have set the default sink correctly
    # Otherwise fall back to BLUETOOTH_SPEAKER env variable
    sink_name = sink_name_override
    if not sink_name and BLUETOOTH_SPEAKER:
        # Convert MAC address to PulseAudio sink name format
        sink_name = f"bluez_output.{BLUETOOTH_SPEAKER.replace(':', '_')}.1"
        print(f"🔊 Audio routing to: {sink_name}")
    
    # Initialize filler player for engaging audio during API delays
    filler_player = None
    if FILLER_ENABLED and not disable_filler:
        filler_player = create_filler_player(AUDIO_PLAYER, sink_name)
        if filler_player:
            print("🎭 Filler player ready for engaging delays")
    
    audio_player = StreamingAudioPlayer(sink_name=sink_name)
    total_chunks = 0
    received_chunks = 0
    response_text = ""
    first_chunk_time = None
    
    try:
        # Prepare headers with request ID
        headers = {}
        add_request_id_header(headers, req_id)

        async with httpx.AsyncClient() as client:
            logger.debug("Establishing streaming connection", headers=headers)

            # Start filler playback while waiting for API response
            if filler_player and FILLER_ENABLED:
                logger.debug("Starting filler phrase during API processing")
                filler_player.start_filler()

            async with client.stream('POST', streaming_url,
                                     json=chat_request,
                                     headers=headers,
                                     timeout=TIMEOUT) as response:
                
                print(f"\n🌐 === STREAMING RESPONSE ===")
                print(f"📊 Status: {response.status_code}")
                print(f"🏷️  Content-Type: {response.headers.get('content-type', 'unknown')}")
                
                if response.status_code != 200:
                    # Wait for filler to complete naturally even on HTTP error
                    if filler_player and filler_player.is_filler_playing():
                        print("⏳ Waiting for filler to complete before handling HTTP error...")
                        while filler_player.is_filler_playing():
                            await asyncio.sleep(0.1)
                        print("✅ Filler completed")
                    
                    error_text = await response.aread()
                    print(f"❌ Stream error: {error_text.decode()}")
                    return None
                
                print("🚀 Starting streaming audio playback...")
                if sink_name:
                    print(f"🔊 Audio routing to: {sink_name}")
                
                audio_player.start_playback()
                print(f"🔊 StreamingAudioPlayer started: {audio_player.play_thread is not None}")
                
                # Process streaming response
                line_count = 0
                async for line in response.aiter_lines():
                    line_count += 1
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])  # Remove "data: " prefix
                            print(f"🔍 Line {line_count}: Received stream data type: {data.get('type', 'unknown')}")
                            
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
                                    
                                    # Wait for filler to complete naturally, then add pause
                                    if filler_player:
                                        print("⏳ Waiting for filler phrase to complete naturally...")
                                        while filler_player.is_filler_playing():
                                            await asyncio.sleep(0.1)  # Check every 100ms
                                        
                                        print("✅ Filler completed naturally")
                                        
                                        # Add natural pause after filler
                                        if POST_FILLER_DELAY > 0:
                                            print(f"⏸️ Natural pause: {POST_FILLER_DELAY}s")
                                            await asyncio.sleep(POST_FILLER_DELAY)
                                
                                print(f"📦 Received chunk {chunk_id}/{total_chunks}: '{text_chunk[:30]}...'")
                                audio_player.add_audio_chunk(audio_base64, chunk_id)
                                received_chunks += 1
                                print(f"🎵 Queue size after adding chunk: {audio_player.audio_queue.qsize()}")
                                
                            elif data['type'] == 'complete':
                                print(f"✅ Stream complete: {received_chunks}/{total_chunks} chunks received")
                                if received_chunks == 0:
                                    print("⚠️ WARNING: Stream completed but no audio chunks were received!")
                                    
                                    # Still wait for filler to complete naturally even if no audio chunks
                                    if filler_player and filler_player.is_filler_playing():
                                        print("⏳ Waiting for filler phrase to complete naturally...")
                                        while filler_player.is_filler_playing():
                                            await asyncio.sleep(0.1)
                                        print("✅ Filler completed naturally")
                                break
                                
                            elif data['type'] == 'error':
                                print(f"❌ Stream error: {data['message']}")
                                
                                # Wait for filler to complete even on error
                                if filler_player and filler_player.is_filler_playing():
                                    print("⏳ Waiting for filler to complete before handling error...")
                                    while filler_player.is_filler_playing():
                                        await asyncio.sleep(0.1)
                                    print("✅ Filler completed")
                                
                                return None
                                
                            elif data['type'] == 'chunk_error':
                                error_msg = data.get('message', 'Unknown chunk error')
                                chunk_id = data.get('chunk_id', 'unknown')
                                print(f"❌ Chunk {chunk_id} error: {error_msg}")
                                # Continue processing - don't fail the entire stream for chunk errors
                                
                            else:
                                print(f"⚠️ Unknown stream data type: {data['type']}")
                                print(f"   Data: {data}")
                                
                        except json.JSONDecodeError as e:
                            print(f"⚠️ Line {line_count}: Failed to parse as JSON: {line[:100]}...")
                            continue
                    else:
                        print(f"🔍 Line {line_count}: Non-data line: {line[:100]}...")
                
                # Wait for all audio to finish playing
                print("⏳ Waiting for audio playback to complete...")
                print(f"🔍 Audio player thread alive: {audio_player.play_thread and audio_player.play_thread.is_alive()}")
                print(f"🔍 Queue size before waiting: {audio_player.audio_queue.qsize()}")
                audio_player.wait_for_completion()
                audio_player.stop_playback()
                
                return {
                    'response': response_text,
                    'chunks_received': received_chunks,
                    'total_chunks': total_chunks
                }
                
    except httpx.TimeoutException:
        print(f"⏱️ Request timed out after {TIMEOUT} seconds")
        
        # Wait for filler to complete naturally even on timeout
        if filler_player and filler_player.is_filler_playing():
            print("⏳ Waiting for filler to complete before handling timeout...")
            while filler_player.is_filler_playing():
                await asyncio.sleep(0.1)
            print("✅ Filler completed")
        
        audio_player.stop_playback()
        return None
    except httpx.ConnectError as e:
        print(f"🔌 Connection failed: {e}")
        
        # Wait for filler to complete naturally even on connection error
        if filler_player and filler_player.is_filler_playing():
            print("⏳ Waiting for filler to complete before handling connection error...")
            while filler_player.is_filler_playing():
                await asyncio.sleep(0.1)
            print("✅ Filler completed")
        
        audio_player.stop_playback()
        return None
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        
        # Wait for filler to complete naturally even on unexpected error
        if filler_player and filler_player.is_filler_playing():
            print("⏳ Waiting for filler to complete before handling error...")
            while filler_player.is_filler_playing():
                await asyncio.sleep(0.1)
            print("✅ Filler completed")
        
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
    
    # Set up microphone for better distance pickup
    setup_microphone()
    
    # Initialize ambient audio player for continuous background audio
    ambient_player = None
    if AMBIENT_ENABLED:
        ambient_player = create_ambient_player(AUDIO_PLAYER, resolve_sink_name(), AMBIENT_VOLUME)
        if ambient_player:
            ambient_player.start_ambient()
            print(f"🌊 Ambient audio started at {AMBIENT_VOLUME*100:.0f}% volume")
        else:
            print("⚠️ Failed to initialize ambient audio - continuing without background sound")
    
    # Set up skeleton connections (assume services are already running)
    skeleton_controller = None
    if SKELETON_AVAILABLE and SKELETON_MOVEMENT_ENABLED:
        print("🤖 Checking for Mr. Bones skeleton connections...")
        try:
            # Verify BLE service is running (don't start it - should already be running)
            from skeleton_ble_service import service
            
            if not service.client or not service.client.is_connected:
                print("❌ FATAL: Skeleton BLE service not running!")
                print("💡 Start it first: python skeleton_ble_service.py")
                print("🚫 Exiting - BLE service must be running")
                sys.exit(1)
            else:
                print("✅ Skeleton BLE service already running")
                
            # Check if Classic BT audio device is connected
            print("🔍 Verifying Classic BT audio connection...")
            bt_check = subprocess.run(
                ["bluetoothctl", "info", "24:F4:95:F4:CA:45"],
                capture_output=True,
                text=True
            )
            
            if "Connected: yes" not in bt_check.stdout:
                print("❌ FATAL: Classic BT audio not connected!")
                print("💡 Run skeleton_bt_pair.py to pair the audio device")
                print("🚫 Exiting - no point running without audio")
                sys.exit(1)
            
            print("✅ Classic BT audio verified connected")
            
            # Initialize movement controller using the existing service's client
            skeleton_controller = await get_skeleton_controller()
            if skeleton_controller and skeleton_controller.connected:
                print("🎭 Mr. Bones skeleton movement enabled!")
            else:
                print("⚠️ Movement controller initialization failed")
                
        except Exception as e:
            print(f"❌ FATAL: Skeleton connection error: {e}")
            print("💡 Make sure both services are running:")
            print("  1. python skeleton_ble_service.py (keep running)")
            print("  2. python skeleton_bt_pair.py (run once)")
            print("🚫 Exiting - skeleton connections required")
            sys.exit(1)
    elif not SKELETON_MOVEMENT_ENABLED:
        print("🤖 Skeleton movement disabled via configuration")
    
    # Note: Bluetooth speaker connection no longer needed - skeleton handles audio
    
    # Load character prompt
    system_prompt = load_character_prompt()
    
    # Initialize conversation
    messages = [{"role": "system", "content": system_prompt}]

    loop = asyncio.get_running_loop()
    conversation_start = None
    conversation_deadline = None

    def reset_conversation():
        nonlocal messages, conversation_start, conversation_deadline
        was_active = conversation_start is not None or len(messages) > 1
        messages = [{"role": "system", "content": system_prompt}]
        conversation_start = None
        conversation_deadline = None
        if was_active:
            print("🧹 Conversation memory cleared.")

    async def conclude_and_reset(reason: str):
        if conversation_start is None:
            reset_conversation()
            return
        try:
            await play_conversation_conclusion(reason, system_prompt)
        except Exception as exc:
            print(f"⚠️ Unable to play {reason} outro: {exc}")
        finally:
            reset_conversation()

    reset_conversation()

    try:
        while True:
            print(f"\n{'='*20} NEW INTERACTION {'='*20}")

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                print("🎤 Listening for speech...")
                result = await loop.run_in_executor(
                    executor,
                    partial(stt.transcribe, max_silence=MAX_SILENCE),
                )

            if not result:
                print("❌ No speech detected, trying again...")
                continue

            user_text, confidence, reason = result

            if reason == "silence_timeout":
                if conversation_start is not None:
                    print("😴 No new question for a while. Wrapping up this chat.")
                    await conclude_and_reset("silence")
                else:
                    print("⌛ Still waiting for a matey to speak up...")
                    # Reset conversation timer so new visitors get full conversation
                    reset_conversation()
                continue

            if reason == "cancelled":
                print("🛑 Transcription cancelled by user. Exiting loop.")
                break

            if reason != "success" and user_text is None:
                print("❌ Transcription error, trying again...")
                continue

            if user_text is None:
                print("❌ No speech detected, trying again...")
                continue

            # Generate and set request ID for this conversation turn
            req_id = generate_request_id()
            set_request_id(req_id)

            logger.info("User speech transcribed", user_text=user_text, confidence=confidence)

            if conversation_start is None:
                conversation_start = time.time()
                conversation_deadline = conversation_start + CONVERSATION_LENGTH
                logger.info("Conversation timer started", limit_seconds=CONVERSATION_LENGTH)

            start_time = time.time()

            messages.append({"role": "user", "content": user_text})

            chat_request = {
                "model": LLM_MODEL,
                "messages": messages
            }

            if (SKELETON_MOVEMENT_ENABLED and
                skeleton_controller and skeleton_controller.connected):
                try:
                    movement_triggered = await skeleton_controller.trigger_speech_movement()
                    if movement_triggered:
                        print("🎭 Mr. Bones movement triggered!")
                except Exception as e:
                    print(f"⚠️ Skeleton movement error: {e}")

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

                if conversation_deadline and time.time() >= conversation_deadline:
                    print("⏰ Conversation time limit reached. Resetting memory.")
                    await conclude_and_reset("time_limit")
                    continue
            else:
                print("❌ Failed to get response, trying again...")

    except KeyboardInterrupt:
        print("\n👋 Goodbye! Mr. Bones is going back to sleep...")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
    finally:
        # Stop ambient audio
        if ambient_player:
            ambient_player.stop_ambient()
            print("🌊 Ambient audio stopped")
        
        # Note: Don't disconnect skeleton BLE service - it should stay running
        # for future client.py sessions and movement control
        if SKELETON_AVAILABLE:
            print("🔌 Leaving skeleton BLE service running for future sessions")

if __name__ == "__main__":
    asyncio.run(main())
