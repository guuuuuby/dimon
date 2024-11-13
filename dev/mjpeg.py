import argparse
import asyncio
import json
import os
import shutil
from datetime import datetime

import cv2
import mss
import numpy as np
import pyautogui
import websockets
from directory import select_directory
from filestream import handle_download_request
from pynput.keyboard import Controller, Key
from rich import print
from rich.traceback import Traceback
from send2trash import send2trash
from websockets.exceptions import ConnectionClosed
from terminal import TerminalSession

keyboard = Controller()


def get_creation_time(path: str) -> str:
    try:
        stat_info = os.stat(path)
        if hasattr(stat_info, "st_birthtime"):
            creation_time = stat_info.st_birthtime
        else:
            creation_time = stat_info.st_ctime
        creation_time_dt = datetime.fromtimestamp(creation_time)
        return creation_time_dt.isoformat()
    except Exception as e:
        return str(e)


async def fs_commands(
    ws: websockets.WebSocketClientProtocol,
    base: str,
    stream_endpoint: str,
    session_id: str,
    shell: str | None,
):
    terminal_session = None
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
                                    "createdAt": get_creation_time(f"{path}/{entry}"),
                                }
                                if os.path.isfile(f"{path}/{entry}")
                                else {
                                    "type": "folder",
                                    "name": entry,
                                    "createdAt": get_creation_time(f"{path}/{entry}"),
                                }
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

            # Handle 'download' request
            elif message["request"] == "download":
                await handle_download_request(
                    message, base, stream_endpoint, session_id
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

            # Handle 'rm' (remove file/folder) request
            elif message["request"] == "rm":
                request_id = message["requestId"]
                path = str(message["path"]).replace("root", base)

                try:
                    # Use send2trash to move the file/folder to the trash
                    send2trash(os.path.abspath(path))
                    await ws.send(
                        json.dumps(
                            {
                                "requestId": request_id,
                                "event": "rm",
                                "success": True,
                            }
                        )
                    )
                except Exception as err:
                    print(err)
                    await ws.send(
                        json.dumps(
                            {
                                "requestId": request_id,
                                "event": "rm",
                                "success": False,
                            }
                        )
                    )

            elif message["request"] == "mv":
                request_id = message["requestId"]
                source = str(message["url"]).replace("root", base)
                destination = str(message["destinationUrl"]).replace("root", base)

                try:
                    print(source, destination)
                    shutil.move(source, destination)
                    await ws.send(
                        json.dumps(
                            {
                                "requestId": request_id,
                                "event": "mv",
                                "success": True,
                            }
                        )
                    )
                except Exception as err:
                    print(err)
                    await ws.send(
                        json.dumps(
                            {
                                "requestId": request_id,
                                "event": "mv",
                                "success": False,
                            }
                        )
                    )

            elif message["request"] == "terminal":
                # Handle terminal events
                event = message.get("event", {})
                action = event.get("action")

                print(f"Received terminal action: {action}")
                if action == "open":
                    if terminal_session and terminal_session.active:
                        await terminal_session.close()

                    columns = event.get("columns", 80)
                    lines = event.get("lines", 24)

                    # Establish a new WebSocket connection for terminal
                    terminal_uri = f"{stream_endpoint}/{session_id}?channel=terminal"

                    try:
                        terminal_ws = await websockets.connect(terminal_uri)
                        print(f"Connected to terminal WebSocket at {terminal_uri}")
                        terminal_session = TerminalSession(terminal_ws, base, shell)
                        await terminal_session.start(columns, lines)

                    except Exception as e:
                        print(f"Failed to connect to terminal WebSocket: {e}")

                elif action == "sync":
                    if terminal_session and terminal_session.active:
                        columns = event.get("columns")
                        lines = event.get("lines")
                        if columns and lines:
                            await terminal_session.set_terminal_size(columns, lines)

                elif action == "close":
                    if terminal_session and terminal_session.active:
                        try:
                            await terminal_session.close()
                        except Exception as e:
                            print(f"Failed to close terminal session: {e}")
                            assert e
                        terminal_session = None

    except Exception as err:
        assert err
        print(Traceback(show_locals=True))
        if terminal_session and terminal_session.active:
            await terminal_session.close()


async def stream(session_id: str, stream_endpoint: str):
    uri = f"{stream_endpoint}/{session_id}"  # WebSocket server URI
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

                # Control frame rate (e.g., 60 FPS)
                await asyncio.sleep(1 / 60)


async def main(
    accept_endpoint: str, stream_endpoint: str, admin_endpoint: str, shell: str | None, folder: str | None
):
    if folder is None:
        print("Виберіть папку, до якої буде надано повний доступ")

    base = folder or select_directory()
    websocket_accept = await websockets.connect(accept_endpoint)
    message = await websocket_accept.recv()

    data = json.loads(message)
    session_id = data["id"]
    print(
        f"Посилання для дистанційного керування вашим комп'ютером: {admin_endpoint}/#/{session_id}"
    )

    # Create tasks for handling file system commands and streaming
    task1 = asyncio.create_task(
        fs_commands(websocket_accept, base, stream_endpoint, session_id, shell)
    )
    task2 = asyncio.create_task(stream(session_id, stream_endpoint))

    await asyncio.gather(task1, task2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="кошки")

    parser.add_argument(
        "--http",
        action="store_true",
        help="Використовувати ws замість wss при підключенні",
    )
    parser.add_argument(
        "--shell",
        default=None,
        help="Власна команда для запуску терміналу",
    )

    # Default WebSocket accept and stream endpoints
    parser.add_argument(
        "--accept",
        default="guby.gay/accept",
        help="эндпоинт для получения команд (дефолт: guby.gay/accept)",
    )
    parser.add_argument(
        "--stream",
        default="guby.gay/live",
        help="эндпоинт для стриминга (дефолт: guby.gay/live)",
    )
    parser.add_argument(
        "--admin",
        default="https://guby.gay",
        help="урл админки (вместе со схемой) (дефолт: https://guby.gay)",
    )
    
    parser.add_argument("--folder", default=None, help="m")

    args = parser.parse_args()

    protocol = "ws" if args.http else "wss"

    asyncio.run(
        main(
            f"{protocol}://{args.accept}",
            f"{protocol}://{args.stream}",
            args.admin,
            args.shell,
            args.folder
        )
    )
