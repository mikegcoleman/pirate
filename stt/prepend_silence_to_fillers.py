#!/usr/bin/env python3
"""
Prepend silence to filler files to prewarm Bluetooth speakers.
Takes original files from ./audio/fillers/original and creates new versions 
with prepended silence in ./audio/fillers.

Usage:
    python prepend_silence_to_fillers.py 500    # 500ms silence
    python prepend_silence_to_fillers.py 750    # 750ms silence
    python prepend_silence_to_fillers.py 0      # No silence (copy originals)
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def prepend_silence_to_mp3(input_file: Path, output_file: Path, silence_ms: int):
    """
    Prepend silence to an MP3 file using ffmpeg.
    
    Args:
        input_file: Path to the input MP3 file
        output_file: Path to the output MP3 file with prepended silence
        silence_ms: Duration of silence in milliseconds
    """
    if silence_ms <= 0:
        # Just copy the file if no silence requested
        try:
            subprocess.run(['cp', str(input_file), str(output_file)], check=True)
            return True
        except Exception as e:
            print(f"❌ Error copying {input_file.name}: {e}")
            return False
    
    try:
        silence_duration = silence_ms / 1000.0  # Convert to seconds
        
        # Use ffmpeg to prepend silence
        # anullsrc generates silence, then we concatenate it with the original audio
        cmd = [
            'ffmpeg',
            '-f', 'lavfi', '-i', f'anullsrc=channel_layout=mono:sample_rate=44100:duration={silence_duration}',
            '-i', str(input_file),
            '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[out]',
            '-map', '[out]',
            '-codec:a', 'libmp3lame',
            '-b:a', '128k',
            '-y',  # Overwrite output file if it exists
            str(output_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            print(f"❌ Error processing {input_file.name}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Exception processing {input_file.name}: {e}")
        return False

def setup_directories():
    """Set up the directory structure and move original files if needed."""
    fillers_dir = Path("audio/fillers")
    original_dir = Path("audio/fillers/original")
    
    # Create directories if they don't exist
    fillers_dir.mkdir(parents=True, exist_ok=True)
    original_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if we need to move files to original directory
    filler_files_in_main = list(fillers_dir.glob("filler_*.mp3"))
    filler_files_in_original = list(original_dir.glob("filler_*.mp3"))
    
    if filler_files_in_main and not filler_files_in_original:
        print("📁 Moving existing filler files to original directory...")
        for filler_file in filler_files_in_main:
            destination = original_dir / filler_file.name
            subprocess.run(['mv', str(filler_file), str(destination)], check=True)
            print(f"📂 Moved: {filler_file.name} → original/")
    
    return original_dir, fillers_dir

def main():
    """Process all filler files to add specified silence at the beginning."""
    if len(sys.argv) != 2:
        print("Usage: python prepend_silence_to_fillers.py <silence_ms>")
        print("Examples:")
        print("  python prepend_silence_to_fillers.py 500   # 500ms silence")
        print("  python prepend_silence_to_fillers.py 750   # 750ms silence")
        print("  python prepend_silence_to_fillers.py 0     # No silence")
        return False
    
    try:
        silence_ms = int(sys.argv[1])
        if silence_ms < 0:
            print("❌ Silence duration must be non-negative")
            return False
    except ValueError:
        print("❌ Silence duration must be a valid integer (milliseconds)")
        return False
    
    print(f"🔇 Processing filler files with {silence_ms}ms of prepended silence...")
    
    # Set up directories
    original_dir, fillers_dir = setup_directories()
    
    # Get all original filler MP3 files
    original_files = list(original_dir.glob("filler_*.mp3"))
    if not original_files:
        print(f"❌ No original filler files found in: {original_dir}")
        print("💡 Make sure you have filler_*.mp3 files in the original directory")
        return False
    
    print(f"📁 Found {len(original_files)} original filler files")
    if silence_ms > 0:
        print(f"🔇 Adding {silence_ms}ms ({silence_ms/1000:.1f}s) of silence to each file...")
    else:
        print("📋 Copying original files without silence...")
    
    successful = 0
    failed = 0
    
    for original_file in sorted(original_files):
        output_file = fillers_dir / original_file.name
        
        print(f"🎵 Processing: {original_file.name}")
        
        if prepend_silence_to_mp3(original_file, output_file, silence_ms):
            successful += 1
            print(f"✅ Created: {output_file.name}")
        else:
            failed += 1
    
    print(f"\n🎉 Processing complete!")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    if successful > 0:
        print(f"\n📊 Results:")
        print(f"• Original files preserved in: {original_dir}")
        print(f"• Modified files created in: {fillers_dir}")
        
        if silence_ms > 0:
            print(f"• All filler files now have {silence_ms}ms of silence prepended")
            print(f"• This should prevent Bluetooth speaker cutoff issues")
        else:
            print(f"• Files copied without modification")
        
        # Check duration of first file to verify
        if original_files:
            test_file = fillers_dir / original_files[0].name
            try:
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', 
                    '-of', 'csv=p=0', str(test_file)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    duration = float(result.stdout.strip())
                    print(f"📏 Sample duration: {duration:.2f}s ({test_file.name})")
            except:
                pass
        
        print(f"\n💡 To try different silence duration, run:")
        print(f"   python prepend_silence_to_fillers.py <new_milliseconds>")
    
    return successful > 0

if __name__ == "__main__":
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ffmpeg is required but not found")
        print("💡 Install with: sudo apt install ffmpeg")
        sys.exit(1)
    
    success = main()
    sys.exit(0 if success else 1)