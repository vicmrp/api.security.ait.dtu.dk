"""Minimal fallback implementation of the :mod:`pkg_resources` API.

The production Docker image that powers this project does not install the
``setuptools`` package, which traditionally exposes the ``pkg_resources``
module.  Third-party dependencies – notably ``drf_yasg`` – expect the module
to be importable in order to retrieve package version metadata.  When the
module is missing Django fails to start with ``ModuleNotFoundError: No module
named 'pkg_resources'``.

To keep the application working without modifying vendored dependencies we
provide a very small compatibility shim that exposes the subset of the
``pkg_resources`` API that the project relies on.  The implementation defers
to :mod:`importlib.metadata`, which is part of the Python standard library
starting from Python 3.8, to resolve package versions.

Because the Django project directory is added to ``sys.path`` ahead of
site-packages, this shim will also be used in environments where
``setuptools`` – and therefore the real ``pkg_resources`` module – is
installed.  The module intentionally only implements the pieces we need,
which keeps the surface area small while remaining compatible with current
usage in the codebase.
"""

from __future__ import annotations

from importlib import metadata
from typing import Any

__all__ = ["DistributionNotFound", "get_distribution"]


class DistributionNotFound(metadata.PackageNotFoundError):
    """Exception raised when a distribution cannot be located."""


class _Distribution:
    """Lightweight representation mimicking ``pkg_resources``' distribution."""

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name
        self.version = metadata.version(project_name)

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive.
        raise AttributeError(
            f"Attribute '{name}' is not implemented in the lightweight"
            " pkg_resources shim."
        )


def get_distribution(project_name: str) -> _Distribution:
    """Return distribution metadata for *project_name*.

    This mirrors ``pkg_resources.get_distribution`` for the subset of
    behaviour we need: returning an object whose ``version`` attribute contains
    the installed version string.  If the package cannot be located we raise a
    ``DistributionNotFound`` error to match the original API contract.
    """

    try:
        return _Distribution(project_name)
    except metadata.PackageNotFoundError as exc:  # pragma: no cover - thin shim.
        raise DistributionNotFound(str(exc)) from exc
