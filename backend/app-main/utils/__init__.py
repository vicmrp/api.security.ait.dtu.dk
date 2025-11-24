"""Utility helpers shared across the Django project."""

from .supabase_client import get_supabase_client, SupabaseConfigurationError

__all__ = ["get_supabase_client", "SupabaseConfigurationError"]
