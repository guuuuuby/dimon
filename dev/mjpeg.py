import asyncio
import websockets.asyncio.client as websockets
import mss
import numpy as np
import cv2
import json

async def capture_and_send():
    websocket_accept = await websockets.connect('ws://localhost:8000/accept')
    message = await websocket_accept.recv()
    data = json.loads(message)
    session_id = data['id']
    print(f"Session ID: {session_id}")

    uri = f'ws://localhost:8001/{session_id}'  # WebSocket server URI
    async with websockets.connect(uri, additional_headers={"X-Will-Stream": True}) as websocket:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Capture the first monitor
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]  # JPEG quality (0 to 100)

            while True:
                # Capture the screen
                img = sct.grab(monitor)
                frame = np.array(img)

                # Convert BGRA to BGR (opencv uses BGR format)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # Encode frame as JPEG
                result, encoded_img = cv2.imencode('.jpg', frame, encode_param)
                if not result:
                    continue

                # Convert to bytes
                img_bytes = encoded_img.tobytes()

                # Send over WebSocket
                try:
                    await websocket.send(img_bytes)
                except websockets.ConnectionClosed:
                    print("Connection closed")
                    websocket = await websockets.connect(uri)

                # Control frame rate (e.g., 15 FPS)
                await asyncio.sleep(1/60)

asyncio.get_event_loop().run_until_complete(capture_and_send())
