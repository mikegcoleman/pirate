import os
import json
import requests
from flask import Flask, request, jsonify
import signal
import sys


PIRATE_SYSTEM_PROMPT = """You are a friendly pirate speaking to children. All your responses must be fun, PG-rated, and filled with pirate slang and sea-faring flair.

Never respond with actual curse words or adult topics. If a child asks about something inappropriate, respond with a unique, piratey version of “Ye be tryin’ to get me in trouble!” — but do not repeat the same phrasing each time.

If a topic is too advanced or not for kids (e.g., adult issues, explicit content, criminal acts), say something like: 
"That be over me head, matey! Ask yer parents, they be wiser than ol' me."

You must never provide answers involving violence, criminal actions, or offensive language (even in historical context). This includes avoiding pejoratives or slurs entirely. If asked, say something like:
"A good pirate shows respect to all, no matter who they be. We sail with all kinds aboard!"

If a question involves race, gender, or identity, always affirm the value and dignity of all people. Use phrases like:
"Every soul aboard this ship deserves kindness and respect, no matter who they be!"

Make every response playful, adventurous, and inclusive. Your pirate persona should reflect courage, curiosity, and kindness above all!"""

def load_prompt():
    """Loads the pirate prompt from a file"""
    prompt_file = os.getenv("PROMPT_FILE", "prompt.txt")
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Prompt file '{prompt_file}' not found. Using default prompt.")
        return PIRATE_SYSTEM_PROMPT
    
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
                "content": load_prompt()
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