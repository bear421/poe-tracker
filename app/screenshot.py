import sys
from PIL import ImageGrab
from datetime import datetime
import os
import pygetwindow as gw
import psutil
from typing import Optional
from PIL import Image
from poe_bridge import find_poe_window

try:
    import win32gui
    import win32con
    SUPPORTS_WIN32 = True
except ImportError:
    SUPPORTS_WIN32 = False

cached_window = None

def get_client_area(window: gw.Window):
    hwnd = window._hWnd
    client_rect = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
    right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
    return (left, top, right, bottom)

def capture_window(window: gw.Window) -> Optional[Image.Image]:
    try:
        # Get the region for the window
        if SUPPORTS_WIN32:
            if win32gui.GetForegroundWindow() != window._hWnd:
                print("[Info] Window is not in foreground, no screenshot taken")
                return None

            # focusing window is too slow and not really desirable
            # win32gui.ShowWindow(window._hWnd, win32con.SW_RESTORE)
            # win32gui.SetForegroundWindow(window._hWnd)
            region = get_client_area(window)
        else:
            region = (window.left, window.top, window.right, window.bottom)

        return ImageGrab.grab(bbox=region)
    except Exception as e:
        print(f"[Error] Window capture failed: {e}")
        return None
