import platform
import websockets

if platform.system() == "Windows":
    import winpty  # noqa
else:
    import pty

import asyncio
import shutil
import os
from websockets.exceptions import ConnectionClosed
from rich import print
from rich.traceback import Traceback


def select_shell():
    """Select the appropriate shell based on the operating system."""
    system = platform.system()
    if system == "Windows":
        return "cmd.exe"
    elif system == "Darwin":  # macOS
        return "zsh" if shutil.which("zsh") else "bash"
    else:  # Assume Linux
        return "bash"


class TerminalSession:
    def __init__(self, ws: websockets.WebSocketClientProtocol):
        self.ws = ws
        self.process = None
        self.read_task = None
        self.write_task = None
        self.active = False
        self.master_fd = None  # Add this attribute to store master_fd

    async def start(self, columns: int, lines: int):
        """Start the shell subprocess within a PTY and initiate data forwarding."""
        shell = select_shell()
        print(f"Starting shell: {shell}")

        system = platform.system()
        if system == 'Windows':
            # Existing Windows implementation...
            self.process = winpty.PtyProcess.spawn(shell)
            self.active = True
            self.read_task = asyncio.create_task(self.read_from_shell_windows())
            self.write_task = asyncio.create_task(self.write_to_shell_windows())
        else:
            # Initialize PTY on Unix-like systems
            self.master_fd, slave_fd = pty.openpty()
            self.process = await asyncio.create_subprocess_exec(
                shell,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid
            )
            self.active = True

            # Start reading and writing
            self.read_task = asyncio.create_task(self.read_from_shell_unix(self.master_fd))
            self.write_task = asyncio.create_task(self.write_to_shell_unix(self.master_fd))

            await self.set_terminal_size(columns, lines)

    async def set_terminal_size(self, columns: int, lines: int):
        """Set the terminal size of the subprocess."""
        system = platform.system()
        if system == 'Windows':
            # pywinpty does not natively support resizing in the same way as Unix PTYs.
            # Advanced implementations may require additional handling.
            # Placeholder for potential future enhancements.
            pass
        else:
            # Use ioctl to set terminal size on Unix-like systems
            import fcntl
            import struct
            import termios

            try:
                if self.master_fd is not None:
                    # Pack the terminal size into the required format
                    size = struct.pack("HHHH", lines, columns, 0, 0)
                    fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, size)
                else:
                    print("master_fd is not set. Cannot set terminal size.")
            except Exception as e:
                print(f"Error setting terminal size: {e}")

    async def read_from_shell_unix(self, master_fd: int):
        """Read output from the shell PTY on Unix-like systems and send to WebSocket."""
        try:
            loop = asyncio.get_running_loop()
            while True:
                # Read asynchronously from the PTY
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                if not data:
                    break
                await self.ws.send(data)
                # print(data.decode("utf-8", errors="ignore"), end="")
        except Exception as e:
            assert e
            print(Traceback(show_locals=True))
        finally:
            await self.close()

    async def write_to_shell_unix(self, master_fd: int):
        """Receive data from the WebSocket and write to the shell PTY on Unix-like systems."""
        try:
            async for message in self.ws:
                if isinstance(message, bytes):
                    data = message
                else:
                    data = message.encode("utf-8", errors="ignore")
                os.write(master_fd, data)
        except ConnectionClosed:
            print("WebSocket connection closed.")
        except Exception as e:
            assert e
            print(Traceback(show_locals=True))
        finally:
            await self.close()

    async def read_from_shell_windows(self):
        """Read output from the shell PTY on Windows and send to WebSocket."""
        try:
            while True:
                data = self.process.read(1024)
                if not data:
                    break
                await self.ws.send(data)
        except Exception as e:
            assert e
            print(Traceback(show_locals=True))
        finally:
            await self.close()

    async def write_to_shell_windows(self):
        """Receive data from the WebSocket and write to the shell PTY on Windows."""
        try:
            async for message in self.ws:
                if isinstance(message, bytes):
                    data = message
                else:
                    data = message.encode("utf-8", errors="ignore")
                self.process.write(data)
        except ConnectionClosed:
            print("WebSocket connection closed.")
        except Exception as e:
            assert e
            print(Traceback(show_locals=True))
        finally:
            await self.close()

    async def close(self):
        """Terminate the shell subprocess and cancel tasks."""
        if self.active:
            self.active = False
            try:
                self.process.terminate()
            except Exception as e:
                assert e
                print(Traceback(show_locals=True))

            if self.read_task:
                self.read_task.cancel()
            if self.write_task:
                self.write_task.cancel()
            print("Terminal session closed.")
