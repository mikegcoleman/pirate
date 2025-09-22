#!/usr/bin/env python3
"""
Persistent BLE service for Mr. Bones skeleton control.
Keeps BLE connection alive and provides movement control.
Run this in one shell and keep it running.
"""

import asyncio
import signal
import sys
from datetime import datetime
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

def log(message: str, level: str = "INFO") -> None:
    """Consistent, timestamped logging for tracking service progress."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level}: {message}", flush=True)


def hx(s: str) -> bytes:
    """Convert hex string to bytes."""
    return bytes.fromhex(''.join(s.split()))


def on_notify(_, data: bytearray):
    """Handle BLE notifications."""
    log(f"Notification received: {data.hex()}", level="DEBUG")

class SkeletonBLEService:
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.running = False
        
    async def find_skeleton(self) -> Optional[str]:
        """Find skeleton BLE device."""
        log("Scanning for Mr. Bones skeleton...")
        devices = await BleakScanner.discover(timeout=8.0)
        if not devices:
            log("No BLE devices discovered during scan window", level="DEBUG")
        for device in devices:
            if device.name and SKELETON_BLE_NAME.lower() in device.name.lower():
                log(f"Matched by name: {device.name} ({device.address})")
                return device.address
            if device.address and SKELETON_BLE_MAC.lower() in device.address.lower():
                log(f"Matched by MAC: {device.address}")
                return device.address
        return None

    async def connect(self):
        """Connect to skeleton BLE."""
        skeleton_addr = await self.find_skeleton()
        if not skeleton_addr:
            log("Skeleton not found", level="ERROR")
            return False

        log(f"Connecting to BLE device {skeleton_addr}")
        self.client = BleakClient(skeleton_addr)

        try:
            await self.client.connect()
            log("BLE connected")

            await self.client.start_notify(NOTIFY_UUID, on_notify)
            log("Notifications enabled")

            await self.client.write_gatt_char(WRITE_UUID, hx(AUTH_COMMAND), response=False)
            await asyncio.sleep(0.5)
            log("BLE authenticated")
            return True

        except Exception as e:
            log(f"BLE connection failed: {e}", level="ERROR")
            return False

    async def enable_classic_bt_mode(self):
        """Enable Classic BT audio mode via BLE commands."""
        if not self.client or not self.client.is_connected:
            log("BLE not connected", level="ERROR")
            return False

        log("Enabling Classic Bluetooth audio mode...")

        try:
            # 1. Preset sync (loads main menu) 
            log("Sending preset sync commands")
            await self.client.write_gatt_char(WRITE_UUID, hx("AA D0 5E"), response=False)
            await asyncio.sleep(0.5)
            await self.client.write_gatt_char(WRITE_UUID, hx("AA E5 DF"), response=False)
            await asyncio.sleep(0.5) 
            await self.client.write_gatt_char(WRITE_UUID, hx("AA D1 00"), response=False)
            await asyncio.sleep(0.5)
            
            # 2. Enter live mode + setup
            log("Sending live mode setup commands")
            await self.client.write_gatt_char(WRITE_UUID, hx("AA E5 DF"), response=False)
            await asyncio.sleep(0.5)
            await self.client.write_gatt_char(WRITE_UUID, hx("AA C6 00 00 00 BE"), response=False)
            await asyncio.sleep(0.5)

            # 3. Trigger record mode (enables Classic BT)
            log("Triggering record mode to enable Classic BT")
            await self.client.write_gatt_char(WRITE_UUID, hx("AA FD 01 D2"), response=False)
            await asyncio.sleep(3)

            log("Classic BT audio mode enabled")
            log("Device now advertising as 'Animated Skelly(Live)' (MAC 24:F4:95:F4:CA:45, PIN 1234)", level="DEBUG")
            return True

        except Exception as e:
            log(f"Failed to enable Classic BT: {e}", level="ERROR")
            return False

    async def send_movement_command(self, command: str):
        """Send movement command to skeleton."""
        if not self.client or not self.client.is_connected:
            log("BLE not connected", level="ERROR")
            return False

        try:
            await self.client.write_gatt_char(WRITE_UUID, hx(command), response=False)
            return True
        except Exception as e:
            log(f"Movement command failed: {e}", level="ERROR")
            return False

    async def run_service(self):
        """Run the persistent BLE service."""
        log("Starting Mr. Bones BLE Service")
        log("----------------------------------------", level="DEBUG")

        if not await self.connect():
            return False

        if not await self.enable_classic_bt_mode():
            return False

        log("BLE Service running: movement control available, Classic BT audio enabled")
        log("Waiting for commands; press Ctrl+C to stop", level="DEBUG")

        self.running = True

        # Keep the service alive
        try:
            while self.running:
                if not self.client.is_connected:
                    log("BLE connection lost - attempting reconnect", level="WARNING")
                    if not await self.connect():
                        break

                await asyncio.sleep(5)  # Heartbeat check

        except KeyboardInterrupt:
            log("Shutdown signal received, stopping service")
        except Exception as e:
            log(f"Service error: {e}", level="ERROR")
        finally:
            await self.disconnect()

        return True

    async def disconnect(self):
        """Disconnect from skeleton."""
        self.running = False
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
                log("BLE disconnected", level="DEBUG")
            except Exception as e:
                log(f"Disconnect error: {e}", level="WARNING")

# Global service instance
service = SkeletonBLEService()

async def main():
    """Main service entry point."""
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        log("Shutdown signal received via system handler", level="WARNING")
        service.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    success = await service.run_service()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
