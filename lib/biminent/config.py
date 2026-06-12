# -*- coding: utf-8 -*-
"""Per-tool JSON settings, stored under %APPDATA%/Biminent/Tools/<tool>.json.

Mirrors the ConfigurationManager convention of the C# products
(%APPDATA%/Biminent/<Product>), so all Biminent settings live together.
"""
import json
import os


def _settings_dir():
    root = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(root, "Biminent", "Tools")


def load(tool_name, default=None):
    """Load the settings dict for a tool, or `default` if none saved yet."""
    path = os.path.join(_settings_dir(), tool_name + ".json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def save(tool_name, data):
    """Persist the settings dict for a tool."""
    folder = _settings_dir()
    if not os.path.isdir(folder):
        os.makedirs(folder)
    path = os.path.join(folder, tool_name + ".json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
