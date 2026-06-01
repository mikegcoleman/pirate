# Platform Configuration Guide

## macOS (Development)
- **TTS**: System `say` command
- **Audio**: `afplay` (Core Audio)
- **Config**: Copy `env.example` to `.env` and set `AUDIO_PLAYER=afplay`

## Raspberry Pi 4 (Production)
- **Audio**: `aplay` (ALSA)
- **Config**: Copy `pi_env_example` to `.env` and fill in your values

## Windows (API Development)
- **Audio**: `mpg123`
- **Config**: Copy `env.example` to `.env` and set `AUDIO_PLAYER=mpg123`

---

## Security Notes

### TLS / HTTPS (Strongly Recommended for Production)

All communication between this frontend and the `llm-api` backend uses plain
HTTP by default. On a local network:

- Conversation audio and text transit the network in cleartext.
- Any host on the same subnet can capture traffic with `tcpdump` / Wireshark.

**Recommended hardening:** Run the API behind a TLS reverse proxy (e.g. Caddy
or nginx with `mkcert`), then set `API_URL=https://...` in your `.env` file.

### Bluetooth / BLE Credentials

Never commit BLE MAC addresses, Bluetooth PINs, or Wi-Fi passwords to source
control. Use environment variables and keep your `.env` file out of git (it is
already in `.gitignore`).

### Microphone Volume (`MIC_VOLUME`)

Must be specified as an integer percentage between `0%` and `200%` (e.g.
`MIC_VOLUME=150%`). Values outside this range are rejected at startup.
