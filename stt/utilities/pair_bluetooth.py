#!/usr/bin/env python3
"""
Bluetooth Pairing Utility
Handles interactive pairing with PIN code for Bluetooth devices.
"""

import pexpect
import sys
import time

def pair_device(mac_address, pin_code="1234", timeout=30):
    """Pair with a Bluetooth device using PIN code."""
    print(f"🔵 Attempting to pair with {mac_address} using PIN: {pin_code}")
    
    try:
        # Start bluetoothctl
        child = pexpect.spawn('bluetoothctl', timeout=timeout)
        child.expect(r'\[bluetooth\]#')
        
        # Enable agent
        child.sendline('agent on')
        child.expect(r'\[bluetooth\]#')
        
        # Set as default agent
        child.sendline('default-agent')
        child.expect(r'\[bluetooth\]#')
        
        # Enable pairable mode
        child.sendline('pairable on')
        child.expect(r'\[bluetooth\]#')
        
        # Start pairing
        child.sendline(f'pair {mac_address}')
        
        # Handle different possible responses
        index = child.expect([
            'Request PIN code',
            'Device .* not available',
            'Pairing successful',
            'Failed to pair',
            pexpect.TIMEOUT
        ], timeout=20)
        
        if index == 0:  # PIN code requested
            print(f"🔑 Entering PIN code: {pin_code}")
            child.sendline(pin_code)
            
            # Wait for pairing result
            index = child.expect([
                'Pairing successful',
                'Failed to pair',
                pexpect.TIMEOUT
            ], timeout=15)
            
            if index == 0:
                print("✅ Pairing successful!")
                
                # Trust the device
                child.sendline(f'trust {mac_address}')
                child.expect(r'\[bluetooth\]#')
                
                # Try to connect
                child.sendline(f'connect {mac_address}')
                
                index = child.expect([
                    'Connection successful',
                    'Failed to connect',
                    pexpect.TIMEOUT
                ], timeout=10)
                
                if index == 0:
                    print("✅ Connected successfully!")
                    return True
                else:
                    print("⚠️ Paired but connection failed")
                    return True  # Still consider it success if paired
            else:
                print("❌ Pairing failed after PIN entry")
                return False
                
        elif index == 1:  # Device not available
            print("❌ Device not available - make sure it's in pairing mode")
            return False
            
        elif index == 2:  # Already paired
            print("✅ Device already paired, trying to connect...")
            child.sendline(f'connect {mac_address}')
            
            index = child.expect([
                'Connection successful',
                'Failed to connect',
                pexpect.TIMEOUT
            ], timeout=10)
            
            if index == 0:
                print("✅ Connected successfully!")
                return True
            else:
                print("⚠️ Paired but connection failed")
                return True
                
        else:  # Failed or timeout
            print("❌ Pairing failed or timed out")
            return False
            
    except Exception as e:
        print(f"❌ Error during pairing: {e}")
        return False
    
    finally:
        try:
            child.sendline('exit')
            child.close()
        except:
            pass

def main():
    if len(sys.argv) < 2:
        print("Usage: python pair_bluetooth.py <MAC_ADDRESS> [PIN_CODE]")
        print("Example: python pair_bluetooth.py 24:F4:95:F4:CA:45 1234")
        sys.exit(1)
    
    mac_address = sys.argv[1]
    pin_code = sys.argv[2] if len(sys.argv) > 2 else "1234"
    
    success = pair_device(mac_address, pin_code)
    
    if success:
        print(f"\n✅ Successfully paired with {mac_address}")
        print(f"💡 Add this to your .env file:")
        print(f"   BLUETOOTH_SPEAKER={mac_address}")
    else:
        print(f"\n❌ Failed to pair with {mac_address}")
        print("💡 Make sure the device is in pairing mode and try again")
        sys.exit(1)

if __name__ == "__main__":
    main()