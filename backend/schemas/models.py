"""Shared data models for model endpoint configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Credentials & rate limits for a model endpoint (chat/LLM, image, video, vision, etc.)."""
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    rate_limit_min: int = 50
    rate_limit_day: int = 2000
