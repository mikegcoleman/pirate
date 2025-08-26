#!/usr/bin/env python3
"""
Performance test comparing different LLM + TTS combinations:
1. Local LLM + Kokoro TTS (via local API)
2. Local LLM + ElevenLabs TTS (Docker Model Runner + ElevenLabs)
3. OpenAI + ElevenLabs TTS

Tests response time for the question: "of all the places you've sailed where's your favorite and why"
"""

import asyncio
import httpx
import time
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.test
load_dotenv('.env.test')

# Configuration from environment
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID')

# Local endpoints
LOCAL_API_URL = os.getenv('LOCAL_API_URL', 'http://192.168.50.66:8080/api/chat')  # Your app.py with Kokoro on Windows machine
DOCKER_MODEL_RUNNER_URL = os.getenv('DOCKER_MODEL_RUNNER_URL', 'http://localhost:12434/engines/llama.cpp/v1/chat/completions')  # Local LLM direct - must run on Windows machine

# Test question
TEST_QUESTION = "of all the places you've sailed where's your favorite and why"

# System prompt from prompt.txt
SYSTEM_PROMPT = """You are "Mr. Bones," a friendly pirate who loves chatting with kids in a playful pirate voice.

IMPORTANT RULES:
- Never break character or speak as anyone but Mr. Bones
- Never reference real-world danger, violence, alcohol, drugs, weapons, or unsafe behavior
- Never discuss inappropriate content or give medical/legal advice
- Always be kind, curious, and age-appropriate

BEHAVIOR:
- Speak in a warm, playful pirate voice using words like "matey," "arr," "aye," "shiver me timbers"
- Be imaginative and whimsical - talk about treasure, ships, islands, sea creatures, maps
- Keep responses conversational and engaging for voice interaction
- If interrupted or confused, ask for clarification in character

FORMAT:
- Keep responses between 50-75 words for natural conversation flow
- Use normal punctuation only (no emojis or asterisks)
- Avoid abbreviations - use "Mister" not "Mr.", "Do Not" instead of "Don't"
- End responses naturally to encourage continued conversation"""

class PerformanceTest:
    def __init__(self):
        self.timeout = 60.0
        
    async def test_local_llm_kokoro(self):
        """Test 1: Local LLM + Kokoro TTS via local API"""
        print("🧪 Testing Local LLM + Kokoro TTS...")
        
        payload = {
            "model": "ai/llama3.2:latest",  # Matches Windows llm-api configuration
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": TEST_QUESTION}
            ]
        }
        
        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(LOCAL_API_URL, json=payload, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                total_time = time.time() - start_time
                
                print(f"✅ Local LLM + Kokoro: {total_time:.3f}s total")
                print(f"📝 Response: {data.get('response', 'No response')[:100]}...")
                if "audio_base64" in data:
                    print(f"🎵 Audio generated: {len(data['audio_base64'])} chars")
                else:
                    print("❌ No audio in response")
                    
                return {
                    "config": "Local LLM + Kokoro",
                    "total_time": total_time,
                    "llm_time": "N/A (combined)",
                    "tts_time": "N/A (combined)",
                    "success": True,
                    "response_text": data.get('response', 'No response')
                }
                
        except Exception as e:
            print(f"❌ Local LLM + Kokoro failed: {e}")
            return {
                "config": "Local LLM + Kokoro", 
                "success": False, 
                "error": str(e),
                "total_time": time.time() - start_time
            }
    
    async def test_local_llm_elevenlabs(self):
        """Test 2: Local LLM (Docker Model Runner) + ElevenLabs TTS"""
        print("🧪 Testing Local LLM + ElevenLabs TTS...")
        
        # Step 1: Get response from local LLM
        llm_start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                llm_payload = {
                    "model": "ai/llama3.2:latest",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": TEST_QUESTION}
                    ]
                }
                
                llm_response = await client.post(DOCKER_MODEL_RUNNER_URL, json=llm_payload, timeout=self.timeout)
                llm_response.raise_for_status()
                llm_data = llm_response.json()
                
                llm_time = time.time() - llm_start
                response_text = llm_data["choices"][0]["message"]["content"]
                
                print(f"✅ Local LLM: {llm_time:.3f}s")
                print(f"📝 Response: {response_text[:100]}...")
                
        except Exception as e:
            print(f"❌ Local LLM failed: {e}")
            return {
                "config": "Local LLM + ElevenLabs",
                "success": False,
                "error": f"LLM error: {str(e)}",
                "llm_time": time.time() - llm_start
            }
        
        # Step 2: Generate TTS with ElevenLabs
        tts_start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
                tts_headers = {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": ELEVENLABS_API_KEY
                }
                tts_payload = {
                    "text": response_text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.5
                    }
                }
                
                tts_response = await client.post(tts_url, json=tts_payload, headers=tts_headers, timeout=self.timeout)
                tts_response.raise_for_status()
                
                tts_time = time.time() - tts_start
                total_time = llm_time + tts_time
                
                print(f"✅ ElevenLabs TTS: {tts_time:.3f}s")
                print(f"🎵 Audio generated: {len(tts_response.content)} bytes")
                
                return {
                    "config": "Local LLM + ElevenLabs",
                    "total_time": total_time,
                    "llm_time": llm_time,
                    "tts_time": tts_time,
                    "success": True,
                    "response_text": response_text
                }
                
        except Exception as e:
            print(f"❌ ElevenLabs TTS failed: {e}")
            return {
                "config": "Local LLM + ElevenLabs",
                "success": False,
                "error": f"TTS error: {str(e)}",
                "llm_time": llm_time,
                "tts_time": time.time() - tts_start
            }
    
    async def test_openai_elevenlabs(self):
        """Test 3: OpenAI + ElevenLabs TTS"""
        print("🧪 Testing OpenAI + ElevenLabs TTS...")
        
        # Step 1: Get response from OpenAI
        llm_start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                openai_headers = {
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                openai_payload = {
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": TEST_QUESTION}
                    ]
                }
                
                openai_response = await client.post("https://api.openai.com/v1/chat/completions", 
                                                   json=openai_payload, headers=openai_headers, timeout=self.timeout)
                openai_response.raise_for_status()
                openai_data = openai_response.json()
                
                llm_time = time.time() - llm_start
                response_text = openai_data["choices"][0]["message"]["content"]
                
                print(f"✅ OpenAI: {llm_time:.3f}s")
                print(f"📝 Response: {response_text[:100]}...")
                
        except Exception as e:
            print(f"❌ OpenAI failed: {e}")
            return {
                "config": "OpenAI + ElevenLabs",
                "success": False,
                "error": f"OpenAI error: {str(e)}",
                "llm_time": time.time() - llm_start
            }
        
        # Step 2: Generate TTS with ElevenLabs (same as test 2)
        tts_start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
                tts_headers = {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": ELEVENLABS_API_KEY
                }
                tts_payload = {
                    "text": response_text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.5
                    }
                }
                
                tts_response = await client.post(tts_url, json=tts_payload, headers=tts_headers, timeout=self.timeout)
                tts_response.raise_for_status()
                
                tts_time = time.time() - tts_start
                total_time = llm_time + tts_time
                
                print(f"✅ ElevenLabs TTS: {tts_time:.3f}s")
                print(f"🎵 Audio generated: {len(tts_response.content)} bytes")
                
                return {
                    "config": "OpenAI + ElevenLabs",
                    "total_time": total_time,
                    "llm_time": llm_time,
                    "tts_time": tts_time,
                    "success": True,
                    "response_text": response_text
                }
                
        except Exception as e:
            print(f"❌ ElevenLabs TTS failed: {e}")
            return {
                "config": "OpenAI + ElevenLabs",
                "success": False,
                "error": f"TTS error: {str(e)}",
                "llm_time": llm_time,
                "tts_time": time.time() - tts_start
            }

async def main():
    """Run all performance tests"""
    print("🏴‍☠️ Mr. Bones Performance Test")
    print("=" * 50)
    print(f"Test question: '{TEST_QUESTION}'")
    print("=" * 50)
    
    test = PerformanceTest()
    results = []
    
    # Run all tests
    results.append(await test.test_local_llm_kokoro())
    print()
    results.append(await test.test_local_llm_elevenlabs()) 
    print()
    results.append(await test.test_openai_elevenlabs())
    print()
    
    # Summary
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 50)
    
    for result in results:
        if result["success"]:
            print(f"✅ {result['config']}")
            print(f"   Total: {result['total_time']:.3f}s")
            if result.get("llm_time") != "N/A (combined)":
                print(f"   LLM: {result['llm_time']:.3f}s")
                print(f"   TTS: {result['tts_time']:.3f}s")
            print()
        else:
            print(f"❌ {result['config']}: {result['error']}")
            print()

if __name__ == "__main__":
    asyncio.run(main())