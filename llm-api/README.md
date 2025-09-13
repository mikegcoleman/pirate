# Pirate Voice Assistant - Node.js API

High-performance Node.js API for the Pirate Voice Assistant, featuring LLM integration and streaming TTS audio generation.

## Features

- **Fast HTTP Performance**: ~1.4s response time (vs 3.4s Python version)
- **Streaming Audio**: Server-Sent Events with chunked TTS generation
- **ElevenLabs TTS**: High-quality voice synthesis
- **Docker Model Runner**: Integration with local LLM inference
- **Text Processing**: Contractions expansion and UTF-8 cleanup
- **Environment Validation**: Comprehensive startup checks
- **Error Handling**: Graceful degradation and detailed logging

## Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Configure environment variables (see below)
# Start the server
npm start

# Or for development with auto-reload
npm run dev
```

## Environment Variables

Required variables in `.env`:

```bash
# Server Configuration
PORT=8080
DEBUG=false
ENABLE_CORS=true

# LLM Backend Configuration
LLM_BASE_URL=http://localhost:12434/engines/llama.cpp/v1
LLM_MODEL=ai/llama3.2:latest

# ElevenLabs TTS Configuration
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here

# Performance Settings
LLM_TIMEOUT=30
```

## API Endpoints

### `POST /api/chat/stream`

Streaming chat endpoint with chunked audio generation.

**Request:**
```json
{
  "model": "ai/llama3.2:latest",
  "messages": [
    {"role": "user", "content": "What is your favorite letter?"}
  ]
}
```

**Response:** Server-Sent Events stream:
```
data: {"type": "metadata", "total_chunks": 3, "text": "Aye, matey! Me favorite letter be 'R'!"}

data: {"type": "audio_chunk", "chunk_id": 1, "text_chunk": "Aye, matey!", "audio_base64": "..."}

data: {"type": "audio_chunk", "chunk_id": 2, "text_chunk": "Me favorite letter be 'R'!", "audio_base64": "..."}

data: {"type": "complete"}
```

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "pirate-api",
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

## Performance

- **LLM Response Time**: ~1.4s (down from 3.4s Python)
- **Memory Usage**: Optimized for streaming
- **Concurrent Requests**: Async/await architecture

## Configuration Files

- `config/contractions.json`: Contraction to expansion mappings
- `config/utf8-fixes.json`: UTF-8 encoding fixes

## Dependencies

- `express`: Web framework
- `axios`: HTTP client (optimized for DMR)
- `elevenlabs`: TTS integration
- `uuid`: Request ID generation
- `dotenv`: Environment configuration

## Docker Deployment

The application is structured for easy containerization:

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY . .
EXPOSE 8080
CMD ["npm", "start"]
```

## Development

```bash
# Install dev dependencies
npm install

# Run in development mode
npm run dev

# Test performance
node ../test_dmr.js
```

## Migration from Python

This Node.js version provides:
- **59% faster response times**
- **Identical functionality** to Python version
- **Better resource utilization**
- **Simplified deployment**