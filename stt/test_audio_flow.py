#!/usr/bin/env python3
"""
Test script to debug the audio flow between filler and response playback
"""

import os
import sys
import asyncio
import time
import base64
import tempfile

# Set up environment
os.environ["FILLER_ENABLED"] = "true"
os.environ["AUDIO_PLAYER"] = "paplay"

# Import after setting environment
from filler_player import create_filler_player
from client import StreamingAudioPlayer, play_wav_bytes

async def test_audio_flow():
    """Test the complete audio flow from filler to response."""
    print("🧪 Testing audio flow between filler and response...")
    
    # Test 1: Create both audio systems
    print("\n--- Test 1: Initialize Audio Systems ---")
    
    filler_player = create_filler_player("paplay", None)
    if not filler_player:
        print("❌ Failed to create filler player")
        return False
    
    streaming_player = StreamingAudioPlayer(sink_name=None)
    print("✅ Both audio systems created")
    
    # Test 2: Start filler
    print("\n--- Test 2: Start Filler ---")
    success = filler_player.start_filler()
    if not success:
        print("❌ Failed to start filler")
        return False
    
    print("✅ Filler started, waiting 2 seconds...")
    await asyncio.sleep(2)
    
    # Test 3: Stop filler and immediately start streaming player
    print("\n--- Test 3: Stop Filler and Start Response ---")
    print("🛑 Stopping filler...")
    filler_player.stop_filler()
    print("✅ Filler stopped")
    
    # Create a simple WAV test audio (sine wave)
    print("🎵 Creating test audio chunk...")
    test_wav = create_test_wav()
    test_base64 = base64.b64encode(test_wav).decode()
    
    # Start streaming player and add test chunk
    streaming_player.start_playback()
    print(f"🔊 Streaming player started: {streaming_player.play_thread is not None}")
    
    streaming_player.add_audio_chunk(test_base64, 1)
    print(f"🎵 Test chunk added, queue size: {streaming_player.audio_queue.qsize()}")
    
    # Wait for playback
    print("⏳ Waiting for test audio to play...")
    streaming_player.wait_for_completion()
    streaming_player.stop_playback()
    
    print("✅ Audio flow test completed!")
    return True

def create_test_wav():
    """Create a simple test WAV file (1 second sine wave)."""
    import wave
    import math
    
    # Create a 1-second 440Hz sine wave
    sample_rate = 44100
    duration = 1.0
    frequency = 440
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        with wave.open(tmp_file.name, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            # Generate sine wave
            for i in range(int(sample_rate * duration)):
                value = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
                wav_file.writeframes(value.to_bytes(2, byteorder='little', signed=True))
        
        # Read the WAV file back
        with open(tmp_file.name, 'rb') as f:
            wav_data = f.read()
        
        # Clean up
        os.unlink(tmp_file.name)
        return wav_data

if __name__ == "__main__":
    success = asyncio.run(test_audio_flow())
    sys.exit(0 if success else 1)