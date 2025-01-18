from datetime import datetime, timedelta
import re
import json
import os
import time
from pynput import keyboard
from xp_table import get_level_from_xp, get_xp_range_for_level
from config_manager import ConfigManager
from item import Item
from typing import Optional
from pyee import EventEmitter
import pygetwindow as gw
import threading
import psutil
from dataclasses import dataclass, asdict


USER_DATA_PATH = "user_data"
LOG_FILE_PATH = os.path.join(USER_DATA_PATH, "poe_xp_tracker.json")
MAP_ENTRY_REGEX = re.compile(r"Generating level (\d+) area \"(.+?)\"(?:.*seed (\d+))?", re.IGNORECASE)
POST_LOAD_REGEX = re.compile(r"\[SHADER\] Delay:", re.IGNORECASE)
os.makedirs(USER_DATA_PATH, exist_ok=True)

events = EventEmitter()
config_manager = ConfigManager(path="user_data/config.json", meta={
    "screenshot_hotkey": {
        "label": "Capture hotkey",
        "type": "hotkey",
        "default": {
            "key_code": keyboard.Key.f6._value_,
            "modifiers": set()
        },
        "description": "Hotkey to capture screenshots"
    },
    "default_log_file": {
        "label": "Default log file",
        "type": str
    },
    "default_league": {
        "label": "Default league",
        "type": str
    },
    "account_name": {
        "label": "Account name",
        "type": str
    },
    "character_name": {
        "label": "Character name",
        "type": str
    },
    "twitch_name": {
        "label": "Twitch name",
        "type": str
    },
    "lock_input_during_capture": {
        "label": "Lock input during capture",
        "type": bool,
        "default": False,
        "description": "Lock keyboard and mouse input during capture of item data and XP (requires admin privileges)"
    },
    "capture_item_data": {
        "label": "Capture item data",
        "type": bool,
        "default": True,
        "description": "Capture item data from clipboard (requires mouse over item)"
    },
    "defer_ocr": {
        "label": "Defer OCR",
        "type": bool,
        "default": True,
        "description": "If false, OCR will be processed immediately (computationally expensive, CPU bound), otherwise awaits until hideout is entered"
    },
    "imgur_client_id": {
        "label": "Imgur client id",
        "type": str,
        "description": "Imgur client ID for uploading screenshots"
    }
})

maps_run = []
xp_snapshots = []
current_map = None
next_waystone = None
cached_window = None

@dataclass
class XPSnapshot:
    ts: datetime
    xp: int
    delta: int
    source: str
    encounter_type: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.xp, int) or self.xp < 0:
            raise ValueError("xp must be a positive integer")
        if not isinstance(self.ts, datetime):
            raise ValueError("timestamp must be a datetime object")
        if self.encounter_type is not None and not isinstance(self.encounter_type, str):
            raise TypeError("encounter_type must be a string or None")

    def to_dict(self):
        return {
            "ts": self.ts.isoformat(),
            "xp": self.xp,
            "delta": self.delta,
            "source": self.source,
            "encounter_type": self.encounter_type
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            ts=datetime.fromisoformat(data["ts"]),
            xp=data["xp"],
            delta=data["delta"],
            source=data["source"],
            encounter_type=data["encounter_type"]
        )

@dataclass
class MapSpan:
    start: datetime
    end: Optional[datetime] = None
    area_entered_at: Optional[datetime] = None
    hideout_time: timedelta = timedelta(0)
    load_time: timedelta = timedelta(0)
    pause_time: timedelta = timedelta(0)

    def __post_init__(self):
        if not isinstance(self.start, datetime):
            raise TypeError("start must be a datetime object")
        if not isinstance(self.load_time, timedelta):
            raise TypeError("load_time must be a timedelta object")
        if not isinstance(self.hideout_time, timedelta):
            raise TypeError("hideout_time must be a timedelta object")
        if not isinstance(self.pause_time, timedelta):
            raise TypeError("pause_time must be a timedelta object")
        if self.load_time.total_seconds() < 0:
            raise ValueError("load_time cannot be negative")
        if self.hideout_time.total_seconds() < 0:
            raise ValueError("hideout_time cannot be negative")
        if self.end and not isinstance(self.end, datetime):
            raise TypeError("end must be a datetime object")
        if self.end and self.end < self.start:
            raise ValueError("end time cannot be before start time")

    def map_time(self):
        total_time = self.end - self.start if self.end else datetime.now() - self.start
        return total_time - self.hideout_time - self.load_time

    def add_to_load_time(self, load_time: timedelta):
        if not isinstance(load_time, timedelta):
            raise TypeError("load_time must be a timedelta object")
        self.load_time += load_time 

    def add_to_hideout_time(self, hideout_time: timedelta):
        if not isinstance(hideout_time, timedelta):
            raise TypeError("hideout_time must be a timedelta object")
        self.hideout_time += hideout_time

    def add_to_pause_time(self, pause_time: timedelta):
        if not isinstance(pause_time, timedelta):
            raise TypeError("pause_time must be a timedelta object")
        self.pause_time += pause_time

    def set_area_entered_at(self, entered_at: datetime):
        if not isinstance(entered_at, datetime):
            raise TypeError("timestamp must be a datetime object")  
        if (entered_at < self.start):
            raise ValueError("timestamp cannot be before start time")
        self.area_entered_at = entered_at

    def set_end(self, end: datetime):
        if not isinstance(end, datetime):
            raise TypeError("end must be a datetime object")
        if (end < self.start):
            raise ValueError("end time cannot be before start time")
        self.end = end

    def to_dict(self):
        return {
            "start": self.start.isoformat(),
            "area_entered_at": self.area_entered_at.isoformat() if self.area_entered_at else None,
            "end": self.end.isoformat() if self.end else None,
            "hideout_time": self.hideout_time.total_seconds(),
            "load_time": self.load_time.total_seconds()
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            start=datetime.fromisoformat(data["start"]),
            area_entered_at=datetime.fromisoformat(data["area_entered_at"]),
            end=datetime.fromisoformat(data["end"]) if data["end"] else None,
            hideout_time=timedelta(seconds=data["hideout_time"]),
            load_time=timedelta(seconds=data["load_time"])
        )


@dataclass
class MapInstance:
    span: MapSpan
    map_name: str
    area_level: int
    seed: int
    xp_start: Optional[int] = None
    xp_gained: int = 0
    waystone: Optional[Item] = None
    in_hideout: bool = False
    hideout_start_time: Optional[datetime] = None

    def __post_init__(self):
        if not isinstance(self.map_name, str) or not self.map_name.strip():
            raise ValueError("map_name must be a non-empty string")
        if not isinstance(self.area_level, int) or self.area_level < 0:
            raise ValueError("area_level must be a positive integer")
        if not isinstance(self.seed, int):
            raise TypeError("map_seed must be an integer")
        if self.xp_start is not None and (not isinstance(self.xp_start, int) or self.xp_start < 0):
            raise ValueError("initial_xp may not be negative")
        if self.hideout_start_time is not None and not isinstance(self.hideout_start_time, datetime):
            raise TypeError("hideout_start_time must be a datetime object")

    def xph(self):
        map_time = self.span.map_time().total_seconds()
        return self.xp_gained / map_time * 3600 if map_time > 0 else 0

    def enter_hideout(self, timestamp: datetime):
        if not isinstance(timestamp, datetime):
            raise TypeError("timestamp must be a datetime object")
        self.hideout_start_time = timestamp
        self.in_hideout = True

    def exit_hideout(self, timestamp: datetime):
        if not isinstance(timestamp, datetime):
            raise TypeError("timestamp must be a datetime object")
        if self.hideout_start_time:
            hideout_duration = timestamp - self.hideout_start_time
            self.span.add_to_hideout_time(hideout_duration)
        self.hideout_start_time = None
        self.in_hideout = False

    def complete(self, end_time: datetime = None):
        if end_time is None:
            end_time = datetime.now()
        self.span.set_end(end_time)

        
    def to_dict(self):
        return {
            "span": self.span.to_dict(),
            "map_name": self.map_name,
            "area_level": self.area_level,
            "seed": self.seed,
            "xp_start": self.xp_start,
            "xp_gained": self.xp_gained,
            "waystone": self.waystone.to_dict() if self.waystone else None,
            "in_hideout": self.in_hideout,
            "hideout_start_time": self.hideout_start_time.isoformat() if self.hideout_start_time else None
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            span=MapSpan.from_dict(data["span"]),
            map_name=data["map_name"],
            area_level=data["area_level"],
            seed=data["seed"],
            xp_start=data["xp_start"],
            xp_gained=data["xp_gained"],
            waystone=Item.from_dict(data["waystone"]) if data["waystone"] else None,
            in_hideout=data["in_hideout"],
            hideout_start_time=datetime.fromisoformat(data["hideout_start_time"]) if data["hideout_start_time"] else None
        )
        

def find_poe_pid():
    procs = psutil.process_iter(['pid', 'name'])
    for name in ["PathOfExile.exe", "PathOfExile_x64.exe", "PathOfExile2.exe", "PathOfExile2_x64.exe", "Path of Exile", "Path of Exile 2"]:
        for proc in procs:
            try:
                if name.lower() == proc.info['name'].lower().strip():
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    return None

try:
    import win32gui
    import win32con
    import win32process
    SUPPORTS_WIN32 = True
except ImportError:
    SUPPORTS_WIN32 = False

def find_poe_window() -> Optional[gw.Window]:
    global cached_window
    if cached_window:
        if SUPPORTS_WIN32:
            try:
                hwnd = cached_window._hWnd
                if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    return cached_window
            except Exception:
                pass
        else:
            for window in gw.getAllWindows():
                if window._hWnd == cached_window._hWnd:
                    return window

    if SUPPORTS_WIN32:
        pid = find_poe_pid()
        if not pid:
            print("[Error] Path of Exile 2 process not found.")
            return None

        def callback(hwnd, target_pid):
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == target_pid and win32gui.IsWindowVisible(hwnd):
                handles.append(hwnd)

        handles = []
        win32gui.EnumWindows(callback, pid)

        if handles:
            target_hwnd = handles[0]
            for window in gw.getAllWindows():
                if window._hWnd == target_hwnd:
                    cached_window = window
                    return window
    else:
        for window in gw.getAllWindows():
            if window.title.strip().lower() == "path of exile 2":
                cached_window = window
                return window

    print("[Error] Path of Exile 2 window not found.")
    return None

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
    
    default_log_file = config_manager.get("default_log_file")
    if default_log_file:
        if not os.path.exists(default_log_file):
            raise FileNotFoundError(f"Default log file not found at: {default_log_file}")

        print(f"failed to guess log file, using default: {default_log_file}")
        return default_log_file

    raise RuntimeError("Path of Exile process not found and no default log file configured.")

def init():
    threading.Thread(target=_monitor_log, daemon=True).start()

def _monitor_log(log_file = find_poe_logfile()):
    def process_log_line(line, timestamp):
        map_match = MAP_ENTRY_REGEX.search(line)
        if not map_match:
            return False
        else:
            post_load_match = POST_LOAD_REGEX.search(line)
            if post_load_match:
                if current_map:
                    entered_at = current_map.span.area_entered_at
                    current_map.span.add_to_load_time(datetime.now() - entered_at)
                events.emit("area_post_load")

        area_level = int(map_match.group(1))
        map_name = map_match.group(2)
        map_seed = int(map_match.group(3)) if map_match.group(3) else None

        enter_area(timestamp, area_level, map_name, map_seed)
        return True

    print("[Monitoring Log File]")
    with open(log_file, "r", encoding="utf-8") as f:
        # Scan backwards to determine current state, up to 5000 lines
        lines = f.readlines()
        lines_to_check = lines[-5000:] if len(lines) > 5000 else lines

        for line in reversed(lines_to_check):
            timestamp = datetime.now()
            if process_log_line(line, timestamp):
                break
        
        if not config_manager.get("default_log_file"):
            config_manager.update({"default_log_file": log_file})
        # Monitor the log file for new lines
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue

            timestamp = datetime.now()
            process_log_line(line, timestamp)

def pretty_map_name(map_name):
    map_name = re.sub(r'^Map', '', map_name)
    words = re.findall(r'[A-Z][a-z]*|[a-z]+', map_name)
    return ' '.join(words)

def enter_area(timestamp: datetime, area_level: int, map_name: str, map_seed: int):
    if not isinstance(timestamp, datetime):
        raise TypeError("timestamp must be a datetime object")

    global current_map, next_waystone
    if current_map and timestamp <= current_map.span.start:
        raise ValueError(f"new areas must be entered in chronological order: {timestamp} <= {current_map.span.start}")

    events.emit("area_entered", {"timestamp": timestamp, "area_level": area_level, "map_name": map_name, "map_seed": map_seed})

    if map_seed is not None and map_seed <= 1:
        if current_map:
            current_map.enter_hideout(timestamp)
            events.emit("hideout_entered", {"map": current_map})
        return None

    if current_map:
        current_map.span.set_area_entered_at(timestamp)
        if current_map.in_hideout:
            current_map.exit_hideout(timestamp)
            events.emit("hideout_exited", {"map": current_map})
        if map_seed == current_map.seed:
            events.emit("map_reentered", {"map": current_map})
            return None

    if current_map:
        complete_current_map()

    initial_xp = xp_snapshots[-1].xp if xp_snapshots else None
    previous_map = current_map
    current_map = MapInstance(
        span=MapSpan(start=timestamp), 
        map_name=pretty_map_name(map_name), 
        area_level=area_level, 
        seed=map_seed, 
        xp_start=initial_xp,
        waystone=next_waystone
    )
    next_waystone = None
    events.emit("map_entered", {"map": current_map, "previous_map": previous_map})
    save_progress()
    return current_map

def get_current_map():
    return current_map

def in_hideout():
    return current_map.in_hideout if current_map else True

def in_map():
    return not in_hideout()

def apply_xp_snapshot(xp: int, ts: datetime = None, source: str = None, encounter_type: str = None):
    if ts is None:
        ts = datetime.now()
    if not isinstance(xp, int) or xp < 0:
        raise ValueError("xp must be a positive integer")
    if not isinstance(ts, datetime):
        raise ValueError("timestamp must be a datetime object")
    if encounter_type is not None and not isinstance(encounter_type, str):
        raise TypeError("encounter_type must be a string or None")

    prev = xp_snapshots[-1] if xp_snapshots else None
    prev_xp = prev.xp if prev else None
    delta = xp - prev_xp if prev_xp else 0
    if source == "ladder" and prev:
        if prev.source != source and delta < 0 and (prev.ts - ts).total_seconds() <= 300: 
            print(f"[Info] skipping ladder XP snapshot with negative delta (prev was non-ladder), delta: {delta}")
            return
    
    xp_snapshots.append(XPSnapshot(ts, xp, delta, source, encounter_type))
    print(f"[Captured XP] ts: {ts}, delta: {delta}, xp: {xp}, source: {source}")

    if current_map and current_map.xp_start:
        xp_gained = (xp - current_map.xp_start) if xp else 0
        current_map.xp_gained = xp_gained

    save_progress()

def set_next_waystone(item: Item):
    global next_waystone
    next_waystone = item

def complete_current_map():
    global current_map
    if not current_map:
        print("[Complete Map] No current map to complete.")
        return None

    current_map.span.set_end(datetime.now())
    xp_end = xp_snapshots[-1].xp if xp_snapshots else None
    xp_gained = (xp_end - current_map.xp_start) if xp_end and current_map.xp_start else 0

    map_data = current_map
    map_data.xp_gained = xp_gained
    maps_run.append(map_data)
    save_progress()
    return None

def save_progress():
    data = {
        "maps_run": [map_data.to_dict() for map_data in maps_run],
        "xp_snapshots": [snapshot.to_dict() for snapshot in xp_snapshots]
    }
    os.makedirs(USER_DATA_PATH, exist_ok=True)
    with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_progress():
    if os.path.isfile(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            maps_run.extend(MapInstance.from_dict(m) for m in data.get("maps_run", []))
            xp_snapshots.extend(XPSnapshot.from_dict(x) for x in data.get("xp_snapshots", []))
            print(f"[Progress Loaded] maps_run: {len(maps_run)}")
    else:
        print("[No Previous Progress Found]")

init()