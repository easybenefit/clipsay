"""Streamlit session session initialization for the Clipsay console.

Centralizes the default values for ``st.session_state`` so every entry
point (the home grid, the production page, the input form, the results
view, the in-app settings popup) reads from a single source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
import yaml


_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
_I2V_SETTINGS_PATH = os.path.join(_PROJECT_ROOT, "configs", "i2v_settings.yaml")


DEFAULTS: dict[str, object] = {
    "config_path": "",
    "config_data": None,
    "pipeline_running": False,
    "progress": None,
    "final_video": None,
    "error": None,
    "error_tb": None,
    "working_dir": "",
    "idea": "",
    "user_requirement": "",
    "style": "Realistic",
    "force_regenerate": False,
    "nav_page": "App",
    "current_clip_id": "",
    "chat_model": None,
    "story_output": "",
    "characters_output": "",
    "script_output": "",
    "portraits_output": "",
    "portraits_images": {},
    "i2v_settings": None,
    "i2v_chat_model": {},
    "i2v_image_model": {},
    "i2v_video_model": {},
}


def init() -> None:
    """Set every key in :data:`DEFAULTS` if not already set."""
    for key, default in DEFAULTS.items():
        st.session_state.setdefault(key, default)


def load_i2v_settings() -> None:
    """Load the per-user model selection from ``configs/i2v_settings.yaml``.

    On first run the file is missing; we leave the in-memory dictionaries
    empty and let the in-app settings popup seed them.  On subsequent
    runs the file's three ``default_name`` entries are resolved into the
    ``i2v_chat_model`` / ``i2v_image_model`` / ``i2v_video_model``
    dictionaries.
    """
    if not os.path.exists(_I2V_SETTINGS_PATH):
        return
    with open(_I2V_SETTINGS_PATH) as f:
        settings = yaml.safe_load(f)
    if settings is None:
        return
    st.session_state.i2v_settings = settings
    for key, list_key, cfg_key in [
        ("chat_model", "chat_models", "i2v_chat_model"),
        ("image_model", "image_models", "i2v_image_model"),
        ("video_model", "video_models", "i2v_video_model"),
    ]:
        default_name = settings.get(key, "")
        for m in settings.get(list_key, []):
            if m.get("model") == default_name:
                st.session_state[cfg_key] = m
                break
        else:
            st.session_state[cfg_key] = {}


def project_root() -> str:
    """Return the absolute project root (for ad-hoc path joins)."""
    return _PROJECT_ROOT
