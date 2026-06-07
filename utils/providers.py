"""
Provider preset system for Clipsay chat model configuration.

Supports auto-detection and resolution of LLM provider settings,
allowing users to specify a provider name (e.g., ``minimax``) instead
of manually configuring base_url and model details.
"""

import os
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"^<[A-Z0-9_]+>$")


def _is_placeholder(value: Any) -> bool:
    """Return True for the ``<LIKE_THIS>`` style placeholders used in example configs."""
    return isinstance(value, str) and bool(_PLACEHOLDER_RE.match(value.strip()))


def _is_blank(value: Any) -> bool:
    """Return True for missing, empty, or placeholder values."""
    if value is None:
        return True
    if isinstance(value, str) and (not value.strip() or _is_placeholder(value)):
        return True
    return False

# ---------------------------------------------------------------------------
# Provider presets
# ---------------------------------------------------------------------------

PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "openai": {
        # Generic OpenAI-compatible fallback.  When the user picks a
        # custom base_url (e.g. OpenRouter) the env var OPENAI_API_KEY
        # is used unless api_key is set explicitly in the yaml.
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "models": [],
        "temperature_range": (0.0, 2.0),
    },
    "minimax": {
        "base_url": "https://api.minimax.io/v1",
        "env_key": "MINIMAX_API_KEY",
        "default_model": "MiniMax-M3",
        "models": [
            "MiniMax-M3",
            "MiniMax-M2.7",
            "MiniMax-M2.7-highspeed",
        ],
        "temperature_range": (0.0, 1.0),
    },
    "agnes": {
        "base_url": "https://apihub.agnes-ai.com/v1",
        "env_key": "AGNES_API_KEY",
        "default_model": "agnes-2.0-flash",
        "models": [
            "agnes-2.0-flash",
            "agnes-1.5-flash",
        ],
        "temperature_range": (0.0, 2.0),
    },
}


def resolve_chat_model_config(init_args: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve provider presets and return final ``init_chat_model`` kwargs.

    If ``model_provider`` matches a known preset (e.g. ``minimax``), the
    returned dict will have:

    * ``model_provider`` rewritten to ``"openai"`` (OpenAI-compatible API)
    * ``base_url`` filled in from the preset when not already set
    * ``api_key`` sourced from the environment when not already set, OR
      when the yaml value is a ``<PLACEHOLDER>`` template
    * ``model`` defaulted to the preset's default model when not already set
    * ``temperature`` clamped to the provider's supported range

    For unknown providers the dict is returned unchanged.
    """
    args = dict(init_args)  # shallow copy
    provider = args.get("model_provider", "openai")

    preset = PROVIDER_PRESETS.get(provider)
    if preset is None:
        return args

    # base_url (only filled if the preset actually defines one — "openai"
    # has no base_url of its own, so custom base_urls are preserved)
    if _is_blank(args.get("base_url")):
        preset_base_url = preset.get("base_url")
        if preset_base_url:
            args["base_url"] = preset_base_url

    # api_key – fall back to env var (treat empty/placeholder as unset)
    if _is_blank(args.get("api_key")):
        env_key = preset.get("env_key", "")
        env_val = os.environ.get(env_key, "")
        if env_val:
            args["api_key"] = env_val
            logger.info("Using %s API key from environment variable %s", provider, env_key)

    # default model
    if _is_blank(args.get("model")):
        args["model"] = preset["default_model"]
        logger.info("Defaulting to model %s for provider %s", args["model"], provider)

    # temperature clamping
    temp_range = preset.get("temperature_range")
    if temp_range and "temperature" in args and args["temperature"] is not None:
        lo, hi = temp_range
        original = args["temperature"]
        args["temperature"] = max(lo, min(hi, original))
        if args["temperature"] != original:
            logger.warning(
                "Clamped temperature %.2f -> %.2f for provider %s",
                original, args["temperature"], provider,
            )

    # rewrite to openai-compatible provider for LangChain
    args["model_provider"] = "openai"

    # remember the original provider name so the validator (and any
    # downstream consumer) can still report provider-specific errors
    # like "set AGNES_API_KEY" rather than the generic OPENAI_API_KEY.
    args["_provider_preset"] = provider

    return args


_INTERNAL_RESOLVE_KEYS = ("_provider_preset",)


def strip_internal_resolve_keys(resolved_args: Dict[str, Any]) -> Dict[str, Any]:
    """Remove internal bookkeeping keys added by :func:`resolve_chat_model_config`.

    ``_provider_preset`` is a private hint used by the validator to remember
    which preset was applied.  If it leaks through ``init_chat_model(**args)``
    it gets forwarded to ``openai.AsyncCompletions.create(**kwargs)`` and
    raises ``TypeError: got an unexpected keyword argument '_provider_preset'``
    at the first real API call.  Callers should run this *after*
    :func:`validate_resolved_chat_model_config` and *before* ``init_chat_model``.
    """
    for key in _INTERNAL_RESOLVE_KEYS:
        resolved_args.pop(key, None)
    return resolved_args


def validate_resolved_chat_model_config(
    resolved_args: Dict[str, Any],
    *,
    provider_name: Optional[str] = None,
) -> None:
    """Raise a clear ``ValueError`` when an api_key is missing after resolution.

    Without this guard, an unset api_key silently propagates into
    ``langchain_openai.ChatOpenAI`` → ``openai.OpenAI(**)``, which raises
    the opaque message "The api_key client option must be set either by
    passing api_key to the client or by setting the OPENAI_API_KEY
    environment variable" — leaving the user to guess whether the problem
    is the OpenAI env var, the Agnes env var, or the yaml.

    The provider name is auto-detected from the ``_provider_preset`` key
    set by :func:`resolve_chat_model_config`.  Callers that did not run
    the resolver can pass ``provider_name`` explicitly.
    """
    if not _is_blank(resolved_args.get("api_key")):
        return

    provider = (
        provider_name
        or resolved_args.get("_provider_preset")
        or resolved_args.get("model_provider", "openai")
    )
    preset = PROVIDER_PRESETS.get(provider, {})
    env_key = preset.get("env_key", "<PROVIDER>_API_KEY")
    raise ValueError(
        f"Missing API key for chat model provider '{provider}'. "
        f"Provide it via one of:\n"
        f"  1. Set the environment variable {env_key}\n"
        f"  2. Fill 'api_key' under chat_model.init_args in your config yaml\n"
        f"     (replace the <...> placeholder with a real key)"
    )


def detect_provider_from_env() -> Optional[str]:
    """Return the name of a provider whose API key is found in the environment.

    Checks ``PROVIDER_PRESETS`` in definition order and returns the first
    match, or ``None`` if no key is set.
    """
    for name, preset in PROVIDER_PRESETS.items():
        env_key = preset.get("env_key", "")
        if env_key and os.environ.get(env_key):
            return name
    return None
