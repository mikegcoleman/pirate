import sounddevice as sd

print("\nAvailable Audio Devices:\n")
for i, device in enumerate(sd.query_devices()):
    device_type = []
    if device['max_input_channels'] > 0:
        device_type.append(f"Input: {device['max_input_channels']}")
    if device['max_output_channels'] > 0:
        device_type.append(f"Output: {device['max_output_channels']}")
    
    # Get hostapi name safely
    try:
        hostapi = sd.query_hostapis()[device['hostapi']]['name']
        api_info = f" | API: {hostapi}"
    except (KeyError, IndexError):
        api_info = ""
    
    print(f"[{i}] {device['name']} | {' | '.join(device_type)}{api_info}")

print(f"\nDefault Devices:")
print(f"Input:  [{sd.default.device[0]}] {sd.query_devices(kind='input')['name']}")
print(f"Output: [{sd.default.device[1]}] {sd.query_devices(kind='output')['name']}")

print(f"\nRecommended .env settings for Raspberry Pi:")
print(f"MIC_DEVICE=default")
print(f"SAMPLE_RATE=16000") 
print(f"BLOCKSIZE=4000")
print(f"AUDIO_PLAYER=aplay")
