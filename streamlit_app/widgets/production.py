"""The production page — the per-clip console with timeline + cards.

This is the second-largest piece of UI in the app.  It shows:

* a 6-step production timeline (Story -> Characters -> Portraits ->
  Script -> Editing -> Release),
* one card per stage with the latest generated content,
* a portrait gallery for the first three characters,
* a quick "Auto Gen" textarea that runs the full pipeline end-to-end.

The pipeline is launched in a background thread (see
:mod:`streamlit_app.pages.idea`) and its progress is written to
``st.session_state.progress`` for live updates.
"""

from __future__ import annotations

import asyncio
import base64
import html
import os
from datetime import datetime

import httpx
import streamlit as st
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from schemas.clip import Clip, ClipStore
from streamlit_app.session import project_root
from clients.agnes_image_generator import AgnesImageGenerator
from utils.providers import (
    resolve_chat_model_config,
    strip_internal_resolve_keys,
    validate_resolved_chat_model_config,
)
from utils.throttling import RateLimiter


NAV_OPTIONS = ("App", "Input", "Results", "Production")
NAV_QUERY_MAP = {"clip": "Production"}

STAGES = (
    ("Story", "story_output"),
    ("Characters", "characters_output"),
    ("Portraits", "portraits_images"),
    ("Script", "script_output"),
    ("Editing", None),
    ("Release", None),
)


# ────────────────────────────────────────────────────────────────────────
#  Persistence
# ────────────────────────────────────────────────────────────────────────


def _clips_dir() -> str:
    return os.path.join(project_root(), ".working_dir", "clips")


def _idea_dir(clip_id: str) -> str:
    return os.path.join(_clips_dir(), "ideas", str(clip_id))


def _save_state_to_disk() -> None:
    clip_id = st.session_state.get("current_clip_id")
    if not clip_id:
        return
    base = _idea_dir(clip_id)
    os.makedirs(base, exist_ok=True)
    for key, fname in [
        ("production_idea", "idea.txt"),
        ("story_output", "story.txt"),
        ("characters_output", "characters.txt"),
        ("script_output", "script.txt"),
    ]:
        value = st.session_state.get(key)
        if value:
            with open(os.path.join(base, fname), "w") as f:
                f.write(value)


def _load_state_from_disk() -> None:
    clip_id = st.session_state.get("current_clip_id")
    if not clip_id:
        return
    base = _idea_dir(clip_id)
    if not os.path.exists(base):
        return
    for key, fname in [
        ("production_idea", "idea.txt"),
        ("story_output", "story.txt"),
        ("characters_output", "characters.txt"),
        ("script_output", "script.txt"),
    ]:
        path = os.path.join(base, fname)
        if os.path.exists(path) and not st.session_state.get(key):
            with open(path) as f:
                st.session_state[key] = f.read()

    portraits: dict[str, dict[str, str]] = {}
    if os.path.isdir(base):
        for entry in os.listdir(base):
            char_dir = os.path.join(base, entry)
            if not os.path.isdir(char_dir):
                continue
            views: dict[str, str] = {}
            for view in ("front", "back", "side"):
                img = os.path.join(char_dir, f"{view}.png")
                if os.path.exists(img):
                    views[view] = img
            if views:
                portraits[entry] = views
    if portraits:
        st.session_state.portraits_images = portraits
        st.session_state["portraits_b64_cache"] = {}


# ────────────────────────────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────────────────────────────


@st.cache_data(show_spinner=False)
def _encode_portrait_b64(path: str, mtime: float) -> str:
    del mtime  # signature only; mtime invalidates the cache when file changes
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _format_bullets(text: str) -> str:
    items = "".join(
        f"<li>{html.escape(line.lstrip('- '))}</li>"
        for line in text.split("\n")
        if line.strip()
    )
    return f"<ul>{items}</ul>"


def _format_ts(ts: str) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts).strftime("%b %d, %Y %H:%M")
    except ValueError:
        return ts


def _parse_characters(text: str) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("-"):
            continue
        content = line[1:].strip()
        if ":" in content:
            name, desc = content.split(":", 1)
            parsed.append((name.strip(), desc.strip()))
        else:
            parsed.append((content, ""))
    return parsed


def _render_portraits_card(raw_id: str) -> str:
    portraits = st.session_state.get("portraits_images") or {}
    if not portraits:
        return (
            '<div class="prod-card">'
            '<div class="prod-card-hdr"><h4>Portraits</h4>'
            '<div class="prod-card-actions">'
            '<button class="prod-card-btn gen">Generate</button>'
            '<button class="prod-card-btn edit">Edit</button>'
            '</div></div>'
            '<p style="margin:0;font-size:13px;color:#999;">Waiting for characters to complete...</p>'
            '<span class="prod-tag">Pending</span>'
            '</div>'
        )

    rows = []
    items = list(portraits.items())
    for i in range(0, len(items), 2):
        pair = items[i:i + 2]
        cells = ""
        for name, views in pair:
            thumbs = ""
            for view in ("front", "back", "side"):
                path = views.get(view)
                if not path or not os.path.exists(path):
                    continue
                try:
                    mtime = os.path.getmtime(path)
                    b64 = _encode_portrait_b64(path, mtime)
                    href = f"?nav=clip&id={html.escape(raw_id, quote=True)}&portrait"
                    thumbs += f'<a href="{href}"><img class="portrait-thumb" src="data:image/png;base64,{b64}" title="{view}"></a>'
                except OSError:
                    thumbs += '<div class="portrait-skeleton"><div class="portrait-skeleton-spinner"></div></div>'
            cells += (
                f'<div class="portrait-cell">'
                f'<span class="portrait-name">{html.escape(name)}</span>'
                f'<div class="portrait-views">{thumbs}</div>'
                f'</div>'
            )
        rows.append(f'<div class="portrait-row">{cells}</div>')

    return (
        '<div class="prod-card">'
        '<div class="prod-card-hdr"><h4>Portraits</h4>'
        '<div class="prod-card-actions">'
        '<button class="prod-card-btn gen">Generate</button>'
        '<button class="prod-card-btn edit">Edit</button>'
        '</div></div>'
        f'<div class="portraits-grid">{"".join(rows)}</div>'
        '<span class="prod-tag">Done</span>'
        '</div>'
    )


# ────────────────────────────────────────────────────────────────────────
#  Auto Gen
# ────────────────────────────────────────────────────────────────────────


def _build_portraits_coro(characters_text: str):
    """Build (but don't await) the coroutine that generates portraits.

    Returns the awaitable; the caller awaits it inside an event loop.
    """
    i2v_image_cfg = st.session_state.i2v_image_model
    if not i2v_image_cfg or not i2v_image_cfg.get("model"):
        async def _empty() -> dict:
            return {}
        return _empty()

    characters = _parse_characters(characters_text)[:3]
    if not characters:
        async def _empty() -> dict:
            return {}
        return _empty()

    rate_limiter = RateLimiter(
        max_requests_per_minute=i2v_image_cfg.get("max_requests_per_minute"),
        max_requests_per_day=i2v_image_cfg.get("max_requests_per_day"),
    )
    img_gen = AgnesImageGenerator(
        api_key=i2v_image_cfg.get("api_key"),
        model=i2v_image_cfg.get("model"),
        rate_limiter=rate_limiter,
    )
    clip_id = st.session_state.get("current_clip_id", "default")
    portraits_dir = _idea_dir(clip_id)
    os.makedirs(portraits_dir, exist_ok=True)

    async def _gen_all() -> dict:
        results: dict = {}
        for name, desc in characters:
            results[name] = {}
            safe_name = name.replace(" ", "_").replace("/", "_")
            char_dir = os.path.join(portraits_dir, safe_name)
            os.makedirs(char_dir, exist_ok=True)
            for view in ("front", "back", "side"):
                prompt = f"{view} view character portrait of {name}, {desc}, character design, plain background, high quality"
                try:
                    img_output = await img_gen.generate_single_image(prompt, size="1024x1024")
                    img_path = os.path.join(char_dir, f"{view}.png")
                    img_output.save(img_path)
                    results[name][view] = img_path
                except Exception as e:
                    st.warning(f"Portrait {view} for {name} failed: {e}")
        return results

    return _gen_all()


def _run_auto_gen(idea_text: str) -> None:
    """Generate story + characters + script + portraits in parallel."""
    if st.session_state.chat_model is None:
        i2v_chat_cfg = st.session_state.i2v_chat_model
        if not i2v_chat_cfg or not i2v_chat_cfg.get("model"):
            st.error("No chat model configured. Open Settings and configure a chat model first.")
            return
        try:
            client = httpx.Client(proxy=None, trust_env=False)
            init_args = {
                "model": i2v_chat_cfg.get("model"),
                "model_provider": i2v_chat_cfg.get("model_provider"),
                "api_key": i2v_chat_cfg.get("api_key"),
                "base_url": i2v_chat_cfg.get("base_url"),
                "http_client": client,
            }
            resolved = resolve_chat_model_config(init_args)
            validate_resolved_chat_model_config(resolved)
            strip_internal_resolve_keys(resolved)
            st.session_state.chat_model = init_chat_model(**resolved)
        except Exception as e:
            st.error(f"Failed to initialize chat model ({type(e).__name__}): {e}")
            return

    st.session_state.production_idea = idea_text

    try:
        prompt = (
            "Based on the following video idea, write a creative story concept. "
            "Keep it concise (2-3 paragraphs):\n\n" + idea_text
        )
        story_result = st.session_state.chat_model.invoke([HumanMessage(content=prompt)])
        st.session_state.story_output = story_result.content

        char_prompt = (
            "Extract the character names and brief descriptions from this story. "
            "Format each as '- Name: description':\n\n" + story_result.content
        )
        char_result = st.session_state.chat_model.invoke([HumanMessage(content=char_prompt)])
        st.session_state.characters_output = char_result.content

        script_prompt = (
            "Based on the following story, generate a video shot list / script. "
            "List each shot as '- Shot N: [camera angle, action, duration in seconds]'. "
            "Keep it to 6-10 shots total.\n\n"
            f"Story:\n{story_result.content}\n\n"
            f"Characters:\n{char_result.content}"
        )

        async def _run_parallel():
            loop = asyncio.get_running_loop()
            script_task = loop.run_in_executor(
                None,
                st.session_state.chat_model.invoke,
                [HumanMessage(content=script_prompt)],
            )
            portraits_coro = _build_portraits_coro(char_result.content)
            return await asyncio.gather(portraits_coro, script_task)

        portraits_result, script_result = asyncio.run(_run_parallel())
        st.session_state.portraits_images = portraits_result
        st.session_state.script_output = script_result.content
        st.session_state["portraits_b64_cache"] = {}
        _save_state_to_disk()
        st.success("Auto Gen completed!")
    except Exception as e:
        st.error(f"Auto Gen failed ({type(e).__name__}): {e}")


# ────────────────────────────────────────────────────────────────────────
#  Timeline
# ────────────────────────────────────────────────────────────────────────


def _render_timeline() -> None:
    story_done = bool(st.session_state.get("story_output"))
    characters_done = bool(st.session_state.get("characters_output"))
    portraits_done = bool(st.session_state.get("portraits_images"))
    script_done = bool(st.session_state.get("script_output"))

    def _class(idx: int) -> str:
        if idx == 0:
            return "complete" if story_done else "active"
        if idx == 1:
            return "complete" if characters_done else ("active" if story_done else "")
        if idx == 2:
            return "complete" if portraits_done else ("active" if characters_done else "")
        if idx == 3:
            return "complete" if script_done else ("active" if portraits_done else "")
        return ""

    steps = "".join(
        f'<div class="prod-step {_class(i)}"><span class="prod-dot">{i+1}</span>'
        f'<div class="prod-step-label">{label}</div></div>'
        for i, (label, _key) in enumerate(STAGES)
    )
    st.html(f'<div class="prod-timeline-row"><div class="prod-timeline">{steps}</div></div>')


# ────────────────────────────────────────────────────────────────────────
#  Entry point
# ────────────────────────────────────────────────────────────────────────


def render() -> None:
    store_path = os.path.join(_clips_dir(), "clips_index.json")
    clip_store = ClipStore(store_path)
    raw_id = st.session_state.get("current_clip_id", "")
    current_clip = clip_store.get(raw_id)

    _load_state_from_disk()

    is_new_clip = current_clip is None or current_clip.status == "new"
    title = current_clip.title if current_clip else "Create creative video"
    created_str = _format_ts(current_clip.created_at) if current_clip else ""
    updated_str = _format_ts(current_clip.updated_at) if current_clip and current_clip.updated_at else ""
    meta_extra = ""
    if not is_new_clip:
        meta_extra = (
            f'<span class="prod-meta-item"><strong>Created</strong>: {created_str}</span>'
            f'<span class="prod-meta-item"><strong>Updated</strong>: {updated_str}</span>'
        )

    st.markdown(
        f'<div class="prod-header">'
        f'<h2>{html.escape(title)}</h2>'
        f'<span class="prod-status">Status: <span style="color:#f0c000">● In Review</span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    chat_name = (st.session_state.i2v_chat_model or {}).get("model", "—")
    img_name = (st.session_state.i2v_image_model or {}).get("model", "—")
    vid_name = (st.session_state.i2v_video_model or {}).get("model", "—")
    st.markdown(
        f'<div class="prod-meta-row">'
        f'<span class="prod-meta-item"><strong>Chat Model</strong>: {chat_name}</span>'
        f'<span class="prod-meta-item"><strong>Image Model</strong>: {img_name}</span>'
        f'<span class="prod-meta-item"><strong>Video Model</strong>: {vid_name}</span>'
        f'{meta_extra}</div>',
        unsafe_allow_html=True,
    )

    # ── Auto Gen: text area + button ──
    idea_val = (
        st.session_state.get("production_idea")
        or st.session_state.get("idea", "")
        or ""
    )
    if "prod_idea" not in st.session_state:
        st.session_state.prod_idea = idea_val

    col1, col2 = st.columns([5, 1])
    with col1:
        st.text_area(
            "Video Idea",
            key="prod_idea",
            placeholder="Describe your video idea...",
            height=80,
            label_visibility="collapsed",
        )
    with col2:
        run = st.button("Auto Gen", key="prod_auto_gen", use_container_width=True, type="primary")

    if run:
        idea_text = (st.session_state.prod_idea or "").strip()
        if len(idea_text) < 5:
            st.warning("Please enter at least 5 characters.")
        else:
            if current_clip is None:
                try:
                    new_id = int(raw_id) if raw_id else 1
                except (ValueError, TypeError):
                    new_id = 1
                current_clip = Clip(id=new_id, title="Create creative video", status="new")
                clips = clip_store.load()
                clips.append(current_clip)
                clip_store.save(clips)
                st.session_state.current_clip_id = str(current_clip.id)
            _run_auto_gen(idea_text)

    # ── Cards ──
    story_out = st.session_state.get("story_output", "")
    story_placeholder = (
        "Waiting for generated..." if is_new_clip
        else "Final draft approved. 3 revisions completed. Ready for storyboard."
    )
    story_html = html.escape(story_out) if story_out else story_placeholder
    story_tag = "Done" if story_out else "Complete"

    characters_out = st.session_state.get("characters_output", "")
    characters_html = _format_bullets(characters_out) if characters_out else "Waiting for generated..."
    characters_tag = "Done" if characters_out else "Pending"

    script_out = st.session_state.get("script_output", "")
    script_html = _format_bullets(script_out) if script_out else "Waiting for portraits to complete..."
    script_tag = "Done" if script_out else "Pending"

    portraits_html = _render_portraits_card(raw_id)

    _render_timeline()

    st.markdown(
        f"""
        <div class="prod-cards">
          <div class="prod-card">
            <div class="prod-card-hdr"><h4>Story</h4>
              <div class="prod-card-actions">
                <button class="prod-card-btn gen">Generate</button>
                <button class="prod-card-btn edit">Edit</button>
              </div>
            </div>
            <p>{story_html}</p>
            <span class="prod-tag">{story_tag}</span>
          </div>
          <div class="prod-card">
            <div class="prod-card-hdr"><h4>Characters</h4>
              <div class="prod-card-actions">
                <button class="prod-card-btn gen">Generate</button>
                <button class="prod-card-btn edit">Edit</button>
              </div>
            </div>
            {characters_html}
            <span class="prod-tag">{characters_tag}</span>
          </div>
          <div class="prod-card">
            <div class="prod-card-hdr"><h4>Script</h4>
              <div class="prod-card-actions">
                <button class="prod-card-btn gen">Generate</button>
                <button class="prod-card-btn edit">Edit</button>
              </div>
            </div>
            {script_html}
            <span class="prod-tag">{script_tag}</span>
          </div>
          {portraits_html}
          <div class="prod-card">
            <h4>Editing</h4>
            <p>Rough cut expected soon. Color grading pipeline configured.</p>
            <span class="prod-tag" style="background:rgba(240,192,0,0.1);color:#f0c000;">Pending</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Portrait gallery dialog ──
    if "portrait" in st.query_params:
        portraits = st.session_state.get("portraits_images") or {}
        flat: list[tuple[str, str, str]] = []
        for n, v in portraits.items():
            for vi in ("front", "back", "side"):
                if vi in v:
                    flat.append((n, vi, v[vi]))
        if flat:
            sel = st.query_params.get("portrait", "")
            current_idx = 0
            for i, (n, vi, _) in enumerate(flat):
                if f"{n}_{vi}" == sel:
                    current_idx = i
                    break
            cur_name, cur_view, cur_path = flat[current_idx]

            @st.dialog(f"{cur_name} — {cur_view}", width="small")
            def _gallery(idx: int, items: list[tuple[str, str, str]]) -> None:
                n, vi, path = items[idx]
                st.image(path, width=320)
                st.caption(f"{idx + 1} / {len(items)}")
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    if st.button("◀ Previous", use_container_width=True, key="gal_prev"):
                        ni = (idx - 1) % len(items)
                        nn, nvi, _ = items[ni]
                        st.query_params["portrait"] = f"{nn}_{nvi}"
                        st.rerun()
                with c2:
                    if st.button("Next ▶", use_container_width=True, key="gal_next"):
                        ni = (idx + 1) % len(items)
                        nn, nvi, _ = items[ni]
                        st.query_params["portrait"] = f"{nn}_{nvi}"
                        st.rerun()

            _gallery(current_idx, flat)
