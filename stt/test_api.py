p#!/usr/bin/env python3
"""
Quick API test script for the pirate chat API
Tests both regular and streaming endpoints
"""

import requests
import json
import sys
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://192.168.50.176:8080"
MODEL = "ai/llama3.2:latest"

def test_health():
    """Test the health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False

def test_chat_endpoint(message="Ahoy there, matey!"):
    """Test the regular chat endpoint"""
    print(f"\n💬 Testing chat endpoint with: '{message}'")
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a friendly pirate assistant named Mr. Bones."},
            {"role": "user", "content": message}
        ]
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/chat",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        elapsed = time.time() - start_time
        
        print(f"   Status: {response.status_code}")
        print(f"   Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            if "response" in data:
                print(f"   ✅ Response: {data['response']}")
                if "audio_base64" in data:
                    print(f"   🔊 Audio: {len(data['audio_base64'])} chars")
                else:
                    print(f"   🔇 No audio (expected if TTS fails)")
                if "error" in data:
                    print(f"   ⚠️  Warning: {data['error']}")
                return True
            else:
                print(f"   ❌ No 'response' field in: {data}")
                return False
        else:
            print(f"   ❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return False

def test_streaming_endpoint(message="Tell me a short pirate joke!"):
    """Test the streaming chat endpoint"""
    print(f"\n🌊 Testing streaming endpoint with: '{message}'")
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a friendly pirate assistant named Mr. Bones."},
            {"role": "user", "content": message}
        ]
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/chat/stream",
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            },
            json=payload,
            timeout=60,
            stream=True
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Error: {response.text}")
            return False
        
        print("   📡 Streaming response:")
        full_response = ""
        chunk_count = 0
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    try:
                        chunk_data = json.loads(data_str)
                        chunk_type = chunk_data.get('type', 'unknown')
                        
                        if chunk_type == 'text_preview':
                            sentence = chunk_data.get('sentence', '')
                            print(f"      📝 Preview: {sentence}")
                            
                        elif chunk_type == 'audio_chunk':
                            sentence = chunk_data.get('sentence', '')
                            audio_size = len(chunk_data.get('audio_base64', ''))
                            print(f"      🔊 Audio: {sentence} ({audio_size} chars)")
                            full_response += sentence + " "
                            chunk_count += 1
                            
                        elif chunk_type == 'text_chunk':
                            sentence = chunk_data.get('sentence', '')
                            error = chunk_data.get('error', '')
                            print(f"      🔇 Text only: {sentence} (Error: {error})")
                            full_response += sentence + " "
                            chunk_count += 1
                            
                        elif chunk_type == 'complete':
                            elapsed = time.time() - start_time
                            print(f"      ✅ Complete in {elapsed:.2f}s")
                            print(f"      📊 Chunks: {chunk_count}")
                            print(f"      📝 Full response: {full_response.strip()}")
                            return True
                            
                        elif chunk_type == 'error':
                            error = chunk_data.get('error', 'Unknown error')
                            print(f"      ❌ Stream error: {error}")
                            return False
                            
                    except json.JSONDecodeError:
                        print(f"      ⚠️  Invalid JSON: {data_str}")
                        continue
        
        print("   ⚠️  Stream ended without completion signal")
        return False
        
    except Exception as e:
        print(f"   ❌ Streaming request failed: {e}")
        return False

def main():
    """Run all tests"""
    print(f"🏴‍☠️ Pirate API Test Suite")
    print(f"🌐 Target: {API_BASE_URL}")
    print(f"🤖 Model: {MODEL}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    results = []
    
    # Test health
    results.append(("Health Check", test_health()))
    
    # Test regular chat
    results.append(("Chat Endpoint", test_chat_endpoint()))
    
    # Test streaming
    results.append(("Streaming Endpoint", test_streaming_endpoint()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! API is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check the API server logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()