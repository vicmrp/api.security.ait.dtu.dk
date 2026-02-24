"""Service helpers for interacting with hub.cert.dk share API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, MutableMapping
from urllib.parse import urljoin

import requests
from django.conf import settings
from requests import RequestException, Response

logger = logging.getLogger(__name__)


class HubCertConfigurationError(RuntimeError):
    """Raised when the Hub CERT client configuration is invalid."""


class HubCertRequestError(RuntimeError):
    """Raised when a network call to hub.cert.dk fails."""


@dataclass(frozen=True)
class HubCertServiceResponse:
    """Simple container for upstream responses."""

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


class HubCertClient:
    """Tiny helper around the hub.cert.dk share endpoint."""

    DEFAULT_BASE_URL = "https://hub.cert.dk:8443"
    DEFAULT_TIMEOUT = 15  # seconds
    DEFAULT_USER_AGENT = "AIT-Security-API/1.0"

    @classmethod
    def _get_base_url(cls) -> str:
        base_url = getattr(settings, "HUB_CERT_API_BASE_URL", cls.DEFAULT_BASE_URL)
        if not base_url:
            raise HubCertConfigurationError("HUB_CERT_API_BASE_URL setting is empty")
        return base_url.rstrip("/") + "/"

    @classmethod
    def _build_url(cls, path: str) -> str:
        base = cls._get_base_url()
        return urljoin(base, path.lstrip("/"))

    @classmethod
    def _get_timeout(cls) -> float:
        timeout = getattr(settings, "HUB_CERT_API_TIMEOUT", cls.DEFAULT_TIMEOUT)
        try:
            return float(timeout)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            logger.warning("Invalid HUB_CERT_API_TIMEOUT=%s; falling back to default", timeout)
            return float(cls.DEFAULT_TIMEOUT)

    @classmethod
    def _build_authorization_header(cls) -> str:
        token = getattr(settings, "HUB_CERT_API_TOKEN", None)
        if token is None:
            raise HubCertConfigurationError("HUB_CERT_API_TOKEN setting is not configured")
        token = str(token).strip()
        if not token:
            raise HubCertConfigurationError("HUB_CERT_API_TOKEN setting is blank")
        if not token.lower().startswith("token "):
            token = f"token {token}"
        return token

    @classmethod
    def _default_headers(cls) -> MutableMapping[str, str]:
        headers: MutableMapping[str, str] = {
            "User-Agent": getattr(settings, "HUB_CERT_API_USER_AGENT", cls.DEFAULT_USER_AGENT),
            "Accept": "application/json",
        }
        headers["Authorization"] = cls._build_authorization_header()
        return headers

    @classmethod
    def get(
        cls,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HubCertServiceResponse:
        url = cls._build_url(path)
        timeout = cls._get_timeout()

        request_headers: MutableMapping[str, str] = cls._default_headers()
        if headers:
            request_headers.update(headers)

        try:
            logger.debug("Hub CERT request url=%s params=%s", url, params)
            response = requests.get(url, headers=request_headers, params=params, timeout=timeout)
        except RequestException as exc:  # pragma: no cover - network failure
            logger.warning("Hub CERT request failed url=%s error=%s", url, exc)
            raise HubCertRequestError(str(exc)) from exc

        return HubCertServiceResponse(response=response)

    @classmethod
    def get_share_events(
        cls,
        share_id: str,
        *,
        params: Mapping[str, object] | None = None,
    ) -> HubCertServiceResponse:
        if not share_id:
            raise HubCertConfigurationError("Share ID must be provided")
        path = f"shares/v2/{share_id}"
        return cls.get(path, params=params)
