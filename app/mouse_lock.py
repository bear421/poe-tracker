import ctypes
import threading
from pynput import mouse

# Flag to control blocking
block_mouse = True

def _on_move(*args):
    if block_mouse:
        return False  # Suppress the mouse movement

def block_mouse_movement():
    global block_mouse
    block_mouse = True
    listener = mouse.Listener(on_move=_on_move)
    listener.start()
    return listener

def unblock_mouse_movement(listener):
    if not listener: return

    global block_mouse
    block_mouse = False
    if listener is not None:
        listener.stop()

def block_input(state):
    """Enable or disable user input (mouse and keyboard)."""
    ctypes.windll.user32.BlockInput(state)

# Thread to manage the lock
def lock_input():
    """Lock mouse and keyboard input."""
    block_input(True)
    handle = "<dummy-handle>"
    return handle

def unlock_input(handle):
    """Unlock mouse and keyboard input."""
    if handle:
        block_input(False)

# Usage example for testing
if __name__ == "__main__":
    print("Locking mouse and keyboard...")
    handle = lock_input()
    try:
        import time
        time.sleep(5)  # Simulate work while input is locked
    finally:
        print("Unlocking mouse and keyboard...")
        unlock_input(handle)
