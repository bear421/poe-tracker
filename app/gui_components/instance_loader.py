import time
import threading
import tkinter as tk
import pandas as pd
from poe_bridge import parse_all_maps_from_log
import poe_bridge
from db import conn

class InstanceLoader:
    def __init__(self):
        self.n = 0
        self.running = True
        self.stop = False
        self.modal = None

    def load_instance_data_from_log(self):
        if self.stop:
            raise Exception("loader stopped, cannot resume")

        try:
            buf = []
            for instance in parse_all_maps_from_log():
                if self.stop:
                    return
                self.n += 1
                buf.append([instance.id, instance.to_dict()])
                if len(buf) >= 1000:
                    df = pd.DataFrame(buf, columns=["id", "data"])
                    conn.register("_pd_buf_table", df)
                    conn.execute("INSERT INTO maps SELECT * FROM _pd_buf_table")
                    buf.clear()
            if buf:
                conn.executemany("INSERT INTO maps VALUES (?, ?)", buf)
            # FIXME handle current_map properly (?)
            poe_bridge._load_state()
        finally:
            self.running = False

    def cancel(self):
        self.stop = True
        if self.modal:
            self.modal.destroy()

    def show_modal(self, frame):
        start = time.perf_counter()
        threading.Thread(target=self.load_instance_data_from_log).start()
        root = frame.winfo_toplevel()
        self.modal = modal = tk.Toplevel(root)
        modal.title("Loading Instances")
        modal.transient(root)
        modal.grab_set()  # Disable interaction with the main window
        modal.protocol("WM_DELETE_WINDOW", lambda: None) # Disable the close button by overriding the close protocol

        root.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() // 2) - (300 // 2)
        y = root.winfo_y() + (root.winfo_height() // 2) - (150 // 2)
        modal.geometry(f"300x150+{x}+{y}")

        label = tk.Label(modal, text="Parsing log ...", font=("Helvetica", 12))
        label.pack(pady=10)

        count_label = tk.Label(modal, text="Loaded: 0 instances", font=("Helvetica", 10))
        count_label.pack(pady=10)

        button_frame = tk.Frame(modal)
        button_frame.pack(pady=10)

        ok_button = tk.Button(
            button_frame,
            text="OK",
            command=modal.destroy,
            state=tk.DISABLED,
            width=10,
            bg="lightgreen",
            font=("Helvetica", 10, "bold")
        )
        ok_button.grid(row=0, column=0, padx=5)

        cancel_button = tk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel,
            width=10,
            bg="lightcoral",
            font=("Helvetica", 10, "bold")
        )
        cancel_button.grid(row=0, column=1, padx=5)

        def update_count():
            took = time.perf_counter() - start
            count_label.config(text=f"Loaded: {self.n} instances in {took:.2f} seconds")
            if self.running: 
                modal.after(100, update_count)
            else:
                label.config(text="Done!")
                modal.protocol("WM_DELETE_WINDOW", modal.destroy)
                ok_button.config(state=tk.NORMAL)
                cancel_button.config(state=tk.DISABLED)

        update_count()
        root.wait_window(modal)

