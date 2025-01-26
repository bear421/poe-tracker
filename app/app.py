import os
import uuid
import re
import time
import json
import pytesseract
from pynput import mouse
import pyautogui
import pyperclip
from PIL import ImageOps, Image
from datetime import datetime
from datetime import timedelta
from time import sleep
import statistics
from gui import TrackerGUI
from mouse_lock import block_mouse_movement, unblock_mouse_movement
from encounter_detect import get_encounter_type
from item import parse_item
from poe_bridge import (
    apply_xp_snapshot,
    get_recent_xp_snapshots,
    set_next_waystone,
    in_hideout,
    in_map,
    Encounter,
    add_encounter
)
from settings import config
import threading
import queue
import pyttsx3
from item import Item
from area_tla import get_threat_level
from screenshot import capture_window, find_poe_window
import traceback
from dataclasses import dataclass
from typing import Optional
from Levenshtein import distance as Levenshtein

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
        print(f"[Info] was_in_map: {self.was_in_map}, in_map: {in_map()}, then: {self.then}")
        if self.was_in_map:
            (encounter_type, encounter_data) = get_encounter_type(self.image)
            if encounter_type:
                if in_map() and datetime.now() - self.then < timedelta(seconds=30):
                    tts_engine.say(f"encounter: {encounter_type}")
                    threading.Thread(target=tts_engine.runAndWait).start()
            elif config.get("add_unknown_encounters_as_screenshot"):
                encounter_type = "screenshot"
        else:
            encounter_type = "hideout"
            encounter_data = None
        width, height = self.image.size
        crop_height = int(height * 0.15)
        cropped_image = self.image.crop((width * 0.2, height - crop_height, width * 0.9, height))
        xp_value = ocr_xp(cropped_image)
        if xp_value is not None: 
            snapshot = apply_xp_snapshot(xp_value, self.then, source="ocr", encounter_type=encounter_type)
        else:
            snapshot = None
            print("[Error] No valid XP value found in OCR results.")
            dir = os.path.join(os.getcwd(), "user_data", "debug_xp")
            os.makedirs(dir, exist_ok=True)
            debug_image_path = os.path.join(dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            cropped_image.save(debug_image_path)
            print(f"Debug screenshot saved at: {debug_image_path}")
        if encounter_type and encounter_type != "hideout":
            image_path = os.path.join("user_data", "encounters")
            os.makedirs(image_path, exist_ok=True)
            image_path = os.path.join(image_path, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            self.image.save(image_path)
            encounter = Encounter(
                str(uuid.uuid4()),
                encounter_type,
                self.then,
                encounter_data,
                image_path,
                snapshot
            )
            add_encounter(encounter)

@dataclass
class OCRRitualJob:
    image: Image.Image
    item: Item
    then: datetime

    def run(self):
        ocr_text = "todo"
        tribute_cost = parse_tribute_cost(ocr_text)
        if tribute_cost:
            print(f"tribute cost: {tribute_cost}")

def capture_data():
    if config.get("capture_item_data"):
        _capture_item()
    _capture_xp()

def _capture_item():
    original_clipboard = pyperclip.paste()
    lock_input = config.get("lock_input_during_capture")
    try:
        try:
            lock_handle = block_mouse_movement() if lock_input else None
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
                    screenshot = capture_window(find_poe_window())
                    ocr_queue.put(OCRRitualJob(screenshot, item, datetime.now()))
                    # cannot capture xp with ritual window open (?)
                    return
                if not lock_input:
                    # necessarily cannot capture xp if mouse was on an item
                    return
    finally:
        pyperclip.copy(original_clipboard)

def _capture_xp():
    try:
        mouse_controller = mouse.Controller()
        original_position = mouse_controller.position

        game_window = find_poe_window()
        if not game_window:
            return

        center_x = game_window.left + (game_window.width // 2)
        bottom_y = game_window.bottom - 5  # Move just above the bottom of the window
        mouse_controller.position = (center_x, bottom_y)

        lock_handle = block_mouse_movement() if config.get("lock_input_during_capture") else None
        try:
            time.sleep(0.15) # Await XP hover
            screenshot = capture_window(game_window)
            if not screenshot: return
        finally:
            unblock_mouse_movement(lock_handle)
            mouse_controller.position = original_position
        
        ocr_queue.put(OCRXPJob(screenshot, in_map(), datetime.now()))
    except Exception as e:
        print(f"[Error] Exception during XP capture: {e}\n{traceback.format_exc()}")

def process_ocr_queue():
    while True: 
        try:
            job = ocr_queue.get(block=True)
            if job is None:  # Exit signal
                break
            while config.get("defer_ocr") == True and in_map():
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
        previous_xp = get_recent_xp_snapshots()[-1].xp if get_recent_xp_snapshots() else None
    ocr_methods = [
        ("grayscale", lambda img: img.convert("L")),
        ("color", lambda img: img),
        ("inverted", lambda img: ImageOps.invert(img.convert("L"))),
        ("binary", lambda img: ImageOps.invert(img.convert("L")).point(lambda p: p > 128 and 255)),
    ]
    xp_values = []

    # Try OCR methods sequentially
    for method_name, preprocess in ocr_methods:
        processed_image = preprocess(image)
        xp_text = pytesseract.image_to_string(processed_image, config="--psm 6 --oem 3")
        xp_value, next_level_xp = parse_xp(xp_text)

        if xp_value is not None:
            xp_values.append(xp_value)

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
    return xp_value

def parse_tribute_cost(text) -> Optional[int]:
    lines = text.splitlines()
    tribute_cost = None
    cost_index = None

    for i, line in enumerate(lines):
        # Check for 'cost' hint
        if re.search(r'cost:?', line, re.IGNORECASE) and cost_index is None:
            cost_index = i

        # Look for 'tribute' based on cost's position
        if cost_index is not None and i > cost_index and i <= cost_index + 3:
            words = line.split()
            tribute_match = next((word for word in words if Levenshtein.distance(word.lower(), "tribute") <= 2), None)
            if tribute_match:
                tribute_cost_match = re.search(r'(\d+(\.\d+)?)[xX]', line)
                if tribute_cost_match:
                    tribute_cost = tribute_cost_match.group(1).replace(".", "")
        elif re.search(r'\bTRIBUTE\b(?!.*\bremaining\b)', line, re.IGNORECASE):
            tribute_cost_match = re.search(r'(\d+(\.\d+)?)[xX]', line)
            if tribute_cost_match:
                tribute_cost = tribute_cost_match.group(1).replace(".", "")
        
        if tribute_cost:
            return int(tribute_cost)

    return None


if __name__ == "__main__":
    try:
        thread = threading.Thread(target=process_ocr_queue).start()
        tts_engine = pyttsx3.init()
        # tts_engine.startLoop()
        tts_engine.setProperty("volume", 0.5)
        voices = tts_engine.getProperty("voices")
        if len(voices) > 1:
            tts_engine.setProperty("voice", voices[1].id)

        gui = TrackerGUI(capture_data)
    except KeyboardInterrupt:
        print("\n[Exiting]")
    except Exception as e:
        print(f"[Error]: {str(e)}\n{traceback.format_exc()}")
