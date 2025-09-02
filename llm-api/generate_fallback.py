#!/usr/bin/env python3
"""
Generate fallback audio message using ElevenLabs TTS
This ensures the fallback voice matches the main TTS voice
"""

import os
import base64
import requests
from dotenv import load_dotenv

def generate_fallback_audio():
    """Generate fallback audio using ElevenLabs API"""
    
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    
    if not api_key or not voice_id:
        print("Error: ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID must be set in .env file")
        return False
    
    # Fallback message in pirate character
    fallback_message = "Ahoy matey! Arr, me voice be havin' some trouble right now, but I be still here to chat with ye!"
    
    print(f"Generating fallback audio with voice ID: {voice_id}")
    print(f"Message: {fallback_message}")
    
    # ElevenLabs API endpoint
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": fallback_message,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.4,
            "style": 0.0,
            "use_speaker_boost": False
        }
    }
    
    try:
        print("Calling ElevenLabs API...")
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            print(f"ElevenLabs API error: {response.status_code} - {response.text}")
            return False
        
        # Encode audio as base64
        audio_data = response.content
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        # Save to fallback file
        fallback_path = "./assets/fallback_message_b64.txt"
        os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
        
        with open(fallback_path, 'w') as f:
            f.write(audio_b64)
        
        print("Fallback audio generated and saved!")
        print(f"Saved to: {fallback_path}")
        print(f"Audio length: {len(audio_b64)} base64 characters")
        print(f"Raw audio size: {len(audio_data)} bytes")
        
        return True
        
    except Exception as e:
        print(f"Error generating fallback audio: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = generate_fallback_audio()
    exit(0 if success else 1)