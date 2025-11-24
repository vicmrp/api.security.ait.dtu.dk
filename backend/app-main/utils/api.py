"""Shared utilities for API views that require secure logging and authentication."""

from __future__ import annotations

import json
import logging
from typing import Any

from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import AzureAdTokenAuthentication
logger = logging.getLogger(__name__)


class SecuredAPIView(APIView):
    """Base API view that mirrors the original security behaviour.

    The view enforces the session/token authentication combination used by the
    legacy endpoints and keeps the request logging that feeds the
    ``UserActivityLog`` model.  All API endpoints that should respect the
    limiter middleware can inherit from this class and keep the exact same
    runtime behaviour.
    """

    authentication_classes = [SessionAuthentication, TokenAuthentication, AzureAdTokenAuthentication]

    def finalize_response(  # type: ignore[override]
        self,
        request: Request,
        response: Response,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        try:
            self._log_api_request_activity(request, response)
        except Exception:  # pragma: no cover - best effort logging
            logger.exception("Failed to capture API activity log entry")
        return response

    def _log_api_request_activity(self, request: Request, response: Response) -> None:
        if request is None or response is None:
            return

        if request.method in {"OPTIONS", "HEAD"}:
            return

        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return

        status_code = getattr(response, "status_code", None)
        was_successful = status_code is not None and 200 <= status_code < 400

        message = ""
        if not was_successful:
            detail = getattr(response, "data", None)
            if isinstance(detail, (dict, list)):
                try:
                    message = json.dumps(detail, default=str)
                except TypeError:
                    message = str(detail)
            elif detail is not None:
                message = str(detail)
            else:
                message = getattr(response, "reason_phrase", "") or ""

        try:
            from myview.models import UserActivityLog

            UserActivityLog.log_api_request(
                user=user,
                request=request,
                was_successful=was_successful,
                status_code=status_code,
                message=message[:1024] if message else "",
            )
        except Exception:  # pragma: no cover - best effort logging
            logger.exception("Unable to persist user activity for %s", getattr(user, "username", user))
