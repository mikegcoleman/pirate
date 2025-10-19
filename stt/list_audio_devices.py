#!/usr/bin/env python3
"""
Audio Device Listing Utility for Raspberry Pi Pirate Project
Shows all available audio devices with PulseAudio/PipeWire source/sink names clearly visible.
"""

import sounddevice as sd

def main():
    print("\n=== Audio Device Information ===\n")
    
    # List all host APIs
    print("Available Host APIs:")
    for i, api in enumerate(sd.query_hostapis()):
        device_count = api.get('device_count', len([d for d in sd.query_devices() if d['hostapi'] == i]))
        print(f"  [{i}] {api['name']} - {device_count} devices")
    print()
    
    # List all devices with detailed information
    print("Available Audio Devices:")
    print("-" * 80)
    
    for i, device in enumerate(sd.query_devices()):
        # Build device capabilities
        capabilities = []
        if device['max_input_channels'] > 0:
            capabilities.append(f"Input: {device['max_input_channels']} ch")
        if device['max_output_channels'] > 0:
            capabilities.append(f"Output: {device['max_output_channels']} ch")
        
        # Get host API info
        try:
            hostapi = sd.query_hostapis()[device['hostapi']]['name']
        except (KeyError, IndexError):
            hostapi = "Unknown"
        
        # Display device info
        print(f"[{i:2d}] {device['name']}")
        print(f"     Capabilities: {' | '.join(capabilities) if capabilities else 'None'}")
        print(f"     Sample Rate: {device['default_samplerate']:.0f} Hz")
        print(f"     Host API: {hostapi}")
        print()
    
    # Show current defaults
    print("=" * 80)
    print("Current Default Devices:")
    try:
        default_input = sd.query_devices(kind='input')
        print(f"Input:  [{sd.default.device[0]}] {default_input['name']}")
    except Exception as e:
        print(f"Input:  Error - {e}")
    
    try:
        default_output = sd.query_devices(kind='output')
        print(f"Output: [{sd.default.device[1]}] {default_output['name']}")
    except Exception as e:
        print(f"Output: Error - {e}")
    
    print()
    print("=" * 80)
    print("Recommended .env Configuration for Raspberry Pi:")
    print("# Use the exact device name from above for MIC_DEVICE")
    print("MIC_DEVICE=alsa_input.usb-Antlion_Audio_Antlion_USB_Microphone-00.mono-fallback")
    print("SAMPLE_RATE=16000")
    print("BLOCKSIZE=4000  # 250ms latency @ 16kHz - try 3200/2400 for lower latency")
    print("AUDIO_PLAYER=paplay")
    print()
    print("PulseAudio Commands to Set Defaults:")
    print("# Set default source (microphone):")
    print('pactl set-default-source "alsa_input.usb-Antlion_Audio_Antlion_USB_Microphone-00.mono-fallback"')
    print("# Set default sink (speaker) - replace with your Bluetooth sink name:")
    print('pactl set-default-sink "bluez_output.24_F4_95_F4_CA_45.1"')
    print()

if __name__ == "__main__":
    main()