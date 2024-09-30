import json
import os
from pathlib import Path

CONFIG_FILE = Path.home() / '.blusoundcli.json'

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_preference(key, default=None):
    config = load_config()
    return config.get(key, default)

def set_preference(key, value):
    config = load_config()
    config[key] = value
    save_config(config)
