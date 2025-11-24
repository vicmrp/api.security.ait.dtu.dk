
import logging
import os
import time
from typing import Optional, Tuple

import requests

from ._graph_get_bearertoken import _get_bearertoken
from ._http import graph_request


logger = logging.getLogger(__name__)


def _load_throttle_window(default: int = 60) -> int:
    """Return the configured throttling window for token warnings."""

    raw_value = os.getenv("GRAPH_TOKEN_WARNING_THROTTLE_SECONDS")
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    # A non-positive window disables throttling, so guard against negatives
    return max(0, value)


_TOKEN_WARNING_WINDOW = _load_throttle_window()
_TOKEN_WARNING_STATE = {"last_logged": float("-inf"), "suppressed": 0}


def _log_token_failure(user_principal_name: str) -> None:
    """Log token acquisition failures with basic throttling.

    When Azure AD is temporarily unavailable we can end up attempting to look up
    hundreds of users in quick succession. Without throttling this would produce
    one warning per lookup, flooding the logs and obscuring other issues. We
    therefore limit logging to once per configured window while keeping track of
    how many similar warnings were suppressed.
    """

    if _TOKEN_WARNING_WINDOW == 0:
        logger.warning(
            "Unable to acquire Microsoft Graph token while requesting user %s",
            user_principal_name,
        )
        _TOKEN_WARNING_STATE["suppressed"] = 0
        return

    now = time.monotonic()
    last_logged = _TOKEN_WARNING_STATE["last_logged"]

    if now - last_logged >= _TOKEN_WARNING_WINDOW:
        suppressed = _TOKEN_WARNING_STATE["suppressed"]
        if suppressed:
            logger.warning(
                "Unable to acquire Microsoft Graph token while requesting user %s "
                "(suppressed %d similar warnings)",
                user_principal_name,
                suppressed,
            )
        else:
            logger.warning(
                "Unable to acquire Microsoft Graph token while requesting user %s",
                user_principal_name,
            )

        _TOKEN_WARNING_STATE["last_logged"] = now
        _TOKEN_WARNING_STATE["suppressed"] = 0
        return

    _TOKEN_WARNING_STATE["suppressed"] += 1


def _build_graph_endpoint(user_principal_name: str, select_parameters: Optional[str]) -> str:
    if select_parameters:
        return f"https://graph.microsoft.com/v1.0/users/{user_principal_name}?{select_parameters}"
    return f"https://graph.microsoft.com/v1.0/users/{user_principal_name}"


def _error_response(message: str, *, code: str = "RequestError", status: int = 503):
    return {"error": {"code": code, "message": message}}, status


def get_user(*, user_principal_name, select_parameters=None) -> Tuple[dict, int]:
    """Retrieve a user from Microsoft Graph.

    Network failures and JSON decoding issues are handled gracefully, returning a
    structured error response instead of raising to the caller.
    """

    # Microsoft api documentation
    # https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0&tabs=http

    token = _get_bearertoken()
    if not token:
        _log_token_failure(user_principal_name)
        return _error_response("Failed to acquire access token", code="AuthTokenUnavailable", status=503)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    api_endpoint = _build_graph_endpoint(user_principal_name, select_parameters)

    try:
        response = graph_request("GET", api_endpoint, headers=headers, timeout=20)
    except requests.exceptions.RequestException as exc:
        logger.warning(
            "Microsoft Graph request for %s failed: %s",
            user_principal_name,
            exc,
        )
        return _error_response(str(exc), status=503)

    try:
        data = response.json()
    except ValueError:
        logger.warning(
            "Received non-JSON response from Microsoft Graph for %s (status %s)",
            user_principal_name,
            response.status_code,
        )
        data = {"raw": response.text}

    return data, response.status_code




def run():
    user_principal_name = 'adm-vicre@dtu.dk'                    # will return status 200
    # user_principal_name = 'adm-vicre-not-a-real-user@dtu.dk'    # will return status 404
    response, status_code = get_user(user_principal_name=user_principal_name, select_parameters='$select=onPremisesImmutableId,userPrincipalName')
    print(response.get('onPremisesImmutableId'))



# if main 
if __name__ == "__main__":
    run()

