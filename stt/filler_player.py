#!/usr/bin/env python3
"""
Filler Phrase Player for Mr. Bones Pirate Assistant

Plays pre-recorded filler phrases while waiting for API responses to make
Mr. Bones feel more responsive and engaging during processing delays.

Features:
- Random selection from available filler audio files
- Thread-safe playback that can be interrupted
- Respects audio routing configuration (Bluetooth speaker, etc.)
- Prevents playing same filler twice in a row
"""

import os
import random
import threading
import subprocess
import tempfile
import time
from typing import Optional, List
from pathlib import Path

class FillerPlayer:
    """Manages playback of filler phrases during API response delays."""
    
    def __init__(self, filler_dir: str, audio_player: str = "paplay", sink_name: Optional[str] = None):
        """
        Initialize the filler player.
        
        Args:
            filler_dir: Directory containing filler MP3 files
            audio_player: Audio player command (paplay, aplay, etc.)
            sink_name: Optional PulseAudio sink name for routing
        """
        self.filler_dir = Path(filler_dir)
        self.audio_player = audio_player
        self.sink_name = sink_name
        self.filler_files = self._discover_filler_files()
        self.last_played = None
        self.is_playing = False
        self.stop_event = threading.Event()
        self.play_thread = None
        
        if not self.filler_files:
            raise ValueError(f"No filler audio files found in {filler_dir}")
        
        print(f"🎵 FillerPlayer initialized with {len(self.filler_files)} filler phrases")
    
    def _discover_filler_files(self) -> List[Path]:
        """Discover all filler audio files in the directory."""
        if not self.filler_dir.exists():
            return []
        
        # Look for MP3 files matching filler_*.mp3 pattern
        filler_files = list(self.filler_dir.glob("filler_*.mp3"))
        filler_files.sort()  # Ensure consistent ordering
        return filler_files
    
    def _select_random_filler(self) -> Path:
        """Select a random filler file, avoiding the last played one if possible."""
        available_files = self.filler_files.copy()
        
        # If we have more than one file, avoid repeating the last one
        if len(available_files) > 1 and self.last_played:
            try:
                available_files.remove(self.last_played)
            except ValueError:
                pass  # File no longer exists, ignore
        
        selected = random.choice(available_files)
        self.last_played = selected
        return selected
    
    def _play_audio_file(self, file_path: Path) -> bool:
        """
        Play an audio file using the configured audio player.
        
        Args:
            file_path: Path to the audio file to play
            
        Returns:
            True if playback succeeded, False otherwise
        """
        try:
            # Read the MP3 file into memory
            with open(file_path, 'rb') as f:
                audio_bytes = f.read()
            
            # Create temporary file for playback
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
                tmp_path = tmp_file.name
            
            # Build playback command
            cmd = [self.audio_player]
            if self.sink_name:
                cmd.extend(["--device", self.sink_name])
            cmd.extend(["--volume", "65536"])  # Max volume
            cmd.append(tmp_path)
            
            # Play the audio (this blocks until playback completes or is interrupted)
            # Use Popen so we can terminate if needed
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Poll the process until it completes or we're asked to stop
            while process.poll() is None:
                if self.stop_event.is_set():
                    # Terminate the audio playback process
                    process.terminate()
                    try:
                        process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    break
                time.sleep(0.05)  # Small delay to avoid busy waiting
            
            # Get the result
            if process.returncode is None:
                # Process was terminated
                return False
            
            stdout, stderr = process.communicate()
            result = type('Result', (), {
                'returncode': process.returncode, 
                'stdout': stdout, 
                'stderr': stderr
            })()
            
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            
            if result.returncode == 0:
                return True
            else:
                print(f"⚠️ Filler playback failed (exit code {result.returncode})")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()}")
                return False
                
        except Exception as e:
            print(f"❌ Error playing filler audio: {e}")
            return False
    
    def _playback_worker(self):
        """Worker thread that plays filler audio."""
        try:
            selected_filler = self._select_random_filler()
            filler_name = selected_filler.name
            
            print(f"🎭 Playing filler: {filler_name}")
            
            # Check if we should stop before starting playback
            if self.stop_event.is_set():
                print("🛑 Filler playback cancelled before starting")
                return
            
            success = self._play_audio_file(selected_filler)
            
            if success and not self.stop_event.is_set():
                print(f"✅ Filler completed: {filler_name}")
            elif self.stop_event.is_set():
                print(f"🛑 Filler interrupted: {filler_name}")
            else:
                print(f"❌ Filler failed: {filler_name}")
        finally:
            # Always reset playing state when worker completes
            self.is_playing = False
    
    def start_filler(self) -> bool:
        """
        Start playing a random filler phrase in a background thread.
        
        Returns:
            True if filler playback started successfully, False otherwise
        """
        if self.is_playing:
            print("⚠️ Filler already playing, skipping")
            return False
        
        if not self.filler_files:
            print("⚠️ No filler files available")
            return False
        
        self.stop_event.clear()
        self.is_playing = True
        
        self.play_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.play_thread.start()
        
        return True
    
    def stop_filler(self):
        """Stop the currently playing filler phrase."""
        if not self.is_playing:
            return
        
        print("🛑 Stopping filler playback...")
        self.stop_event.set()
        
        # Wait for playback thread to finish (with timeout)
        if self.play_thread:
            self.play_thread.join(timeout=2.0)
        
        self.is_playing = False
        
        # Brief delay to allow audio device to be released
        import time
        time.sleep(0.1)
    
    def is_filler_playing(self) -> bool:
        """Check if a filler is currently playing."""
        return self.is_playing and self.play_thread and self.play_thread.is_alive()

def create_filler_player(audio_player: str = "paplay", sink_name: Optional[str] = None) -> Optional[FillerPlayer]:
    """
    Create a FillerPlayer instance with default configuration.
    
    Args:
        audio_player: Audio player command
        sink_name: Optional PulseAudio sink name
        
    Returns:
        FillerPlayer instance or None if filler directory not found
    """
    # Look for filler directory relative to the script location
    script_dir = Path(__file__).parent
    filler_dir = script_dir / "audio" / "fillers"
    
    if not filler_dir.exists():
        print(f"⚠️ Filler directory not found: {filler_dir}")
        return None
    
    try:
        return FillerPlayer(str(filler_dir), audio_player, sink_name)
    except ValueError as e:
        print(f"⚠️ Failed to create filler player: {e}")
        return None

# Example usage and testing
if __name__ == "__main__":
    import sys
    import signal
    
    def signal_handler(sig, frame):
        print("\n🛑 Interrupted by user")
        if 'player' in locals() and player:
            player.stop_filler()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Test the filler player
    print("🧪 Testing FillerPlayer...")
    
    player = create_filler_player()
    if not player:
        print("❌ Failed to create filler player")
        sys.exit(1)
    
    print(f"✅ Created filler player with {len(player.filler_files)} files")
    
    # Test playing a few fillers
    for i in range(3):
        print(f"\n--- Test {i+1}/3 ---")
        success = player.start_filler()
        if success:
            # Wait for filler to complete or timeout
            start_time = time.time()
            while player.is_filler_playing() and (time.time() - start_time) < 10:
                time.sleep(0.1)
        else:
            print("❌ Failed to start filler")
        
        # Brief pause between tests
        time.sleep(1)
    
    print("\n🎉 Filler testing complete!")