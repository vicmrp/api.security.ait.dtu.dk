class Client:  # pragma: no cover
    """Lightweight stub used for local testing where the supabase package is unavailable."""


def create_client(*args, **kwargs):  # pragma: no cover
    raise NotImplementedError("Supabase client is not available in this environment.")

