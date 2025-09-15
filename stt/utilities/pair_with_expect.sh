#!/bin/bash
# Interactive Bluetooth pairing script

MAC="24:F4:95:F4:CA:45"
PIN="1234"

echo "Pairing with $MAC using PIN $PIN"

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