from __future__ import annotations

from backend.schemas import (
    CreateProject, GenerateRequest, CharacterSave, SceneSave, ShotSave, ProjectUpdate,
)


def test_create_project_defaults():
    m = CreateProject(name="test")
    assert m.name == "test"
    assert m.language == "zh"


def test_generate_request_defaults():
    m = GenerateRequest(prompt="hello", model="gpt-4")
    assert m.api_key == ""
    assert m.base_url == ""


def test_character_save_alias():
    payload = {
        "identifier": "Alice",
        "staticFeatures": "tall, blue eyes",
        "dynamicFeatures": "red dress",
        "sourceUrl": "http://example.com/img.png",
    }
    m = CharacterSave.model_validate(payload)
    assert m.identifier == "Alice"
    assert m.appearance == "tall, blue eyes"
    assert m.attire == "red dress"
    assert m.source_url == "http://example.com/img.png"
    dumped = m.model_dump(by_alias=True)
    assert dumped["staticFeatures"] == "tall, blue eyes"
    assert dumped["sourceUrl"] == "http://example.com/img.png"

    internal = m.model_dump()
    assert internal["appearance"] == "tall, blue eyes"
    assert internal["attire"] == "red dress"


def test_shot_save_alias():
    payload = {
        "visualDescription": "wide shot of city",
        "voiceDescription": "ambient noise",
        "motionDescription": "camera pans left",
        "variationType": "medium",
        "firstFrame": "img1.png",
        "lastFrame": "img2.png",
    }
    m = ShotSave.model_validate(payload)
    assert m.visual_description == "wide shot of city"
    assert m.variation_type == "medium"
    assert m.first_frame == "img1.png"

    dumped = m.model_dump(by_alias=True)
    assert dumped["visualDescription"] == "wide shot of city"
    assert dumped["variationType"] == "medium"


def test_scene_save_with_shots():
    payload = {
        "title": "Opening",
        "content": "A quiet morning",
        "slugline": "EXT. PARK - DAY",
        "environmentDesc": "sunny park",
        "script": "Alice walks in",
        "compositedVideo": "video.mp4",
        "shots": [
            {"visualDescription": "bird flies", "variationType": "small"}
        ],
    }
    m = SceneSave.model_validate(payload)
    assert m.environment_desc == "sunny park"
    assert m.composited_video == "video.mp4"
    assert len(m.shots) == 1
    assert m.shots[0].visual_description == "bird flies"


def test_scene_save_defaults():
    s = SceneSave(title="Test", content="content")
    assert s.title == "Test"
    assert s.environment_desc == ""


def test_project_update_partial():
    payload = {
        "name": "new name",
        "frame_rate": 30,
        "chat_model": "gpt-4",
    }
    m = ProjectUpdate.model_validate(payload)
    assert m.name == "new name"
    assert m.frame_rate == 30
    assert m.chat_model == "gpt-4"
    assert m.story is None
