import asyncio
import json
import os

import cv2
import mss
import numpy as np
import pyautogui
import websockets.asyncio.client as websockets
from directory import select_directory
from pynput.keyboard import Controller, Key
from rich import print
from rich.traceback import Traceback
from websockets.exceptions import ConnectionClosed

keyboard = Controller()


async def fs_commands(ws: websockets.ClientConnection):
    base = select_directory()

    try:
        while True:
            message = json.loads(await ws.recv())

            # Handle 'ls' request
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

            # Handle 'mouseClick' request
            elif message["request"] == "mouseClick":
                point = message["point"]

                # Get the screen size
                screen_width, screen_height = pyautogui.size()

                # Normalize the x and y coordinates
                x = point["x"] * screen_width
                y = point["y"] * screen_height

                # Perform the mouse click at the calculated position
                pyautogui.click(
                    x,
                    y,
                    button=(
                        pyautogui.PRIMARY if not message["aux"] else pyautogui.SECONDARY
                    ),
                )

            elif message["request"] == "keypress":
                event = message["event"]
                action = event["action"]
                nya = (
                    event["keyCode"]
                    .replace("Right", "_r")
                    .replace("Left", "_l")
                    .replace("Meta", "cmd")
                    .replace("Arrow_r", "right")
                    .replace("Arrow_l", "left")
                    .replace("Arrow", "")
                    .replace("Caps", "caps_")
                    .lower()
                )
                key = getattr(Key, nya, event["key"])

                modifiers = event["modifiers"]

                try:
                    # Apply modifiers
                    for mod in modifiers:
                        if mod == "shift":
                            keyboard.press(Key.shift)
                        elif mod == "control":
                            keyboard.press(Key.ctrl)
                        elif mod == "meta":
                            keyboard.press(Key.cmd)
                        elif mod == "alt":
                            keyboard.press(Key.alt)

                    # Perform key press or release action
                    if action == "down":
                        keyboard.press(key)
                    elif action == "up":
                        keyboard.release(key)

                    # Release modifiers
                    for mod in modifiers:
                        if mod == "shift":
                            keyboard.release(Key.shift)
                        elif mod == "control":
                            keyboard.release(Key.ctrl)
                        elif mod == "meta":
                            keyboard.release(Key.cmd)
                        elif mod == "alt":
                            keyboard.release(Key.alt)

                except Exception as e:
                    assert e
                    print(Traceback(show_locals=True))
                    continue

    except Exception as err:
        assert err
        print(Traceback(show_locals=True))
        await ws.close()


async def stream(session_id: str):
    uri = f"wss://guby.gay/live/{session_id}"  # WebSocket server URI
    async with websockets.connect(uri) as websocket:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Capture the first monitor
            encode_param = [
                int(cv2.IMWRITE_JPEG_QUALITY),
                30,
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
                except ConnectionClosed:
                    print("Connection closed")
                    websocket = await websockets.connect(uri)

                # Control frame rate (e.g., 15 FPS)
                await asyncio.sleep(1 / 60)


async def main():
    websocket_accept = await websockets.connect("wss://guby.gay/accept")
    message = await websocket_accept.recv()
    data = json.loads(message)
    session_id = data["id"]
    print(f"Session ID: {session_id}")

    # Create two tasks: one for handling file system commands and mouse clicks, and one for streaming
    task1 = asyncio.create_task(fs_commands(websocket_accept))
    task2 = asyncio.create_task(stream(session_id))

    await asyncio.gather(task1, task2)


asyncio.run(main())
