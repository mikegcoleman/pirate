#!/usr/bin/env python3
"""
Test script to verify filler integration works correctly
"""

import os
import sys
import asyncio
import time

# Set up environment for testing
os.environ["FILLER_ENABLED"] = "true"
os.environ["AUDIO_PLAYER"] = "paplay"
os.environ["API_URL"] = "http://localhost:8080/api/chat"
os.environ["LLM_MODEL"] = "test-model"
os.environ["TIMEOUT"] = "5"

# Import after setting environment
from filler_player import create_filler_player

async def test_filler_integration():
    """Test that filler integration works as expected."""
    print("🧪 Testing filler integration...")
    
    # Test 1: Create filler player
    print("\n--- Test 1: Create Filler Player ---")
    filler_player = create_filler_player("paplay", None)
    
    if not filler_player:
        print("❌ Failed to create filler player")
        return False
    
    print(f"✅ Filler player created with {len(filler_player.filler_files)} files")
    
    # Test 2: Start and stop filler
    print("\n--- Test 2: Start and Stop Filler ---")
    success = filler_player.start_filler()
    if not success:
        print("❌ Failed to start filler")
        return False
    
    print("✅ Filler started successfully")
    
    # Wait a moment then stop
    await asyncio.sleep(2)
    filler_player.stop_filler()
    print("✅ Filler stopped successfully")
    
    # Test 3: Multiple rapid start/stop cycles
    print("\n--- Test 3: Rapid Start/Stop Cycles ---")
    for i in range(3):
        print(f"Cycle {i+1}/3")
        filler_player.start_filler()
        await asyncio.sleep(0.5)  # Brief delay
        filler_player.stop_filler()
        await asyncio.sleep(0.2)  # Brief pause between cycles
    
    print("✅ Rapid cycles completed successfully")
    
    print("\n🎉 All filler integration tests passed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_filler_integration())
    sys.exit(0 if success else 1)