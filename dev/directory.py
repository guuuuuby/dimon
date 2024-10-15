import ctypes
import platform
import subprocess
from ctypes import wintypes


def select_directory():
    system = platform.system()

    if system == "Windows":
        return windows_directory_dialog()
    elif system == "Darwin":  # macOS
        return macos_directory_dialog()
    elif system == "Linux":
        return linux_directory_dialog()
    else:
        raise NotImplementedError(f"Unsupported operating system: {system}")


### Windows - Using ctypes to access Windows API (WinAPI) ###
def windows_directory_dialog():
    import tkinter as tk
    from tkinter import filedialog

    def browse_folder():
        root = tk.Tk()
        root.withdraw()  # Hide the root window as we don't need it

        # Open the folder selection dialog
        folder_selected = filedialog.askdirectory(title="Select a folder")

        # Return the selected directory, or None if the user cancels
        if folder_selected:
            return folder_selected
        else:
            return None

    return browse_folder()


### macOS - Using AppleScript via osascript ###
def macos_directory_dialog():
    script = """
    set dir_path to POSIX path of (choose folder with prompt "Select a directory")
    return dir_path
    """
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip()


### Linux - Using zenity or kdialog ###
def linux_directory_dialog():
    # Try zenity first
    try:
        result = subprocess.run(
            ["zenity", "--file-selection", "--directory"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    # Fallback to kdialog if zenity is not available
    try:
        result = subprocess.run(
            ["kdialog", "--getexistingdirectory"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    raise RuntimeError(
        "No supported directory selection dialog found on this Linux system."
    )
