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
│   ├── app.py            # Flask API server with Kokoro TTS
│   ├── requirements.txt  # Python dependencies (kokoro-onnx, torch)
│   ├── Dockerfile        # Container configuration
│   ├── compose.yaml      # Docker compose setup (simplified)
│   ├── env.example       # Environment template
│   └── README.md         # Comprehensive documentation
├── combined/              # Cloud-dependent test version
│   └── main.py           # Fully cloud-dependent app for quick hardware testing
└── CLAUDE.md             # This file
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

### 5. Filler Phrase System (New Feature)
- Pre-recorded engaging phrases during API delays
- 25 pirate-themed filler audio clips
- Random selection with no immediate repeats
- Thread-safe playback with interrupt capability
- Respects audio routing configuration
- **Status**: ✅ Implemented

### 8. Ambient Audio System (New Feature)
- Continuous looping background ambience audio
- Low volume (30% default) to avoid interfering with speech
- Plays continuously during filler phrases and API responses
- Thread-safe with graceful startup/shutdown
- Configurable volume and enable/disable options
- **Status**: ✅ Implemented

### 6. Environment Variable Validation
- Comprehensive startup validation
- Range checking for numeric values
- File and tool availability checks
- **Status**: ✅ Implemented

### 7. TTS Integration (Kokoro)
- Character-focused TTS engine
- Automatic model downloading
- GPU/CPU acceleration support
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
- **TTS**: Kokoro TTS with GPU acceleration (RTX 5070)
- **Audio**: `mpg123` or Windows Media Player
- **Performance**: GPU-accelerated TTS, similar to macOS
- **Config**: Use `requirements-win.txt` for proper PyTorch CUDA support

## Environment Variables

### Required
```bash
API_URL=http://localhost:8080/api/chat
LLM_MODEL=llama3.2:8b-instruct-q4_K_M
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

### Filler Phrases Configuration
```bash
FILLER_ENABLED=true     # Enable engaging filler phrases during API delays
```

### Ambient Audio Configuration
```bash
AMBIENT_ENABLED=true    # Enable continuous background ambience
AMBIENT_VOLUME=0.3      # Background volume (0.0 to 1.0, low to not interfere)
```

## Recent Changes

### Ambient Audio System Implementation (Current Session)
- ✅ Created continuous ambient audio system with looping background audio
- ✅ Integrated ambient player into main client.py for continuous operation
- ✅ Added low volume (30% default) to avoid interfering with speech
- ✅ Thread-safe playback with graceful startup and shutdown
- ✅ Respects existing audio routing (Bluetooth speaker, skeleton audio)
- ✅ Added AMBIENT_ENABLED and AMBIENT_VOLUME environment variables for control
- ✅ Full testing suite to verify functionality and speech overlap scenarios
- 🌊 **Impact**: Mr. Bones now has immersive background atmosphere throughout interactions

### Filler Phrase System Implementation (Previous Session)
- ✅ Created comprehensive filler playback system with 25 pre-recorded phrases
- ✅ Integrated filler player into main client.py to play during API delays
- ✅ Added thread-safe playback with interrupt capability when response arrives
- ✅ Random phrase selection with no immediate repeats for variety
- ✅ Respects existing audio routing (Bluetooth speaker, skeleton audio)
- ✅ Added FILLER_ENABLED environment variable for easy control
- ✅ Full testing suite to verify functionality across scenarios
- 🎭 **Impact**: Mr. Bones now feels much more responsive during processing delays

### Model Comparison Test Restructuring (Previous Session)
- ✅ Restructured `models_list.json` to separate DMR and OpenAI models into `"dmr"` and `"openai"` sections
- ✅ Updated `model_comparison_test.py` to route requests to correct provider based on model categorization
- ❌ **BLOCKER**: Windows machine (192.168.50.66:12434) Docker Model Runner not responding - need to start DMR service
- 🔧 **Next Steps**: Start Docker Model Runner on Windows machine, verify firewall settings, update models_list.json with actual available models

### TTS GPU Acceleration Fixed (Latest)
- ✅ Fixed Kokoro TTS to use GPU acceleration instead of hardcoded CPU
- ✅ Resolved Windows file locking issue with temporary WAV files
- ✅ Updated LLM_BASE_URL to correct Docker Model Runner endpoint
- ✅ Added platform-specific requirements files (requirements-win.txt)
- ✅ Full RTX 5070 compatibility with PyTorch 2.7.0+cu128

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
- ✅ Kokoro TTS integration with GPU acceleration
- ✅ Health check endpoint
- ✅ Comprehensive documentation
- ✅ Environment template
- ✅ Simplified Docker configuration
- ✅ Automatic TTS model downloading
- ✅ Windows file handling fixes
- ✅ Docker Model Runner integration

## Development Workflow

### For Windows API Development:
1. Copy `env.example` to `.env` in `llm-api/`
2. Configure `LLM_BASE_URL=http://localhost:12434/engines/llama.cpp/v1` for Docker Model Runner
3. Set `PORT` if needed (default: 8080)
4. Install dependencies: `pip install -r requirements-win.txt` (includes CUDA PyTorch support)
5. Ensure Docker Model Runner is running with desired LLM model
6. Run `python app.py`
7. Test with: `curl http://localhost:8080/health`

### For Frontend Testing:
1. Copy `mac_env` to `stt/.env` for Mac development
2. Copy `pi_env` to `stt/.env` for Pi deployment
3. Configure `API_URL` to point to your API
4. Run `python main.py`

### For Quick Hardware Testing:
1. Use `combined/main.py` for fully cloud-dependent testing
2. This version bypasses local API setup for rapid hardware validation
3. Ideal for testing audio input/output without setting up the full architecture

## LLM Recommendations

### For RTX 5070 (12GB VRAM):
- **Llama 3.2 8B** - Current choice, good character consistency
- **Llama 3.3 8B** - Best character consistency (future upgrade)
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
1. ✅ ~~Prewarm bluetooth speaker w/ underlying ambient sounds~~ (Ambient audio system implemented)
2. Add movement
3. Add conversation timer

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

## Production Environment Details

### API Server (Windows)
- **Hardware**: AMD 9800X3D, 64GB RAM, RTX 5070
- **Network**: High-speed internet available
- **Role**: All heavy processing (LLM, TTS) runs here
- **Deployment**: Containerized with Docker

### Frontend (Raspberry Pi)
- **Hardware**: Raspberry Pi 4 (limited resources)
- **Network**: Connected to API server
- **Role**: Audio capture, playback, and user interaction
- **Deployment**: Native Python application

### TTS Implementation Status
- **Current Status**: ✅ Kokoro TTS with GPU acceleration working
- **Performance**: GPU-accelerated on RTX 5070 (CUDA 13.0 + PyTorch 2.7.0+cu128)
- **Voice Quality**: Good English voice quality, character-focused TTS
- **Platform Support**: Windows (GPU), Linux/Pi (CPU fallback)
- **File Management**: Windows file locking issues resolved
- **Future Enhancement**: Consider voice cloning for authentic pirate voice

## Animated Skeleton Integration

### Overview
The project integrates with Home Depot's 6.5' "Animated Skelly" BLE device to provide physical movement synchronized with Mr. Bones' speech. The skeleton uses Zhuhai Jieli (JL) RCSP protocol over BLE for control commands.

### Device Specifications
- **Device Name**: "Animated Skelly"
- **BLE MAC Address**: `24:F4:95:CA:21:91` (control interface)
- **Classic BT MAC Address**: `24:F4:95:F4:CA:45` (audio interface) 
- **Primary Service**: `0000ae00-0000-1000-8000-00805f9b34fb` (JL RCSP)
- **Write Characteristic**: `0000ae01-0000-1000-8000-00805f9b34fb` (AE01, handle 0x0082)
- **Notify Characteristic**: `0000ae02-0000-1000-8000-00805f9b34fb` (AE02, handle 0x0084)

### Connection Protocol
1. **Connect** to BLE device by name or MAC address
2. **Subscribe** to AE02 notifications (enable CCCD)
3. **Authenticate** with `02 70 61 73 73` (0x02 + ASCII "pass")
4. **Wait** 300-500ms for authentication acceptance
5. **Send control commands** with 300-500ms spacing between commands

### Movement Control System
The skeleton supports 7 distinct movement patterns controlled by `AA CA` command family:

```python
MOVEMENT_COMMANDS = {
    "Head only": "aaca0100000000000086",
    "Torso only": "aaca040000000000004f", 
    "Arm only": "aaca02000000000000c1",
    "Head + Torso": "aaca0500000000000072",
    "Head + Arm": "aaca030000000000000fc",
    "Torso + Arm": "aaca0600000000000035",
    "All (Head + Torso + Arm)": "aacaff0000000000000bd"
}
```

**Movement Behavior**:
- Each command starts a ~15-20 second movement sequence
- Same command sent twice = **extends** movement duration
- Different command = **switches** to new movement type
- Movement stops naturally when sequence completes
- No explicit stop command - only sequence completion or switching

### Eyes Animation Control
18 distinct eye animations controlled by `AA F9` command family:

```python
EYES_COMMANDS = [
    "aaf90b00000000000034", "aaf9060000000000000c", "aaf9090000000000004e",
    "aaf90c00000000000087", "aaf903000000000000c5", "aaf90f000000000000c0",
    "aaf90d000000000000ba", "aaf90400000000000076", "aaf90a00000000000009",
    "aaf90700000000000031", "aaf901000000000000bf", "aaf91000000000000079",
    "aaf9050000000000004b", "aaf90e000000000000fd", "aaf90800000000000073",
    "aaf91100000000000044", "aaf902000000000000f8", "aaf91200000000000003"
]
```

Usage: `await eyes(client, animation_num)` where animation_num is 1-18.

### Lights Control System
Complete RGB lighting control with zones, modes, brightness, speed, and color:

#### Zone Selection (`AA F5` family):
- **All lights**: `AAF5 FFCF`
- **Lights 1**: `AAF5 00FA`
- **Lights 2**: `AAF5 01A4`

#### Mode Selection (`AA F2` family):
- **Static**: `AAF2 0101 0000 0000 0067`
- **Strobe**: `AAF2 0102 0000 0000 003E`
- **Pulsing**: `AAF2 0103 0000 0000 0009`

#### Parameter Control:
- **Brightness**: `AAF3 FFXX 0000 0000 XXXX` (XX = 0-255 scale)
- **Color**: `AAF4 XXXX XXXX 0000 0000 0000 XX` (proprietary color encoding)
- **Speed**: `AAF6 FFXX 0000 0000 XXXX` (XX = 0-10 decimal scale)

### Classic Bluetooth Audio Integration
The skeleton includes a built-in speaker accessible via Classic Bluetooth A2DP. This enables dual connectivity:

#### Dual Connectivity Architecture:
- **BLE Connection**: Control commands (movement, eyes, lights)
- **Classic BT Connection**: Audio streaming to built-in speaker

#### Audio Pairing Sequence:
```python
# Complete sequence to enable Classic BT audio pairing
async def enable_classic_bt_audio(client):
    # 1. Preset sync (loads main menu)
    await send_cmd(client, "AA D0 5E")  # Query presets
    await send_cmd(client, "AA E5 DF")  # Initialize
    await send_cmd(client, "AA D1 00")  # Confirm presets
    
    # 2. Enter live mode + setup
    await send_cmd(client, "AA E5 DF")  # Re-initialize
    await send_cmd(client, "AA C6 00 00 00 BE")  # Setup
    
    # 3. Trigger record mode (enables Classic BT)
    await send_cmd(client, "AA FD 01 D2")  # Record mode trigger
    
    # Classic BT now advertising as "Animated Skelly(Live)" at 24:F4:95:F4:CA:45
    # Use PIN: 1234 for pairing
```

**Critical Requirement**: BLE connection must remain active to maintain Classic BT availability.

### Integration Points with Pirate Assistant

#### 1. Movement Synchronization
```python
# In client.py - trigger movement when Mr. Bones starts speaking
if skeleton_controller and skeleton_controller.connected:
    movement_triggered = await skeleton_controller.trigger_speech_movement()
```

#### 2. Audio Routing
- **Option A**: Route TTS audio through skeleton's built-in speaker via Classic BT
- **Option B**: Use external Bluetooth speaker while controlling skeleton movement via BLE
- **Current Implementation**: Supports both via BLUETOOTH_SPEAKER environment variable

#### 3. Visual Effects
Synchronize eye animations and lighting effects with speech patterns:
```python
# Example: Flash eyes during key phrases
await skeleton_controller.trigger_eyes_animation(animation_id=5)

# Example: Pulse lights during dramatic moments  
await skeleton_controller.set_lights(mode="pulsing", color="red", brightness=200)
```

### Environment Variables for Skeleton Integration
```bash
# Skeleton Control
SKELETON_BLE_ADDRESS=24:F4:95:CA:21:91  # Optional: specific BLE address
SKELETON_AUDIO_BLE_ADDRESS=24:F4:95:F4:CA:45  # Classic BT for audio
SKELETON_AUDIO_PIN=1234  # Classic BT pairing PIN

# Movement Settings
SKELETON_MOVEMENT_DURATION=15  # Movement sequence duration (seconds)
SKELETON_MOVEMENT_TYPE=all     # Default movement: head, torso, arm, all
SKELETON_EYES_ANIMATION=1      # Default eye animation (1-18)

# Lighting Settings  
SKELETON_LIGHTS_MODE=static    # static, strobe, pulsing
SKELETON_LIGHTS_COLOR=white    # white, red, blue, green
SKELETON_LIGHTS_BRIGHTNESS=255 # 0-255
SKELETON_LIGHTS_SPEED=5        # 0-10 (for animated modes)
```

### Implementation Status
- ✅ **BLE Protocol Decoded**: Complete command set for movement, eyes, lights
- ✅ **Classic BT Audio**: Working dual connectivity with audio streaming
- ✅ **Movement Integration**: Basic movement triggering in client.py
- ❌ **Advanced Synchronization**: Detailed speech-to-movement mapping (pending)
- ❌ **Visual Effects**: Eye/light synchronization with speech content (pending)
- ❌ **Audio Routing**: Direct integration with skeleton speaker (pending)

### Ready-to-Use Python Code
Complete skeleton controller implementation available in `/home/mikegcoleman/src/ble/`:
- `audio_pairing.py`: Classic BT audio setup
- `CLAUDE.md`: Complete protocol documentation
- `test_all_controls.py`: Comprehensive testing suite

### Future Enhancements
1. **Emotion-Based Movements**: Map speech sentiment to movement patterns
2. **Synchronized Lighting**: Beat detection for music-synchronized lighting
3. **Advanced Eye Animations**: Context-aware eye expressions
4. **Audio Ducking**: Automatically lower skeleton audio during speech
5. **Voice Commands**: Direct skeleton control via voice commands
6. **Performance Modes**: Pre-programmed sequences for different scenarios 