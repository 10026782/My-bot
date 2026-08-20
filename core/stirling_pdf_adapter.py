"""Stirling-PDF capability adapter — POC / NOT PRODUCTION READY.

One operation only: merge_pdfs. Governed input artifacts (never arbitrary
caller-supplied filesystem paths) -> isolated, internal-only Stirling-PDF
2.14.3 backend service -> a governed output PDF artifact. See
docs/research/STIRLING_PDF_CAPABILITY_POC.md for full scope, the
authentication-licensing nuance discovered while building this (the
customGlobalAPIKey/login mechanism this POC uses lives in Stirling-PDF's
proprietary-licensed module, not the MIT core — permitted here under that
license's own Trial/Minimal-Use carve-out, but a real blocker before any
production wiring), and every other production blocker.

This is a sync capability (CapabilityContract.execution_mode == "sync"):
submit() performs the whole merge and returns a terminal SubmitResult
directly — poll() is never legitimately reached and exists only to satisfy
the ExternalAdapter contract.

Concurrency: intentionally NOT gated by a `.policy` object in this POC — see
the module docstring in docs/research/STIRLING_PDF_CAPABILITY_POC.md
("Concurrency decision") for why the existing adapter-declared `.policy`
mechanism (built for MPT's long-lived async jobs) is not a safe fit for a
fast synchronous single-flight guarantee, and what a real production
concurrency primitive would need to look like.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
from pathlib import Path

import httpx

from core.artifact_store import ArtifactStoreError
from core.external_execution_boundary import PollResult, SubmitResult
from core.local_artifact_store import LocalArtifactStore

UPSTREAM_REPOSITORY = "https://github.com/Stirling-Tools/Stirling-PDF"
UPSTREAM_VERSION = "2.14.3"

_MERGE_PATH = "/api/v1/general/merge-pdfs"
_STATUS_PATH = "/api/v1/info/status"
_ALLOWED_MIME = "application/pdf"

_MIN_FILES = 2
_MAX_FILES = 10
_MAX_FILE_BYTES = 20 * 1024 * 1024
_MAX_TOTAL_BYTES = 60 * 1024 * 1024
_MAX_OUTPUT_BYTES = 80 * 1024 * 1024
_DEFAULT_HTTP_TIMEOUT_SECONDS = 45.0
_MAX_HTTP_TIMEOUT_SECONDS = 120.0
_HEALTHCHECK_TIMEOUT_SECONDS = 5.0

_REQUIRED_INPUT_FIELDS = ("result_ref", "mime_type", "size", "sha256")


class _StirlingDeterministicFailure(Exception):
    """Stirling-PDF returned a definite non-200 HTTP response."""


def _configured_store():
    root = os.environ.get("STIRLING_PDF_ARTIFACT_ROOT")
    if not root:
        return None
    return LocalArtifactStore(root=root, subdir="stirling_pdf", suffix=".pdf")


def _within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path), str(root))) == str(root)
    except ValueError:
        return False


class StirlingPDFAdapter:
    name = "stirling_pdf"

    # See core/external_execution_boundary.py's _UNIVERSAL_EVIDENCE_KEYS for
    # the shared core (adapter_name, provider_status, result_ref,
    # result_checksum, completed_at, ...).
    evidence_extra_keys = frozenset({
        "operation", "input_count", "input_total_bytes", "output_bytes",
        "stirling_pdf_version", "elapsed_ms",
    })

    def __init__(self, *, base_url=None, api_key=None, store=None, input_root=None,
                 http_timeout_seconds=None):
        self.base_url = (base_url if base_url is not None else os.environ.get("STIRLING_PDF_BASE_URL", "")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("STIRLING_PDF_API_KEY", "")
        self.store = store if store is not None else _configured_store()
        input_root_value = input_root if input_root is not None else os.environ.get("STIRLING_PDF_INPUT_ROOT")
        self.input_root = Path(input_root_value).resolve() if input_root_value else None
        timeout_value = http_timeout_seconds if http_timeout_seconds is not None else os.environ.get("STIRLING_PDF_HTTP_TIMEOUT_SECONDS", _DEFAULT_HTTP_TIMEOUT_SECONDS)
        self.http_timeout_seconds = min(float(timeout_value), _MAX_HTTP_TIMEOUT_SECONDS)

    def submit(self, request: dict) -> SubmitResult:
        payload = request.get("payload") if isinstance(request, dict) else None
        try:
            input_paths = self._validate_inputs(payload)
        except ValueError as exc:
            return SubmitResult("failed", failure_code=f"stirling_pdf_{exc}"[:120])
        if not self.base_url:
            return SubmitResult("failed", failure_code="stirling_pdf_base_url_unconfigured")
        if not self.api_key:
            return SubmitResult("failed", failure_code="stirling_pdf_api_key_unconfigured")
        if self.store is None:
            return SubmitResult("failed", failure_code="stirling_pdf_storage_unconfigured")

        try:
            response, elapsed_ms = self._call_merge(input_paths)
        except _StirlingDeterministicFailure as exc:
            return SubmitResult("failed", failure_code=str(exc)[:120])
        except Exception:
            # Network-level exceptions (timeout, connection reset, DNS/TLS
            # failure) never tell us whether the server-side merge actually
            # ran — never presented as success.
            return SubmitResult("outcome_unknown", failure_code="stirling_pdf_submit_exception")

        try:
            output_bytes = self._validate_output(response)
        except ValueError as exc:
            return SubmitResult("failed", failure_code=f"stirling_pdf_{exc}"[:120])

        contract_id = str(request.get("contract_id") or "")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as tmp:
                tmp.write(output_bytes)
                tmp_path = Path(tmp.name)
            stored = self.store.put(path=tmp_path, identity=contract_id, metadata={})
        except ArtifactStoreError as exc:
            status = "outcome_unknown" if exc.uncertain else "failed"
            return SubmitResult(status, failure_code=exc.code[:120])
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        input_total_bytes = sum(p.stat().st_size for p in input_paths)
        return SubmitResult(
            "completed",
            result_ref=stored.result_ref,
            evidence={
                "adapter_name": self.name,
                "provider_status": "completed",
                "result_ref": stored.result_ref,
                "result_checksum": stored.sha256,
                "operation": "merge_pdfs",
                "input_count": str(len(input_paths)),
                "input_total_bytes": str(input_total_bytes),
                "output_bytes": str(len(output_bytes)),
                "stirling_pdf_version": UPSTREAM_VERSION,
                "elapsed_ms": str(elapsed_ms),
            },
        )

    def poll(self, job) -> PollResult:
        # execution_mode is "sync" — submit() already returned a terminal
        # result and the boundary never schedules this job for polling.
        return PollResult("outcome_unknown", failure_code="stirling_pdf_unexpected_poll")

    def healthcheck(self) -> bool:
        """Narrow readiness probe -- not BOSS health-monitoring infrastructure."""
        if not self.base_url:
            return False
        try:
            response = httpx.get(f"{self.base_url}{_STATUS_PATH}", timeout=_HEALTHCHECK_TIMEOUT_SECONDS)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _validate_inputs(self, payload) -> list[Path]:
        if not isinstance(payload, dict):
            raise ValueError("payload")
        inputs = payload.get("inputs")
        if not isinstance(inputs, list):
            raise ValueError("inputs_missing")
        if len(inputs) < _MIN_FILES:
            raise ValueError("too_few_inputs")
        if len(inputs) > _MAX_FILES:
            raise ValueError("too_many_inputs")
        if self.input_root is None:
            raise ValueError("input_root_unconfigured")

        paths: list[Path] = []
        total_bytes = 0
        for item in inputs:
            if not isinstance(item, dict) or any(k not in item for k in _REQUIRED_INPUT_FIELDS):
                raise ValueError("input_metadata_invalid")
            result_ref, mime_type, size, sha256 = (
                item["result_ref"], item["mime_type"], item["size"], item["sha256"],
            )
            if not isinstance(result_ref, str) or not isinstance(mime_type, str) or not isinstance(sha256, str) or not isinstance(size, int):
                raise ValueError("input_metadata_invalid")

            raw_path = Path(result_ref)
            if raw_path.is_symlink():
                raise ValueError("input_symlink")
            path = raw_path.resolve()
            if not _within(path, self.input_root):
                raise ValueError("input_outside_approved_root")
            if not path.is_file():
                raise ValueError("input_not_regular_file")

            actual_size = path.stat().st_size
            if actual_size == 0:
                raise ValueError("input_empty")
            if actual_size > _MAX_FILE_BYTES:
                raise ValueError("input_too_large")
            if mime_type != _ALLOWED_MIME:
                raise ValueError("input_mime_mismatch")

            data = path.read_bytes()
            if not data.startswith(b"%PDF-"):
                raise ValueError("input_pdf_signature_invalid")
            if actual_size != size:
                raise ValueError("input_size_mismatch")
            if hashlib.sha256(data).hexdigest() != sha256:
                raise ValueError("input_checksum_mismatch")

            total_bytes += actual_size
            if total_bytes > _MAX_TOTAL_BYTES:
                raise ValueError("total_input_too_large")
            paths.append(path)

        return paths

    def _call_merge(self, input_paths: list[Path]) -> tuple[httpx.Response, int]:
        opened = [path.open("rb") for path in input_paths]
        try:
            files = [("fileInput", (path.name, handle, _ALLOWED_MIME)) for path, handle in zip(input_paths, opened)]
            data = {"sortType": "orderProvided", "removeCertSign": "false", "generateToc": "false"}
            headers = {"X-API-KEY": self.api_key}
            started = time.monotonic()
            response = httpx.post(
                f"{self.base_url}{_MERGE_PATH}", files=files, data=data, headers=headers,
                timeout=self.http_timeout_seconds,
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
        finally:
            for handle in opened:
                handle.close()
        if response.status_code != 200:
            raise _StirlingDeterministicFailure(f"stirling_pdf_http_{response.status_code}")
        return response, elapsed_ms

    @staticmethod
    def _validate_output(response) -> bytes:
        content_type = response.headers.get("content-type", "")
        if content_type and not content_type.startswith(_ALLOWED_MIME):
            raise ValueError("output_content_type_mismatch")
        data = response.content
        if not data:
            raise ValueError("output_empty")
        if len(data) > _MAX_OUTPUT_BYTES:
            raise ValueError("output_too_large")
        if not data.startswith(b"%PDF-"):
            raise ValueError("output_signature_invalid")
        return data
