import warnings

warnings.warn(
    "Importing from backend.clients.legacy is deprecated. "
    "Use backend.clients.{video,image,llm} instead.",
    FutureWarning,
    stacklevel=2,
)
