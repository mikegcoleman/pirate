import os
import json
import requests
from flask import Flask, request, jsonify, send_file
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
    print(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

app = Flask(__name__)

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
            
            # Read and encode as base64
            with open(tmp_audio.name, 'rb') as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Clean up temp file
            os.unlink(tmp_audio.name)
        
        return audio_base64

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

# Initialize TTS
tts_provider = initialize_tts_provider()
fallback_provider = FallbackTTSProvider()

def get_llm_endpoint():
    """Returns the complete LLM API endpoint URL"""
    base_url = os.getenv("LLM_BASE_URL", " http://model-runner.docker.internal/engines/v1")
    return f"{base_url}/chat/completions"

@app.route('/')
def index():
    return "Welcome to the pirate LLM chat API! Use /api/chat to interact with the model.", 200

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Basic health check - just return success
        return jsonify({
            'status': 'healthy',
            'service': 'pirate-api',
            'timestamp': '2024-01-01T00:00:00Z'  # You could add real timestamp if needed
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
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

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    
    # Validate environment before starting
    validate_api_environment()
    
    print(f"Server starting on http://localhost:{port}")
    print(f"Using LLM endpoint: {get_llm_endpoint()}")
    
    app.run(host='0.0.0.0', port=port, debug=os.getenv("DEBUG", "false").lower() == "true")