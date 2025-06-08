import os
import queue
import sounddevice as sd
import vosk
import dotenv

"""Speech-to-text module for Mr. Bones, the pirate voice assistant.
Handles audio input, Vosk model loading, and transcription.
"""
dotenv.load_dotenv()
MODEL_PATH = os.path.abspath(os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15"))

print(f"Using Vosk model at: {MODEL_PATH}")

SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", 16000))
DEVICE = os.getenv("MIC_DEVICE", "default")

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

def transcribe():
    """Transcribe audio from the microphone using the Vosk model.
    Returns:
        str: The recognized text from speech.
    Raises:
        FileNotFoundError: If the Vosk model path does not exist.
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found at: {MODEL_PATH}")
    model = vosk.Model(MODEL_PATH)
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)

    print("🎤 Listening... Press Ctrl+C to stop.")

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                           channels=1, callback=callback, device=DEVICE):
        while True:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                result = recognizer.Result()
                text = eval(result).get("text", "")
                if text:
                    return text