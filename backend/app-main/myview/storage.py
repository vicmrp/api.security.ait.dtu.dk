import logging
from typing import Any

from django.conf import settings
from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger("myview.staticfiles")


class LenientCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Serve non-hashed paths instead of crashing when the manifest is stale.

    In developer environments we occasionally run with ``DEBUG=False`` without
    having executed ``collectstatic``. The default
    ``CompressedManifestStaticFilesStorage`` raises a ``ValueError`` in that
    situation which bubbles up as a 500 response. This wrapper keeps the
    existing behaviour when hashed assets are available, but logs a warning and
    falls back to the original asset path when the manifest entry or collected
    file is missing.
    """

    manifest_strict = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._logged_missing_files: set[str] = set()

    def stored_name(self, name: str) -> str:  # type: ignore[override]
        try:
            return super().stored_name(name)
        except ValueError as exc:
            self._log_missing(name, exc)
            return name

    def hashed_name(  # type: ignore[override]
        self,
        name: str,
        content=None,
        filename: str | None = None,
    ) -> str:
        try:
            return super().hashed_name(name, content=content, filename=filename)
        except ValueError as exc:
            self._log_missing(filename or name, exc)
            return name

    def _log_missing(self, name: str, exc: Exception) -> None:
        key = name.lower()
        if key in self._logged_missing_files:
            return
        self._logged_missing_files.add(key)
        if getattr(settings, "DEBUG", False) or getattr(settings, "WHITENOISE_USE_FINDERS", False):
            log_method = logger.debug
        else:
            log_method = logger.warning
        log_method(
            "Static asset '%s' missing from manifest or storage. "
            "Serving original path; run collectstatic to restore hashed assets. (%s)",
            name,
            exc,
        )
