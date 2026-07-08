from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from backend.core.types import ImageRef

if TYPE_CHECKING:
    from backend.schemas.character import CharacterRead

CHARACTER_VIEWS = ("front", "side", "back")


def character_image_refs(char_idx: int, characters: List["CharacterRead"]) -> List[Tuple[str, str, str]]:
    if char_idx < 0 or char_idx >= len(characters):
        return []
    c = characters[char_idx]
    refs: List[Tuple[str, str, str]] = []
    for view in CHARACTER_VIEWS:
        path = getattr(c, f"{view}_path", "")
        url = getattr(c, f"{view}_url", "")
        if not path and not url:
            continue
        refs.append((path, url, ""))
    return refs


def collect_character_references(
    vis_char_idxs: List[int],
    characters: List["CharacterRead"],
) -> List[ImageRef]:
    refs: List[ImageRef] = []
    for character_idx in vis_char_idxs:
        for path, url, desc in character_image_refs(character_idx, characters):
            refs.append(ImageRef(url=url, prompt=desc))
    return refs
