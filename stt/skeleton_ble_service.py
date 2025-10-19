#!/usr/bin/env python3
"""
Persistent BLE service for Mr. Bones skeleton control.
Keeps BLE connection alive and provides movement control.
Run this in one shell and keep it running.
"""

import asyncio
import signal
import sys
from typing import Optional

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("❌ Bleak not installed. Install with: pip install bleak>=1.1.0")
    exit(1)

# Skeleton Configuration
SKELETON_BLE_NAME = "Animated Skelly"
SKELETON_BLE_MAC = "24:F4:95:CA:21:91"

# BLE Configuration
WRITE_UUID = "0000ae01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ae02-0000-1000-8000-00805f9b34fb"
AUTH_COMMAND = "02 70 61 73 73"

def hx(s: str) -> bytes:
    """Convert hex string to bytes."""
    return bytes.fromhex(''.join(s.split()))

def on_notify(_, data: bytearray):
    """Handle BLE notifications."""
    print(f"BLE: {data.hex()}")

class SkeletonBLEService:
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.running = False
        
    async def find_skeleton(self) -> Optional[str]:
        """Find skeleton BLE device."""
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
    
    async def connect(self):
        """Connect to skeleton BLE."""
        skeleton_addr = await self.find_skeleton()
        if not skeleton_addr:
            print("❌ Skeleton not found")
            return False
            
        print(f"🔗 Connecting to BLE: {skeleton_addr}")
        self.client = BleakClient(skeleton_addr)
        
        try:
            await self.client.connect()
            print("  ✅ BLE connected")
            
            await self.client.start_notify(NOTIFY_UUID, on_notify)
            print("  ✅ Notifications enabled")
            
            await self.client.write_gatt_char(WRITE_UUID, hx(AUTH_COMMAND), response=False)
            await asyncio.sleep(0.5)
            print("  ✅ BLE authenticated")
            return True
            
        except Exception as e:
            print(f"❌ BLE connection failed: {e}")
            return False
    
    async def enable_classic_bt_mode(self):
        """Enable Classic BT audio mode via BLE commands."""
        if not self.client or not self.client.is_connected:
            print("❌ BLE not connected")
            return False
            
        print("🎵 Enabling Classic Bluetooth audio mode...")
        
        try:
            # 1. Preset sync (loads main menu) 
            await self.client.write_gatt_char(WRITE_UUID, hx("AA D0 5E"), response=False)
            await asyncio.sleep(0.5)
            await self.client.write_gatt_char(WRITE_UUID, hx("AA E5 DF"), response=False)
            await asyncio.sleep(0.5) 
            await self.client.write_gatt_char(WRITE_UUID, hx("AA D1 00"), response=False)
            await asyncio.sleep(0.5)
            
            # 2. Enter live mode + setup
            await self.client.write_gatt_char(WRITE_UUID, hx("AA E5 DF"), response=False)
            await asyncio.sleep(0.5)
            await self.client.write_gatt_char(WRITE_UUID, hx("AA C6 00 00 00 BE"), response=False)
            await asyncio.sleep(0.5)
            
            # 3. Trigger record mode (enables Classic BT)
            await self.client.write_gatt_char(WRITE_UUID, hx("AA FD 01 D2"), response=False)
            await asyncio.sleep(3)
            
            print("  ✅ Classic BT audio mode enabled!")
            print("  📱 Device now advertising as: 'Animated Skelly(Live)'")
            print("  📍 MAC: 24:F4:95:F4:CA:45, PIN: 1234")
            return True
            
        except Exception as e:
            print(f"❌ Failed to enable Classic BT: {e}")
            return False
    
    async def send_movement_command(self, command: str):
        """Send movement command to skeleton."""
        if not self.client or not self.client.is_connected:
            print("❌ BLE not connected")
            return False
            
        try:
            await self.client.write_gatt_char(WRITE_UUID, hx(command), response=False)
            return True
        except Exception as e:
            print(f"❌ Movement command failed: {e}")
            return False
    
    async def run_service(self):
        """Run the persistent BLE service."""
        print("🤖 Starting Mr. Bones BLE Service")
        print("=" * 40)
        
        if not await self.connect():
            return False
            
        if not await self.enable_classic_bt_mode():
            return False
            
        print("\n🟢 BLE Service Running")
        print("  • Movement control available")
        print("  • Classic BT audio mode enabled")
        print("  • Press Ctrl+C to stop")
        print("-" * 40)
        
        self.running = True
        
        # Keep the service alive
        try:
            while self.running:
                if not self.client.is_connected:
                    print("❌ BLE connection lost - attempting reconnect...")
                    if not await self.connect():
                        break
                        
                await asyncio.sleep(5)  # Heartbeat check
                
        except KeyboardInterrupt:
            print("\n⏹️ Service stopping...")
        except Exception as e:
            print(f"💥 Service error: {e}")
        finally:
            await self.disconnect()
            
        return True
    
    async def disconnect(self):
        """Disconnect from skeleton."""
        self.running = False
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
                print("🔌 BLE disconnected")
            except Exception as e:
                print(f"⚠️ Disconnect error: {e}")

# Global service instance
service = SkeletonBLEService()

async def main():
    """Main service entry point."""
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n⏹️ Shutdown signal received...")
        service.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    success = await service.run_service()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)