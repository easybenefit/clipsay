"""The home page — a grid of clip thumbnails with a "create new" tile.

The grid is rendered as static HTML/CSS so it can include a real
``<a href="?nav=clip&id=...">`` link (the ``st.page_link`` widget doesn't
support query strings).  The :class:`Clip` records are persisted to
``clips_index.json`` under ``.working_dir/clips/`` by :class:`ClipStore`.
"""

from __future__ import annotations

import os

import streamlit as st

from schemas.clip import Clip, ClipStore
from streamlit_app.session import project_root


def _store_path() -> str:
    return os.path.join(project_root(), ".working_dir", "clips", "clips_index.json")


def _gradients() -> list[str]:
    return [
        "linear-gradient(135deg,#1a1a2e,#16213e)",
        "linear-gradient(135deg,#0f3460,#533483)",
        "linear-gradient(135deg,#2b1b3d,#1a1a2e)",
        "linear-gradient(135deg,#16213e,#0f3460)",
        "linear-gradient(135deg,#533483,#1a1a2e)",
        "linear-gradient(135deg,#1a1a2e,#2b1b3d)",
        "linear-gradient(135deg,#0f3460,#533483)",
        "linear-gradient(135deg,#2b1b3d,#16213e)",
        "linear-gradient(135deg,#16213e,#1a1a2e)",
    ]


def render() -> None:
    st.title("Clipsay")
    st.markdown("Just say it, Clipsay makes it")

    has_run = st.session_state.get("final_video") or st.session_state.get("error")
    if has_run:
        if st.session_state.get("final_video"):
            st.success(f"Video generated: `{st.session_state.final_video}`")
        if st.session_state.get("error"):
            st.error(f"Failed: {st.session_state.error}")

    store = ClipStore(_store_path())
    clips = store.load()

    next_id = (max(c.id for c in clips) + 1) if clips else 1
    new_clip = Clip(id=next_id, title="Create New Idea", status="new")
    display = [new_clip] + clips

    gradients = _gradients()
    cells = []
    for i, c in enumerate(display):
        bg = gradients[i % len(gradients)]
        status = c.status if c else "cancel"
        play = "+" if status == "new" else "▶"
        title = c.title if c else ""
        cells.append(
            f'<div class="clipsay-item">'
            f'<a class="clipsay-cell{" clipsay-cell-new" if status == "new" else ""}" '
            f'href="?nav=clip&id={c.id}">'
            f'<div class="clipsay-thumb" style="background:{bg}">'
            f'<div class="clipsay-play">{play}</div>'
            f'</div></a>'
            f'<div class="clipsay-meta">'
            f'<span class="clipsay-dot {status}"></span>'
            f'<span class="clipsay-title">{title}</span>'
            f'</div></div>'
        )

    st.html(f'<div class="clipsay-grid">{"".join(cells)}</div>')
