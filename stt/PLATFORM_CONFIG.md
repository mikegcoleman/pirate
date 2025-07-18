# Platform Configuration Guide

This system automatically detects your platform and adjusts settings for optimal performance.

## Environment Variables

Create a `.env` file in the `stt/` directory with these variables:

### Platform Configuration
```bash
# Auto-detected, but can be overridden
PLATFORM=linux  # for Raspberry Pi
PLATFORM=darwin # for macOS
PLATFORM=windows # for Windows
```

### API Configuration
```bash
API_URL=http://localhost:8080/api/chat
LLM_MODEL=llama3.1:8b-instruct-q4_K_M
```

### Audio Configuration
```bash
# Voice options
VOICE=espeak     # for Raspberry Pi (more reliable)
VOICE=Samantha   # for macOS
VOICE=          # leave empty for auto-detection

# Speech rate
SPEECH_RATE=150  # for Pi (slower, better performance)
SPEECH_RATE=200  # for Mac (faster)

# Audio player
AUDIO_PLAYER=aplay   # for Pi (ALSA)
AUDIO_PLAYER=afplay  # for macOS
AUDIO_PLAYER=       # leave empty for auto-detection
```

### Performance Settings
```bash
# Timeout for API requests
TIMEOUT=60   # for Pi (shorter)
TIMEOUT=90   # for Mac (longer)

# Wait interval for thinking phrases
WAIT_INTERVAL=5  # for Pi (longer intervals)
WAIT_INTERVAL=3  # for Mac (shorter intervals)
```

### STT Configuration
```bash
VOSK_MODEL_PATH=models/vosk-model-small-en-us-0.15
SAMPLE_RATE=16000
MIC_DEVICE=RØDE VideoMic NTG
```

### Prompt Configuration
```bash
PROMPT_FILE=prompt.txt
```

## Platform-Specific Optimizations

### Raspberry Pi 4
- **TTS**: Uses `espeak` (more reliable than `say`)
- **Audio**: Uses `aplay` (ALSA audio system)
- **Performance**: Slower speech rate (150) and longer timeouts
- **Memory**: Optimized for limited RAM

### macOS
- **TTS**: Uses `say` command with system voices
- **Audio**: Uses `afplay` (Core Audio)
- **Performance**: Faster speech rate (200) and shorter timeouts
- **Memory**: Optimized for higher performance

## Auto-Detection

If you don't set platform-specific variables, the system will:
1. Auto-detect your platform
2. Use appropriate defaults
3. Display detected settings on startup

## Example .env for Pi4
```bash
PLATFORM=linux
API_URL=http://localhost:8080/api/chat
LLM_MODEL=llama3.1:8b-instruct-q4_K_M
VOICE=espeak
SPEECH_RATE=150
AUDIO_PLAYER=aplay
TIMEOUT=60
WAIT_INTERVAL=5
VOSK_MODEL_PATH=models/vosk-model-small-en-us-0.15
SAMPLE_RATE=16000
MIC_DEVICE=default
PROMPT_FILE=prompt.txt
```

## Example .env for macOS
```bash
PLATFORM=darwin
API_URL=http://localhost:8080/api/chat
LLM_MODEL=llama3.1:8b-instruct-q4_K_M
VOICE=Samantha
SPEECH_RATE=200
AUDIO_PLAYER=afplay
TIMEOUT=90
WAIT_INTERVAL=3
VOSK_MODEL_PATH=models/vosk-model-small-en-us-0.15
SAMPLE_RATE=16000
MIC_DEVICE=RØDE VideoMic NTG
PROMPT_FILE=prompt.txt
``` 