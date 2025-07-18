#!/usr/bin/env python3
"""
Test script to debug HTTP request issues
"""
import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

async def test_request():
    """Test the HTTP request directly"""
    if not API_URL:
        print("ERROR: API_URL not found in environment variables")
        return
        
    chat_request = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello"}
        ]
    }
    
    print(f"Testing request to: {API_URL}")
    print(f"Request payload: {json.dumps(chat_request, indent=2)}")
    
    try:
        # Test with different client configurations
        print("\n1. Testing with default httpx.AsyncClient()...")
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, json=chat_request, timeout=10)
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text[:200]}...")
            
    except Exception as e:
        print(f"Error with default client: {e}")
    
    try:
        print("\n2. Testing with verify=False...")
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(API_URL, json=chat_request, timeout=10)
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text[:200]}...")
            
    except Exception as e:
        print(f"Error with verify=False: {e}")
    
    try:
        print("\n3. Testing with specific headers...")
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, json=chat_request, headers=headers, timeout=10)
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text[:200]}...")
            
    except Exception as e:
        print(f"Error with headers: {e}")

if __name__ == "__main__":
    asyncio.run(test_request())
