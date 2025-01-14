import os
import re
import time
import json
import pytesseract
from pynput import keyboard
from pynput import mouse
from PIL import ImageGrab, ImageOps
from datetime import datetime
from datetime import timedelta
import psutil
import threading
import tkinter as tk
from tkinter import ttk
import statistics
from mouse_lock import lock_mouse, unlock_mouse
from encounter_detect import get_encounter_type

# Configure Tesseract path (adjust if necessary)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Data storage
maps_run = []  # List of maps with timestamps
xp_snapshots = []  # List of dictionaries with XP details
LOG_FILE_PATH = "poe_xp_tracker.json"

# Regex for map entry detection
MAP_ENTRY_REGEX = re.compile(r"Generating level (\d+) area \"(.+?)\"(?:.*seed (\d+))?", re.IGNORECASE)

# Global variables for Tkinter elements
map_table = None  # Reference to the table for updating
stats_table = None
current_map = None  # Tracks the currently active map
last_map_seed = None  # Tracks the seed of the last detected map
overview_frame = None
current_tab = None

# Function to find the Path of Exile log file
def find_poe_logfile():
    for proc in psutil.process_iter(['name', 'exe', 'cwd']):
        try:
            if "PathOfExile" in proc.info['name']:
                game_dir = proc.info['cwd'] or os.path.dirname(proc.info['exe'])
                log_file = os.path.join(game_dir, "logs", "Client.txt")
                if os.path.isfile(log_file):
                    print(f"[Log File Found] {log_file}")
                    return log_file
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    raise FileNotFoundError("Could not locate the Path of Exile Client.txt log file.")

# OCR function to capture XP and next level XP from screenshot
def capture_xp():
    try:
        # Save the current mouse position
        mouse_controller = mouse.Controller()
        original_position = mouse_controller.position

        # Move the mouse to the center bottom of the screen
        screen_width, screen_height = ImageGrab.grab().size
        center_x = screen_width // 2
        bottom_y = screen_height - 5  # Move just above the bottom of the screen
        mouse_controller.position = (center_x, bottom_y)

        try:
            mlock_handle = lock_mouse()
            time.sleep(0.15)  # Await XP hover
            screenshot = ImageGrab.grab()
        finally:
            unlock_mouse(mlock_handle)
            mouse_controller.position = original_position

        # Process the screenshot
        width, height = screenshot.size
        crop_height = int(height * 0.15)
        cropped_screenshot = screenshot.crop((0, height - crop_height, width, height))

        # Preprocessed images and OCR methods
        ocr_methods = [
            ("grayscale", lambda img: img.convert("L")),
            ("color", lambda img: img),
            ("inverted", lambda img: ImageOps.invert(img.convert("L"))),
            ("binary", lambda img: ImageOps.invert(img.convert("L")).point(lambda p: p > 128 and 255)),
        ]

        previous_xp = xp_snapshots[-1]["xp"] if xp_snapshots else None
        xp_values = []
        next_level_xp_values = []

        # Try OCR methods sequentially
        for method_name, preprocess in ocr_methods:
            processed_image = preprocess(cropped_screenshot)
            xp_text = pytesseract.image_to_string(processed_image, config="--psm 6 --oem 3")
            xp_value, next_level_xp = parse_xp(xp_text)

            if xp_value is not None:
                xp_values.append(xp_value)
            if next_level_xp is not None:
                next_level_xp_values.append(next_level_xp)

            # Stop early if a valid XP value is within 50% of prior XP
            if previous_xp is not None and xp_value is not None:
                if abs(xp_value - previous_xp) / previous_xp <= 0.5:
                    print(f"[OCR Success] Method: {method_name}, XP: {xp_value}, Next Level XP: {next_level_xp}")
                    break

        # Select XP and next_level_xp values
        xp_value = (
            min(xp_values, key=lambda x: abs(x - previous_xp))
            if previous_xp is not None and xp_values
            else statistics.mode(xp_values) if xp_values else None
        )
        next_level_xp = statistics.mode(next_level_xp_values) if next_level_xp_values else None

        if xp_value is not None and next_level_xp is not None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            encounter_type = None
            if current_map and not current_map.get("in_hideout", True):
                encounter_type = get_encounter_type(screenshot)
            xp_snapshots.append({
                "timestamp": timestamp,
                "xp": xp_value,
                "next_level_xp": next_level_xp,
                "previous_xp": previous_xp,
                "encounter_type": encounter_type
            })
            print(f"[Captured XP] {timestamp}: {xp_value} / {next_level_xp} (Previous XP: {previous_xp})")

            if current_map:
                xp_gained = (xp_value - current_map.get("xp_start", 0)) if xp_value else 0
                percentage_gained = (xp_gained / next_level_xp) * 100 if next_level_xp else 0
                current_map.update({
                    "xp_gained": xp_gained,
                    "percentage_gained": percentage_gained
                })

            save_progress()
            update_map_table()
        else:
            print("[Error] No valid XP value found in OCR results.")
            # Save the screenshot for debugging
            debug_image_path = os.path.join(os.getcwd(), f"debug_xp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            screenshot.save(debug_image_path)
            print(f"Debug screenshot saved at: {debug_image_path}")

    except Exception as e:
        print(f"[Error] Exception during XP capture: {e}")


# Function to parse the XP and next level XP values from the text
def parse_xp(xp_text):
    xp_match = re.search(r"Current Exp:?\s*([0-9.,:]+).*Next Level:?\s*([0-9.,:]+)", xp_text, re.IGNORECASE)
    if xp_match:
        xp_value = ''.join(char for char in xp_match.group(1) if char.isdigit())
        next_level_xp = ''.join(char for char in xp_match.group(2) if char.isdigit())
        if xp_value and next_level_xp:
            return int(xp_value), int(next_level_xp)
    return None, None

# Function to monitor log file
def monitor_log(log_file):
    global current_map, last_map_seed

    def process_log_line(line, timestamp):
        global current_map, last_map_seed

        map_match = MAP_ENTRY_REGEX.search(line)
        if not map_match:
            return False

        area_level = int(map_match.group(1))
        map_name = map_match.group(2)
        map_seed = int(map_match.group(3)) if map_match.group(3) else None

        if map_seed is not None and map_seed <= 1:
            # Entering hideout
            if current_map:
                current_map["hideout_start_time"] = timestamp
                current_map["in_hideout"] = True
            return True

        if current_map:
            hideout_start = current_map.pop("hideout_start_time", None)
            current_map["in_hideout"] = False
            if hideout_start:
                hideout_duration = (timestamp - hideout_start).total_seconds()
                current_map["total_hideout_time"] = current_map.get("total_hideout_time", 0) + hideout_duration

        if map_seed == last_map_seed:
            return True  # Skip if the map seed matches the last map

        # new map entered
        

        if current_map:
            complete_current_map()

        current_map = {
            "start_time": timestamp,
            "map_name": pretty_map_name(map_name),
            "map_name_raw": map_name,
            "area_level": area_level,
            "seed": map_seed,
            "xp_start": xp_snapshots[-1]["xp"] if xp_snapshots else 0,
            "end_time": None,
            "xp_gained": 0,
            "percentage_gained": 0,
            "total_hideout_time": 0,
            "in_hideout": False,
            "hideout_start_time": None
        }
        last_map_seed = map_seed
        save_progress()
        update_map_table()
        return True

    print("[Monitoring Log File]")
    with open(log_file, "r", encoding="utf-8") as f:
        # Scan backwards to determine current state, up to 5000 lines
        lines = f.readlines()
        lines_to_check = lines[-5000:] if len(lines) > 5000 else lines

        for line in reversed(lines_to_check):
            timestamp = datetime.now()  # Adjust if the log file contains timestamps
            if process_log_line(line, timestamp):
                break

        # Monitor the log file for new lines
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue

            timestamp = datetime.now()
            process_log_line(line, timestamp)


# Function to complete the current map
def complete_current_map():
    global current_map
    if not current_map:
        print("[Complete Map] No current map to complete.")
        return

    if current_map.get("end_time") is None:
        current_map["end_time"] = datetime.now()

    xp_end = xp_snapshots[-1]["xp"] if xp_snapshots else None
    next_level_xp = xp_snapshots[-1]["next_level_xp"] if xp_snapshots else None
    xp_gained = (xp_end - current_map["xp_start"]) if xp_end else 0
    percentage_gained = (xp_gained / next_level_xp) * 100 if next_level_xp else 0

    duration_seconds = (
        (current_map["end_time"] - current_map["start_time"]).total_seconds()
        - current_map.get("total_hideout_time", 0)
    )
    xph = (xp_gained / duration_seconds) * 3600 if duration_seconds > 0 else 0
    percentage_per_hour = (percentage_gained * 3600 / duration_seconds) if duration_seconds > 0 else 0

    # Copy all fields except 'in_hideout' and ensure datetime objects are serialized
    """
    map_data = {
        key: (value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, datetime) else value)
        for key, value in current_map.items()
        if key != "in_hideout" and key != "hideout_start_time"
    }
    map_data.update({
        "end_time": current_map["end_time"].strftime("%Y-%m-%d %H:%M:%S"),
        "xp_gained": xp_gained,
        "percentage_gained": percentage_gained,
        "xph": int(xph),
        "percentage_per_hour": round(percentage_per_hour, 4),
        "total_hideout_time": current_map.get("total_hideout_time", 0),
    })
    """
    map_data = current_map.copy()
    map_data.update({
        "xp_gained": xp_gained,
        "percentage_gained": percentage_gained,
        "xph": int(xph),
        "percentage_per_hour": round(percentage_per_hour, 4),
        "total_hideout_time": current_map.get("total_hideout_time", 0)
    })

    maps_run.append(map_data)
    current_map = None
    save_progress()
    update_map_table()

# Function to finalize all incomplete maps (called on program exit)
def finalize_incomplete_maps():
    if current_map:
        print("[Finalize] Completing the current map on exit.")
        complete_current_map()

# Function to save progress to a JSON file
def save_progress():
    data = {
        "maps_run": [
            {
                key: (value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, datetime) else value)
                for key, value in map_data.items()
            }
            for map_data in maps_run
        ],
        "xp_snapshots": xp_snapshots
    }
    with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Function to load progress from a JSON file
def load_progress():
    global maps_run, xp_snapshots
    if os.path.isfile(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            maps_run = data.get("maps_run", [])
            xp_snapshots = data.get("xp_snapshots", [])
            
            # Convert datetime strings back to datetime objects
            for map_data in maps_run:
                if "start_time" in map_data:
                    map_data["start_time"] = datetime.strptime(map_data["start_time"], "%Y-%m-%d %H:%M:%S")
                if "end_time" in map_data:
                    map_data["end_time"] = datetime.strptime(map_data["end_time"], "%Y-%m-%d %H:%M:%S")
                    
            print(f"[Progress Loaded] maps_run: {len(maps_run)}")
    else:
        print("[No Previous Progress Found]")


# Function to update the map table display
def update_map_table():
    for row in map_table.get_children():
        map_table.delete(row)
    for idx, map_data in enumerate(maps_run, start=1):
        start_time = map_data["start_time"]
        end_time = map_data["end_time"]
        # start_time = datetime.strptime(map_data["start_time"], "%Y-%m-%d %H:%M:%S")
        # end_time = datetime.strptime(map_data["end_time"], "%Y-%m-%d %H:%M:%S")
        duration_seconds = (end_time - start_time).total_seconds()
        duration_seconds -= map_data.get("total_hideout_time", 0)

        # Format duration as hh:mm:ss
        duration_str = str(timedelta(seconds=int(duration_seconds)))

        map_table.insert("", "end", values=(
            idx,
            map_data.get("map_name", "Unknown"),
            f"{map_data.get('xp_gained', 0):,}",
            f"{map_data.get('xph', 0):,}",
            f"{map_data.get('percentage_per_hour', 0):.4f}",
            map_data.get("area_level", "Unknown"),
            duration_str
        ))

# Function to aggregate stats by map name
def update_stats_table():
    stats = {}
    for map_data in maps_run:
        name = map_data["map_name"]
        if name not in stats:
            stats[name] = {"count": 0, "total_xp": 0, "total_xph": 0}
        stats[name]["count"] += 1
        stats[name]["total_xp"] += map_data.get("xp_gained", 0)
        stats[name]["total_xph"] += map_data.get("xph", 0)

    for row in stats_table.get_children():
        stats_table.delete(row)

    for map_name, data in stats.items():
        avg_xph = data["total_xph"] // data["count"]
        stats_table.insert("", "end", values=(map_name, data["count"], f"{data['total_xp']:,}", f"{avg_xph:,}"))

# Function to create the Overview tab
def update_overview():
    global current_map, overview_frame
    if not overview_frame or not overview_frame.winfo_exists():
        print("[Error] Overview frame does not exist.")
        return

    try:
        # Clear the frame
        for widget in overview_frame.winfo_children():
            widget.destroy()

        if not current_map:
            tk.Label(overview_frame, text="No current map data to display.").pack()
            return

        # Display map overview details
        map_name = current_map.get("map_name", "Unknown")
        xp_gained = current_map.get("xp_gained", 0)
        now_or_ho = current_map["hideout_start_time"] if current_map["in_hideout"] else datetime.now()
        total_duration = (
            now_or_ho - current_map["start_time"]
        ).total_seconds() if current_map["end_time"] is None else (
            current_map["end_time"] - current_map["start_time"]
        ).total_seconds()

        tk.Label(overview_frame, text=f"Map: {map_name}", font=("Helvetica", 12, "bold"), anchor="w").grid(row=0, column=0, sticky="w", columnspan=5)
        tk.Label(overview_frame, text=f"XP Gained: {xp_gained}", font=("Helvetica", 12), anchor="w").grid(row=1, column=0, sticky="w", columnspan=5)
        tk.Label(overview_frame, text=f"Duration: {str(timedelta(seconds=int(total_duration)))}", font=("Helvetica", 12), anchor="w").grid(row=2, column=0, sticky="w", columnspan=5)

        # Display the snapshots table
        columns = ["#", "Encounter Type", "XP", "XP/hour", "Duration"]
        for i, column in enumerate(columns):
            tk.Label(overview_frame, text=column, font=("Helvetica", 10, "bold"), anchor="w" if i == 1 else "e").grid(row=0, column=i, sticky="w" if i == 1 else "e")

        # Process snapshots of the current map and display them
        snapshots = []
        if xp_snapshots and current_map:
            map_start_time = current_map["start_time"].strftime("%Y-%m-%d %H:%M:%S")
            for i, snapshot in enumerate(xp_snapshots):
                if snapshot["timestamp"] < map_start_time:
                    continue

                next_snapshot = xp_snapshots[i + 1] if i + 1 < len(xp_snapshots) else None
                duration = (
                    (datetime.strptime(next_snapshot["timestamp"], "%Y-%m-%d %H:%M:%S") - datetime.strptime(snapshot["timestamp"], "%Y-%m-%d %H:%M:%S")).total_seconds()
                    if next_snapshot
                    else (now_or_ho - datetime.strptime(snapshot["timestamp"], "%Y-%m-%d %H:%M:%S")).total_seconds()
                )
                xp_gained = next_snapshot["xp"] - snapshot["xp"] if next_snapshot else 0
                xph = (xp_gained / duration) * 3600 if duration > 0 else 0

                snapshots.append({
                    "#": len(snapshots) + 1,
                    "Encounter Type": "Map" if "map_name" in current_map else "Other",
                    "XP": xp_gained,
                    "XP/hour": int(xph),
                    "Duration": str(timedelta(seconds=int(duration)))
                })

        for i, row in enumerate(snapshots):
            tk.Label(overview_frame, text=row["#"], anchor="e").grid(row=i + 1, column=0, sticky="e")
            tk.Label(overview_frame, text=row["Encounter Type"], anchor="w").grid(row=i + 1, column=1, sticky="w")
            tk.Label(overview_frame, text=f"{row['XP']:,}", anchor="e").grid(row=i + 1, column=2, sticky="e")
            tk.Label(overview_frame, text=f"{row['XP/hour']:,}", anchor="e").grid(row=i + 1, column=3, sticky="e")
            tk.Label(overview_frame, text=row["Duration"], anchor="e").grid(row=i + 1, column=4, sticky="e")

    except Exception as e:
        print(f"[Error in update_overview]: {e}")

def pretty_map_name(map_name):
    map_name = re.sub(r'^Map', '', map_name)
    words = re.findall(r'[A-Z][a-z]*|[a-z]+', map_name)
    return ' '.join(words)

# Create the Tkinter GUI
def create_gui():
    global map_table, stats_table, overview_frame

    root = tk.Tk()
    root.title("PoE XP Tracker")
    root.geometry("1000x600")

    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True)

    # Maps Tab
    maps_tab = ttk.Frame(notebook)
    notebook.add(maps_tab, text="Maps")

    columns = ("#", "Map Name", "XP Gained", "XP/hour", "%/hour", "Area Level", "Duration")
    map_table = ttk.Treeview(maps_tab, columns=columns, show="headings")

    # Configure column headings and alignment
    for col in columns:
        map_table.heading(col, text=col, anchor="w")  # Left-align all headers

    # Configure column alignment and size
    map_table.column("#", anchor="e", width=5)  # Smallest possible for index
    map_table.column("Map Name", anchor="w", width=150)  # Left-align map name
    map_table.column("XP Gained", anchor="e", width=60)  # Right-align XP Gained
    map_table.column("XP/hour", anchor="e", width=60)  # Right-align XP/hour
    map_table.column("%/hour", anchor="e", width=40)  # Center-align %/hour
    map_table.column("Area Level", anchor="e", width=40)  # Center-align Area Level
    map_table.column("Duration", anchor="e", width=60)  # Center-align Duration

    map_table.pack(fill=tk.BOTH, expand=True)

    # Stats Tab
    stats_tab = ttk.Frame(notebook)
    notebook.add(stats_tab, text="Stats")

    stats_columns = ("Map Name", "Count", "Total XP", "Average XPH")
    stats_table = ttk.Treeview(stats_tab, columns=stats_columns, show="headings")
    for col in stats_columns:
        stats_table.heading(col, text=col)
        stats_table.column(col, anchor="center")
    stats_table.pack(fill=tk.BOTH, expand=True)

    # Overview Tab
    overview_frame = ttk.Frame(notebook)
    notebook.add(overview_frame, text="Overview")
    update_overview()

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    log_file = find_poe_logfile()
    threading.Thread(target=monitor_log, args=(log_file,), daemon=True).start()
    load_progress()
    update_map_table()
    update_stats_table()
    def on_tab_change(event):
        global current_tab
        selected_tab = event.widget.tab(event.widget.index("current"))["text"]
        current_tab = selected_tab
        if current_tab == "Overview":
            periodic_overview_update()

    notebook.bind("<<NotebookTabChanged>>", on_tab_change)
    
    def periodic_overview_update():
        global current_tab
        if current_tab == "Overview":
            update_overview()
            overview_frame.after(250, periodic_overview_update)
    
    root.mainloop()

# Key listener to capture XP on F6
def on_press(key):
    try:
        if key == keyboard.Key.f6:
            capture_xp()
    except Exception as e:
        print(f"[Error] {e}")

if __name__ == "__main__":
    try:
        load_progress()
        create_gui()
    except KeyboardInterrupt:
        print("\n[Exiting]")
        finalize_incomplete_maps()
    except Exception as e:
        print(f"[Error] {e}")
