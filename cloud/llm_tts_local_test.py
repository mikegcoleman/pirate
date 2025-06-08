import os
import openai
import httpx
import asyncio

def get_env(var, default=None):
    val = os.getenv(var)
    if val is None:
        if default is not None:
            return default
        raise RuntimeError(f"Environment variable {var} not set.")
    return val

OPENAI_API_KEY = get_env("OPENAI_API_KEY","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")
OPENAI_MODEL = get_env("OPENAI_MODEL", "gpt-4o")
# Valid OpenAI TTS voices: alloy, echo, fable, onyx, nova, shimmer
OPENAI_TTS_VOICE = get_env("OPENAI_TTS_VOICE", "ballad")
SYSTEM_PROMPT = get_env("SYSTEM_PROMPT", "You are Mr. Bones, a friendly pirate. Do not use emojis or asterisks. Use only letters, numbers, and regular punctuation. Please answer questions concisely - never more than 100 words. You are speaking to children, so keep answers appropriate and fun. Always use a pirate tone and style. If you don't know the answer, say 'I don't know'.")

async def get_llm_response(user_text, system_prompt, model, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

async def get_tts_audio(text, voice, api_key):
    url = "https://api.openai.com/v1/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "audio/wav"}
    # Use tts-1-hd for ballad, tts-1 for others
    model = "tts-1-hd" if voice == "ballad" else "tts-1"
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "wav"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.content

def save_audio(audio_bytes, filename="output.wav"):
    with open(filename, "wb") as f:
        f.write(audio_bytes)
    print(f"Audio saved to {filename}")

def play_audio(filename):
    # macOS: afplay, Linux: aplay
    if os.name == "posix":
        import subprocess
        if sys.platform == "darwin":
            subprocess.run(["afplay", filename])
        else:
            subprocess.run(["aplay", filename])
    else:
        print(f"Please play {filename} manually.")

async def main():
    user_text = input("You: ")
    print("Calling LLM...")
    llm_text = await get_llm_response(user_text, SYSTEM_PROMPT, OPENAI_MODEL, OPENAI_API_KEY)
    print(f"LLM: {llm_text}")
    print("Calling TTS...")
    audio_bytes = await get_tts_audio(llm_text, OPENAI_TTS_VOICE, OPENAI_API_KEY)
    save_audio(audio_bytes, "output.wav")
    play_audio("output.wav")

if __name__ == "__main__":
    import sys
    asyncio.run(main())
