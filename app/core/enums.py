"""Enums compatibles con Python 3.9+.

StrEnum está disponible en Python 3.11+. Este módulo proporciona
una versión compatible para versiones anteriores.
"""

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Enum compatible con string para Python <3.11."""

        pass


__all__ = ["StrEnum"]
