# TTS Provider System

The API now supports multiple TTS providers with automatic fallback.

## Configuration

Set the TTS provider in your `.env` file:

```bash
# Use local Kokoro TTS (default)
TTS_PROVIDER=kokoro

# Use ElevenLabs TTS (requires API key)
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
```

## Providers

### 1. Kokoro TTS (Local)
- **Type**: Local neural TTS
- **Pros**: Free, works offline, fast
- **Cons**: Limited voice options
- **Voice**: af_heart (English)

### 2. ElevenLabs TTS (Cloud)
- **Type**: Cloud-based premium TTS
- **Pros**: High quality, natural voices, pirate voice options
- **Cons**: Requires API key, costs per character
- **Model**: eleven_monolingual_v1

### 3. Fallback Message
- **Type**: Pre-recorded message
- **Used when**: Primary TTS fails
- **Message**: "Ahoy matey! I need to head out for a bit - me ship's in need of repairs. I'll be back shortly!"

## Fallback Behavior

1. Try primary TTS provider (Kokoro or ElevenLabs)
2. If primary fails → play pre-recorded fallback message
3. If fallback fails → return error

## Benefits

- **Seamless Experience**: Users always get audio, never silence
- **Character Consistency**: Fallback maintains pirate character
- **No Voice Switching**: Avoids jarring voice changes mid-conversation
- **Reliability**: Multiple layers of fallback ensure robust operation

## Generating Fallback Audio

To generate the actual fallback audio file, run the API once with Kokoro TTS and it will create the proper audio file.