"""Service layer for interacting with the DTU-hosted Have I Been Pwned API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, MutableMapping
from urllib.parse import urljoin

import requests
from django.conf import settings
from requests import RequestException, Response

logger = logging.getLogger(__name__)


class HIBPConfigurationError(RuntimeError):
    """Raised when the HIBP client configuration is invalid."""


class HIBPRequestError(RuntimeError):
    """Raised when a network call to the HIBP API fails."""


@dataclass(frozen=True)
class HIBPServiceResponse:
    """Container for responses returned by :class:`HIBPClient`."""

    response: Response

    @property
    def status_code(self) -> int:
        return self.response.status_code

    @property
    def headers(self) -> Mapping[str, str]:
        return self.response.headers

    def json(self) -> object:
        return self.response.json()

    @property
    def text(self) -> str:
        return self.response.text


class HIBPClient:
    """Small helper wrapping calls to the DTU HIBP proxy service."""

    DEFAULT_BASE_URL = "https://api.haveibeenpwned.cert.dk"
    DEFAULT_TIMEOUT = 15  # seconds

    @classmethod
    def _get_base_url(cls) -> str:
        base_url = getattr(settings, "HIBP_API_BASE_URL", cls.DEFAULT_BASE_URL)
        if not base_url:
            raise HIBPConfigurationError("HIBP_API_BASE_URL setting is empty")
        return base_url.rstrip("/") + "/"

    @classmethod
    def _build_url(cls, path: str) -> str:
        base = cls._get_base_url()
        return urljoin(base, path.lstrip("/"))

    @classmethod
    def _get_timeout(cls) -> float:
        timeout = getattr(settings, "HIBP_API_TIMEOUT", cls.DEFAULT_TIMEOUT)
        try:
            return float(timeout)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            logger.warning("Invalid HIBP_API_TIMEOUT=%s; falling back to default", timeout)
            return float(cls.DEFAULT_TIMEOUT)

    @classmethod
    def _default_headers(cls) -> MutableMapping[str, str]:
        user_agent = getattr(settings, "HIBP_API_USER_AGENT", "AIT-Security-API/1.0")
        return {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    @classmethod
    def get(
        cls,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HIBPServiceResponse:
        """Perform a GET request against the HIBP API."""

        request_headers: MutableMapping[str, str] = cls._default_headers()
        if headers:
            request_headers.update(headers)

        url = cls._build_url(path)
        timeout = cls._get_timeout()

        try:
            logger.debug("HIBP request url=%s params=%s", url, params)
            response = requests.get(url, headers=request_headers, params=params, timeout=timeout)
        except RequestException as exc:  # pragma: no cover - network failure
            logger.warning("HIBP request failed url=%s error=%s", url, exc)
            raise HIBPRequestError(str(exc)) from exc

        return HIBPServiceResponse(response=response)
