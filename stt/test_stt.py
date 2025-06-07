import stt
import requests
import subprocess

def speak_text(text):
    subprocess.run(["say", "-v", "Whisper", text])


API_URL = "http://192.168.86.38:8080/api/chat"

if __name__ == "__main__":
    text = stt.transcribe()
    
    try:
        response = requests.post(API_URL, json={"message": text}, timeout=90)
        response.raise_for_status()
        print("Transcribed text:", text)
        print("Response:", response.json()["response"])
        speak_text(response.json()["response"])
        
    except Exception as e:
        print("Error:", str(e))
    
