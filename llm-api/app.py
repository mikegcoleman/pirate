import os
import json
import requests
from flask import Flask, request, jsonify, send_file
import signal
import sys
from kokoro import KPipeline
import tempfile
import base64
import torch
    
def handle_shutdown(signum, frame):
    print(f"🔌 Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

app = Flask(__name__)

use_gpu = torch.cuda.is_available()

# Initialize Kokoro TTS
# Kokoro requires specific model files, not just directories
model_path = os.getenv("KOKORO_MODEL_PATH", "./models/kokoro/model.onnx")
voices_path = os.getenv("KOKORO_VOICES_PATH", "./models/kokoro/voices-v1.0.bin")

# Create models directory if it doesn't exist
os.makedirs(os.path.dirname(model_path), exist_ok=True)

# Let Kokoro handle model downloading if files don't exist
tts_engine = KPipeline(lang_code='a')  # 'a' for American English

# Kokoro handles GPU/CPU automatically based on ONNX Runtime
if use_gpu:
    print("✅ GPU available - Kokoro will use GPU acceleration if supported")
else:
    print("✅ Using CPU for Kokoro TTS")

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
    try:
        # Validate request
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        chat_request = request.json
        if not chat_request:
            return jsonify({'error': 'No data received'}), 400
        
        # Validate required fields
        if 'model' not in chat_request:
            return jsonify({'error': 'Missing required field: model'}), 400
        if 'messages' not in chat_request:
            return jsonify({'error': 'Missing required field: messages'}), 400
        
        print(json.dumps(chat_request, indent=2))

        # Call the LLM API
        try:
            response_text = call_llm_api(chat_request)
            
            # Validate response
            if not response_text or not response_text.strip():
                return jsonify({'error': 'Empty response from LLM'}), 500
            
            # Generate TTS audio for the response
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
                    # Use the correct Kokoro API
                    generator = tts_engine(response_text, voice='af_heart')
                    audio_data = None
                    for i, (gs, ps, audio) in enumerate(generator):
                        audio_data = audio
                        break  # Take the first audio chunk
                    
                    if audio_data is None:
                        raise Exception("No audio generated")
                    
                    tmp_audio.write(audio_data)
                    tmp_audio.seek(0)
                    audio_bytes = tmp_audio.read()
                    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                return jsonify({
                    'response': response_text, 
                    'audio_base64': audio_b64
                })
            except Exception as tts_error:
                app.logger.error(f"TTS error: {tts_error}")
                # Return text response even if TTS fails
                return jsonify({
                    'response': response_text,
                    'error': 'TTS generation failed, returning text only'
                }), 200
                
        except requests.exceptions.Timeout:
            app.logger.error("LLM API timeout")
            return jsonify({'error': 'LLM API request timed out'}), 504
        except requests.exceptions.ConnectionError:
            app.logger.error("LLM API connection error")
            return jsonify({'error': 'Cannot connect to LLM API'}), 503
        except requests.exceptions.HTTPError as e:
            app.logger.error(f"LLM API HTTP error: {e}")
            return jsonify({'error': f'LLM API error: {e.response.status_code}'}), e.response.status_code
        except Exception as e:
            app.logger.error(f"LLM API error: {e}")
            return jsonify({'error': 'Failed to get response from LLM'}), 500
            
    except Exception as e:
        app.logger.error(f"Unexpected error in chat_api: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def call_llm_api(chat_request):
    """Calls the LLM API and returns the response"""
    
    headers = {"Content-Type": "application/json"}
    
    # Validate LLM endpoint
    llm_endpoint = get_llm_endpoint()
    if not llm_endpoint:
        raise Exception("LLM_BASE_URL environment variable is not set")
    
    # Send request to LLM API
    response = requests.post(
        llm_endpoint,
        headers=headers,
        json=chat_request,
        timeout=30
    )
    
    # Check if the status code is not 200 OK
    if response.status_code != 200:
        raise requests.exceptions.HTTPError(f"API returned status code {response.status_code}: {response.text}")
    
    # Parse the response
    try:
        chat_response = response.json()
    except json.JSONDecodeError as e:
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
    
    return content.strip()

def validate_api_environment():
    """Validate API environment variables and dependencies"""
    errors = []
    
    # Check required environment variables
    llm_base_url = os.getenv("LLM_BASE_URL")
    if not llm_base_url:
        errors.append("LLM_BASE_URL environment variable is not set")
    
    # Check TTS model
    try:
        # Test Kokoro TTS loading
        test_tts = KPipeline(lang_code='a')
        print("✅ Kokoro TTS loaded successfully")
    except Exception as e:
        errors.append(f"Kokoro TTS loading failed: {e}")
    
    # Check CUDA availability
    if torch.cuda.is_available():
        print("✅ CUDA available for GPU acceleration")
    else:
        print("⚠️ CUDA not available, using CPU")
    
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