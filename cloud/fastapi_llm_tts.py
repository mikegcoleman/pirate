# cloud/fastapi_llm_tts.py
"""
FastAPI endpoint that receives a user question, calls OpenAI LLM, then OpenAI TTS, and returns the audio (WAV) response.
- Requires OPENAI_API_KEY in environment.
- Returns audio/wav bytestream.
"""
import os
import openai
from fastapi import FastAPI, UploadFile, File, Form, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable not set.")
openai.api_key = OPENAI_API_KEY

app = FastAPI()

class LLMRequest(BaseModel):
    user_text: str
    system_prompt: str = ""
    model: str = "gpt-4o"
    tts_voice: str = "onyx"  # OpenAI TTS voices: alloy, echo, fable, onyx, nova, shimmer

async def get_llm_response(user_text, system_prompt, model):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})
    resp = await openai.ChatCompletion.acreate(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=512
    )
    return resp.choices[0].message.content.strip()

async def get_tts_audio(text, voice="onyx"):
    resp = await openai.audio.atranslate.create(
        model="tts-1",
        input=text,
        voice=voice,
        response_format="wav"
    )
    return resp.content

@app.post("/ask", response_class=StreamingResponse)
async def ask_llm_tts(req: LLMRequest):
    llm_text = await get_llm_response(req.user_text, req.system_prompt, req.model)
    audio_bytes = await get_tts_audio(llm_text, req.tts_voice)
    return StreamingResponse(
        iter([audio_bytes]),
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=output.wav"}
    )
