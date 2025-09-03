#!/usr/bin/env python3
"""
Test script for WebSocket audio chunk delivery debugging.
Bypasses audio input to focus on the WebSocket message transmission issue.
"""

import asyncio
import socketio
import os
import signal
import sys
from dotenv import load_dotenv
import uuid

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8080")
print(f"🌐 API URL: {API_URL}")

# Convert HTTP to WebSocket URL if needed
if API_URL.startswith("http://"):
    WS_URL = API_URL.replace("http://", "ws://")
elif API_URL.startswith("https://"):
    WS_URL = API_URL.replace("https://", "wss://")
else:
    WS_URL = API_URL

print(f"📡 WebSocket URL: {WS_URL}")

class WebSocketChunkTest:
    def __init__(self):
        self.sio = socketio.AsyncClient(
            logger=True, 
            engineio_logger=False,
            # Increase client-side buffer limits
            request_timeout=60
        )
        self.current_request_id = None
        self.audio_chunks_received = []
        self.test_chunks_received = []
        self.simple_test_chunks_received = []
        # For handling chunked audio reassembly
        self.audio_chunk_parts = {}  # {sequence: {parts: [], total_parts: int}}
        
        self.setup_handlers()
    
    def setup_handlers(self):
        @self.sio.event
        async def connect():
            print("🔌 CLIENT: Connected to WebSocket server")
            
        @self.sio.event  
        async def disconnect():
            print("🔌 CLIENT: Disconnected from WebSocket server")
            
        @self.sio.event
        async def text_response(data):
            try:
                print(f"💬 CLIENT: Got text_response: {data.get('text', 'No text')}")
            except Exception as e:
                print(f"❌ CLIENT: Error in text_response handler: {e}")
        
        @self.sio.event
        async def audio_start(data):
            try:
                print(f"🎵 CLIENT: Got audio_start: {data}")
            except Exception as e:
                print(f"❌ CLIENT: Error in audio_start handler: {e}")
        
        @self.sio.event
        async def chunk_data(data):
            try:
                print(f"🔊 CLIENT: chunk_data received! Type: {type(data)}")
                if isinstance(data, dict):
                    sequence = data.get('sequence', 'unknown')
                    audio_b64 = data.get('data', '')
                    request_id = data.get('request_id', 'unknown')
                    is_complete = data.get('is_complete', True)
                    part = data.get('part', 0)
                    total_parts = data.get('total_parts', 1)
                    
                    print(f"🔊 CLIENT: Chunk - seq={sequence}, part={part}/{total_parts}, b64_len={len(audio_b64)}, complete={is_complete}, req_id={request_id}")
                    
                    # Handle chunked audio reassembly
                    if total_parts > 1:
                        # Multi-part chunk - reassemble
                        if sequence not in self.audio_chunk_parts:
                            self.audio_chunk_parts[sequence] = {
                                'parts': [None] * total_parts,
                                'total_parts': total_parts,
                                'request_id': request_id
                            }
                        
                        self.audio_chunk_parts[sequence]['parts'][part] = audio_b64
                        
                        # Check if all parts received
                        if all(p is not None for p in self.audio_chunk_parts[sequence]['parts']):
                            # Reassemble complete audio chunk
                            complete_audio = ''.join(self.audio_chunk_parts[sequence]['parts'])
                            complete_chunk = {
                                'sequence': sequence,
                                'data': complete_audio,
                                'request_id': request_id,
                                'reassembled': True
                            }
                            self.audio_chunks_received.append(complete_chunk)
                            print(f"✅ CLIENT: Reassembled complete chunk seq={sequence}, total_len={len(complete_audio)}")
                            del self.audio_chunk_parts[sequence]
                    else:
                        # Single part chunk
                        self.audio_chunks_received.append(data)
                        print(f"✅ CLIENT: Single chunk received seq={sequence}")
                        
                else:
                    print(f"🔊 CLIENT: Unexpected chunk_data format: {data}")
            except Exception as e:
                print(f"❌ CLIENT: Error in chunk_data handler: {e}")
        
        @self.sio.event
        async def simple_test(data):
            try:
                print(f"✅ CLIENT: simple_test received! Data: {data}")
                self.simple_test_chunks_received.append(data)
            except Exception as e:
                print(f"❌ CLIENT: Error in simple_test handler: {e}")
                
        @self.sio.event
        async def test_event(data):
            try:
                print(f"🧪 CLIENT: test_event received! Data: {data}")
                self.test_chunks_received.append(data)
            except Exception as e:
                print(f"❌ CLIENT: Error in test_event handler: {e}")
        
        @self.sio.event
        async def audio_complete(data):
            try:
                print(f"🏁 CLIENT: Got audio_complete: {data}")
                print(f"📊 CLIENT: Final stats:")
                print(f"   - Audio chunks received: {len(self.audio_chunks_received)}")
                print(f"   - Test events received: {len(self.test_chunks_received)}")  
                print(f"   - Simple test chunks received: {len(self.simple_test_chunks_received)}")
                
                if len(self.audio_chunks_received) == 0:
                    print("❌ CLIENT: NO AUDIO CHUNKS WERE RECEIVED!")
                    if len(self.test_chunks_received) > 0:
                        print("✅ CLIENT: But test events were received - this confirms payload size issue")
                    if len(self.simple_test_chunks_received) > 0:
                        print("✅ CLIENT: Simple test chunks were received - confirms issue is with large payloads")
                        
            except Exception as e:
                print(f"❌ CLIENT: Error in audio_complete handler: {e}")
        
        # Catch-all event handler for debugging
        @self.sio.event
        async def generic_event_handler(event_name, *args):
            if event_name not in ['connect', 'disconnect', 'text_response', 'audio_start', 'chunk_data', 'simple_test', 'test_event', 'audio_complete']:
                print(f"🔍 CLIENT: Generic handler - event='{event_name}', args={len(args) if args else 0}")
                if args:
                    print(f"🔍 CLIENT: Args: {args}")
    
    async def run_test(self):
        print("🚀 CLIENT: Starting WebSocket chunk test...")
        
        try:
            # Connect to WebSocket server
            print("🔌 CLIENT: Connecting to WebSocket server...")
            await self.sio.connect(WS_URL)
            
            # Wait for connection to stabilize
            await asyncio.sleep(1)
            
            # Send a test message to trigger audio generation
            print("📤 CLIENT: Sending test message...")
            test_message = "Hello Mr. Bones, tell me about treasure!"
            
            await self.sio.emit('chat', {
                'message': test_message,
                'request_id': str(uuid.uuid4())
            })
            
            # Wait for response processing
            print("⏳ CLIENT: Waiting for response...")
            await asyncio.sleep(5)  # Wait for initial events
            
            # Check if we got anything
            print(f"📊 CLIENT: Midway check - chunks: {len(self.audio_chunks_received)}, tests: {len(self.test_chunks_received)}")
            
            await asyncio.sleep(5)  # Wait a bit more
            
            print("📊 CLIENT: Test completed. Final results:")
            print(f"   - Audio chunks received: {len(self.audio_chunks_received)}")
            print(f"   - Test events received: {len(self.test_chunks_received)}")
            print(f"   - Simple test chunks received: {len(self.simple_test_chunks_received)}")
            
        except Exception as e:
            print(f"❌ CLIENT: Error during test: {e}")
        finally:
            await self.sio.disconnect()

def signal_handler(signum, frame):
    print("\\n👋 CLIENT: Received interrupt signal")
    os._exit(0)

async def main():
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🧪 WebSocket Chunk Test Starting")
    print("=" * 50)
    
    test_client = WebSocketChunkTest()
    await test_client.run_test()

if __name__ == "__main__":
    asyncio.run(main())