#!/usr/bin/env python3
"""
Mr. Bones Skeleton Connection Setup
Establishes both BLE control connection and BT Classic audio pairing.
Run this once before starting the main pirate assistant.
"""

import asyncio
import subprocess
from typing import Optional

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("❌ Bleak not installed. Install with: pip install bleak>=1.1.0")
    exit(1)

# Skeleton Configuration
SKELETON_BLE_NAME = "Animated Skelly"
SKELETON_BLE_MAC = "24:F4:95:CA:21:91"      # BLE control interface
SKELETON_AUDIO_MAC = "24:F4:95:F4:CA:45"    # Classic BT audio interface
SKELETON_AUDIO_PIN = "1234"                 # Classic BT pairing PIN

# BLE Configuration
WRITE_UUID = "0000ae01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ae02-0000-1000-8000-00805f9b34fb"
AUTH_COMMAND = "02 70 61 73 73"

def hx(s: str) -> bytes:
    """Convert hex string to bytes."""
    return bytes.fromhex(''.join(s.split()))

def on_notify(_, data: bytearray):
    """Handle BLE notifications."""
    print(f"  BLE notify: {data.hex()}")

def cleanup_existing_bt_pairing() -> bool:
    """Remove any existing BT pairing with skeleton audio interface."""
    try:
        print(f"🧹 Cleaning up existing BT pairing for {SKELETON_AUDIO_MAC}...")
        
        # Check if device is known/paired
        list_cmd = ["bluetoothctl", "info", SKELETON_AUDIO_MAC]
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "Device" in result.stdout:
            print("  Found existing pairing - removing...")
            
            # Disconnect and remove the device
            cleanup_commands = f"""
disconnect {SKELETON_AUDIO_MAC}
remove {SKELETON_AUDIO_MAC}
quit
"""
            
            process = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, _ = process.communicate(input=cleanup_commands, timeout=15)
            
            if "Device has been removed" in stdout or "not available" in stdout:
                print("✅ Existing pairing cleaned up")
            else:
                print("⚠️ Cleanup may have failed, continuing anyway")
        else:
            print("  No existing pairing found")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("⏱️ BT cleanup timed out")
        return False
    except Exception as e:
        print(f"⚠️ BT cleanup error: {e}")
        return False

async def find_skeleton() -> Optional[str]:
    """Find skeleton BLE device and return its address."""
    print("🔍 Scanning for Mr. Bones skeleton...")
    
    devices = await BleakScanner.discover(timeout=8.0)
    for device in devices:
        if device.name and SKELETON_BLE_NAME.lower() in device.name.lower():
            print(f"  Found: {device.name} ({device.address})")
            return device.address
        if device.address and SKELETON_BLE_MAC.lower() in device.address.lower():
            print(f"  Found by MAC: {device.address}")
            return device.address
    
    return None

async def setup_ble_and_audio(verbose: bool = True):
    """Set up both BLE control and BT Classic audio connections."""
    if verbose:
        print("🤖 Mr. Bones Skeleton Connection Setup")
        print("=" * 45)
    
    # Step 0: Clean up any existing BT pairing
    if not cleanup_existing_bt_pairing():
        if verbose:
            print("⚠️ BT cleanup failed, continuing anyway...")
        # Continue anyway - might still work
    
    # Step 1: Find and connect to BLE
    skeleton_addr = await find_skeleton()
    if not skeleton_addr:
        if verbose:
            print("❌ Skeleton not found via BLE scan")
        return False
    
    if verbose:
        print(f"🔗 Connecting to BLE interface: {skeleton_addr}")
    
    async with BleakClient(skeleton_addr) as client:
        print("  Enabling notifications...")
        await client.start_notify(NOTIFY_UUID, on_notify)
        
        print("  Authenticating...")
        await client.write_gatt_char(WRITE_UUID, hx(AUTH_COMMAND), response=False)
        await asyncio.sleep(0.5)
        
        print("✅ BLE connected and authenticated!")
        
        # Step 2: Enable Classic BT audio mode
        print("\n🎵 Enabling Classic Bluetooth audio mode...")
        
        # Complete sequence from working demo code
        await client.write_gatt_char(WRITE_UUID, hx("AA D0 5E"), response=False)  # Query presets
        await asyncio.sleep(0.5)
        await client.write_gatt_char(WRITE_UUID, hx("AA E5 DF"), response=False)  # Initialize
        await asyncio.sleep(0.5)
        await client.write_gatt_char(WRITE_UUID, hx("AA D1 00"), response=False)  # Confirm presets
        await asyncio.sleep(0.5)
        
        # Enter live mode + setup
        await client.write_gatt_char(WRITE_UUID, hx("AA E5 DF"), response=False)  # Re-initialize
        await asyncio.sleep(0.5)
        await client.write_gatt_char(WRITE_UUID, hx("AA C6 00 00 00 BE"), response=False)  # Setup
        await asyncio.sleep(0.5)
        
        # Trigger record mode (enables Classic BT)
        await client.write_gatt_char(WRITE_UUID, hx("AA FD 01 D2"), response=False)
        await asyncio.sleep(2)  # Give skeleton time to start advertising
        
        print("✅ Classic BT audio mode enabled!")
        print(f"  Device will appear as: 'Animated Skelly(Live)'")
        print(f"  MAC address: {SKELETON_AUDIO_MAC}")
        print(f"  PIN: {SKELETON_AUDIO_PIN}")
        
        # Step 3: Pair with Classic BT audio
        print(f"\n🔵 Pairing with Classic BT audio interface...")
        
        # Check if bluetoothctl is available
        result = subprocess.run(["which", "bluetoothctl"], capture_output=True)
        if result.returncode != 0:
            print("❌ bluetoothctl not found - install bluez-utils")
            return False
        
        # Interactive pairing with dual scan method (this was the working approach)
        try:
            print("  Starting first scan...")
            
            # First scan: 20 seconds
            scan_result = subprocess.run(
                ["timeout", "20", "bluetoothctl", "--", "scan", "on"],
                capture_output=True,
                text=True
            )
            
            # Give time for Classic BT device to be discovered
            await asyncio.sleep(15)
            
            # Stop scanning temporarily
            subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True)
            await asyncio.sleep(2)
            
            # Second scan: 15 seconds (this is what you remembered working)
            print("  Starting second scan for Classic BT device...")
            scan_result2 = subprocess.run(
                ["timeout", "15", "bluetoothctl", "--", "scan", "on"],
                capture_output=True,
                text=True
            )
            await asyncio.sleep(10)
            
            # Stop scanning before pairing
            subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True)
            await asyncio.sleep(1)
            
            # Now try pairing
            pair_result = subprocess.run(
                ["bluetoothctl", "pair", SKELETON_AUDIO_MAC],
                input=f"{SKELETON_AUDIO_PIN}\n",
                text=True,
                capture_output=True,
                timeout=20
            )
            
            # Try connecting
            connect_result = subprocess.run(
                ["bluetoothctl", "connect", SKELETON_AUDIO_MAC],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Trust the device
            subprocess.run(["bluetoothctl", "trust", SKELETON_AUDIO_MAC], capture_output=True)
            
            # Create combined result for success checking
            stdout = f"{pair_result.stdout}\n{connect_result.stdout}"
            
            if ("Pairing successful" in stdout or 
                "Already paired" in stdout or
                "Connection successful" in stdout):
                print("✅ Classic BT audio paired successfully!")
                
                # Test audio sink availability
                sink_name = f"bluez_output.{SKELETON_AUDIO_MAC.replace(':', '_')}.1"
                print(f"🔊 Audio sink should be: {sink_name}")
                
                # Check if PulseAudio sees the sink
                result = subprocess.run(["pactl", "list", "short", "sinks"], 
                                      capture_output=True, text=True)
                if sink_name in result.stdout:
                    print("✅ PulseAudio sink detected!")
                    
                    # Set as default sink for audio routing
                    result = subprocess.run(["pactl", "set-default-sink", sink_name], 
                                          capture_output=True)
                    if result.returncode == 0:
                        print("✅ Set as default audio sink")
                    else:
                        print("⚠️ Could not set as default sink, but manual routing will work")
                else:
                    print("⚠️ PulseAudio sink not yet visible (may take a moment)")
                
                print(f"\n🎭 Setup complete! Skeleton ready for:")
                print(f"  • Movement control via BLE")
                print(f"  • Audio playback with jaw animation via Classic BT")
                print(f"\n💡 Audio will now route to skeleton speaker by default")
                print(f"   Or use: aplay --device={sink_name} file.wav")
                
                return True
                
            else:
                print(f"❌ Classic BT pairing failed")
                print(f"Output: {stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            print("⏱️ Classic BT pairing timed out")
            return False
        except Exception as e:
            print(f"❌ Classic BT pairing error: {e}")
            return False

async def test_movement():
    """Test skeleton movement after setup."""
    print(f"\n🎯 Testing skeleton movement...")
    
    skeleton_addr = await find_skeleton()
    if not skeleton_addr:
        print("❌ Skeleton not found for movement test")
        return
    
    async with BleakClient(skeleton_addr) as client:
        await client.start_notify(NOTIFY_UUID, on_notify)
        await client.write_gatt_char(WRITE_UUID, hx(AUTH_COMMAND), response=False)
        await asyncio.sleep(0.5)
        
        print("🎭 Triggering head movement test...")
        await client.write_gatt_char(WRITE_UUID, hx("aaca0100000000000086"), response=False)
        print("  Movement should last ~15-20 seconds")

async def setup_skeleton_for_client() -> bool:
    """
    Simplified setup function for client.py integration.
    Returns True if setup succeeded, False otherwise.
    """
    try:
        return await setup_ble_and_audio(verbose=False)
    except Exception:
        return False

async def main():
    """Main setup function for standalone use."""
    try:
        success = await setup_ble_and_audio(verbose=True)
        
        if success:
            test_movement_choice = input("\n🎯 Test skeleton movement? (y/N): ").strip().lower()
            if test_movement_choice in ['y', 'yes']:
                await test_movement()
        else:
            print("\n❌ Setup failed - check connections and try again")
            
    except KeyboardInterrupt:
        print("\n⏹️ Setup interrupted")
    except Exception as e:
        print(f"\n💥 Setup error: {e}")

if __name__ == "__main__":
    asyncio.run(main())