# LLM API - Backend Server

The backend API server for Mr. Bones pirate voice assistant, providing LLM chat completions with integrated text-to-speech generation.

## 🎯 Overview

This Flask-based API server handles chat requests, processes them through local or cloud LLM services, and generates character-appropriate audio responses using Kokoro TTS or ElevenLabs. It's designed to run on powerful hardware with GPU acceleration for optimal performance.

## 🚀 Features

- **LLM Integration**: Support for local (Ollama) and cloud (OpenAI) LLM providers
- **Kokoro TTS**: High-quality local text-to-speech with character voices
- **ElevenLabs TTS**: Cloud-based TTS with custom voice cloning
- **Streaming Support**: Real-time response streaming with sentence-level audio
- **GPU Acceleration**: CUDA support for faster TTS generation
- **Health Monitoring**: Built-in health checks and comprehensive logging
- **Error Handling**: Graceful degradation and fallback mechanisms

## 📋 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt

# For Kokoro TTS (recommended)
pip install kokoro soundfile

# For ElevenLabs TTS (optional)
pip install elevenlabs
```

### 2. Configure Environment

```bash
cp env.example .env
# Edit .env with your configuration
```

### 3. Start the Server

```bash
python app.py
```

The server will start on `http://localhost:8080` by default.

### 4. Test the API

```bash
# Health check
curl http://localhost:8080/health

# Chat request
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:8b-instruct-q4_K_M",
    "messages": [
      {"role": "system", "content": "You are a friendly pirate named Mr. Bones."},
      {"role": "user", "content": "Hello there!"}
    ]
  }'
```

## ⚙️ Configuration

### Environment Variables

#### Server Configuration
```bash
PORT=8080                    # Server port
DEBUG=false                  # Enable debug mode
ENABLE_CORS=true            # Enable CORS for frontend
LOG_LEVEL=INFO              # Logging level
```

#### LLM Configuration
```bash
# Local LLM (Ollama/Docker Model Runner)
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2:8b-instruct-q4_K_M
LLM_TIMEOUT=30

# OpenAI (alternative)
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-your-key-here
```

#### TTS Configuration
```bash
# TTS Provider Selection
TTS_PROVIDER=kokoro          # 'kokoro' or 'elevenlabs'

# Kokoro TTS (local)
KOKORO_MODEL_PATH=./models/kokoro/model.onnx
KOKORO_VOICES_PATH=./models/kokoro/voices-v1.0.bin
USE_GPU=true                 # Enable CUDA acceleration

# ElevenLabs TTS (cloud)
ELEVENLABS_API_KEY=your_api_key
ELEVENLABS_VOICE_ID=your_voice_id

# Fallback Audio
FALLBACK_MESSAGE_PATH=./assets/fallback_message_b64.txt
```

## 🎤 TTS Providers

### Kokoro TTS (Recommended)

**Advantages:**
- High-quality character voices
- Local processing (no API costs)
- GPU acceleration support
- Automatic model downloading

**Setup:**
```bash
pip install kokoro soundfile
# Models download automatically on first use
```

### ElevenLabs TTS

**Advantages:**
- Professional voice cloning
- Cloud processing (no local GPU needed)
- Wide voice selection

**Setup:**
```bash
pip install elevenlabs
# Set API key and voice ID in .env
```

### Fallback Provider

Pre-recorded audio message for when both TTS providers fail. Currently configured but requires audio file generation.

## 🌐 API Endpoints

### `/health` - Health Check
```bash
GET /health
```

Returns server status and configuration info.

### `/api/chat` - Chat Completion
```bash
POST /api/chat
Content-Type: application/json

{
  "model": "llama3.2:8b-instruct-q4_K_M",
  "messages": [
    {"role": "system", "content": "System prompt"},
    {"role": "user", "content": "User message"}
  ]
}
```

**Response:**
```json
{
  "response": "Generated text response",
  "audio_base64": "base64-encoded-wav-audio"
}
```

### `/api/chat/stream` - Streaming Chat
```bash
POST /api/chat/stream
Content-Type: application/json

{
  "model": "llama3.2:8b-instruct-q4_K_M",
  "messages": [...],
  "stream": true
}
```

**Response:** Server-Sent Events stream with text and audio chunks.

## 🐳 Docker Deployment

### Build Image
```bash
docker build -t pirate-api .
```

### Run with Docker Compose
```bash
docker-compose up -d
```

### Environment Configuration
Edit `compose.yaml` to configure environment variables and GPU access.

## 🔧 Development

### Local LLM Setup

#### Ollama
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama3.2:8b-instruct-q4_K_M

# Start server (default: localhost:11434)
ollama serve
```

#### Docker Model Runner
```bash
# Example for local model server
docker run -d -p 11434:11434 \
  --gpus all \
  -v ollama:/root/.ollama \
  ollama/ollama
```

### Testing

```bash
# Test health endpoint
curl http://localhost:8080/health

# Test chat with minimal payload
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"test","messages":[{"role":"user","content":"Hello"}]}'
```

### Debugging

Enable debug mode in `.env`:
```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

Check logs for detailed request/response information.

## 📊 Performance

### Hardware Recommendations

#### Minimum (CPU Only)
- **CPU**: 8+ cores, 3.0GHz+
- **RAM**: 16GB
- **Storage**: 50GB for models

#### Recommended (GPU Accelerated)
- **GPU**: RTX 4070+ with 12GB+ VRAM
- **CPU**: 8+ cores, 3.5GHz+
- **RAM**: 32GB
- **Storage**: 100GB SSD

### Performance Tuning

#### GPU Acceleration
```bash
# Enable CUDA for TTS
USE_GPU=true

# Verify GPU availability
python -c "import torch; print(torch.cuda.is_available())"
```

#### Model Selection
- **Llama 3.2 8B**: Good balance of quality and speed
- **Llama 3.3 8B**: Best character consistency
- **Phi-3.5 3.8B**: Fastest option

#### Quantization
Use `q4_K_M` quantization for optimal VRAM usage with minimal quality loss.

## 🛡️ Security

### API Security
- Input validation on all endpoints
- Request size limits
- Timeout handling
- Error message sanitization

### Model Security
- Local model storage
- Environment variable validation
- Secure credential handling

### Network Security
- CORS configuration
- Port binding options
- Health check endpoints

## 📁 File Structure

```
llm-api/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies  
├── requirements-mac.txt    # macOS-specific dependencies
├── Dockerfile             # Container configuration
├── compose.yaml           # Docker Compose setup
├── env.example            # Environment template
├── assets/               # Static assets
│   └── fallback_message_b64.txt
└── models/               # TTS models (auto-downloaded)
    └── kokoro/
```

## 🔍 Dependencies

### Core
- **Flask**: Web framework
- **requests**: HTTP client for LLM APIs
- **python-dotenv**: Environment management

### TTS (Kokoro)
- **kokoro**: Local TTS engine
- **torch**: PyTorch for neural networks
- **soundfile**: Audio file I/O

### TTS (ElevenLabs)
- **elevenlabs**: Cloud TTS client

### Utilities
- **logging**: Structured logging
- **uuid**: Request tracking
- **tempfile**: Temporary file management

## 🚨 Troubleshooting

### Common Issues

#### TTS Model Loading Fails
```bash
# Check GPU availability
python -c "import torch; print(torch.cuda.is_available())"

# Reinstall with CUDA support
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

#### LLM Connection Errors
```bash
# Test LLM endpoint
curl http://localhost:11434/api/generate

# Check model availability
ollama list
```

#### Audio Generation Fails
- Check TTS provider configuration
- Verify model paths exist
- Test with fallback provider

### Performance Issues

#### Slow Response Times
- Enable GPU acceleration
- Use smaller models (Phi-3.5 3.8B)
- Increase timeout values

#### High Memory Usage
- Use quantized models (q4_K_M)
- Reduce context window size
- Monitor VRAM usage

## 📈 Monitoring

### Health Checks
```bash
# Basic health
curl http://localhost:8080/health

# Detailed status with timestamps
curl -v http://localhost:8080/health
```

### Logging
- Request/response timing
- TTS generation metrics
- Error tracking with request IDs
- GPU utilization monitoring

### Metrics
- Response latency
- TTS generation time
- Memory usage
- Error rates