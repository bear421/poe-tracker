import ctypes
import threading

# Constants for Windows API
WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200

def block_input(state):
    """Enable or disable user input (mouse and keyboard)."""
    ctypes.windll.user32.BlockInput(state)

# Thread to manage the lock
def lock_mouse():
    """Lock mouse and keyboard input."""
    block_input(True)
    handle = None
    return handle

def unlock_mouse(handle):
    """Unlock mouse and keyboard input."""
    block_input(False)

# Usage example for testing
if __name__ == "__main__":
    print("Locking mouse and keyboard...")
    handle = lock_mouse()
    try:
        import time
        time.sleep(5)  # Simulate work while input is locked
    finally:
        print("Unlocking mouse and keyboard...")
        unlock_mouse(handle)
