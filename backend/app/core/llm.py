"""Multi-model LLM invocation with automatic quota & availability fallback."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def call_gemini_with_fallback(
    client: Any,
    contents: Any,
    config: Any,
    preferred_model: Optional[str] = None
) -> Any:
    """Executes client.models.generate_content with automatic failover across models.
    
    If the preferred model (e.g. gemini-2.5-flash) is retired (404) or exceeds rate limits
    (429 RESOURCE_EXHAUSTED), this automatically tries alternative active Flash models
    (gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3.6-flash).
    """
    from app.core.config import settings

    candidates = [
        preferred_model,
        getattr(settings, "default_model", None),
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
    ]

    seen = set()
    models_to_try = []
    for m in candidates:
        if m and m not in seen:
            seen.add(m)
            models_to_try.append(m)

    last_err = None
    for model_name in models_to_try:
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            err_str = str(exc)
            if any(k in err_str for k in ("404", "429", "RESOURCE_EXHAUSTED", "NOT_FOUND", "503", "UNAVAILABLE")):
                logger.warning(
                    "Model %s failed (%s). Trying next fallback model...",
                    model_name,
                    exc
                )
                last_err = exc
                continue
            raise exc

    if last_err:
        raise last_err
    raise RuntimeError("No Gemini models were available.")
