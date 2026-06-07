"""Results page — live progress and final video.

Renders one of three views depending on the pipeline session:

* **Running** — auto-refreshes every 2 s, draws the overall progress
  bar, per-phase status, scene expansion panels, and any intermediate
  PNGs found under the working directory.
* **Completed** — shows the final MP4 with a download button, plus all
  the intermediates for inspection.
* **Errored** — surfaces the error and a collapsible traceback.

The auto-refresh uses ``st.rerun()`` + ``time.sleep(2)`` to give the
background pipeline thread time to update :class:`ProgressTracker`.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import streamlit as st

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from streamlit_app.progress import SCENE_SUB_WEIGHTS, ProgressTracker


# ── Discovery ──


def _discover_intermediates(working_dir: str) -> tuple[list[str], list[str]]:
    """Return (image_paths, video_paths) under ``working_dir/scene_*/shots/``."""
    images: list[str] = []
    videos: list[str] = []
    base = Path(working_dir)
    if not base.exists():
        return images, videos
    for scene_dir in sorted(base.glob("scene_*")):
        shots_dir = scene_dir / "shots"
        if not shots_dir.exists():
            continue
        for shot_dir in sorted(shots_dir.iterdir()):
            for f in shot_dir.iterdir():
                if f.suffix == ".png":
                    images.append(str(f))
                elif f.suffix == ".mp4":
                    videos.append(str(f))
    return images, videos


# ── Renderers ──


_STATUS_ICON = {
    "pending": "PENDING",
    "running": "RUNNING",
    "completed": "DONE",
    "failed": "FAILED",
}


def _status_icon(session: str) -> str:
    return _STATUS_ICON.get(session, "PENDING")


def _render_step(step_name: str, session, indent: int = 0) -> None:
    prefix = "  " * indent
    icon = _status_icon(session.status)
    st.markdown(f"{prefix}`{icon}` **{step_name}**: {session.detail}")


def _render_scene_progress(progress: ProgressTracker, scene_idx: int) -> None:
    scene_phase = f"scene_{scene_idx}"
    scene_state = progress.steps.get(scene_phase)
    if scene_state is None:
        return
    expanded = scene_state.status == "running"
    with st.expander(f"Scene {scene_idx + 1}", expanded=expanded):
        _render_step(scene_phase, scene_state)
        for sub_name in SCENE_SUB_WEIGHTS:
            sub_phase = f"{scene_phase}.{sub_name}"
            sub_state = progress.steps.get(sub_phase)
            if sub_state is not None:
                _render_step(sub_name, sub_state, indent=1)


def _render_frame_grid(images: list[str]) -> None:
    cols = st.columns(min(len(images), 4))
    for i, img_path in enumerate(images):
        with cols[i % 4]:
            st.image(img_path, caption=Path(img_path).name, use_container_width=True)


# ── Entry point ──


def render() -> None:
    st.header("Results")
    progress: ProgressTracker = st.session_state.get("progress")
    pipeline_running = st.session_state.get("pipeline_running", False)
    working_dir = st.session_state.get("working_dir", "")
    final_video = st.session_state.get("final_video")
    error = st.session_state.get("error")
    error_tb = st.session_state.get("error_tb")

    if not progress and not pipeline_running and not final_video and not error:
        st.info("No pipeline has been run yet. Go to **Input** to start one.")
        return

    # ── Error display ──
    if error:
        st.error(f"Pipeline failed: {error}")
        if error_tb:
            with st.expander("Traceback"):
                st.code(error_tb)
        if st.button("Go back to Input"):
            st.session_state.nav_page = "Input"
            st.rerun()
        return

    # ── Final video (done) ──
    if final_video and os.path.exists(final_video):
        st.success("Pipeline completed successfully!")
        st.subheader("Final Video")
        with open(final_video, "rb") as f:
            video_bytes = f.read()
        st.video(video_bytes)
        st.download_button(
            "Download Video",
            data=video_bytes,
            file_name=os.path.basename(final_video),
            mime="video/mp4",
        )
        st.divider()

    # ── Auto-refresh while running ──
    if pipeline_running:
        progress = st.session_state.get("progress")
        if progress:
            overall = progress.overall_progress
            current = progress.current_phase or ""
            st.progress(overall, text=f"**{current}** — {overall * 100:.1f}%")

            st.subheader("Pipeline Progress")
            col1, col2 = st.columns(2)
            top_phases = (
                "develop_story", "extract_characters",
                "portraits", "write_script", "concat_final",
            )
            for i, phase in enumerate(top_phases):
                state_ = progress.steps.get(phase)
                if state_ is None:
                    continue
                col = col1 if i % 2 == 0 else col2
                with col:
                    _render_step(phase.replace("_", " ").title(), state_)

            if progress.num_scenes > 0:
                st.subheader("Scenes")
                for idx in range(progress.num_scenes):
                    _render_scene_progress(progress, idx)

            st.divider()
            st.subheader("Log")
            log_text = "\n".join(progress.logs[-100:])
            st.text_area("Latest logs", log_text, height=200, label_visibility="collapsed")

            if working_dir:
                images, _ = _discover_intermediates(working_dir)
                if images:
                    st.divider()
                    st.subheader("Generated Frames")
                    _render_frame_grid(images)

        time.sleep(2)
        st.rerun()

    # ── Completed but no final video (show intermediates) ──
    elif not final_video and not error:
        if progress:
            st.progress(1.0)
            st.subheader("Pipeline Progress")
            for phase, state_ in progress.steps.items():
                if phase.startswith("scene_"):
                    continue
                _render_step(phase.replace("_", " ").title(), state_)
            for idx in range(progress.num_scenes):
                _render_scene_progress(progress, idx)
        if working_dir:
            images, videos = _discover_intermediates(working_dir)
            if images:
                st.divider()
                st.subheader("Generated Frames")
                _render_frame_grid(images)
            if videos:
                st.divider()
                st.subheader("Shot Videos")
                for v in videos:
                    with open(v, "rb") as f:
                        st.video(f.read())
                    st.download_button(
                        f"Download {Path(v).name}",
                        data=open(v, "rb").read(),
                        file_name=Path(v).name,
                        mime="video/mp4",
                    )
        st.info("Pipeline finished but final video was not produced. Check logs above.")
