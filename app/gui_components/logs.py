import tkinter as tk
from tkinter import ttk
from poe_bridge import find_poe_logfile

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