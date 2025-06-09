import os
import json
import requests
from flask import Flask, request, jsonify, send_file
import signal
import sys
from TTS.api import TTS
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

# Initialize Coqui TTS model (load once)
use_gpu = torch.cuda.is_available()

tts_engine = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
if use_gpu:
    try:
        tts_engine.to("cuda")
    except RuntimeError as e:
        print("⚠️ Could not use GPU for TTS, falling back to CPU:", e)
        tts_engine.to("cpu")
else:
    tts_engine.to("cpu")

def get_llm_endpoint():
    """Returns the complete LLM API endpoint URL"""
    base_url = os.getenv("LLM_BASE_URL", "")
    return f"{base_url}/chat/completions"

@app.route('/')
def index():
    return "Welcome to the pirate LLM chat API! Use /api/chat to interact with the model.", 200

@app.route('/api/chat', methods=['POST'])
def chat_api():
    """Processes chat API requests"""
    chat_request = request.json
    print(json.dumps(chat_request, indent=2))

    if not chat_request:
        return jsonify({'error': 'No Data Received'}), 400

    # Call the LLM API
    try:
        response_text = call_llm_api(chat_request)
        # Generate TTS audio for the response
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
            tts_engine.tts_to_file(text=response_text, file_path=tmp_audio.name)
            tmp_audio.seek(0)
            audio_bytes = tmp_audio.read()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        return jsonify({'response': response_text, 'audio_base64': audio_b64})
    except Exception as e:
        app.logger.error(f"Error calling LLM API: {e}")
        return jsonify({'error': 'Failed to get response from LLM'}), 500

def call_llm_api(chat_request):
    """Calls the LLM API and returns the response"""
    
    headers = {"Content-Type": "application/json"}
    
    # Send request to LLM API
    response = requests.post(
        get_llm_endpoint(),
        headers=headers,
        json=chat_request,
        timeout=30
    )
    
    # Check if the status code is not 200 OK
    if response.status_code != 200:
        raise Exception(f"API returned status code {response.status_code}: {response.text}")
    
    # Parse the response
    chat_response = response.json()
    
    # Extract the assistant's message
    if chat_response.get('choices') and len(chat_response['choices']) > 0:
        return chat_response['choices'][0]['message']['content'].strip()
    
    raise Exception("No response choices returned from API")

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    
    print(f"Server starting on http://localhost:{port}")
    print(f"Using LLM endpoint: {get_llm_endpoint()}")
    
    app.run(host='0.0.0.0', port=port, debug=os.getenv("DEBUG", "false").lower() == "true")