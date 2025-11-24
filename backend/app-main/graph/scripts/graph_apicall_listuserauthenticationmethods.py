"""Helpers for listing Microsoft Graph authentication methods."""

from ._graph_get_bearertoken import _get_bearertoken
from ._http import graph_request


def list_user_authentication_methods(user_id):
    """Return the authentication methods configured for a given user."""

    token = _get_bearertoken()
    api_endpoint = f"https://graph.microsoft.com/v1.0/users/{user_id}/authentication/methods"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = graph_request("GET", api_endpoint, headers=headers, timeout=20)
    return response, response.status_code


def run():
    user_id = "3358461b-2b36-4019-a2b7-2da92001cf7c"
    response, status_code = list_user_authentication_methods(user_id)
    print(response)


if __name__ == "__main__":
    run()
