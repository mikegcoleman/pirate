#!/usr/bin/env python3
"""
Generate pirate filler phrase audio files using ElevenLabs API
"""

import requests
import os
from pathlib import Path

# ElevenLabs configuration from combined/.env
ELEVENLABS_API_KEY = "sk_71b236fc23adeebf226c35960f92c2068bb438e519665302"
ELEVENLABS_VOICE_ID = "Myn1LuZgd2qPMOg9BNtC"

# 25 Pirate filler phrases
FILLER_PHRASES = [
    "Arr, let me think on that, matey...",
    "That be a fine question, give ol' Bones a moment...",
    "Shiver me timbers, that's got me ponderin'...",
    "Interesting tale ye spin there, let me consider...",
    "Arr, me old bones need a moment to think...",
    "That be worthy of some deep thought, savvy?",
    "Blimey, ye've given me something to chew on...",
    "Let me consult me pirate wisdom, matey...",
    "Yo ho ho, that deserves proper consideration...",
    "Batten down the hatches while I think...",
    "By Blackbeard's beard, let me ponder that...",
    "Arr, me nautical mind be workin' on it...",
    "That be a treasure of a question, hold fast...",
    "Splice the mainbrace while I consider...",
    "Ahoy, give this old salt a moment...",
    "That's got me sea legs shakin' with thought...",
    "Arr, let me chart a course through that idea...",
    "By the seven seas, that needs pondering...",
    "Heave ho, let me weigh anchor on that thought...",
    "That be deeper than Davy Jones' locker...",
    "Arr, me compass be spinnin' on that one...",
    "All hands on deck while I think...",
    "That question's got more twists than a kraken...",
    "Let me dig through me treasure chest of knowledge...",
    "Arr, that be worth its weight in doubloons to consider..."
]

def generate_audio(text, filename):
    """Generate audio file using ElevenLabs TTS API"""
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        
        # Create audio directory if it doesn't exist
        audio_dir = Path("audio/fillers")
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Save audio file
        filepath = audio_dir / f"{filename}.mp3"
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        print(f"✅ Generated: {filepath}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error generating {filename}: {e}")
        return False

def main():
    """Generate all filler phrase audio files"""
    print("🎵 Generating pirate filler phrases...")
    
    success_count = 0
    
    for i, phrase in enumerate(FILLER_PHRASES, 1):
        filename = f"filler_{i:02d}"
        if generate_audio(phrase, filename):
            success_count += 1
    
    print(f"\n🏴‍☠️ Generated {success_count}/{len(FILLER_PHRASES)} pirate filler phrases!")
    print("Audio files saved in: audio/fillers/")

if __name__ == "__main__":
    main()