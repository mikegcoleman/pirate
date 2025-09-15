#!/usr/bin/env python3
"""
Speech-to-Text Module for Raspberry Pi Pirate Project
Captures audio from USB microphone and performs real-time STT using Vosk.

Environment Variables:
- MIC_DEVICE: PulseAudio source name (e.g., "alsa_input.usb-Antlion_Audio_Antlion_USB_Microphone-00.mono-fallback")
- SAMPLE_RATE: Audio sample rate (default: 16000 Hz)
- BLOCKSIZE: Audio buffer size in samples (default: 4000 ≈ 250ms @ 16kHz)

Tuning BLOCKSIZE for latency:
- 4000 samples @ 16kHz ≈ 250ms latency (good for Pi 4)
- 3200 samples @ 16kHz ≈ 200ms latency (try if CPU allows)
- 2400 samples @ 16kHz ≈ 150ms latency (for faster response)
"""

import os
import sys
import json
import queue
import time
import sounddevice as sd

try:
    import vosk
except ImportError:
    print("Error: vosk not installed. Install with: pip install vosk")
    sys.exit(1)

# Load environment variables
import dotenv
dotenv.load_dotenv()

# Disable Vosk logging for cleaner output
vosk.SetLogLevel(-1)

# Environment configuration
mic_device_str = os.getenv("MIC_DEVICE", "default")
# Convert to int if it's a number, otherwise keep as string
try:
    MIC_DEVICE = int(mic_device_str)
except ValueError:
    MIC_DEVICE = mic_device_str
    
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
BLOCKSIZE = int(os.getenv("BLOCKSIZE", "4000"))
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15")

# Global audio queue
audio_queue = queue.Queue()

def audio_callback(indata, frames, timestamp, status):
    """Audio input callback - queues raw audio data for processing."""
    if status:
        print(f"Audio callback status: {status}", file=sys.stderr)
    
    # Queue raw int16 audio data (frames and timestamp not used)
    audio_queue.put(bytes(indata))

def setup_audio():
    """Configure sounddevice with environment settings."""
    # Set device defaults - if MIC_DEVICE is empty, let sounddevice auto-detect
    if MIC_DEVICE:
        sd.default.device = (None, MIC_DEVICE)  # (output, input)
    sd.default.samplerate = SAMPLE_RATE
    sd.default.channels = 1  # Mono for STT
    sd.default.dtype = 'int16'  # 16-bit PCM
    
    print(f"Audio Configuration:")
    print(f"  Microphone: {MIC_DEVICE}")
    print(f"  Sample Rate: {SAMPLE_RATE} Hz")
    print(f"  Block Size: {BLOCKSIZE} samples ({BLOCKSIZE/SAMPLE_RATE*1000:.1f}ms)")
    print(f"  Channels: 1 (mono)")
    print(f"  Format: int16")

def load_vosk_model():
    """Load Vosk speech recognition model."""
    if not os.path.exists(VOSK_MODEL_PATH):
        print(f"Error: Vosk model not found at {VOSK_MODEL_PATH}")
        print("Download a model from https://alphacephei.com/vosk/models")
        sys.exit(1)
    
    print(f"Loading Vosk model from: {VOSK_MODEL_PATH}")
    model = vosk.Model(VOSK_MODEL_PATH)
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    print("Vosk model loaded successfully")
    
    return recognizer

def should_process_transcription(text, confidence=None):
    """Validate transcription quality before processing.
    
    Args:
        text (str): The transcribed text
        confidence (float, optional): Confidence score from STT
        
    Returns:
        bool: True if transcription should be processed, False otherwise
    """
    # Check for empty or whitespace-only text
    if not text or text.strip() == "":
        print("Empty transcription received")
        return False
    
    # Check for common non-speech sounds
    if text.strip().lower().strip('.,!?;:') == "huh":
        print("Heard only 'huh', ignoring")
        return False
    
    # Check confidence threshold if available (lowered for children's speech)
    if confidence is not None:
        CONFIDENCE_THRESHOLD = 0.3  # More lenient for children
        if confidence < CONFIDENCE_THRESHOLD:
            print(f"Low confidence transcription ({confidence:.2f}), ignoring")
            return False
    
    # Check for very short transcriptions (likely noise)
    if len(text.strip()) < 2:
        print("Very short transcription, likely noise")
        return False
    
    return True

def transcribe():
    """
    Perform real-time speech-to-text transcription.
    
    Returns:
        tuple: (final_text, confidence) or (None, None) if no speech detected
    """
    setup_audio()
    recognizer = load_vosk_model()
    
    # Clear any existing audio data
    while not audio_queue.empty():
        audio_queue.get()
    
    print("\n🎤 Listening for speech... (Press Ctrl+C to stop)")
    
    last_partial_time = 0
    partial_throttle_interval = 0.5  # Print partials every 500ms max
    
    try:
        with sd.RawInputStream(callback=audio_callback, 
                              blocksize=BLOCKSIZE,
                              dtype='int16',
                              channels=1,
                              samplerate=SAMPLE_RATE):
            
            while True:
                try:
                    # Get audio data from queue (blocking with timeout)
                    data = audio_queue.get(timeout=1.0)
                    
                    if recognizer.AcceptWaveform(data):
                        # Final recognition result
                        result = json.loads(recognizer.Result())
                        final_text = result.get('text', '').strip()
                        confidence = result.get('confidence', None)  # Vosk may not provide this
                        
                        if final_text and should_process_transcription(final_text, confidence):
                            print(f"\n✅ Final: {final_text}")
                            if confidence is not None:
                                print(f"   Confidence: {confidence:.2f}")
                            return final_text, confidence
                    
                    else:
                        # Partial recognition result (throttled output)
                        current_time = time.time()
                        if current_time - last_partial_time > partial_throttle_interval:
                            partial = json.loads(recognizer.PartialResult())
                            partial_text = partial.get('partial', '').strip()
                            
                            if partial_text:
                                print(f"🔄 Partial: {partial_text}", end='\r')
                                last_partial_time = current_time
                
                except queue.Empty:
                    # Timeout - check if we should continue
                    continue
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Transcription stopped by user")
                    return None, None
                    
    except Exception as e:
        print(f"\n❌ Error during transcription: {e}")
        return None, None

def main():
    """Main function for standalone testing."""
    print("=== Raspberry Pi Speech-to-Text Test ===")
    print("\nTo optimize audio settings, use these PulseAudio commands:")
    print('pactl set-default-source "alsa_input.usb-Antlion_Audio_Antlion_USB_Microphone-00.mono-fallback"')
    print('pactl set-default-sink "bluez_output.24_F4_95_F4_CA_45.1"')
    print("\nTune BLOCKSIZE in .env for latency:")
    print("- 4000 samples ≈ 250ms (current)")
    print("- 3200 samples ≈ 200ms (try if CPU allows)")
    print("- 2400 samples ≈ 150ms (for faster response)")
    
    while True:
        try:
            result = transcribe()
            
            if result[0] is not None:
                final_text, confidence = result
                print(f"\nTranscribed: '{final_text}'")
                if confidence is not None:
                    print(f"Confidence: {confidence:.2f}")
            else:
                print("No speech detected or transcription cancelled")
            
            # Ask if user wants to continue
            try:
                continue_choice = input("\nTry again? (y/n): ").strip().lower()
                if continue_choice not in ['y', 'yes', '']:
                    break
            except KeyboardInterrupt:
                break
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()