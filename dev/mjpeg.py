import asyncio
import websockets.asyncio.client as websockets
import mss
import numpy as np
import cv2
import os
import json


async def fs_commands(ws: websockets.ClientConnection):
    base = f"/Application"

    try:
        while True:
            message = json.loads(await ws.recv())
            if message["request"] == "ls":
                request_id = message["requestId"]
                path = str(message["path"]).replace("root", base)
                try:
                    content = sorted(
                        [
                            (
                                {
                                    "type": "file",
                                    "name": entry,
                                    "bytes": os.path.getsize(f"{path}/{entry}"),
                                }
                                if os.path.isfile(f"{path}/{entry}")
                                else {"type": "folder", "name": entry}
                            )
                            for entry in os.listdir(path)
                        ],
                        key=lambda x: (x["type"] == "file", x["name"]),
                    )
                    await ws.send(
                        json.dumps(
                            {
                                "requestId": request_id,
                                "event": "ls",
                                "path": message["path"],
                                "contents": content,
                            }
                        )
                    )
                except Exception as err:
                    print(err)
                    await ws.send(
                        json.dumps(
                            {
                                "requestId": request_id,
                                "event": "ls",
                                "path": message["path"],
                                "contents": [],
                            }
                        )
                    )
    except Exception as err:
        print(err)
        await ws.close()


async def stream(sessionId: str):
    uri = f"ws://localhost:8001/{sessionId}"  # WebSocket server URI
    async with websockets.connect(
        uri, additional_headers={"X-Will-Stream": True}
    ) as websocket:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Capture the first monitor
            encode_param = [
                int(cv2.IMWRITE_JPEG_QUALITY),
                70,
            ]  # JPEG quality (0 to 100)

            while True:
                # Capture the screen
                img = sct.grab(monitor)
                frame = np.array(img)

                # Convert BGRA to BGR (opencv uses BGR format)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # Encode frame as JPEG
                result, encoded_img = cv2.imencode(".jpg", frame, encode_param)
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
                await asyncio.sleep(1 / 60)


async def main():
    websocket_accept = await websockets.connect("ws://localhost:8000/accept")
    message = await websocket_accept.recv()
    data = json.loads(message)
    session_id = data["id"]
    print(f"Session ID: {session_id}")

    task1 = asyncio.create_task(fs_commands(websocket_accept))
    task2 = asyncio.create_task(stream(session_id))

    await asyncio.gather(task1, task2)


asyncio.run(main())
