import os
import json
import requests
from flask import Flask, request, jsonify, send_file, Response
import signal
import sys
from piper import PiperVoice
import tempfile
import base64
import torch
import wave
import re
import uuid
    
def handle_shutdown(signum, frame):
    print(f"🔌 Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

app = Flask(__name__)

use_gpu = torch.cuda.is_available()

# Initialize Piper TTS with optimized settings
model_path = os.getenv("PIPER_MODEL_PATH", "./models/piper/en_US-lessac-medium.onnx")
model_config_path = os.getenv("PIPER_CONFIG_PATH", "./models/piper/en_US-lessac-medium.onnx.json")

# Create models directory if it doesn't exist
os.makedirs(os.path.dirname(model_path), exist_ok=True)

# Initialize Piper voice - will download model if needed
tts_engine = None
try:
    tts_engine = PiperVoice.load(model_path, config_path=model_config_path, use_cuda=use_gpu)
    print(f"✅ Piper TTS loaded successfully with {'GPU' if use_gpu else 'CPU'}")
except Exception as e:
    print(f"⚠️ Using fallback Piper model: {e}")
    # Fallback to a basic model that Piper can auto-download
    tts_engine = PiperVoice.load("en_US-lessac-medium", use_cuda=use_gpu)
    print(f"✅ Piper TTS fallback loaded with {'GPU' if use_gpu else 'CPU'}")

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
                                app.logger.error(f"TTS error for sentence: {tts_error}")
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
                        app.logger.error(f"TTS error for final sentence: {tts_error}")
                        chunk_data = {
                            'type': 'text_chunk',
                            'sentence': sentence_buffer.strip(),
                            'error': 'TTS generation failed',
                            'chunk_id': str(uuid.uuid4())
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                
                # Send completion signal
                completion_data = {
                    'type': 'complete',
                    'full_response': accumulated_text
                }
                yield f"data: {json.dumps(completion_data)}\n\n"
                
            except Exception as e:
                app.logger.error(f"Streaming error: {e}")
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
        app.logger.error(f"Unexpected error in chat_stream_api: {e}")
        return jsonify({'error': 'Internal server error'}), 500

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
                    # Use Piper TTS API
                    wav_bytes = bytes()
                    for audio_chunk in tts_engine.synthesize(response_text):
                        wav_bytes += audio_chunk
                    
                    if not wav_bytes:
                        raise Exception("No audio generated")
                    
                    # Write WAV bytes directly to file
                    tmp_audio.write(wav_bytes)
                    tmp_audio.flush()
                    
                    # Read the WAV file as bytes for base64 encoding
                    with open(tmp_audio.name, 'rb') as f:
                        audio_bytes = f.read()
                    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                    
                    # Clean up temp file
                    os.unlink(tmp_audio.name)
                
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

def call_streaming_llm_api(chat_request):
    """Calls the LLM API with streaming and yields response chunks"""
    headers = {"Content-Type": "application/json"}
    
    # Validate LLM endpoint
    llm_endpoint = get_llm_endpoint()
    if not llm_endpoint:
        raise Exception("LLM_BASE_URL environment variable is not set")
    
    # Send streaming request to LLM API
    response = requests.post(
        llm_endpoint,
        headers=headers,
        json=chat_request,
        timeout=60,  # Longer timeout for streaming
        stream=True
    )
    
    # Check if the status code is not 200 OK
    if response.status_code != 200:
        raise requests.exceptions.HTTPError(f"API returned status code {response.status_code}: {response.text}")
    
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
    start_time = time.time()
    
    try:
        # Use Piper TTS for the sentence
        wav_bytes = bytes()
        for audio_chunk in tts_engine.synthesize(sentence):
            wav_bytes += audio_chunk
        
        if not wav_bytes:
            raise Exception("No audio generated for sentence")
        
        generation_time = time.time() - start_time
        print(f"TTS generation time: {generation_time:.3f}s for sentence: {sentence[:50]}...")
        
        return base64.b64encode(wav_bytes).decode('utf-8')
        
    except Exception as e:
        generation_time = time.time() - start_time
        print(f"TTS generation failed after {generation_time:.3f}s: {e}")
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
        # Test Piper TTS loading
        test_tts = PiperVoice.load("en_US-lessac-medium", use_cuda=False)
        print("✅ Piper TTS loaded successfully")
    except Exception as e:
        errors.append(f"Piper TTS loading failed: {e}")
    
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