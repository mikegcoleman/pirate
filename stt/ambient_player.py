#!/usr/bin/env python3
"""
Ambient Audio Player for Mr. Bones Pirate Assistant

Provides continuous background ambience audio that loops at low volume.
The ambient audio continues playing during filler phrases and API responses,
but at a volume that doesn't interfere with speech.
"""

import os
import subprocess
import threading
import time
import tempfile
from typing import Optional
from logger_utils import get_logger, generate_operation_id

# Initialize logger
logger = get_logger("ambient-player")


class AmbientPlayer:
    """Manages continuous ambient audio playback with low volume looping."""
    
    def __init__(self, audio_file_path: str, audio_player: str = "paplay", sink_name: Optional[str] = None, volume: float = 0.3):
        """
        Initialize the ambient player.
        
        Args:
            audio_file_path: Path to the ambient audio file (MP3)
            audio_player: Audio player command (paplay, aplay, etc.)
            sink_name: Optional PulseAudio sink name for routing
            volume: Volume level (0.0 to 1.0, default 0.3 for background)
        """
        self.audio_file_path = audio_file_path
        self.audio_player = audio_player
        self.sink_name = sink_name
        self.volume = volume
        
        self.is_playing = False
        self.stop_event = threading.Event()
        self.play_thread = None
        
        # Validate audio file exists
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Ambient audio file not found: {audio_file_path}")

        # Generate operation ID for background ambient playback
        self.op_id = generate_operation_id()

        logger.info("Ambient player initialized",
                    file=os.path.basename(audio_file_path),
                    volume_percent=int(volume*100),
                    opId=self.op_id)
    
    def start_ambient(self):
        """Start continuous ambient audio playback."""
        if self.is_playing:
            logger.warn("Ambient audio already playing", opId=self.op_id)
            return

        self.is_playing = True
        self.stop_event.clear()
        self.play_thread = threading.Thread(target=self._ambient_loop, daemon=True)
        self.play_thread.start()
        logger.info("Started ambient audio",
                    file=os.path.basename(self.audio_file_path),
                    opId=self.op_id)
    
    def stop_ambient(self):
        """Stop ambient audio playback."""
        if not self.is_playing:
            return

        self.stop_event.set()
        if self.play_thread:
            self.play_thread.join(timeout=3)
        self.is_playing = False
        logger.info("Stopped ambient audio", opId=self.op_id)
    
    def _ambient_loop(self):
        """Worker thread that continuously loops the ambient audio."""
        logger.debug("Ambient loop started", volume_percent=int(self.volume*100), opId=self.op_id)
        
        while not self.stop_event.is_set():
            try:
                # Calculate volume for paplay (0-65536 scale)
                paplay_volume = int(self.volume * 65536)
                
                # Build command
                cmd = [self.audio_player]
                if self.sink_name:
                    cmd.extend(["--device", self.sink_name])
                cmd.extend(["--volume", str(paplay_volume)])
                cmd.append(self.audio_file_path)
                
                # Play the file
                process = subprocess.Popen(cmd, 
                                         stdout=subprocess.DEVNULL, 
                                         stderr=subprocess.DEVNULL)
                
                # Wait for completion or stop signal
                while process.poll() is None:
                    if self.stop_event.wait(0.1):  # Check every 100ms
                        process.terminate()
                        break
                
                # Clean up process
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                
                # Small gap between loops (only if not stopping)
                if not self.stop_event.is_set():
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"❌ Ambient playback error: {e}")
                if not self.stop_event.is_set():
                    time.sleep(1)  # Wait before retry
        
        print("🌊 Ambient loop stopped")
    
    def is_ambient_playing(self) -> bool:
        """Check if ambient audio is currently playing."""
        return self.is_playing and self.play_thread and self.play_thread.is_alive()
    
    def set_volume(self, volume: float):
        """
        Adjust ambient volume (0.0 to 1.0).
        Note: This only affects new playback cycles, not current one.
        """
        self.volume = max(0.0, min(1.0, volume))
        print(f"🌊 Ambient volume set to {self.volume*100:.0f}%")


def create_ambient_player(audio_player: str, sink_name: Optional[str] = None, volume: float = 0.3) -> Optional[AmbientPlayer]:
    """
    Create and return an ambient audio player for the default ambience file.
    
    Args:
        audio_player: Audio player command (paplay, aplay, etc.)
        sink_name: Optional PulseAudio sink name for routing
        volume: Volume level (0.0 to 1.0, default 0.3 for background)
    
    Returns:
        AmbientPlayer instance or None if file not found
    """
    # Look for ambience file in the expected location
    ambience_file = "audio/ambience/ambience.mp3"
    
    if not os.path.exists(ambience_file):
        print(f"⚠️ Ambience file not found: {ambience_file}")
        return None
    
    try:
        return AmbientPlayer(ambience_file, audio_player, sink_name, volume)
    except Exception as e:
        print(f"❌ Failed to create ambient player: {e}")
        return None


if __name__ == "__main__":
    """Test the ambient player."""
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print("\n🛑 Stopping ambient test...")
        if player:
            player.stop_ambient()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🧪 Testing ambient player...")
    player = create_ambient_player("paplay", volume=0.2)
    
    if player:
        player.start_ambient()
        print("🌊 Ambient playing... Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        print("❌ Failed to create ambient player")