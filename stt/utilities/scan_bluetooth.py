#!/usr/bin/env python3
"""
Bluetooth Device Scanner Utility
Scans for nearby Bluetooth devices and shows their MAC addresses.
Useful for finding your Bluetooth speaker's MAC address for the BLUETOOTH_SPEAKER env variable.
"""

import subprocess
import sys
import time
import re

def check_bluetooth_tools():
    """Check if required Bluetooth tools are available."""
    try:
        result = subprocess.run(["which", "bluetoothctl"], capture_output=True)
        if result.returncode != 0:
            print("❌ bluetoothctl not found")
            print("💡 Install with: sudo apt install bluez-utils")
            return False
        return True
    except Exception as e:
        print(f"❌ Error checking Bluetooth tools: {e}")
        return False

def scan_devices(scan_time=10):
    """Scan for Bluetooth devices for the specified time."""
    print(f"🔵 Scanning for Bluetooth devices for {scan_time} seconds...")
    print("💡 Make sure your Bluetooth speaker is in pairing mode!")
    print()
    
    try:
        # Start scanning
        scan_process = subprocess.Popen(
            ["bluetoothctl", "scan", "on"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for scan time
        time.sleep(scan_time)
        
        # Stop scanning
        subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True)
        scan_process.terminate()
        
        # Get list of discovered devices
        result = subprocess.run(
            ["bluetoothctl", "devices"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("❌ Failed to get device list")
            return []
        
        return parse_devices(result.stdout)
        
    except Exception as e:
        print(f"❌ Error during scan: {e}")
        return []

def parse_devices(devices_output):
    """Parse bluetoothctl devices output."""
    devices = []
    
    for line in devices_output.strip().split('\n'):
        if line.startswith('Device '):
            # Format: Device AA:BB:CC:DD:EE:FF Device Name
            parts = line.split(' ', 2)
            if len(parts) >= 3:
                mac = parts[1]
                name = parts[2]
                devices.append((mac, name))
            elif len(parts) == 2:
                mac = parts[1]
                name = "Unknown Device"
                devices.append((mac, name))
    
    return devices

def show_paired_devices():
    """Show already paired devices."""
    try:
        result = subprocess.run(
            ["bluetoothctl", "devices", "Paired"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            devices = parse_devices(result.stdout)
            if devices:
                print("🔗 Already Paired Devices:")
                for mac, name in devices:
                    print(f"   {mac} - {name}")
                print()
        
    except Exception:
        pass  # Skip if command fails

def main():
    """Main scanner function."""
    print("🔵 Bluetooth Device Scanner")
    print("=" * 40)
    
    # Check if Bluetooth tools are available
    if not check_bluetooth_tools():
        sys.exit(1)
    
    # Show already paired devices first
    show_paired_devices()
    
    # Ask user for scan time
    try:
        scan_time = input("Enter scan time in seconds (default 10): ").strip()
        scan_time = int(scan_time) if scan_time else 10
    except ValueError:
        scan_time = 10
    
    # Scan for devices
    devices = scan_devices(scan_time)
    
    print("\n🔍 Discovered Devices:")
    if not devices:
        print("   No devices found")
        print("💡 Make sure your device is in pairing mode and try again")
    else:
        print()
        for i, (mac, name) in enumerate(devices, 1):
            print(f"   {i}. {mac} - {name}")
        
        print("\n📋 To use a device, add this to your .env file:")
        print("   BLUETOOTH_SPEAKER=<MAC_ADDRESS>")
        print("\n📖 Example:")
        if devices:
            example_mac = devices[0][0]
            print(f"   BLUETOOTH_SPEAKER={example_mac}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Scan cancelled")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")