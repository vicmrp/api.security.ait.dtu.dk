# load modules
from dotenv import load_dotenv, find_dotenv
import os
from typing import Optional, Tuple
from urllib.parse import urlparse

from ldap3 import ALL, Connection, Server

# Load .env file
load_dotenv(dotenv_path=find_dotenv())


def _get_clean_env(name: str) -> Optional[str]:
    """Return the environment variable stripped of whitespace or ``None``."""

    value = os.getenv(name)
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def _get_float_env(name: str, default: float, *, minimum: float | None = None) -> float:
    """Return a float from the environment variable with optional clamping."""

    value = os.getenv(name)
    if value is None:
        result = default
    else:
        try:
            result = float(value)
        except (TypeError, ValueError):
            result = default

    if minimum is not None and result < minimum:
        return minimum
    return result


def _missing_config_message(missing: list[str]) -> str:
    formatted = ', '.join(sorted(missing))
    return (
        "Missing required Active Directory configuration: "
        f"{formatted}. Update the environment configuration and try again."
    )


def _parse_server(value: str) -> tuple[str, bool, Optional[int]]:
    """Return host, use_ssl flag, and port from configuration string."""

    if not value:
        return "", True, None

    if "://" not in value:
        # Bare hostname or IP; assume LDAPS by default.
        return value, True, None

    parsed = urlparse(value)
    if not parsed.hostname:
        return value, True, None

    scheme = (parsed.scheme or "ldaps").lower()
    use_ssl = scheme != "ldap"
    port = parsed.port
    if port is None:
        port = 636 if use_ssl else 389
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        port_int = 636 if use_ssl else 389
    return parsed.hostname, use_ssl, port_int


def active_directory_connect() -> Tuple[Optional[Connection], str]:
    try:
        ad_username = _get_clean_env('ACTIVE_DIRECTORY_USERNAME')
        ad_password = _get_clean_env('ACTIVE_DIRECTORY_PASSWORD')
        ad_server_raw = _get_clean_env('ACTIVE_DIRECTORY_SERVER')

        missing_variables = [
            name
            for name, value in {
                'ACTIVE_DIRECTORY_USERNAME': ad_username,
                'ACTIVE_DIRECTORY_PASSWORD': ad_password,
                'ACTIVE_DIRECTORY_SERVER': ad_server_raw,
            }.items()
            if not value
        ]

        if missing_variables:
            return None, _missing_config_message(missing_variables)

        ad_host, use_ssl, ad_port = _parse_server(ad_server_raw)
        if not ad_host:
            return None, _missing_config_message(['ACTIVE_DIRECTORY_SERVER'])

        connect_timeout = _get_float_env(
            'ACTIVE_DIRECTORY_CONNECT_TIMEOUT',
            5.0,
            minimum=0.1,
        )
        receive_timeout = _get_float_env(
            'ACTIVE_DIRECTORY_RECEIVE_TIMEOUT',
            10.0,
            minimum=0.1,
        )
        # ldap3 expects integer timeouts; coercing to int avoids socket errors.
        connect_timeout_int = max(1, int(round(connect_timeout)))
        receive_timeout_int = max(1, int(round(receive_timeout)))

        server_kwargs = {
            "use_ssl": use_ssl,
            "get_info": ALL,
            "connect_timeout": connect_timeout_int,
        }
        if ad_port is not None:
            try:
                server_kwargs["port"] = int(ad_port)
            except (TypeError, ValueError):
                pass

        server = Server(
            ad_host,
            **server_kwargs,
        )
        conn = Connection(
            server,
            ad_username,
            ad_password,
            receive_timeout=receive_timeout_int,
        )

        # Check if the connection is successful
        if not conn.bind():
            return None, "Failed to connect to Active Directory"

        return conn, "Successfully connected to Active Directory"
    except Exception as e:
        return None, f"Error connecting to Active Directory: {type(e).__name__}: {e}"


def run():
    ad_connection_object, message = active_directory_connect()
    if message:
        print(message)


# if main
if __name__ == "__main__":
    run()
