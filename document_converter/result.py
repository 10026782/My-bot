from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConversionResult:
    status: str
    confidence: str
    warnings: list[str]
    output_file: Optional[str]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "output_file": self.output_file,
        }


def success(output_file: str, warnings: list[str] | None = None) -> ConversionResult:
    return ConversionResult(
        status="success",
        confidence="high",
        warnings=warnings or [],
        output_file=output_file,
    )


def failure(message: str, warnings: list[str] | None = None) -> ConversionResult:
    return ConversionResult(
        status=f"error: {message}",
        confidence="low",
        warnings=warnings or [],
        output_file=None,
    )
