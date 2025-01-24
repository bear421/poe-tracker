import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from db import conn
from poe_bridge import _tracker
from gui_components.logs import LogViewer
import math
import random
from poe_bridge import get_recent_xp_snapshots
from gui_components.instance_loader import InstanceLoader

class DebugFrame(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        xp_frame = ttk.LabelFrame(self, text="Debug apply_xp_snapshot")
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
                _tracker.apply_xp_snapshot(xp, timestamp)
            except ValueError as e:
                print(f"[Debug Error] Invalid input: {e}")

        ttk.Button(xp_frame, text="XP Snapshot", command=test_xp_snapshot).grid(row=2, column=0, columnspan=2, pady=10)

        def random_xp_snapshot():
            pass
            xp = random.randint(1000000000, 1000000000000000000)
            timestamp = datetime.now() - timedelta(days=random.randint(0, 30))
            _tracker.apply_xp_snapshot(xp, timestamp)

        ttk.Button(xp_frame, text="Random XP Snapshot", command=random_xp_snapshot).grid(row=2, column=1, columnspan=2, pady=10)

        # Enter Area Form
        area_frame = ttk.LabelFrame(self, text="Debug enter_area")
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
                _tracker.enter_area(timestamp, area_level, area_name, seed)
            except ValueError as e:
                print(f"[Debug Error] Invalid input: {e}")

        ttk.Button(area_frame, text="Test Enter Area", command=test_enter_area).grid(row=3, column=0, columnspan=2, pady=10)

        # Log Viewer Button
        log_frame = ttk.LabelFrame(self, text="Advanced")
        log_frame.pack(fill=tk.X, padx=5, pady=5)

        button_frame = ttk.Frame(log_frame)
        button_frame.pack(pady=5)

        ttk.Button(button_frame, text="Open Log Viewer", command=self.open_log_viewer).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show XP Snapshots", command=self.show_snapshots_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Import Instance Data", command=self.load_instance_data_from_log).pack(side=tk.LEFT, padx=5)

    def open_log_viewer(self):
        LogViewer(self.winfo_toplevel())

    def show_snapshots_data(self):
        data_window = tk.Toplevel(self.winfo_toplevel())
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
        for idx, snapshot in enumerate(get_recent_xp_snapshots()):
            tree.insert("", tk.END, values=(
                idx,
                snapshot.ts,
                f"{snapshot.xp:,}",
                snapshot.encounter_type
            ))

    def load_instance_data_from_log(self):
        loader = InstanceLoader()
        loader.show_modal(self)