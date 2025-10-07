#!/usr/bin/env python3
"""
Simple test to check if audio device conflicts exist between filler and response
"""

import os
import subprocess
import threading
import time
import tempfile
import wave
import math

def create_test_wav(filename, duration=1.0, frequency=440):
    """Create a simple test WAV file."""
    sample_rate = 44100
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        # Generate sine wave
        for i in range(int(sample_rate * duration)):
            value = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            wav_file.writeframes(value.to_bytes(2, byteorder='little', signed=True))

def play_audio_file(filename, label):
    """Play an audio file and measure timing."""
    print(f"🎵 Playing {label}...")
    start_time = time.time()
    
    result = subprocess.run(["paplay", filename], capture_output=True)
    
    end_time = time.time()
    duration = end_time - start_time
    
    if result.returncode == 0:
        print(f"✅ {label} completed in {duration:.2f}s")
        return True
    else:
        print(f"❌ {label} failed: {result.stderr.decode()}")
        return False

def test_sequential_playback():
    """Test playing audio files one after another."""
    print("🧪 Testing sequential audio playback...")
    
    # Create two test files
    with tempfile.NamedTemporaryFile(suffix="_filler.wav", delete=False) as f1:
        filler_file = f1.name
    with tempfile.NamedTemporaryFile(suffix="_response.wav", delete=False) as f2:
        response_file = f2.name
    
    try:
        create_test_wav(filler_file, duration=2.0, frequency=440)  # 2 sec, 440Hz
        create_test_wav(response_file, duration=1.0, frequency=880)  # 1 sec, 880Hz
        
        # Test 1: Play filler, then response
        print("\n--- Test 1: Sequential Playback ---")
        success1 = play_audio_file(filler_file, "Filler")
        success2 = play_audio_file(response_file, "Response")
        
        if success1 and success2:
            print("✅ Sequential playback works")
        else:
            print("❌ Sequential playback failed")
            return False
        
        # Test 2: Interrupt filler, then play response
        print("\n--- Test 2: Interrupt Filler Test ---")
        
        def interrupt_after_delay():
            time.sleep(1.0)  # Let filler play for 1 second
            print("🛑 Interrupting filler...")
            # Find and kill paplay process
            subprocess.run(["pkill", "-f", "paplay.*filler"], capture_output=True)
        
        # Start filler in background
        print("🎭 Starting filler (will be interrupted)...")
        filler_process = subprocess.Popen(["paplay", filler_file])
        
        # Start interrupt timer
        interrupt_thread = threading.Thread(target=interrupt_after_delay)
        interrupt_thread.start()
        
        # Wait for filler to finish or be killed
        filler_process.wait()
        interrupt_thread.join()
        
        print("⏳ Brief pause to let audio device settle...")
        time.sleep(0.2)
        
        # Now try to play response
        success3 = play_audio_file(response_file, "Response after interrupt")
        
        if success3:
            print("✅ Interrupt and recovery works")
        else:
            print("❌ Response failed after interrupt")
            return False
        
        print("\n🎉 All audio conflict tests passed!")
        return True
        
    finally:
        # Clean up
        try:
            os.unlink(filler_file)
            os.unlink(response_file)
        except:
            pass

if __name__ == "__main__":
    success = test_sequential_playback()
    exit(0 if success else 1)