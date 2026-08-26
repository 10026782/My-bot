# Current Media, Session, and Idempotency Contracts

**Status:** current code contract; static documentation only
**Authority:** the implementation on `main` is authoritative. This document
describes observable boundaries and does not add runtime guarantees.

## Media results and processing status

`media_handler.py` exposes three related types:

- `MediaError` carries `error_code`, user-facing `error_message`, and
  `retryable`.
- `MediaResult` carries `ok`, optional asset/Drive/transcript fields, a user
  `message`, and an optional `MediaError`.
- `MediaProcessingStatus` is the bounded status projection used where a
  provider acknowledgement must be separated from downstream processing. Its
  statuses are `COMPLETED`, `FAILED`, and `NOT_COMPLETED`; only `COMPLETED`
  has `success_evidence=True`.

Photo/document callers treat `MediaResult.ok` as the result of the local
Drive-plus-metadata pipeline. Voice callers may receive a successful result
that contains a transcript, inbox save, or approval request rather than a
Drive asset. Callers should display `message` when present and use `error` and
`retryable` for failure handling; they must not infer success from a provider
ACK or from generated text alone.

## WhatsApp acknowledgement

The WhatsApp webhook returns transport-level receipt after the inbound event
has been accepted and processed by the request path. For Meta WhatsApp, the
outbound reply remains a stub: a computed reply is logged but not sent. Media
processing is reported separately in the response when a media adapter
produces a status. A transport `200`/receipt therefore does not mean that a
Drive upload, Media Files write, or outbound WhatsApp message completed.

## File context and `last_uploaded_file`

`PersistentSessionStore` keeps `last_uploaded_file` inside the session state.
The value is a serialized `FileUploadResult` describing either a
`drive_file` (Media Files record ID and Drive URL) or an `inbox_file` (Decision
Inbox record ID). Session state is synchronized to the Airtable `Sessions`
table in the `State JSON` field and is restored after a process restart when
the external store is available. The linked-record meaning of `file_id` is
therefore determined by `FileUploadResult.type`; it is not universally a
Telegram file ID.

The old `SPEC_File_Context_Reference.md` citation in historical code comments
is not an authority and the file is absent. The current authority is
`session_store.py` and the callers in `app.py`/`tma_api.py`.

## Google Drive artifact store

`GoogleDriveArtifactStore` is an `ArtifactStore` implementation for current
MPT video outputs. It accepts an existing local file, requires
`GOOGLE_DRIVE_ARTIFACT_FOLDER_ID` (or an explicit folder ID), uploads with
resumable Google Drive calls, checks identity/size/MIME/parent metadata, and
returns a `StoredArtifact` containing a JSON `result_ref`, Drive file ID,
size, checksum, and MIME type. It retries only bounded transient failures;
uncertain provider outcomes are surfaced as errors. `cleanup()` does not
delete the retained Drive artifact.

This is a storage boundary, not a general media-ingestion replacement.
Telegram/TMA/WhatsApp media currently uses `media_handler.py` plus
`media_gateway.py`; MPT-specific use must not be generalized from this
document.

## Media Files responsibility

The Airtable `Media Files` table stores media metadata and the Drive
reference, not file bytes. `media_gateway.py` is the metadata persistence
boundary: it creates and patches `Media Files` records through
`tools.airtable_gateway`, and reads exact `Logical Media Key` matches for
reuse/reconciliation. `media_handler.py` orchestrates source-specific upload
and processing; `app.py` and `tma_api.py` are current ingress callers.

The table currently includes source, domain, MIME/type, size, Drive ID/URL,
logical media key, transcript fields, creator, linked lead, and persistence
state fields as defined by `MediaFileFields`. The schema must exist in
Airtable before the relevant media flags are enabled. This document does not
claim that every field is present in every deployment.

## Session durability

`session_store.PersistentSessionStore` owns lead/session workflow state. It
keeps an in-process LRU cache (up to 1000 sessions), synchronizes updates to
Airtable `Sessions`, and attempts to restore a session after a restart. A
failed or unavailable Airtable sync is not equivalent to durable persistence;
the code records/logs that outcome and callers must not treat the RAM cache as
the durable source.

`memory_store.MemoryStore` owns ordinary conversation history and the
separate action-state context-event channel used to shape the next model call.
It is process-local, capped, and expires inactive entries after 12 hours. A
restart or redeploy loses it. It is not a durable business record and does
not replace ActionContract/ExecutionLedger lifecycle truth.

## Idempotency boundaries

- `guards/idempotency.py` blocks repeated inbound events using a hashed
  channel/sender/content key with a five-minute TTL. It is the ingress retry
  guard, not a durable business identity.
- `tools/dispatcher.py` uses table-specific deduplication fields for selected
  Airtable writes, such as task title or lead phone. It prevents duplicate
  business records where that table mapping applies; it is not a universal
  request-id store.
- `media_handler.py` reserves a source/file/user key and uses a provider-
  scoped logical media key. `media_gateway.py` then performs exact-key lookup
  and distinguishes reusable, incomplete, duplicate, and lookup-error
  states. This protects media upload/reuse and reconciliation, not arbitrary
  non-media writes.
- ActionContract execution has its own lifecycle/idempotency controls and
  remains the authority for governed action execution. These mechanisms must
  not be collapsed into the short-lived ingress guard or inferred from a
  successful HTTP response.
