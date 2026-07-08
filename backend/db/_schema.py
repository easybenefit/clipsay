"""Database table definitions and schema constants."""

from __future__ import annotations


TABLES = [
    """
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        language TEXT DEFAULT 'zh',
        idea TEXT DEFAULT '',
        style TEXT DEFAULT 'realistic',
        size TEXT DEFAULT '16:9',
        resolution TEXT DEFAULT '720p',
        frame_rate INTEGER DEFAULT 24,
        duration INTEGER DEFAULT 10,
        chat_model TEXT DEFAULT '',
        chat_api_key TEXT DEFAULT '',
        chat_base_url TEXT DEFAULT '',
        image_model TEXT DEFAULT '',
        image_api_key TEXT DEFAULT '',
        image_base_url TEXT DEFAULT '',
        video_model TEXT DEFAULT '',
        video_api_key TEXT DEFAULT '',
        video_base_url TEXT DEFAULT '',
        stage TEXT DEFAULT 'new',
        pipeline_status TEXT DEFAULT 'idle',
        pipeline_step TEXT DEFAULT '',
        pipeline_error TEXT DEFAULT '',
        story_content TEXT DEFAULT '',
        script_title TEXT DEFAULT '',
        script_text TEXT DEFAULT '',
        final_video TEXT DEFAULT '',
        final_preview TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT ''
    )
    """,
    """
    DROP TABLE IF EXISTS attributes;
    CREATE TABLE IF NOT EXISTS attributes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        identifier TEXT NOT NULL DEFAULT '',
        appearance TEXT DEFAULT '',
        attire TEXT DEFAULT '',
        idx INTEGER DEFAULT 0,
        front_url TEXT DEFAULT '',
        side_url TEXT DEFAULT '',
        back_url TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        idx INTEGER NOT NULL,
        title TEXT DEFAULT '',
        content TEXT NOT NULL,
        environment_desc TEXT DEFAULT '',
        script TEXT DEFAULT '',
        composited_video TEXT DEFAULT '',
        composited_preview TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cameras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
        idx INTEGER NOT NULL,
        active_shot_idxs TEXT DEFAULT '[]',
        parent_cam_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL,
        parent_shot_idx INTEGER,
        reason TEXT DEFAULT '',
        is_parent_fully_covers_child INTEGER DEFAULT 0,
        missing_info TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
        idx INTEGER NOT NULL,
        is_last INTEGER DEFAULT 0,
        cam_idx INTEGER NOT NULL,
        variation_type TEXT DEFAULT 'medium',
        variation_reason TEXT DEFAULT '',
        visual_desc TEXT DEFAULT '',
        audio_desc TEXT DEFAULT '',
        sf_dec TEXT DEFAULT '',
        sf_desc TEXT DEFAULT '',
        motion_desc TEXT DEFAULT '',
        start_frame_url TEXT DEFAULT '',
        end_frame_url TEXT DEFAULT '',
        start_frame_path TEXT DEFAULT '',
        end_frame_path TEXT DEFAULT '',
        shot_preview_url TEXT DEFAULT '',
        shot_video_url TEXT DEFAULT '',
        shot_video_path TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        image_status TEXT DEFAULT 'pending',
        video_status TEXT DEFAULT 'pending',
        image_status_int INTEGER DEFAULT 0,
        start_frame_status INTEGER DEFAULT 0,
        end_frame_status INTEGER DEFAULT 0,
        video_dependency TEXT DEFAULT '',
        source_url TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS prompt_rewrites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        scene_idx INTEGER,
        shot_idx INTEGER,
        frame_type TEXT,
        version INTEGER NOT NULL,
        original_prompt TEXT NOT NULL,
        rewritten_prompt TEXT NOT NULL,
        reason TEXT NOT NULL,
        provider TEXT DEFAULT '',
        model TEXT DEFAULT '',
        succeeded INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

MIGRATIONS = [
    "ALTER TABLE projects ADD COLUMN chat_api_key TEXT DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN chat_base_url TEXT DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN image_api_key TEXT DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN image_base_url TEXT DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN video_api_key TEXT DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN video_base_url TEXT DEFAULT ''",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_attributes_project ON attributes(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_shots_scene ON shots(scene_id)",
    "CREATE INDEX IF NOT EXISTS idx_cameras_scene ON cameras(scene_id)",
]
