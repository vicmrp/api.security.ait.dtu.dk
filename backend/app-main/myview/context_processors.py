import logging

def swagger_defaults(request):
    """Provide default token and Authorization header placeholder for Swagger UI."""

    token_value = ""
    authorization_value = ""

    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        try:
            from rest_framework.authtoken.models import Token

            token, _ = Token.objects.get_or_create(user=user)
            token_value = token.key
            authorization_value = f"Token {token_value}"
        except Exception:
            logging.getLogger(__name__).exception("Failed to obtain user API token for Swagger defaults")

    return {
        "swagger_default_token": token_value,
        "swagger_default_authorization": authorization_value,
    }
