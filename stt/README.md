# STT Frontend - Voice Interface

The frontend component of Mr. Bones pirate voice assistant, handling speech-to-text processing, API communication, and audio playback.

## 🎤 Overview

This module captures voice input, transcribes it using Vosk speech recognition, sends text to the LLM API, and plays back the generated audio responses. It's designed to run on resource-constrained devices like Raspberry Pi.

## 📋 Features

- **Vosk Speech Recognition**: Offline STT processing with confidence validation
- **Audio Device Management**: Cross-platform microphone and speaker support
- **API Communication**: Async HTTP requests to LLM backend
- **Audio Playback**: Platform-specific audio players (afplay, aplay)
- **Environment Validation**: Comprehensive startup checks
- **Error Handling**: Graceful degradation and user feedback

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download Vosk Model

The Vosk model should be downloaded automatically, but if needed:

```bash
# Download and extract to models/vosk-model-small-en-us-0.15/
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip -d models/
```

### 3. Configure Environment

Copy the appropriate platform configuration:

```bash
# For macOS development
cp mac_env .env

# For Raspberry Pi production
cp pi_env .env
```

### 4. Set Up Audio Devices

List available audio devices:

```bash
python list_audio_devices.py
```

Update your `.env` file with the correct device name:

```bash
# Example for macOS
MIC_DEVICE=RØDE VideoMic NTG

# Example for Raspberry Pi
MIC_DEVICE=default
```

### 5. Run the Voice Assistant

```bash
python main.py
```

## ⚙️ Configuration

### Environment Variables

#### Required
```bash
API_URL=http://localhost:8080/api/chat    # LLM API endpoint
LLM_MODEL=llama3.2:8b-instruct-q4_K_M   # Model identifier
```

#### Audio Configuration
```bash
SPEECH_RATE=200        # TTS speech rate (150 for Pi, 200 for Mac)
AUDIO_PLAYER=afplay    # Audio player command
MIC_DEVICE=default     # Microphone device name
```

#### Performance Settings
```bash
TIMEOUT=90             # API request timeout (60s for Pi, 90s for Mac)
WAIT_INTERVAL=3        # Wait interval for status updates
BLOCKSIZE=8000         # Audio block size (4000 for Pi, 8000 for Mac)
```

#### STT Configuration
```bash
VOSK_MODEL_PATH=models/vosk-model-small-en-us-0.15
SAMPLE_RATE=16000
PROMPT_FILE=prompt.txt
```

### Platform-Specific Configurations

#### macOS (Development)
- **Audio Player**: `afplay` (Core Audio)
- **Performance**: Higher settings for responsive development
- **Microphone**: USB/external mics typically work well

#### Raspberry Pi (Production)
- **Audio Player**: `aplay` (ALSA)
- **Performance**: Conservative settings for limited resources
- **Microphone**: USB microphones recommended over built-in

#### Windows (Alternative)
- **Audio Player**: `mpg123` or system player
- **Microphone**: Use device names from `list_audio_devices.py`

## 🔧 Usage

### Basic Operation

1. **Start**: Run `python main.py`
2. **Speak**: Say something when prompted
3. **Listen**: Mr. Bones will respond with pirate character voice
4. **Continue**: Keep the conversation going
5. **Exit**: Ctrl+C to stop

### Audio Device Setup

If you encounter audio issues:

1. **List devices**: `python list_audio_devices.py`
2. **Test microphone**: Check if your device appears in the list
3. **Update config**: Set `MIC_DEVICE` in `.env` to the exact device name
4. **Test speakers**: Ensure your audio player works with test files

### Troubleshooting

#### No Audio Input
- Check microphone permissions
- Verify `MIC_DEVICE` setting
- Test with `list_audio_devices.py`

#### No Audio Output
- Verify `AUDIO_PLAYER` is installed and working
- Test: `afplay test.wav` (macOS) or `aplay test.wav` (Linux)

#### Poor Speech Recognition
- Speak clearly and close to microphone
- Check for background noise
- Adjust `BLOCKSIZE` if needed

#### API Connection Issues
- Verify `API_URL` points to running backend
- Check network connectivity
- Confirm backend health: `curl http://localhost:8080/health`

## 📁 File Structure

```
stt/
├── main.py              # Main conversation loop and API handling
├── stt.py               # Speech-to-text processing with Vosk
├── prompt.txt           # Mr. Bones character prompt
├── requirements.txt     # Python dependencies
├── env.example          # Environment template with examples
├── mac_env             # macOS-specific configuration
├── pi_env              # Raspberry Pi configuration
├── list_audio_devices.py # Audio device discovery utility
└── models/             # Vosk speech recognition models
    └── vosk-model-small-en-us-0.15/
```

## 🔍 Dependencies

- **vosk**: Offline speech recognition
- **sounddevice**: Cross-platform audio I/O
- **httpx**: Async HTTP client for API requests
- **python-dotenv**: Environment variable management
- **cffi**: Required for audio processing
- **tqdm**: Progress bars and utilities

## 🎯 STT Confidence Checking

The system includes intelligent speech validation:

- **Confidence Threshold**: 0.3 (lenient for children's speech)
- **Noise Filtering**: Removes common non-speech sounds
- **Length Validation**: Ignores very short transcriptions
- **Feedback**: Provides audio prompts for unclear speech

## 🔄 Error Handling

- **API Failures**: Graceful degradation with user feedback
- **Audio Issues**: Platform-specific error messages
- **Network Problems**: Timeout handling and retry suggestions
- **Configuration Errors**: Detailed validation messages

## 🚀 Performance Tips

### For Raspberry Pi
- Use lower `BLOCKSIZE` (4000) for better real-time performance
- Set longer `TIMEOUT` (60s) to accommodate slower processing
- Consider USB microphone for better audio quality

### For Development
- Higher `BLOCKSIZE` (8000) for better audio quality
- Shorter `TIMEOUT` (90s) for responsive testing
- Use quality USB microphones for consistent results

## 📊 Monitoring

The frontend provides detailed logging:

- **Environment validation** results at startup
- **Audio device** detection and configuration
- **API request/response** details with timing
- **STT confidence** scores and validation
- **Error details** with troubleshooting hints

Check console output for real-time status and debugging information.