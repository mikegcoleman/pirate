#!/usr/bin/env python3
"""
Combined Pirate Voice Assistant Application
Integrates STT (Vosk), LLM inference (OpenAI), and TTS (ElevenLabs) into a single application.

Flow: Microphone -> Vosk STT -> OpenAI GPT -> ElevenLabs TTS -> Audio playback
"""

import os
import sys
import json
import queue
import tempfile
import base64
import asyncio
import subprocess
import platform
from dotenv import load_dotenv

# Audio and STT imports
import sounddevice as sd
import vosk

# LLM API imports
import openai

# TTS imports
from elevenlabs.client import ElevenLabs

# Load environment variables
load_dotenv()

# Disable Vosk logging
vosk.SetLogLevel(-1)

class CombinedPirateAssistant:
    def __init__(self):
        """Initialize the combined pirate assistant"""
        self.validate_environment()
        self.setup_stt()
        self.setup_llm()
        self.setup_tts()
        self.setup_audio_queue()
        self.load_pirate_prompt()
        
        # Conversation history
        self.messages = [{"role": "system", "content": self.pirate_prompt}]
        
        print("🏴‍☠️ Mr. Bones, the Combined Pirate Assistant is ready!")
        print(f"🎤 Using Vosk model: {self.vosk_model_path}")
        print(f"🤖 Using OpenAI model: {self.openai_model}")
        print(f"🔊 Using ElevenLabs voice: {self.elevenlabs_voice_id}")
    
    def validate_environment(self):
        """Validate all required environment variables"""
        errors = []
        
        # OpenAI configuration
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            errors.append("Missing OPENAI_API_KEY")
        
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4")
        
        # ElevenLabs configuration
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.elevenlabs_api_key:
            errors.append("Missing ELEVENLABS_API_KEY")
        
        self.elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        if not self.elevenlabs_voice_id:
            errors.append("Missing ELEVENLABS_VOICE_ID")
        
        # Vosk model path
        self.vosk_model_path = os.path.abspath(os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15"))
        if not os.path.exists(self.vosk_model_path):
            errors.append(f"Vosk model not found: {self.vosk_model_path}")
        
        # Audio configuration
        self.sample_rate = int(os.getenv("SAMPLE_RATE", "16000"))
        self.mic_device = os.getenv("MIC_DEVICE", "default")
        self.blocksize = int(os.getenv("BLOCKSIZE", "8000"))
        self.audio_player = os.getenv("AUDIO_PLAYER", "afplay")
        
        # Prompt file
        self.prompt_file = os.getenv("PROMPT_FILE", "prompt.txt")
        
        if errors:
            print("❌ Environment validation failed:")
            for error in errors:
                print(f"  • {error}")
            sys.exit(1)
        
        print("✅ Environment validation passed")
    
    def setup_stt(self):
        """Initialize Vosk speech-to-text"""
        try:
            self.vosk_model = vosk.Model(self.vosk_model_path)
            self.vosk_recognizer = vosk.KaldiRecognizer(self.vosk_model, self.sample_rate)
            print("✅ Vosk STT initialized")
        except Exception as e:
            print(f"❌ Failed to initialize Vosk STT: {e}")
            sys.exit(1)
    
    def setup_llm(self):
        """Initialize OpenAI client"""
        try:
            self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
            print("✅ OpenAI client initialized")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI client: {e}")
            sys.exit(1)
    
    def setup_tts(self):
        """Initialize ElevenLabs TTS"""
        try:
            self.elevenlabs_client = ElevenLabs(api_key=self.elevenlabs_api_key)
            print("✅ ElevenLabs TTS initialized")
        except Exception as e:
            print(f"❌ Failed to initialize ElevenLabs TTS: {e}")
            sys.exit(1)
    
    def setup_audio_queue(self):
        """Initialize audio queue for STT"""
        self.audio_queue = queue.Queue()
    
    def load_pirate_prompt(self):
        """Load the pirate character prompt"""
        if os.path.exists(self.prompt_file):
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                self.pirate_prompt = f.read().strip()
        else:
            # Default pirate prompt if file doesn't exist
            self.pirate_prompt = """You are Mr. Bones, a friendly pirate voice assistant. 
            Respond to all queries in character as a pirate, using pirate speech patterns and vocabulary. 
            Keep responses conversational and engaging, but helpful. 
            Always stay in character as a pirate."""
        
        print("✅ Pirate prompt loaded")
    
    def audio_callback(self, indata, frames, time, status):
        """Audio input callback for sounddevice"""
        if status:
            print(f"Audio callback status: {status}")
        self.audio_queue.put(bytes(indata))
    
    def should_process_transcription(self, text, confidence=None):
        """Validate transcription quality"""
        if not text or text.strip() == "":
            return False
        
        # Filter out common non-speech sounds
        if text.strip().lower().strip('.,!?;:') == "huh":
            return False
        
        # Check for very short transcriptions (likely noise)
        if len(text.strip()) < 2:
            return False
        
        return True
    
    def transcribe_audio(self):
        """Transcribe audio from microphone using Vosk"""
        print("🎤 Listening for speech...")
        
        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype='int16',
            channels=1,
            callback=self.audio_callback,
            device=self.mic_device
        ):
            while True:
                try:
                    data = self.audio_queue.get(timeout=5)
                    if self.vosk_recognizer.AcceptWaveform(data):
                        result = self.vosk_recognizer.Result()
                        result_dict = json.loads(result)
                        text = result_dict.get("text", "")
                        
                        if text and self.should_process_transcription(text):
                            print(f"🎤 Transcribed: '{text}'")
                            return text
                except queue.Empty:
                    continue
                except KeyboardInterrupt:
                    print("\n👋 Goodbye, matey!")
                    sys.exit(0)
    
    async def get_llm_response(self, user_input):
        """Get response from OpenAI GPT"""
        try:
            print(f"🤖 Sending to OpenAI: '{user_input[:50]}...'")
            
            # Add user message to conversation
            self.messages.append({"role": "user", "content": user_input})
            
            # Get response from OpenAI
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=self.messages,
                max_tokens=150,
                temperature=0.7
            )
            
            assistant_response = response.choices[0].message.content.strip()
            
            # Add assistant response to conversation
            self.messages.append({"role": "assistant", "content": assistant_response})
            
            # Keep conversation history manageable (last 10 messages)
            if len(self.messages) > 11:  # system + 10 messages
                self.messages = [self.messages[0]] + self.messages[-10:]
            
            print(f"🤖 OpenAI response: '{assistant_response[:50]}...'")
            return assistant_response
            
        except Exception as e:
            print(f"❌ OpenAI API error: {e}")
            return "Arr, I be havin' trouble with me thoughts right now, matey!"
    
    def generate_tts_audio(self, text):
        """Generate audio using ElevenLabs TTS"""
        try:
            print(f"🔊 Generating TTS for: '{text[:50]}...'")
            
            # Generate audio using ElevenLabs
            audio_generator = self.elevenlabs_client.text_to_speech.convert(
                voice_id=self.elevenlabs_voice_id,
                text=text,
                model_id="eleven_monolingual_v1"
            )
            
            # Convert generator to bytes
            audio_bytes = b""
            for chunk in audio_generator:
                audio_bytes += chunk
            
            print("✅ TTS audio generated successfully")
            return audio_bytes
            
        except Exception as e:
            print(f"❌ ElevenLabs TTS error: {e}")
            return None
    
    def play_audio(self, audio_data):
        """Play audio data using system audio player"""
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file.flush()
                
                print(f"🔊 Playing audio...")
                
                # Play audio using system player
                if platform.system() == "Darwin":  # macOS
                    subprocess.run([self.audio_player, tmp_file.name], check=True)
                elif platform.system() == "Linux":
                    subprocess.run(["aplay", tmp_file.name], check=True)
                else:  # Windows
                    subprocess.run(["powershell", "-c", f"(New-Object Media.SoundPlayer '{tmp_file.name}').PlaySync()"], check=True)
                
                # Clean up temporary file
                os.unlink(tmp_file.name)
                
        except Exception as e:
            print(f"❌ Audio playback error: {e}")
    
    async def run_conversation_loop(self):
        """Main conversation loop"""
        print("\n🏴‍☠️ Mr. Bones is ready to chat! Press Ctrl+C to quit.")
        
        while True:
            try:
                # Step 1: Listen for speech input
                user_input = self.transcribe_audio()
                if not user_input:
                    continue
                
                # Step 2: Get LLM response
                response_text = await self.get_llm_response(user_input)
                
                # Step 3: Generate TTS audio
                audio_data = self.generate_tts_audio(response_text)
                
                # Step 4: Play audio response
                if audio_data:
                    self.play_audio(audio_data)
                else:
                    print(f"🗣️ Text response: {response_text}")
                
                print("\n" + "="*50 + "\n")
                
            except KeyboardInterrupt:
                print("\n👋 Farewell, matey! Until we meet again!")
                break
            except Exception as e:
                print(f"❌ Unexpected error in conversation loop: {e}")
                continue

def main():
    """Main entry point"""
    try:
        assistant = CombinedPirateAssistant()
        asyncio.run(assistant.run_conversation_loop())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()