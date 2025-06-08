import stt
import subprocess
import os
import asyncio
import httpx

API_URL = os.getenv("API_URL", "http://localhost:8080/api/chat")
VOICE = os.getenv("VOICE", "Samantha")
SPEECH_RATE = os.getenv("SPEECH_RATE", "200")

def speak_text(text):
    subprocess.run(["say", "-v", VOICE, "-r", SPEECH_RATE, text])


async def send_request(text):
    async with httpx.AsyncClient() as client:
        return await client.post(API_URL, json={"message": text}, timeout=90)

async def main():
    text = stt.transcribe()
    print("Mr. Bones is thinking...")
    speak_text("Mr. Bones is thinking")

    request_task = asyncio.create_task(send_request(text))
    while not request_task.done():
        print("Still waiting...")
        await asyncio.sleep(0.25)  # Check every 0.25 seconds

    try:
        response = await request_task
        response.raise_for_status()
        print("Transcribed text:", text)
        print("Response:", response.json()["response"])
        speak_text(response.json()["response"])
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    asyncio.run(main())