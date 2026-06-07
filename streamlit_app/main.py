"""Clipsay Streamlit console — entry point.

Run with::

    uv run streamlit run streamlit_app/main.py

The entry point's only job is page configuration, global CSS injection,
in-app settings wiring, and dispatching to one of the four pages:

* ``App``        — the home grid of clips.
* ``Input``      — the pipeline input form.
* ``Results``    — the live-progress + final-video view.
* ``Production`` — the per-clip console with timeline and gallery.

Page routing uses the ``nav_page`` session-session key.  Production-page
deeps links (e.g. from a clip thumbnail) come in via ``?nav=clip&id=...``
and are translated to ``nav_page="Production"`` + ``current_clip_id``
before the page renders.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Force no proxy for all HTTP clients — the in-app models call out to
# provider APIs that don't sit behind a corporate proxy.
for _key in (
    "HTTP_PROXY", "HTTPS_PROXY",
    "http_proxy", "https_proxy",
    "ALL_PROXY", "all_proxy",
):
    os.environ.pop(_key, None)

import streamlit as st

from streamlit_app import session
from streamlit_app.widgets import gallery, production, settings
from streamlit_app.theme import (
    CLIP_GRID_CSS,
    GLOBAL_CSS,
    PRODUCTION_CSS,
    SETTINGS_PANEL_CSS,
)


st.set_page_config(
    page_title="Clipsay",
    page_icon="clipsay",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── One-time initialization ──

session.init()
session.load_i2v_settings()


# ── Global CSS ──

st.html(f"<style>{GLOBAL_CSS}{CLIP_GRID_CSS}{SETTINGS_PANEL_CSS}{PRODUCTION_CSS}</style>")


# ── Settings popup ──

settings.render()
settings.handle_save_from_query_params()
settings.handle_close_query_param()


# ── Sidebar navigation (hidden on home page) ──

NAV_OPTIONS = ("App", "Input", "Results", "Production")


if st.session_state.nav_page != "App":
    st.sidebar.title("Home")
    current_idx = NAV_OPTIONS.index(st.session_state.nav_page) if st.session_state.nav_page in NAV_OPTIONS else 0
    selected = st.sidebar.radio("Go to", NAV_OPTIONS, index=current_idx, key="sidebar_nav")
    st.session_state.nav_page = selected


# ── Translate query-string deep links to session session ──

nav_query = st.query_params.get("nav")
if nav_query:
    if nav_query in NAV_OPTIONS:
        st.session_state.nav_page = nav_query
    clip_id = st.query_params.get("id")
    if clip_id:
        st.session_state.current_clip_id = clip_id


# ── Page dispatch ──

page = st.session_state.nav_page

if page == "App":
    gallery.render()
elif page == "Input":
    from streamlit_app.pages.idea import render as render_input
    render_input()
elif page == "Results":
    from streamlit_app.pages.output import render as render_results
    render_results()
elif page == "Production":
    production.render()
else:
    st.session_state.nav_page = "App"
    st.rerun()
