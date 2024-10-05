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
    BIF_RETURNONLYFSDIRS = 0x00000001
    BIF_NEWDIALOGSTYLE = 0x00000040

    class BROWSEINFO(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", wintypes.HWND),
            ("pidlRoot", wintypes.LPCITEMIDLIST),
            ("pszDisplayName", wintypes.LPWSTR),
            ("lpszTitle", wintypes.LPCWSTR),
            ("ulFlags", ctypes.c_uint),
            ("lpfn", wintypes.LPARAM),
            ("lParam", wintypes.LPARAM),
            ("iImage", ctypes.c_int),
        ]

    SHBrowseForFolder = ctypes.windll.shell32.SHBrowseForFolderW
    SHGetPathFromIDList = ctypes.windll.shell32.SHGetPathFromIDListW

    def browse_folder():
        buffer = ctypes.create_unicode_buffer(1024)
        browse_info = BROWSEINFO()
        browse_info.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE
        item_list = SHBrowseForFolder(ctypes.byref(browse_info))
        if SHGetPathFromIDList(item_list, buffer):
            return buffer.value
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
