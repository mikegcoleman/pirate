# Combined - Cloud Testing Version

A simplified, all-in-one version of Mr. Bones pirate voice assistant for quick hardware testing and cloud-dependent deployment scenarios.

## 🎯 Purpose

This version bypasses the local API architecture and connects directly to cloud services, making it ideal for:

- **Quick Hardware Testing**: Validate audio input/output without setting up the full backend
- **Cloud-Dependent Deployment**: When local LLM processing isn't available
- **Development Prototyping**: Rapid testing of voice interaction flows
- **Demo Scenarios**: Simple setup for demonstrations

## 🏗️ Architecture

```
Voice Input → STT (Vosk) → Cloud LLM (OpenAI) → Cloud TTS (ElevenLabs) → Audio Output
```

**Key Differences from Full System:**
- No local API server required
- Direct cloud service integration
- Simplified configuration
- Faster setup time

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download Vosk Model

The system expects the Vosk model at the standard location:

```bash
# Model should be at: ../stt/models/vosk-model-small-en-us-0.15
# If missing, download from: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
```

### 3. Configure API Keys

```bash
cp .env.example .env
# Edit .env with your API credentials
```

Required environment variables:
```bash
OPENAI_API_KEY=sk-your-openai-key-here
ELEVENLABS_API_KEY=your-elevenlabs-key
ELEVENLABS_VOICE_ID=your-voice-id
VOSK_MODEL_PATH=../stt/models/vosk-model-small-en-us-0.15
```

### 4. Run the Assistant

```bash
python main.py
```

## ⚙️ Configuration

### Environment Variables

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here        # Required: OpenAI API key
OPENAI_MODEL=gpt-4o                    # Optional: Model to use

# ElevenLabs Configuration  
ELEVENLABS_API_KEY=your-key-here       # Required: ElevenLabs API key
ELEVENLABS_VOICE_ID=your-voice-id      # Required: Voice ID for character

# Vosk Configuration
VOSK_MODEL_PATH=../stt/models/vosk-model-small-en-us-0.15  # Path to STT model

# Audio Configuration (Optional)
MIC_DEVICE=default                     # Microphone device name
SAMPLE_RATE=16000                      # Audio sample rate
BLOCKSIZE=8000                         # Audio processing block size
```

### Voice Selection

To find and configure ElevenLabs voice:

1. Visit [ElevenLabs Voice Library](https://elevenlabs.io/voice-library)
2. Choose a character-appropriate voice
3. Copy the Voice ID to your `.env` file
4. Consider creating a custom pirate voice for authenticity

## 🎮 Usage

### Basic Operation

1. **Start**: `python main.py`
2. **Listen**: Wait for "Listening for speech..." prompt
3. **Speak**: Say something to Mr. Bones
4. **Enjoy**: Listen to the pirate character response
5. **Continue**: Keep the conversation going
6. **Exit**: Press Ctrl+C to stop

### Character Interaction

Mr. Bones will respond with:
- Authentic pirate language and expressions
- Age-appropriate, family-friendly content
- Conversational responses about pirate life
- Helpful answers in character

## 🔧 Hardware Testing

This version is perfect for validating:

### Audio Input Testing
- Microphone capture quality
- Speech recognition accuracy
- Background noise handling
- Device compatibility

### Audio Output Testing
- Speaker functionality
- Audio quality and volume
- Latency measurements
- Platform compatibility

### Platform Testing
- Cross-platform audio device support
- Library compatibility
- Performance characteristics
- Error handling

## 📊 Performance

### Cloud Service Latency
- **STT**: Local processing (fast)
- **LLM**: Cloud API (~1-3 seconds)
- **TTS**: Cloud API (~2-5 seconds)
- **Total**: ~3-8 seconds per interaction

### Optimization Tips
- Use faster OpenAI models (gpt-3.5-turbo)
- Enable ElevenLabs voice optimization
- Optimize audio buffer sizes
- Consider regional API endpoints

## 🔍 Dependencies

```python
# Core
vosk==0.3.44              # Speech recognition
openai                    # LLM API client
elevenlabs               # TTS API client
sounddevice==0.5.2       # Audio I/O
python-dotenv==1.1.0     # Environment management

# Audio Processing
cffi==1.17.1             # Audio library bindings
```

## 🚨 Troubleshooting

### Common Issues

#### STT Not Working
- Check microphone permissions
- Verify Vosk model path
- Test with `list_audio_devices.py` from stt/

#### OpenAI API Errors
- Verify API key is correct and active
- Check account credit balance
- Test with simple API call

#### ElevenLabs TTS Fails
- Confirm API key and voice ID
- Check account quota limits
- Test voice ID in ElevenLabs dashboard

#### Audio Playback Issues
- Verify speakers/headphones connected
- Check system audio settings
- Test with simple audio file

### Network Issues
- Ensure stable internet connection
- Check firewall settings for API calls
- Consider API rate limiting

## 🔄 Migration to Full System

When ready to deploy the full architecture:

1. **Backend Setup**: Deploy `llm-api/` with local LLM
2. **Frontend Config**: Update `stt/` to use local API
3. **Performance**: Gain local processing benefits
4. **Cost**: Reduce cloud API usage

## 📁 File Structure

```
combined/
├── main.py              # All-in-one application
├── prompt.txt           # Mr. Bones character prompt
├── requirements.txt     # Python dependencies
├── test_setup.py        # Hardware validation script
└── README.md           # This file
```

## 🎯 Use Cases

### Development Testing
- Quick iteration on voice interaction flows
- Testing character prompt modifications
- Validating audio hardware setup

### Demo Scenarios
- Simple setup for showcasing the concept
- No need for local LLM infrastructure
- Reliable cloud service backends

### Hardware Validation
- Test Raspberry Pi audio capabilities
- Validate microphone and speaker setup
- Measure performance characteristics

### Prototype Development
- Rapid voice assistant prototyping
- Character voice experimentation
- User experience testing

## 💡 Next Steps

Once hardware testing is complete:

1. **Deploy Full System**: Set up local LLM and API
2. **Performance Tuning**: Optimize for production use
3. **Character Enhancement**: Fine-tune voice and responses
4. **Feature Addition**: Implement conversation timer and advanced features

This cloud version provides a solid foundation for understanding the complete voice assistant workflow before committing to the full local infrastructure.