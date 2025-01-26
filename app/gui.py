import sys
import tkinter as tk
from tkinter import ttk
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QTabWidget
from PySide6.QtCore import Qt
from datetime import datetime, timedelta
import re
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from settings import config_manager
import math
import random
import traceback
from db import conn
from ladder_api import LadderEntry
import time
import threading
from gui_components.overview import OverviewWidget
from gui_components.maps import MapsWidget
from gui_components.stats import StatsWindow
from gui_components.debug import DebugFrame
from gui_components.config import ConfigFrame
from gui_components.encounters import EncountersWidget
import traceback
from PySide6.QtCore import qInstallMessageHandler, QtMsgType

class TrackerGUI:

    def __init__(self, capture_callback):
        self.capture_callback = capture_callback
        self.current_modifiers = set()
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self._create_gui()

    def _create_gui(self):
        app = QApplication(sys.argv)
        window = QMainWindow()
        window.setWindowTitle("PoE Tracker")
        window.setGeometry(100, 100, 1000, 600)
        layout = QVBoxLayout()
        tabs = QTabWidget()
        tabs.addTab(OverviewWidget(), "Overview")
        tabs.addTab(MapsWidget(), "Maps")
        tabs.addTab(StatsWindow(), "Stats")
        tabs.addTab(EncountersWidget(), "Encounters")
        layout.addWidget(tabs)
        widget = QWidget()
        widget.setLayout(layout)
        window.setCentralWidget(widget)
        window.show()
        #notebook.add(ConfigFrame(notebook), text="Config")
        #notebook.add(DebugFrame(notebook), text="Debug")

        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()

        sys.exit(app.exec())

    def on_press(self, key):
        try:
            # Get current hotkey config
            hotkey_config = config_manager.get("screenshot_hotkey", {})
            if not hotkey_config:
                return

            # Get keycode from the key event
            key_code = getattr(key, 'vk', None) or getattr(key, '_value_', None)
            if not key_code:
                return

            # Compare and trigger if matched
            if key_code == hotkey_config.get('key_code'):
                self.capture_callback()
        except Exception as e:
            print(f"[Error]: {str(e)}\n{traceback.format_exc()}")

    def on_key_press(self, key):
        # Don't process hotkeys if we're capturing a new one
        if hasattr(self, 'capturing_hotkey') and self.capturing_hotkey:
            return True

        # Convert key to string representation for comparison
        if hasattr(key, 'char'):
            key_str = key.char
        else:
            key_code = None
            key_str = str(key).replace('Key.', '')

        # Handle modifier keys
        if key in (keyboard.Key.ctrl, keyboard.Key.alt, keyboard.Key.shift):
            self.current_modifiers.add(key)
            return True

        # Get current config for hotkey check
        hotkey_config = config_manager.get("screenshot_hotkey", {})
        if not hotkey_config:
            return True

        # Check if current modifiers match configured modifiers
        configured_mods = set(mod.lower() for mod in hotkey_config.get('modifiers', []))
        current_mods = set(str(mod).lower().replace('key.', '') for mod in self.current_modifiers)
        
        # Check both key code and key name for compatibility
        config_key_code = hotkey_config.get('key_code')
        config_key = hotkey_config.get('key', '').lower()

        print(f"try match: {key_code} == {config_key_code} or {key_str} == {config_key}")
        if (current_mods == configured_mods and 
            (key_code == config_key_code or key_str.lower() == config_key)):
            self.capture_callback()
        return True

    def on_key_release(self, key):
        if key in (keyboard.Key.ctrl, keyboard.Key.alt, keyboard.Key.shift):
            self.current_modifiers.discard(key)
        return True 

    def run(self):
        #sys.exit(self.app.exec())
        #self.root.mainloop()
        pass
