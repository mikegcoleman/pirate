#!/usr/bin/env python3
"""
Microphone Setup Script for Pirate Voice Assistant
Automatically configures microphone volume and sensitivity settings.
"""

import os
import subprocess
import sys

# Load environment variables
import dotenv
dotenv.load_dotenv()

def setup_microphone():
    """Configure microphone volume and sensitivity settings."""
    mic_device = os.getenv("MIC_DEVICE", "")
    mic_volume = os.getenv("MIC_VOLUME", "150%")
    
    if not mic_device:
        print("⚠️ MIC_DEVICE not set in .env file")
        return False
    
    print(f"🎤 Setting up microphone: {mic_device}")
    print(f"🔊 Setting volume to: {mic_volume}")
    
    try:
        # Set microphone volume
        result = subprocess.run([
            "pactl", "set-source-volume", mic_device, mic_volume
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Failed to set microphone volume: {result.stderr}")
            return False
        
        # Verify the setting
        result = subprocess.run([
            "pactl", "get-source-volume", mic_device
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Microphone volume set successfully:")
            print(f"   {result.stdout.strip()}")
        
        # Set as default input source
        result = subprocess.run([
            "pactl", "set-default-source", mic_device
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Set as default microphone")
        else:
            print(f"⚠️ Could not set as default: {result.stderr}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up microphone: {e}")
        return False

if __name__ == "__main__":
    if setup_microphone():
        print("\n🎤 Microphone setup complete!")
        print("💡 Test pickup distance with: python stt.py")
    else:
        print("\n❌ Microphone setup failed")
        sys.exit(1)