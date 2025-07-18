#!/usr/bin/env python3
"""
Test script to exactly replicate the main.py request
"""
import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

def load_prompt():
    """Load the system prompt from the prompt file."""
    prompt_file = os.getenv("PROMPT_FILE", "prompt.txt")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r") as f:
            return f.read().strip()
    return "You are a helpful assistant."

async def send_request(chat_request):
    """Exact copy of send_request from main.py"""
    if not API_URL:
        raise ValueError("API_URL not configured")
        
    if LLM_MODEL and LLM_MODEL.startswith("ai/mistral"):
        # This won't execute for mgc0216/pirate-mistral:Q4_K_M
        print("Applying Mistral formatting...")
        pass
        
    print("Sending request to LLM API:", json.dumps(chat_request, indent=2))
    async with httpx.AsyncClient() as client:
        return await client.post(API_URL, json=chat_request, timeout=90)

async def test_exact_request():
    """Test the exact request that main.py makes"""
    if not API_URL:
        print("ERROR: API_URL not found in environment variables")
        return
    
    # Build the exact same request as main.py
    messages = [{"role": "system", "content": load_prompt()}]
    
    # Simulate user input
    test_text = "Hello, say something pirate-like"
    messages.append({"role": "user", "content": test_text})
    
    chat_request = {
        "model": LLM_MODEL,
        "messages": messages
    }
    
    print(f"Testing exact main.py request to: {API_URL}")
    print(f"Model: {LLM_MODEL}")
    
    try:
        response = await send_request(chat_request)
        print(f"Response status: {response.status_code}")
        response.raise_for_status()
        response_data = response.json()
        if "error" in response_data:
            print("Error from API:", response_data["error"])
        else:
            print("Success! Got response from API")
            if "response" in response_data:
                print(f"Response text: {response_data['response'][:100]}...")
            if "audio_base64" in response_data:
                print("Audio response included")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_exact_request())
