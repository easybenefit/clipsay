from __future__ import annotations

import pytest

from backend.pipeline.conductor import (
    END_FRAME,
    START_FRAME,
    SHOT_VIDEO,
    SCENE_PREVIEW_VIDEO,
    PROJECT_COMPOUND_VIDEO,
    SCENE_VIDEO,
    FINAL_VIDEO,
    PipelineConductor,
    ArtifactRef,
    get_conductor,
)


def test_get_conductor_singleton():
    a = get_conductor()
    b = get_conductor()
    assert a is b


async def test_complete_start_frame():
    c = PipelineConductor()
    c.register_scene(1, 0, [make_sd(0, "small")])
    await c.complete_start_frame(1, 0, 0)
    se = c._shot_states[(1, 0, 0)][START_FRAME]
    assert se.is_set()
    assert se.status == 2


async def test_complete_end_frame():
    c = PipelineConductor()
    c.register_scene(1, 0, [make_sd(0, "medium")])
    await c.complete_end_frame(1, 0, 0)
    se = c._shot_states[(1, 0, 0)][END_FRAME]
    assert se.is_set()
    assert se.status == 2


async def test_complete_shot_video():
    c = PipelineConductor()
    c.register_scene(1, 0, [make_sd(0, "small")])
    await c.complete_shot_video(1, 0, 0)
    se = c._shot_states[(1, 0, 0)][SHOT_VIDEO]
    assert se.is_set()
    assert se.status == 2


async def test_scene_payload():
    c = PipelineConductor()
    c.register_scene(1, 0, [make_sd(0, "small")])
    await c.complete_scene_preview_video(1, 0, video_url="/v1", preview_url="/p1")
    payload = c.get_scene_payload(1, 0)
    assert payload.video_url == "/v1"
    assert payload.preview_url == "/p1"


async def test_project_payload():
    c = PipelineConductor()
    c.register_project(1)
    await c.complete_project_compound_video(1, video_url="/final.mp4", preview_url="/final.jpg")
    payload = c.get_project_payload(1)
    assert payload.video_url == "/final.mp4"
    assert payload.preview_url == "/final.jpg"


def test_mark_shot_frame_restored():
    c = PipelineConductor()
    c.mark_shot_frame_restored(2, 3, 1, START_FRAME)
    se = c._shot_states[(2, 3, 1)][START_FRAME]
    assert se.is_set()
    assert se.status == 2


def test_mark_shot_frame_restored_multiple():
    c = PipelineConductor()
    c.mark_shot_frame_restored(2, 3, 1, START_FRAME)
    c.mark_shot_frame_restored(2, 3, 1, END_FRAME)
    c.mark_shot_frame_restored(2, 3, 1, SHOT_VIDEO)
    assert c._shot_states[(2, 3, 1)][START_FRAME].is_set()
    assert c._shot_states[(2, 3, 1)][END_FRAME].is_set()
    assert c._shot_states[(2, 3, 1)][SHOT_VIDEO].is_set()


def test_mark_scene_payload_restored():
    c = PipelineConductor()
    c.mark_scene_payload_restored(1, 0, video_url="/scene.mp4", preview_url="/scene.jpg")
    ev = c._scene_events[(1, 0)][SCENE_PREVIEW_VIDEO]
    assert ev.is_set()
    assert c._scene_payloads[(1, 0)].video_url == "/scene.mp4"
    assert c._scene_payloads[(1, 0)].preview_url == "/scene.jpg"


def test_mark_project_payload_restored():
    c = PipelineConductor()
    c.mark_project_payload_restored(1, video_url="/final.mp4", preview_url="/final.jpg")
    ev = c._project_events[1][PROJECT_COMPOUND_VIDEO]
    assert ev.is_set()
    assert c._project_payloads[1].video_url == "/final.mp4"
    assert c._project_payloads[1].preview_url == "/final.jpg"


def test_reset_project():
    c = PipelineConductor()
    c.register_scene(1, 0, [make_sd(0, "medium")])
    c.register_project(1)
    c.reset_project(1)
    assert (1, 0) not in c._scene_events
    assert (1, 0, 0) not in c._shot_states
    assert 1 not in c._project_events


async def test_multiple_projects():
    c = PipelineConductor()
    c.register_scene(1, 0, [make_sd(0, "small")])
    c.register_scene(2, 0, [make_sd(1, "medium")])

    await c.complete_start_frame(1, 0, 0)
    await c.complete_start_frame(2, 0, 1)
    await c.complete_end_frame(2, 0, 1)

    assert c._shot_states[(1, 0, 0)][START_FRAME].is_set()
    assert c._shot_states[(2, 0, 1)][START_FRAME].is_set()
    assert c._shot_states[(2, 0, 1)][END_FRAME].is_set()

    # project 1 should not have end_frame
    assert END_FRAME not in c._shot_states[(1, 0, 0)]


def test_restore_sets_events():
    c = PipelineConductor()
    c.mark_shot_frame_restored(1, 0, 0, START_FRAME)
    c.mark_scene_payload_restored(1, 0, video_url="/scene.mp4")
    c.mark_project_payload_restored(1, video_url="/final.mp4")

    # wait methods should return immediately since events are set
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(c.wait_start_frame(1, 0, 0))
        payload = loop.run_until_complete(c.wait_scene_preview_video(1, 0))
        assert payload.video_url == "/scene.mp4"
        proj_payload = loop.run_until_complete(c.wait_project_compound_video(1))
        assert proj_payload.video_url == "/final.mp4"
    finally:
        loop.close()


async def test_listener():
    c = PipelineConductor()
    events = []

    async def handler(project_id, scene_id, shot_idx, name, status, **kwargs):
        events.append((name, status))

    c.on("start_frame", handler)
    await c.complete_start_frame(1, 0, 0)
    assert ("start_frame", 2) in events

    await c.creating_start_frame(1, 0, 0)
    assert ("start_frame", 1) in events

    c.off("start_frame", handler)
    await c.complete_start_frame(1, 0, 1)
    assert len(events) == 2  # no new events


# ── helpers ─────────────────────────────────────────────────────────────

def make_sd(idx: int, variation_type: str = "small"):
    from backend.schemas.shot_spec import ShotSpec
    return ShotSpec(
        idx=idx,
        cam_idx=0,
        is_last=False,
        visual_desc=f"shot {idx}",
        sf_dec=f"ff {idx}",
        sf_desc=f"lf {idx}",
        motion_desc="",
        audio_desc="",
        variation_type=variation_type,
        sf_vis_char_idxs=[],
        ef_vis_char_idxs=[],
    )
