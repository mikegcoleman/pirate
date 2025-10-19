#!/usr/bin/env python3
"""
Script to convert remaining print statements to structured logging in client.py
This helps automate the conversion process for the large client.py file.
"""

import re

def convert_print_to_log(line):
    """Convert a print statement to appropriate logger call."""
    # Skip lines that are already using logger
    if 'logger.' in line:
        return line

    # Match print statements
    print_match = re.match(r'(\s*)print\((.*)\)', line)
    if not print_match:
        return line

    indent = print_match.group(1)
    content = print_match.group(2)

    # Determine log level based on emoji/content
    if any(emoji in content for emoji in ['❌', '💥', 'ERROR', 'Failed', 'failed']):
        level = 'error'
    elif any(emoji in content for emoji in ['⚠️', 'WARNING', 'Warning']):
        level = 'warn'
    elif any(emoji in content for emoji in ['🔍', '📊', '📡', '🎵', 'DEBUG']):
        level = 'debug'
    else:
        level = 'info'

    # Extract f-string or regular string
    # Simple conversion: just use the content as-is for now
    # Keep user-facing messages as print + log
    if any(face in content for face in ['🏴‍☠️', '👋', '💡']):
        return f"{indent}print({content})\n{indent}logger.{level}({content})"

    return f"{indent}logger.{level}({content})"

# Read client.py
with open('/mnt/c/Users/msmik/Documents/src/pirate/stt/client.py', 'r') as f:
    lines = f.readlines()

# Convert lines
converted = [convert_print_to_log(line.rstrip('\n')) + '\n' for line in lines]

# Write back
with open('/mnt/c/Users/msmik/Documents/src/pirate/stt/client.py', 'w') as f:
    f.writelines(converted)

print("✅ Conversion complete!")
