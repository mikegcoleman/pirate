# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
A voice-controlled pirate character ("Mr. Bones") porch prop system with speech-to-text, LLM processing, and text-to-speech output. Two-component architecture: frontend (stt/) for audio handling and backend (llm-api/) for processing.

## Development Commands

### Frontend (stt/)
```bash
# Install dependencies
pip install -r stt/requirements.txt

# Run the main application
cd stt && python main.py

# Test STT functionality
cd stt && python test_exact.py

# Test HTTP API integration  
cd stt && python test_http.py

# List available audio devices
cd stt && python list_audio_devices.py
```

### Backend (llm-api/)
```bash
# Install dependencies
pip install -r llm-api/requirements.txt

# Run the Flask API server
cd llm-api && python app.py

# Test health endpoint
curl http://localhost:8080/health

# Run with Docker
cd llm-api && docker-compose up
```

## Architecture

### Two-Component System
- **Frontend (stt/)**: Handles audio capture, speech-to-text (Vosk), and audio playback
- **Backend (llm-api/)**: Flask API server with LLM integration and TTS (Kokoro)
- **Data Flow**: Audio → STT → HTTP API → LLM → TTS → Audio Output

### Key Components
- `stt/main.py`: Main conversation loop with environment validation and streaming audio support
- `stt/stt.py`: Vosk-based speech-to-text with confidence checking
- `llm-api/app.py`: Flask API with Kokoro TTS integration and streaming responses
- Environment files: `mac_env`, `pi_env`, `env.example` for platform-specific configs

### Streaming Implementation
- `/api/chat/stream`: New Server-Sent Events endpoint for streaming responses
- Sentence-level TTS processing: Generates audio for complete sentences as LLM streams tokens
- Real-time audio playback: Plays first sentence while subsequent sentences are still generating
- Automatic fallback to `/api/chat` for non-streaming compatibility

### Platform Support
- **macOS Development**: Uses `say` and `afplay`, higher performance settings
- **Raspberry Pi Production**: Uses `espeak` and `aplay`, conservative resource settings  
- **Windows API Server**: High-performance backend with RTX GPU support

## Configuration

### Required Environment Variables
```bash
API_URL=http://localhost:8080/api/chat
LLM_MODEL=llama3.2:8b-instruct-q4_K_M
LLM_BASE_URL=http://model-runner.docker.internal/engines/v1
```

### Platform-Specific Settings
- Copy `mac_env` → `.env` for macOS development
- Copy `pi_env` → `.env` for Raspberry Pi deployment
- Use `env.example` as template for Windows

### Audio Configuration
- `SPEECH_RATE`: 150 (Pi) / 200 (Mac/Windows)  
- `AUDIO_PLAYER`: aplay (Pi) / afplay (Mac) / mpg123 (Windows)
- `BLOCKSIZE`: 4000 (Pi) / 8000 (Mac/Windows)

## Key Features
- **STT Confidence Checking**: Filters unclear speech with audio feedback
- **Environment Validation**: Comprehensive startup checks for all required configs
- **Temporary Audio Files**: Automatic cleanup prevents disk space issues
- **Platform-Agnostic Design**: User-provided platform-specific configurations
- **Graceful Error Handling**: Text-only fallback when TTS fails

## Character Implementation
Mr. Bones character prompt in `stt/prompt.txt` - friendly pirate with 50-75 word responses, age-appropriate content, uses pirate vocabulary without breaking character.

## Known Issues
- Conversation timer feature (#1) not yet implemented
- Voice character needs improvement (considering RVC/Coqui for authentic pirate voice)

## Testing
- Use `test_exact.py` for STT accuracy testing
- Use `test_http.py` for API integration testing
- Health check endpoint at `/health` for backend status