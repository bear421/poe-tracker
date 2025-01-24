import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import traceback
from db import conn
from settings import config_manager
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

class ConfigFrame(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.capturing_hotkey = False
        self.current_modifiers = set()
        style = ttk.Style()
        style.configure('Error.TEntry', fieldbackground='#ffd1d1')
        self.create_fields()


    def on_field_change(self, key, widget, value_type):
        try:
            if isinstance(widget, tk.BooleanVar):
                value = widget.get()
            else:
                value = value_type(widget.get())
            
            config_manager.validate(key, value)
            config_manager.update({key: value})
            
            if not isinstance(widget, tk.BooleanVar):
                widget.configure(style='TEntry')
        except Exception as e:
            print(f"[Config Error] {key}: {str(e)}")
            if not isinstance(widget, tk.BooleanVar):
                widget.configure(style='Error.TEntry')

    def create_fields(self):
        current_config = config_manager.get_all()
        meta = config_manager.meta

        for row, (key, cfg_meta) in enumerate(meta.items()):
            label_text = cfg_meta.get('label', key.replace('_', ' ').title())
            ttk.Label(self, text=label_text).grid(row=row, column=0, padx=5, pady=5, sticky="w")
            
            value_type = cfg_meta.get('type', str)
            current_value = current_config.get(key, cfg_meta.get('default', ''))
            
            if value_type == bool:
                self.create_bool_field(row, key, current_value)
            elif value_type == "hotkey":
                self.create_hotkey_field(row, key, current_value)
            else:
                self.create_text_field(row, key, current_value, value_type)

            if 'error_msg' in cfg_meta:
                ttk.Label(self, text="ℹ️").grid(row=row, column=2, padx=2, pady=5)

    def create_bool_field(self, row, key, current_value):
        var = tk.BooleanVar(value=current_value)
        checkbox = ttk.Checkbutton(
            self,
            variable=var,
            command=lambda: self.on_field_change(key, var, bool)
        )
        checkbox.grid(row=row, column=1, padx=5, pady=5, sticky="w")

    def create_text_field(self, row, key, current_value, value_type):
        entry = ttk.Entry(self)
        entry.insert(0, str(current_value))
        entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        entry.bind('<FocusOut>', lambda e: self.on_field_change(key, entry, value_type))

    def create_hotkey_field(self, row, key, current_value):
        hotkey_frame = ttk.Frame(self)
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
                    config_manager.update({key: current_value})
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