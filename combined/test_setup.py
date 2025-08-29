#!/usr/bin/env python3
"""
Test script to validate the combined pirate assistant setup
without requiring microphone input.
"""

import os
import sys
from dotenv import load_dotenv

def test_environment():
    """Test environment configuration"""
    print("🧪 Testing environment configuration...")
    
    load_dotenv()
    
    errors = []
    
    # Check required environment variables
    required_vars = {
        "OPENAI_API_KEY": "OpenAI API key",
        "ELEVENLABS_API_KEY": "ElevenLabs API key", 
        "ELEVENLABS_VOICE_ID": "ElevenLabs voice ID"
    }
    
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if not value:
            errors.append(f"Missing {var} ({desc})")
        else:
            print(f"✅ {desc}: {'*' * 8}")
    
    # Check Vosk model path
    vosk_path = os.getenv("VOSK_MODEL_PATH", "../stt/models/vosk-model-small-en-us-0.15")
    if os.path.exists(vosk_path):
        print(f"✅ Vosk model found: {vosk_path}")
    else:
        errors.append(f"Vosk model not found: {vosk_path}")
    
    if errors:
        print("\n❌ Environment errors:")
        for error in errors:
            print(f"  • {error}")
        return False
    else:
        print("\n✅ Environment configuration valid")
        return True

def test_imports():
    """Test all required imports"""
    print("\n🧪 Testing imports...")
    
    try:
        import vosk
        print("✅ vosk imported successfully")
    except ImportError as e:
        print(f"❌ vosk import failed: {e}")
        return False
    
    try:
        import sounddevice as sd
        print("✅ sounddevice imported successfully")
    except ImportError as e:
        print(f"❌ sounddevice import failed: {e}")
        return False
    
    try:
        import openai
        print("✅ openai imported successfully")
    except ImportError as e:
        print(f"❌ openai import failed: {e}")
        return False
    
    try:
        from elevenlabs.client import ElevenLabs
        print("✅ elevenlabs imported successfully")
    except ImportError as e:
        print(f"❌ elevenlabs import failed: {e}")
        return False
    
    print("\n✅ All imports successful")
    return True

def test_openai_connection():
    """Test OpenAI API connection"""
    print("\n🧪 Testing OpenAI connection...")
    
    try:
        import openai
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ No OpenAI API key found")
            return False
        
        client = openai.OpenAI(api_key=api_key)
        
        # Simple test request
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Say 'test successful' in pirate speak"}],
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip()
        print(f"✅ OpenAI test successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")
        return False

def test_elevenlabs_connection():
    """Test ElevenLabs API connection"""
    print("\n🧪 Testing ElevenLabs connection...")
    
    try:
        from elevenlabs.client import ElevenLabs
        
        api_key = os.getenv("ELEVENLABS_API_KEY")
        voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        
        if not api_key:
            print("❌ No ElevenLabs API key found")
            return False
            
        if not voice_id:
            print("❌ No ElevenLabs voice ID found")
            return False
        
        # Test client initialization
        client = ElevenLabs(api_key=api_key)
        print(f"✅ ElevenLabs client initialized with voice: {voice_id}")
        return True
        
    except Exception as e:
        print(f"❌ ElevenLabs test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🏴‍☠️ Combined Pirate Assistant Setup Test")
    print("=" * 50)
    
    all_passed = True
    
    # Test environment
    if not test_environment():
        all_passed = False
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test API connections
    if not test_openai_connection():
        all_passed = False
    
    if not test_elevenlabs_connection():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! The combined pirate assistant is ready to sail!")
        print("\nRun 'python main.py' to start the voice assistant.")
    else:
        print("❌ Some tests failed. Please fix the issues before running the main application.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())