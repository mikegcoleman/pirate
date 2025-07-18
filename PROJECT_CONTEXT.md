# Pirate Voice Assistant - Project Context

## Project Overview
A voice-controlled pirate character ("Mr. Bones") that runs as a porch prop. The system captures audio, converts it to text, sends it to an LLM API, gets a response, converts it to speech, and plays it back.

## Architecture
```
Voice Input → STT (Vosk) → Frontend (main.py) → API (llm-api) → LLM → TTS → Audio Output
```

## File Structure
```
pirate/
├── stt/                    # Frontend (Speech-to-Text + Audio Playback)
│   ├── main.py            # Main conversation loop
│   ├── stt.py             # Speech-to-text module (Vosk)
│   ├── prompt.txt         # Mr. Bones character prompt
│   ├── env.example        # Environment template
│   ├── mac_env           # macOS configuration
│   ├── pi_env            # Raspberry Pi configuration
│   └── PLATFORM_CONFIG.md # Platform configuration guide
├── llm-api/               # Backend API
│   ├── app.py            # Flask API server
│   ├── requirements.txt  # Python dependencies (pinned versions)
│   ├── Dockerfile        # Container configuration (fixed port)
│   ├── compose.yaml      # Docker compose setup
│   ├── env.example       # Environment template
│   └── README.md         # Comprehensive documentation
└── PROJECT_CONTEXT.md    # This file
```

## Key Features Implemented

### 1. Conversation Timer (Issue #1)
- 2-3 minute conversation limit
- Graceful goodbye message
- Automatic reset for new sessions
- **Status**: Not yet implemented

### 2. STT Confidence Checking (Issue #2)
- Validates transcription quality
- Filters out noise and unclear speech
- Provides audio feedback for unclear input
- **Status**: ✅ Implemented

### 3. Enhanced Error Handling (Issue #3)
- Platform-specific error messages
- Graceful degradation (TTS fails → text only)
- Comprehensive validation
- **Status**: ✅ Implemented

### 4. Audio File Management (Issue #4)
- Temporary file usage
- Immediate cleanup
- Prevents disk space issues
- **Status**: ✅ Implemented

### 5. Environment Variable Validation
- Comprehensive startup validation
- Range checking for numeric values
- File and tool availability checks
- **Status**: ✅ Implemented

## Platform Support

### macOS (Development)
- **TTS**: System `say` command
- **Audio**: `afplay` (Core Audio)
- **Performance**: Optimized for higher performance
- **Config**: `mac_env`

### Raspberry Pi 4 (Production)
- **TTS**: `espeak` (more reliable on Linux)
- **Audio**: `aplay` (ALSA)
- **Performance**: Conservative settings for limited resources
- **Config**: `pi_env`

### Windows (API Development)
- **TTS**: System TTS or espeak
- **Audio**: `mpg123` or Windows Media Player
- **Performance**: Similar to macOS
- **Config**: Use `env.example` as template

## Environment Variables

### Required
```bash
API_URL=http://localhost:8080/api/chat
LLM_MODEL=llama3.1:8b-instruct-q4_K_M
```

### Audio Configuration
```bash
SPEECH_RATE=200          # 150 for Pi, 200 for Mac/Windows
AUDIO_PLAYER=afplay      # afplay (Mac), aplay (Pi), mpg123 (Windows)
```

### Performance Settings
```bash
TIMEOUT=90              # 60 for Pi, 90 for Mac/Windows
WAIT_INTERVAL=3         # 5 for Pi, 3 for Mac/Windows
```

### STT Configuration
```bash
VOSK_MODEL_PATH=models/vosk-model-small-en-us-0.15
SAMPLE_RATE=16000
MIC_DEVICE=default      # Platform-specific
BLOCKSIZE=8000          # 4000 for Pi, 8000 for Mac/Windows
```

## Recent Changes

### Platform Detection Removed
- Removed complex platform detection logic
- User provides all platform-specific values
- Better portability across platforms
- Simpler configuration management

### Voice Configuration Removed
- Voice selection moved to TTS API backend
- Frontend only handles speech rate and audio player
- Cleaner separation of concerns

### Error Handling Enhanced
- Frontend: Comprehensive environment validation
- Backend: Specific error types and graceful degradation
- Better debugging and user feedback

## Current Status

### Frontend (stt/)
- ✅ STT confidence checking
- ✅ Audio file management
- ✅ Environment validation
- ✅ Platform-agnostic configuration
- ❌ Conversation timer (pending)

### Backend (llm-api/)
- ✅ Enhanced error handling
- ✅ Request validation
- ✅ Response validation
- ✅ Startup validation
- ✅ TTS integration
- ✅ Health check endpoint
- ✅ Comprehensive documentation
- ✅ Environment template
- ✅ Pinned dependency versions
- ✅ Fixed Docker configuration

## Development Workflow

### For Windows API Development:
1. Copy `env.example` to `.env` in `llm-api/`
2. Configure `LLM_BASE_URL` to point to your LLM server
3. Set `PORT` if needed (default: 8080)
4. Install dependencies: `pip install -r requirements.txt`
5. Run `python app.py`
6. Test with: `curl http://localhost:8080/health`

### For Frontend Testing:
1. Copy `mac_env` to `stt/.env` for Mac development
2. Copy `pi_env` to `stt/.env` for Pi deployment
3. Configure `API_URL` to point to your API
4. Run `python main.py`

## LLM Recommendations

### For RTX 5070 (12GB VRAM):
- **Llama 3.1 8B** - Best overall performance
- **Mistral 7B v0.2** - Good alternative
- **Phi-3.5 3.8B** - Most efficient

### Quantization:
- Use `q4_K_M` quantization for 12GB VRAM
- Models fit comfortably with room for conversation history

## Character Prompt

Mr. Bones is a friendly pirate who:
- Speaks in pirate voice with "matey," "arr," "aye"
- Never breaks character
- Age-appropriate and safe for kids
- 50-75 word responses
- No emojis or abbreviations
- Talks about treasure, ships, islands, sea creatures

## Next Steps

### High Priority:
1. Implement conversation timer (2-3 minute limit)
2. Test on Windows environment
3. Deploy to Raspberry Pi

### Medium Priority:
1. Add response streaming for faster perceived performance
2. Implement conversation history management
3. Add reset conversation command

### Low Priority:
1. Add visual/audio cues for approaching time limit
2. Implement confidence-based retry logic
3. Add conversation analytics

## GitHub Issues
- #1: Implement conversation timer with graceful exit
- #2: Add STT confidence checking for prop reliability ✅
- #3: Improve error handling for unattended prop operation ✅
- #4: Optimize audio file management and cleanup ✅

## Notes for Windows Development
- Use `mpg123` or Windows Media Player for audio playback
- Consider using `espeak` for TTS feedback
- Test with different microphone devices
- Ensure Vosk model is properly installed
- Check firewall settings for API communication 