import os
import json
import requests
from flask import Flask, request, jsonify, send_file, Response
import signal
import sys
from kokoro import KPipeline
import tempfile
import base64
import torch
import wave
import re
import uuid
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

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

use_gpu = torch.cuda.is_available()

# Initialize Kokoro TTS
# Kokoro requires specific model files, not just directories
model_path = os.getenv("KOKORO_MODEL_PATH", "./models/kokoro/model.onnx")
voices_path = os.getenv("KOKORO_VOICES_PATH", "./models/kokoro/voices-v1.0.bin")

# Create models directory if it doesn't exist
os.makedirs(os.path.dirname(model_path), exist_ok=True)

# Let Kokoro handle model downloading if files don't exist
tts_engine = KPipeline(lang_code='a', device='cpu', repo_id='hexgrad/Kokoro-82M')

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

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream_api():
    """Processes streaming chat API requests with sentence-level TTS"""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] 📥 Received streaming chat request from {request.remote_addr}")
    
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
        
        def generate_streaming_response():
            """Generator function for streaming audio chunks"""
            try:
                # Set streaming flag for LLM API
                chat_request['stream'] = True
                
                # Call streaming LLM API
                accumulated_text = ""
                sentence_buffer = ""
                
                for chunk_text in call_streaming_llm_api(chat_request):
                    accumulated_text += chunk_text
                    sentence_buffer += chunk_text
                    
                    # Check for sentence boundaries
                    sentences = split_into_sentences(sentence_buffer)
                    
                    # Process complete sentences
                    for sentence in sentences[:-1]:  # All but the last (incomplete) sentence
                        if sentence.strip():
                            # Send text immediately for faster display
                            text_chunk_data = {
                                'type': 'text_preview',
                                'sentence': sentence.strip(),
                                'chunk_id': str(uuid.uuid4())
                            }
                            yield f"data: {json.dumps(text_chunk_data)}\n\n"
                            
                            # Then generate and send audio
                            try:
                                audio_b64 = generate_sentence_audio(sentence.strip())
                                chunk_data = {
                                    'type': 'audio_chunk',
                                    'sentence': sentence.strip(),
                                    'audio_base64': audio_b64,
                                    'chunk_id': str(uuid.uuid4())
                                }
                                yield f"data: {json.dumps(chunk_data)}\n\n"
                            except Exception as tts_error:
                                logger.error(f"[{request_id}] ❌ TTS error for sentence: {tts_error}")
                                # Send text-only chunk if TTS fails
                                chunk_data = {
                                    'type': 'text_chunk',
                                    'sentence': sentence.strip(),
                                    'error': 'TTS generation failed',
                                    'chunk_id': str(uuid.uuid4())
                                }
                                yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    # Keep the incomplete sentence in buffer
                    sentence_buffer = sentences[-1] if sentences else ""
                
                # Process any remaining text
                if sentence_buffer.strip():
                    try:
                        audio_b64 = generate_sentence_audio(sentence_buffer.strip())
                        chunk_data = {
                            'type': 'audio_chunk',
                            'sentence': sentence_buffer.strip(),
                            'audio_base64': audio_b64,
                            'chunk_id': str(uuid.uuid4())
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                    except Exception as tts_error:
                        logger.error(f"[{request_id}] ❌ TTS error for final sentence: {tts_error}")
                        chunk_data = {
                            'type': 'text_chunk',
                            'sentence': sentence_buffer.strip(),
                            'error': 'TTS generation failed',
                            'chunk_id': str(uuid.uuid4())
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                
                # Send completion signal
                logger.info(f"[{request_id}] 🏁 Streaming response completed, total length: {len(accumulated_text)} chars")
                logger.info(f"[{request_id}] 📤 Sending completion signal back to client")
                completion_data = {
                    'type': 'complete',
                    'full_response': accumulated_text
                }
                yield f"data: {json.dumps(completion_data)}\n\n"
                
            except Exception as e:
                logger.error(f"[{request_id}] ❌ Streaming error: {e}")
                error_data = {
                    'type': 'error',
                    'error': str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return Response(
            generate_streaming_response(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] 💥 Unexpected error in chat_stream_api: {e}")
        return jsonify({'error': 'Internal server error'}), 500

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
                logger.info(f"[{request_id}] 🎵 Starting TTS generation...")
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
                    # Use the correct Kokoro API
                    generator = tts_engine(response_text, voice='af_heart')
                    audio_tensor = None
                    for i, (gs, ps, audio) in enumerate(generator):
                        audio_tensor = audio
                        break  # Take the first audio chunk
                    
                    if audio_tensor is None:
                        raise Exception("No audio generated")
                    
                    # Convert tensor to numpy array and then to WAV format
                    import soundfile as sf
                    import numpy as np
                    
                    # Convert tensor to numpy if needed
                    if hasattr(audio_tensor, 'cpu'):
                        audio_np = audio_tensor.cpu().numpy()
                    else:
                        audio_np = np.array(audio_tensor)
                    
                    # Write WAV file using soundfile
                    sf.write(tmp_audio.name, audio_np, 24000)  # Kokoro uses 24kHz sample rate
                    
                    # Read the WAV file as bytes
                    tmp_audio.seek(0)
                    audio_bytes = tmp_audio.read()
                    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                
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
    
    # Validate LLM endpoint
    llm_endpoint = get_llm_endpoint()
    if not llm_endpoint:
        logger.error(f"[{request_id}] ❌ LLM_BASE_URL environment variable is not set")
        raise Exception("LLM_BASE_URL environment variable is not set")
    
    model = chat_request.get('model', 'unknown')
    logger.info(f"[{request_id}] 🌐 Calling LLM endpoint: {llm_endpoint}")
    logger.info(f"[{request_id}] 🤖 Using model: {model}")
    
    # Send request to LLM API
    logger.info(f"[{request_id}] 📡 Sending request to LLM...")
    response = requests.post(
        llm_endpoint,
        headers=headers,
        json=chat_request,
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
    
    return content.strip()

def call_streaming_llm_api(chat_request):
    """Calls the LLM API with streaming and yields response chunks"""
    request_id = str(uuid.uuid4())[:8]
    headers = {"Content-Type": "application/json"}
    
    # Validate LLM endpoint
    llm_endpoint = get_llm_endpoint()
    if not llm_endpoint:
        logger.error(f"[{request_id}] ❌ LLM_BASE_URL environment variable is not set")
        raise Exception("LLM_BASE_URL environment variable is not set")
    
    model = chat_request.get('model', 'unknown')
    logger.info(f"[{request_id}] 🌐 Calling streaming LLM endpoint: {llm_endpoint}")
    logger.info(f"[{request_id}] 🤖 Using model: {model}")
    
    # Send streaming request to LLM API
    logger.info(f"[{request_id}] 📡 Sending streaming request to LLM...")
    response = requests.post(
        llm_endpoint,
        headers=headers,
        json=chat_request,
        timeout=60,  # Longer timeout for streaming
        stream=True
    )
    
    # Check if the status code is not 200 OK
    if response.status_code != 200:
        logger.error(f"[{request_id}] 🚫 Streaming LLM API returned status {response.status_code}: {response.text}")
        raise requests.exceptions.HTTPError(f"API returned status code {response.status_code}: {response.text}")
    
    logger.info(f"[{request_id}] ✅ Streaming LLM API responded with status 200")
    
    # Process streaming response
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                data_str = line_str[6:]  # Remove 'data: ' prefix
                if data_str.strip() == '[DONE]':
                    break
                
                try:
                    chunk_data = json.loads(data_str)
                    if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                        delta = chunk_data['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield content
                except json.JSONDecodeError:
                    # Skip invalid JSON chunks
                    continue

def split_into_sentences(text):
    """Split text into sentences using punctuation boundaries"""
    # Simple sentence splitting - can be enhanced for better accuracy
    sentence_endings = r'[.!?]+\s*'
    sentences = re.split(f'({sentence_endings})', text)
    
    # Recombine sentences with their punctuation
    result = []
    for i in range(0, len(sentences), 2):
        if i < len(sentences):
            sentence = sentences[i]
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]
            if sentence.strip():
                result.append(sentence)
    
    return result

def generate_sentence_audio(sentence):
    """Generate TTS audio for a single sentence and return base64 encoded WAV"""
    import time
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info(f"[{request_id}] 🎵 Starting TTS for sentence: {sentence[:50]}...")
    
    try:
        # Use Kokoro TTS for the sentence
        generator = tts_engine(sentence, voice='af_heart')
        audio_tensor = None
        for i, (gs, ps, audio) in enumerate(generator):
            audio_tensor = audio
            break  # Take the first audio chunk
        
        if audio_tensor is None:
            raise Exception("No audio generated for sentence")
        
        # Convert tensor to numpy array and then to WAV format
        import soundfile as sf
        import numpy as np
        
        # Convert tensor to numpy if needed
        if hasattr(audio_tensor, 'cpu'):
            audio_np = audio_tensor.cpu().numpy()
        else:
            audio_np = np.array(audio_tensor)
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
            sf.write(tmp_audio.name, audio_np, 24000)  # Kokoro uses 24kHz sample rate
            
            # Read the WAV file as bytes
            with open(tmp_audio.name, 'rb') as f:
                audio_bytes = f.read()
            
            # Clean up temp file
            os.unlink(tmp_audio.name)
        
        generation_time = time.time() - start_time
        logger.info(f"[{request_id}] ✅ TTS generation completed in {generation_time:.3f}s for sentence: {sentence[:50]}...")
        
        return base64.b64encode(audio_bytes).decode('utf-8')
        
    except Exception as e:
        generation_time = time.time() - start_time
        logger.error(f"[{request_id}] ❌ TTS generation failed after {generation_time:.3f}s: {e}")
        raise

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
        test_tts = KPipeline(lang_code='a', device='cpu', repo_id='hexgrad/Kokoro-82M')
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