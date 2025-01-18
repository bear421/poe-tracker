import os
import re
import time
import json
import pytesseract
import pygetwindow as gw
from pynput import keyboard
from pynput import mouse
import pyautogui
import pyperclip
from PIL import ImageOps, Image
from datetime import datetime
from datetime import timedelta
from time import sleep
import psutil
import statistics
from gui import XPTrackerGUI
from mouse_lock import block_mouse_movement, unblock_mouse_movement
from encounter_detect import get_encounter_type
from item import parse_item
from instance_tracker import (
    maps_run, xp_snapshots,
    enter_area, apply_xp_snapshot,
    get_current_map,
    save_progress, load_progress,
    set_next_waystone,
    in_hideout,
    in_map,
    config_manager,
    events
)
from ladder_api import fetch_data
import threading
import queue
import pyttsx3
from item import Item
from area_tla import get_threat_level
from screenshot import capture_window, find_poe_window
import traceback
from dataclasses import dataclass

# Configure Tesseract path (adjust if necessary)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

MAP_ENTRY_REGEX = re.compile(r"Generating level (\d+) area \"(.+?)\"(?:.*seed (\d+))?", re.IGNORECASE)
tts_engine = None
ocr_queue = queue.Queue()

@dataclass
class OCRXPJob:
    image: Image.Image
    was_in_map: bool
    then: datetime

    def run(self):
        encounter_type = None
        if self.was_in_map:
            encounter_type = get_encounter_type(self.image)
            if encounter_type != "Map" and in_map() and datetime.now() - self.then < timedelta(seconds=30):
                tts_engine.say(f"encounter: {encounter_type}")
                threading.Thread(target=tts_engine.runAndWait).start()
        width, height = self.image.size
        crop_height = int(height * 0.15)
        cropped_image = self.image.crop((width * 0.2, height - crop_height, width * 0.9, height))
        xp_value = ocr_xp(cropped_image)
        if xp_value is not None: 
            apply_xp_snapshot(xp_value, self.then, source="ocr", encounter_type=encounter_type)
        else:
            print("[Error] No valid XP value found in OCR results.")
            dir = os.path.join(os.getcwd(), "user_data", "debug_xp")
            os.makedirs(dir, exist_ok=True)
            debug_image_path = os.path.join(dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            cropped_image.save(debug_image_path)
            print(f"Debug screenshot saved at: {debug_image_path}")

def capture_data():
    if config_manager.get("capture_item_data"):
        original_clipboard = pyperclip.paste()
        try:
            try:
                lock_handle = block_mouse_movement() if config_manager.get("lock_input_during_capture") else None
                pyautogui.hotkey("ctrl", "c")
                sleep(0.1)  # Delay to allow clipboard to update
                clipboard_text = pyperclip.paste()
            finally:
                unblock_mouse_movement(lock_handle)
            if clipboard_text:
                item = parse_item(clipboard_text)
                if item:
                    if in_hideout():
                        if item.item_class == "Waystones":
                            set_next_waystone(item)
                            threat_level, hint = get_threat_level(item)
                            tts_engine.say(f"threat level:{threat_level} - {hint}")
                            threading.Thread(target=tts_engine.runAndWait).start()
                    else:
                        # TODO attempt ritual capture
                        pass
        finally:
            pyperclip.copy(original_clipboard)

    capture_xp()

def capture_xp():
    try:
        print(f"current map start: {get_current_map().span.start}")
        mouse_controller = mouse.Controller()
        original_position = mouse_controller.position

        game_window = find_poe_window()
        center_x = game_window.left + (game_window.width // 2)
        bottom_y = game_window.bottom - 5  # Move just above the bottom of the window
        mouse_controller.position = (center_x, bottom_y)

        lock_handle = block_mouse_movement() if config_manager.get("lock_input_during_capture") else None
        try:
            time.sleep(0.1) # Await XP hover
            screenshot = capture_window(game_window)
            if not screenshot: return
        finally:
            unblock_mouse_movement(lock_handle)
            mouse_controller.position = original_position
        
        ocr_queue.put(OCRXPJob(screenshot, in_map(), datetime.now()))
    except Exception as e:
        print(f"[Error] Exception during XP capture: {e}")

def process_ocr_queue():
    while True: 
        try:
            job = ocr_queue.get(block=True)
            if job is None:  # Exit signal
                break
            while config_manager.get("defer_ocr") == True and in_map():
                sleep(2)
            job.run()
        finally:
            ocr_queue.task_done()

# Function to parse the XP and next level XP values from the text
def parse_xp(xp_text):
    xp_match = re.search(r"Current Exp:?\s*([0-9.,:]+).*Next Level:?\s*([0-9.,:]+)", xp_text, re.IGNORECASE)
    if xp_match:
        xp_value = ''.join(char for char in xp_match.group(1) if char.isdigit())
        next_level_xp = ''.join(char for char in xp_match.group(2) if char.isdigit())
        if xp_value and next_level_xp:
            return int(xp_value), int(next_level_xp)
    return None, None

def ocr_xp(image, previous_xp = None):
    if previous_xp is None:
        previous_xp = xp_snapshots[-1].xp if xp_snapshots else None
    ocr_methods = [
        ("grayscale", lambda img: img.convert("L")),
        ("color", lambda img: img),
        ("inverted", lambda img: ImageOps.invert(img.convert("L"))),
        ("binary", lambda img: ImageOps.invert(img.convert("L")).point(lambda p: p > 128 and 255)),
    ]
    xp_values = []
    # next_level_xp_values = []

    # Try OCR methods sequentially
    for method_name, preprocess in ocr_methods:
        processed_image = preprocess(image)
        xp_text = pytesseract.image_to_string(processed_image, config="--psm 6 --oem 3")
        xp_value, next_level_xp = parse_xp(xp_text)

        if xp_value is not None:
            xp_values.append(xp_value)
        #if next_level_xp is not None:
            #next_level_xp_values.append(next_level_xp)

        # Stop early if a valid XP value is within 50% of prior XP
        if previous_xp is not None and xp_value is not None:
            if abs(xp_value - previous_xp) / previous_xp <= 0.5:
                print(f"[OCR Success] Method: {method_name}, XP: {xp_value}, Next Level XP: {next_level_xp}")
                break

    xp_value = (
        min(xp_values, key=lambda x: abs(x - previous_xp))
        if previous_xp is not None and xp_values
        else statistics.mode(xp_values) if xp_values else None
    )
    #next_level_xp = statistics.mode(next_level_xp_values) if next_level_xp_values else None
    return xp_value#, next_level_xp

def on_map_entered(event):
    default_league = config_manager.get("default_league")
    character_name = config_manager.get("character_name")
    account_name = config_manager.get("account_name")
    if default_league and (character_name or account_name):
        ladder_data = fetch_data(character_name=character_name, account_name=account_name, league=default_league)
        if ladder_data:
            xp = ladder_data.character.experience
            apply_xp_snapshot(xp, source="ladder")


if __name__ == "__main__":
    try:
        load_progress()
        thread = threading.Thread(target=process_ocr_queue).start()
        gui = XPTrackerGUI(capture_callback=capture_data)
        events.on("map_entered", on_map_entered)
        events.on("area_entered",  lambda _: gui.update_map_table(maps_run))
        events.on("area_entered",  lambda _: gui.update_stats_table(maps_run))
        tts_engine = pyttsx3.init()
        # tts_engine.startLoop()
        tts_engine.setProperty("volume", 0.5)
        voices = tts_engine.getProperty("voices")
        if len(voices) > 1:
            tts_engine.setProperty("voice", voices[1].id)
        gui.run()
    except KeyboardInterrupt:
        print("\n[Exiting]")
    except Exception as e:
        print(f"[Error]: {str(e)}\n{traceback.format_exc()}")
