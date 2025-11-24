from .scripts.myview_generate_api_token import generate_custom_api_token as _generate_custom_api_token

def generate_custom_api_token(request=None, username=""):
    return _generate_custom_api_token(request=request, username=username)

