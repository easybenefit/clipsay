"""Input page — the form that kicks off the idea-to-video pipeline.

On submit, this page:

1. Stashes the user's idea / requirement / style into session session.
2. Optionally wipes the previous working directory (force-regenerate).
3. Spins up a :class:`ProgressTracker` and a background thread that
   runs the pipeline end-to-end.
4. Reroutes to the **Results** page for live progress updates.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import threading
from pathlib import Path

import streamlit as st

from streamlit_app.progress import ProgressTracker


_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _run_pipeline_in_thread(
    config_path: str,
    idea: str,
    user_requirement: str,
    style: str,
    progress_tracker: ProgressTracker,
) -> None:
    """Run the pipeline in a fresh event loop on a background thread.

    Streamlit reruns the page on every interaction; the rerun must not
    leave the previous pipeline coroutine in a half-cancelled session.
    We deliberately use a brand-new loop on a daemon thread so the
    rerun can't touch it.
    """
    from pipelines.idea_pipeline import IdeaPipeline

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        pipeline = IdeaPipeline.init_from_config(config_path)
        pipeline.progress_tracker = progress_tracker
        result = loop.run_until_complete(
            pipeline(idea=idea, user_requirement=user_requirement, style=style)
        )
        st.session_state.final_video = result
    except Exception as e:
        st.session_state.error = str(e)
        import traceback
        st.session_state.error_tb = traceback.format_exc()
    finally:
        st.session_state.pipeline_running = False
        loop.close()


def render() -> None:
    st.header("Input")
    st.markdown("Describe your idea and how you want it visualized.")

    if st.session_state.config_path:
        st.info(f"Config: {st.session_state.config_path}")
    else:
        st.warning("No config selected. Go to **Config** page first.")
        if st.button("Go to Config"):
            st.session_state.nav_page = "Config"
            st.rerun()
        return

    idea = st.text_area(
        "Idea",
        value=st.session_state.idea,
        height=250,
        placeholder="Describe your video idea in detail...",
        help="The core concept of your video. Be as descriptive as possible.",
    )
    user_requirement = st.text_area(
        "User Requirement",
        value=st.session_state.user_requirement,
        height=120,
        placeholder="e.g. For adults, do not exceed 3 scenes. Each scene should be no more than 5 shots.",
        help="Optional constraints on the output.",
    )
    style = st.text_input(
        "Style",
        value=st.session_state.style,
        placeholder="e.g. Realistic, warm feel / Anime / Cinematic",
    )
    force = st.checkbox(
        "Force regenerate (delete existing working directory)",
        value=st.session_state.force_regenerate,
        help="Check to delete the working directory before starting.",
    )

    disabled = st.session_state.pipeline_running or not idea.strip()
    if st.button(
        "Generate Video",
        type="primary",
        disabled=disabled,
        use_container_width=True,
    ):
        st.session_state.idea = idea
        st.session_state.user_requirement = user_requirement
        st.session_state.style = style
        st.session_state.force_regenerate = force
        st.session_state.final_video = None
        st.session_state.error = None
        st.session_state.error_tb = None

        working_dir = st.session_state.working_dir
        if force and os.path.exists(working_dir):
            shutil.rmtree(working_dir)
            st.info(f"Deleted {working_dir}")

        progress_tracker = ProgressTracker()
        st.session_state.progress = progress_tracker
        st.session_state.pipeline_running = True

        thread = threading.Thread(
            target=_run_pipeline_in_thread,
            args=(
                st.session_state.config_path,
                idea,
                user_requirement,
                style,
                progress_tracker,
            ),
            daemon=True,
        )
        thread.start()

        st.session_state.nav_page = "Results"
        st.rerun()

    if st.session_state.pipeline_running:
        st.warning("Pipeline is already running. Check the **Results** page.")
