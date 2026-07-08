"""Prompt sanitizer with persistent learned rules.

Two-layer defence:
  1. Dictionary-based pre-filter (auto-learned from ContentFilterError).
  2. LLM rewrite fallback in the calling layer.

Learned rules are persisted to ``DATA_ROOT / sanitizer_rules.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.utils.paths import DATA_ROOT

_SANITIZER_PATH = Path(DATA_ROOT) / "sanitizer_rules.json"

_DEFAULT_REPLACEMENTS: dict[str, str] = {
    "裸露": "露出的",
    "赤裸": "未遮蔽",
    "一丝不挂": "穿着衣物",
    "丰满": "匀称",
    "乳沟": "胸前",
    "臀部": "身后",
    "大腿根部": "大腿上方",
    "肚脐": "腹部",
    "内衣": "贴身衣物",
    "内裤": "短裤",
    "比基尼": "泳装",
    "透视装": "轻薄装",
    "半透明": "轻薄的",
    "冻疮": "冻伤",
    "血迹": "红色痕迹",
    "伤口": "伤处",
    "疤痕": "痕迹",
    "瘀青": "青紫",
    "红肿": "微红",
    "尸体": "身躯",
    "死亡": "沉睡",
    "暴力": "激烈",
    "武器": "工具",
    "性感": "迷人",
    "诱惑": "吸引",
    "暴露": "外露",
    "湿身": "沾湿",
}


class Sanitizer:
    _instance: Sanitizer | None = None

    @classmethod
    def instance(cls) -> Sanitizer:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._rules: dict[str, str] = dict(_DEFAULT_REPLACEMENTS)
        self._rules.update(self._load_learned())

    def sanitize(self, text: str) -> str:
        for word, replacement in self._rules.items():
            text = text.replace(word, replacement)
        return text

    def learn(self, word: str, replacement: str) -> None:
        if word not in self._rules:
            self._rules[word] = replacement
            self._persist()

    def _load_learned(self) -> dict[str, str]:
        try:
            if _SANITIZER_PATH.exists():
                return json.loads(_SANITIZER_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _persist(self) -> None:
        _SANITIZER_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SANITIZER_PATH.write_text(
            json.dumps(self._rules, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


sanitizer = Sanitizer.instance()
