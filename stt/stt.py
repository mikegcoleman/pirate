import os
import queue
import sounddevice as sd
import vosk
import dotenv
import json
import platform

"""Speech-to-text module for Mr. Bones, the pirate voice assistant.
Handles audio input, Vosk model loading, and transcription.
"""
dotenv.load_dotenv()
MODEL_PATH = os.path.abspath(os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15"))

print(f"Using Vosk model at: {MODEL_PATH}")

# Audio Configuration
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
DEVICE = os.getenv("MIC_DEVICE", "default")
BLOCKSIZE = int(os.getenv("BLOCKSIZE", "8000"))

q = queue.Queue()

def callback(indata, frames, time, status):
    """Callback function for sounddevice audio input.
    Args:
        indata: Audio input data.
        frames: Number of frames.
        time: Time information.
        status: Callback status.
    """
    if status:
        print("Audio callback status:", status)
    q.put(bytes(indata))

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
    
    # Check confidence threshold if available
    if confidence is not None:
        CONFIDENCE_THRESHOLD = 0.7
        if confidence < CONFIDENCE_THRESHOLD:
            print(f"Low confidence transcription ({confidence:.2f}), ignoring")
            return False
    
    # Check for very short transcriptions (likely noise)
    if len(text.strip()) < 2:
        print("Very short transcription, likely noise")
        return False
    
    return True

def transcribe():
    """Transcribe audio from the microphone using the Vosk model.
    Returns:
        tuple: (text, confidence) where text is the recognized speech and confidence is the confidence score.
               Returns (None, None) if no valid transcription is found.
    Raises:
        FileNotFoundError: If the Vosk model path does not exist.
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found at: {MODEL_PATH}")
    model = vosk.Model(MODEL_PATH)
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)

    print("Listening... Press Ctrl+C to stop.")

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCKSIZE, dtype='int16',
                           channels=1, callback=callback, device=DEVICE):
        while True:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                result = recognizer.Result()
                result_dict = json.loads(result)
                
                text = result_dict.get("text", "")
                # Vosk doesn't provide confidence scores in the standard output
                # We'll use None for confidence and rely on other validation methods
                confidence = None
                
                if text:
                    # Validate the transcription
                    if should_process_transcription(text, confidence):
                        return text, confidence
                    else:
                        # Continue listening for better input
                        continue