"""Utilities for interacting with the Supabase instance used by the project.

The helper exported by this module returns a cached Supabase client that can be
used alongside the primary Django PostgreSQL connection without replacing it.
"""
from __future__ import annotations

from functools import lru_cache
import os
from typing import Literal

from supabase import Client, create_client


class SupabaseConfigurationError(RuntimeError):
    """Raised when the Supabase credentials are missing from the environment."""


def _get_env_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SupabaseConfigurationError(
            f"The environment variable '{name}' must be configured to use Supabase."
        )
    return value


@lru_cache(maxsize=2)
def get_supabase_client(*, role: Literal["anon", "service"] = "anon") -> Client:
    """Return a configured Supabase client.

    Parameters
    ----------
    role:
        Select which API key to use. ``"anon"`` (the default) authenticates as the
        public client, while ``"service"`` authenticates using the service role key
        for elevated access.
    """

    supabase_url = _get_env_setting("SUPABASE_URL")
    key_var = "SUPABASE_SERVICE_ROLE_KEY" if role == "service" else "SUPABASE_ANON_KEY"
    supabase_key = _get_env_setting(key_var)

    return create_client(supabase_url, supabase_key)


__all__ = ["get_supabase_client", "SupabaseConfigurationError"]
