# Pirate Voice Assistant - Mr. Bones

A voice-controlled pirate character that runs as a porch prop, capturing audio, processing it with AI, and responding with authentic pirate character voice.

## 🏴‍☠️ Overview

Mr. Bones is a friendly pirate voice assistant designed for interactive entertainment. The system uses speech-to-text to capture user input, sends it to a local LLM for character-appropriate responses, and uses text-to-speech to deliver authentic pirate audio responses.

### Architecture

```
Voice Input → STT (Vosk) → Frontend → API → LLM → TTS → Audio Output
```

## 🚀 Quick Start

### Prerequisites

- **Development**: macOS or Windows with Python 3.8+
- **Production**: Raspberry Pi 4 + Windows server for LLM processing
- **LLM Server**: Local server with 12GB+ VRAM (e.g., RTX 5070)

### 1. Backend Setup (LLM API)

```bash
cd llm-api/
cp env.example .env
# Configure your LLM endpoint in .env
pip install -r requirements.txt
python app.py
```

### 2. Frontend Setup (Voice Interface)

```bash
cd stt/
# Copy platform-specific config
cp mac_env .env    # For macOS development
# OR
cp pi_env .env     # For Raspberry Pi production

# Install dependencies
pip install -r requirements.txt

# List available audio devices
python list_audio_devices.py

# Update .env with your microphone device
# Run the voice assistant
python main.py
```

## 📁 Project Structure

```
pirate/
├── README.md              # This file
├── CLAUDE.md             # Detailed project context and configuration
├── stt/                  # Frontend (Speech-to-Text + Audio)
│   ├── main.py          # Main conversation loop
│   ├── stt.py           # Speech-to-text processing
│   ├── mac_env          # macOS configuration
│   ├── pi_env           # Raspberry Pi configuration
│   └── README.md        # Frontend documentation
├── llm-api/             # Backend API Server
│   ├── app.py           # Flask API with TTS integration
│   ├── requirements.txt # Python dependencies
│   ├── Dockerfile       # Container configuration
│   └── README.md        # API documentation
└── combined/            # Cloud Testing Version
    ├── main.py          # All-in-one cloud-dependent version
    └── README.md        # Testing documentation
```

## 🎯 Features

### ✅ Implemented
- **STT Confidence Checking**: Filters out unclear speech and background noise
- **Enhanced Error Handling**: Graceful degradation and comprehensive validation
- **Audio File Management**: Efficient temporary file usage and cleanup
- **Environment Validation**: Startup checks for all dependencies and configuration
- **Kokoro TTS Integration**: High-quality character voice synthesis
- **Platform Support**: macOS (development) and Raspberry Pi (production)

### 🚧 In Development
- **Conversation Timer**: 2-3 minute conversation limits with graceful exit

## 🎮 Character

**Mr. Bones** is a friendly pirate who:
- Speaks with authentic pirate language ("matey," "arr," "aye")
- Never breaks character
- Provides age-appropriate, family-safe responses
- Keeps responses concise (50-75 words)
- Talks about treasure, ships, islands, and sea creatures

## 🔧 Configuration

### Platform-Specific Settings

| Setting | macOS (Dev) | Raspberry Pi (Prod) |
|---------|-------------|-------------------|
| Speech Rate | 200 | 150 |
| Audio Player | afplay | aplay |
| Timeout | 90s | 60s |
| Block Size | 8000 | 4000 |

### LLM Recommendations

For RTX 5070 (12GB VRAM):
- **Llama 3.2 8B** (q4_K_M quantization) - Current choice
- **Llama 3.3 8B** (q4_K_M quantization) - Best character consistency
- **Mistral 7B v0.2** - Good alternative
- **Phi-3.5 3.8B** - Most efficient

## 🚀 Deployment

### Development (macOS/Windows)
- Use `stt/mac_env` configuration
- Run both frontend and backend locally
- Higher performance settings for responsive testing

### Production (Raspberry Pi + Server)
- **Pi**: Frontend only (`stt/pi_env`)
- **Server**: Backend API (`llm-api/`)
- Conservative settings for Pi's limited resources

### Quick Hardware Testing
- Use `combined/main.py` for cloud-dependent testing
- Bypasses local API setup for rapid validation

## 📚 Documentation

- **[CLAUDE.md](CLAUDE.md)**: Comprehensive project context and configuration guide
- **[stt/README.md](stt/README.md)**: Frontend setup and usage
- **[llm-api/README.md](llm-api/README.md)**: API server configuration and deployment
- **[combined/README.md](combined/README.md)**: Cloud testing version

## 🐛 Issues & Development

Current GitHub issues:
- **#1**: Implement conversation timer with graceful exit
- **#2**: ✅ Add STT confidence checking
- **#3**: ✅ Improve error handling  
- **#4**: ✅ Optimize audio file management

## 📄 License

This project is for educational and entertainment purposes. Ensure compliance with your local LLM and TTS service terms of use.