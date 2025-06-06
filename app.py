import os
import json
import requests
from flask import Flask, request, jsonify
import signal
import sys


PIRATE_SYSTEM_PROMPT = """You are a pirate. You are speaking to children. 
If they ask you a question that is inappropriate for children, do not answer it. 
Instead respond "Oh, you're trying to get me in trouble". 
If a topic is too advanced for children respond with 
"Well, I'm not smart enough to talk about that with you. You should go ask your parents". 
The conversation should be kept PG rated — no swear words at all, ever."""

def handle_shutdown(signum, frame):
    print(f"🔌 Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

app = Flask(__name__)

def get_llm_endpoint():
    """Returns the complete LLM API endpoint URL"""
    base_url = os.getenv("LLM_BASE_URL", "")
    return f"{base_url}/chat/completions"

def get_model_name():
    """Returns the model name to use for API requests"""
    return os.getenv("LLM_MODEL_NAME", "")

@app.route('/')
def index():
    return "Welcome to the pirate LLM chat API! Use /api/chat to interact with the model.", 200

@app.route('/api/chat', methods=['POST'])
def chat_api():
    """Processes chat API requests"""
    data = request.json
    message = data.get('message', '')
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Call the LLM API
    try:
        print(f"🦜 Received message: {message}")
        app.logger.info(f"Received message: {message}")
        response = call_llm_api(message)
        return jsonify({'response': response})
    except Exception as e:
        app.logger.error(f"Error calling LLM API: {e}")
        return jsonify({'error': 'Failed to get response from LLM'}), 500

def call_llm_api(user_message):
    """Calls the LLM API and returns the response"""
    chat_request = {
        "model": get_model_name(),
        "messages": [
            {
                "role": "system",
                "content": PIRATE_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    }
    
    headers = {"Content-Type": "application/json"}
    
    # Send request to LLM API
    print(f"Sending request to LLM API: {json.dumps(chat_request, indent=2)}")
    print(f"Using model: {get_model_name()}")
    print(f"Using endpoint: {get_llm_endpoint()}")
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
    print(f"Using model: {get_model_name()}")
    
    app.run(host='0.0.0.0', port=port, debug=os.getenv("DEBUG", "false").lower() == "true")