import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import re
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from instance_tracker import (
    get_current_map,
    apply_xp_snapshot,
    enter_area,
    xp_snapshots,
    config_manager,
    find_poe_logfile
)
import math
import random
import traceback

class XPTrackerGUI:

    def __init__(self, capture_callback):
        self.root = tk.Tk()
        self.root.title("PoE XP Tracker")
        self.root.geometry("1000x600")
        
        self.map_table = None
        self.stats_table = None
        self.overview_frame = None
        self.current_tab = None
        
        self.capture_callback = capture_callback
        self.create_gui()
        self.current_modifiers = set()
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )

    def create_gui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Maps Tab
        maps_tab = ttk.Frame(notebook)
        notebook.add(maps_tab, text="Maps")
        self.create_maps_tab(maps_tab)

        # Stats Tab
        stats_tab = ttk.Frame(notebook)
        notebook.add(stats_tab, text="Stats")
        self.create_stats_tab(stats_tab)

        # Overview Tab
        self.overview_frame = ttk.Frame(notebook)
        notebook.add(self.overview_frame, text="Overview")

        # Config Tab
        config_tab = ttk.Frame(notebook)
        notebook.add(config_tab, text="Config")
        self.create_config_tab(config_tab)

        # Debug Tab
        debug_tab = ttk.Frame(notebook)
        notebook.add(debug_tab, text="Debug")
        self.create_debug_tab(debug_tab)

        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()

        notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

    def create_maps_tab(self, parent):
        columns = ("#", "Map Name", "XP Gained", "XP/hour", "Area Level", "Duration")
        self.map_table = ttk.Treeview(parent, columns=columns, show="headings")

        for col in columns:
            self.map_table.heading(col, text=col, anchor="w")

        self.map_table.column("#", anchor="e", width=5)
        self.map_table.column("Map Name", anchor="w", width=150)
        self.map_table.column("XP Gained", anchor="e", width=60)
        self.map_table.column("XP/hour", anchor="e", width=60)
        self.map_table.column("Area Level", anchor="e", width=40)
        self.map_table.column("Duration", anchor="e", width=60)

        self.map_table.pack(fill=tk.BOTH, expand=True)

    def create_stats_tab(self, parent):
        stats_columns = ("Map Name", "Count", "Total XP", "Average XPH")
        self.stats_table = ttk.Treeview(parent, columns=stats_columns, show="headings")
        
        for col in stats_columns:
            self.stats_table.heading(col, text=col)
            self.stats_table.column(col, anchor="center")
            
        self.stats_table.pack(fill=tk.BOTH, expand=True)

    def create_debug_tab(self, parent):
        # XP Snapshot Form
        xp_frame = ttk.LabelFrame(parent, text="Debug apply_xp_snapshot")
        xp_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(xp_frame, text="XP Value:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        xp_entry = ttk.Entry(xp_frame)
        xp_entry.insert(0, "3939232944")
        xp_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(xp_frame, text="Timestamp (YYYY-MM-DD HH:MM:SS):").grid(row=1, column=0, padx=5, pady=5)
        timestamp_entry = ttk.Entry(xp_frame)
        timestamp_entry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        timestamp_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        def test_xp_snapshot():
            try:
                xp = int(xp_entry.get())
                timestamp = datetime.strptime(timestamp_entry.get(), "%Y-%m-%d %H:%M:%S")
                apply_xp_snapshot(xp, timestamp)
            except ValueError as e:
                print(f"[Debug Error] Invalid input: {e}")

        ttk.Button(xp_frame, text="Test XP Snapshot", command=test_xp_snapshot).grid(row=2, column=0, columnspan=2, pady=10)

        # Enter Area Form
        area_frame = ttk.LabelFrame(parent, text="Debug enter_area")
        area_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(area_frame, text="Area Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        area_entry = ttk.Entry(area_frame)
        area_entry.insert(0, "Augury")
        area_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(area_frame, text="Area Level:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        level_entry = ttk.Entry(area_frame)
        level_entry.insert(0, "80")
        level_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(area_frame, text="Timestamp (YYYY-MM-DD HH:MM:SS):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        area_timestamp_entry = ttk.Entry(area_frame)
        area_timestamp_entry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        area_timestamp_entry.grid(row=2, column=1, padx=5, pady=5)

        def test_enter_area():
            try:
                area_name = area_entry.get()
                area_level = int(level_entry.get()) if level_entry.get() else None
                timestamp = datetime.strptime(area_timestamp_entry.get(), "%Y-%m-%d %H:%M:%S")  
                seed = int(math.floor(random.random() * 10000000))
                enter_area(timestamp, area_level, area_name, seed)
            except ValueError as e:
                print(f"[Debug Error] Invalid input: {e}")

        ttk.Button(area_frame, text="Test Enter Area", command=test_enter_area).grid(row=3, column=0, columnspan=2, pady=10)

        # Log Viewer Button
        log_frame = ttk.LabelFrame(parent, text="Advanced")
        log_frame.pack(fill=tk.X, padx=5, pady=5)

        def open_log_viewer():
            LogViewer(self.root)

        def show_maps_data():
            data_window = tk.Toplevel(self.root)
            data_window.title("Maps Run Data")
            data_window.geometry("800x600")
            
            # Create notebook for tabs
            notebook = ttk.Notebook(data_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Current Map Tab
            current_map_frame = ttk.Frame(notebook)
            notebook.add(current_map_frame, text="Current Map")
            
            # Create Treeview for current map details
            current_map_tree = ttk.Treeview(current_map_frame, columns=("Value",), show="headings")
            current_map_tree.heading("Value", text="Value")
            current_map_tree.column("Value", width=400)
            
            # Add scrollbar
            scrollbar = ttk.Scrollbar(current_map_frame, orient=tk.VERTICAL, command=current_map_tree.yview)
            current_map_tree.configure(yscrollcommand=scrollbar.set)
            
            # Pack widgets
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            current_map_tree.pack(fill=tk.BOTH, expand=True)
            
            # Get current map data
            current_map = get_current_map()
            if current_map:
                attrs = vars(current_map)
                for key, value in attrs.items():
                    current_map_tree.insert("", tk.END, values=(f"{key}: {value}",))
            else:
                current_map_tree.insert("", tk.END, values=("No current map data",))
            
            # Raw Data Tab
            raw_frame = ttk.Frame(notebook)
            notebook.add(raw_frame, text="Raw Data")
            
            text_widget = tk.Text(raw_frame, wrap=tk.NONE)
            scrollbar_y = ttk.Scrollbar(raw_frame, orient="vertical", command=text_widget.yview)
            scrollbar_x = ttk.Scrollbar(raw_frame, orient="horizontal", command=text_widget.xview)
            text_widget.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
            
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
            scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            text_widget.insert(tk.END, str(vars(current_map)) if current_map else "No map data")

        def show_snapshots_data():
            data_window = tk.Toplevel(self.root)
            data_window.title("XP Snapshots Data")
            data_window.geometry("800x600")
            
            # Create Treeview
            columns = ("Index", "Timestamp", "XP", "Encounter Type")
            tree = ttk.Treeview(data_window, columns=columns, show="headings")
            
            # Configure columns
            tree.heading("Index", text="#")
            tree.heading("Timestamp", text="Timestamp")
            tree.heading("XP", text="XP")
            tree.heading("Encounter Type", text="Encounter Type")
            
            tree.column("Index", width=50, anchor="center")
            tree.column("Timestamp", width=200, anchor="w")
            tree.column("XP", width=150, anchor="e")
            tree.column("Encounter Type", width=200, anchor="w")
            
            # Add scrollbars
            scrollbar_y = ttk.Scrollbar(data_window, orient=tk.VERTICAL, command=tree.yview)
            scrollbar_x = ttk.Scrollbar(data_window, orient=tk.HORIZONTAL, command=tree.xview)
            tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
            
            # Pack widgets
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
            scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Insert data
            for idx, snapshot in enumerate(xp_snapshots):
                tree.insert("", tk.END, values=(
                    idx,
                    snapshot.ts,
                    f"{snapshot.xp:,}",
                    snapshot.encounter_type
                ))

        button_frame = ttk.Frame(log_frame)
        button_frame.pack(pady=5)

        ttk.Button(button_frame, text="Open Log Viewer", command=open_log_viewer).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show Maps Data", command=show_maps_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show XP Snapshots", command=show_snapshots_data).pack(side=tk.LEFT, padx=5)

    def on_tab_change(self, event):
        self.current_tab = event.widget.tab(event.widget.index("current"))["text"]
        if self.current_tab == "Overview":
            self.periodic_overview_update()

    def periodic_overview_update(self):
        if self.current_tab == "Overview":
            self.update_overview()
            self.overview_frame.after(250, self.periodic_overview_update)

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

    def update_map_table(self, maps_run):
        for row in self.map_table.get_children():
            self.map_table.delete(row)
            
        for idx, map_data in enumerate(maps_run, start=1):
            duration_seconds = map_data.span.map_time().total_seconds()
            duration_str = str(timedelta(seconds=int(duration_seconds)))

            self.map_table.insert("", "end", values=(
                idx,
                map_data.map_name,
                f"{map_data.xp_gained:,}",
                f"{map_data.xph():,}",
                map_data.area_level,
                duration_str
            ))

    def update_stats_table(self, maps_run):
        if not self.stats_table: return
        
        stats = {}
        for map in maps_run:
            name = map.map_name
            if name not in stats:
                stats[name] = {"count": 0, "total_xp": 0, "total_xph": 0}
            stats[name]["count"] += 1
            stats[name]["total_xp"] += map.xp_gained
            stats[name]["total_xph"] += map.xph()

        for row in self.stats_table.get_children():
            self.stats_table.delete(row)

        for map_name, data in stats.items():
            avg_xph = data["total_xph"] // data["count"]
            self.stats_table.insert("", "end", values=(
                map_name, 
                data["count"], 
                f"{data['total_xp']:,}", 
                f"{avg_xph:,}"
            ))

    def update_overview(self):
        """Update the overview tab with current map and XP snapshot data."""
        try:
            # Clear the frame
            for widget in self.overview_frame.winfo_children():
                widget.destroy()

            current_map = get_current_map()
            if not current_map:
                tk.Label(self.overview_frame, text=f"No current map data to display").pack()
                return

            # Display map overview details
            map_name = current_map.map_name
            xp_gained = current_map.xp_gained
            now_or_ho = current_map.hideout_start_time if current_map.in_hideout else datetime.now()
            total_duration = (
                now_or_ho - current_map.span.start
            ).total_seconds() if current_map.span.end is None else (
                current_map.span.map_time()
            ).total_seconds()

            # Create header labels
            tk.Label(self.overview_frame, text=f"Map: {map_name}", font=("Helvetica", 12, "bold"), anchor="w").grid(row=0, column=0, sticky="w", columnspan=5)
            tk.Label(self.overview_frame, text=f"XP Gained: {xp_gained:,}", font=("Helvetica", 12), anchor="w").grid(row=1, column=0, sticky="w", columnspan=5)
            tk.Label(self.overview_frame, text=f"Duration: {str(timedelta(seconds=int(total_duration)))}", font=("Helvetica", 12), anchor="w").grid(row=2, column=0, sticky="w", columnspan=5)

            # Display the snapshots table headers
            columns = ["#", "Encounter Type", "XP", "XP/hour", "Duration"]
            for i, column in enumerate(columns):
                tk.Label(self.overview_frame, text=column, font=("Helvetica", 10, "bold"), anchor="w").grid(row=3, column=i, sticky="w" if i == 1 else "e")

            # Process snapshots
            snapshots = []
            if xp_snapshots and current_map:
                map_start_time = current_map.span.start
                for i in range(len(xp_snapshots) - 1, 0, -1):
                    if i == len(xp_snapshots) - 1:
                        # head encounter ("incomplete", xp gained unknown)
                        snapshot = xp_snapshots[i]
                        next_snapshot = None
                    else:
                        snapshot = xp_snapshots[i - 1]
                        next_snapshot = xp_snapshots[i]
                    if snapshot.ts < map_start_time: break

                    if next_snapshot:
                        duration = (next_snapshot.ts - snapshot.ts).total_seconds()
                        xp_gained = next_snapshot.xp - snapshot.xp
                    else:
                        duration = (now_or_ho - snapshot.ts).total_seconds()
                        xp_gained = 0
                    xph = (xp_gained / duration) * 3600 if duration > 0 else 0
                    snapshots.append({
                        "Encounter Type": snapshot.encounter_type,
                        "XP": xp_gained,
                        "XP/hour": int(xph),
                        "Duration": str(timedelta(seconds=int(duration)))
                    })

            #for i, row in reversed(list(enumerate(snapshots))):
            for i, row in enumerate(reversed(snapshots)):
                tk.Label(self.overview_frame, text=i + 1, anchor="e").grid(row=i + 4, column=0, sticky="e")
                tk.Label(self.overview_frame, text=row["Encounter Type"], anchor="w").grid(row=i + 4, column=1, sticky="w")
                tk.Label(self.overview_frame, text=f"{row['XP']:,}", anchor="e").grid(row=i + 4, column=2, sticky="e")
                tk.Label(self.overview_frame, text=f"{row['XP/hour']:,}", anchor="e").grid(row=i + 4, column=3, sticky="e")
                tk.Label(self.overview_frame, text=row["Duration"], anchor="e").grid(row=i + 4, column=4, sticky="e")

        except Exception as e:
            print(f"[Error in update_overview]: {str(e)}\n{traceback.format_exc()}")

    def create_config_tab(self, parent):
        # Create a frame for the config entries
        config_frame = ttk.LabelFrame(parent, text="Configuration Settings")
        config_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create a canvas and scrollbar for scrolling
        canvas = tk.Canvas(config_frame)
        scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Create config fields manager
        ConfigFields(scrollable_frame, config_manager).create_fields()

        # Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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
        self.root.mainloop()

class ConfigFields:
    def __init__(self, parent, config_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.capturing_hotkey = False
        self.current_modifiers = set()
        
        # Create error style for entry widgets
        style = ttk.Style()
        style.configure('Error.TEntry', fieldbackground='#ffd1d1')

    def on_field_change(self, key, widget, value_type):
        try:
            if isinstance(widget, tk.BooleanVar):
                value = widget.get()
            else:
                value = value_type(widget.get())
            
            self.config_manager.validate(key, value)
            self.config_manager.update({key: value})
            
            if not isinstance(widget, tk.BooleanVar):
                widget.configure(style='TEntry')
        except Exception as e:
            print(f"[Config Error] {key}: {str(e)}")
            if not isinstance(widget, tk.BooleanVar):
                widget.configure(style='Error.TEntry')

    def create_fields(self):
        current_config = self.config_manager.get_all()
        meta = self.config_manager.meta

        for row, (key, cfg_meta) in enumerate(meta.items()):
            # Create label
            label_text = cfg_meta.get('label', key.replace('_', ' ').title())
            ttk.Label(self.parent, text=label_text).grid(row=row, column=0, padx=5, pady=5, sticky="w")
            
            value_type = cfg_meta.get('type', str)
            current_value = current_config.get(key, cfg_meta.get('default', ''))
            
            if value_type == bool:
                self.create_bool_field(row, key, current_value)
            elif value_type == "hotkey":
                self.create_hotkey_field(row, key, current_value)
            else:
                self.create_text_field(row, key, current_value, value_type)

            # Add tooltip if there's an error message
            if 'error_msg' in cfg_meta:
                ttk.Label(self.parent, text="ℹ️").grid(row=row, column=2, padx=2, pady=5)

    def create_bool_field(self, row, key, current_value):
        var = tk.BooleanVar(value=current_value)
        checkbox = ttk.Checkbutton(
            self.parent,
            variable=var,
            command=lambda: self.on_field_change(key, var, bool)
        )
        checkbox.grid(row=row, column=1, padx=5, pady=5, sticky="w")

    def create_text_field(self, row, key, current_value, value_type):
        entry = ttk.Entry(self.parent)
        entry.insert(0, str(current_value))
        entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        entry.bind('<FocusOut>', lambda e: self.on_field_change(key, entry, value_type))

    def create_hotkey_field(self, row, key, current_value):
        hotkey_frame = ttk.Frame(self.parent)
        hotkey_frame.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        
        key_label = self.get_keycode_label(current_value['key_code'])

        hotkey_label = ttk.Label(hotkey_frame, text=key_label)
        hotkey_label.pack(side="left", padx=(0, 10))

        def start_capture():
            if self.capturing_hotkey:
                return
            
            self.capturing_hotkey = True
            hotkey_label.config(text="Press your desired key...")
            
            def on_key(event):
                if not self.capturing_hotkey:
                    return
                
                if event.keycode != 27:  # Escape
                    current_value = {
                        "key_code": event.keycode,
                        "modifiers": list(self.current_modifiers)
                    }
                    self.config_manager.update({key: current_value})
                self.capturing_hotkey = False
                hotkey_label.config(text=self.get_keycode_label(current_value.get('key_code', 'None')))

            hotkey_frame.bind("<KeyPress>", on_key)
            hotkey_frame.focus_set()

        ttk.Button(
            hotkey_frame,
            text="Set",
            command=start_capture
        ).pack(side="left")

    def on_key_release(self, key):
        if key in (keyboard.Key.ctrl, keyboard.Key.alt, keyboard.Key.shift):
            self.current_modifiers.discard(key)
        return True 

    def get_keycode_label(self, key_code):
        try:
            ch = KeyCode.from_vk(key_code).char
            if ch:
                return ch.upper()
        except ValueError:
            pass

        for k in Key:
            if k.value.vk == key_code:
                return k.name
                
        return chr(key_code)
        # return f"KC<{key_code}>"
        

    def format_hotkey(self, hotkey_config):
        if not hotkey_config:
            return "None"
        
        mods = "+".join(sorted(hotkey_config.get("modifiers", [])))
        key = hotkey_config.get("key", "")
        return f"{mods}+{key}" if mods else str(key)

    def update_hotkey_display(self, label):
        if self.capturing_hotkey:
            mods = "+".join(sorted(self.current_modifiers))
            display = mods + " ..." if mods else "..."
            label.config(text=display)

class LogViewer:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("Path of Exile Log Viewer")
        self.window.geometry("800x600")
        
        # Create main frame
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create Text widget with scrollbar
        self.log_text = tk.Text(main_frame, wrap=tk.NONE)
        scrollbar_y = ttk.Scrollbar(main_frame, orient="vertical", command=self.log_text.yview)
        scrollbar_x = ttk.Scrollbar(main_frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # Control frame for buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 5))

        # Refresh button
        ttk.Button(control_frame, text="Refresh", command=self.show_log_tail).pack(side=tk.LEFT, padx=5)

        # Auto-refresh checkbox
        self.auto_refresh = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            control_frame, 
            text="Auto-refresh (5s)", 
            variable=self.auto_refresh,
            command=self.toggle_auto_refresh
        ).pack(side=tk.LEFT, padx=5)

        # Pack the text widget and scrollbars
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Show initial log content
        self.show_log_tail()

    def show_log_tail(self):
        try:
            log_path = find_poe_logfile()
            if not log_path:
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(tk.END, "Could not locate Path of Exile log file.")
                return

            with open(log_path, 'r', encoding='utf-8') as f:
                # Read last 1000 lines
                lines = f.readlines()[-1000:]
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(tk.END, ''.join(lines))
                self.log_text.see(tk.END)  # Scroll to bottom
        except Exception as e:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, f"Error reading log file: {str(e)}")

    def toggle_auto_refresh(self):
        if self.auto_refresh.get():
            self.schedule_refresh()

    def schedule_refresh(self):
        if self.auto_refresh.get():
            self.show_log_tail()
            self.window.after(5000, self.schedule_refresh)