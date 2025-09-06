import os
import json
import requests
from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import signal
import sys
import tempfile
import base64
import wave
import uuid
from dotenv import load_dotenv
import logging
from datetime import datetime
from abc import ABC, abstractmethod
import re
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables first to check TTS provider
load_dotenv()

# Conditional imports based on TTS provider
tts_provider_name = os.getenv("TTS_PROVIDER", "kokoro").lower()
if tts_provider_name == "kokoro":
    try:
        from kokoro import KPipeline
        import torch
        KOKORO_AVAILABLE = True
    except ImportError:
        KOKORO_AVAILABLE = False
        print("⚠️  Kokoro TTS not available - install with: pip install kokoro")
else:
    KOKORO_AVAILABLE = False


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
    
def handle_shutdown(signum, frame):
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    os._exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

app = Flask(__name__)
# WebSocket configuration for chunked audio streaming
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# GPU detection (only if torch is available)
try:
    import torch
    use_gpu = torch.cuda.is_available()
except ImportError:
    use_gpu = False

# TTS Provider Classes
class TTSProvider(ABC):
    """Abstract base class for TTS providers"""
    
    @abstractmethod
    def generate_audio(self, text: str) -> str:
        """Generate audio and return base64 encoded WAV data"""
        pass

class KokoroTTSProvider(TTSProvider):
    """Kokoro TTS Provider (local)"""
    
    def __init__(self):
        if not KOKORO_AVAILABLE:
            raise ImportError("Kokoro TTS not available. Install with: pip install kokoro")
        
        model_path = os.getenv("KOKORO_MODEL_PATH", "./models/kokoro/model.onnx")
        voices_path = os.getenv("KOKORO_VOICES_PATH", "./models/kokoro/voices-v1.0.bin")
        
        # Create models directory if it doesn't exist
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Initialize Kokoro TTS with GPU support
        device = 'cuda' if use_gpu else 'cpu'
        self.tts_engine = KPipeline(lang_code='a', device=device, repo_id='hexgrad/Kokoro-82M')
        
        if use_gpu:
            print("✅ Kokoro TTS: Using GPU acceleration")
        else:
            print("✅ Kokoro TTS: Using CPU")
    
    def generate_audio(self, text: str) -> str:
        """Generate audio using Kokoro TTS"""
        try:
            import soundfile as sf
            import numpy as np
        except ImportError:
            raise ImportError("soundfile required for Kokoro TTS. Install with: pip install soundfile")
        
        # Use Kokoro TTS with valid voice
        # Using af_heart as shown in the error message example
        generator = self.tts_engine(
            text, 
            voice="af_heart",
            speed=0.95
        )
        audio_tensor = None
        for i, (gs, ps, audio) in enumerate(generator):
            audio_tensor = audio
            break  # Take the first audio chunk
        
        if audio_tensor is None:
            raise Exception("No audio generated")
        
        # Convert tensor to numpy if needed
        if hasattr(audio_tensor, 'cpu'):
            audio_np = audio_tensor.cpu().numpy()
        else:
            audio_np = np.array(audio_tensor)
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
            temp_path = tmp_audio.name
        
        try:
            # Write audio to temp file (file handle is now closed)
            sf.write(temp_path, audio_np.squeeze(), 24000)
            
            # Read the WAV file and encode as base64
            with open(temp_path, 'rb') as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                # Ignore cleanup errors on Windows
                pass
        
        return audio_base64

class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS Provider (cloud)"""
    
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        
        if not self.api_key or not self.voice_id:
            raise ValueError("ElevenLabs API key and voice ID must be set in environment variables")
        
        print(f"✅ ElevenLabs TTS: Initialized with voice ID {self.voice_id}")
    
    def generate_audio(self, text: str) -> str:
        """Generate audio using ElevenLabs API"""
        try:
            from elevenlabs import ElevenLabs
        except ImportError:
            raise ImportError("elevenlabs package not installed. Run: pip install elevenlabs")
        
        # Initialize ElevenLabs client
        client = ElevenLabs(api_key=self.api_key)
        
        # Generate audio using ElevenLabs
        audio_generator = client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id="eleven_monolingual_v1"
        )
        
        # Collect audio data from generator
        audio_data = b""
        for chunk in audio_generator:
            audio_data += chunk
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
            tmp_audio.write(audio_data)
            tmp_audio.flush()
            temp_path = tmp_audio.name
        
        try:
            # Read and encode as base64 (file handle is now closed)
            with open(temp_path, 'rb') as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                # Ignore cleanup errors on Windows
                pass
        
        return audio_base64

class ElevenLabsStreamingTTSProvider:
    """ElevenLabs Streaming TTS Provider for WebSocket"""
    
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        
        if not self.api_key or not self.voice_id:
            raise ValueError("ElevenLabs API key and voice ID must be set for streaming TTS")
        
        print(f"✅ ElevenLabs Streaming TTS: Initialized with voice ID {self.voice_id}")
    
    def get_first_chunk(self, text: str) -> tuple[str, str]:
        """Get the first sentence/chunk for ultra-fast start."""
        import re
        # Find first sentence end
        match = re.search(r'^.*?[.!?]\s*', text)
        if match:
            first = match.group(0).strip()
            remaining = text[len(first):].strip()
            return first, remaining
        else:
            # No sentence boundary, take first ~50 chars at word boundary
            if len(text) > 50:
                split_point = text.rfind(' ', 0, 50)
                if split_point > 20:  # Ensure meaningful chunk
                    return text[:split_point], text[split_point:].strip()
            return text, ""
    
    def chunk_remaining_text(self, text: str, max_chunk_size: int = 80) -> list[str]:
        """Split remaining text into chunks optimized for speed."""
        if not text:
            return []
            
        chunks = []
        words = text.split()
        current_chunk = ""
        
        for word in words:
            if len(current_chunk + " " + word) < max_chunk_size:
                current_chunk += " " + word if current_chunk else word
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def text_to_speech_chunk(self, text: str) -> bytes:
        """Convert text chunk to MP3 audio data."""
        # Check if mock TTS mode is enabled
        mock_tts_mode = os.getenv('MOCK_TTS_MODE', 'false').lower() == 'true'
        if mock_tts_mode:
            # Generate fake audio data (much smaller for WebSocket compatibility)
            # Limit to ~1KB per chunk to avoid WebSocket size issues
            fake_audio_size = min(len(text) * 20, 1000)  # Max 1KB chunks
            fake_audio_data = b'FAKE_AUDIO_' + text.encode('utf-8') + b'_' + b'X' * fake_audio_size
            return fake_audio_data
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.4,
                "style": 0.0,
                "use_speaker_boost": False
            },
            "optimize_streaming_latency": 4
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"ElevenLabs API error: {response.status_code} - {response.text}")
        
        return response.content
    
    def emit_large_audio_chunk(self, audio_b64: str, sequence: int, socket_id: str, request_id: str, max_chunk_size: int = 200):
        """Split large base64 audio data into WebSocket-safe chunks and emit them."""
        # If data is small enough, emit normally
        if len(audio_b64) <= max_chunk_size:
            socketio.emit('chunk_data', {
                'sequence': sequence,
                'data': audio_b64,
                'request_id': request_id,
                'is_complete': True
            }, room=socket_id)
            logger.info(f"[{request_id}] ✅ Single chunk emitted: seq={sequence}, size={len(audio_b64)} chars")
            return
        
        # Split large data into smaller chunks
        chunks = []
        for i in range(0, len(audio_b64), max_chunk_size):
            chunk = audio_b64[i:i + max_chunk_size]
            chunks.append(chunk)
        
        logger.info(f"[{request_id}] 📦 Splitting large audio into {len(chunks)} WebSocket chunks (seq={sequence})")
        
        # Emit each sub-chunk
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            socketio.emit('chunk_data', {
                'sequence': sequence,
                'part': i,
                'data': chunk,
                'request_id': request_id,
                'is_complete': is_last,
                'total_parts': len(chunks)
            }, room=socket_id)
            logger.info(f"[{request_id}] ✅ Sub-chunk emitted: seq={sequence}, part={i}/{len(chunks)}, size={len(chunk)} chars")

    def generate_streaming_audio(self, text: str, socket_id: str, request_id: str):
        """Generate streaming audio chunks and emit via WebSocket with ultra-fast first chunk."""
        try:
            # Use ultra-fast first chunk strategy
            first_chunk, remaining_text = self.get_first_chunk(text)
            remaining_chunks = self.chunk_remaining_text(remaining_text)
            
            total_chunks = 1 + len(remaining_chunks)
            logger.info(f"[{request_id}] 🎵 Ultra-fast chunking: first={len(first_chunk)} chars, remaining={len(remaining_chunks)} chunks")
            
            # Emit start signal
            socketio.emit('audio_start', {
                'total_chunks': total_chunks,
                'request_id': request_id
            }, room=socket_id)
            
            # DEBUG: Test if basic events work
            logger.info(f"[{request_id}] 🧪 Testing basic event emission to room {socket_id}")
            socketio.emit('test_event', {
                'message': 'This is a test event',
                'request_id': request_id
            }, room=socket_id)
            logger.info(f"[{request_id}] ✅ Test event emitted")
            
            # Process first chunk immediately for fastest response
            logger.info(f"[{request_id}] 🚀 Processing first chunk immediately (ultra-fast)...")
            logger.info(f"[{request_id}] 🔤 First chunk text: '{first_chunk}'")
            first_start = time.time()
            
            try:
                first_audio = self.text_to_speech_chunk(first_chunk)
                first_time = time.time() - first_start
                logger.info(f"[{request_id}] ✅ First chunk TTS successful: {len(first_audio)} bytes in {first_time:.2f}s")
                
                # Emit first chunk using chunked transmission
                first_audio_b64 = base64.b64encode(first_audio).decode('utf-8')
                logger.info(f"[{request_id}] 📤 Emitting first chunk: seq=0, size={len(first_audio_b64)} chars, to room={socket_id}")
                self.emit_large_audio_chunk(first_audio_b64, 0, socket_id, request_id)
                logger.info(f"[{request_id}] ✅ First chunk emitted successfully")
                
            except Exception as e:
                logger.error(f"[{request_id}] ❌ First chunk TTS FAILED: {e}")
                # Send error to client
                socketio.emit('audio_error', {
                    'error': f'TTS generation failed: {str(e)}',
                    'request_id': request_id
                }, room=socket_id)
                return  # Stop processing if TTS fails
            
            logger.info(f"[{request_id}] ⚡ First chunk ready in {first_time:.2f}s")
            
            # Process remaining chunks in parallel if there are more
            if remaining_chunks:
                def process_chunk(chunk_data):
                    index, chunk_text = chunk_data
                    try:
                        audio_data = self.text_to_speech_chunk(chunk_text)
                        return (index, audio_data)
                    except Exception as e:
                        logger.error(f"[{request_id}] Error processing chunk {index}: {e}")
                        return (index, None)
                
                # Process remaining chunks in parallel
                logger.info(f"[{request_id}] 🔄 Processing {len(remaining_chunks)} remaining chunks...")
                with ThreadPoolExecutor(max_workers=3) as executor:
                    chunk_data = [(i+1, chunk) for i, chunk in enumerate(remaining_chunks)]
                    future_to_index = {
                        executor.submit(process_chunk, data): data[0] 
                        for data in chunk_data
                    }
                    
                    # Collect results and emit in order
                    results = {}
                    errors = []
                    for future in as_completed(future_to_index):
                        index, audio_data = future.result()
                        if audio_data:
                            results[index] = audio_data
                            logger.info(f"[{request_id}] ✅ Chunk {index} TTS completed: {len(audio_data)} bytes")
                        else:
                            errors.append(index)
                            logger.error(f"[{request_id}] ❌ Chunk {index} TTS FAILED")
                    
                    # Emit chunks in sequence order
                    for i in range(1, total_chunks):
                        if i in results:
                            try:
                                audio_b64 = base64.b64encode(results[i]).decode('utf-8')
                                logger.info(f"[{request_id}] 📤 Emitting chunk: seq={i}, size={len(audio_b64)} chars, to room={socket_id}")
                                
                                # Use chunked transmission for remaining chunks
                                self.emit_large_audio_chunk(audio_b64, i, socket_id, request_id)
                                logger.info(f"[{request_id}] ✅ Chunk {i+1}/{total_chunks} emitted successfully")
                            except Exception as e:
                                logger.error(f"[{request_id}] ❌ Failed to emit chunk {i}: {e}")
                        else:
                            logger.warning(f"[{request_id}] ⚠️ Skipping missing chunk {i}")
                    
                    if errors:
                        logger.warning(f"[{request_id}] ⚠️ {len(errors)} chunks failed TTS generation")
            
            else:
                logger.info(f"[{request_id}] ✅ Single chunk response - no additional processing needed")
            
            # Skip streaming entirely - combine all audio and send as fallback
            logger.info(f"[{request_id}] 🔄 Combining all chunks into single audio file...")
            combined_audio = first_audio  # Start with first chunk
            
            # Add all remaining chunks
            if remaining_chunks:
                for i in range(1, total_chunks):
                    if i in results:
                        combined_audio += results[i]
            
            # Send as fallback audio, but split if too large
            combined_b64 = base64.b64encode(combined_audio).decode('utf-8')
            
            # If audio is small enough, send as single message
            if len(combined_b64) <= 32000:
                socketio.emit('audio_complete_fallback', {
                    'audio_base64': combined_b64,
                    'request_id': request_id
                }, room=socket_id)
                logger.info(f"[{request_id}] ✅ Sent complete audio as fallback: {len(combined_b64)} chars")
            else:
                # Split into multiple parts
                chunk_size = 32000
                total_parts = (len(combined_b64) + chunk_size - 1) // chunk_size
                
                logger.info(f"[{request_id}] 📦 Splitting fallback audio into {total_parts} parts")
                
                for part in range(total_parts):
                    start = part * chunk_size
                    end = min(start + chunk_size, len(combined_b64))
                    chunk = combined_b64[start:end]
                    
                    socketio.emit('audio_fallback_part', {
                        'data': chunk,
                        'part': part,
                        'total_parts': total_parts,
                        'is_complete': (part == total_parts - 1),
                        'request_id': request_id
                    }, room=socket_id)
                    logger.info(f"[{request_id}] ✅ Sent fallback part {part+1}/{total_parts}: {len(chunk)} chars")
            
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Streaming TTS error: {e}")
            socketio.emit('audio_error', {
                'error': str(e),
                'request_id': request_id
            }, room=socket_id)

class FallbackTTSProvider(TTSProvider):
    """Fallback TTS Provider (pre-recorded message)"""
    
    def __init__(self):
        self.fallback_path = os.getenv("FALLBACK_MESSAGE_PATH", "./assets/fallback_message_b64.txt")
        self.fallback_audio = self._load_fallback_audio()
        print(f"✅ Fallback TTS: Loaded from {self.fallback_path}")
    
    def _load_fallback_audio(self) -> str:
        """Load the pre-recorded fallback message"""
        try:
            with open(self.fallback_path, 'r') as f:
                content = f.read().strip()
                if content == "PLACEHOLDER_FALLBACK_AUDIO_BASE64_WILL_BE_GENERATED_LATER":
                    # Return a simple placeholder for now
                    return ""
                return content
        except FileNotFoundError:
            logger.warning(f"Fallback audio file not found: {self.fallback_path}")
            return ""
    
    def generate_audio(self, text: str) -> str:
        """Return the pre-recorded fallback message"""
        if not self.fallback_audio:
            raise Exception("No fallback audio available - please generate fallback_message_b64.txt")
        return self.fallback_audio

# Initialize TTS Provider based on configuration
def initialize_tts_provider():
    """Initialize the appropriate TTS provider based on configuration"""
    provider_name = os.getenv("TTS_PROVIDER", "kokoro").lower()
    
    try:
        if provider_name == "elevenlabs":
            return ElevenLabsTTSProvider()
        elif provider_name == "kokoro":
            return KokoroTTSProvider()
        else:
            logger.warning(f"Unknown TTS provider: {provider_name}, falling back to Kokoro")
            return KokoroTTSProvider()
    except Exception as e:
        logger.error(f"Failed to initialize {provider_name} TTS provider: {e}")
        logger.info("Falling back to Kokoro TTS")
        return KokoroTTSProvider()

# Initialize TTS providers
tts_provider = initialize_tts_provider()
fallback_provider = FallbackTTSProvider()

# Initialize streaming TTS if ElevenLabs credentials are available
streaming_tts_provider = None
if os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID"):
    try:
        streaming_tts_provider = ElevenLabsStreamingTTSProvider()
    except Exception as e:
        logger.warning(f"Failed to initialize streaming TTS: {e}")
        streaming_tts_provider = None

def get_llm_endpoint():
    """Returns the complete LLM API endpoint URL"""
    base_url = os.getenv("LLM_BASE_URL", " http://model-runner.docker.internal/engines/v1")
    return f"{base_url}/chat/completions"

@app.route('/')
def index():
    return "Welcome to the pirate LLM chat API! Use /api/chat to interact with the model.", 200

def test_llm_connection():
    """Test LLM connection with a simple request"""
    try:
        logger.info("🔍 Testing LLM connection...")
        test_request = {
            "model": os.getenv("LLM_MODEL", "llama3.2:8b-instruct-q4_K_M"),
            "messages": [{"role": "user", "content": "Say 'OK' if you can hear me."}],
            "max_tokens": 5,
            "temperature": 0.1
        }
        
        response_text = call_llm_api(test_request, "health-check")
        logger.info(f"✅ LLM test successful: {response_text[:50]}...")
        return True, response_text
    except Exception as e:
        logger.error(f"❌ LLM test failed: {e}")
        return False, str(e)

def test_tts_connection():
    """Test TTS provider with a simple request"""
    try:
        logger.info("🔍 Testing TTS connection...")
        
        # Test the primary TTS provider
        if tts_provider:
            test_audio = tts_provider.generate_audio("Test")
            logger.info(f"✅ Primary TTS test successful (audio length: {len(test_audio)} chars)")
            return True, "Primary TTS working"
        else:
            logger.warning("⚠️ No primary TTS provider configured")
            
        # Test fallback if available
        if fallback_provider:
            test_audio = fallback_provider.generate_audio("Test")
            logger.info(f"✅ Fallback TTS test successful (audio length: {len(test_audio)} chars)")
            return True, "Fallback TTS working"
        else:
            logger.warning("⚠️ No fallback TTS provider configured")
            
        return False, "No TTS providers available"
    except Exception as e:
        logger.error(f"❌ TTS test failed: {e}")
        return False, str(e)

@app.route('/health')
def health_check():
    """Comprehensive health check endpoint for monitoring"""
    health_status = {
        'status': 'healthy',
        'service': 'pirate-api',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'checks': {}
    }
    
    all_healthy = True
    
    try:
        # Test LLM connection
        llm_healthy, llm_result = test_llm_connection()
        health_status['checks']['llm'] = {
            'status': 'healthy' if llm_healthy else 'unhealthy',
            'details': llm_result,
            'endpoint': get_llm_endpoint()
        }
        if not llm_healthy:
            all_healthy = False
        
        # Test TTS connection  
        tts_healthy, tts_result = test_tts_connection()
        health_status['checks']['tts'] = {
            'status': 'healthy' if tts_healthy else 'unhealthy', 
            'details': tts_result,
            'primary_provider': tts_provider_name if tts_provider else None,
            'fallback_available': fallback_provider is not None
        }
        if not tts_healthy:
            all_healthy = False
            
        # Overall status
        if not all_healthy:
            health_status['status'] = 'degraded'
            
        status_code = 200 if all_healthy else 503
        logger.info(f"🏥 Health check completed: {health_status['status']}")
        
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'pirate-api',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'error': str(e)
        }), 500


@app.route('/api/chat', methods=['POST'])
def chat_api():
    """Processes chat API requests"""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] 📥 Received chat request from {request.remote_addr}")
    
    try:
        # Validate request
        if not request.is_json:
            logger.error(f"[{request_id}] ❌ Invalid content type - not JSON")
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        chat_request = request.json
        if not chat_request:
            logger.error(f"[{request_id}] ❌ No data received in request body")
            return jsonify({'error': 'No data received'}), 400
        
        # Validate required fields
        if 'model' not in chat_request:
            logger.error(f"[{request_id}] ❌ Missing required field: model")
            return jsonify({'error': 'Missing required field: model'}), 400
        if 'messages' not in chat_request:
            logger.error(f"[{request_id}] ❌ Missing required field: messages")
            return jsonify({'error': 'Missing required field: messages'}), 400
        
        logger.info(f"[{request_id}] 📋 Request payload: {json.dumps(chat_request, indent=2)}")

        # Call the LLM API
        try:
            logger.info(f"[{request_id}] 🚀 Calling LLM API...")
            response_text = call_llm_api(chat_request, request_id)
            
            # Validate response
            if not response_text or not response_text.strip():
                logger.error(f"[{request_id}] ❌ Empty response from LLM")
                return jsonify({'error': 'Empty response from LLM'}), 500
            
            logger.info(f"[{request_id}] ✅ Received LLM response: {response_text[:100]}...")
            
            # Generate TTS audio for the response
            try:
                audio_b64 = generate_sentence_audio(response_text, request_id)
                
                logger.info(f"[{request_id}] ✅ TTS generation successful, audio size: {len(audio_b64)} chars")
                logger.info(f"[{request_id}] 📤 Sending response back to client")
                return jsonify({
                    'response': response_text, 
                    'audio_base64': audio_b64
                })
            except Exception as tts_error:
                logger.error(f"[{request_id}] ❌ TTS error: {tts_error}")
                # Return text response even if TTS fails
                logger.info(f"[{request_id}] 📤 Sending text-only response back to client")
                return jsonify({
                    'response': response_text,
                    'error': 'TTS generation failed, returning text only'
                }), 200
                
        except requests.exceptions.Timeout:
            logger.error(f"[{request_id}] ⏰ LLM API timeout")
            return jsonify({'error': 'LLM API request timed out'}), 504
        except requests.exceptions.ConnectionError:
            logger.error(f"[{request_id}] 🔌 LLM API connection error")
            return jsonify({'error': 'Cannot connect to LLM API'}), 503
        except requests.exceptions.HTTPError as e:
            logger.error(f"[{request_id}] 🚫 LLM API HTTP error: {e}")
            return jsonify({'error': f'LLM API error: {e.response.status_code}'}), e.response.status_code
        except Exception as e:
            logger.error(f"[{request_id}] ❌ LLM API error: {e}")
            return jsonify({'error': 'Failed to get response from LLM'}), 500
            
    except Exception as e:
        logger.error(f"[{request_id}] 💥 Unexpected error in chat_api: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def call_llm_api(chat_request, request_id=None):
    """Calls the LLM API and returns the response"""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    
    headers = {"Content-Type": "application/json"}
    
    # Add OpenAI API key if available (for OpenAI endpoints)
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        headers["Authorization"] = f"Bearer {openai_api_key}"
    
    # Validate LLM endpoint
    llm_endpoint = get_llm_endpoint()
    if not llm_endpoint:
        logger.error(f"[{request_id}] ❌ LLM_BASE_URL environment variable is not set")
        raise Exception("LLM_BASE_URL environment variable is not set")
    
    model = chat_request.get('model', 'unknown')
    logger.info(f"[{request_id}] 🌐 Calling LLM endpoint: {llm_endpoint}")
    logger.info(f"[{request_id}] 🤖 Using model: {model}")
    
    # Add optimal decode parameters for Mistral models
    optimized_request = chat_request.copy()
    if model and 'mistral' in model.lower():
        optimized_request.update({
            'temperature': 0.6,
            'top_p': 0.9,
            'max_tokens': 120,
            'presence_penalty': 0.3,
            'frequency_penalty': 0.2
        })
        logger.info(f"[{request_id}] 🎯 Applied Mistral optimization parameters")
    
    # Send request to LLM API
    logger.info(f"[{request_id}] 📡 Sending request to LLM...")
    response = requests.post(
        llm_endpoint,
        headers=headers,
        json=optimized_request,
        timeout=30
    )
    
    # Check if the status code is not 200 OK
    if response.status_code != 200:
        logger.error(f"[{request_id}] 🚫 LLM API returned status {response.status_code}: {response.text}")
        raise requests.exceptions.HTTPError(f"API returned status code {response.status_code}: {response.text}")
    
    logger.info(f"[{request_id}] ✅ LLM API responded with status 200")
    
    # Parse the response
    try:
        chat_response = response.json()
        logger.info(f"[{request_id}] 📋 LLM response parsed successfully")
    except json.JSONDecodeError as e:
        logger.error(f"[{request_id}] ❌ Invalid JSON response from LLM API: {e}")
        raise Exception(f"Invalid JSON response from LLM API: {e}")
    
    # Extract the assistant's message
    if not chat_response.get('choices'):
        raise Exception("No 'choices' field in LLM API response")
    
    if len(chat_response['choices']) == 0:
        raise Exception("Empty choices array in LLM API response")
    
    choice = chat_response['choices'][0]
    if 'message' not in choice:
        raise Exception("No 'message' field in LLM API choice")
    
    if 'content' not in choice['message']:
        raise Exception("No 'content' field in LLM API message")
    
    content = choice['message']['content']
    if not content or not content.strip():
        raise Exception("Empty content in LLM API response")
    
    # Apply fast format post-processing for character consistency
    processed_content = apply_format_post_processing(content.strip(), request_id)
    return processed_content

def apply_format_post_processing(content, request_id=None):
    """Apply fast format post-processing for Mr. Bones character consistency"""
    if request_id is None:
        request_id = "unknown"
    
    original_content = content
    
    # Fix UTF-8 encoding issues (mojibake)
    content = content.encode('utf-8', errors='ignore').decode('utf-8')
    
    # Replace contractions with expanded forms
    contractions_map = {
        "don't": "do not", "Don't": "Do not", "DON'T": "DO NOT",
        "can't": "cannot", "Can't": "Cannot", "CAN'T": "CANNOT", 
        "won't": "will not", "Won't": "Will not", "WON'T": "WILL NOT",
        "I'm": "I am", "I'M": "I AM",
        "you're": "you are", "You're": "You are", "YOU'RE": "YOU ARE",
        "we're": "we are", "We're": "We are", "WE'RE": "WE ARE",
        "they're": "they are", "They're": "They are", "THEY'RE": "THEY ARE",
        "it's": "it is", "It's": "It is", "IT'S": "IT IS",
        "that's": "that is", "That's": "That is", "THAT'S": "THAT IS",
        "what's": "what is", "What's": "What is", "WHAT'S": "WHAT IS",
        "here's": "here is", "Here's": "Here is", "HERE'S": "HERE IS",
        "there's": "there is", "There's": "There is", "THERE'S": "THERE IS",
        "let's": "let us", "Let's": "Let us", "LET'S": "LET US",
        "I'll": "I will", "I'LL": "I WILL",
        "you'll": "you will", "You'll": "You will", "YOU'LL": "YOU WILL",
        "he'll": "he will", "He'll": "He will", "HE'LL": "HE WILL",
        "she'll": "she will", "She'll": "She will", "SHE'LL": "SHE WILL",
        "we'll": "we will", "We'll": "We will", "WE'LL": "WE WILL",
        "they'll": "they will", "They'll": "They will", "THEY'LL": "THEY WILL",
        "I've": "I have", "I'VE": "I HAVE",
        "you've": "you have", "You've": "You have", "YOU'VE": "YOU HAVE",
        "we've": "we have", "We've": "We have", "WE'VE": "WE HAVE",
        "they've": "they have", "They've": "They have", "THEY'VE": "THEY HAVE",
        "I'd": "I would", "I'D": "I WOULD",
        "you'd": "you would", "You'd": "You would", "YOU'D": "YOU WOULD",
        "he'd": "he would", "He'd": "He would", "HE'D": "HE WOULD",
        "she'd": "she would", "She'd": "She would", "SHE'D": "SHE WOULD",
        "we'd": "we would", "We'd": "We would", "WE'D": "WE WOULD",
        "they'd": "they would", "They'd": "They would", "THEY'D": "THEY WOULD"
    }
    
    # Apply contraction replacements
    for contraction, expansion in contractions_map.items():
        content = re.sub(r'\b' + re.escape(contraction) + r'\b', expansion, content)
    
    # Replace Mr. with Mister
    content = re.sub(r'\bMr\.', 'Mister', content)
    content = re.sub(r'\bmr\.', 'mister', content)  # Handle lowercase
    
    # Fix common UTF-8 issues
    utf8_fixes = {
        'â€™': "'",  # Right single quotation mark
        'â€œ': '"',  # Left double quotation mark  
        'â€': '"',   # Right double quotation mark
        'â€¦': '...',  # Ellipsis
        'â€"': '-',   # Em dash
        'â€"': '--',  # En dash
    }
    
    for broken, fixed in utf8_fixes.items():
        content = content.replace(broken, fixed)
    
    # Log if any changes were made
    if content != original_content:
        logger.info(f"[{request_id}] 🔧 Applied format post-processing")
    
    return content



def generate_sentence_audio(sentence, request_id=None):
    """Generate TTS audio for a single sentence and return base64 encoded WAV"""
    import time
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info(f"[{request_id}] 🎵 Starting TTS for sentence: {sentence[:50]}...")
    
    try:
        # Try the primary TTS provider
        audio_base64 = tts_provider.generate_audio(sentence)
        
        generation_time = time.time() - start_time
        logger.info(f"[{request_id}] ✅ TTS generation completed in {generation_time:.3f}s for sentence: {sentence[:50]}...")
        
        return audio_base64
        
    except Exception as e:
        generation_time = time.time() - start_time
        logger.error(f"[{request_id}] ❌ Primary TTS failed after {generation_time:.3f}s: {e}")
        
        # Try fallback provider
        try:
            logger.info(f"[{request_id}] 🔄 Attempting fallback TTS...")
            fallback_audio = fallback_provider.generate_audio(sentence)
            
            fallback_time = time.time() - start_time
            logger.info(f"[{request_id}] ✅ Fallback TTS completed in {fallback_time:.3f}s")
            
            return fallback_audio
            
        except Exception as fallback_error:
            final_time = time.time() - start_time
            logger.error(f"[{request_id}] 💥 Both primary and fallback TTS failed after {final_time:.3f}s")
            logger.error(f"[{request_id}] Primary error: {e}")
            logger.error(f"[{request_id}] Fallback error: {fallback_error}")
            raise Exception(f"All TTS providers failed. Primary: {e}, Fallback: {fallback_error}")

# WebSocket Event Handlers
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info(f"🔌 Client connected: {request.sid}")
    emit('connected', {'status': 'Connected to Pirate API'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info(f"🔌 Client disconnected: {request.sid}")

@socketio.on('chat')
def handle_chat(data):
    """Handle chat message with streaming TTS response"""
    request_id = str(uuid.uuid4())[:8]
    socket_id = request.sid
    logger.info(f"[{request_id}] 💬 WebSocket chat from {socket_id}")
    
    try:
        # Validate input - support both old and new message formats
        if not data:
            emit('error', {'error': 'Missing chat data'})
            return
        
        model = data.get('model', os.getenv('LLM_MODEL', 'llama3.2:8b-instruct-q4_K_M'))
        
        # Handle new format with full message history (includes system prompt)
        if 'messages' in data:
            messages = data['messages']
            user_message = messages[-1]['content'] if messages else "No message"
            logger.info(f"[{request_id}] 📝 User message: {user_message}")
            
            chat_request = {
                'model': model,
                'messages': messages
            }
        # Handle old format with just message
        elif 'message' in data:
            user_message = data['message']
            logger.info(f"[{request_id}] 📝 User message: {user_message}")
            
            chat_request = {
                'model': model,
                'messages': [
                    {'role': 'user', 'content': user_message}
                ]
            }
        else:
            emit('error', {'error': 'Missing message or messages in chat data'})
            return
        
        # Get LLM response
        try:
            # Check if test mode is enabled
            test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
            if test_mode:
                logger.info(f"[{request_id}] 🧪 Test mode - using mock response...")
                response_text = "Ahoy matey! This be a test response from Mr. Bones to test our audio streaming capabilities!"
            else:
                logger.info(f"[{request_id}] 🤖 Calling LLM...")
                response_text = call_llm_api(chat_request, request_id)
            
            # Send text response immediately
            emit('text_response', {
                'text': response_text,
                'request_id': request_id
            })
            
            logger.info(f"[{request_id}] 📤 Sent text response: {response_text[:50]}...")
            
            # Generate streaming TTS if available
            if streaming_tts_provider:
                logger.info(f"[{request_id}] 🎵 Starting streaming TTS...")
                # Run in background thread to avoid blocking
                threading.Thread(
                    target=streaming_tts_provider.generate_streaming_audio,
                    args=(response_text, socket_id, request_id),
                    daemon=True
                ).start()
            else:
                # No streaming TTS available - send error
                logger.error(f"[{request_id}] ❌ No streaming TTS provider configured")
                emit('audio_error', {
                    'error': 'No streaming TTS provider available. ElevenLabs credentials required.',
                    'request_id': request_id
                })
                    
        except Exception as llm_error:
            logger.error(f"[{request_id}] ❌ LLM error: {llm_error}")
            emit('error', {
                'error': f'Failed to get response from LLM: {llm_error}',
                'request_id': request_id
            })
            
    except Exception as e:
        logger.error(f"[{request_id}] 💥 Chat handler error: {e}")
        emit('error', {
            'error': 'Internal server error',
            'request_id': request_id
        })

def validate_api_environment():
    """Validate API environment variables and dependencies"""
    errors = []
    
    # Check required environment variables
    llm_base_url = os.getenv("LLM_BASE_URL")
    if not llm_base_url:
        errors.append("LLM_BASE_URL environment variable is not set")
    
    # Check TTS model
    if KOKORO_AVAILABLE:
        try:
            # Test Kokoro TTS loading
            test_tts = KPipeline(lang_code='a', device='cpu', repo_id='hexgrad/Kokoro-82M')
            print("✅ Kokoro TTS loaded successfully")
        except Exception as e:
            errors.append(f"Kokoro TTS loading failed: {e}")
    else:
        print("⚠️ Kokoro TTS not available (using ElevenLabs)")
    
    # Check CUDA availability
    try:
        import torch
        if torch.cuda.is_available():
            print("✅ CUDA available for GPU acceleration")
        else:
            print("⚠️ CUDA not available, using CPU")
    except ImportError:
        print("⚠️ PyTorch not available, using CPU")
    
    if errors:
        print("❌ API environment validation failed:")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)
    
    print("✅ API environment validation passed")

def run_startup_health_checks():
    """Run comprehensive health checks at startup"""
    print("\n🏥 Running startup health checks...")
    
    all_healthy = True
    
    # Test LLM connection
    print("📡 Testing LLM connection...")
    try:
        llm_healthy, llm_result = test_llm_connection()
        if llm_healthy:
            print(f"✅ LLM connection successful")
        else:
            print(f"❌ LLM connection failed: {llm_result}")
            all_healthy = False
    except Exception as e:
        print(f"❌ LLM test error: {e}")
        all_healthy = False
    
    # Test TTS connection
    print("🎵 Testing TTS connection...")
    try:
        tts_healthy, tts_result = test_tts_connection()
        if tts_healthy:
            print(f"✅ TTS connection successful: {tts_result}")
        else:
            print(f"❌ TTS connection failed: {tts_result}")
            all_healthy = False
    except Exception as e:
        print(f"❌ TTS test error: {e}")
        all_healthy = False
    
    if all_healthy:
        print("✅ All startup health checks passed!")
    else:
        print("⚠️ Some health checks failed - server will start but may have limited functionality")
    
    return all_healthy

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    
    # Validate environment before starting
    validate_api_environment()
    
    # Run startup health checks
    startup_healthy = run_startup_health_checks()
    
    print(f"\n🚀 Server starting on http://localhost:{port}")
    print(f"📡 Using LLM endpoint: {get_llm_endpoint()}")
    print(f"🎵 Primary TTS provider: {tts_provider_name}")
    print(f"🔄 Fallback TTS available: {'✅ Yes' if fallback_provider else '❌ No'}")
    print(f"🌐 WebSocket streaming TTS: {'✅ Available' if streaming_tts_provider else '❌ Not available'}")
    print(f"🏥 Startup health status: {'✅ All systems operational' if startup_healthy else '⚠️ Some issues detected'}")
    print(f"📍 Health endpoint: http://localhost:{port}/health")
    
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=os.getenv("DEBUG", "false").lower() == "true")
    except KeyboardInterrupt:
        print("\nShutting down...")
        os._exit(0)