"""External credential discovery helpers."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping


def environment_credentials(names: Iterable[str]) -> Mapping[str, str]:
    """Read explicitly requested credentials from the process environment only."""
    return {name: value for name in names if (value := os.environ.get(name)) is not None}
