import os
import json
import requests
from flask import Flask, request, jsonify, send_file, Response
import signal
import sys
import tempfile
import base64
import wave
import uuid
from dotenv import load_dotenv
import logging
from datetime import datetime
import re

# Load environment variables first
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

# GPU detection removed - no longer needed for ElevenLabs-only TTS

# ElevenLabs TTS Provider
class ElevenLabsTTSProvider:
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
            temp_path = tmp_audio.name
            tmp_audio.write(audio_data)
            tmp_audio.flush()
        
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


# Initialize ElevenLabs TTS
tts_provider = ElevenLabsTTSProvider()

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

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream_api():
    """Processes streaming chat API requests with chunked audio"""
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
        
        logger.info(f"[{request_id}] 📋 Streaming request payload: {json.dumps(chat_request, indent=2)}")

        def generate_streaming_response():
            """Generator function for Server-Sent Events"""
            try:
                # Call the LLM API first (we need complete text for ElevenLabs)
                logger.info(f"[{request_id}] 🚀 Calling LLM API...")
                response_text = call_llm_api(chat_request, request_id)
                
                # Validate response
                if not response_text or not response_text.strip():
                    logger.error(f"[{request_id}] ❌ Empty response from LLM")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Empty response from LLM'})}\n\n"
                    return
                
                logger.info(f"[{request_id}] ✅ Received LLM response: {response_text[:100]}...")
                
                # Split response into sentences for chunked audio generation
                sentences = split_into_sentences(response_text)
                total_chunks = len(sentences)
                
                logger.info(f"[{request_id}] 📊 Split response into {total_chunks} sentences")
                
                # Send metadata first
                yield f"data: {json.dumps({'type': 'metadata', 'total_chunks': total_chunks, 'text': response_text})}\n\n"
                
                # Generate TTS for each sentence and stream
                for chunk_id, sentence in enumerate(sentences, 1):
                    try:
                        logger.info(f"[{request_id}] 🎵 Generating TTS for chunk {chunk_id}/{total_chunks}: '{sentence[:30]}...'")
                        audio_base64 = generate_sentence_audio(sentence, f"{request_id}-{chunk_id}")
                        
                        # Send audio chunk
                        chunk_data = {
                            'type': 'audio_chunk',
                            'chunk_id': chunk_id,
                            'text_chunk': sentence,
                            'audio_base64': audio_base64
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        logger.info(f"[{request_id}] ✅ Sent chunk {chunk_id}/{total_chunks}")
                        
                    except Exception as e:
                        logger.error(f"[{request_id}] ❌ Failed to generate TTS for chunk {chunk_id}: {e}")
                        # Send error for this chunk but continue with others
                        error_data = {
                            'type': 'chunk_error',
                            'chunk_id': chunk_id,
                            'text_chunk': sentence,
                            'error': str(e)
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                logger.info(f"[{request_id}] ✅ Streaming response completed successfully")
                
            except Exception as e:
                logger.error(f"[{request_id}] 💥 Error in streaming response generation: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(generate_streaming_response(), 
                       content_type='text/plain; charset=utf-8',
                       headers={'Cache-Control': 'no-cache'})
                       
    except Exception as e:
        logger.error(f"[{request_id}] 💥 Unexpected error in chat_stream_api: {e}")
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

def split_into_sentences(text):
    """Split text into sentences for streaming TTS generation"""
    import re
    
    # Simple sentence splitting on common sentence endings
    # This works well for pirate speech which tends to be short sentences
    sentences = re.split(r'[.!?]+\s+', text)
    
    # Filter out empty sentences and add back punctuation
    result = []
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if sentence:
            # Add punctuation back if not at the end
            if i < len(sentences) - 1:
                # Try to preserve original punctuation
                if text.find(sentence + '.') != -1:
                    sentence += '.'
                elif text.find(sentence + '!') != -1:
                    sentence += '!'
                elif text.find(sentence + '?') != -1:
                    sentence += '?'
                else:
                    sentence += '.'
            result.append(sentence)
    
    # If no sentences found, return the whole text as one sentence
    if not result:
        result = [text.strip()]
    
    return result

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
        # Generate TTS audio using ElevenLabs
        audio_base64 = tts_provider.generate_audio(sentence)
        
        generation_time = time.time() - start_time
        logger.info(f"[{request_id}] ✅ TTS generation completed in {generation_time:.3f}s for sentence: {sentence[:50]}...")
        
        return audio_base64
        
    except Exception as e:
        generation_time = time.time() - start_time
        logger.error(f"[{request_id}] ❌ TTS generation failed after {generation_time:.3f}s: {e}")
        raise Exception(f"TTS generation failed: {e}")

def validate_api_environment():
    """Validate API environment variables and dependencies"""
    errors = []
    
    # Check required environment variables
    llm_base_url = os.getenv("LLM_BASE_URL")
    if not llm_base_url:
        errors.append("LLM_BASE_URL environment variable is not set")
    
    # Check ElevenLabs TTS configuration
    print("✅ Using ElevenLabs TTS")
    
# CUDA check removed - no longer needed for ElevenLabs-only TTS
    
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