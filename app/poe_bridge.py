from datetime import datetime, timedelta
import re
import json
import os
import time
from settings import config
from item import Item
from typing import Optional
import pygetwindow as gw
import threading
import psutil
from db import conn
from ladder_api import fetch_data
from instance_tracker import InstanceTracker, MapInstance, XPSnapshot
from collections import deque
from dataclasses import dataclass

USER_DATA_PATH = "user_data"
LOG_FILE_PATH = os.path.join(USER_DATA_PATH, "poe_xp_tracker.json")
os.makedirs(USER_DATA_PATH, exist_ok=True)

_cached_window = None
_last_ladder_capture = None
_tracker = InstanceTracker()
_recent_encounters = deque(maxlen=100)
events = _tracker.events

@dataclass
class Encounter:
    id: str
    name: str
    ts: datetime
    data: {}
    screenshot_path: Optional[str]
    snapshot: Optional[XPSnapshot]

    def to_dict(self):
        return {
            "name": self.name,
            "ts": self.ts.isoformat(),
            "data": self.data,
            "screenshot_path": self.screenshot_path,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None
        }

    @classmethod
    def from_dict(cls, id, data):
        return cls(
            id=id,
            name=data["name"],
            ts=datetime.fromisoformat(data["ts"]),
            data=data["data"],
            screenshot_path=data["screenshot_path"],
            snapshot=None #XPSnapshot.from_dict(data["snapshot"]) if data["snapshot"] else None
        )
    
    @classmethod
    def from_row(cls, id, data):
        return cls.from_dict(id, json.loads(data))

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
    global _cached_window
    if _cached_window:
        if SUPPORTS_WIN32:
            try:
                hwnd = _cached_window._hWnd
                if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    return _cached_window
            except Exception:
                pass
        else:
            for window in gw.getAllWindows():
                if window._hWnd == _cached_window._hWnd:
                    return window

    if SUPPORTS_WIN32:
        pid = find_poe_pid()
        if not pid:
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
                    _cached_window = window
                    return window
    else:
        for window in gw.getAllWindows():
            if window.title.strip().lower() == "path of exile 2":
                _cached_window = window
                return window

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
    
    default_log_file = config.get("default_log_file")
    if default_log_file:
        if not os.path.exists(default_log_file):
            raise FileNotFoundError(f"Default log file not found at: {default_log_file}")

        print(f"failed to guess log file, using default: {default_log_file}")
        return default_log_file

    raise RuntimeError("Path of Exile process not found and no default log file configured.")

apply_xp_snapshot = _tracker.apply_xp_snapshot
in_hideout = _tracker.in_hideout
in_map = _tracker.in_map

def get_recent_maps():
    return _tracker.recent_maps

def get_recent_xp_snapshots():
    return _tracker.recent_xp_snapshots

def get_recent_encounters():
    return _recent_encounters

def get_current_map():
    return _tracker.get_current_map()

def parse_all_maps_from_log(log_file=None):
    if not log_file:
        log_file = find_poe_logfile()

    with open(log_file, "r", encoding="utf-8") as f:
        f.seek(0)
        temp_tracker = InstanceTracker()
        completed_maps = []
        def on_map_completed(event):
            nonlocal completed_maps
            completed_maps.append(event["map"])
        temp_tracker.events.on("map_completed", on_map_completed)
        for line in f:
            temp_tracker.process_log_lines([line])
            for m in completed_maps:
                yield m
            completed_maps.clear()

def delete_map(map: MapInstance):
    conn.execute("DELETE FROM maps WHERE id = ?", [map.id])
    _tracker.recent_maps.remove(map)

def update_map(map: MapInstance):
    pass

def set_next_waystone(item: Item):
    if not isinstance(item, Item):
        raise TypeError("item must be an Item object")

    _tracker.set_next_waystone(item)
    _update_state(item.id, "next_waystone", item)

def add_encounter(encounter: Encounter):    
    conn.execute("INSERT INTO encounters VALUES (?, ?)", [encounter.id, encounter.to_dict()])
    _recent_encounters.append(encounter)
    events.emit("encounter_detected", {"encounter": encounter})

def init():
    _load_state()
    threading.Thread(target=_observe_log, daemon=True).start()
    threading.Thread(target=_observe_focus, daemon=True).start()
    events.on("xp_snapshot", _on_xp_snapshot)
    events.on("map_completed", _on_map_completed)
    events.on("map_entered", _on_map_entered)
    events.on("map_entered", lambda _: threading.Thread(target=_capture_ladder_data).start())

def _load_state():
    # recent maps and xp-snapshots are ordered oldest to newest, but we want the 100 most recent ones, therefore, we extendLeft
    _tracker.recent_maps.extendleft(
        MapInstance.from_row(row[0], row[1])
        for row in conn.execute("SELECT id, data FROM maps ORDER BY data->'span'->'start' DESC LIMIT 100").fetchall()
    )
    _tracker.recent_xp_snapshots.extendleft(
        XPSnapshot.from_row(row[0], row[1])
        for row in conn.execute("SELECT id, data FROM xp_snapshots ORDER BY data->'ts' DESC LIMIT 100").fetchall()
    )
    _recent_encounters.extendleft(
        Encounter.from_row(row[0], row[1])
        for row in conn.execute("SELECT id, data FROM encounters ORDER BY data->'ts' DESC LIMIT 100").fetchall()
    )
    for (id, field, data) in conn.execute("SELECT id, field, data FROM instance_manager_state").fetchall():
        if field == "current_map":
            _tracker._current_map = MapInstance.from_row(id, data)
            print(f"[Info] Loaded current map: {_tracker._current_map.map_name}")
        elif field == "next_waystone":
            _tracker.set_next_waystone(Item.from_row(data))

def _on_map_completed(event):
    m = event["map"]
    conn.execute("INSERT INTO maps VALUES (?, ?)", [m.id, m.to_dict()])

def _on_map_entered(event):
    _update_state(event["map"].id, "current_map", event["map"])

def _on_xp_snapshot(event):
    snapshot = event["snapshot"]
    conn.execute("INSERT INTO xp_snapshots VALUES (?, ?)", [snapshot.id, snapshot.to_dict()])

def _update_state(id, field, object):
    conn.execute("INSERT INTO instance_manager_state (id, field, data) VALUES (?, ?, ?) ON CONFLICT (field) DO UPDATE SET id = EXCLUDED.id, data = EXCLUDED.data", 
        [id, field, object.to_dict() if hasattr(object, "to_dict") else object])

def _observe_log():
    log_file = find_poe_logfile()
    print(f"[Monitoring Log File] {log_file}")
    _tracker.process_log_lines_rev(_read_log_rev(log_file))
    _tracker.process_log_lines(_log_updates_generator(log_file))

def _log_updates_generator(log_file):
     with open(log_file, "r", encoding="utf-8") as f:
        if not config.get("default_log_file"):
            config.update({"default_log_file": log_file})
        # Monitor the log file for new lines, ensure we start at the end of the file even if poe is not running
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            yield line

def _read_log_rev(log_file, limit=5000):
    with open(log_file, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        buf = bytearray()
        lines_found = 0
        for pos in range(file_size - 1, -1, -1):
            f.seek(pos)
            char = f.read(1)
            if char == b'\n':
                if buf:
                    yield buf[::-1].decode('utf-8')
                    buf.clear()
                    lines_found += 1
                    if lines_found >= limit:
                        break
            else:
                buf.append(char[0])

        if buf:
            yield buf[::-1].decode('utf-8')

def _observe_focus():
    if SUPPORTS_WIN32:
        while True:
            window = find_poe_window()
            if window:
                if win32gui.GetForegroundWindow() == window._hWnd:
                    _tracker.inform_interaction(datetime.now())
                    _tracker.unpause()
                else:
                    _tracker.pause()
            time.sleep(1)

def _capture_ladder_data():
    global _last_ladder_capture
    if _last_ladder_capture and datetime.now() - _last_ladder_capture < timedelta(seconds=30):
        return
    _last_ladder_capture = datetime.now()
    default_league = config.get("default_league")
    character_name = config.get("character_name")
    account_name = config.get("account_name")
    if default_league and (character_name or account_name):
        ladder_data = fetch_data(character_name=character_name, account_name=account_name, league=default_league)
        if ladder_data:
            xp = ladder_data.character.experience
            _tracker.apply_xp_snapshot(xp, source="ladder")
            events.emit("ladder_data", {"ladder_data": ladder_data})

init()