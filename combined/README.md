# Combined Pirate Voice Assistant

A unified voice assistant that combines speech-to-text (Vosk), language model inference (OpenAI), and text-to-speech (ElevenLabs) into a single application.

## Features

- **Speech-to-Text**: Uses Vosk for local speech recognition
- **Language Model**: OpenAI GPT for intelligent responses  
- **Text-to-Speech**: ElevenLabs for high-quality voice synthesis
- **Character**: Mr. Bones, a friendly pirate assistant

## Flow

1. **Listen**: Captures audio from microphone
2. **Transcribe**: Converts speech to text using Vosk
3. **Process**: Sends text to OpenAI GPT for response
4. **Synthesize**: Converts response to speech using ElevenLabs
5. **Play**: Outputs audio through system speakers

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Download Vosk Model**:
   ```bash
   # The Vosk model should be in: ../stt/models/vosk-model-small-en-us-0.15
   # If not present, download from: https://alphacephei.com/vosk/models
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the Application**:
   ```bash
   python main.py
   ```

## Configuration

Edit `.env` file with your credentials:

- `OPENAI_API_KEY`: Your OpenAI API key
- `ELEVENLABS_API_KEY`: Your ElevenLabs API key  
- `ELEVENLABS_VOICE_ID`: ElevenLabs voice ID to use
- `VOSK_MODEL_PATH`: Path to Vosk model directory

## Usage

1. Run `python main.py`
2. Wait for "Listening for speech..." message
3. Speak your question or command
4. Listen to Mr. Bones' pirate response!
5. Press Ctrl+C to quit

## Requirements

- Python 3.8+
- Microphone for speech input
- Speakers for audio output
- OpenAI API key
- ElevenLabs API key
- Internet connection for API calls