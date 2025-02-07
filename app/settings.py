from util.config_manager import ConfigManager
from pynput import keyboard

config = config_manager = ConfigManager(path="user_data/config.json", meta={
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
    "apply_ladder_xp_snapshot": {
        "label": "Apply ladder XP snapshot",
        "type": bool,
        "default": False,
        "description": "If true, will use ladder XP to create XP snapshots (typically inaccurate due to delay)"
    },
    "twitch_name": {
        "label": "Twitch name",
        "type": str
    },
    "lock_input_during_capture": {
        "label": "Lock mouse movement during capture",
        "type": bool,
        "default": False,
        "description": "Locks mouse movement for roughly 200ms during capture of item data and XP (requires admin privileges)"
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
    },
    "add_unknown_encounters_as_screenshot": {
        "label": "Add unknown encounters as screenshot",
        "type": bool,
        "default": True
    }
})