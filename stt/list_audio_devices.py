import sounddevice as sd

print("\n🔊 Available Audio Devices:\n")
for i, device in enumerate(sd.query_devices()):
    print(f"[{i}] {device['name']}  |  Input Channels: {device['max_input_channels']}  |  Output Channels: {device['max_output_channels']}")
