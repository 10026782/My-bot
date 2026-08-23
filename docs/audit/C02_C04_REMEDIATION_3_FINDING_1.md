# C02–C04 Remediation 3 — Finding #1

## Historical finding — preserved

WhatsApp media download/processing failure is currently swallowed/logged,
while the webhook still returns provider acknowledgement success (HTTP 200 /
TwiML / "received"), creating a false-success interpretation.

Important distinction: provider acknowledgement is not the same as
business/media processing success.

## Truth-reset against current main

`START_SHA=2b0c08ed8782d6cafb02a1541036c9b74841ed34`.

- Twilio: `app.py:6343-6356` `webhook_whatsapp()` →
  `app.py:6354-6415` `_webhook_whatsapp_impl()` →
  `_validate_twilio_signature()` → `app.py:6415-6423`
  `extract_whatsapp_media()`/`download_whatsapp_media()` →
  `app.py:6429-6442` `handle_voice_note()` or `handle_file_upload()` →
  `app.py:6561-6568` `MessagingResponse` / HTTP 200. Download and
  handler exceptions were logged and the function continued to the normal
  reply path; a failed or missing result did not alter the TwiML ACK.
- Meta: `app.py:6575-6593` `webhook_meta_whatsapp()` →
  `_validate_meta_signature()` → `app.py:466-508` `_normalize_meta_payload()` →
  `app.py:6676-6715` Meta media URL fetch/download → `handle_voice_note()` or
  `handle_file_upload()` → `app.py:6749-6771` JSON HTTP 200. Download,
  extraction, and handler exceptions were logged; media processing occurred
  before the `META_OUTBOUND_ENABLED` guard and the response still reported
  `received` or `received_no_outbound`.

Evidence level: LIVE STRUCTURE CONFIRMED from current `origin/main`; no
provider or production runtime claim is made.

## Remediation note

The bounded `MediaProcessingStatus` object now distinguishes `COMPLETED`,
`FAILED`, and `NOT_COMPLETED`, carries `error_code`/`retryable`, and sets
`success_evidence=False` for every failed or incomplete path. Twilio retains
its valid TwiML/HTTP 200 provider acknowledgement, while the internal log
records the truthful processing status. Meta retains HTTP 200 acknowledgement
but includes the structured `media_processing` status in the JSON response.
Successful processing is the only path that emits `success_evidence=True`.

Final gap fix: when inbound Twilio media is present, adapter import failure and
outer metadata/extraction failure now also create a non-success status with an
explicit error code and retryability. Invalid metadata, empty download, and
handler failures remain covered by the same invariant.

No provider redelivery loop was introduced, no media/business write path was
redesigned, and ordinary WhatsApp text handling is unchanged. There is still
no durable processing-status record or reconciliation queue; retry/recovery
eligibility is explicit in the bounded result but automatic retry remains
deferred.

Status: implemented locally and locally verified; no production writes,
deployment, merge, or production verification.
