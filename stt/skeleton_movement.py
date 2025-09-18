#!/usr/bin/env python3
"""
Mr. Bones Skeleton Movement Controller
Provides BLE movement control for the Animated Skelly device during speech.
"""

import asyncio
import random
import time
from typing import Optional, List
import logging

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("Warning: bleak not installed. Install with: pip install bleak>=1.1.0")
    BleakClient = None
    BleakScanner = None

# BLE Configuration
SKELETON_NAME = "Animated Skelly"
SKELETON_MAC = "24:F4:95:CA:21:91"  # Note: Different from Bluetooth speaker!
WRITE_UUID = "0000ae01-0000-1000-8000-00805f9b34fb"  # AE01 (write)
NOTIFY_UUID = "0000ae02-0000-1000-8000-00805f9b34fb"  # AE02 (notify)
AUTH_COMMAND = "02 70 61 73 73"  # 0x02 + ASCII "pass"

# Movement Commands (15-20 second sequences each)
MOVEMENT_COMMANDS = {
    "Head only": "aaca0100000000000086",
    "Torso only": "aaca040000000000004f", 
    "Arm only": "aaca02000000000000c1",
    "Head + Torso": "aaca0500000000000072",
    "Head + Arm": "aaca030000000000000c",
    "Torso + Arm": "aaca0600000000000035",
    "All (Head + Torso + Arm)": "aacaff000000000000bd"
}

# Weighted random selection (favor single movements over combinations)
MOVEMENT_WEIGHTS = {
    "Head only": 25,
    "Torso only": 20, 
    "Arm only": 25,
    "Head + Torso": 10,
    "Head + Arm": 10,
    "Torso + Arm": 5,
    "All (Head + Torso + Arm)": 5
}

class SkeletonController:
    """Controls Mr. Bones skeleton movements via BLE."""
    
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.connected = False
        self.last_movement_time = 0
        self.current_movement = None
        self.logger = logging.getLogger(__name__)
        
    def hex_to_bytes(self, hex_string: str) -> bytes:
        """Convert hex string to bytes."""
        return bytes.fromhex(''.join(hex_string.split()))
    
    def on_notify(self, sender, data: bytearray):
        """Handle BLE notifications from skeleton."""
        self.logger.debug(f"Skeleton notify: {data.hex()}")
    
    async def connect(self) -> bool:
        """
        Connect to the skeleton BLE device.
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        if not BleakClient:
            print("❌ Bleak not available - skeleton movement disabled")
            return False
            
        try:
            print("🔍 Scanning for Mr. Bones skeleton...")
            
            # Scan for device
            devices = await BleakScanner.discover(timeout=8.0)
            skeleton_device = None
            
            for device in devices:
                if device.name and SKELETON_NAME.lower() in device.name.lower():
                    skeleton_device = device
                    break
                # Also try MAC address if name doesn't match
                if device.address and SKELETON_MAC.lower() in device.address.lower():
                    skeleton_device = device
                    break
            
            if not skeleton_device:
                print(f"❌ Skeleton '{SKELETON_NAME}' not found")
                return False
            
            print(f"🤖 Connecting to {skeleton_device.name} ({skeleton_device.address})...")
            
            # Connect and authenticate
            self.client = BleakClient(skeleton_device)
            await self.client.connect()
            await self.client.start_notify(NOTIFY_UUID, self.on_notify)
            
            # Authenticate with skeleton
            print("🔐 Authenticating with skeleton...")
            await self.client.write_gatt_char(
                WRITE_UUID, 
                self.hex_to_bytes(AUTH_COMMAND), 
                response=False
            )
            await asyncio.sleep(0.5)
            
            self.connected = True
            print("✅ Mr. Bones skeleton connected and ready!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to skeleton: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from skeleton."""
        if self.client and self.connected:
            try:
                await self.client.disconnect()
                print("🔌 Disconnected from skeleton")
            except Exception as e:
                print(f"⚠️ Error disconnecting from skeleton: {e}")
        
        self.connected = False
        self.client = None
    
    async def send_movement_command(self, movement_name: str) -> bool:
        """
        Send a movement command to the skeleton.
        
        Args:
            movement_name: Name of movement from MOVEMENT_COMMANDS
            
        Returns:
            bool: True if command sent successfully
        """
        if not self.connected or not self.client:
            self.logger.warning("Skeleton not connected - skipping movement")
            return False
        
        if movement_name not in MOVEMENT_COMMANDS:
            self.logger.error(f"Unknown movement: {movement_name}")
            return False
        
        try:
            command = MOVEMENT_COMMANDS[movement_name]
            await self.client.write_gatt_char(
                WRITE_UUID,
                self.hex_to_bytes(command),
                response=False
            )
            
            self.current_movement = movement_name
            self.last_movement_time = time.time()
            
            print(f"🎭 Skeleton performing: {movement_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send movement command: {e}")
            return False
    
    def get_random_movement(self) -> str:
        """
        Get a random movement with weighted selection.
        
        Returns:
            str: Random movement name
        """
        movements = list(MOVEMENT_WEIGHTS.keys())
        weights = list(MOVEMENT_WEIGHTS.values())
        return random.choices(movements, weights=weights)[0]
    
    async def trigger_speech_movement(self) -> bool:
        """
        Trigger a random movement for speech animation.
        Respects timing to avoid overwhelming the skeleton.
        
        Returns:
            bool: True if movement was triggered
        """
        if not self.connected:
            return False
        
        # Don't trigger if a movement was started recently (movements last 15-20 seconds)
        # Use configured cooldown period
        import os
        cooldown = int(os.getenv("SKELETON_MOVEMENT_COOLDOWN", "10"))
        time_since_last = time.time() - self.last_movement_time
        if time_since_last < cooldown:
            print(f"⏳ Skeleton still moving ({self.current_movement}) - skipping new movement")
            return False
        
        # Get random movement and trigger it
        movement = self.get_random_movement()
        return await self.send_movement_command(movement)
    
    async def test_all_movements(self):
        """Test all movement commands (for debugging)."""
        if not self.connected:
            print("❌ Skeleton not connected")
            return
        
        print("🧪 Testing all skeleton movements...")
        
        for movement_name in MOVEMENT_COMMANDS.keys():
            print(f"\n🎭 Testing: {movement_name}")
            await self.send_movement_command(movement_name)
            
            # Wait for movement to complete
            print("⏱️ Waiting 20 seconds for movement to complete...")
            await asyncio.sleep(20)
        
        print("✅ Movement test complete")

# Global skeleton controller instance
_skeleton_controller = None

async def get_skeleton_controller() -> SkeletonController:
    """Get or create the global skeleton controller instance."""
    global _skeleton_controller
    
    if _skeleton_controller is None:
        _skeleton_controller = SkeletonController()
        # Use existing BLE connection from service instead of creating new one
        try:
            from skeleton_ble_service import service
            if service.client and service.client.is_connected:
                _skeleton_controller.client = service.client
                _skeleton_controller.connected = True
                print("🔗 Using existing skeleton BLE connection for movement control")
            else:
                print("⚠️ No existing skeleton BLE connection - movement disabled")
        except ImportError:
            # Fallback to original connection method if service not available
            await _skeleton_controller.connect()
    
    return _skeleton_controller

async def trigger_random_movement() -> bool:
    """
    Convenience function to trigger a random skeleton movement.
    
    Returns:
        bool: True if movement was triggered successfully
    """
    controller = await get_skeleton_controller()
    return await controller.trigger_speech_movement()

async def disconnect_skeleton():
    """Disconnect from skeleton (cleanup)."""
    global _skeleton_controller
    
    if _skeleton_controller:
        await _skeleton_controller.disconnect()
        _skeleton_controller = None

async def main():
    """Test function for standalone usage."""
    print("🤖 Mr. Bones Skeleton Movement Test")
    print("=" * 40)
    
    controller = SkeletonController()
    
    try:
        if await controller.connect():
            print("\n🎯 Choose test:")
            print("1. Trigger random movement")
            print("2. Test all movements")
            print("3. Interactive movement selection")
            
            choice = input("Enter choice (1-3): ").strip()
            
            if choice == "1":
                movement = controller.get_random_movement()
                print(f"🎲 Random movement: {movement}")
                await controller.send_movement_command(movement)
                
            elif choice == "2":
                await controller.test_all_movements()
                
            elif choice == "3":
                print("\nAvailable movements:")
                movements = list(MOVEMENT_COMMANDS.keys())
                for i, movement in enumerate(movements, 1):
                    print(f"{i}. {movement}")
                
                try:
                    selection = int(input("Choose movement (1-7): ")) - 1
                    if 0 <= selection < len(movements):
                        movement = movements[selection]
                        await controller.send_movement_command(movement)
                    else:
                        print("Invalid selection")
                except ValueError:
                    print("Invalid input")
            
            # Wait a bit before disconnecting
            await asyncio.sleep(2)
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted")
    finally:
        await controller.disconnect()

if __name__ == "__main__":
    asyncio.run(main())