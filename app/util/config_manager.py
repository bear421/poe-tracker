import json
import os

class ConfigManager:

    def __init__(self, path="config.json", meta=None):
        self.path = path
        self.meta = meta or {}
        self.cache = None
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                self.cache = json.load(f)
        else:
            self.cache = {}

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.cache, f, indent=4)

    def get(self, key, default=None):
        value = self.cache.get(key, default)
        if value is not None: return value
        
        return self.meta.get(key, {}).get("default", default)

    def get_all(self):
        return self.cache

    def validate(self, key, value):
        """Validate a single key-value pair against metadata rules"""
        if key not in self.meta: return

        rules = self.meta[key]
        if "required" in rules and rules["required"] and value is None:
            raise ValueError(f"Key '{key}' is required")
        if "type_validator" in rules and callable(rules["type_validator"]):
            if not rules["type_validator"](value):
                error_msg = rules.get("error_msg", f"Validation failed for key '{key}'")
                raise ValueError(error_msg)
        elif "type" in rules and not isinstance(value, rules["type"]):
            raise ValueError(f"Key '{key}' must be of type {rules['type'].__name__}")
        if "validator" in rules and callable(rules["validator"]):
            if not rules["validator"](value):
                error_msg = rules.get("error_msg", f"Validation failed for key '{key}'")
                raise ValueError(error_msg)

    def update(self, updates):
        for key, value in updates.items():
            self.validate(key, value)
        self.cache.update(updates)
        self.save()
