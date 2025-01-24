from datetime import datetime, timedelta
import re
import json
from item import Item
from typing import Optional
from pyee import EventEmitter
from dataclasses import dataclass
import uuid
from collections import deque

@dataclass
class XPSnapshot:
    id: str
    ts: datetime
    xp: int
    delta: int
    area_level: Optional[int] = None
    source: Optional[str] = None
    encounter_type: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.xp, int) or self.xp < 0:
            raise ValueError("xp must be a positive integer")
        if not isinstance(self.ts, datetime):
            raise ValueError("ts must be a datetime object")
        if self.encounter_type is not None and not isinstance(self.encounter_type, str):
            raise TypeError("encounter_type must be a string or None")


    def to_dict(self):
        return {
            "ts": self.ts.isoformat(),
            "xp": self.xp,
            "delta": self.delta,
            "area_level": self.area_level,
            "source": self.source,
            "encounter_type": self.encounter_type
        }
    
    @classmethod
    def from_dict(cls, id, data):
        return cls(
            id,
            ts=datetime.fromisoformat(data["ts"]),
            xp=data["xp"],
            delta=data["delta"],
            area_level=data["area_level"] if data["area_level"] else None,
            source=data["source"],
            encounter_type=data["encounter_type"]
        )

    @classmethod
    def from_row(cls, id, data):
        return cls.from_dict(id, json.loads(data))

@dataclass
class MapSpan:
    start: datetime
    end: Optional[datetime] = None
    area_entered_at: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
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
        if self.pause_time.total_seconds() < 0:
            raise ValueError("pause_time cannot be negative")
        if self.end and not isinstance(self.end, datetime):
            raise TypeError("end must be a datetime object")
        if self.end and self.end < self.start:
            raise ValueError("end time cannot be before start time")

    def map_time(self, end: datetime = None):
        if end is None:
            end = self.end
        if end is None:
            return None
        total_time = end - self.start
        return total_time - self.idle_time()

    def idle_time(self):
        return self.hideout_time + self.load_time + self.pause_time

    def add_to_load_time(self, load_time: timedelta):
        if not isinstance(load_time, timedelta):
            raise TypeError(f"load_time must be a timedelta object: {type(load_time)}")
        if load_time.total_seconds() < 0:
            raise ValueError("load_time cannot be negative")    
        self.load_time += load_time 

    def add_to_hideout_time(self, hideout_time: timedelta):
        if not isinstance(hideout_time, timedelta):
            raise TypeError(f"hideout_time must be a timedelta object: {type(hideout_time)}")
        if hideout_time.total_seconds() < 0:
            raise ValueError("hideout_time cannot be negative")
        self.hideout_time += hideout_time

    def add_to_pause_time(self, pause_time: timedelta):
        if not isinstance(pause_time, timedelta):
            raise TypeError(f"pause_time must be a timedelta object: {type(pause_time)}")
        if pause_time.total_seconds() < 0:
            raise ValueError("pause_time cannot be negative") 
        self.pause_time += pause_time

    def set_area_entered_at(self, entered_at: datetime):
        if not isinstance(entered_at, datetime):
            raise TypeError(f"entered_at must be a datetime object: {type(entered_at)}")  
        if (entered_at < self.start):
            raise ValueError("entered_at cannot be before start time")
        self.area_entered_at = entered_at

    def set_last_interaction(self, ts: datetime):
        if not isinstance(ts, datetime):
            raise TypeError(f"last_interaction must be a datetime object: {type(ts)}")
        self.last_interaction = ts

    def set_end(self, end: datetime):
        if not isinstance(end, datetime):
            raise TypeError(f"end must be a datetime object: {type(end)}")
        if (end < self.start):
            raise ValueError("end time cannot be before start time")
        self.end = end

    def to_dict(self):
        def seconds(td: timedelta):
            return td.total_seconds() if td is not None else None
        return {
            "start": self.start.isoformat(),
            "area_entered_at": self.area_entered_at.isoformat() if self.area_entered_at else None,
            "end": self.end.isoformat() if self.end else None,
            "map_time": seconds(self.map_time()),
            "hideout_time": seconds(self.hideout_time),
            "load_time": seconds(self.load_time),
            "pause_time": seconds(self.pause_time)
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            start=datetime.fromisoformat(data["start"]),
            area_entered_at=datetime.fromisoformat(data["area_entered_at"]) if data["area_entered_at"] else None,
            end=datetime.fromisoformat(data["end"]) if data["end"] else None,
            hideout_time=timedelta(seconds=data["hideout_time"]),
            load_time=timedelta(seconds=data["load_time"]),
            pause_time=timedelta(seconds=data["pause_time"])
        )

@dataclass
class AreaInfo:
    ts: datetime
    area_level: int
    map_name: str
    map_seed: int

    def is_map(self):
        return self.map_seed is not None and self.map_seed > 1

@dataclass
class MapInstance:
    id: str
    span: MapSpan
    map_name: str
    area_level: int
    seed: int
    xp_start: Optional[int] = None
    xp_gained: int = 0
    xph: int = 0
    waystone: Optional[Item] = None
    hideout_start_time: Optional[datetime] = None
    hideout_exit_time: Optional[datetime] = None
    has_boss: bool = False

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
        self.has_boss = not self.map_name.lower().endswith("noboss") or self.map_name.lower().startswith("uberboss")

    def in_hideout(self):
        return self.hideout_start_time is not None

    def map_label(self):
        map_name = re.sub(r'^Map', '', self.map_name)
        words = re.findall(r'[A-Z][a-z]*|[a-z]+', map_name)
        return ' '.join(words)

    def enter_hideout(self, ts: datetime):
        if not isinstance(ts, datetime):
            raise TypeError("ts must be a datetime object")
        self.hideout_start_time = ts
        self.hideout_exit_time = None

    def exit_hideout(self, ts: datetime):
        if not isinstance(ts, datetime):
            raise TypeError("ts must be a datetime object")
        if self.hideout_start_time:
            hideout_duration = ts - self.hideout_start_time
            self.span.add_to_hideout_time(hideout_duration)
        self.hideout_start_time = None
        self.hideout_exit_time = ts
        
    def to_dict(self):
        return {
            "span": self.span.to_dict(),
            "map_name": self.map_name,
            "map_label": self.map_label(),
            "area_level": self.area_level,
            "seed": self.seed,
            "xp_start": self.xp_start,
            "xp_gained": self.xp_gained,
            "xph": self.xph,
            "waystone": self.waystone.to_dict() if self.waystone else None,
            "hideout_start_time": self.hideout_start_time.isoformat() if self.hideout_start_time else None,
            "hideout_exit_time": self.hideout_exit_time.isoformat() if self.hideout_exit_time else None,
            "has_boss": self.has_boss
        }
    
    @classmethod
    def from_dict(cls, id, data):
        return cls( 
            id,
            span=MapSpan.from_dict(data["span"]),
            map_name=data["map_name"],
            area_level=data["area_level"],
            seed=data["seed"],
            xp_start=data["xp_start"],
            xp_gained=data["xp_gained"],
            xph=data["xph"],
            waystone=Item.from_dict(data["waystone"]) if data["waystone"] else None,
            hideout_start_time=datetime.fromisoformat(data["hideout_start_time"]) if data["hideout_start_time"] else None,
            hideout_exit_time=datetime.fromisoformat(data["hideout_exit_time"]) if data["hideout_exit_time"] else None,
            has_boss=data["has_boss"] if data["has_boss"] else False
        )

    @classmethod
    def from_row(cls, id, data):
        return cls.from_dict(id, json.loads(data))


TS_PATTERN = r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
TS_REGEX = re.compile(TS_PATTERN)
MAP_ENTRY_REGEX = re.compile(rf"{TS_PATTERN}.*?Generating level (\d+) area \"(.+?)\"(?:.*seed (\d+))?", re.IGNORECASE)
POST_LOAD_REGEX = re.compile(rf"{TS_PATTERN}.*?\[SHADER\] Delay:", re.IGNORECASE)
STALE_MAP_THRESHOLD = timedelta(hours=6)

class InstanceTracker:
    def __init__(self):
        self.events = EventEmitter()
        self.recent_maps = deque(maxlen=100)
        self.recent_xp_snapshots = deque(maxlen=100)
        self._current_map = None
        self._next_waystone = None
        self._paused_at = None

    def process_log_lines_rev(self, reverse_lines):
        """
        Process log lines in reverse and look for the first area match. used to catch up
        """
        lines = []
        for line in reverse_lines:
            lines.append(line)
            if MAP_ENTRY_REGEX.search(line):
                break
        self.process_log_lines(reversed(lines))

    def process_log_lines(self, lines):
        """
        Process log lines from poe's Client.txt
        """
        for line in lines:
            map_match = MAP_ENTRY_REGEX.search(line)
            if not map_match:
                if self._current_map:
                    ts_match = TS_REGEX.search(line)
                    if ts_match:
                        self.inform_interaction(datetime.strptime(ts_match.group(1), "%Y/%m/%d %H:%M:%S"))
                continue
            else:
                post_load_match = POST_LOAD_REGEX.search(line)
                if post_load_match:
                    post_load_ts = datetime.strptime(map_match.group(1), "%Y/%m/%d %H:%M:%S")
                    if self._current_map:
                        entered_at = self._current_map.span.area_entered_at
                        load_delta = post_load_ts - entered_at
                        if (load_delta >= 0):
                            self._current_map.span.add_to_load_time(load_delta)
                        else:
                            print(f"[Warning] load_delta is negative: {load_delta}")
                    self.events.emit("area_post_load", {"load_delta": load_delta})

            area_entered_ts = datetime.strptime(map_match.group(1), "%Y/%m/%d %H:%M:%S")
            area_level = int(map_match.group(2))
            map_name = map_match.group(3)
            map_seed = int(map_match.group(4)) if map_match.group(3) else None
            self.enter_area(AreaInfo(area_entered_ts, area_level, map_name, map_seed))

    def enter_area(self, area_info: AreaInfo):
        if not isinstance(area_info, AreaInfo):
            raise TypeError("area_info must be an AreaInfo object")

        current_map = self._current_map
        if current_map and area_info.ts <= current_map.span.start and current_map.seed != area_info.map_seed:
            raise ValueError(f"new areas must be entered in chronological order: {area_info.ts} <= {current_map.span.start}")

        if current_map and current_map.seed != area_info.map_seed:
            # stale map handling - always happens for the last map of a session, because normally the termination of a map
            # is recognized by the player entering a new map that has a different seed
            map_time = current_map.span.map_time(area_info.ts)
            end_time = None
            if map_time > STALE_MAP_THRESHOLD:
                if current_map.hideout_start_time:
                    # player exited client while in hideout
                    end_time = current_map.hideout_start_time
                else:
                    # player exited client while in map
                    last_interaction = current_map.span.last_interaction
                    if last_interaction:
                        if last_interaction >= current_map.span.start:
                            end_time = last_interaction
                        else:
                            print(f"[Warn] unable to determine stale map's end_time: {current_map}")
                            end_time = area_info.ts
                    elif current_map.hideout_start_time:
                        end_time = current_map.hideout_start_time
                    else:
                        print(f"[Warn] unable to determine stale map's end_time: {current_map}")
                        end_time = area_info.ts
                self._complete_current_map(end_time)
                current_map = self._current_map = None

        self.events.emit("area_entered", {"area_info": area_info})
        if not area_info.is_map():
            if current_map:
                current_map.enter_hideout(area_info.ts)
                self.events.emit("hideout_entered", {"map": current_map})
            return

        if current_map:
            current_map.span.set_area_entered_at(area_info.ts)
            if current_map.in_hideout:
                current_map.exit_hideout(area_info.ts)
                self.events.emit("hideout_exited", {"map": current_map})
            if area_info.map_seed == current_map.seed:
                self.events.emit("map_reentered", {"map": current_map})
                return

        if current_map:
            # player entered a map with a different seed, this can be inaccurate if player enters a map of another party member
            self._complete_current_map(area_info.ts)

        initial_xp = self.recent_xp_snapshots[-1].xp if self.recent_xp_snapshots else None
        previous_map = current_map
        self._current_map = MapInstance(
            id=str(uuid.uuid4()),
            span=MapSpan(start=area_info.ts), 
            map_name=area_info.map_name, 
            area_level=area_info.area_level, 
            seed=area_info.map_seed, 
            xp_start = initial_xp,
            waystone = self._next_waystone
        )
        self._next_waystone = None
        self.events.emit("map_entered", {"map": self._current_map, "previous_map": previous_map})

    def set_next_waystone(self, item: Item):
        if not isinstance(item, Item):
            raise TypeError("item must be an Item object")

        self._next_waystone = item

    def inform_interaction(self, ts: datetime):
        if self.in_map():
            self._current_map.span.set_last_interaction(ts)

    def pause(self):
        if self.in_map() and not self._paused_at:
            self._paused_at = datetime.now()

    def unpause(self):
        if not self._paused_at:
            return
        if self.in_map():
            self._current_map.span.add_to_pause_time(datetime.now() - self._paused_at)
            print(f"[Info] Unpaused with delta {datetime.now() - self._paused_at}")
        else:
            hideout_start_time = self._current_map.hideout_start_time if self._current_map else None
            if hideout_start_time:
                # don't double dip and don't count time during hideout as pause time, count it as hideout time
                self._current_map.span.add_to_pause_time(hideout_start_time - self._paused_at)
        self._paused_at = None

    def _complete_current_map(self, end_time: datetime):
        current_map = self._current_map
        if not current_map:
            raise ValueError("no current map to complete")
        xp_end = self.recent_xp_snapshots[-1].xp if self.recent_xp_snapshots else None
        current_map.xp_gained = (xp_end - current_map.xp_start) if xp_end and current_map.xp_start else 0
        current_map.span.set_end(end_time)
        current_map.xph = current_map.xp_gained / current_map.span.map_time().total_seconds() * 3600
        self.recent_maps.append(current_map)
        self.events.emit("map_completed", {"map": current_map})

    def get_current_map(self) -> Optional[MapInstance]:
        return self._current_map

    def in_hideout(self) -> bool:
        """
        returns true if the player isn't currently in amap
        """
        return self._current_map.in_hideout() if self._current_map else True

    def in_map(self) -> bool:
        """
        returns true if the player is currently in a map
        """
        return not self.in_hideout()

    def apply_xp_snapshot(self, xp: int, ts: datetime = None, source: str = None, encounter_type: str = None) -> XPSnapshot:
        if ts is None:
            ts = datetime.now()
        if not isinstance(xp, int) or xp < 0:
            raise ValueError("xp must be a positive integer")
        if not isinstance(ts, datetime):
            raise ValueError("ts must be a datetime object")
        if encounter_type is not None and not isinstance(encounter_type, str):
            raise TypeError("encounter_type must be a string or None")

        prev = self.recent_xp_snapshots[-1] if self.recent_xp_snapshots else None
        prev_xp = prev.xp if prev else None
        delta = xp - prev_xp if prev_xp else 0
        if source == "ladder" and prev:
            if prev.source != source and delta < 0 and (prev.ts - ts).total_seconds() <= 300: 
                print(f"[Info] skipping ladder XP snapshot with negative delta (prev was non-ladder), delta: {delta}")
                return
        
        current_map = self._current_map
        area_level = current_map.area_level if current_map else None
        snapshot = XPSnapshot(str(uuid.uuid4()), ts, xp, delta, area_level, source, encounter_type)
        self.recent_xp_snapshots.append(snapshot)
        self.events.emit("xp_snapshot", {"snapshot": snapshot})

        if current_map:
            if current_map.xp_start:
                xp_gained = (xp - current_map.xp_start) if xp else 0
                current_map.xp_gained = xp_gained
            else:
                delta = ts - current_map.span.start - current_map.span.idle_time()
                # grace period if user takes snapshot after entering map
                if delta.total_seconds() <= 30:
                    current_map.xp_start = xp

        return snapshot
