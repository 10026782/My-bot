"""Safe deterministic document conversion API."""

from .engine import convert_document
from .result import ConversionResult

__all__ = ["ConversionResult", "convert_document"]
