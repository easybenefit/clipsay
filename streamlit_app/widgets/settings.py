"""In-app settings popup (chat / image / video model + API key).

The popup is implemented as a pure-CSS overlay (an :class:`st.html` block
with a hidden checkbox as the toggle and the standard ``:checked`` sibling
selector to swap visibility).  Form submissions round-trip through the
query string so the popup's "Save" button works without any client-side
JavaScript.

Public surface:

* :func:`render` — emit the popup markup into the current Streamlit page.
* :func:`handle_save_from_query_params` — if a "Save" submit landed on
  the page, persist the form values back into
  ``configs/i2v_settings.yaml`` and the session session.
"""

from __future__ import annotations

import html
import os
from typing import Any

import streamlit as st
import yaml

from streamlit_app.session import project_root


_POPUP_ID = "clipsay-settings-toggle"
_CARDS = ("chat", "image", "video")


def _esc(value: Any) -> str:
    return html.escape(str(value) if value is not None else "")


def _model_options_html(models: list[dict], current: str) -> str:
    return "".join(
        f'<option{" selected" if m.get("model") == current else ""}>'
        f'{_esc(m.get("model", ""))}</option>'
        for m in models
    )


def _card_html(card: str, settings: dict) -> str:
    cfg_key = f"i2v_{card}_model"
    cfg = st.session_state.get(cfg_key, {}) or {}

    if card == "chat":
        models = settings.get("chat_models", [])
        title, desc = "Chat Model", "Language model for script generation"
    elif card == "image":
        models = settings.get("image_models", [])
        title, desc = "Image Model", "Image generation model selection"
    else:
        models = settings.get("video_models", [])
        title, desc = "Video Model", "T2V &amp; I2V model selection"

    model_opts = _model_options_html(models, cfg.get("model", ""))
    api_key = _esc(cfg.get("api_key", ""))
    base_url = _esc(cfg.get("base_url", ""))
    rl_min = cfg.get("max_requests_per_minute", "")
    rl_day = cfg.get("max_requests_per_day", "")

    return f'''
    <form action="" method="GET" class="clipsay-card">
      <input type="hidden" name="settings_card" value="{card}">
      <div class="clipsay-card-header"><span class="clipsay-card-title">{title}</span></div>
      <div class="clipsay-card-desc">{desc}</div>
      <div class="clipsay-model"><span>Model</span><select name="{card}_model_name" class="clipsay-select">{model_opts}</select></div>
      <div class="clipsay-field"><span>API Key</span><input type="password" name="{card}_api_key" class="clipsay-input" value="{api_key}"></div>
      <div class="clipsay-field"><span>Base URL</span><input type="text" name="{card}_base_url" class="clipsay-input" value="{base_url}"></div>
      <div class="clipsay-ratelimit"><span>Rate Limit</span>
        <div class="clipsay-rl-inline">
          <div class="clipsay-rl-row"><input type="text" name="{card}_rl_min" class="clipsay-input" value="{rl_min}"><span>/ min</span></div>
          <div class="clipsay-rl-row"><input type="text" name="{card}_rl_day" class="clipsay-input" value="{rl_day}"><span>/ day</span></div>
        </div>
      </div>
      <div class="clipsay-card-spacer"></div>
      <div class="clipsay-btns"><button type="submit" class="clipsay-btn clipsay-btn-save">Save</button></div>
    </form>
    '''


def render() -> None:
    """Render the settings popup markup and the trigger label.

    Reads the current model configuration from ``st.session_state`` and
    pre-fills each form field.  The actual write-back happens in
    :func:`handle_save_from_query_params` after the form re-submits.
    """
    settings = st.session_state.get("i2v_settings") or {}

    cards_html = "\n".join(_card_html(card, settings) for card in _CARDS)

    st.html(f'''
<input type="checkbox" id="{_POPUP_ID}" style="display:none">
<label for="{_POPUP_ID}" class="clipsay-settings-label">Settings</label>
<label for="{_POPUP_ID}" class="clipsay-backdrop"></label>
<div class="clipsay-popup">
  <div class="clipsay-popup-header">
    <span>Settings</span>
    <label for="{_POPUP_ID}" class="clipsay-popup-close">&times;</label>
  </div>
  <div class="clipsay-popup-grid">
    {cards_html}
  </div>
</div>
''')


def _coerce_int(value: Any) -> int | str:
    try:
        return int(value)
    except (ValueError, TypeError):
        return ""


def _i2v_settings_path() -> str:
    return os.path.join(project_root(), "configs", "i2v_settings.yaml")


def handle_save_from_query_params() -> None:
    """Persist a submitted card's form values back to ``i2v_settings.yaml``.

    No-op unless ``?settings_card=...`` is present in the query string.
    After persisting, clears the related query params and triggers
    ``st.rerun()`` so the rest of the page sees the new values.
    """
    card = st.query_params.get("settings_card")
    if not card or card not in _CARDS:
        return

    card_to_keys = {
        "chat": ("chat_model", "chat_models", "i2v_chat_model"),
        "image": ("image_model", "image_models", "i2v_image_model"),
        "video": ("video_model", "video_models", "i2v_video_model"),
    }
    default_key, list_key, cfg_key = card_to_keys[card]

    new_cfg = {
        "model": st.query_params.get(f"{card}_model_name", ""),
        "api_key": st.query_params.get(f"{card}_api_key", ""),
        "base_url": st.query_params.get(f"{card}_base_url", ""),
        "max_requests_per_minute": _coerce_int(st.query_params.get(f"{card}_rl_min", "")),
        "max_requests_per_day": _coerce_int(st.query_params.get(f"{card}_rl_day", "")),
    }

    settings = st.session_state.i2v_settings
    if settings is not None:
        settings[default_key] = new_cfg["model"]
        for m in settings.get(list_key, []):
            if m.get("model") == new_cfg["model"]:
                m.update({k: v for k, v in new_cfg.items() if v not in (None, "")})
                break
        with open(_i2v_settings_path(), "w") as f:
            yaml.dump(settings, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    st.session_state[cfg_key] = new_cfg
    st.session_state.i2v_settings = settings

    for k in list(st.query_params.keys()):
        if k.startswith(f"{card}_") or k == "settings_card":
            del st.query_params[k]
    st.rerun()


def handle_close_query_param() -> None:
    """Strip ``?settings_close=...`` from the URL and rerun."""
    if st.query_params.get("settings_close"):
        st.query_params.pop("settings_close", None)
        st.rerun()
