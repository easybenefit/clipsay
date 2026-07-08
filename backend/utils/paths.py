import os
import re
from pathlib import Path
from typing import Dict, Any


_DEFAULT_DEV_ROOT = Path(__file__).resolve().parents[2] / "_dev" / "data"
DATA_ROOT = Path(os.environ.get("CLIPSAY_DATA_ROOT") or _DEFAULT_DEV_ROOT)

_BAD_FILENAME = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")
_MAX_FILENAME_LEN = 120


def _sanitize_filename(filename: str) -> str:
    base = _BAD_FILENAME.sub("_", filename).strip().strip(".")
    return (base[:_MAX_FILENAME_LEN]) or "untitled"


_PATH_TEMPLATES = {
    "portrait": "{project_id}/portraits/{filename}",
    "project_file": "{project_id}/{filename}",
    "scene_file": "{project_id}/scenes/{scene_idx}/{filename}",
    "shot_file": "{project_id}/scenes/{scene_idx}/shots/{shot_id}/{filename}",
}


class PathResolver:

    def __init__(self, base_root: Path = DATA_ROOT) -> None:
        self._data_root = Path(base_root)
        self._data_root.mkdir(parents=True, exist_ok=True)

    def project(self, project_id: str | int) -> "ProjectScope":
        pid = str(project_id)
        if not pid.startswith("proj_"):
            pid = f"proj_{pid}"
        return ProjectScope(self, pid)

    def _url(self, template_key: str, context: Dict[str, Any]) -> str:
        raw_template = _PATH_TEMPLATES.get(template_key)
        if not raw_template:
            raise ValueError(f"Unknown template key: {template_key}")
        return f"/local/{raw_template.format(**context)}"

    def relpath(self, path_str: str) -> str:
        s = path_str.replace("\\", "/")
        local_prefix = "/local/"
        if s.startswith(local_prefix):
            return "/" + s[len(local_prefix):]
        data_root = str(self._data_root).replace("\\", "/")
        if s.startswith(data_root):
            return "/" + s[len(data_root):].lstrip("/")
        return "/" + s.lstrip("/")

    def _resolve(self, template_key: str, context: Dict[str, Any]) -> Path:
        raw_template = _PATH_TEMPLATES.get(template_key)
        if not raw_template:
            raise ValueError(f"Unknown template key: {template_key}")

        ctx = dict(context)
        if "filename" in ctx:
            ctx["filename"] = _sanitize_filename(ctx["filename"])

        try:
            relative_path = raw_template.format(**ctx)
        except KeyError as e:
            raise KeyError(
                f"Template '{template_key}' missing context variable: {e}")

        full_path = self._data_root / relative_path

        abs_root = self._data_root.resolve()
        abs_full = full_path.resolve()
        if not abs_full.is_relative_to(abs_root):
            raise PermissionError(f"path escape blocked: {full_path}")

        full_path.parent.mkdir(parents=True, exist_ok=True)
        return full_path


class ProjectScope:

    def __init__(self, resolver: PathResolver, project_id: str):
        self._resolver = resolver
        self._project_id = project_id
        self._context = {"project_id": project_id}
        self._portrait = PortraitScope(resolver, project_id)

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def portrait(self) -> "PortraitScope":
        return self._portrait

    def path(self, filename: str) -> str:
        return str(self._resolver._resolve("project_file", {**self._context, "filename": filename}))

    def url(self, filename: str) -> str:
        return self._resolver._url("project_file", {**self._context, "filename": filename})

    def scene(self, scene_idx: int) -> "SceneScope":
        return SceneScope(self._resolver, self._project_id, scene_idx)


class PortraitScope:

    def __init__(self, resolver: PathResolver, project_id: str):
        self._resolver = resolver
        self._context = {"project_id": project_id}

    # full path for backend
    def path(self, filename: str) -> str:
        return str(self._resolver._resolve("portrait", {**self._context, "filename": filename}))

    # for front
    def url(self, filename: str) -> str:
        return self._resolver._url("portrait", {**self._context, "filename": filename})

    def scene(self, scene_idx: int) -> "SceneScope":
        return SceneScope(self._resolver, self._project_id, scene_idx)


class SceneScope:

    def __init__(self, resolver: PathResolver, project_id: str, scene_idx: int):
        self._resolver = resolver
        self._project_id = project_id
        self._scene_idx = scene_idx
        self._context = {"project_id": project_id, "scene_idx": str(scene_idx)}

    @property
    def scene_idx(self) -> int:
        return self._scene_idx

    @property
    def project_id(self) -> str:
        return self._project_id

    def path(self, filename: str) -> str:
        return str(self._resolver._resolve("scene_file", {**self._context, "filename": filename}))

    def url(self, filename: str) -> str:
        return self._resolver._url("scene_file", {**self._context, "filename": filename})

    def shot(self, shot_id: int) -> "ShotScope":
        return ShotScope(self._resolver, self._project_id, self._scene_idx, shot_id)


class ShotScope:

    def __init__(self, resolver: PathResolver, project_id: str, scene_idx: int, shot_id: int):
        self._resolver = resolver
        self._project_id = project_id
        self._scene_idx = scene_idx
        self._shot_id = shot_id
        self._context = {"project_id": project_id,
                         "scene_idx": str(scene_idx), "shot_id": str(shot_id)}

    def path(self, filename: str) -> str:
        return str(self._resolver._resolve("shot_file", {**self._context, "filename": filename}))

    def url(self, filename: str) -> str:
        return self._resolver._url("shot_file", {**self._context, "filename": filename})
