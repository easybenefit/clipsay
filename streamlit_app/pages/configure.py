"""Config page — pick a YAML config and tweak chat / image / video models.

The page writes a temporary copy of the chosen YAML to
``/tmp/clipsay_<rand>.yaml`` rather than mutating the source file, so
multiple users can share the same checked-in config without trampling
each other.  The temp file's path is what gets fed to the pipeline.
"""

from __future__ import annotations

import copy
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml


_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _available_configs() -> list[dict]:
    configs_dir = Path(_PROJECT_ROOT) / "configs"
    return [
        {"label": f.name, "path": str(f)}
        for f in sorted(configs_dir.glob("idea2video_*.yaml"))
    ]


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _resolve_api_key(hint: str) -> str:
    if hint and not hint.startswith("<") and hint != "<YOUR_API_KEY>":
        return hint
    return os.environ.get("AGNES_API_KEY", "")


def render() -> None:
    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        if st.button("Back"):
            st.session_state.nav_page = "App"
            st.rerun()
    with col2:
        st.header("Configuration")
    st.markdown("Select a config file and customize model settings.")

    configs = _available_configs()
    if not configs:
        st.error("No config files found in configs/")
        return

    config_labels = [c["label"] for c in configs]
    default_idx = 0
    if st.session_state.config_path:
        for i, c in enumerate(configs):
            if c["path"] == st.session_state.config_path:
                default_idx = i
                break

    selected_label = st.selectbox("Config file", config_labels, index=default_idx)
    selected_path = next(c["path"] for c in configs if c["label"] == selected_label)

    if selected_path != st.session_state.config_path:
        st.session_state.config_path = selected_path
        st.session_state.config_data = _load_yaml(selected_path)
        st.rerun()

    if st.session_state.config_data is None:
        st.session_state.config_data = _load_yaml(selected_path)

    config = copy.deepcopy(st.session_state.config_data)
    st.divider()

    st.subheader("API Key")
    current_key = config.get("chat_model", {}).get("init_args", {}).get("api_key", "")
    api_key = st.text_input(
        "API Key",
        value=_resolve_api_key(current_key),
        type="password",
        help="Set the relevant env var (e.g. AGNES_API_KEY) or enter here",
    )

    st.subheader("Chat Model")
    chat_init = config.setdefault("chat_model", {}).setdefault("init_args", {})
    chat_model = st.text_input("Model name", value=chat_init.get("model", "agnes-2.0-flash"))
    chat_init["model"] = chat_model
    chat_init["api_key"] = api_key

    chat_limits = config.setdefault("chat_model", {})
    chat_limits["max_requests_per_minute"] = st.number_input(
        "Chat: max requests/min (0 = no limit)",
        value=chat_limits.get("max_requests_per_minute") or 0,
        min_value=0, step=1,
    ) or None

    st.subheader("Image Generator")
    img_init = config.setdefault("image_generator", {}).setdefault("init_args", {})
    image_models = ["agnes-image-2.1-flash", "agnes-image-2.0-flash"]
    current_img = img_init.get("model", "agnes-image-2.1-flash")
    img_model = st.selectbox(
        "Image model",
        image_models,
        index=image_models.index(current_img) if current_img in image_models else 0,
    )
    img_init["model"] = img_model
    img_init["api_key"] = api_key

    img_limits = config.setdefault("image_generator", {})
    c1, c2 = st.columns(2)
    with c1:
        img_limits["max_requests_per_minute"] = st.number_input(
            "Image: max/min", value=img_limits.get("max_requests_per_minute") or 2,
            min_value=1, step=1,
        )
    with c2:
        img_limits["max_requests_per_day"] = st.number_input(
            "Image: max/day", value=img_limits.get("max_requests_per_day") or 50,
            min_value=1, step=1,
        )

    st.subheader("Video Generator")
    vid_init = config.setdefault("video_generator", {}).setdefault("init_args", {})
    video_models = ["agnes-video-v2.0"]
    current_t2v = vid_init.get("t2v_model", "agnes-video-v2.0")
    vid_t2v = st.selectbox(
        "T2V model",
        video_models,
        index=video_models.index(current_t2v) if current_t2v in video_models else 0,
    )
    current_i2v = vid_init.get("i2v_model", "agnes-video-v2.0")
    vid_i2v = st.selectbox(
        "I2V model",
        video_models,
        index=video_models.index(current_i2v) if current_i2v in video_models else 0,
    )
    vid_init["t2v_model"] = vid_t2v
    vid_init["i2v_model"] = vid_i2v
    vid_init["api_key"] = api_key

    vid_limits = config.setdefault("video_generator", {})
    c1, c2 = st.columns(2)
    with c1:
        vid_limits["max_requests_per_minute"] = st.number_input(
            "Video: max/min", value=vid_limits.get("max_requests_per_minute") or 10,
            min_value=1, step=1,
        )
    with c2:
        vid_limits["max_requests_per_day"] = st.number_input(
            "Video: max/day", value=vid_limits.get("max_requests_per_day") or 500,
            min_value=1, step=1,
        )

    st.divider()
    st.subheader("Run Name")
    default_run = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_name = st.text_input(
        "Output directory name",
        value=st.session_state.get("run_name", ""),
        placeholder=default_run,
        help="Subdirectory under .working_dir/idea2video/. Leave empty for auto-name.",
    )
    if not run_name:
        run_name = default_run
    st.session_state.run_name = run_name

    working_dir = f".working_dir/idea2video/{run_name}"
    st.code(working_dir)
    st.session_state.working_dir = working_dir
    config["working_dir"] = working_dir

    st.divider()
    if st.button("Save Config", type="primary"):
        config["chat_model"]["init_args"]["api_key"] = api_key
        _, tmp_path = tempfile.mkstemp(suffix=".yaml", prefix="clipsay_")
        with open(tmp_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        st.session_state.config_path = tmp_path
        st.session_state.config_data = config
        st.success(f"Config saved to {tmp_path}")
