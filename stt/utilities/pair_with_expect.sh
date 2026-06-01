#!/bin/bash
# Interactive Bluetooth pairing script
# Set MAC and PIN via environment variables or pass them as arguments:
#   MAC=AA:BB:CC:DD:EE:FF PIN=0000 ./pair_with_expect.sh
# or:
#   ./pair_with_expect.sh AA:BB:CC:DD:EE:FF 0000

MAC="${1:-${MAC:-}}"
PIN="${2:-${PIN:-}}"

if [ -z "$MAC" ] || [ -z "$PIN" ]; then
    echo "Usage: MAC=<address> PIN=<pin> $0" >&2
    echo "  or:  $0 <MAC> <PIN>" >&2
    exit 1
fi

# Validate MAC address format (XX:XX:XX:XX:XX:XX)
if ! echo "$MAC" | grep -qE '^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'; then
    echo "Error: invalid MAC address format" >&2
    exit 1
fi

echo "Pairing with device using provided credentials"

expect << EOF
spawn bluetoothctl
expect "\\[bluetooth\\]#"
send "agent on\r"
expect "\\[bluetooth\\]#"
send "default-agent\r"
expect "\\[bluetooth\\]#"
send "pair $MAC\r"
expect {
    "Request PIN code" {
        send "$PIN\r"
        expect {
            "Pairing successful" {
                send "trust $MAC\r"
                expect "\\[bluetooth\\]#"
                send "connect $MAC\r"
                expect "\\[bluetooth\\]#"
                send "exit\r"
            }
            "Failed to pair" {
                send "exit\r"
                exit 1
            }
        }
    }
    "Device * not available" {
        send "exit\r"
        exit 2
    }
    "Pairing successful" {
        send "trust $MAC\r"
        expect "\\[bluetooth\\]#"
        send "connect $MAC\r"
        expect "\\[bluetooth\\]#"
        send "exit\r"
    }
}
EOF
